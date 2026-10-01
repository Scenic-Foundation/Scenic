""" Tests visibility calculation time on an object almost completely enclosed in two spheres, 
trying to view the outside sphere.
"""

from scipy.spatial.transform import Rotation
from pathlib import Path

workspace = Workspace(everywhere)

ego = new Object facing Orientation(Rotation.random()), at (Range(-0.1,0.1),Range(-0.1,0.1),Range(-0.1,0.1))

hollow_sphere_shape = MeshShape(
		SpheroidRegion(dimensions=(5,5,5)).difference(SpheroidRegion(dimensions=(4.8,4.8,4.8))).mesh
	)

hollow_sphere_shape_with_hole = MeshShape(
		SpheroidRegion(dimensions=(5.2,5.2,5.2)).difference(SpheroidRegion(dimensions=(5.01,5.01,5.01))).difference(
		BoxRegion(dimensions=(0.1,0.1,1), position=(0,0,2.5))).mesh
	)

occluding_sphere = new Object at (0,0,0), with shape hollow_sphere_shape_with_hole
target_sphere = new Object at (0,0,0), with shape hollow_sphere_shape, visible
