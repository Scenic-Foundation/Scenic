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
from scenic.simulators.Gazebo.utils.spawn_delete_model import DeleteObject, SpawnObject
from scenic.simulators.Gazebo.utils.start_gazebo import (
    CreateSimLaunchParent,
    PauseGazebo,
    ResetGazeboWorld,
    ResetGazeboWorldAndSim,
    UnpauseGazebo,
)
from scenic.simulators.Gazebo.utils.state_utils import ( 
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
        rospy.init_node("scenic", anonymous=True)
        self.client = dict()

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

        # TODO the following gazebo_<>_ground_truth are meant to be used in
        # coordinate transform functions. Specify them if needed
        self.gazebo_x_ground_truth = 0.0
        self.gazebo_y_ground_truth = 0.0
        self.gazebo_z_ground_truth = 0.0
        self.gazebo_to_robot_yaw_rot = 0.0
        self.gazebo_yaw_ground_truth = 0.0
        super().__init__(scene, timestep=timestep, **kwargs)

    def setup(self):
        # TODO set up the necessary variable, etc.
        # Note that super().setup() already calls
        # createObjectInSimulator
        super().setup()  # Calls createObjectInSimulator for each object
        return

    def createObjectInSimulator(self, obj):
        """
        Spawns the object in the Gazebo simulator.
        Args:
        obj: the scenic object, needs to have a name and position field

        Returns:
        bool success
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
            # TODO implement how you would like to spawn the robot
            raise NotImplementedError()
        return success

    def executeActions(self, allActions):
        """
        execute action for each object. Does not immediately render,
        but instead buffers the object
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
        Gets the state of the object at each timestep
        Not directly called by the user
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
        # TODO add in any special object destruction code as needed
        if self.render:
            PauseGazebo()  # Finally, pause Gazebo
            for obj in self.objects:  # Delte all objects spawned by scenic
                if (
                    obj.object_type != "robot"
                ):  # TODO robots are not deleted by default, change this as needed
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
        pose: (x, y, z, roll, pitch, yaw)
        """
        # TODO implement this coordinate transformation
        pass

    def RobotToGazeboMap(self, pose):
        """
        Converts from the Robot map frame to the gazebo map frame
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        """
        # TODO implement this coordinate transformation
        pass

    def ScenicToRobotMap(self, pose, obj=None):
        """
        Converts from the Scenic map coordinate to the Robot map frame
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        # TODO implement this coordinate transformation
        pass

    def RobotToScenicMap(self, pose, obj=None):
        """
        Converts from the Robot 'map' frame coordinate to the Scenic map coordinate
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        # TODO implement this coordinate transformation
        pass

    def ScenicToGazeboMap(self, pose, obj=None):
        """
        Converts from the Scenic map coordinate to the Gazebo map frame coordinate
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        # assert len(pose) == 4
        return self.RobotToGazeboMap(self.ScenicToRobotMap(pose, obj=obj))

    def GazeboToScenicMap(self, pose, obj=None):
        """
        Converts from the Gazebo map frame coordinate to the Scenic map coordinate
        Args:
        pose: (x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        # assert len(pose) == 4
        return self.RobotToScenicMap(self.GazeboToRobotMap(pose), obj=obj)
