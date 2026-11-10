# NOTE: add your world info path here
# param worldInfoPath = "[YOUR PATH HERE]"
param worldOffset = Vector(0,0,50) # blocks world offset

model scenic.simulators.airsim.model


drone1 = new Drone at (0,0,10),
    with behavior Patrol([(-10,20,10),(10,40,10),(-10,40,10),(-10,20,10),(10,20,10),(10,40,10),(-1,40,10)],True)
