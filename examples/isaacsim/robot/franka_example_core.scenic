"""Explicit end-effector pick-and-place with the Franka Panda.

Unlike ``franka.scenic`` (which runs the backend's built-in pick-place state
machine via ``PickPlaceObject``), this example lays out each task step directly
as a Scenic behavior sequence.

Run with:
    scenic -S -b examples/isaacsim/robot/franka_example_core.scenic
"""

param isaacBackend = "core_51"
param environmentUSDPath = "Isaac/Environments/Simple_Room/simple_room.usd"

duration = 60
cubeSize = 0.0515
binHeight = 0.1475
hoverHeight = 0.3
retractHeight = 0.2
releaseGap = 0.02

model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj
from scenic.simulators.isaac.actions import ManipulatorTimeout

table = getExistingObj("/Root/table_low_327/table_low")
# Mirror the whole task across the y axis: the cube spawns on either side
# of the robot, with the bin always on the opposite side.
taskSide = Uniform(-1, 1)
CUBE_POSITION = (Range(0.45, 0.55), taskSide * Range(0.25, 0.35))
BIN_POSITION = (Range(0.25, 0.35), -taskSide * Range(0.25, 0.35))

class IsaacBin(IsaacSimObject):
    length: 0.3
    width: 0.2
    height: binHeight
    physics: False
    shape: BoxShape()
    isaacAssetPath: "Isaac/Props/KLT_Bin/small_KLT.usd"

class PickCube(IsaacSimObject):
    width: cubeSize
    length: cubeSize
    height: cubeSize
    mass: 0.05
    color: (1, 0, 0)
    shape: BoxShape()

cube = new PickCube on table, at CUBE_POSITION

small_bin = new IsaacBin on table, at BIN_POSITION

place_pos = (small_bin.x, small_bin.y, cube.z)

def endEffectorTarget(pos):
    return pos

behavior FrankaMoveToPickPlace(targetObject, place_pos):
    pick_pos = (targetObject.x, targetObject.y, targetObject.z)
    home = endEffectorTarget((
        0.30,
        0.0,
        pick_pos[2] + hoverHeight,
    ))
    hover_pick = endEffectorTarget((
        pick_pos[0],
        pick_pos[1],
        pick_pos[2] + hoverHeight,
    ))
    at_pick = endEffectorTarget(pick_pos)

    release_pos = (
        place_pos[0],
        place_pos[1],
        place_pos[2] + releaseGap,
    )
    hover_place = endEffectorTarget((
        place_pos[0],
        place_pos[1],
        place_pos[2] + retractHeight,
    ))
    at_place = endEffectorTarget(release_pos)

    try:
        do MoveEndEffectorTo(home)
        do OpenGripper()
        do MoveEndEffectorTo(hover_pick)
        do MoveEndEffectorTo(at_pick, threshold=0.015)
        do HoldPosition()
        do CloseGripper()
        do MoveEndEffectorTo(hover_pick)
        do MoveEndEffectorTo(hover_place)
        do MoveEndEffectorTo(at_place)
        do OpenGripper()
        do MoveEndEffectorTo(hover_place)
        do MoveEndEffectorTo(home)
    except ManipulatorTimeout:
        print("Pick-place aborted", flush=True)
    terminate simulation

ego = new FrankaPanda on table, at (0, 0),
    with behavior FrankaMoveToPickPlace(
        cube,
        place_pos,
    )

print(f"CUBE POS: {cube.x}, {cube.y}, {cube.z}")
print(f"SMALL_BIN POS: {small_bin.x}, {small_bin.y}, {small_bin.z}")

require 0.42 <= distance from cube to ego <= 0.82
require 0.25 <= distance from small_bin to ego <= 0.82
require distance from cube to small_bin > 0.38

terminate after duration seconds
