""" Tests visibility calculation time on an object completely enclosed in two spheres, 
trying to view the outside sphere.
"""

from scipy.spatial.transform import Rotation
from pathlib import Path

workspace = Workspace(everywhere)

ego = new Object facing Orientation(Rotation.random()), at (Range(-0.1,0.1),Range(-0.1,0.1),Range(-0.1,0.1))

def get_shape(hole_size):
	return MeshShape(
			SpheroidRegion(dimensions=(1,1,1)).difference(
			SpheroidRegion(dimensions=(0.9,0.9,0.9))).difference(
			BoxRegion(dimensions=(hole_size,0.5,hole_size), position=(0,0.5,0))).mesh
		)

occluding_sphere = new Object at (0,0,0), with shape get_shape(0.1), with width 3, with length 3, with height 3
target_sphere = new Object at (0,0,0), with shape get_shape(0.3), with width 5, with length 5, with height 5, not visible
