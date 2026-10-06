import math
import sys

import actionlib
from actionlib_msgs.msg import GoalStatus
import controller_manager_msgs.srv
from geometry_msgs.msg import (
    Point,
    Pose,
    PoseStamped,
    Quaternion,
    TransformStamped,
    Twist,
)
import numpy as np
import rospy
import tf2_ros

# import tf.transformations as T
from tf.transformations import euler_from_quaternion, quaternion_from_euler
import trajectory_msgs.msg
from visualization_msgs.msg import Marker, MarkerArray

from scenic.core.simulators import *
from scenic.simulators.Gazebo.utils.state_utils import ApplyROSTransform

"""
READ:
This is the library of all Actions. For each any actions you would like to perform,
check if a corresponding behavior exists in behavior.scenic. It is recommended to use
the behaviors since those take care of waiting for controllers and waiting until finish

If you would like to add a new Action, make sure the applyTo() function returns a function
that takes no arguments
"""
