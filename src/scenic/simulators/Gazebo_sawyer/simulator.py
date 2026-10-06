"""Simulator interface for Gazebo."""
import logging
import math
import os
import traceback
import warnings

import actionlib
from gazebo_msgs.srv import DeleteModel
from geometry_msgs.msg import Point, PoseStamped, Quaternion, Twist
import numpy as np
import roslaunch
import rospy
from tf.transformations import euler_from_quaternion

import scenic.core.errors as errors
from scenic.core.simulators import Simulation, SimulationCreationError, Simulator
from scenic.core.vectors import Vector
from scenic.domains.driving.simulators import DrivingSimulation, DrivingSimulator
from scenic.simulators.Gazebo_sawyer.utils.spawn_delete_model import (
    DeleteObject,
    SpawnObject,
)
from scenic.simulators.Gazebo_sawyer.utils.start_gazebo import (
    CreateSimLaunchParent,
    PauseGazebo,
    ResetGazeboWorld,
    ResetGazeboWorldAndSim,
    UnpauseGazebo,
)
from scenic.simulators.Gazebo_sawyer.utils.state_utils import ( 
    GetObjectPose,
    GetObjectState,
    SetModelPose,
)

if errors.verbosityLevel == 0:  # suppress pygame advertisement at zero verbosity
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

from scenic.core.simulators import SimulationCreationError
from scenic.syntax.veneer import verbosePrint

# TODO: Import Robot-specific library
import intera_interface


class GazeboSimCreationError(SimulationCreationError):
    """
    If anything went wrong in setting up the scene, this error is thrown.
    If Scenic is run using the CLI, The current scene terminates, and a new scene is started
    Args:
    String msg: the message to be given
    """

    def __init__(self, msg):
        self.msg = msg
        super().__init__(self.msg)


class GazeboSimRuntimeError(SimulationCreationError):
    """
    If anything went wrong in running the scene, this error is thrown.
    If Scenic is run using the CLI, The current scene terminates, and a new scene is started
    Args:
    String msg: the message to be given
    Exception exc: the exception thrown by other parts of the code that makes us stop scene
    """

    def __init__(self, msg, exc):
        self.msg = exc.args[0]
        self.file_name, self.lineno = exc.filename, exc.lineno
        super().__init__(self.msg)
        self.with_traceback(exc.__traceback__)


class GazeboSimulator(Simulator):
    """Implementation of `Simulator`."""

    def __init__(
        self,
        map_path="",
        timeout=10,
        render=True,
        record="",
        timestep=0.1,
    ):
        super().__init__()
        verbosePrint(f"Connecting to Gazebo simulator")
        self.timestep = timestep
        self.render = (
            render  # visualization mode ON/OFF, for future use with fast physics
        )
        self.record = record
        self.scenario_number = 0

        # TODO Decide the form of your client
        rospy.init_node("scenic_sawyer", anonymous=True)
        self.client = dict(
            arm=intera_interface.Limb(),
            gripper=intera_interface.Gripper(),
            head=intera_interface.Head(),
            head_display=intera_interface.HeadDisplay(),
            cameras=intera_interface.Cameras(),
            cuff=intera_interface.Cuff(),
            lights=intera_interface.Lights(),
            navigator=intera_interface.Navigator(),
        )

    def createSimulation(self, scene, timestep, **kwargs):
        if timestep is not None and timestep != self.timestep:
            raise RuntimeError(
                "cannot customize timestep for individual Gazebo simulations; "
                "set timestep when creating the GazeboSimulator instead"
            )
        self.scenario_number += 1
        return GazeboSimulation(
            scene,
            self.client,
            self.render,
            self.record,
            timestep=self.timestep,
            **kwargs,
        )

    def destroy(self):
        # TODO add code to be run when Scenic runs terminates, if needed
        super().destroy()


class GazeboSimulation(Simulation):
    """
    Simulation class for Gazebo-Scenic
    gazebo_<xyz>_ground_truth: the offset FROM the Gazebo frame TO the robot frame
    gazebo_yaw_ground_truth: true offset FROM the Gazebo frame TO the robot frame
    """

    def __init__(self, scene, client, render, record, timestep=0.1, **kwargs):
        self.client = client
        self.render = True
        self.record = record
        self.timestep = timestep
        self.step_actions = []
        self.collision_objects = dict()
        self.gazebo_x_ground_truth = 0.0
        self.gazebo_y_ground_truth = 0.0
        self.gazebo_z_ground_truth = 0.0
        self.gazebo_to_robot_yaw_rot = 0.0
        self.gazebo_yaw_ground_truth = 0.0

        self.current_target_joint = dict()
        super().__init__(scene, timestep=timestep, **kwargs)

    def setup(self):
        # TODO set up the necessary variable, etc.
        # Note that super().setup() already calls
        # createObjectInSimulator()
        self.arm = self.client["arm"]
        self.gripper = self.client["gripper"]
        self.head = self.client["head"]
        self.head_display = self.client["head_display"]
        self.cameras = self.client["cameras"]
        self.cuff = self.client["cuff"]
        self.lights = self.client["lights"]
        self.navigator = self.client["navigator"]
        super().setup()  # Calls createObjectInSimulator for each object and does other setup things
        return

    def createObjectInSimulator(self, obj):
        """
        Spawns the object in the Gazebo simulator.
        Args:
        obj: the scenic object, needs to have a name and position field

        Returns:
        Tuple(bool success, status_message)
        """

        print(f"Object name: {obj.name}\nObject position: {obj.position}")
        position = obj.position
        position = (position[0], position[1], position[2], obj.roll, obj.pitch, obj.yaw)

        position = self.ScenicToGazeboMap(position, obj=obj)
        x, y, z, roll, pitch, yaw = position
        success = False
        if obj.object_type != "robot":
            print(f"spawning: {obj.name}")
            print(x, y, z, yaw)
            success = SpawnObject(
                obj.name,
                object_xml=obj.description_file,
                x=x,
                y=y,
                z=z,
                roll=roll,
                pitch=pitch,
                yaw=yaw,
                file_type=obj.description_file_type,
            )
            rospy.sleep(0.1)

        else:
            self.arm.move_to_neutral()
            success = True
        return success

    def executeActions(self, allActions):
        """
        execute action for each object. Does not immediately render,
        but instead buffers the actions
        """
        for agent, actions in allActions.items():
            for action in actions:
                try:
                    a = action.applyTo(agent, self)
                    self.step_actions.append(a)
                except Exception as e:
                    print(f"Failed to execute action, exception:\n{str(e)}")
                    logging.error(traceback.format_exc())
        return

    def step(self):
        """
        This function takes the actions in the action buffer and executes all of them
        in simulation. The simulator will unpause and run for a single timestep and
        pause again.
        """
        # TODO: if you implemented your actions' applyTo to return anything
        # other than a function taking no arguments, change this piece of code
        # such that the action is properly executed
        UnpauseGazebo()
        t0 = rospy.get_rostime()

        for a in self.step_actions:
            try:
                a()
            except Exception as e:
                print(
                    f"Failed to execute action, proceed to next action, exception\n{str(e)}"
                )
                logging.error(traceback.format_exc())
        self.step_actions = []

        t1 = rospy.get_rostime()
        time_elapsed = t1 - t0
        while time_elapsed.to_sec() < self.timestep:
            t1 = rospy.get_rostime()
            time_elapsed = t1 - t0

        PauseGazebo()
        return

    def getProperties(self, obj, properties):
        """
        Gets the state of each object and agent
        """
        try:
            obj_gazebo_state = GetObjectState(obj.name)
            pose = (
                obj_gazebo_state["x"],
                obj_gazebo_state["y"],
                obj_gazebo_state["z"],
                obj_gazebo_state["roll"],
                obj_gazebo_state["pitch"],
                obj_gazebo_state["yaw"],
            )

            pose = self.GazeboToScenicMap(pose, obj=obj)
            v = obj_gazebo_state["velocity"]
            w = obj_gazebo_state["angularVelocity"]
            d = dict(
                position=Vector(pose[0], pose[1], pose[2]),
                yaw=pose[-1],
                pitch=pose[4],
                roll=pose[3],
                speed=obj_gazebo_state["speed"],
                velocity=Vector(v.x, v.y, v.z),
                angularSpeed=obj_gazebo_state["angularSpeed"],
                angularVelocity=Vector(w.x, w.y, w.z),
            )
            return d

        except Exception as e:
            raise RobotSimRuntimeError(
                f"Failed to get {obj.name} states. An exception occured: {e}", e
            )

    def destroy(self):
        """
        Deletes the objects spawned by Scenic and resets the Gazebo world
        Note that the Gazebo simulation is not reset, since doing so resets the ROS
        time and messes up the simulation.
        By default, any robot that is spawned is not deleted
        """
        if self.render:
            PauseGazebo()
            for obj in self.objects:  # Delte all objects spawned by scenic
                if obj.object_type != "robot":
                    success, status_message = DeleteObject(obj.name, sim=self)
                    print(f"Deleted Model: {success}\nStatus Message:{status_message}")
            ResetGazeboWorld()
            UnpauseGazebo()
            rospy.sleep(3.0)
        super().destroy()
        return

    def GazeboToRobotMap(self, pose):
        """
        Converts from the gazebo map frame to the Robot map frame
        Args:
        pose = Tuple(x, y, z, roll, pitch, yaw)
        """
        x_offset = self.gazebo_x_ground_truth
        y_offset = self.gazebo_y_ground_truth
        z_offset = self.gazebo_z_ground_truth
        yaw_offset = self.gazebo_yaw_ground_truth
        yaw_rotation = self.gazebo_to_robot_yaw_rot

        g = np.array(
            [
                [np.cos(yaw_offset), -np.sin(yaw_offset), x_offset],
                [np.sin(yaw_offset), np.cos(yaw_offset), y_offset],
                [0, 0, 1],
            ]
        )
        g = np.linalg.inv(g)

        x, y, _ = g @ np.array(list(pose[:2]) + [1])
        z = pose[2] - z_offset
        yaw = pose[-1] - yaw_offset

        return (x, y, z, pose[3], pose[4], yaw)

    def RobotToGazeboMap(self, pose):
        """
        Converts from the Robot map frame to the gazebo map frame
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        """
        x_offset = self.gazebo_x_ground_truth
        y_offset = self.gazebo_y_ground_truth
        z_offset = self.gazebo_z_ground_truth
        yaw_offset = self.gazebo_yaw_ground_truth
        g = np.array(
            [
                [np.cos(yaw_offset), -np.sin(yaw_offset), x_offset],
                [np.sin(yaw_offset), np.cos(yaw_offset), y_offset],
                [0, 0, 1],
            ]
        )
        x, y, _ = g @ np.array(list(pose[:2]) + [1])

        z = pose[2] + z_offset
        yaw = pose[-1] + yaw_offset

        return (x, y, z, pose[3], pose[4], yaw)

    def ScenicToRobotMap(self, pose, obj=None):
        """
        Converts from the Scenic map coordinate to the Robot map frame
        Args:
        pose: (x, y, z, yaw)
        """
        x, y, z, roll, pitch, yaw = pose
        if obj and hasattr(obj, "positionOffset"):
            dx, dy, dz = (
                obj.positionOffset[0],
                obj.positionOffset[1],
                obj.positionOffset[2],
            )
            x = x + dx
            y = y + dy
            z = z + dz

        return (x, y, z, roll, pitch, yaw + math.pi / 2)

    def RobotToScenicMap(self, pose, obj=None):
        """
        Converts from the Robot 'map' frame coordinate to the Scenic map coordinate
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        obj: the Scenic object
        """
        x, y, z, roll, pitch, yaw = pose

        if obj and hasattr(obj, "positionOffset"):
            dx, dy, dz = (
                obj.positionOffset[0],
                obj.positionOffset[1],
                obj.positionOffset[2],
            )
            x = x - dx
            y = y - dy
            z = z - dz
        return (x, y, z, roll, pitch, yaw - math.pi / 2)

    def ScenicToGazeboMap(self, pose, obj=None):
        """
        Converts from the Scenic map coordinate to the Gazebo map frame coordinate
        Args:
        pose = Tuple(x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        # assert len(pose) == 4
        return self.RobotToGazeboMap(self.ScenicToRobotMap(pose, obj=obj))

    def GazeboToScenicMap(self, pose, obj=None):
        """
        Converts from the Gazebo map frame coordinate to the Scenic map coordinate
        Args:
        pose = Tuple(x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        # assert len(pose) == 4
        return self.RobotToScenicMap(self.GazeboToRobotMap(pose), obj=obj)
