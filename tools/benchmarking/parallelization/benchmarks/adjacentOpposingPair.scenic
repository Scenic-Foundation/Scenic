model scenic.simulators.carla.model

ego = new Car with visibleDistance 20
c2 = new Car visible
c3 = new Car at c2 offset by Range(-10, 1) @ 0
require abs(relative heading of c3 from c2) >= 150 deg