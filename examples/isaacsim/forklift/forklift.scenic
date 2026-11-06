param environmentUSDPath = "Isaac/Environments/Simple_Warehouse/warehouse.usd"
param duration = 60

model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj
from common import *

floor_piece = getExistingObj("/Root/SM_floor58/SM_floor02")
shelf = getExistingObj("/Root/SM_RackShelf_159/SM_RackShelf_01/Section1")
pallet = getExistingObj("/Root/SM_PaletteA_12/SM_PaletteA_01")

approach_heading = Range(0, 180 deg)

load = new PalletLoad on floor_piece, behind pallet by 4,
    facing approach_heading

ego = new AckermannForkliftB behind load by Range(2, 3),
    facing approach_heading,
    with behavior AckermannForkliftPickup(load, shelf)

terminate after globalParameters.duration seconds
