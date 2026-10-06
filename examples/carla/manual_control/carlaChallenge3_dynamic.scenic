""" Scenario Description
Traffic Scenario 03 (dynamic).
Obstacle avoidance without prior action.
The ego-vehicle encounters an obstacle / unexpected entity on the road and must perform an
emergency brake or an avoidance maneuver.

To run this file using the Carla simulator:
    scenic examples/carla/manual_control/carlaChallenge3_dynamic.scenic --2d --model scenic.simulators.carla.model --simulate
"""

# SET MAP AND MODEL (i.e. definitions of all referenceable vehicle types, road library, etc)
param map = localPath('../../../assets/maps/CARLA/Town10HD_Opt.xodr')  # or other CARLA map that definitely works
param carla_map = 'Town10HD_Opt'
param render = 0
model scenic.simulators.carla.model

# CONSTANTS
EGO_MODEL = "vehicle.nissan.patrol"
EGO_SPEED = 10

PEDESTRIAN_MIN_SPEED = 0.5
THRESHOLD = 17

behavior PedestrianBehavior(min_speed=1, threshold=10):
    while (ego.speed <= 0.1):
        wait

    do CrossingBehavior(ego, min_speed, threshold)

## DEFINING SPATIAL RELATIONS
# Please refer to scenic/domains/driving/roads.py how to access detailed road infrastructure
# 'network' is the 'class Network' object in roads.py 

# make sure to put '*' to uniformly randomly select from all elements of the list, 'network.lanes'
lane = Uniform(*network.lanes)

spot = new OrientedPoint on lane.centerline
vending_spot = new OrientedPoint following roadDirection from spot for -3

pedestrian = new Pedestrian right of spot by 3,
    with heading 90 deg relative to spot.heading,
    with regionContainedIn None,
    with behavior PedestrianBehavior(PEDESTRIAN_MIN_SPEED, THRESHOLD)

vending_machine = new VendingMachine right of vending_spot by 3,
    with heading -90 deg relative to vending_spot.heading,
    with regionContainedIn None

ego = new Car following roadDirection from spot for Range(-30, -20),
    with blueprint EGO_MODEL,
    with rolename "hero"

require (distance to intersection) > 50
require always (ego.laneSection._slowerLane is None)
terminate when (distance to spot) > 50
