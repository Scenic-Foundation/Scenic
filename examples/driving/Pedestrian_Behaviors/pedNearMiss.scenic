param map = localPath('../../../assets/maps/CARLA/Town01.xodr')
model scenic.simulators.metadrive.model

targetIntersection = Uniform(*network.intersections)
targetManeuver = Uniform(*targetIntersection.maneuvers)

behavior StopInIntersection():
    try:
        do FollowLaneBehavior(laneToFollow=targetManeuver.connectingLane)
    interrupt when distance from self to targetManeuver.connectingLane.centerline.end < 5:
        take SetBrakeAction(1)
        abort

ego = new Car at targetManeuver.connectingLane.centerline.start,
    with behavior StopInIntersection()

target_sidewalk = Uniform(*targetManeuver.endLane.road.sidewalks)
start_point = target_sidewalk.centerline.end
target_point = start_point offset by (-20, -1)

ped = new Pedestrian at start_point, with behavior WalkTo(target=target_point, targetSpeed=1.8)

terminate when distance from ped to target_point < 0.1