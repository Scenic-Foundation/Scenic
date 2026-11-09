from gazebo_msgs.msg import ModelState
from gazebo_msgs.srv import (
    GetModelProperties,
    GetModelState,
    GetWorldProperties,
    SetModelState,
)
from geometry_msgs.msg import (
    Pose,
    PoseStamped,
    PoseWithCovarianceStamped,
    TransformStamped,
    Vector3,
)
from tf.transformations import euler_from_quaternion, quaternion_from_euler

# from geometry_msgs.msg import Quaternion
import rospy

# import tf_conversions
import numpy as np
import tf2_geometry_msgs
import tf2_ros


def GetObjectPose(obj, frame="map"):  # works
    """
    String obj: the name of the object
    String frame: the reference frame for the pose
    Returns: dictionary containing pose information
    """
    state = GetObjectGazeboState(obj, frame=frame)
    if state:
        pos = state.pose.position
        ori = state.pose.orientation
        ori = euler_from_quaternion([ori.x, ori.y, ori.z, ori.w])
        # return (pos.x, pos.y, pos.z, ori[-1])
        return dict(x=pos.x, y=pos.y, z=pos.z, roll=ori[0], pitch=ori[1], yaw=ori[-1])

    return None


def GetObjectState(obj, frame="map"):
    """
    Probably what you want to call to get an object's current states
    String obj: the name of the object
    String frame: the reference frame for the pose
    Returns: dictionary containing state information
    """
    try:
        state = GetObjectGazeboState(obj, frame)
        if state:
            pos = state.pose.position
            ori = state.pose.orientation
            ori = euler_from_quaternion([ori.x, ori.y, ori.z, ori.w])
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
        rospy.logerr("GetObjectState Fail go")
        raise e


def GetObjectGazeboState(obj, frame="map"):
    """
    String obj: the name of the object
    String frame: the reference frame for the pose
    Returns: gazebo_msgs.msg.ModelState
    """
    try:
        try:
            frame = settings.get_frame(frame)
        except:
            frame = frame

        rospy.wait_for_service("/gazebo/get_model_state")
        get_model_state = rospy.ServiceProxy("/gazebo/get_model_state", GetModelState)
        state = get_model_state(obj, frame)
        return state

    except Exception as e:
        rospy.logerr("GetObjectGazeboState Fail go")
        raise RuntimeError(
            f"Failed to get {obj.name} state; Gazebo\
                           get_model_state service failed with exception {e}"
        )



def SetModelPose(
    tgt_model, x=0.0, y=0.0, z=0.0, roll=0, pitch=0, yaw=0.0, frame="map"
):  # Good
    """
    Set the Model's Pose
    Args:
    String tgt_model: name of model
    float x: x position
    float y: y position
    float z: z position
    float Yaw: angle
    Returns: Typle(bool success, String status_message)
    """
    ref_frame_id = frame
    try:
        frame = settings.get_frame(frame)
    except:
        frame = ref_frame_id

    rospy.wait_for_service("/gazebo/get_model_state")
    get_model_state = rospy.ServiceProxy("/gazebo/get_model_state", GetModelState)
    model_state = get_model_state(tgt_model, "")

    quat = tf.transformations.quaternion_from_euler(roll, pitch, yaw)

    new_pose = Pose()
    new_pose.position.x = x
    new_pose.position.y = y
    new_pose.position.z = z
    new_pose.orientation.x = quat[0]
    new_pose.orientation.y = quat[1]
    new_pose.orientation.z = quat[2]
    new_pose.orientation.w = quat[3]

    new_model_state = ModelState()
    new_model_state.model_name = tgt_model
    new_model_state.pose = new_pose
    new_model_state.twist = geometry_msgs.Twist()
    new_model_state.reference_frame = frame

    rospy.wait_for_service("/gazebo/set_model_state")
    set_state = rospy.ServiceProxy("/gazebo/set_model_state", SetModelState)
    resp = set_state(new_model_state)
    return (resp.success, resp.status_message)


def ApplyROSTransform(transform, x=0, y=0, z=0, quat=(0, 0, 0, 1)):
    """
    transform: rospy.TransformStamped
    x, y, z: position
    quat: a quaternion (any indexable object is fine)
    returns
        Pose
    """
    pose_stamped = PoseStamped()
    pose = Pose()
    pose.position.x = x
    pose.position.y = y
    pose.position.z = z
    pose.orientation.x = quat[0]
    pose.orientation.y = quat[1]
    pose.orientation.z = quat[2]
    pose.orientation.w = quat[3]

    new_pose = tf2_geometry_msgs.do_transform_pose(pose, transform)
    return new_pose.pose


def ListenToTransform(source, target):
    """
    Get the ROS transform from the source frame to the target frame
    Args:
        source: String
            The source frame of reference
        target: Target
            The target frame of reference
    Returns:
        trans: rospy.TransformStamped
    """
    tfBuffer = tf2_ros.Buffer()
    listener = tf2_ros.TransformListener(tfBuffer)
    while not rospy.is_shutdown():
        try:
            trans = tfBuffer.lookup_transform(source, target, rospy.Time())
            break
        except:
            continue
    return trans
