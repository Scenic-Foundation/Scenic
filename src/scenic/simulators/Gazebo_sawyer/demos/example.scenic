model scenic.simulators.Gazebo_sawyer.model
from scenic.simulators.Gazebo_sawyer.model import *
from scenic.simulators.Gazebo_sawyer.behaviors import *
from scenic.simulators.Gazebo_sawyer.actions import *
import math
import time

behavior PickAndPlaceBehavior(target):
    do MoveToNeutral()
    do WaitForTimeROS(0.5)

    take OpenGripperAction()
    do WaitForTimeROS(1.0)

    x = target.position[0]
    y = target.position[1]
    z = target.position[2]

    do MoveEndEffector(x=x, y=y, z=z+0.5, roll=math.pi, pitch=0, yaw=math.pi)
    do WaitForTimeROS(1.0)
    
    do MoveEndEffector(x=x, y=y, z=z+0.15, roll=math.pi, pitch=0, yaw=math.pi)
    do WaitForTimeROS(1.0)
    
    take CloseGripperAction()
    do WaitForTimeROS(1.0)

    do MoveEndEffector(x=x, y=y, z=z+0.5, roll=math.pi, pitch=0, yaw=math.pi)
    do WaitForTimeROS(1.0)

    do MoveEndEffector(x=0.75, y=0, z=z+0.15, roll=math.pi, pitch=0, yaw=math.pi)
    do WaitForTimeROS(1.0)

    take OpenGripperAction()
    do WaitForTimeROS(1.0)

    do MoveEndEffector(x=0.75, y=0, z=z+0.5, roll=math.pi, pitch=0, yaw=math.pi)
    do WaitForTimeROS(1.0)

    do MoveToNeutral()
    do WaitForTimeROS(3.0)
    terminate

table = new CafeTable on (0.75, 0, 0)
cube = new WoodCube5cm on table
ego = new Robot at (0,0,0.93), with name 'sawyer', with behavior PickAndPlaceBehavior(cube)


require distance from cube to ego < 1.2
