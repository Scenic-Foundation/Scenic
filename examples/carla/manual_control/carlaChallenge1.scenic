""" Scenario Description
Traffic Scenario 01.
Control loss without previous action.
The ego-vehicle loses control due to bad conditions on the road and it must recover, coming back to
its original lane.

To run this file using the Carla simulator:
    scenic examples/carla/manual_control/carlaChallenge1.scenic --2d --model scenic.simulators.carla.model --simulate
"""

## SET MAP AND MODEL (i.e. definitions of all referenceable vehicle types, road library, etc)
param map = localPath('../../../assets/maps/CARLA/Town10HD_Opt.xodr')  # or other CARLA map that definitely works
param carla_map = 'Town10HD_Opt'
param render = 0
model scenic.simulators.carla.model

## CONSTANTS
EGO_MODEL = "vehicle.nissan.patrol"
EGO_SPEED = 10

## DEFINING SPATIAL RELATIONS
# Please refer to scenic/domains/driving/roads.py how to access detailed road infrastructure
# 'network' is the 'class Network' object in roads.py

# make sure to put '*' to uniformly randomly select from all elements of the list, 'lanes'
lane = Uniform(*network.lanes)

start = new OrientedPoint on lane.centerline
ego = new Car at start,
    with blueprint EGO_MODEL,
    with rolename "hero"

debris1 = new Debris following roadDirection for Range(10, 20)
debris2 = new Debris following roadDirection from debris1 for Range(5, 10)
debris3 = new Debris following roadDirection from debris2 for Range(5, 10)

require (distance to intersection) > 50
terminate when (distance from debris3 to ego) > 10 and (distance to start) > 50
