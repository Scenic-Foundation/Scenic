import math
from scenic.simulators.Gazebo_sawyer.simulator import GazeboSimulator, GazeboSimulation
from scenic.core.utils import repairMesh
import os

# Convention:
# for new objects: let the width  be the dimension along the gazebo y direcition,
# the length the direction along the gazebo x axis,
# the height the direction along the z axis.

# Positions are the 'map' frame NOT according to gazebo but to the robot
# Will be converted backstage for other purposes

simulator GazeboSimulator()
# TODO fill int he prefix/suffixes to where you store your sdf/urdf files
object_prefix = '<Your prefix>' + '/gazebo_models/' # TODO put here where you cloned gazebo_models
default_file_name = "model.sdf"
get_sdf_dir = lambda s: object_prefix +  s + "/" + default_file_name

class Robot:
    """
    center_offset: the vector, pointing from the center of the object to the 
    internal ref frame used by Gazebo to place the object
    """
    name: 'robot'
    object_type: 'robot'
    domain_name: ''
    position: (0.0, 0.0, 0.93)    
    yaw:-math.pi/2
    roll: 0.0
    pitch: 0.0
    yaw_offset: 0.0
    shape: CylinderShape(dimensions=(0.43,0.43, 1.8))
    positionOffset: (0, 0, -0.5) # vectorpointing from center of object to its ref frame
    
    holdingObject: False


    def distanceToClosest(self, object_class):
        objects = simulation().objects
        minDist = float('inf')
        for obj in objects:
            if not isinstance(obj, object_class):
                continue
            d = distance from self to obj
            if 0 < d < minDist:
                minDist = d
        return minDist

    def getClosest(self, object_class):
        objects = simulation().objects
        minDist = float('inf')
        tgt = None
        for obj in objects:
            if not isinstance(obj, object_class):
                continue
            d = distance from self to obj
            if 0 < d < minDist:
                minDist = d
                tgt = obj
        return tgt


class GazeboObject:
    name: 'gazebo_object'
    object_type: 'gazebo_object'
    description_file: ''
    description_file_type: 'sdf'
    width: 1
    length: 1
    height: 1
    positionOffset:(0, 0, 0)

class CafeTable(GazeboObject):
    name: 'cafe_table'
    description_file: get_sdf_dir('cafe_table')
    description_file_type: 'sdf'
    width: 0.913
    length: 0.913
    height: 0.8
    positionOffset:(0, 0, -0.4)

class WoodCube10cm(GazeboObject):
    name: 'wood_cube_10'
    description_file: get_sdf_dir('wood_cube_10cm')
    description_file_type: 'sdf'
    width: 0.1
    length: 0.1
    height: 0.1

class WoodCube5cm(GazeboObject):
    name: 'wood_cube_5'
    description_file: get_sdf_dir('wood_cube_5cm')
    description_file_type: 'sdf'
    width: 0.05
    length: 0.05
    height: 0.05
