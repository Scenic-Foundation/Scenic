"""
TITLE: Bypassing 03
AUTHOR: Francis Indaheng, findaheng@berkeley.edu
DESCRIPTION: Ego vehicle performs a lane change to bypass a slow 
adversary vehicle but cannot return to its original lane because 
the adversary accelerates. Ego vehicle must then slow down to avoid 
collision with leading vehicle in new lane.
SOURCE: NHSTA, #16

To run this file using the Carla simulator:
    scenic examples/carla/NHTSA_Scenarios/bypassing/bypassing_03.scenic --2d --model scenic.simulators.carla.model --simulate
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

param EGO_SPEED = VerifaiRange(7, 10)
param EGO_BRAKE = VerifaiRange(0.7, 1.0)

param ADV_DIST = VerifaiRange(10, 15)
param ADV_INIT_SPEED = VerifaiRange(2, 4)
param ADV_END_SPEED = 2 * VerifaiRange(7, 10)
ADV_BUFFER_TIME = 5

LEAD_DIST = globalParameters.ADV_DIST + 10
LEAD_SPEED = globalParameters.EGO_SPEED - 4

BYPASS_DIST = [15, 10]
SAFE_DIST = 15
INIT_DIST = 50
TERM_DIST = 70
TERM_TIME = 10

#################################
# AGENT BEHAVIORS               #
#################################

behavior DecelerateBehavior(brake):
    take SetBrakeAction(brake)

behavior EgoBehavior():
    try:
        do FollowLaneBehavior(target_speed=globalParameters.EGO_SPEED)
    interrupt when (distance to adversary) < BYPASS_DIST[0]:
        fasterLaneSec = self.laneSection.fasterLane
        do LaneChangeBehavior(
                laneSectionToSwitch=fasterLaneSec,
                target_speed=globalParameters.EGO_SPEED)
        try:
            do FollowLaneBehavior(
                    target_speed=globalParameters.EGO_SPEED,
                    laneToFollow=fasterLaneSec.lane) \
                until (distance to adversary) > BYPASS_DIST[1]
        interrupt when (distance to lead) < SAFE_DIST:
            try:
                do DecelerateBehavior(globalParameters.EGO_BRAKE)
            interrupt when (distance to lead) > SAFE_DIST:
                do FollowLaneBehavior(target_speed=LEAD_SPEED) for TERM_TIME seconds
                terminate 

behavior AdversaryBehavior():
    do FollowLaneBehavior(target_speed=globalParameters.ADV_INIT_SPEED) \
        until self.lane is not ego.lane
    do FollowLaneBehavior(target_speed=globalParameters.ADV_END_SPEED)

behavior LeadBehavior():
    fasterLaneSec = self.laneSection.fasterLane
    do LaneChangeBehavior(
            laneSectionToSwitch=fasterLaneSec,
            target_speed=LEAD_SPEED)
    do FollowLaneBehavior(target_speed=LEAD_SPEED)

#################################
# SPATIAL RELATIONS             #
#################################

initLane = Uniform(*network.lanes)
egoSpawnPt = new OrientedPoint in initLane.centerline

#################################
# SCENARIO SPECIFICATION        #
#################################

ego = new Car at egoSpawnPt,
    with blueprint MODEL,
    with behavior EgoBehavior()

adversary = new Car following roadDirection for globalParameters.ADV_DIST,
    with blueprint MODEL,
    with behavior AdversaryBehavior()

lead = new Car following roadDirection for LEAD_DIST,
    with blueprint MODEL,
    with behavior LeadBehavior()

require (distance to intersection) > INIT_DIST
require (distance from adversary to intersection) > INIT_DIST
require (distance from lead to intersection) > INIT_DIST
require always (adversary.laneSection._fasterLane is not None)
terminate when (distance to egoSpawnPt) > TERM_DIST
