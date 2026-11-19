""" Scenario Description
Traffic Scenario 04.
Obstacle avoidance without prior action.
The ego-vehicle encounters an obstacle / unexpected entity on the road and must perform an
emergency brake or an avoidance maneuver.

To run this file using the Carla simulator:
    scenic examples/carla/manual_control/carlaChallenge4.scenic --2d --model scenic.simulators.carla.model --simulate
"""

## SET MAP AND MODEL (i.e. definitions of all referenceable vehicle types, road library, etc)
param map = localPath('../../../assets/maps/CARLA/Town10HD_Opt.xodr')  # or other CARLA map that definitely works
param carla_map = 'Town10HD_Opt'
param render = 0
model scenic.simulators.carla.model

## CONSTANTS
EGO_MODEL = "vehicle.nissan.patrol"
BICYCLE_MIN_SPEED = 1
THRESHOLD = 15

behavior BicycleBehavior(speed=3, threshold=15):
    do CrossingBehavior(ego, speed, threshold)

## GEOMETRY

# make sure to put '*' to uniformly randomly select from all elements of the list
intersec = Uniform(*network.intersections)
startLane = Uniform(*intersec.incomingLanes)
maneuver = Uniform(*startLane.maneuvers)
ego_trajectory = [maneuver.startLane, maneuver.connectingLane, maneuver.endLane]

spot = new OrientedPoint in maneuver.startLane.centerline
ego = new Car at spot,
    with blueprint EGO_MODEL,
    with rolename 'hero'

spotBicycle = new OrientedPoint in maneuver.endLane.centerline,
    facing roadDirection
bicycle = new Bicycle at spotBicycle offset by 3.5@0,
    with heading 90 deg relative to spotBicycle.heading,
    with behavior BicycleBehavior(BICYCLE_MIN_SPEED, THRESHOLD),
    with regionContainedIn None

require 10 <= (distance to intersec) <= 25
require 5 <= (distance from bicycle to intersec) <= 10
terminate when (distance to spot) > 50
