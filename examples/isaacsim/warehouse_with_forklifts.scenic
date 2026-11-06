param environmentUSDPath = "Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd"

model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj

floor_piece = getExistingObj("/Root/SM_floor58/SM_floor02")

new Create3 on floor_piece, with color (1, 0, 0), with behavior KeepMoving