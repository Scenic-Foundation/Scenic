import math
from scenic.simulators.Gazebo.simulator import GazeboSimulator, GazeboSimulation
from scenic.core.utils import repairMesh
import os

simulator GazeboSimulator()
object_prefix = '' # TODO fill in the prefix/suffixes to where you store your sdf/urdf files
default_file_name = "model.sdf"
get_sdf_dir = lambda s: object_prefix +  s + "/" + default_file_name

class Robot:
    """
    The default class for the robot agents. Can be used as a superclass
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
    """
    Superclass for non-agent objects
    """
    name: 'gazebo_object'
    object_type: 'gazebo_object'
    description_file: ''
    description_file_type: 'sdf'
    width: 1
    length: 1
    height: 1
    positionOffset:(0, 0, 0)
