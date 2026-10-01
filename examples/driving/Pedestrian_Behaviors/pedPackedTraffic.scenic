param map = localPath('../../../assets/maps/CARLA/Town05.xodr')
model scenic.simulators.metadrive.model

# Pick a road with at least 3 lanes and a sidewalk on other side
targetRoad = Uniform(*filter(lambda r: len(r.lanes) > 3 and len(r.sidewalks) >= 2, network.roads))

# TODO: Improve this
from scenic.core.distributions import distributionFunction
@distributionFunction
def foo(targetRoad, i):
    return targetRoad.sidewalks[i]

startPt = new Point on foo(targetRoad, 0)
endPt = new Point on foo(targetRoad, 1)
ped = new Pedestrian at startPt, with behavior WalkTo(target=endPt, targetSpeed=1.8)

for _ in range(10):
    targetLane = Uniform(*targetRoad.lanes)
    ego = new Car on targetLane.centerline, visible from ped

terminate when distance from ped to endPt < 0.1