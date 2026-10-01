"""
TITLE: Pedestrian 02
AUTHOR: Francis Indaheng, findaheng@berkeley.edu
DESCRIPTION: Both ego and adversary vehicles must suddenly stop to avoid 
collision when pedestrian crosses the road unexpectedly.
SOURCE: Carla Challenge, #03
"""

#################################
# MAP AND MODEL                 #
#################################

model scenic.simulators.carla.model

#################################
# CONSTANTS                     #
#################################

MODEL = 'vehicle.lincoln.mkz2017'

param EGO_INIT_DIST = VerifaiRange(-30, -20)
param EGO_SPEED = VerifaiRange(7, 10)
EGO_BRAKE = 1.0

param ADV_INIT_DIST = VerifaiRange(40, 50)
param ADV_SPEED = VerifaiRange(7, 10)
ADV_BRAKE = 1.0

PED_MIN_SPEED = 1.0
PED_THRESHOLD = 20

param SAFETY_DIST = VerifaiRange(10, 15)
BUFFER_DIST = 75
CRASH_DIST = 5
TERM_DIST = 50

#################################
# AGENT BEHAVIORS               #
#################################

behavior EgoBehavior():
    try:
        do FollowLaneBehavior(target_speed=globalParameters.EGO_SPEED)
    interrupt when withinDistanceToObjsInLane(self, globalParameters.SAFETY_DIST) and (ped in network.drivableRegion):
        take SetBrakeAction(EGO_BRAKE)
    interrupt when withinDistanceToAnyObjs(self, CRASH_DIST):
        terminate

behavior AdvBehavior():
    try:
        do FollowLaneBehavior(target_speed=globalParameters.ADV_SPEED)
    interrupt when (withinDistanceToObjsInLane(self, globalParameters.SAFETY_DIST) or (distance from adv to ped) < 10) and (ped in network.drivableRegion):
        take SetBrakeAction(ADV_BRAKE)
    interrupt when withinDistanceToAnyObjs(self, CRASH_DIST):
        terminate

#################################
# SPATIAL RELATIONS             #
#################################

road = Uniform(*filter(lambda r: len(r.forwardLanes.lanes) == len(r.backwardLanes.lanes) == 1, network.roads))
egoLane = Uniform(road.forwardLanes.lanes)[0]
spawnPt = new OrientedPoint on egoLane.centerline
advSpawnPt = new OrientedPoint following roadDirection from spawnPt for globalParameters.ADV_INIT_DIST

#################################
# SCENARIO SPECIFICATION        #
#################################

ego = new Car following roadDirection from spawnPt for globalParameters.EGO_INIT_DIST,
    with blueprint MODEL,
    with behavior EgoBehavior()

ped = new Pedestrian right of spawnPt by 3,
    with heading 90 deg relative to spawnPt.heading,
    with regionContainedIn None,
    with behavior CrossingBehavior(ego, PED_MIN_SPEED, PED_THRESHOLD)

adv = new Car left of advSpawnPt by 3,
    with blueprint MODEL,
    with heading 180 deg relative to spawnPt.heading,
    with behavior AdvBehavior()

require (distance from spawnPt to intersection) > BUFFER_DIST
require always (ego.laneSection._slowerLane is None)
require always (ego.laneSection._fasterLane is None)
require always (adv.laneSection._slowerLane is None)
require always (adv.laneSection._fasterLane is None)
terminate when (distance to spawnPt) > TERM_DIST
