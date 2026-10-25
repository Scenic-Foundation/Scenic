"""
Introduction to Models

In this file, you will define all the Scenic
classes that will represent your object and agent models

"""


"""
By default, all classes inherit the Scenic Object class
See the Scenic docs for more details

You can add any attribute/methods you need to a Scenic class.
"""

class Agent:
    """
    Instance variables are assigned with the colon
    like in Python dataclasses, whereas class variables
    are assigned with '='
    """
    name: "agent"
    agent_controller: None
    class_name = 'agent'

    """
    You can add distributions to instance and class attributes
    For class attributes, the value will be the same for all
    instances of the class within the same scene.
    """
    position: (Range(0, 1), Range(0, 10), Range(1, 2))
    robot_language = Uniform('English', 'Japanese', 'Hungarian')


    """
    You can add in methods just like in Python classes
    """
    def distanceToClosest(self, object_class):
        objects = simulation().objects
        minDist = float('inf')
        for obj in objects:
            if not isinstance(obj, object_class):
                continue
            d = distance from self to obj
            if 0 < d < minDist:
                minDist = d
        return minDist
    
    """
    Decorators such as property, getter, and setter etc. work as well
    """
    @property
    def PositionNorm(self):
        return self.position.norm()

"""
Inheritance works the same way as in Python
"""
class Robot(Agent):
    name: "robot"
    agent_controller: YourRobotAPI.robot_controller
    class_name = "robot"


"""
Mixin's are also supported
"""
class RobotArm(Robot):
    name: "robot_arm"
    agent_controller: YourRobotAPI.robot_controller
    class_name = "robot_arm"

    @property
    def gripper_position(self):
        return YourRobotAPI.gripper_pos()


class RobotMobileBase(Robot):
    name: "robot_base"
    agent_controller: YourRobotAPI.robot_controller
    class_name = "robot_base"

    @property
    def base_position(self):
        return YourRobotAPI.base_pos()

class MobileManipulator(RobotArm, RobotMobileBase):
    name: "mobile_manipulator"
    agent_controller: YourRobotAPI.robot_controller
    class_name = "mobile_manipulator"

