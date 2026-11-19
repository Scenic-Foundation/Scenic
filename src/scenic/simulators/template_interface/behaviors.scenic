"""
Introduction to Behaviors

Behaviors allow us to specify at a high level how
an agents should act. It can be made up of other behaviors
or Actions. While the Scenic documentation introduces you to
the basics of beahivors, we re going to see here some more specific
examples of using behaviors when you write your own Scenic interface.
"""


"""
Example 1: Using behaviors to get around
having Action code that blocks background 
Scenic execution (mentioned in actions.py)
"""

behavior MoveToPosition(x, y, z):
    """
    If you are in the robotics domain, chances are you have
    code in your robot API that looks like this:
    
    def move_to_position(self, x, y, z):
        self.set_robot_goal_point(x, y, z)

        while <robot has not reached goal>:
            continue

    As mentioned in actions.py, since the while loop above
    blocks the backgournd Scenic code execution, we cannot have it
    in a Scenic Action. However, we can get around it with the code
    below:
    """

    take SetRobotGoalPointAction(x, y, z) # This Action calls set_robot_goal_point, but does not have the while loop

    while <robot has not reached goal>: # This while loop waits until the robot reaches its goal point
        wait

    """
    Recall that the Scenic 'wait' tells Scenic that the agent is not taking 
    any actions for this timestep. Seeing this, Scenic will move on to manage
    other agents and objects while your robot marches its way to the goal.
    So when you write your Scenic programs, rather than simply taking the
    Action that tells the robot to move to a goal point, you would just
    call this behavior instead.

    You can also put the while loop above in its own behavior and call that 
    for all your robot's Actions like shown below:
    """
    take SetRobotGoalPointAction(x, y, z) # This Action calls set_robot_goal_point
    do WaitUntilFinishBehavior()



