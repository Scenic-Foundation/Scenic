param worldOffset = Vector(0, 0, 50)

model scenic.simulators.airsim.model


ground = getPrexistingObj("ground")
centerArea = RectangularRegion(Vector(0, 0, 30), 0, 100, 100)

platforms = []
for i in range(10):
    platforms.append(new StaticObj on ground,
        contained in centerArea,
        with assetName "Cone",
        with width Range(3, 10),
        with length Range(3, 10),
        with height 10)

points = []
for platform in platforms:
    platformRegion = platform.occupiedSpace.boundingPolygon
    point = new Point on platformRegion
    points.append(new Point at point.position + Vector(0, 0, 15))

drone = new Drone at Uniform(*points) + Vector(0, 0, 5),
    with behavior Patrol(points, True)
