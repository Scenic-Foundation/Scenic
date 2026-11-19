'''
To run this file using the Carla simulator:
    scenic examples/carla/adjacentLanes.scenic --2d --model scenic.simulators.carla.model
'''

param map = localPath('../../assets/maps/CARLA/Town10HD_Opt.xodr')
model scenic.simulators.carla.model

# Cars on adjacent lanes of the first section of Road 69
roadSec = network.elements['road0'].sections[0]
ego = new Car in roadSec.forwardLanes[0],    # rightmost lane
    with color Color(1, 0, 0)
c1 = new Car in roadSec.forwardLanes[1],     # next lane to left
    with color Color(0, 1, 0)
c2 = new Car in roadSec.backwardLanes[0],    # rightmost lane on other side of road
    with color Color(0, 0, 1)
c3 = new Car in roadSec.backwardLanes[1],    # next lane to left
    with color Color(0, 0, 0)
