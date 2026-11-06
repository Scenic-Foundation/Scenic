import asyncio
import atexit
import os

import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from scenic.core.simulators import SimulationCreationError
from scenic.core.vectors import Orientation, Vector
from scenic.simulators.isaac.actions import _Robot
from scenic.simulators.isaac.backends.robotiq import requireStagePrim
import scenic.simulators.isaac.utils as scenic_utils

#: Values of ``wheelController`` handled by the built-in wheeled-robot support.
WHEEL_CONTROLLERS = frozenset({"differential", "holonomic", "ackermann"})


def isWheeledRobot(obj):
    # wheelController is only declared on IsaacSimRobot, so check isinstance
    # first: this is called on every object in the scene, robot or not.
    return isinstance(obj, _Robot) and obj.wheelController in WHEEL_CONTROLLERS


def positionArray(position):
    """Convert a Scenic Vector or any 3-sequence to a numpy array."""
    if isinstance(position, Vector):
        return scenic_utils.vectorToArray(position)
    return np.asarray(position, dtype=float).reshape(-1)[:3]


def wxyzToRotation(quat_wxyz):
    """Convert one or more Isaac/USD scalar-first quaternions to a scipy Rotation."""
    return Rotation.from_quat(np.roll(np.asarray(quat_wxyz, dtype=float), -1, axis=-1))


def rotationToWxyz(rotation):
    """Convert a scipy Rotation to an Isaac/USD scalar-first quaternion array."""
    return np.roll(rotation.as_quat(), 1, axis=-1)


class IsaacBackend:
    """Interface implemented by Isaac Sim API backends.

    Methods raising `NotImplementedError` must be provided by each backend;
    the rest are shared helpers that only depend on USD (``pxr``) or on APIs
    common to every supported Isaac Sim release.
    """

    name = None

    def __init__(self):
        self._simulation_app = None

    # ------------------------------------------------------------------
    # Simulation app lifecycle
    # ------------------------------------------------------------------

    def _simulationAppConfig(self, headless):
        return {
            "headless": headless,
            "sync_loads": True,
            "fast_shutdown": True,
            "multi_gpu": False,
            "max_gpu_count": 1,
        }

    def getSimulationApp(self, headless=False):
        if self._simulation_app is None:
            from isaacsim.simulation_app import SimulationApp

            self._simulation_app = SimulationApp(
                launch_config=self._simulationAppConfig(headless)
            )
            atexit.register(self._closeSimulationAppAtExit)
        return self._simulation_app

    def attachSimulationApp(self, app):
        """Use an already-running app (e.g. the Isaac editor) instead of launching one."""
        self._simulation_app = app

    def closeSimulationApp(self, app):
        app.close()
        if app is self._simulation_app:
            self._simulation_app = None

    def _closeSimulationAppAtExit(self):
        if self._simulation_app is not None:
            self.closeSimulationApp(self._simulation_app)

    def kitAppRunning(self):
        try:
            import omni.kit.app

            return omni.kit.app.get_app() is not None
        except Exception:
            return False

    def updateApp(self, app):
        app.update()

    def enableExtension(self, name):
        raise NotImplementedError

    def isStageLoading(self):
        from isaacsim.core.utils.stage import is_stage_loading

        return is_stage_loading()

    def setupLighting(self, headless):
        if headless:
            return
        import omni.kit.actions.core

        action = omni.kit.actions.core.get_action_registry().get_action(
            "omni.kit.viewport.menubar.lighting", "set_lighting_mode_camera"
        )
        if action is not None:
            action.execute()

    # ------------------------------------------------------------------
    # World lifecycle
    # ------------------------------------------------------------------

    def createWorld(self, timestep):
        raise NotImplementedError

    def openEnvironmentStage(self, usd_path):
        raise NotImplementedError

    def initializePhysics(self, world, objects):
        raise NotImplementedError

    def playWorld(self, world):
        raise NotImplementedError

    def stepWorld(self, world):
        raise NotImplementedError

    def stopAndClearWorld(self, world):
        raise NotImplementedError

    def releaseWorld(self, world):
        pass

    def addObject(self, world, obj, *, scenic_obj=None):
        pass

    # ------------------------------------------------------------------
    # Asset paths and conversion
    # ------------------------------------------------------------------

    def getAssetsRootPath(self):
        from isaacsim.storage.native import get_assets_root_path

        return get_assets_root_path()

    def assetPath(self, relative_path):
        return f"{self.getAssetsRootPath()}/{relative_path}"

    def kitUsdPath(self, path):
        """Resolve an ``Isaac/...`` asset reference, URL, or local path for Kit.

        A bz2-compressed local USD is decompressed into a cache first.
        """
        source = os.fspath(path)
        if scenic_utils.isIsaacAssetReference(source):
            return self.assetPath(source)
        if scenic_utils.hasUrlScheme(source):
            return source
        return str(scenic_utils.decompressedPath(source))

    def objectUsdPath(self, obj):
        """Return the USD path to spawn for an object with ``usdPath``/``isaacAssetPath``."""
        source = obj.isaacAssetPath or obj.usdPath
        if not source:
            raise SimulationCreationError(
                f"{obj.name} needs a usdPath or isaacAssetPath to be created in Isaac Sim"
            )
        return self.kitUsdPath(source)

    async def convert(self, in_file, out_file, load_materials=False):
        import omni.kit.asset_converter

        def progressCallback(progress, total_steps):
            pass

        converter_context = omni.kit.asset_converter.AssetConverterContext()
        converter_context.ignore_materials = not load_materials
        converter_context.ignore_animation = False
        converter_context.ignore_cameras = True
        converter_context.use_meter_as_world_unit = True
        converter_context.create_world_as_default_root_prim = True
        instance = omni.kit.asset_converter.get_instance()
        task = instance.create_converter_task(
            in_file, out_file, progressCallback, converter_context
        )
        while True:
            success = await task.wait_until_finished()
            if success:
                return True
            await asyncio.sleep(0.1)

    def runCoroutine(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import omni.kit.app

            task = loop.create_task(coro)
            app = omni.kit.app.get_app()
            while not task.done():
                app.update()
            return task.result()

        return loop.run_until_complete(coro)

    def convertSync(self, in_file, out_file, load_materials=False):
        return self.runCoroutine(
            self.convert(in_file, out_file, load_materials=load_materials)
        )

    def exportMeshToUsd(self, mesh, name, tmp_dir):
        """Write a trimesh to ``tmp_dir`` as OBJ and convert it to a USD asset."""
        os.makedirs(tmp_dir, exist_ok=True)
        obj_path = os.path.join(tmp_dir, f"{name}.obj")
        usd_path = os.path.join(tmp_dir, f"{name}.usd")
        trimesh.exchange.export.export_mesh(mesh, obj_path)
        if not self.convertSync(obj_path, usd_path, load_materials=True):
            raise SimulationCreationError(
                f"Unable to convert the mesh for {name} into a USD asset"
            )
        return usd_path

    def ensureEnvironmentMeshPaths(
        self,
        environmentUsdPath,
        environment_mesh_path=None,
        environment_info_path=None,
        *,
        headless=True,
        overwrite=False,
    ):
        """Return (mesh, info) paths for an environment USD, converting it if needed.

        The converted GLTF mesh and JSON prim metadata are what the Scenic
        model uses to reason about existing objects in the environment.
        """
        default_mesh_path, default_info_path = scenic_utils.defaultEnvironmentMeshPaths(
            environmentUsdPath
        )
        mesh_path = (
            scenic_utils.resolvedPath(environment_mesh_path)
            if environment_mesh_path
            else default_mesh_path
        )
        info_path = (
            scenic_utils.resolvedPath(environment_info_path)
            if environment_info_path
            else default_info_path
        )

        if not overwrite and scenic_utils.environmentOutputsCurrent(
            environmentUsdPath, mesh_path, info_path
        ):
            return mesh_path, info_path

        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        info_path.parent.mkdir(parents=True, exist_ok=True)

        self._prepareAppForConversion(headless)
        self.enableExtension("omni.kit.asset_converter")
        from scenic.simulators.isaac.usd_conversion import convertEnvironmentUsd

        convertEnvironmentUsd(
            self.kitUsdPath(environmentUsdPath),
            str(mesh_path),
            str(info_path),
            backend=self,
            open_stage_func=self._openStageForConversion,
        )
        return mesh_path, info_path

    def _prepareAppForConversion(self, headless):
        if not self.kitAppRunning():
            self.getSimulationApp(headless=headless)

    def _openStageForConversion(self, usd_path):
        from isaacsim.core.utils.stage import open_stage

        return open_stage(usd_path)

    # ------------------------------------------------------------------
    # USD helpers
    # ------------------------------------------------------------------

    def setMeshCollisionApproximation(self, prim_path, approximation):
        import omni.usd
        from pxr import UsdPhysics

        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if prim is None or not prim.IsValid():
            return

        mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
        mesh_collision_api.GetApproximationAttr().Set(approximation)

    def setRequiredVariant(self, prim, variant_name, selection):
        variant_set = prim.GetVariantSet(variant_name)
        if not variant_set or not variant_set.IsValid():
            raise RuntimeError(f"{prim.GetPath()} has no {variant_name!r} variant set")
        if selection not in list(variant_set.GetVariantNames()):
            raise RuntimeError(
                f"{prim.GetPath()} {variant_name!r} variant {selection!r} is missing"
            )
        variant_set.SetVariantSelection(selection)

    def requireStagePrim(self, stage, prim_path):
        return requireStagePrim(stage, prim_path)

    def computePrimWorldBbox(self, prim_path):
        """Return world-space bbox min, max, center, and size for a prim."""
        from isaacsim.core.utils import prims

        prim = prims.get_prim_at_path(prim_path)
        if prim is None or not prim.IsValid():
            raise ValueError(f"invalid prim path: {prim_path}")

        return self.computePrimBbox(prim)

    def computeUsdAssetBbox(self, usd_path):
        """Return the composed bbox of a USD asset referenced at the origin."""
        from pxr import Usd

        stage = Usd.Stage.CreateInMemory()
        prim = stage.DefinePrim("/Asset", "Xform")
        prim.GetReferences().AddReference(os.fspath(usd_path))
        return self.computePrimBbox(prim)

    def computePrimBbox(self, prim):
        """Return world-space bbox min, max, center, and size for a USD prim."""
        from pxr import Usd, UsdGeom

        cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(),
            [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
            useExtentsHint=True,
        )
        box = cache.ComputeWorldBound(prim).ComputeAlignedBox()
        mn = np.asarray(box.GetMin(), dtype=float)
        mx = np.asarray(box.GetMax(), dtype=float)
        return mn, mx, (mn + mx) * 0.5, mx - mn

    # ------------------------------------------------------------------
    # Coordinate conversions
    # ------------------------------------------------------------------

    def scenicToIsaacOrientation(self, orientation, initial_rotation=None):
        """Convert a Scenic Orientation to an Isaac Sim wxyz quaternion.

        ``initial_rotation`` (yaw, pitch, roll) is applied first, to align an
        asset's native frame with Scenic's (see e.g. ``model.scenic``'s
        built-in wheeled robots, whose USD assets are authored with local +X
        as forward instead of Scenic's local +Y). The composition is done as
        a full rotation, not just on yaw, so it is correct for any
        combination of yaw, pitch, and roll in either ``orientation`` or
        ``initial_rotation``.
        """
        rotation = orientation.r
        if initial_rotation is not None:
            rotation = rotation * Orientation.fromEuler(*initial_rotation).r
        return rotationToWxyz(rotation)

    def isaacQuatToScenicEulerAngles(self, quat, initial_rotation=None):
        """Convert an Isaac Sim wxyz quaternion to Scenic yaw, pitch, roll.

        ``initial_rotation`` must be passed whenever the object was spawned
        with it (see `scenicToIsaacOrientation`), so the asset-frame
        correction is undone and the result is the object's actual Scenic
        orientation rather than that orientation composed with the
        correction.
        """
        rotation = wxyzToRotation(quat)
        if initial_rotation is not None:
            rotation = rotation * Orientation.fromEuler(*initial_rotation).r.inv()
        return Orientation(rotation).eulerAngles

    def rotateVectorByWxyzQuat(self, quat_wxyz, vec):
        """Rotate a vector by an Isaac/USD wxyz quaternion."""
        return wxyzToRotation(quat_wxyz).apply(np.asarray(vec, dtype=float))

    def computeUsdScaleAndRootPosition(
        self, obj, prim_path, scenic_position, orientation
    ):
        """Compute the scale and root position for a spawned prim (see `computeScaleAndRootPosition`)."""
        _, _, native_center, native_size = self.computePrimWorldBbox(prim_path)
        return self.computeScaleAndRootPosition(
            obj, native_center, native_size, scenic_position, orientation
        )

    def computeUsdAssetScaleAndRootPosition(
        self, obj, usd_path, scenic_position, orientation
    ):
        """Compute the scale and root position for a USD asset before it is spawned."""
        _, _, native_center, native_size = self.computeUsdAssetBbox(usd_path)
        return self.computeScaleAndRootPosition(
            obj, native_center, native_size, scenic_position, orientation
        )

    def computeScaleAndRootPosition(
        self, obj, native_center, native_size, scenic_position, orientation
    ):
        """Compute the scale and root position so an asset matches Scenic's dimensions.

        Returns:
            root_position: position to give the USD root prim
            local_scale: x/y/z scale to apply to the USD root prim
            native_size: measured unscaled USD bbox size
            native_center: measured unscaled USD bbox center relative to the root
        """
        desired_size = np.array(
            [float(obj.width), float(obj.length), float(obj.height)], dtype=float
        )
        native_center = np.asarray(native_center, dtype=float)
        native_size = np.asarray(native_size, dtype=float)
        local_scale = desired_size / native_size

        # avoid tiny numerical scale changes when dimensions already match.
        if np.allclose(local_scale, np.ones(3), rtol=1e-5, atol=1e-7):
            local_scale = np.ones(3, dtype=float)

        # If the asset's geometry center is offset from its root prim, scaling
        # changes that offset. Compensate so the visual bbox center lands at
        # Scenic's obj.position.
        scaled_center_offset_world = self.rotateVectorByWxyzQuat(
            orientation, native_center * local_scale
        )
        root_position = (
            np.asarray(scenic_position, dtype=float) - scaled_center_offset_world
        )

        return root_position, local_scale, native_size, native_center

    def manipulatorRootPosition(self, obj):
        """Scenic positions an arm by its bounding box center; the USD root is at its base."""
        position = scenic_utils.vectorToArray(obj.position)
        position[2] -= obj.height / 2
        return position

    # ------------------------------------------------------------------
    # Object creation
    # ------------------------------------------------------------------

    def createGenericObject(self, obj):
        raise NotImplementedError

    def createRobot(self, obj):
        raise NotImplementedError

    def createWheeledRobot(self, obj):
        raise NotImplementedError

    def createManipulator(self, obj):
        raise NotImplementedError

    def createGroundPlane(self, obj):
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Control and state
    # ------------------------------------------------------------------

    def applyRobotControl(self, sim, obj, command):
        raise NotImplementedError

    def applyWheeledControl(self, sim, obj, command):
        raise NotImplementedError

    def applyArticulationAction(self, sim, obj, action):
        raise NotImplementedError

    def articulationAction(self, **kwargs):
        from scenic.simulators.isaac.backends import articulationAction

        return articulationAction(**kwargs)

    def articulationDofNames(self, sim, obj):
        raise NotImplementedError

    def articulationDofIndices(self, sim, obj, names):
        dof_names = self.articulationDofNames(sim, obj)
        return [dof_names.index(name) for name in names]

    def getObjectPose(self, sim, obj):
        raise NotImplementedError

    def setObjectPose(self, sim, obj, position, orientation=None):
        raise NotImplementedError

    def getPhysicsProperties(self, world, obj):
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Manipulators
    # ------------------------------------------------------------------

    def moveManipulatorPickPlace(
        self,
        sim,
        obj,
        targetObject,
        goalPosition,
        endEffectorOffset=None,
        endEffectorOrientation=None,
    ):
        raise NotImplementedError

    def moveManipulatorEndEffector(self, sim, obj, position, orientation=None):
        raise NotImplementedError

    def setManipulatorGripper(self, sim, obj, opened):
        raise NotImplementedError

    def setManipulatorArmJointPositions(self, sim, obj, joint_positions):
        raise NotImplementedError

    def holdManipulatorPosition(self, sim, obj):
        raise NotImplementedError

    def getManipulatorEndEffectorPose(self, sim, obj):
        raise NotImplementedError

    def getManipulatorGripperPositions(self, sim, obj):
        raise NotImplementedError

    def manipulatorGripperTargetPositions(self, profile, opened):
        positions = (
            profile.openGripperPositions if opened else profile.closedGripperPositions
        )
        return positions.copy()
