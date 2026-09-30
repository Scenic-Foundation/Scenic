param isaacBackend = "core_51"
param environmentUSDPath = "Isaac/Environments/Simple_Room/simple_room.usd"
param duration = 30
param cubeSize = 0.0515
param binHeight = 0.1475
param dropHeight = 0.2

model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj

table = getExistingObj("/Root/table_low_327/table_low")

class IsaacBin(IsaacSimObject):
    length: 0.3
    width: 0.2
    height: globalParameters.binHeight
    physics: False
    shape: BoxShape()
    isaacAssetPath: "Isaac/Props/KLT_Bin/small_KLT.usd"

class PickCube(IsaacSimObject):
    width: globalParameters.cubeSize
    length: globalParameters.cubeSize
    height: globalParameters.cubeSize
    mass: 0.05
    color: (1, 0, 0)
    shape: BoxShape()

cube = new PickCube on table

small_bin = new IsaacBin on table,
    facing toward cube

ego = new FrankaPanda on table, at (0, 0),
    facing toward cube,
    with behavior PickPlaceObject(
        cube,
        Vector(small_bin.x, small_bin.y, small_bin.z + globalParameters.dropHeight),
    )

require 0.42 <= distance from cube to ego <= 0.82
require 0.25 <= distance from small_bin to ego <= 0.82
require distance from cube to small_bin > 0.38

terminate after globalParameters.duration seconds
