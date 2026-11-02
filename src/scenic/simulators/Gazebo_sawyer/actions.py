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
from scenic.simulators.Gazebo_sawyer.utils.state_utils import ApplyROSTransform

"""
READ:
This is the library of all Actions. For each any actions you would like to perform,
check if a corresponding behavior exists in behavior.scenic. It is recommended to use
the behaviors since those take care of waiting for controllers and waiting until finish

If you would like to add a new Action, make sure the applyTo() function returns a function
that takes no arguments
"""
GRIPPER_MAX_POSITION = 0.04167
GRIPPER_MIN_POSITION = 0.0
GRIPPER_MAX_VELOCITY = 3.0
GRIPPER_MIN_VELOCITY = 0.15
JOINT_ANGLE_TOLERANCE = 0.008726646


class SawyerAction(Action):
    """
    Super class for all Sawyer actions
    """

    def applyTo(self, obj, sim):
        pass

    def move_to_joint_positions(
        self, positions, sim, timeout=15.0, threshold=JOINT_ANGLE_TOLERANCE, test=None
    ):
        """
        moves the arm to the spcified joint position
        Args:
            positions: dict
                The dictionary with joint name as keys and joint angle as values
            timeout: float
                Timeout for the action
            threshold:
                Threshold angle for the joints
            test:
                test function to test for end of action
        """
        cmd = sim.arm.joint_angles()

        def genf(joint, angle):
            def joint_diff():
                return abs(angle - sim.arm._joint_angle[joint])

            return joint_diff

        diffs = [
            genf(j, a) for j, a in list(positions.items()) if j in sim.arm._joint_angle
        ]
        fail_msg = "{0} limb failed to reach commanded joint positions.".format(
            sim.arm.name.capitalize()
        )

        def test_collision():
            if sim.arm.has_collided():
                rospy.logerr(" ".join(["Collision detected.", fail_msg]))
                return True
            return False

        sim.arm.set_joint_positions(positions)


class MoveEndEffectorAction(SawyerAction):
    """
    Moves the end effector to the specified position and orientation
    Args:
        x/y/z: float
            the x/y/z coordinate to move the end effector to
        roll/pitch/yaw: float
            the roll/pitch/yaw angle to set the gripper
        timeout: float
            the timeout time for the action
        frame: String
            the frame in which the coordinates are specified
    """

    def __init__(self, x, y, z, roll, pitch, yaw, timeout=15.0, frame="scenic"):
        self.pose = Pose()
        self.pose.position.x = x
        self.pose.position.y = y
        self.pose.position.z = z
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        quat = quaternion_from_euler(roll, pitch, yaw)
        self.pose.orientation.x = quat[0]
        self.pose.orientation.y = quat[1]
        self.pose.orientation.z = quat[2]
        self.pose.orientation.w = quat[3]
        self.timeout = timeout
        self.frame = frame

    def applyTo(self, obj, sim):
        arm = sim.arm
        if self.frame == "scenic":
            self.pose.position.z -= 0.93
        elif self.frame != "base":
            tfBuffer = tf2_ros.Buffer()
            listener = tf2_ros.TransformListener(tfBuffer)

            while (
                not rospy.is_shutdown()
            ):  # TODO implement some kind of time out for this?
                try:
                    trans = tfBuffer.lookup_transform("base", self.frame, rospy.Time())
                    break
                except:
                    continue
            quat = quaternion_from_euler(roll, pitch, yaw)
            self.pose = ApplyROSTransform(trans, x, y, z, quat)
        joint_angles = arm.ik_request(self.pose)
        if joint_angles:
            sim.current_target_joint = joint_angles
            return lambda: self.move_to_joint_positions(
                joint_angles, sim, timeout=self.timeout
            )
        else:
            print("IK Failed")
            raise Exception("IK failed")


class MoveToNeutralAction(SawyerAction):
    """
    Moves the sawyer arm to neutral positions
    Args:
        timeout: float
            the timeout for the action
        speed: float
            the joint position speed to set
    """

    def __init__(self, timeout=15.0, speed=0.3):
        self.timeout = timeout
        self.speed = speed

    def applyTo(self, obj, sim):
        try:
            neutral_pose = rospy.get_param(
                "named_poses/{0}/poses/neutral".format(sim.arm.name)
            )
        except KeyError:
            rospy.logerr(('Get neutral pose failed, arm: "{0}".').format(sim.arm.name))
            return
        angles = dict(list(zip(sim.arm.joint_names(), neutral_pose)))
        sim.arm.set_joint_position_speed(self.speed)
        return lambda: self.move_to_joint_positions(angles, sim, timeout=self.timeout)


class OpenGripperAction(Action):
    """
    Opens the gripper to a certain position
    Args:
        position: float
            the position to which to open the gripper
    """

    def __init__(self, position=GRIPPER_MAX_POSITION):
        self.position = position

    def applyTo(self, obj, sim):
        return lambda: sim.gripper.open(position=self.position)


class CloseGripperAction(Action):
    """
    Close the gripper to a certain position
    Args:
        position: float
            the position to which to close the gripper
    """

    def __init__(self, position=GRIPPER_MIN_POSITION):
        self.position = position

    def applyTo(self, obj, sim):
        return lambda: sim.gripper.close(position=self.position)


class TuckAction(SawyerAction):
    """
    Moves the robot arm to a "tuck" position, with its cameras facing downward
    """

    def __init__(self):
        joints = [
            "right_j0",
            "right_j1",
            "right_j2",
            "right_j3",
            "right_j4",
            "right_j5",
            "right_j6",
        ]
        tuck_positions = [
            -0.0001416015625,
            -1.0003623046875,
            -0.0005185546875,
            1.499224609375,
            -0.000107421875,
            -0.50001171875,
            1.698958984375,
        ]

        tuck_dict = dict()
        for j, p in zip(joints, tuck_positions):
            tuck_dict[j] = p
        self.tuck_dict = tuck_dict

    def applyTo(self, obj, sim):
        return lambda: self.move_to_joint_positions(self.tuck_dict, sim)
