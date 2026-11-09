
from scenic.simulators.webots.road.world import setLocalWorld
setLocalWorld(__file__, 'berkeley.wbt')

from scenic.simulators.webots.road.model import *

ped = new Pedestrian on crossing

spot = ped offset along roadDirection by Range(-5, 5) @ Range(-3, -20)

ego = new ToyotaPrius at spot, with roadDeviation Range(-10, 10) deg
