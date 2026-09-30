model scenic.simulators.isaac.model

floor = new GroundPlane with color (1, 1, 1), with width 8, with length 8
floor_region = RectangularRegion(0 @ 0, 0, 8.1, 8.1)
workspace = Workspace(floor_region)

class Cube(IsaacSimObject):
    shape: BoxShape()
    width: 0.2
    length: 0.2
    height: 0.2
    isaacAssetPath: "Isaac/Props/Rubiks_Cube/rubiks_cube.usd"

new Jetbot on floor, with behavior JetbotDrive

for _ in range(25):
    new Cube on floor, facing Range(0, 360 deg)
