
from scenic.simulators.webots.road.world import setLocalWorld
setLocalWorld(__file__, 'berkeley.wbt')

from scenic.simulators.webots.road.model import *

ego = new ToyotaPrius with visibleDistance 30

new Pedestrian on visible sidewalk
