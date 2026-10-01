"""
Generate a room for the i-roomba create vacuum
"""
model scenic.simulators.webots.model

import numpy as np
import trimesh
import random
from pathlib import Path

param numToys = 0
param duration = 10

## Class Definitions ##

class Vacuum(WebotsObject):
    webotsName: "IROBOT_CREATE"
    shape: CylinderShape()
    width: 0.335
    length: 0.335
    height: 0.07
    customData: str(random.getrandbits(32)) # Random seed for robot controller

# Floor uses builtin Webots floor to keep Vacuum Sensors from breaking
# Not actually linked to WebotsObject because Webots floor is 2D
class Floor(Object):
    width: 5
    length: 5
    height: 0.01
    position: (0,0,-0.005)

class Wall(WebotsObject):
    webotsAdhoc: {'physics': False}
    width: 5
    length: 0.04
    height: 0.5

class DiningTable(WebotsObject):
    webotsAdhoc: {'physics': True}
    shape: MeshShape.fromFile(globalParameters.meshBasePath / "dining_table.obj.bz2")
    width: Range(0.7, 1.5)
    length: Range(0.7, 1.5)
    height: 0.75
    density: 670 # Density of solid birch

class DiningChair(WebotsObject):
    webotsAdhoc: {'physics': True}
    shape: MeshShape.fromFile(globalParameters.meshBasePath / "dining_chair.obj.bz2", initial_rotation=(180 deg, 0, 0))
    width: 0.4
    length: 0.4
    height: 1
    density: 670 # Density of solid birch
    positionStdDev: (0.05, 0.05 ,0)
    orientationStdDev: (10 deg, 0, 0)

class Couch(WebotsObject):
    webotsAdhoc: {'physics': False}
    shape: MeshShape.fromFile(globalParameters.meshBasePath / "couch.obj.bz2", initial_rotation=(-90 deg, 0, 0))
    width: 2
    length: 0.75
    height: 0.75
    positionStdDev: (0.05, 0.5 ,0)
    orientationStdDev: (5 deg, 0, 0)

class CoffeeTable(WebotsObject):
    webotsAdhoc: {'physics': False}
    shape: MeshShape.fromFile(globalParameters.meshBasePath / "coffee_table.obj.bz2")
    width: 1.5
    length: 0.5
    height: 0.4
    positionStdDev: (0.05, 0.05 ,0)
    orientationStdDev: (5 deg, 0, 0)

class Toy(WebotsObject):
    webotsAdhoc: {'physics': True}
    shape: Uniform(BoxShape(), CylinderShape(), ConeShape(), SpheroidShape())
    width: 0.1
    length: 0.1
    height: 0.1
    density: 100

class BlockToy(Toy):
    shape: BoxShape()

## Scene Layout ##

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
ego = new Vacuum on floor

# Create a "safe zone" around the vacuum so that it does not start stuck
safe_zone = CircularRegion(ego.position, radius=1)

# Create a dining room region where we will place dining room furniture
dining_room_region = RectangularRegion(1.25 @ 0, 0, 2.5, 5).difference(safe_zone)

# Place a table with 3 chairs around it, and one knocked over on the floor
dining_table = new DiningTable contained in dining_room_region, on floor,
    facing Range(0, 360 deg)

chair_1 = new DiningChair behind dining_table by -0.1, on floor,
                facing toward dining_table, with regionContainedIn dining_room_region
chair_2 = new DiningChair ahead of dining_table by -0.1, on floor,
                facing toward dining_table, with regionContainedIn dining_room_region
chair_3 = new DiningChair left of dining_table by -0.1, on floor,
                facing toward dining_table, with regionContainedIn dining_room_region

fallen_orientation = Uniform((0, -90 deg, 0), (0, 90 deg, 0), (0, 0, -90 deg), (0, 0, 90 deg))

chair_4 = new DiningChair contained in dining_room_region, facing fallen_orientation,
                on floor, with baseOffset(0,0,-0.2)

# Add some noise to the positions and yaw of the chairs around the table
mutate chair_1, chair_2, chair_3

# Create a living room region where we will place living room furniture
living_room_region = RectangularRegion(-1.25 @ 0, 0, 2.5, 5).difference(safe_zone)

couch = new Couch ahead of left_wall by 0.335,
            on floor, facing away from left_wall

coffee_table = new CoffeeTable ahead of couch by 0.336,
            on floor, facing away from couch

# Add some noise to the positions of the couch and coffee table
mutate couch, coffee_table

toy_stack = new BlockToy on floor
toy_stack = new BlockToy on toy_stack
toy_stack = new BlockToy on toy_stack

# Spawn some toys
for _ in range(globalParameters.numToys):
    new Toy on floor

## Simulation Setup ##
terminate after globalParameters.duration * 60 seconds
record (ego.x, ego.y) as VacuumPosition
