import math

param worldOffset = Vector(0, 0, 50)
param timestep = 0.1

model scenic.simulators.airsim.model


def magnitude(v):
    return math.hypot(v.x, v.y, v.z)


behavior Follow(target, speed=5, tolerance=2, offset=(0, 0, 1)):
    while True:
        targetPosition = target.position + offset
        velocity = targetPosition - self.position
        distance = magnitude(velocity)
        if distance > tolerance:
            velocity = (velocity / distance) * speed
            take SetVelocity(velocity)
        wait


drone1 = new Drone at (0, 0, 10),
    with behavior Patrol([(0, 0, 10), (0, 10, 10), (10, 10, 10), (10, 0, 10)], True, speed=2)

drone2 = new Drone at (0, 100, 10),
    with behavior Follow(drone1, 5, 5, (0, 0, 0))
