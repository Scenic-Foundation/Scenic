"""Simulator interface"""

"""
Introduction to Simulator Interface

This file illustrates the basics on how to 
implement the Simultor and Simulation class for your
Scenic interface. The docstrings in each function
and class gives a brief description on what you should
write in each function and gives examples where needed.

"""
import logging
import math
import os
import traceback
import warnings

import scenic.core.errors as errors
from scenic.core.simulators import Simulation, SimulationCreationError, Simulator
from scenic.core.vectors import Vector
from scenic.core.simulators import SimulationCreationError
from scenic.syntax.veneer import verbosePrint


class TemplateSimulator(Simulator):
    """
    Implementation of `Simulator` in scenic.core.simulator.
    At each simulation, Simulator creates a Simulation class
    The Simulation class then runs the actual simulation.

    The core methods that need to be implemented/modified in this class are:

        __init__
        createSimulation
        destroy

    See their respective docstrings for details and how to fill them out.


    The rough execution flow in the background for a n-iteration Scenic run is:

        while number_of_simulations <= n:
            simulation = self.createSimulation()
            run_simulation(simulation)
            number_of_simulations += 1

        self.destory()

    see the Scenic docs and scenic.core.simulator for more details.
    """

    def __init__(self):
        """
        You can put anything you want in __init__ here, as long as super().__init__() is called.
        Keyword arguments can be added to the signature to set up some desired field, such as the
        size of the simulation timestep
        
        Example 1:
            def __init__(self, timestep=0):
                self.timestep = timestep
                super().__init__()

        Example 2:
            def __init__(self):
                YourSimulatorAPI.turn_on_simulator()
                super().__init__()
        """

        super().__init__()


    def createSimulation(self, scene, **kwargs):
        """
        Creates the Simulation class that will run 1 simulation.
        Depending on your needs and your implementation of the Simulation class,
        you can pass in different arguments.

        Note that you always need to pass in the 'scene' 
        variable for instatiating the Simulation class

        Example:
            def createSimulation(self, scene, **kwargs)
                return TemplateSimulation(scene, self.timestep, self.simulator_client, **kwargs)
        """
        return TemplateSimulation(scene, **kwargs)

    def destroy(self):
        """
        There is no required code here other than super().destory()
        You can add code does post-processing of the simulation output
        or code that turns of the simulator here

        Example 1:
            def destroy(self):
                YourSimulatorAPI.turn_off_simulator()
                super().destory()

        Example 2:
            def destroy(self):
                YourSimulatorAPI.save_simulation_recordings()
                super().destory()
        """

        super().destroy()


class TemplateSimulation(Simulation):

    """
    Implemation of the Simulation class in scenic.core.simulator

    This class is responsible for:
        1. Running the simulation
        2. Creating the simulation world according to the Scenic program
        3. Passing on Scenic's commands to control the agents to the simulator
        4. Obtaining the world state information from the simulator and passing
            it back to Scenic

    Core Methods to implement/modify:
        1. __init__
        2. setup
        3. createObjectInSimulator
        4. executeActions
        5. step
        6. getProperties
        7. destory

    See their respective docstrings for details and how to fill them out.
    NOTE: createObjectInSimulator() is already called for you for each object in super().setup()

    The rough execution flow when running a simulation is as follows:

        self.setup() # calls createObjectInSimulator inside

        while simulation is running:
            self.executeActions()
            self.step()
            self.getProperties()

        self.destroy()

    See the Simulation class in scenic.core.simulator for more details
    """

    def __init__(self, scene, **kwargs):
        """
        There is no specific requirement for code here
        other than calling super().__init__()
        You can instantiate here any variables that would be useful.

        Args
        Object scene: the object representing the scene to simulate.
        This argument has to be present.


        Example:
            def __init__(self, scene, timestep, client_ip):
                self.sim_connection = YourSimulatorAPI.connect_simulator(client_ip)
                YourSimulatorAPI.set_timestep_size(timestep)

                super().__init__()
        """
        super().__init__(scene, **kwargs)

    def setup(self):
        """
        The only requirement here is that you call super().setup(),
        which will call createObjectInSimulator() on each Scenic object for you roughly like this:

            for obj in scene.objects:
                self.createObjectInSimulator(obj)

        You can use setup() as another place to create some useful variables
        or call some useful functions

        Example:
            def setup(self):
                self.robot_arm_controller = RobotSimulatorAPI.get_arm_controller()
                self.robot_leg_controller = RobotSimulatorAPI.get_leg_controller()
                super().setup()
                return
        """

        super().setup()  # Calls createObjectInSimulator for each object
        return

    def createObjectInSimulator(self, obj):
        """
        Arg
        Object obj: a Scenic obj/agent

        Spawns a single object/agent in the simulator
        with the desired parameters (position, orientation, color, etc.)

        Example:
            Note that when you fail to spawn an object, you should
            raise a SimulationCreationError

            def createObjectInSimulator(self, obj):
                if <obj is a Car>:
                    try:
                        YourSimulatorAPI.spawn_car(
                                        position = obj.position,
                                        orientation = obj.yaw,
                                        color = obj.color,
                                        model = obj.modelx
                        )

                    except:
                        raise SimulationCreationError("spawn objec failed")
                else:
                    try:
                        YourSimulatorAPI.spawn_object(
                                        position = obj.position 
                                        orientation = obj.yaw
                        )
                    except:
                        raise SimulationCreationError("spawn objec failed")
        """
        pass

    def executeActions(self, allActions):
        """
        Args:
        allActions: a :obj:`~collections.defaultdict` mapping each agent to a tuple
                        of actions, with the default value being an empty tuple. The order of
                        agents in the dict should be respected in case the order of actions matters.

        Iterates through all the Scenic Actions to be carried out for all the agents.
        For each Scenic Action, this function calls the applyTo() method of the Action's class
        as defined in actions.py.

        Note that typically, when calling applyTo(), we do not actually render the physics of the action.
        That is, the action command is sent, but the world remains frozen.
        The action only gets carried out when we call step(), where the world unfreezes and
        the simulation physics is advanced by one timestep.

        Example 1:
            This is the implementation if you call super().executeActions(allActions)

            for agent, actions in allActions.items():
                for action in actions:
                    action.applyTo(agent, self)
            return


        Example 2:
            You can implement your Action.applyTo() to return something.
            The following is an example where the applyTo() returns a function that,
            when called in step(), execute the Action and renders it in simulation
            
            self.step_action_buffer = []

            for agent, actions in allActions.items():
                for action in actions:
                    a = action.applyTo(agent, self)

            self.step_action_buffer.append(a)

            return

            Where we will iterate through the step_action_buffer in step()
            and call each function like this:

            def step(self):
                for a in self.step_action_buffer:
                    a()
        """
        for agent, actions in allActions.items():
            for action in actions:
                action.applyTo(agent, self)
        return

    def step(self):
        """
        This function unfreezes the simulation world and 
        advances the physics by 1 timestep.
        When this function is called, all the Scenic Actions will be executed and
        rendered in simulation.


        Example 1:
            def step(self):
                YourSimulatorAPI.step_physics(self.timestep)

        """
        pass

    def getProperties(self, obj, properties):
        """
        Args:
        obj (Object): Scenic object in question.
        properties (set): Set of names of properties to read from the simulator.
        It is safe to destructively iterate through the set if you want.

        Returns:
        values (dict): A dictionary that with the property names as keys
        that returns the current value of the property

        Obtains the current values for each Scenic agent/object's properties
        such as current position, orientation, speed, etc. 

        There are certain properties that you have to obtain for all objects.
        The 'values' dictionary in Example 1 below contains these core properties.
        If any of these core properties does not apply to you or does not matter,
        feel free to always set them to 0 (like with pitch and roll values in Example 1)


        Example 1:

            def getProperties(self, obj, properties)
                position = YourSimulatorAPI.get_position(obj.id)
                yaw = YourSimulatorAPI.get_orientation(obj.id)
                velocity = YourSimulatorAPI.get_velocity(obj.id)
                etc etc ...

                values = dict(
                    position=position,
                    yaw=yaw,
                    pitch=0,
                    roll=0,
                    velocity=velocity,
                    speed=speed,
                    angularSpeed=angularSpeed,
                    angularVelocity=angularVelocity,
                )

        Example 2 (from the Newtonian simulator interface):
            
            You can also update properties unique to each object class 
            like how we update the 'elevation' property below

            def getProperties(self, obj, properties):
                yaw, _, _ = obj.parentOrientation.globalToLocalAngles(obj.heading, 0, 0)
                values = dict(
                    position=obj.position,
                    yaw=yaw,
                    pitch=0,
                    roll=0,
                    velocity=obj.velocity,
                    speed=obj.speed,
                    angularSpeed=obj.angularSpeed,
                    angularVelocity=obj.angularVelocity,
                )

                if "elevation" in properties:
                    values["elevation"] = obj.elevation
                return values


        Example 3:

            You can also update non-core properties without using the values dictionary,
            like what we do with the obj.camera_observation below
            
             
            position = YourSimulatorAPI.get_position(obj.id)
            yaw = YourSimulatorAPI.get_orientation(obj.id)
            velocity = YourSimulatorAPI.get_velocity(obj.id)
            etc etc ...

            def getProperties(self, obj, properties):
                values = dict(
                    position=position,
                    yaw=yaw,
                    pitch=0,
                    roll=0,
                    velocity=obj.velocity,
                    speed=obj.speed,
                    angularSpeed=obj.angularSpeed,
                    angularVelocity=obj.angularVelocity,
                )

                camera_observation = YourSimulatorAPI.get_camera_observation(obj.id)

                obj.camear_observation.append(camera_observation)

                return values
        """

    def destroy(self):
        """
        You should delete/destroy/unspawn objects created by Scenic here when needed.
        Data processing at the end of simulation can also be done here.
        Scenic 3.0.0, super().destroy() does nothing and can be overridden


        Example 1:
        You can always use the self.objects field, inherited from the 
        Simulation class from scenic.core.simulator, to access the objects/agents
        spawned by Scenic

            def destroy(self):
                for obj in self.objects:
                    if obj is Robot:
                        YourSimulatorAPI.shut_down_robot(obj.robot_id)
                        YourSimulatorAPI.delete_robot(obj.robot_id)
                    else:
                        YourSimulatorAPI.delete_object(obj.object_id)

                # Making videos of the simulation, assuming self.observations
                # contains the observations we have made throughout the simulation

                video_save_path = your/video/save/path/
                YourSimulatorAPI.make_video(self.observations, path=video_save_path + "video_1.mp4")
                return
        """
        pass

