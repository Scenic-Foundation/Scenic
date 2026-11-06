model scenic.simulators.isaac.model

import numpy as np
import trimesh
import random

param numToys = 10
param duration = 10

class Floor(GroundPlane):
    width: 5
    length: 5
    position: (0,0,-0.005)
    color: [0.785, 0.785, 0.785]

class Wall(IsaacSimObject):
    width: 5
    length: 0.04
    height: 0.5
    physics: False
    allowCollisions: True
    color: [0.627, 0.627, 0.627]

class DiningTable(IsaacSimObject):
    shape: MeshShape.fromFile(localPath("../../assets/meshes/dining_table.obj.bz2"))
    width: Range(0.7, 1.5)
    length: Range(0.7, 1.5)
    height: 0.75
    density: 670 # Density of solid birch
    color: [0.403, 0.278, 0.212]

class DiningChair(IsaacSimObject):
    shape: MeshShape.fromFile(localPath("../../assets/meshes/dining_chair.obj.bz2"), initial_rotation=(180 deg, 0, 0))
    width: 0.4
    length: 0.4
    height: 1
    density: 670 # Density of solid birch
    positionStdDev: (0.05, 0.05 ,0)
    orientationStdDev: (10 deg, 0, 0)
    color: [0.403, 0.278, 0.212]

class Couch(IsaacSimObject):
    shape: MeshShape.fromFile(localPath("../../assets/meshes/couch.obj.bz2"), initial_rotation=(-90 deg, 0, 0))
    width: 2
    length: 0.75
    height: 0.75
    positionStdDev: (0.05, 0.5 ,0)
    orientationStdDev: (5 deg, 0, 0)
    color: [0.2, 0.2, 1]

class CoffeeTable(IsaacSimObject):
    shape: MeshShape.fromFile(localPath("../../assets/meshes/coffee_table.obj.bz2"))
    width: 1.5
    length: 0.5
    height: 0.4
    positionStdDev: (0.05, 0.05 ,0)
    orientationStdDev: (5 deg, 0, 0)
    color: [0.404, 0.278, 0.212]

class Toy(IsaacSimObject):
    shape: Uniform(BoxShape(), CylinderShape(), ConeShape(), SpheroidShape())
    width: 0.1
    length: 0.1
    height: 0.1
    density: 100
    color: [1, 0.502, 0]

class BlockToy(Toy):
    shape: BoxShape()