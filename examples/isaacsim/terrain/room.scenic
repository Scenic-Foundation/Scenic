model scenic.simulators.isaac.model

import sys
sys.path.append(str(localPath("..")))

from lib import *
param uniform_noise_range = (Range(0.1, 0.2), Range(0.2, 0.5))

terrain = new RandomUniformTerrain at (0, 0, 0), 
                with width 20, 
                with length 20, 
                with noiseRange globalParameters.uniform_noise_range

sofa = new Couch on terrain

coffee_table = new CoffeeTable on terrain, ahead of sofa by Range(0.5, 1.5)

wall = new Wall on terrain, behind sofa by Range(0.1, 0.2)

dining_room_region = RectangularRegion(1.25 @ 0, 0, 2.5, 5)

dining_table = new DiningTable contained in dining_room_region, on terrain,
    facing Range(0, 360 deg)

chair_1 = new DiningChair behind dining_table by -0.1, on terrain,
                facing toward dining_table, with regionContainedIn dining_room_region
chair_2 = new DiningChair ahead of dining_table by -0.1, on terrain,
                facing toward dining_table, with regionContainedIn dining_room_region
chair_3 = new DiningChair left of dining_table by -0.1, on terrain,
                facing toward dining_table, with regionContainedIn dining_room_region

# Spawn some toys
for _ in range(20):
    new Toy on terrain