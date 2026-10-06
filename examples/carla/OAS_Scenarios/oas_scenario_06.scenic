""" Scenario Description
Voyage OAS Scenario Unique ID: 2-2-XX-CF-STR-CAR:Pa>E:03
The car ahead of ego that is badly parked over the sidewalk cuts into ego vehicle's lane.
This scenario may fail if there exists any obstacle (e.g. fences) on the sidewalk 

To run this file using the Carla simulator:
    scenic examples/carla/NHTSA_Scenarios/OAS_Scenarios/oas_scenario_06.scenic --2d --model scenic.simulators.carla.model --simulate
"""


param map = localPath('../../../assets/maps/CARLA/Town10HD_Opt.xodr')  # or other CARLA map that definitely works
param carla_map = 'Town10HD_Opt'
model scenic.domains.driving.model

MAX_BREAK_THRESHOLD = 1
SAFETY_DISTANCE = 8
PARKING_SIDEWALK_OFFSET_RANGE = 2
CUT_IN_TRIGGER_DISTANCE = Range(10, 12)
EGO_SPEED = 8
PARKEDCAR_SPEED = 7

behavior CutInBehavior(laneToFollow, target_speed):
    while (distance from self to ego) > CUT_IN_TRIGGER_DISTANCE:
        wait

    do FollowLaneBehavior(laneToFollow = laneToFollow, target_speed=target_speed)

behavior CollisionAvoidance():
    while withinDistanceToAnyObjs(self, SAFETY_DISTANCE):
        take SetBrakeAction(MAX_BREAK_THRESHOLD)


behavior EgoBehavior(target_speed):
    try: 
        do FollowLaneBehavior(target_speed=target_speed)

    interrupt when withinDistanceToAnyObjs(self, SAFETY_DISTANCE):
        do CollisionAvoidance()


roads = network.roads
select_road = Uniform(*roads)
ego_lane = select_road.lanes[0]

ego = new Car on ego_lane.centerline,
        with behavior EgoBehavior(target_speed=EGO_SPEED)
        
spot = new OrientedPoint on visible curb
parkedHeadingAngle = Uniform(-1,1)*Range(10,20) deg

other = new Car left of (spot offset by PARKING_SIDEWALK_OFFSET_RANGE @ 0), facing parkedHeadingAngle relative to ego.heading,
            with behavior CutInBehavior(ego_lane, target_speed=PARKEDCAR_SPEED),
            with regionContainedIn None

require (angle from ego to other) - ego.heading < 0 deg
require 10 < (distance from ego to other) < 20
