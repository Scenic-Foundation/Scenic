""" Scenario Description
A vehicle drives toward an intersection with the intent to go straight through
it. The intersection has a pedestrian crosswalk on the side the vehicle is
entering or exiting. A pedestrian waits next to the crosswalk. As the ego
approaches, the pedestrian steps onto the crosswalk and walks across.
The ego is expected to brake before reaching the pedestrian.

To run this file using the MetaDrive simulator:
    scenic examples/driving/crosswalkStraightThrough.scenic --2d --model scenic.simulators.metadrive.model --simulate

To run this file using the Carla simulator:
    scenic examples/driving/crosswalkStraightThrough.scenic --2d --model scenic.simulators.carla.model --simulate
"""

param map = localPath('../../assets/maps/CARLA/Town03.xodr')
param carla_map = 'Town03'
model scenic.domains.driving.model

param time_step = 1.0/10

# CONSTANTS
EGO_SPEED = Range(7, 12)
EGO_OFFSET = -1 * Range(25, 40)
PED_SPEED = 1.2
PED_THRESHOLD = Range(35, 55)

# BEHAVIOR
behavior EgoBehavior(target_speed=10, trajectory=None):
    assert trajectory is not None
    brakeIntensity = 0.7

    try:
        do FollowTrajectoryBehavior(target_speed=target_speed, trajectory=trajectory)
        terminate

    interrupt when withinDistanceToAnyPedestrians(self, 12):
        take SetBrakeAction(brakeIntensity)

behavior PedestrianCrossBehavior(threshold=20, walking_speed=1.2, walking_direction=0):
    wait until distance from self to ego <= threshold
    take SetWalkingDirectionAction(walking_direction), SetWalkingSpeedAction(walking_speed)

# GEOMETRY
def orderedEnds(cr, m):
    ends = [cr.centerline[0], cr.centerline[-1]]
    ends.sort(key=lambda p: distance from p to m.startLane.centerline)
    return ends

straightManeuverCrossingTriples = []
for inter in network.intersections:
    for cr in inter.crossings:
        for m in cr.conflictingManeuvers:
            if m.type != ManeuverType.STRAIGHT:
                continue
            near, far = orderedEnds(cr, m)
            straightManeuverCrossingTriples.append((inter, m, cr, near, far))
chosen = Uniform(*straightManeuverCrossingTriples)
intersection = chosen[0]
straight_maneuver = chosen[1]
crossing = chosen[2]
pedSpawn = chosen[3]
pedEnd = chosen[4]

startLane = straight_maneuver.startLane
connectingLane = straight_maneuver.connectingLane
endLane = straight_maneuver.endLane

lane_traj = [startLane, connectingLane, endLane]
intersection_edge = startLane.centerline[-1]

# --

walkDirection = angle from pedSpawn to pedEnd
pedStartPoint = new OrientedPoint at pedSpawn,
                    facing walkDirection

# PLACEMENT
ego = new Car following roadDirection from intersection_edge for EGO_OFFSET,
        with behavior EgoBehavior(target_speed=EGO_SPEED, trajectory=lane_traj)

ped = new Pedestrian at pedStartPoint,
        with regionContainedIn None,
        with parentOrientation 0,
        with behavior PedestrianCrossBehavior(PED_THRESHOLD, PED_SPEED, walkDirection),
        facing walkDirection
