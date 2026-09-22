param map = localPath('../../../assets/maps/CARLA/Town03.xodr')
model scenic.domains.driving.model

param numPedestrians = 20

targetIntersection = Uniform(*filter(lambda x: x.is3Way or x.is4Way, network.intersections))

egoStartManeuver = Uniform(*targetIntersection.maneuvers)
egoStartPoint = network.roadDirection.followFrom(egoStartManeuver.startLane.centerline.end, -5)
ego = new Car at egoStartPoint

pedestrianStartZone = network.sidewalkRegion.intersect(
        CircularRegion(targetIntersection.midpoint, 60)
    )
for _ in range(globalParameters.numPedestrians):
    new Pedestrian in pedestrianStartZone, with behavior Walk(), with regionContainedIn None

terminate after 30 seconds
