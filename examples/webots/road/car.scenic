
from scenic.simulators.webots.road.world import setLocalWorld
setLocalWorld(__file__, 'berkeley.wbt')

from scenic.simulators.webots.road.model import *

ego = new ToyotaPrius
