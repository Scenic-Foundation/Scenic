"""Simulator interface for Gazebo."""
import logging
import math
import traceback

from simulation_interfaces.srv import (
    SpawnEntity, 
    DeleteEntity, 
    SetSimulationState, 
    GetEntityState, 
    SetEntityState, 
    ResetSimulation, 
    StepSimulation
)
import numpy as np
import rclpy

from scenic.core.simulators import Simulation, SimulationCreationError, Simulator
from scenic.core.vectors import Vector
from scenic.simulators.gazebo.utils.spawn_delete_model import DeleteObject, SpawnObject
from scenic.simulators.gazebo.utils.start_gazebo import (
    PauseGazebo,
    ResetGazeboWorld,
    UnpauseGazebo,
    TakeStep
)
from scenic.simulators.gazebo.utils.state_utils import ( 
    GetObjectState,
)

from scenic.core.simulators import SimulationCreationError
from scenic.syntax.veneer import verbosePrint

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
        record="",
        timestep=0.1,
    ):  
        super().__init__()
        verbosePrint(f"Connecting to Gazebo simulator")
        self.timestep = timestep
        self.record = record
        self.scenario_number = 0

        rclpy.init()

        # create rclpy node and clients to interact with gazebo services
        self.scenicNode = rclpy.create_node("scenic")
        self.spawnClient = self.scenicNode.create_client(SpawnEntity, "/gzserver/spawn_entity")
        self.deleteClient = self.scenicNode.create_client(DeleteEntity, "/gzserver/delete_entity")
        self.controlClient = self.scenicNode.create_client(SetSimulationState, "/gzserver/set_simulation_state")
        self.resetClient = self.scenicNode.create_client(ResetSimulation, "/gzserver/reset_simulation")
        self.observeClient = self.scenicNode.create_client(GetEntityState, "/gzserver/get_entity_state")
        self.stepClient = self.scenicNode.create_client(StepSimulation, '/gzserver/step_simulation')
        self.poseClient = self.scenicNode.create_client(SetEntityState, "/gzserver/set_entity_state")


    def createSimulation(self, scene, timestep, **kwargs):
        if timestep is not None and timestep != self.timestep:
            raise RuntimeError(
                "cannot customize timestep for individual Gazebo simulations; "
                "set timestep when creating the GazeboSimulator instead"
            )
        
        self.scenario_number += 1
        return GazeboSimulation(
            scene,
            self.scenicNode,
            self.spawnClient,
            self.deleteClient,
            self.controlClient,
            self.resetClient,
            self.observeClient,
            self.stepClient,
            self.poseClient,
            self.record,
            timestep=self.timestep,
            **kwargs,
        )

    def destroy(self):
        self.scenicNode.destroy_node()
        rclpy.shutdown()
        super().destroy()


class GazeboSimulation(Simulation):
    """
    Simulation class for Gazebo-Scenic
    gazebo_<xyz>_ground_truth: the offset FROM the Gazebo frame TO the robot frame
    gazebo_yaw_ground_truth: true offset FROM the Gazebo frame TO the robot frame
    """

    def __init__(self, scene, scenicNode, spawnClient, deleteClient, controlClient, resetClient, observeClient, stepClient, poseClient, record, timestep=0.1, **kwargs):
        self.scenicNode = scenicNode
        self.spawnClient = spawnClient
        self.deleteClient = deleteClient
        self.controlClient = controlClient
        self.resetClient = resetClient
        self.observeClient = observeClient
        self.stepClient = stepClient
        self.poseClient = poseClient
        
        self.record = record
        self.timestep = timestep
        self.step_actions = []
        self.navigation_status = None

        self.transforms_available = True
        self.numSteps = 0

        # TODO the following gazebo_<>_ground_truth are meant to be used in
        # coordinate transform functions. Specify them if needed
        self.gazebo_x_ground_truth = 0.0
        self.gazebo_y_ground_truth = 0.0
        self.gazebo_z_ground_truth = 0.0
        self.gazebo_to_robot_yaw_rot = 0.0
        self.gazebo_yaw_ground_truth = 0.0
        
        super().__init__(scene, timestep=timestep, **kwargs)

    def setup(self):
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
        if obj.object_type == "robot":
            return True
        elif obj.object_type == "sdf_object":
            pass
        elif obj.object_type == "goal_object":
            pass
        else:
            print(f"spawning: {obj.name}")
            print(x, y, z, roll, yaw, pitch)
            success = SpawnObject(
                obj.name,
                object_xml=obj.description_file,
                node=self.scenicNode,
                client=self.spawnClient,
                x=x,
                y=y,
                z=z,
                roll=roll,
                pitch=pitch,
                yaw=yaw,
                file_type=obj.description_file_type,
            )
        return success

    def step(self):
        """
        This function takes the actions in the action buffer and executes all of them
        in simulation. The simulator will unpause and run for a single timestep and
        pause again.
        """
        # TODO: if you implemented your actions' applyTo to return anything
        # other than a function taking no arguments, change this piece of code
        # such that the action is properly executed
        
        # stepping forward breaks stuff, using pause/unpause is more reliable
        # TakeStep(self.scenicNode, self.stepClient)
        
        UnpauseGazebo(self.scenicNode, self.controlClient)
        t0 = self.scenicNode.get_clock().now()

        for a in self.step_actions:
            try:
                a()
            except Exception as e:
                print(
                    f"Failed to execute action, proceed to next action, exception\n{str(e)}"
                )
                logging.error(traceback.format_exc())
        self.step_actions = []

        t1 = self.scenicNode.get_clock().now()
        time_elapsed = t1 - t0
        while time_elapsed.to_msg().sec < self.timestep:
            t1 = self.scenicNode.get_clock().now()
            time_elapsed = t1 - t0
        PauseGazebo(self.scenicNode, self.controlClient)
        self.numSteps += 1
        return

    def getProperties(self, obj, properties):
        """
        Gets the state of the object at each timestep
        Not directly called by the user
        """
        try:
            obj_gazebo_state = GetObjectState(obj.name, node=self.scenicNode, client=self.observeClient)
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
            raise RuntimeError(
                f"Failed to get {obj.name} states. An exception occured: {e}", e
            )

    def destroy(self):
        PauseGazebo(self.scenicNode, self.controlClient)  # Finally, pause Gazebo
        for obj in self.objects:  # Delete all objects spawned by scenic
            if (
                obj.object_type != "robot" and obj.object_type != "sdf_object"
            ):
                success = DeleteObject(obj.name, client=self.deleteClient, node=self.scenicNode, sim=self)
                print(f"Deleted Model: {success}")

        ResetGazeboWorld(self.scenicNode, self.resetClient)
        super().destroy()
        return
        
    # NOTE: You may need to modify these to your own use case if needed.
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
        return self.RobotToGazeboMap(self.ScenicToRobotMap(pose, obj=obj))

    def GazeboToScenicMap(self, pose, obj=None):
        """
        Converts from the Gazebo map frame coordinate to the Scenic map coordinate
        Args:
        pose = Tuple(x, y, z, roll, pitch, yaw)
        obj: the scenic object
        """
        return self.RobotToScenicMap(self.GazeboToRobotMap(pose), obj=obj)
