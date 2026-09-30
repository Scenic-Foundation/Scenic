model scenic.simulators.isaac.model

class Box(IsaacSimObject):
    width: .2
    height: .2
    length: .2
    density: 50
    color: Uniform([1, 0.502, 0], [1, 0, 0], [0, 1, 1], [1, 0, 1])

floor = new GroundPlane with color (1, 1, 1), with width 5, with length 5

room_region = RectangularRegion(0 @ 0, 0, 5.09, 5.09)
workspace = Workspace(room_region)

b1 = new Box on floor
ego = new Kaya on floor, facing toward b1, with behavior DriveForward, ahead of b1 by 2

b2 = new Box right of b1 by .01
b3 = new Box left of b1 by .01
b4 = new Box on b1 
b5 = new Box on b4
b6 = new Box on b2
b7 = new Box on b3
b8 = new Box on b5