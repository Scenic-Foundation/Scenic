
from scenic.simulators.webots.road.world import setLocalWorld
setLocalWorld(__file__, 'berkeley.wbt')

from scenic.simulators.webots.road.model import *

ego = new Car with visibleDistance 20
c2 = new Car visible
require abs((relative heading of c2) - 90 deg) <= 10 deg
