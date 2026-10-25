"""
Introduction to Scenic Actions


This file, actions.py, is where you should define all
your Scenic Actions that are to be carried out with the 
'take <Action>' syntax. 

Each Action should be a class inheriting from
the Action class from scenic.core.simulators
"""

from scenic.core.simulators import * # imports the Action superclass


class ExampleAction1(Action):
    """
    Each Action has two methods you need to implement,
    __init__() and the applyTo(). We will see how to implement
    them below
    """

    def __init__(self):
        """
        __init__ can have any arguments beside based on the need of your actions

        For instance, you can have

        def __init__(self, x, y, z)

        as the funciton signature, and when taking the Action in your Scenic program,
        you would write:

        take ExampleAction1(x, y, z)

        You should not execute or send the command
        for the Action in __init__. That is the applyTo method's job.

        Other than that, there is no requirement as to what to do in __init__. You can
        fill in the code according to your needs
        """

        pass


    def applyTo(self, obj, sim):
        """
        Contrary to __init__(), applyTo()'s signature is fixed
        to applyTo(self, obj, sim). You should not change this.
        
        Args:
        Object obj: The Scenic object that takes the action
        scenic.core.simulator.Simulation sim: the Simulation instance you implemented in simulator.py

        applyTo is generally where you send the command to the simulator to execute an action

        You can choose to let it return anything or None based on your needs. However,
        remember that your implementation for the step() and executeAction() in simulator.py
        should account for this

        """
        pass



"""
Let's see an example Action
"""

class MoveAction(Action):
    """
    This Action sends to command to move the agent
    to an (x, y, z) coordinate
    """

    def __init__(self, x=0, y=0, z=0):
        self.target_coord = [x, y, z]

    def applyTo(self, obj, sim):

        agent_id = obj.agent_id

        target_reachable = sim.YourSimulatorAPI.target_reachable(self.target_coord)

        if target_reachable:
            YourSimulatorAPI.move_agent(agent_id=agent_id, target_coordinate=self.target_coord)



"""
Here's an example where applyTo returns a function that executes a command
"""

class MoveAction(Action):
    """
    This Action sends to command to move the agent
    to an (x, y, z) coordinate
    """

    def __init__(self, x=0, y=0, z=0):
        self.target_coord = [x, y, z]

    def applyTo(self, obj, sim):
        agent_id = obj.agent_id

        target_reachable = sim.YourSimulatorAPI.target_reachable(self.target_coord)

        if target_reachable:
            f = lambda: sim.YourSimulatorAPI.move_agent(agent_id=agent_id, target_coordinate=self.target_coord)

        return f



"""
An example for a BAD Action:
You should NOT have any code in Actions that blocks code execution

This prevents Scenic from simultaneously (at least approximately simulatenaously) manage 
all the agents, objects, and simulation world.
"""

class BadAction(Action):
    """
    This Action sends to command to move the agent
    to an (x, y, z) coordinate and waits for it to reach its goal
    """

    def __init__(self, x=0, y=0, z=0):
        self.target_coord = [x, y, z]

    def applyTo(self, obj, sim):
        """
        Here we send a command to move an agent and then wait until
        the agent reaches its goal using the final while loop.

        This will cause problems as Scenic is prevented from
        managing and sending the action commands for other agents.
        Scenic would also not be able to get information of the simulation world
        during the time when the agent is moving.
        

        This kind of blocking code can be common in robot API's, where 
        methods that commands the robot often conatins code that waits
        until the robot has finished executing its commands.

        We will see a way around this problem in behaviors.scenic
        """

        agent_id = obj.agent_id

        YourSimulatorAPI.move_agent(agent_id=agent_id, target_coordinate=self.target_coord)

        while not YourSimulatorAPI.agent_reached_goal(agent_id): # this code blocks Scenic's execution
            continue


