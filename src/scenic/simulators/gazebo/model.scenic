import math
from scenic.simulators.gazebo.simulator import GazeboSimulator, GazeboSimulation
import os

simulator GazeboSimulator()
object_prefix = '/mnt/l/scenic/src/scenic/simulators/gazebo/'# placeholder, put the path to the folder storing the Gazebo models you want to spawn
default_file_name = "model.sdf"
get_sdf_dir = lambda s: object_prefix + s + "/" + default_file_name

class Robot:
    name: 'robot'
    object_type: 'robot'

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

class SDFObject:
    """
    Used for SDF parsing to make Scenic aware of predefined objects in the world
    """
    name: 'sdf_object'
    object_type: 'sdf_object'
    description_file: ''
    description_file_type: 'sdf'
