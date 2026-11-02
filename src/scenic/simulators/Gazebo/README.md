# Scenic-Gazebo Interface
This repo contains the code to the Scenic-Gazebo interface.
## Requirements & Installation

 - Scenic 3 is required, as well as Python 3.8+, ROS Noetic, and Ubuntu 20.04.
 - The Ubuntu 20.04 requirement is due to ROS Noetic officicially supporting it. It should not be strictly required if you can get ROS Noetic running with Gazebo on your machine. Though this interface is only tested on Ubuntu 20.04.
 - Other than the official installation, ROS Noetic can also be installed with [RoboStack](https://robostack.github.io/index.html), which can be helpful if you are on MacOS or Windows.
 - It is strongly recommended to install Scenic outside any virtual environment for Gazebo/ROS purposes since Gazebo/ROS utilizes some Ubuntu native packages that is difficult to get from conda/pip
 - When installing Scenic, please do the "Repository" install outlined in this page: https://scenic-lang.readthedocs.io/en/latest/quickstart.html#installation 
 - In terms of using ROS and Gazebo, it should be fine to control your robot without ROS. However, Gazebo needs to be started with ROS.

## Instructions for Use
If you are new to Gazebo/ROS, we highly recommend you start by going through the [ROS tutorial](https://wiki.ros.org/ROS/Tutorials)
 1. Before running Scenic, start the Gazebo simulator with ROS, launch and bringup any ROS stack you need, and unpause the
    simulation.
 2. Open a separate terminal, run `scenic <YOUR PROGRAM>.scenic --simulate`(see https://scenic-lang.readthedocs.io/en/latest/options.html for more
    command-line options). Make sure you sourced the corresponding `.bash` or `.zsh` in your ROS workspace needed to run your simulaton in this terminal, too!.
 3. In general, any ROS launch files should be run before starting Scenic.
 4. Any new models (e.g. furniture, small objects) should be added in `model.scenic`. See below for more notes on adding models. 

## Important Notes

 - The Scenic coordinate system should match the `map` frame of the simulator which may or may not be the Gazebo `world` frame depending on the developer's choice, except that `yaw=0` is defined to be the +y axis rather than the +x as it is in the simulator.
 - When adding new models, for objects whose reference frame used by Gazebo to determine its location is on the bottom, please specify a `positionOffset` field in the class definition. This field is the vector pointing from the center of the object to the position of the reference frame. When placing objects whose frame is at the bottom, please use the `on` syntax and never the `at` syntax.
 - It is necessary to specify dimensions or shapes of new models you add. If this is not done, Scenic defaults to treating each object as boxes with side-length 1m, causing `RejectionExceptions` and other errors in generating scenes.
 - When creating new actions, `applyTo` should return a function that takes no argument. If the user wishes to do other wise, please reflect the change in the `step` function in `simulator.py`.
 - Before running the scene, it is helpful to run scenic `<YOUR PROGRAM>.scenic` with out the `--simulate` flag to see how Scenic is seeing the world as a sanity check. Note you need to run Scenic from a gui/desktop to do this rather than on an ssh terminal.

## Model Library
-   Robot
	-   String name: name used by Gazebo to identify the robot
	-   String object_type: the kind of object (table, chair, bottle etc.); used to access the .sdf/urdf file, default ‘robot’
	-  String domain_name: the domain name of the robot in ROS
	- Vector positionOffset: vector pointing from the center of the robot to the ref frame used by Gazebo to identify the robot's position
	-   Vector Position: position in the Scenic coordinate
	-  MeshShape shape: the shape of the robot as perceived by Scenic
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

-   General Objects, including KitchenTable, SmallBottle, BottleWithMarker, HighTable, and Chair
	-   String name: name used by Gazebo to identify the object
	-   String object_type: the kind of object (table, chair, bed); used to access the .sdf file
	-  String description_file: the file that  is used to spawn the object
	-  String description_file_type: the file type for the description file
	- Vector positionOffset: vector pointing from the center of the robot to the ref frame used by Gazebo to identify the object's position
	-   Vector Position: position in the robot  map coordinate
	-  MeshShape shape: the shape of the robot as perceived by Scenic
	-   float roll: the roll as used by Scenic
	-   float pitch: the pitch as used by Scenic
	-   float yaw: the yaw as used by Scenic
	-   String marker_id (if the object is has a marker): identifies the tf frame created by the attached marker if there is one
	-   bool collision: whether this object will be part of the collision world
	-   String mesh (if available): uri to the mesh files for collision avoidance
	-   shape: set if a mesh for the object exist  
	-   float width (if no mesh)
	-   float height (if no mesh)
	-   float length (if no mesh) 
	-   String rough_collision_shape: the shape (box, sphere, cylinder) that is used to approximated the object’s collision
## On Implementing Actions and Behaviors:
- One important thing when adapting your robot to the Gazebo interface is to separate out any code that handles waiting-until-finish for each action when implementing actions in `actions.py` . This is because it is important to not have any code that blocks execution of Scenic in the background. 
- Instead, implement your action, and write the wait code as a behavior in `behavior.scenic`, and chain the `take` clause for the action and the `do` clause for the wait behavior inside another behavior, and call this new behavior to perform the action in your Scenic program. See the Sawyer implementation as an example.
- In general, any kind of complex action/function from the robot's API that will block code execution should be written as a `behavior` rather than an `Action`.
