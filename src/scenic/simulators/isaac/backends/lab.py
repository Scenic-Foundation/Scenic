from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from scenic.core.regions import MeshVolumeRegion
from scenic.core.simulators import SimulationCreationError
from scenic.simulators.isaac.backends.base import IsaacBackend
import scenic.simulators.isaac.utils as scenic_utils


class LabBackend(IsaacBackend):
    """Backend translating Scenic objects into Isaac Lab asset configurations.

    Unlike the direct Isaac Sim backends, objects are not spawned one at a
    time: `IsaacLabSimulation` collects them, this backend turns each into an
    asset cfg added to the env's ``scene`` cfg, and Isaac Lab builds the whole
    scene (cloned across ``num_envs`` environments).
    """

    name = "lab"

    def __init__(self):
        super().__init__()
        self.app_launcher = None

    def ensureApp(self, *, headless=False, device=None, app_launcher_args=None):
        """Launch Isaac Sim once through Isaac Lab's AppLauncher."""
        if self._simulation_app is not None:
            return self._simulation_app

        # Preload before Kit starts: h5py's HDF5 DLLs must be the first copy loaded,
        # or the one Kit bundles shadows them and `import h5py` inside the running
        # app fails (entrypoint not found).
        try:
            import h5py  # noqa: F401
        except ImportError:
            pass

        from isaaclab.app import AppLauncher

        launcher_args = {"headless": headless}
        if device is not None:
            launcher_args["device"] = device
        launcher_args.update(app_launcher_args or {})

        self.app_launcher = AppLauncher(launcher_args)
        self._simulation_app = self.app_launcher.app
        return self._simulation_app

    def closeApp(self):
        if self._simulation_app is not None:
            self.closeSimulationApp(self._simulation_app)
            self.app_launcher = None

    def enableExtension(self, name):
        from isaacsim.core.utils.extensions import enable_extension

        enable_extension(name)

    def _prepareAppForConversion(self, headless):
        self.ensureApp(headless=headless)

    def _openStageForConversion(self, usd_path):
        import isaacsim.core.experimental.utils.stage as stage_utils

        result = stage_utils.open_stage(usd_path)
        return result[0] if isinstance(result, tuple) else bool(result)

    # ------------------------------------------------------------------
    # Scenic -> Isaac Lab conversions
    # ------------------------------------------------------------------

    def assetPrimPath(self, asset_name: str, num_envs: int | None) -> str:
        if int(num_envs or 1) == 1:
            return f"/World/envs/env_0/{asset_name}"
        return f"{{ENV_REGEX_NS}}/{asset_name}"

    def safeAssetName(self, name: str):
        """Turn a Scenic object name into a valid cfg field / prim name."""
        name = re.sub(r"\W+", "_", str(name)) or "scenic_object"
        if name[0].isdigit():
            name = f"obj_{name}"
        return name

    def scenicPose(self, obj):
        position = tuple(float(v) for v in scenic_utils.vectorToArray(obj.position))
        orientation = self.scenicToIsaacOrientation(
            obj.orientation, initial_rotation=obj.initialRotation
        )
        return position, tuple(float(v) for v in orientation)

    def previewSurfaceCfg(self, obj):
        color = obj.color
        if color is None:
            return None

        import isaaclab.sim as sim_utils

        r, g, b = color[:3]
        return sim_utils.PreviewSurfaceCfg(
            diffuse_color=(float(r), float(g), float(b)),
            roughness=0.5,
            metallic=0.0,
        )

    def tensorRow(self, tensor, env_id: int):
        return tuple(float(v) for v in tensor[env_id].tolist())

    # ------------------------------------------------------------------
    # Asset cfg builders
    # ------------------------------------------------------------------

    def makeEnvironmentCfg(self, environmentUsdPath):
        """Create a static environment asset cloned into every Lab environment."""
        from isaaclab.assets import AssetBaseCfg
        import isaaclab.sim as sim_utils

        usd_path = self.kitUsdPath(environmentUsdPath)
        if not urlparse(usd_path).scheme and not os.path.isfile(usd_path):
            raise SimulationCreationError(
                f"Isaac Lab environment USD does not exist or is not a file: {usd_path!r}"
            )

        return AssetBaseCfg(
            prim_path="{ENV_REGEX_NS}/ScenicEnvironment",
            spawn=sim_utils.UsdFileCfg(usd_path=usd_path),
        )

    def makeAssetCfg(
        self, obj, asset_name: str, *, num_envs: int | None, tmp_mesh_dir: str
    ):
        if obj.blueprint == "GroundPlane":
            return self.makeGroundPlaneCfg(obj, asset_name, num_envs=num_envs)

        if obj.blueprint == "Robot":
            return self.makeRobotCfg(obj, asset_name, num_envs=num_envs)

        return self.makeObjectCfg(
            obj, asset_name, num_envs=num_envs, tmp_mesh_dir=tmp_mesh_dir
        )

    def makeGroundPlaneCfg(self, obj, asset_name: str, *, num_envs: int | None):
        from isaaclab.assets import AssetBaseCfg
        import isaaclab.sim as sim_utils

        pos, rot = self.scenicPose(obj)

        return AssetBaseCfg(
            prim_path=self.assetPrimPath(asset_name, num_envs),
            spawn=sim_utils.CuboidCfg(
                size=(obj.width, obj.length, obj.height),
                collision_props=sim_utils.CollisionPropertiesCfg(),
                visual_material=self.previewSurfaceCfg(obj),
            ),
            init_state=AssetBaseCfg.InitialStateCfg(pos=pos, rot=rot),
        )

    def makeObjectCfg(
        self, obj, asset_name: str, *, num_envs: int | None, tmp_mesh_dir: str
    ):
        from isaaclab.assets import AssetBaseCfg, RigidObjectCfg
        import isaaclab.sim as sim_utils

        prim_path = self.assetPrimPath(asset_name, num_envs)
        has_usd_asset = bool(obj.usdPath or obj.isaacAssetPath)

        if not has_usd_asset:
            self.convertMeshObjectToUsd(obj, tmp_mesh_dir)

        usd_path = self.objectUsdPath(obj)
        if has_usd_asset and obj.physics:
            usd_path = self.makeRigidUsdWrapper(usd_path, obj, asset_name, tmp_mesh_dir)

        scenic_position, rot = self.scenicPose(obj)
        pos, scale, _, _ = self.computeUsdAssetScaleAndRootPosition(
            obj, usd_path, scenic_position, rot
        )
        pos = tuple(float(value) for value in pos)
        scale = tuple(float(value) for value in scale)
        spawn = sim_utils.UsdFileCfg(
            usd_path=usd_path,
            scale=scale,
            visual_material=self.previewSurfaceCfg(obj),
        )

        if obj.physics:
            return RigidObjectCfg(
                prim_path=prim_path,
                spawn=spawn,
                init_state=RigidObjectCfg.InitialStateCfg(pos=pos, rot=rot),
            )

        return AssetBaseCfg(
            prim_path=prim_path,
            spawn=spawn,
            init_state=AssetBaseCfg.InitialStateCfg(pos=pos, rot=rot),
        )

    def makeRobotCfg(self, obj, asset_name: str, *, num_envs: int | None):
        from isaaclab.actuators import ImplicitActuatorCfg
        from isaaclab.assets import ArticulationCfg
        import isaaclab.sim as sim_utils

        pos, rot = self.scenicPose(obj)

        return ArticulationCfg(
            prim_path=self.assetPrimPath(asset_name, num_envs),
            spawn=sim_utils.UsdFileCfg(
                usd_path=self.objectUsdPath(obj),
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=False,
                ),
                visual_material=self.previewSurfaceCfg(obj),
            ),
            init_state=ArticulationCfg.InitialStateCfg(pos=pos, rot=rot),
            actuators={
                "all_joints": ImplicitActuatorCfg(
                    joint_names_expr=[".*"],
                    effort_limit_sim=None,
                    velocity_limit_sim=None,
                    stiffness=0.0,
                    damping=100.0,
                )
            },
        )

    def patchAssetInitialPose(self, lab_asset_cfg, obj):
        if lab_asset_cfg.init_state is None:
            lab_asset_cfg.init_state = type(lab_asset_cfg).InitialStateCfg()

        pos, rot = self.scenicPose(obj)
        lab_asset_cfg.init_state.pos = pos
        lab_asset_cfg.init_state.rot = rot

    def convertMeshObjectToUsd(self, obj, tmp_mesh_dir: str):
        mesh = MeshVolumeRegion(
            mesh=obj.shape.mesh,
            dimensions=(obj.width, obj.length, obj.height),
        ).mesh
        # TODO: the direct Isaac Sim path exports `scenic_utils.meshToObjFrame(mesh)`
        # here to undo the asset converter's Y-up interpretation of OBJ files; check
        # whether mesh objects spawn correctly oriented in Isaac Lab without it.
        usd_path = self.exportMeshToUsd(mesh, obj.name, tmp_mesh_dir)

        if obj.physics:
            self.applyRigidBodyApiToUsd(usd_path, obj)

        obj.usdPath = usd_path

    def makeRigidUsdWrapper(self, usd_path, obj, asset_name, tmp_mesh_dir):
        """Create a local rigid-body wrapper without modifying the source USD."""
        from pxr import Usd, UsdGeom

        os.makedirs(tmp_mesh_dir, exist_ok=True)
        wrapper_path = os.path.join(tmp_mesh_dir, f"{asset_name}_rigid.usd")

        stage = Usd.Stage.CreateNew(wrapper_path)
        root_prim = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
        root_prim.GetReferences().AddReference(usd_path)
        stage.SetDefaultPrim(root_prim)
        stage.GetRootLayer().Save()

        self.applyRigidBodyApiToUsd(wrapper_path, obj)
        return wrapper_path

    def applyRigidBodyApiToUsd(self, usd_path, obj):
        """Patch a local USD so Isaac Lab can load it as a RigidObjectCfg.

        RigidObjectCfg requires exactly one UsdPhysics.RigidBodyAPI below its
        configured prim. CollisionAPI is applied to mesh children and MassAPI to
        the rigid body prim.
        """
        from pxr import Usd, UsdGeom, UsdPhysics

        stage = Usd.Stage.Open(usd_path)
        if stage is None:
            raise SimulationCreationError(f"Could not open USD: {usd_path}")

        root_prim = stage.GetDefaultPrim()

        if not root_prim or not root_prim.IsValid():
            children = list(stage.GetPseudoRoot().GetChildren())
            if not children:
                raise SimulationCreationError(
                    f"USD for {obj.name!r} has no root prim: {usd_path}"
                )
            root_prim = children[0]
            stage.SetDefaultPrim(root_prim)

        rigid_body_prims = [
            prim
            for prim in Usd.PrimRange(root_prim)
            if prim.HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        if len(rigid_body_prims) > 1:
            raise SimulationCreationError(
                f"USD asset for {obj.name!r} contains multiple rigid bodies "
                "and cannot be loaded as one Isaac Lab RigidObjectCfg."
            )

        if rigid_body_prims:
            rigid_body_prim = rigid_body_prims[0]
        else:
            UsdPhysics.RigidBodyAPI.Apply(root_prim)
            rigid_body_prim = root_prim

        mass_api = UsdPhysics.MassAPI(rigid_body_prim)
        if not mass_api:
            mass_api = UsdPhysics.MassAPI.Apply(rigid_body_prim)

        mass = obj.mass
        if mass is None and obj.density is not None:
            mass = float(obj.density) * obj.width * obj.length * obj.height
        if mass is not None:
            mass_api.CreateMassAttr(float(mass))

        mesh_prims = [prim for prim in Usd.PrimRange(root_prim) if prim.IsA(UsdGeom.Mesh)]
        if not mesh_prims:
            # Fallback: try collision on root, although this only works if root has geometry.
            if not root_prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI.Apply(root_prim)
        for mesh_prim in mesh_prims:
            if not mesh_prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI.Apply(mesh_prim)

            try:
                mesh_collision_api = UsdPhysics.MeshCollisionAPI(mesh_prim)
                if not mesh_collision_api:
                    mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(mesh_prim)
                mesh_collision_api.CreateApproximationAttr("convexHull")
            except Exception:
                pass

        stage.GetRootLayer().Save()

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def applyRobotControl(self, sim, obj, command):
        """Buffer a robot command; `IsaacLabSimulation` applies it before env.step()."""
        if obj.wheelController or callable(obj.control):
            sim.bufferRobotCommand(obj, command)

    def applyDifferentialDriveCommand(self, asset, obj, command):
        import torch

        throttle, steering = (float(v) for v in command)
        radius = float(obj.wheelRadius)
        base = float(obj.wheelBase)

        left_vel = ((2.0 * throttle) - (steering * base)) / (2.0 * radius)
        right_vel = ((2.0 * throttle) + (steering * base)) / (2.0 * radius)

        joint_ids = self.findJointIds(asset, list(obj.wheelDofNames))
        if len(joint_ids) < 2:
            raise RuntimeError(
                f"could not resolve wheel joints {list(obj.wheelDofNames)} for "
                f"{obj.name}; available joints: {asset.joint_names}"
            )

        target = torch.zeros((int(asset.num_instances), 2), device=asset.device)
        target[:, 0] = left_vel
        target[:, 1] = right_vel

        asset.set_joint_velocity_target(target, joint_ids=joint_ids[:2])
        asset.write_data_to_sim()

    def applyArticulationAction(self, sim, obj, action):
        """Apply a generic articulation action to every environment."""
        import torch

        asset = sim.assetForScenicObject(obj)
        joint_ids = action.get("joint_indices", action.get("dof_indices"))
        if hasattr(joint_ids, "tolist"):
            joint_ids = joint_ids.tolist()

        applied = False
        for field, index_field, setter_name in (
            ("joint_positions", "joint_position_indices", "set_joint_position_target"),
            ("joint_velocities", "joint_velocity_indices", "set_joint_velocity_target"),
            ("joint_efforts", "joint_effort_indices", "set_joint_effort_target"),
        ):
            values = action.get(field)
            if values is None:
                continue

            field_joint_ids = action.get(index_field, joint_ids)
            if hasattr(field_joint_ids, "tolist"):
                field_joint_ids = field_joint_ids.tolist()

            target = torch.as_tensor(values, dtype=torch.float32, device=asset.device)
            if target.ndim == 1:
                target = target.unsqueeze(0).repeat(int(asset.num_instances), 1)

            getattr(asset, setter_name)(target, joint_ids=field_joint_ids)
            applied = True

        if applied:
            asset.write_data_to_sim()

    def findJointIds(self, asset, joint_names):
        joint_ids, _ = asset.find_joints(joint_names, preserve_order=True)
        return joint_ids.tolist() if hasattr(joint_ids, "tolist") else list(joint_ids)
