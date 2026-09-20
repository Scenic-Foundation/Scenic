from pathlib import Path

import numpy
import pytest
import trimesh

from scenic.core.utils import cached, cached_method, repairMesh, unifyMesh


@pytest.mark.slow
def test_mesh_repair(getAssetPath):
    plane_mesh = trimesh.load(getAssetPath("meshes/classic_plane.obj.bz2"), force="mesh")
    # Test simple fix
    inverted_mesh = plane_mesh.copy()
    inverted_mesh.invert()
    assert not inverted_mesh.is_volume
    inverted_mesh = repairMesh(inverted_mesh, verbose=False)
    assert inverted_mesh.is_volume
    assert numpy.allclose(inverted_mesh.bounds, plane_mesh.bounds)
    assert numpy.allclose(
        numpy.mean(inverted_mesh.bounds, axis=0), numpy.mean(plane_mesh.bounds, axis=0)
    )

    # Test missing faces
    broken_mesh = plane_mesh.copy()
    broken_mesh.faces = broken_mesh.faces[40:]
    assert not broken_mesh.is_volume
    broken_mesh = repairMesh(broken_mesh, verbose=False)
    assert broken_mesh.is_volume
    assert numpy.allclose(broken_mesh.bounds, plane_mesh.bounds)
    assert numpy.allclose(
        numpy.mean(broken_mesh.bounds, axis=0), numpy.mean(plane_mesh.bounds, axis=0)
    )

    # Test a planar mesh, which should raise an error.
    plane = trimesh.Trimesh(
        vertices=[(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
        faces=[(0, 1, 2), (0, 2, 3)],
    )

    with pytest.raises(ValueError):
        repairMesh(plane)


@pytest.mark.slow
def test_unify_mesh():
    # Create nested sphere
    nested_sphere = (
        trimesh.creation.icosphere(radius=5)
        .difference(trimesh.creation.icosphere(radius=4))
        .union(trimesh.creation.icosphere(radius=3))
        .difference(trimesh.creation.icosphere(radius=2))
    )

    # Manually append a box
    bad_mesh = trimesh.util.concatenate(
        nested_sphere, trimesh.creation.box(bounds=((0, 0, 0), (3, 5, 3)))
    )

    fixed_mesh = unifyMesh(bad_mesh)
    assert fixed_mesh.is_volume
    assert fixed_mesh.body_count == 3


def test_cached_method():
    calls = []

    class Foo:
        @cached_method
        def bar(self, x):
            calls.append(x)
            return 2 * x

    foo, other = Foo(), Foo()
    assert foo.bar(1) == 2
    assert foo.bar(1) == 2
    assert calls == [1]
    # Different arguments get different cache entries...
    assert foo.bar(3) == 6
    assert calls == [1, 3]
    assert foo.bar(1) == 2
    assert foo.bar(3) == 6
    assert calls == [1, 3]
    # ...as do different objects...
    assert other.bar(1) == 2
    assert calls == [1, 3, 1]
    # ...and clearing one object's cache leaves the other's alone.
    Foo.bar._scenic_cache_clearer(foo)
    assert foo.bar(1) == 2
    assert foo.bar(3) == 6
    assert calls == [1, 3, 1, 1, 3]
    assert other.bar(1) == 2
    assert calls == [1, 3, 1, 1, 3]
    Foo.bar._scenic_cache_clearer(Foo())  # object with no caches at all


def test_cached():
    calls = 0

    class Foo:
        @cached
        def bar(self):
            nonlocal calls
            calls += 1
            return 42

    foo = Foo()
    assert foo.bar() == 42
    assert foo.bar() == 42
    assert calls == 1
    clearer = Foo.bar._scenic_cache_clearer
    assert getattr(foo, clearer._scenic_cache_attr) == 42
    clearer(foo)
    assert not hasattr(foo, clearer._scenic_cache_attr)
    clearer(foo)  # clearing an already-empty cache does nothing
    assert foo.bar() == 42
    assert calls == 2
