"""Simulator interface running Scenic scenarios in Isaac Lab manager-based environments."""

from __future__ import annotations

import copy
import importlib
import math
import os
import tempfile
from typing import Any

from scenic.core.simulators import Simulation, SimulationCreationError, Simulator
from scenic.core.vectors import Vector
from scenic.simulators.isaac.backends import getBackend
from scenic.simulators.isaac.terrain_utils import buildScenicTerrainData

DEFAULT_EMPTY_ENV_CFG = "scenic.simulators.isaac.empty_env_cfg:ScenicEmptyEnvCfg"


class IsaacLabSimulator(Simulator):
    """Scenic simulator backend for Isaac Lab manager-based environments.

    Supported construction modes:
        1. env=<already-created Isaac Lab env>
        2. task="Isaac-Cartpole-v0" or another registered Isaac Lab task
        3. env_cfg=<ManagerBasedEnvCfg / ManagerBasedRLEnvCfg instance or class>
        4. env_cfg_entry_point="package.module:CfgClass"

    If none of these is given, a minimal empty manager-based environment is
    used and populated with the sampled Scenic objects.
    """

    def __init__(
        self,
        *,
        env: Any | None = None,
        task: str | None = None,
        env_cfg: Any | None = None,
        env_cfg_entry_point: str | None = None,
        env_cls: Any | None = None,
        timestep: float | None = 0.01,
        decimation: int | None = None,
        num_envs: int | None = None,
        env_spacing: float | None = None,
        terrainBorderWidth: float = 20.0,
        environmentUSDPath: str | os.PathLike | None = None,
        headless: bool = False,
        device: str | None = None,
        use_fabric: bool = True,
        render_mode: str | None = None,
        app_launcher_args: dict[str, Any] | None = None,
        debug_lifecycle: bool = True,
        **kwargs,
    ):
        super().__init__()

        self.env = env
        self.task = task
        self.env_cfg = env_cfg
        self.env_cfg_entry_point = env_cfg_entry_point
        self.env_cls = env_cls
        if (
            env is None
            and task is None
            and env_cfg is None
            and env_cfg_entry_point is None
        ):
            self.env_cfg_entry_point = DEFAULT_EMPTY_ENV_CFG

        self.timestep = timestep
        self.decimation = decimation
        self.num_envs = num_envs
        self.env_spacing = env_spacing
        self.terrainBorderWidth = terrainBorderWidth
        self.environmentUSDPath = environmentUSDPath

        self.headless = headless
        self.device = device
        self.use_fabric = use_fabric
        self.render_mode = render_mode
        self.debug_lifecycle = debug_lifecycle

        self.backend = getBackend("lab")

        # If an env is already provided, assume the caller owns the app/env.
        if self.env is None:
            self.backend.ensureApp(
                headless=headless,
                device=device,
                app_launcher_args=dict(app_launcher_args or {}),
            )

    def createSimulation(self, scene, **kwargs):
        timestep = kwargs.pop("timestep", None)
        if timestep is None:
            timestep = self.timestep
        return IsaacLabSimulation(scene, self, timestep=timestep, **kwargs)

    def destroy(self):
        super().destroy()
        if self.env is None:
            self.backend.closeApp()


class IsaacLabSimulation(Simulation):
    """A Scenic Simulation backed by an Isaac Lab manager-based environment.

    Scenic objects are collected during `createObjectInSimulator` and turned
    into asset cfgs in `setup`, when the Isaac Lab environment is built.
    """

    def __init__(self, scene, simulator: IsaacLabSimulator, *, timestep, **kwargs):
        kwargs.setdefault("maxSteps", None)
        kwargs.setdefault("name", "IsaacLabSimulation")

        self.simulator = simulator
        self.backend = simulator.backend
        self.env = simulator.env
        self._owns_env = simulator.env is None
        self.tmpMeshDir = tempfile.mkdtemp()

        self.scenic_objects = []
        self.scenic_existing_objects = []
        self.terrains = []
        self.env_cfg = None

        # Maps Scenic object names to Isaac Lab scene entity names.
        self._asset_names: dict[str, str] = {}
        # Robot commands buffered by the backend, applied right before env.step().
        self._pending_robot_commands = {}
        self._last_step_output = None
        self._step_count = 0

        super().__init__(scene, timestep=timestep, **kwargs)

    def setup(self):
        """Build the Isaac Lab env after Scenic has collected all objects."""
        super().setup()

        if self.env is None:
            self.env_cfg = self._buildEnvCfg()
            self.env = self._makeEnv(self.env_cfg)

        self.env.reset()

    # ------------------------------------------------------------------
    # Environment configuration
    # ------------------------------------------------------------------

    def _buildEnvCfg(self):
        """Create, validate, and patch an Isaac Lab manager-based env cfg."""
        cfg = self._materializeEnvCfg()
        self._validateManagerBasedCfg(cfg)
        self._applyStandardOverrides(cfg)
        self._applyScenicToEnvCfg(cfg)
        return cfg

    def _materializeEnvCfg(self):
        """Resolve env cfg from task, cfg object/class, or entry point."""
        simulator = self.simulator

        if simulator.env_cfg is not None:
            return self._instantiateCfg(simulator.env_cfg)

        if simulator.env_cfg_entry_point is not None:
            return self._instantiateCfg(simulator.env_cfg_entry_point)

        if simulator.task is not None:
            import isaaclab_tasks  # noqa: F401
            from isaaclab_tasks.utils import parse_env_cfg

            return parse_env_cfg(
                simulator.task,
                device=simulator.device,
                num_envs=simulator.num_envs,
                use_fabric=simulator.use_fabric,
            )

        raise SimulationCreationError(
            "IsaacLabSimulation requires one of: env, task, env_cfg, or env_cfg_entry_point."
        )

    def _instantiateCfg(self, cfg_like):
        if isinstance(cfg_like, str):
            return self._instantiateCfg(self._loadEntryPoint(cfg_like))

        if isinstance(cfg_like, type):
            return cfg_like()

        if callable(cfg_like) and not hasattr(cfg_like, "scene"):
            return cfg_like()

        return copy.deepcopy(cfg_like)

    def _loadEntryPoint(self, entry_point: str):
        """Load 'package.module:ClassName'."""
        if ":" not in entry_point:
            raise SimulationCreationError(
                f"Invalid env_cfg_entry_point {entry_point!r}; expected 'module.submodule:ClassName'."
            )

        module_name, attr_name = entry_point.split(":", 1)
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr_name)
        except Exception as exc:
            raise SimulationCreationError(
                f"Could not load Isaac Lab env cfg entry point {entry_point!r}."
            ) from exc

    def _validateManagerBasedCfg(self, cfg):
        from isaaclab.envs import ManagerBasedEnvCfg, ManagerBasedRLEnvCfg

        if not isinstance(cfg, (ManagerBasedEnvCfg, ManagerBasedRLEnvCfg)):
            raise SimulationCreationError(
                "The Isaac Lab Scenic backend currently expects a manager-based config: "
                "ManagerBasedEnvCfg or ManagerBasedRLEnvCfg. "
                f"Got {type(cfg).__name__}. If you selected an Isaac Lab task, make sure it is "
                "not one of the '-Direct-' environments."
            )

    def _applyStandardOverrides(self, cfg):
        """Apply common simulator-level overrides to the env cfg."""
        simulator = self.simulator

        if simulator.device is not None:
            cfg.sim.device = simulator.device

        if self.timestep is not None:
            cfg.sim.dt = self.timestep

        if simulator.decimation is not None:
            cfg.decimation = simulator.decimation

        if simulator.use_fabric is not None:
            cfg.sim.use_fabric = simulator.use_fabric

        if simulator.num_envs is not None:
            cfg.scene.num_envs = simulator.num_envs

        if simulator.env_spacing is not None:
            cfg.scene.env_spacing = simulator.env_spacing

    def _applyScenicToEnvCfg(self, cfg):
        """Patch the Isaac Lab cfg using the objects sampled by Scenic.

        - Terrain objects are merged into one mesh installed via a custom
          terrain generator (see `lab_env.configureEnvCfgForScenicTerrain`).
        - The environment USD, if any, is added as a static asset.
        - If a Scenic object name matches an existing cfg.scene field, that
          asset's initial pose is patched; otherwise a new asset cfg is created.
        """
        simulator = self.simulator

        if self.terrains:
            from scenic.simulators.isaac.lab_env import configureEnvCfgForScenicTerrain

            if not hasattr(cfg.scene, "terrain"):
                raise SimulationCreationError(
                    "This Isaac Lab env cfg has no cfg.scene.terrain. "
                    "Scenic Terrain objects require a task/config with a TerrainImporterCfg."
                )
            terrain_data = buildScenicTerrainData(
                self.terrains, border_width=simulator.terrainBorderWidth
            )
            configureEnvCfgForScenicTerrain(cfg, terrain_data)

        if simulator.environmentUSDPath is not None:
            cfg.scene.scenic_environment = self.backend.makeEnvironmentCfg(
                simulator.environmentUSDPath
            )
        else:
            for obj in self.scenic_existing_objects:
                self._patchOrRegisterScenicObject(cfg, obj, must_exist=True)

        for obj in self.scenic_objects:
            self._patchOrRegisterScenicObject(cfg, obj, must_exist=False)

    def _patchOrRegisterScenicObject(self, cfg, obj, *, must_exist: bool):
        asset_name = self.backend.safeAssetName(obj.name)

        if hasattr(cfg.scene, asset_name):
            self.backend.patchAssetInitialPose(getattr(cfg.scene, asset_name), obj)
        elif must_exist:
            raise SimulationCreationError(
                f"Existing object {obj.name!r} has no matching cfg.scene field {asset_name!r}."
            )
        else:
            lab_asset_cfg = self.backend.makeAssetCfg(
                obj,
                asset_name,
                num_envs=self.simulator.num_envs,
                tmp_mesh_dir=self.tmpMeshDir,
            )
            setattr(cfg.scene, asset_name, lab_asset_cfg)

        self._asset_names[obj.name] = asset_name

    def _makeEnv(self, cfg):
        """Construct the actual Isaac Lab environment."""
        simulator = self.simulator

        if simulator.task is not None:
            import gymnasium as gym
            import isaaclab_tasks  # noqa: F401

            # gym.make uses the task's registered entry_point, usually:
            # "isaaclab.envs:ManagerBasedRLEnv"
            return gym.make(simulator.task, cfg=cfg, render_mode=simulator.render_mode)

        from isaaclab.envs import ManagerBasedRLEnv

        env_cls = self._resolveEnvCls(cfg)
        if issubclass(env_cls, ManagerBasedRLEnv):
            return env_cls(cfg=cfg, render_mode=simulator.render_mode)
        return env_cls(cfg=cfg)

    def _resolveEnvCls(self, cfg):
        """Pick ManagerBasedEnv or ManagerBasedRLEnv from the cfg type."""
        env_cls = self.simulator.env_cls
        if env_cls is not None:
            return self._loadEntryPoint(env_cls) if isinstance(env_cls, str) else env_cls

        from isaaclab.envs import (
            ManagerBasedEnv,
            ManagerBasedEnvCfg,
            ManagerBasedRLEnv,
            ManagerBasedRLEnvCfg,
        )

        if isinstance(cfg, ManagerBasedRLEnvCfg):
            return ManagerBasedRLEnv
        if isinstance(cfg, ManagerBasedEnvCfg):
            return ManagerBasedEnv

        raise SimulationCreationError(
            f"Unsupported Isaac Lab cfg type: {type(cfg).__name__}"
        )

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def createObjectInSimulator(self, obj):
        """Collect Scenic objects; they are spawned together in `setup`."""
        if obj.blueprint == "Terrain":
            self.terrains.append(obj)
        elif obj.blueprint == "ExistingIsaacSimObject":
            self.scenic_existing_objects.append(obj)
        else:
            self.scenic_objects.append(obj)

    def executeActions(self, allActions):
        self._pending_robot_commands = {}
        # Actions call obj.move(self, ...), which buffers robot commands via the backend.
        super().executeActions(allActions)

    def bufferRobotCommand(self, obj, command):
        self._pending_robot_commands[obj.name] = (obj, command)

    def step(self):
        """Apply buffered robot commands, then step the Isaac Lab environment once."""
        import torch

        self._applyPendingRobotCommands()

        # Isaac Lab tasks also expect an action tensor; no policy is connected,
        # so send zeros.
        with torch.inference_mode():
            self._last_step_output = self.env.step(self._zeroLabAction())

        self._step_count += 1
        if self.simulator.debug_lifecycle and self._step_count % 100 == 0:
            print(
                f"[SCENIC LAB DEBUG] step={self._step_count}, "
                f"sim_time={self._step_count * float(self.timestep):.3f}s"
            )

    def _applyPendingRobotCommands(self):
        """Apply buffered Scenic robot commands to Isaac Lab articulations."""
        for obj, command in self._pending_robot_commands.values():
            controller = obj.wheelController
            if controller == "differential":
                self.backend.applyDifferentialDriveCommand(
                    self.assetForScenicObject(obj), obj, command
                )
            elif callable(obj.control):
                self.backend.applyArticulationAction(self, obj, obj.control(command))
            else:
                raise RuntimeError(
                    f"the Isaac Lab backend does not support wheelController "
                    f"{controller!r} (robot {obj.name})"
                )
        self._pending_robot_commands = {}

    def _zeroLabAction(self):
        """A zero action tensor with the shape Isaac Lab expects (num_envs first)."""
        import torch

        env = getattr(self.env, "unwrapped", self.env)

        if hasattr(env, "action_manager") and hasattr(env.action_manager, "action"):
            return torch.zeros_like(env.action_manager.action)

        action_space = getattr(self.env, "action_space", None)
        if action_space is None:
            return None

        shape = tuple(action_space.shape)
        if len(shape) == 1:
            shape = (int(getattr(env, "num_envs", 1)), *shape)
        return torch.zeros(shape, device=env.device)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def assetForScenicObject(self, obj):
        asset_name = self._asset_names.get(obj.name) or self.backend.safeAssetName(
            obj.name
        )
        env = getattr(self.env, "unwrapped", self.env)
        return env.scene[asset_name]

    def getProperties(self, obj, properties):
        """Read Scenic-requested properties from Isaac Lab asset buffers (env 0)."""
        if not obj.physics:
            return {prop: getattr(obj, prop) for prop in properties}

        values = self._physicsValuesFromAsset(
            self.assetForScenicObject(obj), initial_rotation=obj.initialRotation
        )
        return {prop: values[prop] for prop in properties}

    def _physicsValuesFromAsset(self, asset, env_id: int = 0, initial_rotation=None):
        """Read the root state of a RigidObject/Articulation for one environment."""
        row = self.backend.tensorRow
        data = asset.data
        pos = row(data.root_pos_w, env_id)
        quat = row(data.root_quat_w, env_id)
        lin_vel = row(data.root_lin_vel_w, env_id)
        ang_vel = row(data.root_ang_vel_w, env_id)

        yaw, pitch, roll = self.backend.isaacQuatToScenicEulerAngles(
            quat, initial_rotation=initial_rotation
        )

        return dict(
            position=Vector(*pos),
            velocity=Vector(*lin_vel),
            speed=math.hypot(*lin_vel),
            angularSpeed=math.hypot(*ang_vel),
            angularVelocity=Vector(*ang_vel),
            yaw=yaw,
            pitch=pitch,
            roll=roll,
        )

    def destroy(self):
        if self.simulator.debug_lifecycle:
            result = self.result
            if result is None:
                print(
                    "[SCENIC ISAAC LAB DEBUG] destroy called before Simulation.result was set."
                )
            else:
                print(
                    "[SCENIC ISAAC LAB DEBUG] simulation ended:",
                    "terminationType=",
                    result.terminationType,
                    "terminationReason=",
                    result.terminationReason,
                )

        if self.env is not None and self._owns_env:
            self.env.close()
            self.env = None
