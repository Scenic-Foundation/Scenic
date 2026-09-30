"""Experimental side pick-and-place with the UR5e and Robotiq 2F-85.

Run with:
    scenic -S -b examples/isaacsim/robot/ur5e_example_experimental_side.scenic
"""

param isaacBackend = "experimental_51"
param environmentUSDPath = "Isaac/Environments/Simple_Room/simple_room.usd"

duration = 60
cubeSize = 0.0515
sideStandoff = cubeSize * 1.55
sideGraspZBias = 0.0
sideGraspOffset = cubeSize * 0.4
hoverHeight = cubeSize * 6
retractHeight = cubeSize * 4
releaseGap = cubeSize
placeRegionSize = cubeSize * 2.3
placeOffsetX = -0.135
placeOffsetY = 0.788
armMaxVelocities = (2.175, 2.175, 2.175, 2.175, 2.61, 2.61)

model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj
from scenic.simulators.isaac.actions import ManipulatorTimeout

table = getExistingObj("/Root/table_low_327/table_low")

cubeSpawnPosition = Range(0.455, 0.515) @ Range(-0.52, -0.455)
PICK_APPROACH_AXIS = (0.0, -1.0, 0.0)
SIDE_PICK_ORIENTATION = (0.70710678, 0.70710678, 0.0, 0.0)

class PickCube(IsaacSimObject):
    width: cubeSize
    length: cubeSize
    height: cubeSize
    mass: 0.05
    color: (1, 0, 0)
    shape: BoxShape()

cube = new PickCube on table, at cubeSpawnPosition

placeRegionCenter = (cube.x + placeOffsetX) @ (cube.y + placeOffsetY)
placeRegion = RectangularRegion(placeRegionCenter, 0, placeRegionSize, placeRegionSize)
sampled_place_point = new Point in placeRegion
place_pos = (sampled_place_point.x, sampled_place_point.y, cube.z)

def sideTarget(center, clearance=0.0):
    return (
        center[0] - PICK_APPROACH_AXIS[0] * clearance,
        center[1] - PICK_APPROACH_AXIS[1] * clearance,
        center[2] - PICK_APPROACH_AXIS[2] * clearance,
    )

behavior UR5eSidePickPlace(targetObject, place_pos):
    pick_center = (
        targetObject.x,
        targetObject.y,
        targetObject.z + sideGraspZBias,
    )
    release_center = (
        place_pos[0],
        place_pos[1],
        place_pos[2] + releaseGap,
    )
    transfer_height = max(pick_center[2], release_center[2]) + retractHeight

    home = sideTarget((
        self.x + (pick_center[0] - self.x) * 0.6,
        self.y + (pick_center[1] - self.y) * 0.6,
        transfer_height,
    ))
    pre_pick_high = sideTarget((
        pick_center[0],
        pick_center[1],
        pick_center[2] + hoverHeight,
    ), clearance=sideStandoff)
    pre_pick_side = sideTarget(pick_center, clearance=sideStandoff)
    at_pick = sideTarget(pick_center, clearance=sideGraspOffset)

    carry_pick = sideTarget((
        pick_center[0],
        pick_center[1],
        transfer_height,
    ))
    carry_transfer = (
        (pick_center[0] + release_center[0]) / 2,
        (pick_center[1] + release_center[1]) / 2,
        transfer_height,
    )
    above_place = (
        release_center[0],
        release_center[1],
        transfer_height,
    )
    at_place = release_center
    post_place_high = (
        release_center[0],
        release_center[1],
        release_center[2] + retractHeight,
    )

    try:
        do MoveEndEffectorTo(home, orientation=SIDE_PICK_ORIENTATION)
        do OpenGripper()
        do MoveEndEffectorTo(pre_pick_high, orientation=SIDE_PICK_ORIENTATION)
        do MoveEndEffectorTo(pre_pick_side, orientation=SIDE_PICK_ORIENTATION)
        do MoveEndEffectorTo(at_pick, orientation=SIDE_PICK_ORIENTATION, threshold=0.015)
        do HoldPosition()
        do CloseGripper()
        do HoldPosition()
        do MoveEndEffectorTo(carry_pick, orientation=SIDE_PICK_ORIENTATION)
        do MoveEndEffectorTo(carry_transfer, orientation=SIDE_PICK_ORIENTATION)
        do MoveEndEffectorTo(above_place, orientation=SIDE_PICK_ORIENTATION)
        do MoveEndEffectorTo(at_place, orientation=SIDE_PICK_ORIENTATION)
        do OpenGripper()
        do HoldPosition()
        do MoveEndEffectorTo(post_place_high, orientation=SIDE_PICK_ORIENTATION)
        do MoveEndEffectorTo(home, orientation=SIDE_PICK_ORIENTATION)
    except ManipulatorTimeout:
        print("Pick-place aborted", flush=True)
    terminate simulation

ego = new UR5e on table, at (0, 0),
    with armMaxVelocities armMaxVelocities,
    with behavior UR5eSidePickPlace(
        cube,
        place_pos,
    )

print(f"CUBE POS: {cube.x}, {cube.y}, {cube.z}")
print(f"PLACE POS: {place_pos[0]}, {place_pos[1]}, {place_pos[2]}")

require 0.42 <= distance from cube to ego <= 0.82
require 0.25 <= distance from sampled_place_point to ego <= 0.82
require distance from cube to sampled_place_point > 0.38

terminate after duration seconds
