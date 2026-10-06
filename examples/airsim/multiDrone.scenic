param worldOffset = Vector(0, 0, 50)

model scenic.simulators.airsim.model


for i in range(3):
    new Drone at (Range(-100, 100), Range(-100, 100), Range(0, 50)),
        with behavior FlyToPosition((Range(-100, 100), Range(-100, 100), Range(0, 50)))
