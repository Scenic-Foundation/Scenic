import math

import numpy as np
from scipy.spatial.transform import Rotation

from scenic.simulators.isaac.backends.base import (
    IsaacBackend,
    isWheeledRobot,
    positionArray,
    rotationToWxyz,
)
from scenic.simulators.isaac.backends.robotiq import configureRobotiqGripper
import scenic.simulators.isaac.utils as scenic_utils


def _asArray(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value, dtype=float)


class _AckermannControllerAdapter:
    """Give the Core AckermannController the (steering, wheel velocities) forward() of the experimental one."""

    def __init__(self, controller):
        self.controller = controller

    def forward(self, command):
        action = self.controller.forward(command=command)
        return action.joint_positions, action.joint_velocities


class Core51Backend(IsaacBackend):
    """Isaac Sim 5.1.0 backend implemented with the Core API."""

    name = "core_51"

    def createWorld(self, timestep):
        from isaacsim.core.api import World

        return World(
            stage_units_in_meters=1.0,
            physics_dt=timestep,
            rendering_dt=timestep,
        )

    def openEnvironmentStage(self, usd_path):
        from isaacsim.core.utils import stage as stage_utils

        if not stage_utils.open_stage(usd_path):
            return False

        stage = stage_utils.get_current_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        return True

    def enableExtension(self, name):
        from isaacsim.core.utils.extensions import enable_extension

        enable_extension(name)

    def initializePhysics(self, world, objects):
        world.initialize_physics()
        for obj in objects:
            if not obj.physics:
                continue
            isaac_obj = world.scene.get_object(obj.name)
            if hasattr(isaac_obj, "initialize"):
                isaac_obj.initialize()
            if isWheeledRobot(obj):
                obj.wheelDofIndices = list(isaac_obj.wheel_dof_indices)
                if obj.wheelController == "ackermann":
                    obj.steeringDofIndices = [
                        isaac_obj.get_dof_index(name) for name in obj.steeringDofNames
                    ]

    def playWorld(self, world):
        world.play()

    def stepWorld(self, world):
        world.step()

    def stopAndClearWorld(self, world):
        world.stop()
        world.clear()
        world.reset()

    def releaseWorld(self, world):
        from isaacsim.core.api import World

        World.clear_instance()

    def addObject(self, world, obj, *, scenic_obj=None):
        world.scene.add(obj)

    def applyVisualMaterial(self, wrapper, obj):
        from isaacsim.core.api.materials import PreviewSurface

        material = PreviewSurface(
            prim_path=f"/World/material/{obj.name}",
            color=scenic_utils.colorToArray(obj.color),
        )
        wrapper.apply_visual_material(material)

    def disableRigidBody(self, prim):
        from pxr import Usd, UsdPhysics

        for descendant in Usd.PrimRange(prim):
            if descendant.HasAPI(UsdPhysics.RigidBodyAPI):
                UsdPhysics.RigidBodyAPI(descendant).CreateRigidBodyEnabledAttr(False)

    def createController(self, forward_func, name):
        from isaacsim.core.api.controllers import BaseController

        class Controller(BaseController):
            def __init__(self):
                super().__init__(name=name)

            def forward(self, command):
                return forward_func(command)

        return Controller()

    def createGenericObject(self, obj):
        from isaacsim.core.prims import SingleGeometryPrim, SingleRigidPrim
        from isaacsim.core.utils import prims
        from omni.physx.scripts import utils as physx_utils

        prim_path = f"/World/{obj.name}"
        usd_prim = prims.create_prim(
            prim_path=prim_path, usd_path=self.objectUsdPath(obj)
        )
        orientation = self.scenicToIsaacOrientation(obj.orientation)

        # Scale the asset from its native size to Scenic's dimensions.
        root_position, local_scale, _, _ = self.computeUsdScaleAndRootPosition(
            obj, prim_path, scenic_utils.vectorToArray(obj.position), orientation
        )

        if obj.physics:
            physx_utils.setRigidBody(
                prims.get_prim_at_path(prim_path), "convexDecomposition", False
            )
            wrapper = SingleRigidPrim(
                prim_path=prim_path,
                name=obj.name,
                position=root_position,
                orientation=orientation,
                mass=obj.mass,
                density=obj.density,
                linear_velocity=scenic_utils.vectorToArray(obj.velocity),
            )
        else:
            wrapper = SingleGeometryPrim(
                prim_path=prim_path,
                name=obj.name,
                position=root_position,
                orientation=orientation,
                collision=True,
            )
            self.disableRigidBody(usd_prim)

        wrapper.set_world_pose(position=root_position, orientation=orientation)
        wrapper.set_local_scale(local_scale)

        if obj.color:
            self.applyVisualMaterial(wrapper, obj)
        return wrapper

    def createRobot(self, obj):
        from isaacsim.core.api.robots import Robot
        from isaacsim.core.utils.stage import add_reference_to_stage

        if obj.manipulatorProfile is not None:
            return self.createManipulator(obj)

        if isWheeledRobot(obj):
            return self.createWheeledRobot(obj)

        if obj.control:
            obj.controller = self.createController(obj.control, f"{obj.name}_controller")

        prim_path = f"/World/{obj.name}"
        add_reference_to_stage(self.objectUsdPath(obj), prim_path)
        return Robot(
            prim_path=prim_path,
            name=obj.name,
            position=scenic_utils.vectorToArray(obj.position),
            orientation=self.scenicToIsaacOrientation(
                obj.orientation, initial_rotation=obj.initialRotation
            ),
        )

    def createWheeledRobot(self, obj):
        from isaacsim.robot.wheeled_robots.controllers import (
            AckermannController,
            DifferentialController,
            HolonomicController,
        )
        from isaacsim.robot.wheeled_robots.robots import (
            HolonomicRobotUsdSetup,
            WheeledRobot,
        )

        prim_path = f"/World/{obj.name}"
        wrapper = WheeledRobot(
            prim_path=prim_path,
            name=obj.name,
            wheel_dof_names=obj.wheelDofNames,
            create_robot=True,
            usd_path=self.objectUsdPath(obj),
            position=scenic_utils.vectorToArray(obj.position),
            orientation=self.scenicToIsaacOrientation(
                obj.orientation, initial_rotation=obj.initialRotation
            ),
        )

        if obj.wheelController == "differential":
            obj.controller = DifferentialController(
                name=f"{obj.name}_controller",
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
                name=f"{obj.name}_controller",
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
            obj.controller = _AckermannControllerAdapter(
                AckermannController(
                    name=f"{obj.name}_controller",
                    wheel_base=obj.wheelBase,
                    track_width=obj.trackWidth,
                    front_wheel_radius=obj.frontWheelRadius,
                    back_wheel_radius=obj.backWheelRadius,
                )
            )

        if obj.color:
            self.applyVisualMaterial(wrapper, obj)
        return wrapper

    def createManipulator(self, obj):
        from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
        from isaacsim.robot.manipulators import SingleManipulator
        from isaacsim.robot.manipulators.grippers import ParallelGripper

        profile = obj.manipulatorProfile
        prim_path = f"/World/{obj.name}"
        robot_prim = add_reference_to_stage(
            usd_path=self.kitUsdPath(profile.usdPath), prim_path=prim_path
        )
        for variant_name, selection in profile.usdVariants:
            self.setRequiredVariant(robot_prim, variant_name, selection)

        stage = get_current_stage()
        end_effector_prim_path = f"{prim_path}/{profile.gripperFramePrim}"
        self.requireStagePrim(stage, end_effector_prim_path)

        gripper_kwargs = dict(
            end_effector_prim_path=end_effector_prim_path,
            joint_prim_names=list(profile.gripperDofNames),
            joint_opened_positions=profile.openGripperPositions.copy(),
            joint_closed_positions=profile.closedGripperPositions.copy(),
        )
        if profile.gripperStyle == "robotiq_2f85":
            configureRobotiqGripper(stage, prim_path, profile)
            gripper = ParallelGripper(use_mimic_joints=True, **gripper_kwargs)
        else:
            action_deltas = getattr(profile, "gripperActionDeltas", None)
            if action_deltas is not None:
                action_deltas = np.array(action_deltas, dtype=float)
            gripper = ParallelGripper(action_deltas=action_deltas, **gripper_kwargs)

        wrapper = SingleManipulator(
            prim_path=prim_path,
            name=obj.name,
            position=self.manipulatorRootPosition(obj),
            orientation=self.scenicToIsaacOrientation(obj.orientation),
            end_effector_prim_path=end_effector_prim_path,
            gripper=gripper,
        )
        wrapper.gripper.set_default_state(wrapper.gripper.joint_opened_positions)
        obj._core_manipulator_ready = False
        obj._core_motion_policy_states = {}
        return wrapper

    def createGroundPlane(self, obj):
        from isaacsim.core.api.objects import GroundPlane

        return GroundPlane(
            name=obj.name,
            prim_path="/World/GroundPlane",
            z_position=0,
            size=max(obj.width, obj.length),
            color=scenic_utils.colorToArray(obj.color),
        )

    def applyRobotControl(self, sim, obj, command):
        if obj.controller is None:
            return
        if isWheeledRobot(obj):
            self.applyWheeledControl(sim, obj, command)
            return

        robot = sim.world.scene.get_object(obj.name)
        action = obj.controller.forward(command=command)
        robot.apply_action(self._toCoreArticulationAction(action))

    def applyWheeledControl(self, sim, obj, command):
        if obj.controller is None:
            return
        wheeled_robot = sim.world.scene.get_object(obj.name)

        if obj.wheelController == "ackermann":
            from isaacsim.core.utils.types import ArticulationAction

            steering_positions, wheel_velocities = obj.controller.forward(command)
            wheeled_robot.apply_action(
                ArticulationAction(
                    joint_positions=steering_positions,
                    joint_indices=obj.steeringDofIndices,
                )
            )
            wheeled_robot.apply_wheel_actions(
                ArticulationAction(joint_velocities=wheel_velocities)
            )
            return

        # Differential command: [linear_speed, angular_speed]
        # Holonomic command: [forward_speed, lateral_speed, yaw_speed]
        wheeled_robot.apply_wheel_actions(obj.controller.forward(command=command))

    def applyArticulationAction(self, sim, obj, action):
        robot = sim.world.scene.get_object(obj.name)
        for field, index_field in (
            ("joint_positions", "joint_position_indices"),
            ("joint_velocities", "joint_velocity_indices"),
            ("joint_efforts", "joint_effort_indices"),
        ):
            split_action = self._coreActionForField(action, field, index_field)
            if split_action is not None:
                robot.apply_action(split_action)

    def _coreActionForField(self, action, field, index_field):
        values = action.get(field)
        if values is None:
            return None

        from isaacsim.core.utils.types import ArticulationAction

        indices = action.get(
            index_field,
            action.get("joint_indices", action.get("dof_indices")),
        )
        return ArticulationAction(**{field: values, "joint_indices": indices})

    def _toCoreArticulationAction(self, action):
        from isaacsim.core.utils.types import ArticulationAction

        return ArticulationAction(**action)

    def articulationDofNames(self, sim, obj):
        robot = sim.world.scene.get_object(obj.name)
        for attr in ("dof_names", "_dof_names"):
            names = getattr(robot, attr, None)
            if names is not None:
                return list(names)
        raise RuntimeError(f"unable to read DOF names for {obj.name}")

    def getObjectPose(self, sim, obj):
        wrapper = sim.world.scene.get_object(obj.name)
        position, orientation = wrapper.get_world_pose()
        return np.array(position, dtype=float), np.array(orientation, dtype=float)

    def setObjectPose(self, sim, obj, position, orientation=None):
        wrapper = sim.world.scene.get_object(obj.name)
        position = np.array(position, dtype=float)
        if orientation is None:
            _, orientation = wrapper.get_world_pose()
        orientation = np.array(orientation, dtype=float)
        wrapper.set_world_pose(position=position, orientation=orientation)
        if hasattr(wrapper, "set_linear_velocity"):
            wrapper.set_linear_velocity(np.zeros(3, dtype=float))
        if hasattr(wrapper, "set_angular_velocity"):
            wrapper.set_angular_velocity(np.zeros(3, dtype=float))

    # ------------------------------------------------------------------
    # Manipulators (RMPflow motion policies + Isaac's PickPlaceController)
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
        manipulator = sim.world.scene.get_object(obj.name)
        if obj.controller is None:
            from isaacsim.robot.manipulators.examples.franka.controllers.pick_place_controller import (
                PickPlaceController,
            )

            obj.controller = PickPlaceController(
                name=f"{obj.name}_pick_place_controller",
                gripper=manipulator.gripper,
                robot_articulation=manipulator,
            )
            obj.controller.reset()
            manipulator.gripper.set_joint_positions(
                manipulator.gripper.joint_opened_positions
            )
        if obj.controller.is_done():
            return

        target = sim.world.scene.get_object(targetObject.name)
        picking_position, _ = target.get_world_pose()
        placing_position = scenic_utils.vectorToArray(goalPosition)
        if endEffectorOffset is None:
            endEffectorOffset = obj.endEffectorOffset
        if endEffectorOrientation is None:
            endEffectorOrientation = obj.endEffectorOrientation
        actions = obj.controller.forward(
            picking_position=picking_position,
            placing_position=placing_position,
            current_joint_positions=manipulator.get_joint_positions(),
            end_effector_offset=np.array(endEffectorOffset, dtype=float),
            end_effector_orientation=endEffectorOrientation,
        )
        manipulator.apply_action(actions)

    def _motionPolicyState(self, sim, obj, manipulator, robot_name):
        states = obj._core_motion_policy_states
        if robot_name not in states:
            import isaacsim.robot_motion.motion_generation as mg

            config = mg.interface_config_loader.load_supported_motion_policy_config(
                robot_name, "RMPflow"
            )
            if config is None:
                raise RuntimeError(f"{robot_name} has no supported RMPflow config")
            rmp_flow = mg.lula.motion_policies.RmpFlow(**config)
            self._syncMotionPolicyBase(manipulator, rmp_flow)
            policy = mg.ArticulationMotionPolicy(manipulator, rmp_flow, sim.timestep)
            states[robot_name] = {
                "controller": mg.MotionPolicyController(
                    name=f"{obj.name}_{robot_name}_rmpflow",
                    articulation_motion_policy=policy,
                ),
                "policy": policy,
                "rmp_flow": rmp_flow,
            }
        return states[robot_name]

    def _syncMotionPolicyBase(self, manipulator, rmp_flow):
        position, orientation = manipulator.get_world_pose()
        rmp_flow.set_robot_base_pose(
            robot_position=position,
            robot_orientation=orientation,
        )

    def _manipulator(self, sim, obj):
        """Return the manipulator wrapper, moving it to its home pose on first use."""
        wrapper = sim.world.scene.get_object(obj.name)
        if not obj._core_manipulator_ready:
            profile = obj.manipulatorProfile
            if profile.gripperStyle == "robotiq_2f85":
                arm_dof_indices = self._coreDofIndices(wrapper, profile.armDofNames)
                wrapper.set_joint_positions(
                    profile.defaultArmPose,
                    joint_indices=np.asarray(arm_dof_indices, dtype=np.int32),
                )
            wrapper.gripper.set_joint_positions(wrapper.gripper.joint_opened_positions)
            obj._core_manipulator_ready = True
        return wrapper

    def moveManipulatorEndEffector(self, sim, obj, position, orientation=None):
        profile = obj.manipulatorProfile
        manipulator = self._manipulator(sim, obj)
        state = self._motionPolicyState(sim, obj, manipulator, profile.rmpflowPolicyName)
        self._syncMotionPolicyBase(manipulator, state["rmp_flow"])
        if orientation is None:
            orientation = profile.downwardOrientation
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        if profile.rmpflowUsesTcpOffset:
            target_position = self._tcpToControlPosition(
                position, orientation, profile.tcpOffset
            )
        else:
            target_position = positionArray(position)
        action = state["controller"].forward(
            target_end_effector_position=target_position,
            target_end_effector_orientation=orientation,
        )
        manipulator.apply_action(action)

    def setManipulatorGripper(self, sim, obj, opened):
        profile = obj.manipulatorProfile
        manipulator = self._manipulator(sim, obj)
        if profile.gripperControlMode == "velocity":
            from isaacsim.core.utils.types import ArticulationAction

            velocity = (
                profile.gripperOpenVelocity if opened else profile.gripperCloseVelocity
            )
            indices = self._coreDofIndices(manipulator, profile.gripperDofNames)
            manipulator.get_articulation_controller().switch_dof_control_mode(
                dof_index=indices[0], mode="velocity"
            )
            action = ArticulationAction(
                joint_velocities=np.array([velocity], dtype=float),
                joint_indices=np.asarray(indices, dtype=np.int32),
            )
            manipulator.apply_action(action)
            return
        action = manipulator.gripper.forward(action="open" if opened else "close")
        manipulator.apply_action(action)

    def setManipulatorArmJointPositions(self, sim, obj, joint_positions):
        from isaacsim.core.utils.types import ArticulationAction

        manipulator = self._manipulator(sim, obj)
        joints = np.asarray(joint_positions, dtype=float).reshape(-1)
        arm_dof_indices = self._coreDofIndices(
            manipulator, obj.manipulatorProfile.armDofNames
        )
        if len(joints) > len(arm_dof_indices):
            raise RuntimeError(
                f"Arm joint target has more than {len(arm_dof_indices)} positions"
            )
        targets = [None] * manipulator.num_dof
        for index, value in zip(arm_dof_indices, joints):
            targets[index] = value
        manipulator.apply_action(ArticulationAction(joint_positions=targets))

    def holdManipulatorPosition(self, sim, obj):
        from isaacsim.core.utils.types import ArticulationAction

        manipulator = self._manipulator(sim, obj)
        arm_dof_indices = self._coreDofIndices(
            manipulator, obj.manipulatorProfile.armDofNames
        )
        current = np.asarray(manipulator.get_joint_positions(), dtype=float)
        targets = [None] * manipulator.num_dof
        for index in arm_dof_indices:
            targets[index] = current[index]
        manipulator.apply_action(ArticulationAction(joint_positions=targets))

    def getManipulatorEndEffectorPose(self, sim, obj):
        profile = obj.manipulatorProfile
        manipulator = self._manipulator(sim, obj)
        state = self._motionPolicyState(sim, obj, manipulator, profile.rmpflowPolicyName)
        self._syncMotionPolicyBase(manipulator, state["rmp_flow"])
        active_joints = state["policy"].get_active_joints_subset().get_joint_positions()
        position, orientation = state["rmp_flow"].get_end_effector_pose(active_joints)
        position = _asArray(position).reshape(-1)[:3]
        orientation = _asArray(orientation)
        if orientation.shape == (3, 3):
            orientation = rotationToWxyz(Rotation.from_matrix(orientation))
        orientation = orientation.reshape(-1)[:4]
        if profile.rmpflowUsesTcpOffset:
            position = self._controlToTcpPosition(
                position, orientation, profile.tcpOffset
            )
        return position, orientation

    def getManipulatorGripperPositions(self, sim, obj):
        manipulator = self._manipulator(sim, obj)
        positions = np.asarray(manipulator.gripper.get_joint_positions(), dtype=float)
        return positions.reshape(-1)

    def _coreDofIndices(self, articulation, names):
        dof_names = list(articulation.dof_names)
        missing = [name for name in names if name not in dof_names]
        if missing:
            raise RuntimeError(f"{articulation.name} is missing required DOFs: {missing}")
        return [dof_names.index(name) for name in names]

    def _tcpToControlPosition(self, tcp_position, orientation, tcp_offset):
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        return positionArray(tcp_position) - self.rotateVectorByWxyzQuat(
            orientation, tcp_offset
        )

    def _controlToTcpPosition(self, control_position, orientation, tcp_offset):
        orientation = np.asarray(orientation, dtype=float).reshape(-1)[:4]
        control_position = np.asarray(control_position, dtype=float).reshape(-1)[:3]
        return control_position + self.rotateVectorByWxyzQuat(orientation, tcp_offset)

    def getPhysicsProperties(self, world, obj):
        isaac_obj = world.scene.get_object(obj.name)
        position, orientation = isaac_obj.get_world_pose()
        yaw, pitch, roll = self.isaacQuatToScenicEulerAngles(
            orientation, initial_rotation=obj.initialRotation
        )
        lx, ly, lz = isaac_obj.get_linear_velocity()
        ax, ay, az = isaac_obj.get_angular_velocity()
        return {
            "position": tuple(position),
            "velocity": (lx, ly, lz),
            "speed": math.hypot(lx, ly, lz),
            "angularSpeed": math.hypot(ax, ay, az),
            "angularVelocity": (ax, ay, az),
            "yaw": yaw,
            "pitch": pitch,
            "roll": roll,
        }
