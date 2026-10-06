'''
To run this file using the Carla simulator:
    scenic examples/carla/adjacentOpposingPair.scenic --2d --model scenic.simulators.carla.model
'''
param map = localPath('../../assets/maps/CARLA/Town10HD_Opt.xodr')
model scenic.simulators.carla.model

ego = new Car with visibleDistance 20
c2 = new Car visible
c3 = new Car at c2 offset by Range(-10, 1) @ 0
require abs(relative heading of c3 from c2) >= 150 deg