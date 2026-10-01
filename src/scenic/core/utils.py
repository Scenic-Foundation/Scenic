"""Assorted utility functions."""

import bz2
import collections
from contextlib import contextmanager
import functools
import io
import itertools
import math
import multiprocessing
import os
import random
import signal
from subprocess import CalledProcessError
import sys
import typing
import warnings
import weakref

import numpy
import trimesh

sqrt2 = math.sqrt(2)

if sys.version_info >= (3, 12):
    from itertools import batched
else:

    def batched(iterable, n):
        if n < 1:
            raise ValueError("n must be at least one")
        it = iter(iterable)
        while batch := tuple(itertools.islice(it, n)):
            yield batch


def cached(oldMethod):
    """Decorator for making a method with no arguments cache its result"""
    storageName = f"_cached_{oldMethod.__name__}"

    @functools.wraps(oldMethod)
    def wrapper(self):
        try:
            # Use __getattribute__ for direct lookup in case self is a Distribution
            return self.__getattribute__(storageName)
        except AttributeError:
            value = oldMethod(self)
            setattr(self, storageName, value)
            return value

    def clearer(self):
        try:
            delattr(self, storageName)
        except AttributeError:
            pass

    wrapper._scenic_cache_clearer = clearer

    return wrapper


_methodCaches = weakref.WeakKeyDictionary()


def cached_method(oldMethod):
    """Decorator for making a method cache its result on a per-object basis.

    Like ``functools.lru_cache(maxsize=None)`` except using a separate cache
    for each object, with the cache automatically deallocated when the object
    is garbage collected.
    """
    name = oldMethod.__name__

    @functools.wraps(oldMethod)
    def wrapper(self, *args, **kwargs):
        caches = _methodCaches.get(self, collections.defaultdict(dict))
        cachedMethod = caches.get(name)
        if cachedMethod is None:
            cachedMethod = functools.lru_cache(maxsize=None)(oldMethod)
            caches[name] = cachedMethod
        return cachedMethod(self, *args, **kwargs)

    def clearer(self):
        caches = _methodCaches.get(self, collections.defaultdict(dict))
        cachedMethod = caches.get(name)
        if cachedMethod:
            cachedMethod.cache_clear()

    wrapper._scenic_cache_clearer = clearer

    return wrapper


def cached_property(oldMethod):
    return property(cached(oldMethod))


def argsToString(args, kwargs={}):
    args = ", ".join(repr(arg) for arg in args)
    kwargs = ", ".join(f"{name}={value!r}" for name, value in kwargs.items())
    parts = []
    if args:
        parts.append(args)
    if kwargs:
        parts.append(kwargs)
    return ", ".join(parts)


@contextmanager
def alarm(seconds, handler=None, noNesting=False):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):  # SIGALRM not supported on Windows
        yield
        return
    if handler is None:
        handler = signal.SIG_IGN
    signal.signal(signal.SIGALRM, handler)
    if noNesting:
        assert oldHandler is signal.SIG_DFL, "SIGALRM handler already installed"
    length = int(math.ceil(seconds))
    previous = signal.alarm(length)
    if noNesting:
        assert previous == 0, 'nested call to "alarm"'
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


def unifyMesh(mesh, verbose=False):
    """Attempt to merge mesh bodies, raising a `ValueError` if something fails.

    Should only be used with meshes that are volumes.

    If a mesh is composed of multiple bodies, the following process
    is applied:
    1. Split mesh into volumes and holes.
    2. From each volume, subtract each hole that is fully contained.
    3. Union all the resulting volumes.
    """
    assert mesh.is_volume

    # No need to unify a mesh with less than 2 bodies
    if mesh.body_count < 2:
        return mesh

    mesh_bodies = mesh.split()

    if all(m.is_volume for m in mesh_bodies):
        # If all mesh bodies are volumes, we can just return the union.
        unified_mesh = trimesh.boolean.union(mesh_bodies)

    else:
        # Split the mesh bodies into volumes and holes.
        volumes = []
        holes = []
        for m in mesh_bodies:
            if m.is_volume:
                volumes.append(m)
            else:
                m.fix_normals()
                assert m.is_volume
                holes.append(m)

        # For each volume, subtract all holes fully contained in the volume,
        # keeping track of which holes are fully contained in at least one solid.
        differenced_volumes = []
        contained_holes = set()

        for v in volumes:
            for h in filter(lambda h: h.volume < v.volume, holes):
                if h.difference(v).is_empty:
                    contained_holes.add(h)
                    v = v.difference(h)
            differenced_volumes.append(v)

        # If one or more holes was not fully contained (and thus ignored),
        # raise a warning.
        if verbose:
            if contained_holes != set(holes):
                warnings.warn(
                    "One or more holes in the provided mesh was not fully contained"
                    " in any solid (and was ignored)."
                )

        # Union all the differenced volumes together.
        unified_mesh = trimesh.boolean.union(differenced_volumes)

    # Check that the output is still a valid mesh
    if unified_mesh.is_volume:
        if verbose:
            if unified_mesh.body_count == 1:
                warnings.warn(
                    "The mesh that you loaded was composed of multiple bodies,"
                    " but Scenic was able to unify it into one single body (though"
                    " you should verify that the result is correct). To save on compile"
                    " time in the future, consider running unifyMesh on your mesh outside"
                    " of Scenic and using that output instead."
                )
            elif unified_mesh.body_count < mesh.body_count:
                warnings.warn(
                    "The mesh that you loaded was composed of multiple bodies,"
                    " but Scenic was able to unify it into fewer bodies (though"
                    " you should verify that the result is correct). To save on compile"
                    " time in the future, consider running unifyMesh on your mesh outside"
                    " of Scenic and using that output instead."
                )

        return unified_mesh
    else:
        raise ValueError("Unable to unify mesh.")


def repairMesh(mesh, pitch=(1 / 2) ** 6, verbose=True):
    """Attempt to repair a mesh, returning a proper 2-manifold.

    Repair is attempted via several steps, each sacrificing more accuracy
    but with a higher chance of returning a proper volumetric mesh.

    Repair is first attempted with easy fixes, like merging vertices and fixing
    winding. These will usually not deteriorate the quality of the mesh.

    Repair is then attempted by voxelizing the mesh, filling it, and then running
    marching cubes on the mesh. This approach is somewhat accurate but always
    produces solid objects. (This is to be expected since non watertight hollow
    objects aren't well defined).

    Repair is finally attempted by using the convex hull, which is unlikely to
    be accurate but is guaranteed to result in a volume.

    NOTE: For planar meshes, this function will throw an error.

    Args:
        mesh: The input mesh to be repaired.
        pitch: The target pitch to be used when attempting to repair the mesh via
            voxelization. A lower pitch uses smaller voxels, and thus a closer
            approximation, but can require significant additional processsing time.
            The actual pitch used may be larger if needed to get a manifold mesh.
        verbose: Whether or not to print warnings describing attempts to repair the mesh.
    """
    # If mesh is already a volume, we're done.
    if mesh.is_volume:
        return mesh

    # If mesh is planar, we can't fix it.
    if numpy.any(mesh.extents == 0):
        raise ValueError("repairMesh is undefined for planar meshes.")

    # Pitch must be positive
    if pitch <= 0:
        raise ValueError("pitch parameter must be positive.")

    ## Trimesh Processing ##
    processed_mesh = mesh.process(validate=True, merge_tex=True, merge_norm=True).copy()

    if processed_mesh.is_volume:
        if verbose:
            warnings.warn("Mesh was repaired via Trimesh process function.")

        return processed_mesh

    if verbose:
        warnings.warn(
            "Mesh could not be repaired via Trimesh process function."
            " attempting voxelization + marching cubes."
        )

    ## Voxelization + Marching Cubes ##
    # Extract largest dimension and scale so that it is unit length
    dims = numpy.abs(processed_mesh.extents)
    position = processed_mesh.bounding_box.center_mass
    scale = numpy.max(dims)

    processed_mesh.vertices -= position

    scale_matrix = numpy.eye(4)
    scale_matrix[:3, :3] /= scale
    processed_mesh.apply_transform(scale_matrix)

    # Compute new mesh with largest possible pitch
    curr_pitch = pitch

    while curr_pitch < 1:
        new_mesh = processed_mesh.voxelized(pitch=curr_pitch).fill().marching_cubes

        if new_mesh.is_volume:
            if verbose:
                warnings.warn(
                    f"Mesh was repaired via voxelization + marching cubes"
                    f" with pitch {curr_pitch}. Check the output to ensure it"
                    f" looks reasonable."
                )

            # Center new mesh
            new_mesh.vertices -= new_mesh.bounding_box.center_mass

            # Rescale mesh to original size
            orig_scale = new_mesh.extents / dims
            scale_matrix = numpy.eye(4)
            scale_matrix[:3, :3] /= orig_scale
            new_mesh.apply_transform(scale_matrix)

            # # Return mesh center to original position
            new_mesh.vertices += position

            return new_mesh

        curr_pitch *= 2

    raise ValueError("Mesh could not be repaired.")


def findMeshInteriorPoint(mesh, num_samples=None):
    # Use center of mass if it's contained
    com = mesh.bounding_box.center_mass
    if mesh.contains([com])[0]:
        return com

    # Try sampling a point inside the volume
    if num_samples is None:
        p_volume = mesh.volume / mesh.bounding_box.volume
        if p_volume > 0.99:
            num_samples = 1
        else:
            num_samples = math.ceil(min(1e6, max(1, math.log(0.01, 1 - p_volume))))

    # Do the "random" number generation ourselves so that it's deterministic
    # (this helps debugging and reproducibility)
    rng = numpy.random.default_rng(49493130352093220597973654454967996892)
    pts = (rng.random((num_samples, 3)) * mesh.extents) + mesh.bounds[0]
    samples = pts[mesh.contains(pts)]
    if samples.size > 0:
        return samples[0]

    # If all else fails, take a point from the surface and move inward
    surfacePt, index = list(zip(*mesh.sample(1, return_index=True)))[0]
    inward = -mesh.face_normals[index]
    startPt = surfacePt + 1e-6 * inward
    hits, _, _ = mesh.ray.intersects_location(
        ray_origins=[startPt],
        ray_directions=[inward],
        multiple_hits=False,
    )
    if hits.size > 0:
        endPt = hits[0]
        midPt = (surfacePt + endPt) / 2.0
        if mesh.contains([midPt])[0]:
            return midPt

    # Should never get here with reasonable geometry, but we return a surface
    # point just in case.
    return surfacePt  # pragma: no cover


class DefaultIdentityDict:
    """Dictionary which is the identity map by default.

    The map works on all objects, even unhashable ones, but doesn't support all
    of the standard mapping operations.
    """

    def __init__(self):
        self.storage = {}

    def clear(self):
        self.storage.clear()

    def __getitem__(self, key):
        return self.storage.get(id(key), key)

    def __setitem__(self, key, value):
        self.storage[id(key)] = value

    def __contains__(self, key):
        return id(key) in self.storage

    def __repr__(self):
        pairs = (f"{hex(key)}: {value!r}" for key, value in self.storage.items())
        allPairs = ", ".join(pairs)
        return f"<DefaultIdentityDict {{{allPairs}}}>"


# Patched version of typing.get_type_hints fixing bpo-37838

if sys.version_info >= (3, 8, 1) or (
    sys.version_info < (3, 8) and sys.version_info >= (3, 7, 6)
):
    get_type_hints = typing.get_type_hints
else:
    import types

    def get_type_hints(obj, globalns=None, localns=None):
        if not isinstance(obj, (type, types.ModuleType)) and globalns is None:
            wrapped = obj
            while hasattr(wrapped, "__wrapped__"):
                wrapped = wrapped.__wrapped__
            globalns = getattr(wrapped, "__globals__", {})
        return typing.get_type_hints(obj, globalns, localns)


def setSeed(seed):
    """Set the random seed used by Scenic"""
    random.seed(seed)
    numpy.random.seed(seed)
