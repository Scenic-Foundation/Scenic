import actionlib
import rospy
import time
import numpy as np
from scenic.simulators.Gazebo_sawyer.actions import *

def test_collision():
    if simulation().arm.has_collided():
        rospy.logerr(' '.join(["Collision detected.", fail_msg]))
        return True
    return False

def genf(joint, angle):
    def joint_diff():
        return abs(angle - simulation().arm._joint_angle[joint])
    return joint_diff


behavior WaitForTime(wait_time):
    """
    Wait for time in terms of real time
    """
    t0 = time.time()
    t1 = t0
    while t1 - t0 < wait_time:
        wait
        t1 = time.time()
    
behavior WaitForTimeROS(wait_time):
    """
    Wait for time in terms of ros time
    """
    t0 = rospy.get_rostime()
    t1 = rospy.get_rostime()
    while (t1.secs + t1.nsecs/(10**9) - t0.secs - t0.nsecs/(10**9)) < wait_time:
        wait
        t1 = rospy.get_rostime()

behavior SawyerWaitFor(test, timeout=10.0, raise_on_error=True, rate=100,
             timeout_msg="timeout expired", body=None):
    """
    Wait for sawyer to finish its current action
    """
    end_time = rospy.get_time() + timeout
    # rate = rospy.Rate(rate)
    notimeout = (timeout < 0.0) or timeout == float("inf")
    while not test():
        if rospy.is_shutdown():
            if raise_on_error:
                raise OSError(errno.ESHUTDOWN, "ROS Shutdown")
            return False
        elif (not notimeout) and (rospy.get_time() >= end_time):
            if raise_on_error:
                raise OSError(errno.ETIMEDOUT, timeout_msg)
            return False
        wait
    return True


behavior MoveEndEffector(x, y, z, roll, pitch, yaw, timeout=15.0, frame='scenic'):
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
    take MoveEndEffectorAction(x, y, z, roll, pitch, yaw, timeout=timeout, frame=frame)
    threshold = 0.008726646 
    positions = simulation().current_target_joint
    diffs = [genf(j, a) for j, a in list(positions.items()) if j in simulation().arm._joint_angle]
    test = lambda: test_collision()  or (all(diff() < threshold for diff in diffs))
    do SawyerWaitFor(test=test, timeout=timeout, rate=100, raise_on_error=False, body=lambda:simulation().arm.set_joint_positions)

behavior MoveToNeutral(timeout=15.0):
    """
    Moves the sawyer arm to neutral positions
    Args:
        timeout: float
            the timeout for the action
        speed: float
            the joint position speed to set
    """
    take MoveToNeutralAction()
    threshold = 0.008726646 
    positions = simulation().current_target_joint
    diffs = [genf(j, a) for j, a in list(positions.items()) if j in simulation().arm._joint_angle]
    test = lambda: test_collision() or (all(diff() < threshold for diff in diffs))
    do SawyerWaitFor(test=test, timeout=timeout, rate=100, raise_on_error=False, body=lambda:simulation().arm.set_joint_positions)
    
