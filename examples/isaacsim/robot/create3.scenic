import sys
sys.path.append(str(localPath("..")))

from lib import *
model scenic.simulators.isaac.model

# Create room region and set it as the workspace
room_region = RectangularRegion(0 @ 0, 0, 5.09, 5.09)
workspace = Workspace(room_region)

# Create floor and walls
floor = new Floor
wall_offset = floor.width/2 + 0.04/2 + 1e-4
right_wall = new Wall at (wall_offset, 0, 0.25), facing toward floor
left_wall = new Wall at (-wall_offset, 0, 0.25), facing toward floor
front_wall = new Wall at (0, wall_offset, 0.25), facing toward floor
back_wall = new Wall at (0, -wall_offset, 0.25), facing toward floor

# Place vacuum on floor
ego = new Create3 on floor, with behavior KeepMoving, with color (1, 0, 0)

# Create a "safe zone" around the vacuum so that it does not start stuck
safe_zone = CircularRegion(ego.position, radius=1)

# Create a dining room region where we will place dining room furniture
dining_room_region = RectangularRegion(1.25 @ 0, 0, 2.5, 5).difference(safe_zone)

# Place a table with 3 chairs around it
dining_table = new DiningTable contained in dining_room_region, on floor,
    facing Range(0, 360 deg)

chair_1 = new DiningChair behind dining_table by -0.1, on floor,
                facing toward dining_table, with regionContainedIn dining_room_region
chair_2 = new DiningChair ahead of dining_table by -0.1, on floor,
                facing toward dining_table, with regionContainedIn dining_room_region
chair_3 = new DiningChair left of dining_table by -0.1, on floor,
                facing toward dining_table, with regionContainedIn dining_room_region

# Create a living room region where we will place living room furniture
living_room_region = RectangularRegion(-1.25 @ 0, 0, 2.5, 5).difference(safe_zone)

couch = new Couch ahead of left_wall by 0.335,
            on floor, facing away from left_wall

coffee_table = new CoffeeTable ahead of couch by 0.336,
            on floor, facing away from couch

# Add some noise to the positions of the couch and coffee table
mutate couch, coffee_table

# Spawn some toys
for _ in range(globalParameters.numToys):
    new Toy on floor

## Simulation Setup ##
terminate after globalParameters.duration seconds
record (ego.x, ego.y) as VacuumPosition