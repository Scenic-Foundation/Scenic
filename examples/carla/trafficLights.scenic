""" Scenario Description
Example scenario of traffic lights management.

To run this file using the Carla simulator:
    scenic examples/carla/trafficLights.scenic --2d --model scenic.simulators.carla.model --simulate
"""

## SET MAP AND MODEL (i.e. definitions of all referenceable vehicle types, road library, etc)
param map = localPath('../../assets/maps/CARLA/Town10HD_Opt.xodr')  # or other CARLA map that definitely works
param carla_map = 'Town10HD_Opt'
model scenic.simulators.carla.model

## CONSTANTS
EGO_MODEL = "vehicle.nissan.patrol"
EGO_SPEED = 10

## DEFINING BEHAVIORS
# Refer to scenic/simulators/carla/model.scenic for more information
# about how to access detailed information about traffic lights

# EGO BEHAVIOR: Follow the lane respecting the traffic lights
behavior EgoBehaviorTL(speed=10):
    try:
        do FollowLaneBehavior(speed)
    interrupt when withinDistanceToRedYellowTrafficLight(self, 15):
        take SetBrakeAction(1.0)

## DEFINING SPATIAL RELATIONS
# Please refer to scenic/domains/driving/roads.py how to access detailed road infrastructure
# 'network' is the 'class Network' object in roads.py

# make sure to put '*' to uniformly randomly select from all elements of the list, 'lanes'
lane = Uniform(*network.lanes)

## ACTOR CREATION
# Please refer to scenic/simulators/carla/model.scenic for detailed information about
# the different actor attributes
ego = new Car on lane.centerline,
    with blueprint EGO_MODEL,
    with behavior EgoBehaviorTL(EGO_SPEED)

require (distance to intersection) < 50
require (distance to intersection) > 5
# This scenario has no end so it has to be manually interrupted
