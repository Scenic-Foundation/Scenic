""" Scenario Description
Voyage OAS Scenario Unique ID: 2-2-XX-CF-STR-CAR:Pa>E:03
The lead car suddenly stops and then resumes moving forward

To run this file using the Carla simulator:
    scenic examples/carla/NHTSA_Scenarios/OAS_Scenarios/oas_scenario_05.scenic --2d --model scenic.simulators.carla.model --simulate
"""

param map = localPath('../../../assets/maps/CARLA/Town10HD_Opt.xodr')  # or other CARLA map that definitely works
param carla_map = 'Town10HD_Opt'
model scenic.domains.driving.model

MAX_BREAK_THRESHOLD = 1
SAFETY_DISTANCE = 10
INITIAL_DISTANCE_APART = -1 * Uniform(5, 10)
STEPS_PER_SEC = 10

behavior LeadCarBehavior():
    try:
        do FollowLaneBehavior()
    interrupt when 5 * STEPS_PER_SEC < simulation().currentTime and simulation().currentTime < 6 * STEPS_PER_SEC:
        take SetBrakeAction(MAX_BREAK_THRESHOLD)

behavior CollisionAvoidance():
    while withinDistanceToAnyObjs(self, SAFETY_DISTANCE):
        take SetBrakeAction(MAX_BREAK_THRESHOLD)


behavior FollowLeadCarBehavior():

    try: 
        do FollowLaneBehavior()

    interrupt when withinDistanceToAnyObjs(self, SAFETY_DISTANCE):
        do CollisionAvoidance()


roads = network.roads
select_road = Uniform(*roads)
select_lane = Uniform(*select_road.lanes)

other = new Car on select_lane.centerline,
        with behavior LeadCarBehavior()

ego = new Car following roadDirection from other for INITIAL_DISTANCE_APART,
        with behavior FollowLeadCarBehavior()