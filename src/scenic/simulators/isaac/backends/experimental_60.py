from dataclasses import dataclass, field
import math

import numpy as np

from scenic.simulators.isaac.actions import _ManipulatorRobot
from scenic.simulators.isaac.backends.base import (
    IsaacBackend,
    isWheeledRobot,
    positionArray,
    wxyzToRotation,
)
from scenic.simulators.isaac.backends.robotiq import (
    configureRobotiqContactMaterial,
    configureRobotiqGripper,
    configureRobotiqPickObjectContact,
)
import scenic.simulators.isaac.utils as scenic_utils


@dataclass
class ExperimentalWorld:
    """The experimental API has no World class; this holds the equivalent state."""

    app: object
    timestep: float
    objects: dict = field(default_factory=dict)
    simulation_time: float = 0.0

    def getObject(self, name):
        return self.objects[name]


@dataclass
class ManipulatorPickPlaceState:
    stage: int = 0
    stage_steps: int = 0
    done: bool = False
    endEffectorOrientation: object = None
    pick_position: object = None
    place_position: object = None


def _differentialInverseKinematics(
    jacobian_end_effector,
    current_position,
    current_orientation,
    goalPosition,
    goal_orientation=None,
    damping=0.05,
    scale=1.0,
):
    """One damped-least-squares IK step; returns the joint position deltas."""
    goal_orientation = (
        current_orientation if goal_orientation is None else goal_orientation
    )
    # Orientation error: vector part of the rotation from current to goal
    # (as an xyzw quaternion), with the sign chosen for the shortest arc.
    q = (
        wxyzToRotation(goal_orientation) * wxyzToRotation(current_orientation).inv()
    ).as_quat()
    orientation_error = q[:, :3] * np.sign(q[:, 3:])
    error = np.expand_dims(
        np.concatenate([goalPosition - current_position, orientation_error], axis=-1),
        axis=2,
    )
    transpose = np.swapaxes(jacobian_end_effector, 1, 2)
    lmbda = np.eye(jacobian_end_effector.shape[1]) * (damping**2)
    return (
        scale
        * transpose
        @ np.linalg.inv(jacobian_end_effector @ transpose + lmbda)
        @ error
    ).squeeze(-1)


class Experimental60Backend(IsaacBackend):
    """Isaac Sim 6.0.0 backend implemented with the Core Experimental APIs."""

    name = "experimental_60"

    def __init__(self):
        super().__init__()
        self._environment_usd_path = None

    def createWorld(self, timestep):
        import isaacsim.core.experimental.utils.stage as stage_utils
        from pxr import UsdPhysics

        if stage_utils.get_current_stage() is None:
            stage_utils.create_new_stage(template="sunlight")

        stage = stage_utils.get_current_stage()
        stage_utils.set_stage_up_axis("Z")
        stage_utils.set_stage_units(meters_per_unit=1.0)

        if not stage.GetPrimAtPath("/World/physicsScene").IsValid():
            UsdPhysics.Scene.Define(stage, "/World/physicsScene")

        return ExperimentalWorld(app=self._simulation_app, timestep=timestep)

    def openEnvironmentStage(self, usd_path):
        import isaacsim.core.experimental.utils.stage as stage_utils

        # Reuse the stage across simulations when the environment has not changed.
        stage = stage_utils.get_current_stage()
        if self._environment_usd_path == usd_path and stage is not None:
            stage.SetEditTarget(stage.GetSessionLayer())
            return True

        opened, stage = stage_utils.open_stage(usd_path)
        if not opened:
            return False
        stage.SetEditTarget(stage.GetSessionLayer())
        self._environment_usd_path = usd_path
        return True

    def _openStageForConversion(self, usd_path):
        import isaacsim.core.experimental.utils.stage as stage_utils

        opened, _ = stage_utils.open_stage(usd_path)
        return opened

    def enableExtension(self, name):
        import isaacsim.core.experimental.utils.app as app_utils

        app_utils.enable_extension(name)

    def initializePhysics(self, world, objects):
        from isaacsim.core.simulation_manager import SimulationManager

        SimulationManager.setup_simulation(dt=world.timestep)
        self._configureManipulatorPickObjectsForWorld(world, objects)
        if world.app is not None:
            world.app.update()

    def _configureManipulatorPickObjectsForWorld(self, world, objects):
        """Apply the Robotiq profile's contact tuning to every rigid generic object."""
        profile = next(
            (
                obj.manipulatorProfile
                for obj in objects
                if isinstance(obj, _ManipulatorRobot)
                and obj.manipulatorProfile.gripperStyle == "robotiq_2f85"
            ),
            None,
        )
        if profile is None:
            return

        import isaacsim.core.experimental.utils.stage as stage_utils

        pick_object_paths = [
            obj._isaac_generic_prim_path
            for obj in objects
            if obj.physics and hasattr(obj, "_isaac_generic_prim_path")
        ]
        if pick_object_paths:
            configureRobotiqPickObjectContact(
                stage_utils.get_current_stage(), pick_object_paths, profile
            )

    def playWorld(self, world):
        import omni.timeline

        omni.timeline.get_timeline_interface().play()
        if world.app is not None:
            world.app.update()

    def stepWorld(self, world):
        from isaacsim.core.rendering_manager import RenderingManager
        from isaacsim.core.simulation_manager import SimulationManager

        SimulationManager.step(steps=1)
        RenderingManager.render()

        if world.app is not None:
            world.app.update()

        world.simulation_time = SimulationManager.get_simulation_time()

    def stopAndClearWorld(self, world):
        import isaacsim.core.experimental.utils.stage as stage_utils
        import omni.timeline

        omni.timeline.get_timeline_interface().stop()
        if world.app is not None:
            world.app.update()

        for name in list(world.objects):
            try:
                stage_utils.delete_prim(f"/World/{name}")
            except Exception:
                pass
        world.objects.clear()
        if world.app is not None:
            world.app.update()

    def runCoroutine(self, coro):
        return self._simulation_app.run_coroutine(coro)

    def addObject(self, world, obj, *, scenic_obj=None):
        world.objects[scenic_obj.name] = obj

    # ------------------------------------------------------------------
    # Object creation
    # ------------------------------------------------------------------

    def createGenericObject(self, obj):
        from isaacsim.core.experimental.prims import RigidPrim, XformPrim
        import isaacsim.core.experimental.utils.stage as stage_utils

        prim_path = f"/World/{obj.name}"
        stage_utils.define_prim(prim_path, "Xform")
        stage_utils.add_reference_to_stage(
            usd_path=self.objectUsdPath(obj), path=f"{prim_path}/asset"
        )

        orientation = self.scenicToIsaacOrientation(obj.orientation)
        geometry_paths = self._geometryPathsUnder(prim_path)
        self._applyCollisionsToGeometry(geometry_paths)

        # Scale the asset (under /World/<name>/asset) to Scenic's dimensions.
        root_position, local_scale, _, _ = self.computeUsdScaleAndRootPosition(
            obj, prim_path, scenic_utils.vectorToArray(obj.position), orientation
        )

        prim_kwargs = dict(
            positions=root_position,
            orientations=orientation,
            scales=local_scale,
            reset_xform_op_properties=True,
        )
        if obj.physics:
            wrapper = RigidPrim(prim_path, **prim_kwargs)
            if obj.mass is not None:
                wrapper.set_masses(np.asarray([obj.mass], dtype=np.float32))
            if obj.density is not None:
                wrapper.set_densities(np.asarray([obj.density], dtype=np.float32))
            wrapper.set_velocities(
                linear_velocities=scenic_utils.vectorToArray(obj.velocity)
            )
        else:
            wrapper = XformPrim(prim_path, **prim_kwargs)
            self.disableRigidBody(prim_path)

        if obj.color:
            self.applyVisualMaterial(wrapper, obj, geometry_paths=geometry_paths)

        obj._isaac_generic_prim_path = prim_path
        return wrapper

    def _geometryPathsUnder(self, prim_path):
        import isaacsim.core.experimental.utils.stage as stage_utils
        from pxr import Usd, UsdGeom

        prim = stage_utils.get_current_stage().GetPrimAtPath(prim_path)
        return [
            str(descendant.GetPath())
            for descendant in Usd.PrimRange(prim)
            if descendant.IsA(UsdGeom.Gprim)
        ]

    def _applyCollisionsToGeometry(self, geometry_paths):
        if not geometry_paths:
            return
        from isaacsim.core.experimental.prims import GeomPrim

        geom = GeomPrim(geometry_paths, apply_collision_apis=True)
        geom.set_collision_approximations(["convexDecomposition"])

    def disableRigidBody(self, prim_path):
        import isaacsim.core.experimental.utils.stage as stage_utils
        from pxr import Usd, UsdPhysics

        prim = stage_utils.get_current_stage().GetPrimAtPath(prim_path)
        for descendant in Usd.PrimRange(prim):
            if descendant.HasAPI(UsdPhysics.RigidBodyAPI):
                UsdPhysics.RigidBodyAPI(descendant).CreateRigidBodyEnabledAttr(False)

    def applyVisualMaterial(self, wrapper, obj, geometry_paths=None):
        from isaacsim.core.experimental.materials import PreviewSurfaceMaterial
        from isaacsim.core.experimental.prims import GeomPrim

        material = PreviewSurfaceMaterial(f"/World/material/{obj.name}")
        color = scenic_utils.colorToArray(obj.color)
        material.set_input_values("diffuseColor", color[:3])
        if len(color) > 3:
            material.set_input_values("opacity", [color[3]])

        if geometry_paths:
            GeomPrim(geometry_paths).apply_visual_materials(material)
        else:
            wrapper.apply_visual_materials(material)

    def createRobot(self, obj):
        from isaacsim.core.experimental.prims import Articulation
        import isaacsim.core.experimental.utils.stage as stage_utils

        if obj.manipulatorProfile is not None:
            return self.createManipulator(obj)

        if isWheeledRobot(obj):
            return self.createWheeledRobot(obj)

        prim_path = f"/World/{obj.name}"
        stage_utils.add_reference_to_stage(
            usd_path=self.objectUsdPath(obj), path=prim_path
        )
        wrapper = Articulation(
            prim_path,
            positions=scenic_utils.vectorToArray(obj.position),
            orientations=self.scenicToIsaacOrientation(
                obj.orientation, initial_rotation=obj.initialRotation
            ),
            reset_xform_op_properties=True,
        )
        if obj.control:
            obj.controller = obj.control
        if obj.color:
            self.applyVisualMaterial(
                wrapper, obj, geometry_paths=self._geometryPathsUnder(prim_path)
            )
        return wrapper

    def createWheeledRobot(self, obj):
        from isaacsim.robot.experimental.wheeled_robots.controllers import (
            AckermannController,
            DifferentialController,
            HolonomicController,
        )
        from isaacsim.robot.experimental.wheeled_robots.robots import (
            HolonomicRobotUsdSetup,
            WheeledRobot,
        )

        prim_path = f"/World/{obj.name}"
        wrapper = WheeledRobot(
            paths=prim_path,
            wheel_dof_names=obj.wheelDofNames,
            usd_path=self.objectUsdPath(obj),
            positions=scenic_utils.vectorToArray(obj.position),
            orientations=self.scenicToIsaacOrientation(
                obj.orientation, initial_rotation=obj.initialRotation
            ),
        )

        obj.wheelDofIndices = wrapper.get_dof_indices(obj.wheelDofNames)

        if obj.wheelController == "differential":
            obj.controller = DifferentialController(
                wheel_radius=obj.wheelRadius,
                wheel_base=obj.wheelBase,
            )
        elif obj.wheelController == "holonomic":
            holonomic_setup = HolonomicRobotUsdSetup(
                robot_prim_path=prim_path,
                com_prim_path=f"{prim_path}/base_link/control_offset",
            )
            (
                wheel_radius,
                wheel_positions,
                wheel_orientations,
                mecanum_angles,
                wheel_axis,
                up_axis,
            ) = holonomic_setup.get_holonomic_controller_params()
            obj.controller = HolonomicController(
                wheel_radius=wheel_radius,
                wheel_positions=wheel_positions,
                wheel_orientations=wheel_orientations,
                mecanum_angles=mecanum_angles,
                wheel_axis=wheel_axis,
                up_axis=up_axis,
                max_linear_speed=obj.maxLinearSpeed,
                max_angular_speed=obj.maxAngularSpeed,
                max_wheel_speed=obj.maxWheelSpeed,
            )
        elif obj.wheelController == "ackermann":
            if not obj.steeringDofNames:
                raise ValueError(
                    f"Ackermann robot {obj.name} requires steeringDofNames, "
                    "usually [front_left_steering_joint, front_right_steering_joint]."
                )
            obj.steeringDofIndices = wrapper.get_dof_indices(obj.steeringDofNames)
            obj.controller = AckermannController(
                wheel_base=obj.wheelBase,
                track_width=obj.trackWidth,
                front_wheel_radius=obj.frontWheelRadius,
                back_wheel_radius=obj.backWheelRadius,
            )

        if obj.color:
            self.applyVisualMaterial(wrapper, obj)

        return wrapper

    def createManipulator(self, obj):
        from isaacsim.core.experimental.prims import Articulation, RigidPrim
        import isaacsim.core.experimental.utils.stage as stage_utils

        profile = obj.manipulatorProfile
        prim_path = f"/World/{obj.name}"

        robot_prim = stage_utils.add_reference_to_stage(
            usd_path=self.kitUsdPath(profile.usdPath), path=prim_path
        )
        for variant_name, selection in profile.usdVariants:
            self.setRequiredVariant(robot_prim, variant_name, selection)

        stage = stage_utils.get_current_stage()
        self.requireStagePrim(stage, f"{prim_path}/{profile.endEffectorPrim}")
        if profile.gripperStyle == "robotiq_2f85":
            configureRobotiqGripper(stage, prim_path, profile)
            configureRobotiqContactMaterial(stage, prim_path, profile)

        wrapper = Articulation(
            prim_path,
            positions=self.manipulatorRootPosition(obj),
            orientations=self.scenicToIsaacOrientation(
                obj.orientation, initial_rotation=obj.initialRotation
            ),
            reset_xform_op_properties=True,
        )
        arm_dof_indices = self._dofIndices(wrapper, list(profile.armDofNames))
        if obj.armMaxVelocities is not None:
            wrapper.set_dof_max_velocities(
                obj.armMaxVelocities, dof_indices=arm_dof_indices
            )
        gripper_dof_indices = self._dofIndices(wrapper, list(profile.gripperDofNames))
        default_dof_positions = np.zeros(len(wrapper.dof_names), dtype=float)
        for value, dof_index in zip(profile.defaultArmPose, arm_dof_indices):
            default_dof_positions[dof_index] = value
        for value, dof_index in zip(profile.openGripperPositions, gripper_dof_indices):
            default_dof_positions[dof_index] = value
        wrapper.set_default_state(dof_positions=default_dof_positions)

        obj._manipulator_metadata = {
            "prim_path": prim_path,
            "end_effector": RigidPrim(f"{prim_path}/{profile.endEffectorPrim}"),
            "end_effector_link_index": self._linkIndex(wrapper, profile.controlLinkName),
            "arm_dof_indices": arm_dof_indices,
            "gripper_dof_indices": gripper_dof_indices,
            "default_dof_positions": default_dof_positions,
        }
        if profile.supportsPickPlace:
            obj._manipulator_pick_place_state = None

        if obj.color:
            self.applyVisualMaterial(
                wrapper, obj, geometry_paths=self._geometryPathsUnder(prim_path)
            )
        return wrapper

    def _linkIndex(self, articulation, name):
        indices = articulation.get_link_indices(name).list()
        if len(indices) != 1:
            raise RuntimeError(f"Expected one link named {name!r}, found {len(indices)}")
        return indices[0]

    def _dofIndices(self, articulation, names):
        dof_names = list(articulation.dof_names)
        missing = [name for name in names if name not in dof_names]
        if missing:
            raise RuntimeError(
                f"{articulation.paths[0]} is missing required DOFs: {missing}"
            )
        return [dof_names.index(name) for name in names]

    def createGroundPlane(self, obj):
        from isaacsim.core.experimental.objects import GroundPlane

        wrapper = GroundPlane(
            "/World/GroundPlane",
            sizes=max(obj.width, obj.length),
            positions=[0, 0, 0],
        )
        if obj.color:
            self.applyVisualMaterial(wrapper, obj)
        return wrapper

    # ------------------------------------------------------------------
    # Control and state
    # ------------------------------------------------------------------

    def applyRobotControl(self, sim, obj, command):
        if obj.controller is None:
            return
        if isWheeledRobot(obj):
            self.applyWheeledControl(sim, obj, command)
            return

        wrapper = sim.world.getObject(obj.name)
        self._applyArticulationAction(wrapper, obj.controller(command))

    def applyWheeledControl(self, sim, obj, command):
        if obj.controller is None:
            return
        wrapper = sim.world.getObject(obj.name)

        if obj.wheelController == "ackermann":
            # Ackermann command: [steering_angle, steering_angle_velocity, speed, acceleration, dt]
            steering_positions, wheel_velocities = obj.controller.forward(command)
            wrapper.set_dof_position_targets(
                steering_positions, dof_indices=obj.steeringDofIndices
            )
            wrapper.apply_wheel_actions(wheel_velocities)
            return

        # Differential command: [linear_speed, angular_speed]
        # Holonomic command: [forward_speed, lateral_speed, yaw_speed]
        wrapper.apply_wheel_actions(obj.controller.forward(command))

    def applyArticulationAction(self, sim, obj, action):
        self._applyArticulationAction(sim.world.getObject(obj.name), action)

    def _applyArticulationAction(self, articulation, action):
        dof_indices = action.get("joint_indices", action.get("dof_indices"))
        if "joint_positions" in action:
            articulation.set_dof_position_targets(
                action["joint_positions"],
                dof_indices=action.get("joint_position_indices", dof_indices),
            )
        if "joint_velocities" in action:
            articulation.set_dof_velocity_targets(
                action["joint_velocities"],
                dof_indices=action.get("joint_velocity_indices", dof_indices),
            )
        if "joint_efforts" in action:
            articulation.set_dof_efforts(
                action["joint_efforts"],
                dof_indices=action.get("joint_effort_indices", dof_indices),
            )

    def articulationDofNames(self, sim, obj):
        return list(sim.world.getObject(obj.name).dof_names)

    def getObjectPose(self, sim, obj):
        position, orientation = sim.world.getObject(obj.name).get_world_poses()
        return position.numpy()[0], orientation.numpy()[0]

    def setObjectPose(self, sim, obj, position, orientation=None):
        wrapper = sim.world.getObject(obj.name)
        position = np.array(position, dtype=float)
        if orientation is None:
            _, orientation = self.getObjectPose(sim, obj)
        orientation = np.array(orientation, dtype=float)
        wrapper.set_world_poses(positions=position, orientations=orientation)
        if hasattr(wrapper, "set_velocities"):
            wrapper.set_velocities(
                linear_velocities=np.zeros(3, dtype=float),
                angular_velocities=np.zeros(3, dtype=float),
            )

    def getPhysicsProperties(self, world, obj):
        wrapper = world.getObject(obj.name)
        position, orientation = wrapper.get_world_poses()
        yaw, pitch, roll = self.isaacQuatToScenicEulerAngles(
            orientation.numpy()[0], initial_rotation=obj.initialRotation
        )
        linear_velocity, angular_velocity = wrapper.get_velocities()
        lx, ly, lz = linear_velocity.numpy()[0]
        ax, ay, az = angular_velocity.numpy()[0]
        return {
            "position": tuple(position.numpy()[0]),
            "velocity": (lx, ly, lz),
            "speed": math.hypot(lx, ly, lz),
            "angularSpeed": math.hypot(ax, ay, az),
            "angularVelocity": (ax, ay, az),
            "yaw": yaw,
            "pitch": pitch,
            "roll": roll,
        }

    # ------------------------------------------------------------------
    # Manipulators (differential IK on the articulation Jacobian)
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
        if not obj.manipulatorProfile.supportsPickPlace:
            raise RuntimeError(
                f"{type(obj).__name__} does not support built-in pick-place"
            )
        wrapper = sim.world.getObject(obj.name)

        state = obj._manipulator_pick_place_state
        if state is None:
            state = ManipulatorPickPlaceState()
            obj._manipulator_pick_place_state = state
            self._resetManipulator(obj, wrapper)

        if state.done:
            return

        if endEffectorOrientation is None:
            endEffectorOrientation = obj.endEffectorOrientation
        if endEffectorOffset is None:
            endEffectorOffset = obj.endEffectorOffset

        self._moveManipulatorPickPlaceHelper(
            wrapper,
            obj,
            state,
            sim,
            targetObject,
            goalPosition,
            np.asarray(endEffectorOffset, dtype=float),
            endEffectorOrientation,
        )

    def _moveManipulatorPickPlaceHelper(
        self,
        wrapper,
        obj,
        state,
        sim,
        targetObject,
        goalPosition,
        endEffectorOffset,
        endEffectorOrientation=None,
    ):
        profile = obj.manipulatorProfile

        if state.pick_position is None:
            target_wrapper = sim.world.getObject(targetObject.name)
            state.pick_position = target_wrapper.get_world_poses()[0].numpy()[0].copy()

        if state.place_position is None:
            state.place_position = scenic_utils.vectorToArray(goalPosition).copy()

        cube_position = state.pick_position
        place_position = state.place_position

        current_position, current_orientation = self._manipulatorEndEffectorPose(obj)

        if endEffectorOrientation is not None:
            state.endEffectorOrientation = np.asarray(
                endEffectorOrientation, dtype=float
            ).copy()
        elif state.endEffectorOrientation is None:
            state.endEffectorOrientation = profile.downwardOrientation.copy()

        orientation = state.endEffectorOrientation

        # (end-effector target, gripper state, steps to spend in the phase)
        phases = [
            (cube_position + np.array([0.0, 0.0, 0.20]), "open", 120),
            (cube_position + np.array([0.0, 0.0, 0.10]), "open", 80),
            (None, "closed", 50),
            (cube_position + np.array([0.0, 0.0, 0.50]), "closed", 150),
            (place_position + np.array([0.0, 0.0, 0.50]), "closed", 180),
            (place_position + np.array([0.0, 0.0, 0.20]), "closed", 90),
            (None, "open", 20),
        ]

        target, gripper_state, steps = phases[state.stage]

        if target is not None:
            self._moveManipulatorEndEffector(
                wrapper,
                obj,
                current_position=current_position,
                current_orientation=current_orientation,
                goalPosition=np.asarray([target + endEffectorOffset], dtype=float),
                goal_orientation=np.asarray([orientation], dtype=float),
            )

        self._setManipulatorGripper(wrapper, obj, gripper_state)

        state.stage_steps += 1
        if state.stage_steps > steps:
            print(
                f"Pick-place stage={state.stage}, steps={state.stage_steps}, "
                f"target={target}, gripper={gripper_state}",
                flush=True,
            )

            state.stage += 1
            state.stage_steps = 0

            if state.stage >= len(phases):
                state.done = True

    def _resetManipulator(self, obj, wrapper):
        metadata = obj._manipulator_metadata
        wrapper.reset_to_default_state()
        wrapper.set_dof_position_targets(metadata["default_dof_positions"])
        if obj.manipulatorProfile.gripperControlMode == "position":
            self._setManipulatorGripper(wrapper, obj, "open")

    def _ensureManipulatorControlReady(self, obj, wrapper):
        metadata = obj._manipulator_metadata
        if not metadata.get("primitive_control_ready", False):
            self._resetManipulator(obj, wrapper)
            metadata["primitive_control_ready"] = True

    def _manipulatorEndEffectorPose(self, obj):
        position, orientation = obj._manipulator_metadata[
            "end_effector"
        ].get_world_poses()
        return position.numpy(), orientation.numpy()

    def _manipulatorTcpPosition(self, obj, control_position, orientation):
        tcp_offset = obj.manipulatorProfile.tcpOffset
        control_position = np.asarray(control_position, dtype=float).reshape(-1)[:3]
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        return control_position + self.rotateVectorByWxyzQuat(orientation, tcp_offset)

    def _manipulatorControlPosition(self, obj, tcp_position, orientation):
        tcp_offset = obj.manipulatorProfile.tcpOffset
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        return positionArray(tcp_position) - self.rotateVectorByWxyzQuat(
            orientation, tcp_offset
        )

    def _moveManipulatorEndEffector(
        self,
        wrapper,
        obj,
        current_position,
        current_orientation,
        goalPosition,
        goal_orientation=None,
    ):
        profile = obj.manipulatorProfile
        metadata = obj._manipulator_metadata
        arm_dof_indices = metadata["arm_dof_indices"]

        current_dof_positions = wrapper.get_dof_positions().numpy()
        jacobian_matrices = wrapper.get_jacobian_matrices().numpy()

        jacobian_link_index = metadata["end_effector_link_index"] - 1
        if jacobian_link_index < 0:
            raise RuntimeError(
                "Manipulator control link index cannot be used for Jacobian"
            )
        jacobian_end_effector = np.take(
            jacobian_matrices[:, jacobian_link_index, :, :],
            arm_dof_indices,
            axis=-1,
        )

        delta_dof_positions = _differentialInverseKinematics(
            jacobian_end_effector=jacobian_end_effector,
            current_position=np.asarray(current_position, dtype=float).reshape(1, 3),
            current_orientation=np.asarray(current_orientation, dtype=float).reshape(
                1, 4
            ),
            goalPosition=np.asarray(goalPosition, dtype=float).reshape(1, 3),
            goal_orientation=(
                None
                if goal_orientation is None
                else np.asarray(goal_orientation, dtype=float).reshape(1, 4)
            ),
            damping=profile.ikDamping,
            scale=profile.ikStepScale,
        )

        if current_dof_positions.ndim == 1:
            dof_position_targets = (
                current_dof_positions[arm_dof_indices] + delta_dof_positions[0]
            )
        else:
            dof_position_targets = (
                current_dof_positions[:, arm_dof_indices] + delta_dof_positions
            )

        wrapper.set_dof_position_targets(
            dof_position_targets, dof_indices=arm_dof_indices
        )

    def _setManipulatorGripper(self, wrapper, obj, state):
        profile = obj.manipulatorProfile
        indices = obj._manipulator_metadata["gripper_dof_indices"]

        if profile.gripperControlMode == "velocity":
            velocity = (
                profile.gripperOpenVelocity
                if state == "open"
                else profile.gripperCloseVelocity
            )
            wrapper.switch_dof_control_mode("velocity", dof_indices=indices)
            wrapper.set_dof_velocity_targets(
                np.full((1, len(indices)), float(velocity), dtype=float),
                dof_indices=indices,
            )
            return

        wrapper.set_dof_position_targets(
            self.manipulatorGripperTargetPositions(profile, state == "open"),
            dof_indices=indices,
        )

    def moveManipulatorEndEffector(self, sim, obj, position, orientation=None):
        wrapper = sim.world.getObject(obj.name)
        self._ensureManipulatorControlReady(obj, wrapper)
        current_position, current_orientation = self._manipulatorEndEffectorPose(obj)
        if orientation is None:
            orientation = obj.manipulatorProfile.downwardOrientation
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        goalPosition = self._manipulatorControlPosition(obj, position, orientation)
        self._moveManipulatorEndEffector(
            wrapper,
            obj,
            current_position,
            current_orientation,
            np.array([goalPosition], dtype=float),
            np.array([orientation], dtype=float),
        )

    def setManipulatorGripper(self, sim, obj, opened):
        wrapper = sim.world.getObject(obj.name)
        self._ensureManipulatorControlReady(obj, wrapper)
        self._setManipulatorGripper(wrapper, obj, "open" if opened else "closed")

    def setManipulatorArmJointPositions(self, sim, obj, joint_positions):
        wrapper = sim.world.getObject(obj.name)
        self._ensureManipulatorControlReady(obj, wrapper)
        joint_positions = np.asarray(joint_positions, dtype=float).reshape(-1)
        arm_dof_indices = obj._manipulator_metadata["arm_dof_indices"]
        if len(joint_positions) > len(arm_dof_indices):
            raise RuntimeError(
                f"Arm joint target has more than {len(arm_dof_indices)} positions"
            )
        wrapper.set_dof_position_targets(
            joint_positions.tolist(),
            dof_indices=arm_dof_indices[: len(joint_positions)],
        )

    def holdManipulatorPosition(self, sim, obj):
        wrapper = sim.world.getObject(obj.name)
        self._ensureManipulatorControlReady(obj, wrapper)
        arm_dof_indices = obj._manipulator_metadata["arm_dof_indices"]
        current_dof_positions = wrapper.get_dof_positions().numpy()
        arm_targets = current_dof_positions[:, arm_dof_indices].reshape(-1).tolist()
        wrapper.set_dof_position_targets(arm_targets, dof_indices=arm_dof_indices)

    def getManipulatorEndEffectorPose(self, sim, obj):
        position, orientation = self._manipulatorEndEffectorPose(obj)
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        return self._manipulatorTcpPosition(obj, position, orientation), orientation

    def getManipulatorGripperPositions(self, sim, obj):
        wrapper = sim.world.getObject(obj.name)
        gripper_dof_indices = obj._manipulator_metadata["gripper_dof_indices"]
        dof_positions = wrapper.get_dof_positions().numpy()
        return dof_positions[:, gripper_dof_indices].reshape(-1)
