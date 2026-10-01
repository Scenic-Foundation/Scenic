model scenic.simulators.webots.model

from pathlib import Path

# Set up workspace
width = 10
length = 10
workspace = Workspace(RectangularRegion(0 @ 0, 0, width, length))

# types of objects

class MarsGround(Ground):
    width: width
    length: length
    gridSize: 20

class MarsHill(Hill):
    position: new Point in workspace
    width: Range(1,2)
    length: Range(1,2)
    height: Range(0.1, 0.3)
    spread: Range(0.2, 0.3)
    regionContainedIn: everywhere

class Goal(WebotsObject):
    """Flag indicating the goal location."""
    width: 0.1
    length: 0.1
    webotsType: 'GOAL'

class Rover(WebotsObject):
    """Mars rover."""
    width: 0.5
    length: 0.7
    height: 0.4
    webotsType: 'ROVER'
    rotationOffset: (90 deg, 0, 0)

class Debris(WebotsObject):
    """Abstract class for debris scattered randomly in the workspace."""
    # Recess things into the ground slightly by default
    baseOffset: (0, 0, -self.height/3)

class BigRock(Debris):
    """Large rock."""
    shape: MeshShape.fromFile(globalParameters.meshBasePath / "webots_rock_large.obj.bz2")
    yaw: Range(0, 360 deg)
    webotsType: 'ROCK_BIG'
    positionOffset: Vector(0,0, -self.height/2)

class Rock(Debris):
    """Small rock."""
    shape: MeshShape.fromFile(globalParameters.meshBasePath / "webots_rock_small.obj.bz2")
    yaw: Range(0, 360 deg)
    webotsType: 'ROCK_SMALL'
    positionOffset: Vector(0,0, -self.height/2)

class Pipe(Debris):
    """Pipe with variable length."""
    width: 0.2
    length: Range(0.5, 1.5)
    height: self.width
    shape: CylinderShape(initial_rotation=(90 deg, 0, 90 deg))
    yaw: Range(0, 360 deg)
    webotsType: 'PIPE'
    rotationOffset: (90 deg, 0, 90 deg)

    def startDynamicSimulation(self):
        # Apply variable length
        self.webotsObject.getField('height').setSFFloat(self.length)

# Ground with random gaussian hills
ground = new MarsGround on (0,0,0), with terrain [new MarsHill for _ in range(60)]

# Ego and goal on ground
ego = new Rover at (0, -3), on ground, with controller 'sojourner'
goal = new Goal at (Range(-2, 2), Range(2, 3)), on ground, facing (0,0,0)

# Bottleneck made of two pipes with a rock in between
bottleneck = new OrientedPoint at ego offset by Range(-1.5, 1.5) @ Range(0.5, 1.5), facing Range(-30, 30) deg
require abs((angle to goal) - (angle to bottleneck)) <= 10 deg
new BigRock at bottleneck, on ground

gap = 1.2 * ego.width
halfGap = gap / 2

leftEdge = new OrientedPoint left of bottleneck by halfGap,
    facing Range(60, 120) deg relative to bottleneck.heading
rightEdge = new OrientedPoint right of bottleneck by halfGap,
    facing Range(-120, -60) deg relative to bottleneck.heading

new Pipe ahead of leftEdge, with length Range(1, 2), on ground, facing leftEdge, with parentOrientation 0
new Pipe ahead of rightEdge, with length Range(1, 2), on ground, facing rightEdge, with parentOrientation 0

# Other junk because why not?

new Pipe on ground, with parentOrientation 0
new BigRock beyond bottleneck by Range(0.25, 0.75) @ Range(0.75, 1), on ground
new BigRock beyond bottleneck by Range(-0.75, -0.25) @ Range(0.75, 1), on ground
new Rock on ground
new Rock on ground
new Rock on ground
