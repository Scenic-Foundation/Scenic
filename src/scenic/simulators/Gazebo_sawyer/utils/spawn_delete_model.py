# Code adapted from the spawn_model script from gazebo_ros

import os
import xml

from gazebo_msgs.msg import ModelStates
from gazebo_msgs.srv import DeleteModel
from gazebo_ros import gazebo_interface
from geometry_msgs.msg import Pose, Quaternion

import rospy
from tf.transformations import quaternion_from_euler

import scenic


def DeleteObject(name, sim=None):
    """
    deletes the object from Gazebo and collision world
    Args:
    String name: the name of the object
    """
    rospy.wait_for_service("/gazebo/delete_model")
    try:
        delete_model = rospy.ServiceProxy("/gazebo/delete_model", DeleteModel)
        resp = delete_model(name)
        if sim:
            if name in sim.collision_objects:
                sim.collision_world.remove(sim.collision_objects[name])
        return (resp.success, resp.status_message)
    except Exception as e:
        rospy.logerr("DeleteObject Fail Go")
        raise RuntimeError(f"Failed to delete object {name}")


def SpawnObject(
    name,
    object_xml,
    x=0,
    y=0,
    z=0,
    roll=0,
    pitch=0,
    yaw=0,
    file_type="sdf",
    ref_frame="map",  # TODO, FIX DOCUMENTATION AND RETURN VALS
):

    rospy.loginfo(f"Loading model XML from file")
    model_xml = object_xml

    if not os.path.exists(model_xml):
        rospy.logfatal("Error: specified file %s does not exist", model_xml)
        return False
    if not os.path.isfile(model_xml):
        rospy.logfatal("Error: specified file %s is not a file", model_xml)
        return False

    try:
        f = open(model_xml, "r")
        model_xml = f.read()

    except IOError as e:
        rospy.logerr(f"Error reading file {model_xml}: {e}")
        return False
    if model_xml == "":
        rospy.logerr(f"Error: file {model_xml} is empty")
        return False

    try:
        xml_parsed = xml.etree.ElementTree.fromstring(model_xml)
    except xml.etree.ElementTree.ParseError as e:
        rospy.logerr(f"Invalid XML: {e}")
        return False

    model_xml = xml.etree.ElementTree.tostring(xml_parsed)

    if not isinstance(model_xml, str):
        model_xml = model_xml.decode(encoding="ascii")

    initial_pose = Pose()
    initial_pose.position.x = x
    initial_pose.position.y = y
    initial_pose.position.z = z
    q = quaternion_from_euler(roll, pitch, yaw)
    initial_pose.orientation = Quaternion(*q)

    if file_type == "urdf":
        success = gazebo_interface.spawn_urdf_model_client(
            name,
            model_xml,
            rospy.get_namespace(),
            initial_pose,
            ref_frame,
            "/gazebo",
        )

    elif file_type == "sdf":
        success = gazebo_interface.spawn_sdf_model_client(
            name,
            model_xml,
            rospy.get_namespace(),
            initial_pose,
            ref_frame,
            "/gazebo",
        )
    else:
        success = False

    if not success:
        rospy.logerr("Spawn service failed. Exiting")
        return success
