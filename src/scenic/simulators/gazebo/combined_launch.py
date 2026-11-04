# mostly copied from gz_server.launch.py in ros_gz_sim
"""Launch gz_server in a component container, and also launch the Gazebo GUI client."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, TextSubstitution
from ros_gz_sim.actions import GzServer


def generate_launch_description():

    declare_world_sdf_file_cmd = DeclareLaunchArgument(
        'world_sdf_file', default_value=TextSubstitution(text='empty.sdf'),
        description='Path to the SDF world file')

    #starts server
    gz_server_action = GzServer(
        world_sdf_file=LaunchConfiguration('world_sdf_file'),
    )

    #starts gui
    gz_sim_action = ExecuteProcess(
        cmd=['gz', 'sim', '-r', LaunchConfiguration('world_sdf_file')],
        output='screen'
    )

    # Create the launch description and populate
    ld = LaunchDescription()

    # Declare the launch options
    ld.add_action(declare_world_sdf_file_cmd)
    # Add the gz_server action
    ld.add_action(gz_server_action)
    ld.add_action(gz_sim_action)

    return ld
