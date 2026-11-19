"""
TITLE: Intersection 10
AUTHOR: Francis Indaheng, findaheng@berkeley.edu
DESCRIPTION: Ego Vehicle waits at 4-way intersection while adversary 
vehicle in adjacent lane passes before performing a lane change to 
bypass a stationary vehicle waiting to make a left turn.
SOURCE: NHSTA, #16

To run this file using the Carla simulator:
    scenic examples/carla/NHTSA_Scenarios/intersection/intersection_10.scenic --2d --model scenic.simulators.carla.model --simulate
"""

#################################
# MAP AND MODEL                 #
#################################

param map = localPath('../../../../assets/maps/CARLA/Town10HD_Opt.xodr')
param carla_map = 'Town10HD_Opt'
model scenic.simulators.carla.model

#################################
# CONSTANTS                     #
#################################

MODEL = 'vehicle.nissan.patrol'

param EGO_INIT_DIST = VerifaiRange(10, 15)
param EGO_SPEED = VerifaiRange(7, 10)
param EGO_BRAKE = VerifaiRange(0.5, 1.0)

STAT_INIT_DIST = [0, 5]

ADV_INIT_DIST = [15, 20]
ADV_SPEED = 10

BYPASS_DIST = 8
TERM_DIST = 70

#################################
# AGENT BEHAVIORS               #
#################################

behavior EgoBehavior():
    while (distance to adversary) < BYPASS_DIST:
        take SetBrakeAction(globalParameters.EGO_BRAKE)
    rightLaneSec = self.laneSection.laneToRight
    do LaneChangeBehavior(
            laneSectionToSwitch=rightLaneSec,
            target_speed=globalParameters.EGO_SPEED)
    do FollowLaneBehavior(target_speed=globalParameters.EGO_SPEED)

#################################
# SPATIAL RELATIONS             #
#################################

intersection = Uniform(*filter(lambda i: i.is4Way, network.intersections))

statInitLane = Uniform(*filter(lambda lane: 
    all([sec._laneToRight is not None for sec in lane.sections]),
    intersection.incomingLanes))
statSpawnPt = new OrientedPoint in statInitLane.centerline

advInitLane = statInitLane.sectionAt(statSpawnPt).laneToRight.lane
advManeuver = Uniform(*filter(lambda m: m.type is ManeuverType.STRAIGHT, advInitLane.maneuvers))
advTrajectory = [advInitLane, advManeuver.connectingLane, advManeuver.endLane]
advSpawnPt = new OrientedPoint in advInitLane.centerline

#################################
# SCENARIO SPECIFICATION        #
#################################

stationary = new Car at statSpawnPt,
    with blueprint MODEL

ego = new Car behind stationary by globalParameters.EGO_INIT_DIST,
    with blueprint MODEL,
    with behavior EgoBehavior()

adversary = new Car at advSpawnPt,
    with blueprint MODEL,
    with behavior FollowTrajectoryBehavior(target_speed=ADV_SPEED, trajectory=advTrajectory)

require STAT_INIT_DIST[0] <= (distance from stationary to intersection) <= STAT_INIT_DIST[1]
require ADV_INIT_DIST[0] <= (distance from adversary to intersection) <= ADV_INIT_DIST[1]
terminate when (distance to statSpawnPt) > TERM_DIST
