from lib import *
model scenic.simulators.isaac.model

param dropHeight = Range(5, 10)

# Create room region and set it as the workspace
room_region = RectangularRegion(0 @ 0, 0, 5.09, 5.09)
workspace = Workspace(room_region)

# Create floor and walls
floor = new Floor with color (0.1, 0.847, 0.1)
wall_offset = floor.width/2 + 0.04/2 + 1e-4
right_wall = new Wall at (wall_offset, 0, 0.25), facing toward floor
left_wall = new Wall at (-wall_offset, 0, 0.25), facing toward floor
front_wall = new Wall at (0, wall_offset, 0.25), facing toward floor
back_wall = new Wall at (0, -wall_offset, 0.25), facing toward floor

# Place dining room furniture above the ground so it falls under physics.
dining_table = new DiningTable at (1.25, 0, globalParameters.dropHeight),
    facing (Range(0, 360 deg), Range(0, 360 deg), Range(0, 360 deg)),
    with regionContainedIn None

chair_1 = new DiningChair at (1.25, -0.65, globalParameters.dropHeight),
    facing toward dining_table, with regionContainedIn None
chair_2 = new DiningChair at (1.25, 0.65, globalParameters.dropHeight),
    facing toward dining_table, with regionContainedIn None
chair_3 = new DiningChair at (0.6, 0, globalParameters.dropHeight),
    facing toward dining_table, with regionContainedIn None

# Place living room furniture above the ground so it falls under physics.
couch = new Couch at (-2, 0, globalParameters.dropHeight),
    facing (Range(0, 360 deg), Range(0, 360 deg), Range(0, 360 deg)),
    with regionContainedIn None

coffee_table = new CoffeeTable at (-1.25, 0, globalParameters.dropHeight),
    facing (Range(0, 360 deg), Range(0, 360 deg), Range(0, 360 deg)),
    with regionContainedIn None

# Add some noise to the positions of the couch and coffee table.
mutate couch, coffee_table

# Spawn some toys above the room.
for _ in range(globalParameters.numToys):
    new Toy at (Range(-2.3, 2.3), Range(-2.3, 2.3), globalParameters.dropHeight),
        with regionContainedIn None

## Simulation Setup ##
terminate after globalParameters.duration seconds
