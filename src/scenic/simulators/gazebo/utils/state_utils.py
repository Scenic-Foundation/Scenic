from simulation_interfaces.srv import GetEntityState
from scenic.simulators.gazebo.utils.quaternion_utils import euler_from_quaternion

import rclpy
import numpy as np

def GetObjectPose(obj, node, client, frame="map"):
    """
    String obj: the name of the object
    String frame: the reference frame for the pose
    Returns: dictionary containing pose information
    """
    state = GetObjectGazeboState(obj, node, client, frame=frame)
    if state:
        pos = state.pose.position
        ori = state.pose.orientation
        ori = euler_from_quaternion(ori.x, ori.y, ori.z, ori.w)
        return dict(x=pos.x, y=pos.y, z=pos.z, roll=ori[0], pitch=ori[1], yaw=ori[-1])

    return None


def GetObjectState(obj, node, client, frame="map"):
    """
    Probably what you want to call to get an object's current states
    String obj: the name of the object
    String frame: the reference frame for the pose
    Returns: dictionary containing state information
    """
    try:
        state = GetObjectGazeboState(obj, node, client, frame)
        if state:
            pos = state.pose.position
            ori = state.pose.orientation
            ori = euler_from_quaternion(ori.x, ori.y, ori.z, ori.w)
            linear = state.twist.linear
            angular = state.twist.angular
            state = dict(
                x=pos.x,
                y=pos.y,
                z=pos.z,
                roll=ori[0],
                pitch=ori[1],
                yaw=ori[-1],
                speed=np.linalg.norm(np.array([linear.x, linear.y, linear.z])),
                velocity=linear,
                angularSpeed=np.linalg.norm(np.array([angular.x, angular.y, angular.z])),
                angularVelocity=angular,
            )
        return state
    except Exception as e:
        node.get_logger().error("GetObjectState failed!")
        raise e


def GetObjectGazeboState(obj, node, client, frame="map"):
    """
    String obj: the name of the object
    String frame: the reference frame for the pose
    Returns: gazebo_msgs.msg.ModelState
    """
    request = GetEntityState.Request()
    request.entity = obj
    state = None
    for _ in range(20): # sometimes spins forever if you don't set a timeout and retry, not sure why but this is necessary
        # print(f'getting {obj} state, attempt {i}')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=1)
        if future.result():
            state = future.result().state
            break
    if state is None:
        node.get_logger().info("Error getting entity state!")
        raise RuntimeError('exception while calling service: %r' % future.exception())
    return state
