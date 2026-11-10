import math

param worldOffset = Vector(0, 0, 50)
param timestep = 0.1

model scenic.simulators.airsim.model


ground = getPrexistingObj("ground")

ego = new StaticObj on ground,
    with assetName "Cone",
    with width 10,
    with length 10,
    with height 10

positions = []
for i in range(10):
    pos = Vector(i * 3, math.cos(i) * Uniform(1, 3), 1)
    positions.append(pos + Vector(0, 0, 3))

    new StaticObj at pos + Vector(0, 0, 1),
        with assetName "Cone",
        with width 1,
        with length 1,
        with height 1

drone = new Drone on positions[0],
    with behavior Patrol(positions, smooth=False, speed=5)
