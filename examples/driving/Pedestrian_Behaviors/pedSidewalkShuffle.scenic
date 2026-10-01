param map = localPath('../../../assets/maps/CARLA/Town01.xodr')
model scenic.domains.driving.model

targetSidewalk = Uniform(*network.sidewalks)

pedASpeed = Range(0.9, 1.8)
pedBSpeed = Range(0.9, 1.8)

pedA = new Pedestrian at targetSidewalk.centerline.start,
    with behavior WalkPath(targetSidewalk.centerline, targetSpeed=pedASpeed)

pedB = new Pedestrian at targetSidewalk.centerline.end,
    with behavior WalkPath(targetSidewalk.centerline.reverse(), targetSpeed=pedBSpeed)

require 10 <= (distance from pedA to pedB) <= 30

terminate when ((distance from pedA to targetSidewalk.centerline.end) < 0.1
        and (distance from pedB to targetSidewalk.centerline.start) < 0.1)
