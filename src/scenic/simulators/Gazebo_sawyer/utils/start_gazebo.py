from gazebo_msgs.srv import DeleteModel
import roslaunch
import rospy
from std_srvs.srv import Empty


def CreateSimLaunchParent(
    x=0.0, y=0.0, z=0.0, Yaw=0.0
):  # For now, the arguments are dummies
    uuid = roslaunch.rlutil.get_or_generate_uuid(None, False)
    roslaunch.configure_logging(uuid)
    cli_args = []  # fill in arg names
    roslaunch_file1 = roslaunch.rlutil.resolve_launch_arguments(cli_args)
    launch_files = (
        roslaunch_file1  # only need to put in list if there are multiple files to launch
    )
    parent = roslaunch.parent.ROSLaunchParent(uuid, launch_files)
    return parent


def PauseGazebo():
    """
    Pauses Gazebo
    """
    rospy.wait_for_service("/gazebo/pause_physics")
    pause = rospy.ServiceProxy("/gazebo/pause_physics", Empty)
    pause()
    return


def UnpauseGazebo():
    """
    Unpauses Gazebo
    """
    rospy.wait_for_service("/gazebo/unpause_physics")
    unpause = rospy.ServiceProxy("/gazebo/unpause_physics", Empty)
    unpause()
    return


def ResetGazeboWorldAndSim():
    """
    Resets the Gazebo world and simulation
    Probably NOT the function you want to call in most cases
    This might cause the robot and ROS to go wild
    """
    rospy.wait_for_service("/gazebo/reset_world")
    reset_world = rospy.ServiceProxy("/gazebo/reset_world", Empty)
    reset_world()

    rospy.wait_for_service("/gazebo/reset_simulation")
    reset_simulation = rospy.ServiceProxy("/gazebo/reset_simulation", Empty)
    reset_simulation()
    return


def ResetGazeboWorld():
    """
    Resets the Gazebo world. Simulation time is NOT reset
    Probably the Reset function that you want
    """
    rospy.wait_for_service("/gazebo/reset_world")
    reset_world = rospy.ServiceProxy("/gazebo/reset_world", Empty)
    reset_world()
    return
