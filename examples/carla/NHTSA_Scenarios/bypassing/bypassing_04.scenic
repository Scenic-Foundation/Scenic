"""
TITLE: Bypassing 04
AUTHOR: Francis Indaheng, findaheng@berkeley.edu
DESCRIPTION: Ego vehicle performs multiple lane changes to bypass 
two slow adversary vehicles.
SOURCE: NHSTA, #16

To run this file using the Carla simulator:
    scenic examples/carla/NHTSA_Scenarios/bypassing/bypassing_04.scenic --2d --model scenic.simulators.carla.model --simulate
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

param EGO_SPEED = VerifaiRange(6, 8)

param ADV1_DIST = VerifaiRange(20, 25)
param ADV2_DIST = globalParameters.ADV1_DIST + VerifaiRange(15, 20)
param ADV_SPEED = VerifaiRange(2, 4)

BYPASS_DIST = 15
INIT_DIST = 50
TERM_DIST = globalParameters.ADV2_DIST + 15

#################################
# AGENT BEHAVIORS               #
#################################

behavior EgoBehavior():
    try:
        do FollowLaneBehavior(target_speed=globalParameters.EGO_SPEED)
    interrupt when (distance to adversary_1) < BYPASS_DIST:
        newLaneSec = self.laneSection.laneToRight
        do LaneChangeBehavior(
            laneSectionToSwitch=newLaneSec,
            target_speed=globalParameters.EGO_SPEED)
    interrupt when (distance to adversary_2) < BYPASS_DIST:
        newLaneSec = self.laneSection.laneToLeft
        do LaneChangeBehavior(
            laneSectionToSwitch=newLaneSec,
            target_speed=globalParameters.EGO_SPEED)

behavior Adversary2Behavior():
    rightLaneSec = self.laneSection.laneToRight
    do LaneChangeBehavior(
        laneSectionToSwitch=rightLaneSec,
        target_speed=globalParameters.ADV_SPEED)
    do FollowLaneBehavior(target_speed=globalParameters.ADV_SPEED)

#################################
# SPATIAL RELATIONS             #
#################################

initLane = Uniform(*filter(lambda lane:
    all([sec._laneToRight is not None for sec in lane.sections]),
    network.lanes))
egoSpawnPt = new OrientedPoint in initLane.centerline
egoLaneSecToSwitch = initLane.sectionAt(egoSpawnPt).laneToRight

#################################
# SCENARIO SPECIFICATION        #
#################################

ego = new Car at egoSpawnPt,
    with blueprint MODEL,
    with behavior EgoBehavior()

adversary_1 = new Car following roadDirection for globalParameters.ADV1_DIST,
    with blueprint MODEL,
    with behavior FollowLaneBehavior(target_speed=globalParameters.ADV_SPEED)

adversary_2 = new Car following roadDirection for globalParameters.ADV2_DIST,
    with blueprint MODEL,
    with behavior Adversary2Behavior()

require (distance to intersection) > INIT_DIST
require (distance from adversary_1 to intersection) > INIT_DIST
require (distance from adversary_2 to intersection) > INIT_DIST
terminate when (distance to adversary_2) > TERM_DIST
