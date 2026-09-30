"""Helpers shared by the Isaac Sim model, simulators, and backends."""

import bz2
import hashlib
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlparse

import numpy as np
import trimesh

from scenic.core.utils import repairMesh

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def resolvedPath(path):
    return Path(os.fspath(path)).expanduser().resolve()


COMPRESSED_SUFFIX = ".bz2"


def isCompressed(path):
    return os.fspath(path).endswith(COMPRESSED_SUFFIX)


def uncompressedName(path):
    """The file name of ``path`` without a trailing ``.bz2``."""
    name = Path(urlparse(os.fspath(path)).path).name
    if name.endswith(COMPRESSED_SUFFIX):
        name = name[: -len(COMPRESSED_SUFFIX)]
    return name


def assetStem(path):
    """The stem of an asset path, ignoring compression: ``a/b.usd.bz2`` -> ``b``."""
    return Path(uncompressedName(path)).stem


def compressFile(source, target=None, *, remove_source=False):
    """bz2-compress ``source`` into ``target`` (default: ``source`` + ``.bz2``)."""
    source = Path(source)
    target = Path(target) if target else source.with_name(source.name + COMPRESSED_SUFFIX)
    with open(source, "rb") as in_file, bz2.open(target, "wb") as out_file:
        shutil.copyfileobj(in_file, out_file)
    if remove_source:
        source.unlink()
    return target


def _cacheDir(*parts):
    return Path.home().joinpath(".cache", "scenic", "isaac", *parts)


def decompressedPath(path):
    """Return a plain-file path for ``path``, decompressing a ``.bz2`` file if needed.

    Compressed files are decompressed once into ``~/.cache/scenic/isaac`` and
    reused while the compressed file is unchanged. Since the decompressed copy
    lives elsewhere, a compressed USD must be self-contained (e.g. flattened).
    """
    source = resolvedPath(path)
    if not isCompressed(source):
        return source

    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:12]
    target = _cacheDir("decompressed", digest, uncompressedName(source))
    if not target.is_file() or target.stat().st_mtime < source.stat().st_mtime:
        target.parent.mkdir(parents=True, exist_ok=True)
        with bz2.open(source, "rb") as in_file, open(target, "wb") as out_file:
            shutil.copyfileobj(in_file, out_file)
    return target


def isIsaacAssetReference(path):
    """Whether ``path`` is relative to the Isaac assets root (``Isaac/...``)."""
    return os.fspath(path).startswith("Isaac/")


def hasUrlScheme(path):
    """Whether ``path`` is a URL rather than a local file path.

    A one-character scheme is a Windows drive letter (``C:\\assets\\room.usd``),
    which :func:`urlparse` happily reports as the scheme ``c``.
    """
    return len(urlparse(os.fspath(path)).scheme) > 1


#: Suffix of converted meshes: a self-contained binary glTF, bz2-compressed.
CONVERTED_MESH_SUFFIX = ".glb" + COMPRESSED_SUFFIX


def convertedMeshPaths(source, output_dir):
    """Names of the converted mesh and info JSON for an asset in ``output_dir``."""
    stem = assetStem(source) or "environment"
    output_dir = Path(output_dir)
    return (
        output_dir / f"{stem}_usd{CONVERTED_MESH_SUFFIX}",
        output_dir / f"{stem}_info.json",
    )


def defaultEnvironmentMeshPaths(environmentUsdPath):
    """Where the converted mesh and info JSON for an environment USD are cached.

    Local USDs are converted next to the source (in a ``_converted`` folder);
    Isaac asset references and URLs are cached under ``~/.cache/scenic``.
    """
    source = os.fspath(environmentUsdPath)

    if isIsaacAssetReference(source) or hasUrlScheme(source):
        digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
        stem = assetStem(source) or "environment"
        output_dir = _cacheDir("environments", f"{stem}_{digest}")
    else:
        output_dir = resolvedPath(source).parent / "_converted"

    return convertedMeshPaths(source, output_dir)


def environmentOutputsCurrent(environmentUsdPath, mesh_path, info_path):
    """Whether cached conversion outputs exist and are newer than a local source USD."""
    mesh_path = Path(mesh_path)
    info_path = Path(info_path)
    if not mesh_path.is_file() or not info_path.is_file():
        return False

    source = os.fspath(environmentUsdPath)
    if isIsaacAssetReference(source) or hasUrlScheme(source):
        return True

    usd_path = resolvedPath(source)
    if not usd_path.is_file():
        return False

    source_mtime = usd_path.stat().st_mtime
    return (
        mesh_path.stat().st_mtime >= source_mtime
        and info_path.stat().st_mtime >= source_mtime
    )


# ---------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------


def vectorToArray(vector):
    return np.array((vector.x, vector.y, vector.z), dtype=float)


def writeMesh(mesh, path):
    """Export a trimesh mesh or scene to ``path``, bz2-compressing if it ends in ``.bz2``.

    The format is taken from the extension (``.glb`` recommended: unlike
    ``.gltf`` it is a single self-contained file).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isCompressed(path):
        mesh.export(path)
        return path
    file_type = Path(uncompressedName(path)).suffix.lstrip(".")
    data = mesh.export(file_type=file_type)
    if isinstance(data, str):
        data = data.encode("utf-8")
    with bz2.open(path, "wb") as out_file:
        out_file.write(data)
    return path


def loadAssetMesh(path):
    """Load a converted asset mesh (e.g. ``foo_usd.glb.bz2``) as one volumetric mesh.

    Suitable for ``MeshShape``: the mesh is repaired if it has no well-defined
    volume. ``trimesh`` handles the compression.
    """
    return repairMesh(trimesh.load(path, force="mesh"))


def colorToArray(color):
    return np.array(color, dtype=float) if color else None


def meshToObjFrame(mesh):
    """Rotate a Z-up mesh into the Y-up frame the OBJ asset converter assumes."""
    obj_mesh = mesh.copy()
    transform = trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0))
    obj_mesh.apply_transform(transform)
    return obj_mesh


def planeToMesh(mesh):
    """Extrude a planar mesh into a thin volume so it has a well-defined interior."""
    normal = mesh.face_normals[0]
    polygon = trimesh.path.polygons.projected(mesh, normal=normal)
    extruded = trimesh.creation.extrude_polygon(polygon, height=0.01)

    z_axis = np.array([0, 0, 1])
    rotation = trimesh.geometry.align_vectors(z_axis, normal)
    extruded.apply_transform(rotation)
    return extruded


def isPlanar(mesh, tolerance=1e-3):
    plane_origin, plane_normal = trimesh.points.plane_fit(mesh.vertices)
    distances = np.abs(np.dot(mesh.vertices - plane_origin, plane_normal))
    return np.all(distances <= tolerance)


class EnvironmentMeshCache:
    """Persistent cache for repaired Scenic meshes from a converted environment.

    Repairing every prim of a large environment into a watertight volume is
    slow, so results are stored next to the converted mesh and reused while
    the mesh and info files are unchanged.
    """

    version = 2

    def __init__(self, environment_mesh_path, environment_info_path):
        self.environment_mesh_path = Path(environment_mesh_path)
        self.environment_info_path = Path(environment_info_path)
        self.cache_dir = self.environment_mesh_path.parent / (
            f"{assetStem(self.environment_mesh_path)}_repaired"
        )
        self.manifest_path = self.cache_dir / "manifest.json"
        self.sources = self._sourceSignatures()
        self.manifest = self._loadManifest()
        self.changed = False

    def get(self, node_name, mesh):
        cache_file = self._cacheFile(node_name)
        if self._manifestCurrent() and cache_file.is_file():
            try:
                cached = trimesh.load(cache_file, force="mesh", process=False)
                if cached.is_volume:
                    return cached
            except Exception:
                pass

        repaired = self._repairMesh(mesh)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        repaired.export(cache_file)
        self.manifest["nodes"][node_name] = cache_file.name
        self.changed = True
        return repaired

    def save(self):
        if not self.changed:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest.update({"version": self.version, "sources": self.sources})
        with open(self.manifest_path, "w") as out_file:
            json.dump(self.manifest, out_file, indent=2)
        self.changed = False

    def _cacheFile(self, node_name):
        digest = hashlib.sha1(node_name.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{digest}.ply"

    def _loadManifest(self):
        default = {"version": self.version, "sources": self.sources, "nodes": {}}
        try:
            with open(self.manifest_path, "r") as in_file:
                manifest = json.load(in_file)
        except Exception:
            return default

        if not isinstance(manifest, dict) or "nodes" not in manifest:
            return default
        return manifest

    def _manifestCurrent(self):
        return (
            self.manifest.get("version") == self.version
            and self.manifest.get("sources") == self.sources
        )

    def _sourceSignatures(self):
        return {
            str(path): {"mtime_ns": path.stat().st_mtime_ns, "size": path.stat().st_size}
            for path in (self.environment_mesh_path, self.environment_info_path)
        }

    def _repairMesh(self, mesh):
        mesh = mesh.copy()
        if isPlanar(mesh):
            mesh = planeToMesh(mesh)
        mesh.apply_scale(0.01)
        return repairMesh(mesh)


# ---------------------------------------------------------------------------
# Existing environment objects
# ---------------------------------------------------------------------------

# Objects the model created for prims of the loaded environment USD, keyed by
# both prim path and name so scenarios can look them up either way.
_existingObj = {}


def _addExistingObj(obj):
    for key in (obj.primPath, obj.name):
        if key is not None:
            _existingObj[str(key)] = obj


def getExistingObj(objName):
    """Return the `ExistingIsaacSimObject` for a prim path (or name) in the environment."""
    try:
        return _existingObj[objName]
    except KeyError as exc:
        available = ", ".join(sorted(_existingObj)) or "none"
        raise KeyError(
            f"no existing Isaac Sim object registered for {objName!r}; "
            f"available objects: {available}"
        ) from exc


def existingObjects():
    """Return each registered existing Isaac object once."""
    objs_by_prim_path = {}
    for obj in _existingObj.values():
        if obj.primPath is not None:
            objs_by_prim_path[str(obj.primPath)] = obj
    return tuple(objs_by_prim_path.values())
