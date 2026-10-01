from scenic.simulators.webots.model import WebotsObject

# Set up workspace
width = 5
length = 5
workspace = Workspace(RectangularRegion(0 @ 0, 0, width, length))

# types of objects

class Goal(WebotsObject):
	"""Flag indicating the goal location."""
	width: 0.3
	length: 0.3
	webotsType: 'GOAL'

class Rover(WebotsObject):
	"""Mars rover."""
	width: 0.5
	length: 0.7
	webotsType: 'ROVER'
	rotationOffset: 90 deg

class Debris(WebotsObject):
	"""Abstract class for debris scattered randomly in the workspace."""
	position: new Point in workspace
	heading: Range(0, 360) deg

class BigRock(Debris):
	"""Large rock."""
	width: 0.17
	length: 0.17
	webotsType: 'ROCK_BIG'

class Rock(Debris):
	"""Small rock."""
	width: 0.10
	length: 0.10
	webotsType: 'ROCK_SMALL'

class Pipe(Debris):
	"""Pipe with variable length."""
	width: 0.2
	length: Range(0.5, 1.5)
	webotsType: 'PIPE'

	def startDynamicSimulation(self):
		# Apply variable length
		self.webotsObject.getField('height').setSFFloat(self.length)
		# Apply 3D rotation to make pipes lie flat on surface
		rotation = [cos(self.heading), sin(self.heading), 0, 90 deg]
		self.webotsObject.getField('rotation').setSFRotation(rotation)

ego = new Rover at 0 @ -2

goal = new Goal at Range(-2, 2) @ Range(2, 2.5)

# Bottleneck made of two pipes with a rock in between

gap = 1.2 * ego.width
halfGap = gap / 2

bottleneck = new OrientedPoint offset by Range(-1.5, 1.5) @ Range(0.5, 1.5), facing Range(-30, 30) deg

require abs((angle to goal) - (angle to bottleneck)) <= 10 deg

new BigRock at bottleneck

leftEdge = new OrientedPoint at bottleneck offset by -halfGap @ 0,
    facing Range(60, 120) deg relative to bottleneck.heading
rightEdge = new OrientedPoint at bottleneck offset by halfGap @ 0,
    facing Range(-120, -60) deg relative to bottleneck.heading

new Pipe ahead of leftEdge, with length Range(1, 2)
new Pipe ahead of rightEdge, with length Range(1, 2)

# Other junk because why not?

new Pipe
new BigRock beyond bottleneck by Range(-0.5, 0.5) @ Range(0.5, 1)
new BigRock beyond bottleneck by Range(-0.5, 0.5) @ Range(0.5, 1)
new Rock
new Rock
new Rock