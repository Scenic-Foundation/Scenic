# Scenic-Sawyer Interface
This repo contains the code to the Scenic-Gazebo interface applied to Sawyer robot.
## Requirements & Installation

 - Scenic 3 is required, as well as Python 3.8+, ROS Noetic, and Ubuntu 20.04.
 - The Ubuntu 20.04 requirement is due to ROS Noetic officicially supporting it. It should not be strictly required if you can get ROS Noetic running with Gazebo on your machine. Though this interface is only tested on Ubuntu 20.04.
 - Other than the official installation, ROS Noetic can also be installed with [RoboStack](https://robostack.github.io/index.html), which can be helpful if you are on MacOS or Windows.
 - It is highly recommended to install Scenic outside any virtual environment for Gazebo/ROS purposes since Gazebo/ROS utilizes some Ubuntu native packages that is difficult to get from conda/pip
 - When installing Scenic, please do the "Repository" install outlined in this [page](https://scenic-lang.readthedocs.io/en/latest/quickstart.html#installation), you can clone Scenic anywhere you want.
 - For the Sawyer simulator, please install according to the instruction [here](https://support.rethinkrobotics.com/support/solutions/articles/80000980381-gazebo-tutorial)The repo for the simulator is at this [link](https://github.com/RethinkRobotics/sawyer_simulator), note to use the `noetic-devel` branch of the cloned Sawyer repo. 
 - For object models (sdf files), please clone this [repo](https://github.com/osrf/gazebo_models) and update the `object_prefix` variable at the beginning of `model.scenic` with directory of the cloned repo. This repo contains a number of useful sdf files for object models and is used for the running `demos/example.scenic`. However, if you are not running that example, you don't have to clone this repo.

## Instructions for Use
If you are new to ROS, we highly recommend starting with the [ROS tutorial](https://wiki.ros.org/ROS/Tutorials).
 1. Before running Scenic, start the Sawyer simulator and unpause the
    simulation. Remember to set the `electric_gripper` field for the launch file to be true.
 2. Open a separate terminal, run `scenic <YOUR PROGRAM>.scenic --simulate`(see https://scenic-lang.readthedocs.io/en/latest/options.html for more
    command-line options). See the files in the `demos` folder for examples. As always with ROS, don't forget to source the `devel/setup.bash` or `devel/setup.zsh` file in your ROS workspace beforehand!!!
 3. In general, any launch files should be run before starting Scenic.
 4. Any new models (e.g. furniture, small objects) should be added in `model.scenic`. See below for more notes on adding models. 

## Important Notes

 - The Scenic coordinate system should match the `map` frame of the simulator which may or may not be the Gazebo `world` frame depending on the developer's choice, except that `yaw=0` is defined to be the +y axis rather than the +x as it is in the simulator.
 - When adding new models, for objects whose reference frame used by Gazebo to determine its location is on the bottom, please specify a `positionOffset` field in the class definition. This field is the vector pointing from the center of the object to the position of the reference frame. When placing objects whose frame is at the bottom, please use the `on` syntax and never the `at` syntax.
 - It is necessary to specify dimensions or shapes of new models you add. If this is not done, Scenic defaults to treating each object as boxes with side-length 1m, causing `RejectionExceptions` and other errors in generating scenes.
 - When creating new actions, `applyTo` should return a function that takes no argument. If the user wishes to do other wise, please reflect the change in the `step` function in `simulator.py`.
 - Before running the scene, it is helpful to run scenic `<YOUR PROGRAM>.scenic` with out the `--simulate` flag to see how Scenic is seeing the world as a sanity check. Note you need to run Scenic from a gui/desktop to do this rather than on an ssh terminal.

## Model Library
-   Robot, which can either be used directly or be the superclass to specific robot types
	-   String name: name used by Gazebo to identify the robot
	-   String object_type: the kind of object (table, chair, bottle etc.); used to access the .sdf/urdf file
	-   String domain_name: the domain name of the robot in ROS
	-   Vector positionOffset: vector pointing from the center of the robot to the ref frame used by Gazebo to identify the robot's position
	-   Vector Position: position in the Scenic coordinate
	-   MeshShape shape: the shape of the robot as perceived by Scenic
	-   float roll: roll in Scenic coordinates
	-   float pitch: pitch in Scenic coordinates
	-   float yaw: yaw in Scenic coordinates
	-   Methods:
		-   distanceToClosest
			-   Inputs: type object_class
			-   Returns the distance to the closest object of type object_class. Returns infinity if no object of type exists.
		-   getClosest
			-   Inputs: type object_class
			-   Returns the closest instance of an object of object_class. Returns None if no such object exists
		-   UniformHeadAngles:
			-   Inputs: None
			-   Returns a tuple of two lists. The first is a list of random positions to which the head joint can move, the second is the velocity at which they move.
		-   UniformArmAngles:
			-   Inputs: None
			-   Returns a tuple of two lists. The first is a list of random positions to which each arm joint can move, the second is the velocity at which they move.

-   GazeboObject, which should be the superclass for regular objects. Some of the standard Scenic object fields are not listed here. Please refer to the official Scenic docs.
    - String name: name used by Gazebo to identify the object
	- String object_type: the kind of object (default to gazebo_object)
	- String description_file: the file that  is used to spawn the object
	- String description_file_type: the file type for the description file
	- Vector positionOffset: vector pointing from the center of the robot to the ref frame used by Gazebo to identify the object's position
	-   Vector Position: position in the Robot map coordinate
	-   float pitch: the pitch as used by Scenic
	-   float yaw: the yaw as used by Scenic
	-   float width (if no mesh)
	-   float height (if no mesh)
	-   float length (if no mesh) 
## Actions and Behaviors
	- A set of actions for the Sawyer robot is implemented as well as behaviors
    - Importantly, the code in the Sawyer API that does the waiting-until-finish for each action is implemented as a behavior, `SawyerWaitFor` , in `behavior.scenic` , and the actions in `actions.py` does not wait for the action to finish.
    - To perform actions such as moving the end effector, where it is needed to wait for the sawyer to finish moving before performing the next action, the user should call the behavior implemented in the `behavior.scenic` file that has the same name as the action. This is because the wait code for the actions are implemented as a behavior, and the way actions are usually performed is to put the `take` clause that performs the action and the `do` clause that performs the waiting behavior in the same behavior. See `behavior.scenic` for examples.

