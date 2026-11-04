# Scenic-Gazebo Interface
This is the code for the Scenic-Gazebo interface.

## Requirements and Installation
- Gazebo Harmonic
- ROS 2 Jazzy
### ROS Packages
- ros-gz
- simulation-interfaces
- ros2launch
- libsdformat14
- python3-sdformat14

## Instructions
This interface requires a running Gazebo simulation with the /gzserver endpoint up, which is launched with a ROS launch file. combined_launch.py is provided as a simple example of one. To use the interface, run:
- ros2 launch combined_launch.py
- scenic *some_scenario.scenic* -S

The interface can spawn, delete, get object states, and pause, unpause, and reset the simulation. Any robot-specific code isn't included.

## Notes
- python3-sdformat14 is a system package, to use it in a venv add include-system-site-packages = true to your venv config file