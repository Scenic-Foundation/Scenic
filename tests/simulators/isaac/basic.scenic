# Representative Isaac Sim scenario: ground plane, a mesh object, a built-in
# wheeled robot, a robot with a custom articulation controller, and a
# manipulator composing the generic end-effector behaviors.
model scenic.simulators.isaac.model
from scenic.simulators.isaac.backends import articulationAction

param duration = 5

def wheelControl(command):
    throttle, steering = command
    return articulationAction(joint_velocities=[throttle - steering, throttle + steering],
                              joint_indices=[0, 1])

class CustomRobot(IsaacSimRobot):
    width: 0.2
    length: 0.2
    height: 0.1
    isaacAssetPath: "Isaac/Robots/NVIDIA/Jetbot/jetbot.usd"
    control: wheelControl

class Crate(IsaacSimObject):
    shape: BoxShape()
    width: 0.3
    length: 0.3
    height: 0.3
    density: 200
    color: (0.8, 0.2, 0.1)

behavior Drive():
    while True:
        take ApplyControllerAction([0.5, 0.1])

behavior PickAndLift(target):
    try:
        do OpenGripper()
        do MoveEndEffectorTo((target.x, target.y, target.z + 0.2))
        do MoveEndEffectorTo((target.x, target.y, target.z), threshold=0.015)
        do CloseGripper()
        do HoldPosition()
        do MoveEndEffectorTo((target.x, target.y, target.z + 0.3))
    except ManipulatorTimeout:
        pass
    terminate simulation

floor = new GroundPlane with width 6, with length 6
workspace = Workspace(RectangularRegion(0 @ 0, 0, 6, 6))

ego = new Create3 on floor, with behavior KeepMoving, with color (1, 0, 0)
robot = new CustomRobot on floor, with behavior Drive
crate = new Crate on floor
arm = new FrankaPanda on floor, with behavior PickAndLift(crate)

require distance from crate to arm < 0.8
require distance from ego to robot > 0.5

terminate after globalParameters.duration seconds
record (ego.x, ego.y) as EgoPosition
