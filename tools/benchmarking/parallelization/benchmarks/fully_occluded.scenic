""" Tests visibility calculation time on a complex mesh, completely occluded by another complex mesh"""

from pathlib import Path

workspace = Workspace(everywhere)

ego = new Object

chair_shape = MeshShape.fromFile(path=globalParameters.meshBasePath / "chair.obj.bz2", initial_rotation=(0,90 deg,0))

obscuring_chair = new Object with shape chair_shape, at (0,5,0),
	with pitch -90 deg, with width 5, with length 5, with height 5

target_chair = new Object with shape chair_shape, at (0,10,0),
	with width 3, with length 3, with height 3, not visible
