# Code adapted from the spawn_model script from gazebo_ros

import os
import xml

from simulation_interfaces.srv import SpawnEntity, DeleteEntity
from simulation_interfaces.msg import Resource
from geometry_msgs.msg import Pose, Quaternion, Point, PoseStamped

from scenic.simulators.gazebo.utils.quaternion_utils import quaternion_from_euler

import rclpy

def DeleteObject(name, node, client, sim=None):
    """
    deletes the object from Gazebo and collision world
    Args:
    String name: the name of the object
    """
    request = DeleteEntity.Request()
    request.entity = name

    node.get_logger().info(f"Attempting to delete entity {name}")
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future)
    if future.result() is not None:
        print('response: %r' % future.result())
    else:
        node.get_logger().error(f"Delete service failed for {name}")
        return False
    return True

# def SpawnObject( # for ROS Rolling
#     name,
#     object_xml,
#     node,
#     client,
#     x=0,
#     y=0,
#     z=0,
#     roll=0,
#     pitch=0,
#     yaw=0,
#     file_type="sdf",
#     ref_frame="map",
# ):
#     node.get_logger().info(f"Loading model XML from file")
#     model_xml = object_xml

#     if not os.path.exists(model_xml):
#         node.get_logger().fatal("Error: specified file %s does not exist", model_xml)
#         return False
#     if not os.path.isfile(model_xml):
#         node.get_logger().fatal("Error: specified file %s is not a file", model_xml)
#         return False

#     try:
#         f = open(model_xml, "r")
#         model_xml = f.read()

#     except IOError as e:
#         node.get_logger().error(f"Error reading file {model_xml}: {e}")
#         return False
#     if model_xml == "":
#         node.get_logger().error(f"Error: file {model_xml} is empty")
#         return False

#     try:
#         xml_parsed = xml.etree.ElementTree.fromstring(model_xml)
#     except xml.etree.ElementTree.ParseError as e:
#         node.get_logger().error(f"Invalid XML: {e}")
#         return False

#     model_xml = xml.etree.ElementTree.tostring(xml_parsed)

#     if not isinstance(model_xml, str):
#         model_xml = model_xml.decode(encoding="ascii")
    
#     initial_pose = Pose()
#     initial_pose.position = Point()
#     initial_pose.position.x = float(x)
#     initial_pose.position.y = float(y)
#     initial_pose.position.z = float(z)

#     q = quaternion_from_euler(roll, pitch, yaw)
#     initial_pose.orientation = Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])

#     request = SpawnEntity.Request()

#     request.name = name
#     request.entity_resource = Resource()
#     request.entity_resource.uri = object_xml
#     request.allow_renaming = False
#     stamped_pose = PoseStamped()
#     stamped_pose.pose = initial_pose
#     request.initial_pose = stamped_pose

#     node.get_logger().info(f"Attempting to spawn entity {name}")

#     future = client.call_async(request)
#     rclpy.spin_until_future_complete(node, future)
#     if future.result() is not None:
#         print('response: %r' % future.result())
#     else:
#         node.get_logger().error(f"Spawn service failed for {name}")
#         return False

#     return True


def SpawnObject( # for ROS Jazzy
    name,
    object_xml,
    node,
    client,
    x=0,
    y=0,
    z=0,
    roll=0,
    pitch=0,
    yaw=0,
    file_type="sdf",
    ref_frame="map",
):
    node.get_logger().info(f"Loading model XML from file")
    model_xml = object_xml

    if not os.path.exists(model_xml):
        node.get_logger().fatal("Error: specified file %s does not exist", model_xml)
        return False
    if not os.path.isfile(model_xml):
        node.get_logger().fatal("Error: specified file %s is not a file", model_xml)
        return False

    try:
        f = open(model_xml, "r")
        model_xml = f.read()

    except IOError as e:
        node.get_logger().error(f"Error reading file {model_xml}: {e}")
        return False
    if model_xml == "":
        node.get_logger().error(f"Error: file {model_xml} is empty")
        return False

    try:
        xml_parsed = xml.etree.ElementTree.fromstring(model_xml)
    except xml.etree.ElementTree.ParseError as e:
        node.get_logger().error(f"Invalid XML: {e}")
        return False

    model_xml = xml.etree.ElementTree.tostring(xml_parsed)

    if not isinstance(model_xml, str):
        model_xml = model_xml.decode(encoding="ascii")
    
    initial_pose = Pose()
    initial_pose.position = Point()
    initial_pose.position.x = float(x)
    initial_pose.position.y = float(y)
    initial_pose.position.z = float(z)

    q = quaternion_from_euler(roll, pitch, yaw)
    initial_pose.orientation = Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])

    request = SpawnEntity.Request()

    request.name = name
    request.uri = object_xml
    request.allow_renaming = False
    stamped_pose = PoseStamped()
    stamped_pose.pose = initial_pose
    request.initial_pose = stamped_pose

    node.get_logger().info(f"Attempting to spawn entity {name}")
    state = None
    for _ in range(20): # sometimes spins forever if you don't set a timeout and retry, not sure why but this is necessary
        # print(f'spawning {name}, attempt {i}')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=1)
        if future.result():
            print(future.result())
            state = future.result()
            break
    if state is None:
        node.get_logger().error(f"Spawn service failed for {name}")
        return False

    return True
