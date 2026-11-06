"""Tests for the Isaac Sim interface that do not require Isaac Sim itself.

The Isaac world model can be compiled without Isaac Sim installed, since the
simulator is only instantiated when a simulation is run.
"""

import bz2
import sys

import pytest
import trimesh

from tests.utils import compileScenic, pickle_test, sampleScene, tryPickling


def test_backend_registry():
    from scenic.simulators.isaac.backends import (
        DEFAULT_BACKEND_NAME,
        articulationAction,
        detectBackend,
        getBackend,
    )

    backend = getBackend(DEFAULT_BACKEND_NAME)
    assert backend is getBackend(None)
    assert backend.name == detectBackend()
    assert getBackend("core_51").name == "core_51"
    assert getBackend("lab").name == "lab"
    with pytest.raises(ValueError):
        getBackend("nonexistent")

    action = articulationAction(joint_velocities=[1, 2], joint_indices=[0, 1])
    assert action == {"joint_velocities": [1, 2], "joint_indices": [0, 1]}
    assert backend.articulationAction(joint_efforts=[3]) == {"joint_efforts": [3]}


def test_detect_backend_version_file_fallback(tmp_path, monkeypatch):
    """detectBackend must also recognize the plain ``VERSION`` file NVIDIA
    ships at the root of every Isaac Sim install: Isaac Sim's own bundled
    Python (as opposed to a pip install) has no pip metadata for the
    ``isaacsim`` package, so pip-metadata detection alone always misses it.

    Faking out both pip-metadata lookup and the ``isaacsim`` module itself
    makes this deterministic regardless of what is actually installed on the
    machine running the test.
    """
    import types

    from scenic.simulators.isaac import backends

    def _noPipMetadata():
        raise ModuleNotFoundError("no pip metadata in this test")

    monkeypatch.setattr(backends, "_majorVersionFromPipMetadata", _noPipMetadata)

    # A fake bundled install several directories below a VERSION file.
    package_dir = tmp_path / "python_packages" / "isaacsim"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("")
    fake_isaacsim = types.ModuleType("isaacsim")
    fake_isaacsim.__file__ = str(package_dir / "__init__.py")
    monkeypatch.setitem(sys.modules, "isaacsim", fake_isaacsim)

    (tmp_path / "VERSION").write_text("5.1.0.0\n")
    assert backends._majorVersionFromVersionFile() == "5"
    assert backends.detectBackend() == "core_51"

    (tmp_path / "VERSION").unlink()
    assert backends._majorVersionFromVersionFile() is None
    assert backends.detectBackend() == backends.FALLBACK_BACKEND_NAME


def test_orientation_conversion():
    """scenicToIsaacOrientation/isaacQuatToScenicEulerAngles must round-trip
    correctly for arbitrary combinations of yaw, pitch, and roll -- not just
    yaw -- both with and without an ``initial_rotation`` asset-frame
    correction (see model.scenic's built-in wheeled robots).
    """
    from scenic.core.vectors import Orientation
    from scenic.simulators.isaac.backends import getBackend

    backend = getBackend("core_51")
    orientations = ((0, 0, 0), (0.3, -0.2, 0.7), (2.0, 1.0, -2.5))
    initialRotations = (None, (0.5, 0.0, 0.0), (0.2, 0.6, -0.4), (-1.0, 0.3, 1.2))
    for angles in orientations:
        orientation = Orientation.fromEuler(*angles)
        quat = backend.scenicToIsaacOrientation(orientation)
        assert quat.shape == (4,)
        yaw, pitch, roll = backend.isaacQuatToScenicEulerAngles(quat)
        assert Orientation.fromEuler(yaw, pitch, roll).approxEq(orientation)

        for initial in initialRotations:
            if initial is None:
                continue
            # initial_rotation is composed in first, in the asset's local
            # frame; passing the same initial_rotation back to
            # isaacQuatToScenicEulerAngles must undo it and recover the
            # original orientation exactly.
            composed = backend.scenicToIsaacOrientation(
                orientation, initial_rotation=initial
            )
            recovered = backend.isaacQuatToScenicEulerAngles(
                composed, initial_rotation=initial
            )
            assert Orientation.fromEuler(*recovered).approxEq(orientation)

            # Without undoing initial_rotation, the raw spawned orientation is
            # orientation composed with initial_rotation, not the original.
            raw = backend.isaacQuatToScenicEulerAngles(composed)
            expected = orientation * Orientation.fromEuler(*initial)
            assert Orientation.fromEuler(*raw).approxEq(expected)


def test_compressed_paths(tmp_path, monkeypatch):
    from scenic.simulators.isaac import utils

    monkeypatch.setattr(utils.Path, "home", lambda: tmp_path / "home")

    assert utils.assetStem("a/b/simple_room.usd.bz2") == "simple_room"
    assert utils.assetStem("Isaac/Props/KLT_Bin/small_KLT.usd") == "small_KLT"
    mesh_path, info_path = utils.defaultEnvironmentMeshPaths(tmp_path / "room.usd.bz2")
    assert mesh_path == tmp_path / "_converted" / "room_usd.glb.bz2"
    assert info_path == tmp_path / "_converted" / "room_info.json"
    mesh_path, _ = utils.defaultEnvironmentMeshPaths("Isaac/Environments/x/y.usd")
    assert mesh_path.name == "y_usd.glb.bz2" and tmp_path / "home" in mesh_path.parents

    # A Windows drive letter is not a URL scheme, on any platform.
    assert not utils.hasUrlScheme(r"C:\assets\room.usd")
    assert not utils.hasUrlScheme("C:/assets/room.usd")
    assert utils.hasUrlScheme("https://example.com/room.usd")

    plain = tmp_path / "asset.usda"
    plain.write_text("#usda 1.0\n")
    assert utils.decompressedPath(plain) == plain
    compressed = utils.compressFile(plain, remove_source=True)
    assert compressed == tmp_path / "asset.usda.bz2" and not plain.exists()
    decompressed = utils.decompressedPath(compressed)
    assert decompressed.name == "asset.usda" and decompressed.read_text() == "#usda 1.0\n"
    assert utils.decompressedPath(compressed) == decompressed  # cached


def test_compressed_meshes(tmp_path):
    from scenic.simulators.isaac import utils

    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.box((1, 2, 3)), node_name="prim_0")
    scene.add_geometry(
        trimesh.creation.icosphere(),
        node_name="prim_1",
        transform=trimesh.transformations.translation_matrix([5, 0, 0]),
    )
    path = utils.writeMesh(scene, tmp_path / "scene_usd.glb.bz2")
    with bz2.open(path, "rb") as in_file:
        assert in_file.read(4) == b"glTF"

    loaded = trimesh.load(path, force="scene")
    assert sorted(loaded.graph.nodes_geometry) == ["prim_0", "prim_1"]
    assert loaded.graph.get("prim_1")[0][0, 3] == pytest.approx(5)

    mesh = utils.loadAssetMesh(path)
    assert mesh.is_volume

    assert compileScenic(
        f"""
        model scenic.simulators.isaac.model
        from scenic.simulators.isaac.utils import loadAssetMesh
        ego = new IsaacSimObject with shape MeshShape(loadAssetMesh({str(path)!r}))
        """
    )


def test_basic(loadLocalScenario):
    scenario = loadLocalScenario("basic.scenic")
    scene = sampleScene(scenario, maxIterations=1000)
    assert len(scene.objects) == 5
    assert scene.egoObject.wheelController == "differential"
    robot = next(obj for obj in scene.objects if obj.blueprint == "Robot" and obj.control)
    assert robot.wheelController is None
    assert robot.control([1.0, 0.5]) == {
        "joint_velocities": [0.5, 1.5],
        "joint_indices": [0, 1],
    }


def test_isaac_lab_params():
    scenario = compileScenic(
        """
        param isaacLab = True
        param labNumEnvs = 4
        model scenic.simulators.isaac.model
        floor = new GroundPlane
        ego = new Jetbot on floor, with behavior JetbotDrive
        """
    )
    scene = sampleScene(scenario, maxIterations=100)
    assert scene.params["labNumEnvs"] == 4
    assert scene.egoObject.wheelDofNames == ["left_wheel_joint", "right_wheel_joint"]


@pickle_test
@pytest.mark.slow
def test_pickle(loadLocalScenario):
    scenario = tryPickling(loadLocalScenario("basic.scenic"))
    tryPickling(sampleScene(scenario, maxIterations=1000))
