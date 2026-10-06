'''
To run this file using the Carla simulator:
    scenic examples/carla/car.scenic --2d --model scenic.simulators.carla.model --simulate
'''
param map = localPath('../../assets/maps/CARLA/Town10HD_Opt.xodr')
param carla_map = 'Town10HD_Opt'
model scenic.simulators.carla.model

ego = new Car
