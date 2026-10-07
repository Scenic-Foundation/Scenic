"""Implementations of Scenic's visibility functions."""

import itertools
import math

import numpy as np
import trimesh

from scenic.core.regions import Region, SpheroidRegion
from scenic.core.type_support import toVector
from scenic.core.utils import batched
from scenic.core.vectors import Vector

BATCH_SIZE = 128


def canSee(
    position,
    orientation,
    visibleDistance,
    viewAngles,
    rayCount,
    rayDensity,
    distanceScaling,
    target,
    occludingObjects,
    debug=False,
):
    """Perform visibility checks on Points, OrientedPoints, or Objects, accounting for occlusion.

    For visibilty of Objects:

    1. Do several quick checks to see if the object is naively visible
       or not visible:

       * If the object contains its position and its position is visible,
         the object is visible.
       * If the viewer is inside the object, the object is visible.
       * If the closest distance from the object to the viewer is greater
         than the visible distance, the object is not visible.

    2. Check if the object crosses the back and/or front of the viewing
       object.
    3. Compute the spherical coordinates of all vertices in the mesh of
       the region we are trying to view, with the goal of using this to
       send rays only where they have a chance of hitting the region.
    4. Compute 2 ranges of angles (horizontal/vertical) in which rays have
       a chance of hitting the object, as follows:

       * If the object does not cross behind the viewer, take the min and
         max of the the spherical coordinate angles, while noting that this range
         is centered on the front of the viewer.
       * If the object crosses behind the viewer but not in front, transform
         the spherical angles so they are coming from the back of the object,
         while noting that this range is centered on the back of the object.
       * If it crosses both, we do not optimize the amount of rays sent.

    5. Compute the intersection of the optimizated range from step 4 and
       the viewAngles range, accounting for where the optimization range is centered.
       If it is empty, the object cannot be visible. If it is not empty, shoot rays at
       the desired density in the intersection region. Keep all rays that intersect
       the object (candidate rays).
    6. If there are no candidate rays, the object is not visible.
    7. For each occluding object in occludingObjects: check if any candidate rays
       intersect the occluding object at a distance less than the distance they intersected
       the target object. If they do, remove them from the candidate rays.
    8. If any candidate rays remain, the object is visible. If not, it is occluded
       and not visible.

    For visibility of Points/OrientedPoints:

    1. Check if distance from the viewer to the point is greater than visibleDistance.
       If so, the point cannot be visible
    2. Create a single candidate ray, using the vector from the viewer to the target.
       If this ray is outside of the bounds of viewAngles, the point cannot be visible.
    3. For each occluding object in occludingObjets: check if the candidate ray hits
       the occluding object at a distance less than the distance from the viewer to the
       target point. If so, then the object is not visible. Otherwise, the object is visible.

    Args:
        position: Position of the viewer, accounting for any offsets.
        orientation: Orientation of the viewer.
        visibleDistance: The maximum distance the viewer can view objects from.
        viewAngles: The horizontal and vertical view angles, in radians, of the viewer.
        rayCount: The total number of rays in each dimension used in visibility calculations..
        target: The target being viewed. Currently supports Point, OrientedPoint, and Object.
        occludingObjects: An optional list of objects which can occlude the target.
    """
    from scenic.core.object_types import Object, OrientedPoint, Point

    # Filter occluding objects that are obviously infeasible
    occludingObjects = [
        obj for obj in occludingObjects if position.distanceTo(obj) <= visibleDistance
    ]

    if rayCount is None:
        rayCount = (
            math.degrees(viewAngles[0]) * rayDensity,
            math.degrees(viewAngles[1]) * rayDensity,
        )

        if distanceScaling:
            target_distance = target.position.distanceTo(position)

            rayCount = (rayCount[0] * target_distance, rayCount[1] * target_distance)

        altitudeScaling = True
    else:
        # Do not scale ray counts with altitude or distance if explicitly given
        altitudeScaling = False

    if isinstance(target, (Region, Object)):
        # Extract the target region from the object or region.
        if isinstance(target, Region):
            raise NotImplementedError
        elif isinstance(target, Object):
            # If the object contains its center and we can see the center, the object
            # is visible.
            if target.shape.containsCenter and canSee(
                position,
                orientation,
                visibleDistance,
                viewAngles,
                rayCount,
                rayDensity,
                distanceScaling,
                target.position,
                occludingObjects,
            ):
                return True
            target_region = target.occupiedSpace

        # Check that the distance to the target is not greater than visibleDistance,
        if target.distanceTo(position) > visibleDistance:
            return False

        # Orient the object so that it has the same relative position and orientation to the
        # origin as it did to the viewer
        target_vertices = target_region.mesh.vertices - np.array(position.coordinates)

        if orientation is not None:
            target_vertices = orientation._inverseRotation.apply(target_vertices)

        # Add additional points along each edge that could potentially have a higher altitude
        # than the endpoints.
        vec_1s = np.asarray(target_vertices[target_region.mesh.edges[:, 0], :])
        vec_2s = np.asarray(target_vertices[target_region.mesh.edges[:, 1], :])
        x1, y1, z1 = vec_1s[:, 0], vec_1s[:, 1], vec_1s[:, 2]
        x2, y2, z2 = vec_2s[:, 0], vec_2s[:, 1], vec_2s[:, 2]
        D = x1 * x2 + y1 * y2
        N = (x1**2 + y1**2) * z2 - D * z1
        M = (x2**2 + y2**2) * z1 - D * z2
        with np.errstate(divide="ignore", invalid="ignore"):
            t_vals = N / (N + M)  # t values that can be an altitude local optimum

        # Keep only points where the t_value is between 0 and 1
        t_mask = np.logical_and(t_vals > 0, t_vals < 1)
        interpolated_points = vec_1s[t_mask] + t_vals[t_mask][:, None] * (
            vec_2s[t_mask] - vec_1s[t_mask]
        )

        target_vertices = np.concatenate((target_vertices, interpolated_points), axis=0)

        ## Check if the object crosses the y axis ahead and/or behind the viewer

        # Extract the two vectors that are part of each edge crossing the y axis.
        with np.errstate(divide="ignore", invalid="ignore"):
            y_cross_edges = (vec_1s[:, 0] / vec_2s[:, 0]) < 0
        vec_1s = vec_1s[y_cross_edges]
        vec_2s = vec_2s[y_cross_edges]

        # Figure out for which t value the vectors cross the y axis
        t = (-vec_1s[:, 0]) / (vec_2s[:, 0] - vec_1s[:, 0])

        # Figure out what the y value is when the y axis is crossed
        y_intercept_points = t * (vec_2s[:, 1] - vec_1s[:, 1]) + vec_1s[:, 1]

        # If the object crosses ahead and behind the object, or through 0,
        # we will not optimize ray casting.
        target_crosses_ahead = np.any(y_intercept_points >= 0)
        target_crosses_behind = np.any(y_intercept_points <= 0)

        ## Compute the horizontal/vertical angle ranges which bound the object
        ## (from the origin facing forwards)
        spherical_angles = np.zeros((len(target_vertices[:, 0]), 2))

        spherical_angles[:, 0] = np.arctan2(target_vertices[:, 1], target_vertices[:, 0])
        spherical_angles[:, 1] = np.arcsin(
            target_vertices[:, 2] / (np.linalg.norm(target_vertices, axis=1))
        )

        # Align azimuthal angle with y axis.
        spherical_angles[:, 0] = spherical_angles[:, 0] - math.pi / 2

        # Normalize angles between (-Pi,Pi)
        spherical_angles[:, 0] = np.mod(spherical_angles[:, 0] + np.pi, 2 * np.pi) - np.pi
        spherical_angles[:, 1] = np.mod(spherical_angles[:, 1] + np.pi, 2 * np.pi) - np.pi

        # First we check if the vertical angles overlap with the vertical view angles.
        # If not, then the object cannot be visible.
        if (
            np.min(spherical_angles[:, 1]) > viewAngles[1] / 2
            or np.max(spherical_angles[:, 1]) < -viewAngles[1] / 2
        ):
            return False

        ## Compute which horizontal/vertical angle ranges to cast rays in
        if target_crosses_ahead and target_crosses_behind:
            # No optimizations feasible here. Just send all rays.
            h_range = (-viewAngles[0] / 2, viewAngles[0] / 2)
            v_range = (-viewAngles[1] / 2, viewAngles[1] / 2)

            view_ranges = [(h_range, v_range)]

        elif target_crosses_behind:
            # We can keep the view angles oriented around the front of the object and
            # consider the spherical angles oriented around the back of the object.
            # We can then check for impossible visibility/optimize which rays will be cast.

            # Extract the viewAngle ranges
            va_h_range = (-viewAngles[0] / 2, viewAngles[0] / 2)
            va_v_range = (-viewAngles[1] / 2, viewAngles[1] / 2)

            # Convert spherical angles to be centered around the back of the viewing object.
            left_points = spherical_angles[:, 0] >= 0
            right_points = spherical_angles[:, 0] < 0

            spherical_angles[:, 0][left_points] = (
                spherical_angles[:, 0][left_points] - np.pi
            )
            spherical_angles[:, 0][right_points] = (
                spherical_angles[:, 0][right_points] + np.pi
            )

            sphere_h_range = (
                np.min(spherical_angles[:, 0]),
                np.max(spherical_angles[:, 0]),
            )
            sphere_v_range = (
                np.min(spherical_angles[:, 1]),
                np.max(spherical_angles[:, 1]),
            )

            # Extract the overlapping ranges in the horizontal and vertical view angles.
            # Note that the spherical range must cross the back plane and the view angles
            # must cross the front plane (and are centered on these points),
            # which means we can just add up each side of the ranges and see if they add up to
            # greater than or equal to Pi. If none do, then it's impossible for object to overlap
            # with the viewAngle range.

            # Otherwise we can extract the overlapping v_ranges and use those going forwards.
            overlapping_v_range = (
                np.clip(sphere_v_range[0], va_v_range[0], va_v_range[1]),
                np.clip(sphere_v_range[1], va_v_range[0], va_v_range[1]),
            )
            view_ranges = []

            if abs(va_h_range[0]) + abs(sphere_h_range[1]) > math.pi:
                h_range = (va_h_range[0], -math.pi + sphere_h_range[1])
                view_ranges.append((h_range, overlapping_v_range))

            if abs(va_h_range[1]) + abs(sphere_h_range[0]) > math.pi:
                h_range = (math.pi + sphere_h_range[0], va_h_range[1])
                view_ranges.append((h_range, overlapping_v_range))

            if len(view_ranges) == 0:
                return False

        else:
            # We can immediately check for impossible visbility/optimize which rays
            # will be cast.

            # Check if view range and spherical angles overlap in horizontal or
            # vertical dimensions. If not, return False
            if (np.max(spherical_angles[:, 0]) < -viewAngles[0] / 2) or (
                np.min(spherical_angles[:, 0]) > viewAngles[0] / 2
            ):
                return False

            # Compute trimmed view angles
            h_min = np.clip(
                np.min(spherical_angles[:, 0]), -viewAngles[0] / 2, viewAngles[0] / 2
            )
            h_max = np.clip(
                np.max(spherical_angles[:, 0]), -viewAngles[0] / 2, viewAngles[0] / 2
            )
            v_min = np.clip(
                np.min(spherical_angles[:, 1]), -viewAngles[1] / 2, viewAngles[1] / 2
            )
            v_max = np.clip(
                np.max(spherical_angles[:, 1]), -viewAngles[1] / 2, viewAngles[1] / 2
            )

            h_range = (h_min, h_max)
            v_range = (v_min, v_max)

            view_ranges = [(h_range, v_range)]

        ## Generate candidate rays
        candidate_ray_list = []

        for h_range, v_range in view_ranges:
            h_size = h_range[1] - h_range[0]
            v_size = v_range[1] - v_range[0]

            assert h_size > 0
            assert v_size > 0

            scaled_v_ray_count = math.ceil(v_size / (viewAngles[1]) * rayCount[1])
            v_angles = np.linspace(v_range[0], v_range[1], scaled_v_ray_count)

            # If altitudeScaling is true, we will scale the number of rays by the cosine of the altitude
            # to get a uniform spread.
            if altitudeScaling:
                h_ray_counts = np.maximum(
                    np.ceil(np.cos(v_angles) * h_size / (viewAngles[0]) * rayCount[0]), 1
                ).astype(int)
                h_angles_list = [
                    np.linspace(h_range[0], h_range[1], h_ray_count)
                    for h_ray_count in h_ray_counts
                ]
                angle_matrices = [
                    np.column_stack(
                        [
                            h_angles_list[i],
                            np.repeat([v_angles[i]], len(h_angles_list[i])),
                        ]
                    )
                    for i in range(len(v_angles))
                ]
                angle_matrix = np.concatenate(angle_matrices, axis=0)
            else:
                scaled_h_ray_count = math.ceil(h_size / (viewAngles[0]) * rayCount[0])
                h_angles = np.linspace(h_range[0], h_range[1], scaled_h_ray_count)
                angle_matrix = np.column_stack(
                    [np.repeat(h_angles, len(v_angles)), np.tile(v_angles, len(h_angles))]
                )

            ray_vectors = np.zeros((len(angle_matrix[:, 0]), 3))

            ray_vectors[:, 0] = -np.sin(angle_matrix[:, 0])
            ray_vectors[:, 1] = np.cos(angle_matrix[:, 0])
            ray_vectors[:, 2] = np.tan(
                angle_matrix[:, 1]
            )  # At 90 deg, np returns super large number

            ray_vectors /= np.linalg.norm(ray_vectors, axis=1)[:, np.newaxis]
            candidate_ray_list.append(ray_vectors)

        ray_vectors = np.concatenate(candidate_ray_list, axis=0)

        if orientation is not None:
            ray_vectors = orientation.getRotation().apply(ray_vectors)

        ## DEBUG ##
        # Show all original candidate rays
        if debug:
            vertices = [
                visibleDistance * vec + position.coordinates for vec in ray_vectors
            ]
            vertices = [position.coordinates] + vertices
            lines = [trimesh.path.entities.Line([0, v]) for v in range(1, len(vertices))]
            colors = [(0, 0, 255, 255) for line in lines]

            render_scene = trimesh.scene.Scene()
            render_scene.add_geometry(
                trimesh.path.Path3D(
                    entities=lines, vertices=vertices, process=False, colors=colors
                )
            )
            render_scene.add_geometry(target.occupiedSpace.mesh)
            for i in list(occludingObjects):
                render_scene.add_geometry(i.occupiedSpace.mesh)
            render_scene.show()

        # Shuffle the rays and split them into smaller batches, so we get the
        # opportunity to return early.
        ray_indices = np.arange(len(ray_vectors))
        rng = np.random.default_rng(seed=42)
        rng.shuffle(ray_indices)

        batch_size = BATCH_SIZE

        # Use a generator to avoid having to immediately split a large array
        for target_ray_indices in batched(ray_indices, batch_size):
            ray_batch = ray_vectors[np.asarray(target_ray_indices)]

            # Check if candidate rays hit target
            raw_target_hit_info = target_region.mesh.ray.intersects_location(
                ray_origins=np.full(ray_batch.shape, position.coordinates),
                ray_directions=ray_batch,
            )

            # If no hits, this object can't be visible with these rays
            if len(raw_target_hit_info[0]) == 0:
                continue

            # Extract rays that are within visibleDistance, mapping the vector
            # to the closest distance at which they hit the target
            hit_locs = raw_target_hit_info[0]
            hit_distances = np.linalg.norm(hit_locs - np.array(position), axis=1)

            target_dist_map = {}

            for hit_iter in range(len(raw_target_hit_info[0])):
                hit_ray = tuple(ray_batch[raw_target_hit_info[1][hit_iter]])
                hit_dist = hit_distances[hit_iter]

                # If the hit was out of visible distance, don't consider it.
                if hit_dist > visibleDistance:
                    continue

                # If we don't already have a hit distance for this vector, or if
                # this hit was closer, update the target distance mapping.
                if hit_ray not in target_dist_map or hit_dist < target_dist_map[hit_ray]:
                    target_dist_map[hit_ray] = hit_dist

            # If no hits within range, this object can't be visible with these rays
            if len(target_dist_map) == 0:
                continue

            # Now check if occluded objects block sight to target
            candidate_rays = set(target_dist_map.keys())

            ## DEBUG ##
            # Show all candidate vertices that hit target
            if debug:
                vertices = [
                    visibleDistance * np.array(vec) + position.coordinates
                    for vec in candidate_rays
                ]
                vertices = [position.coordinates] + vertices
                lines = [
                    trimesh.path.entities.Line([0, v]) for v in range(1, len(vertices))
                ]
                colors = [(0, 0, 255, 255) for line in lines]

                render_scene = trimesh.scene.Scene()
                render_scene.add_geometry(
                    trimesh.path.Path3D(
                        entities=lines, vertices=vertices, process=False, colors=colors
                    )
                )
                render_scene.add_geometry(target.occupiedSpace.mesh)
                for occ_obj in list(occludingObjects):
                    render_scene.add_geometry(occ_obj.occupiedSpace.mesh)
                render_scene.show()

            for occ_obj in occludingObjects:
                # If no more rays are candidates, then object is no longer visible.
                # Short circuit the loop to get to the next batch of rays.
                if len(candidate_rays) == 0:
                    break

                candidate_ray_list = np.array(list(candidate_rays))

                # Test all candidate rays against this occluding object
                object_hit_info = occ_obj.occupiedSpace.mesh.ray.intersects_location(
                    ray_origins=np.full(candidate_ray_list.shape, position.coordinates),
                    ray_directions=candidate_ray_list,
                )

                # If no hits, this object doesn't occlude. We don't need to
                # filter any rays for this object so move on the next object.
                if len(object_hit_info[0]) == 0:
                    continue

                # Check if any candidate ray hits the occluding object with a smaller
                # distance than the target.
                object_distances = np.linalg.norm(
                    object_hit_info[0] - np.array(position), axis=1
                )

                occluded_rays = set()

                for hit_iter in range(len(object_hit_info[0])):
                    hit_ray = tuple(candidate_ray_list[object_hit_info[1][hit_iter]])
                    hit_dist = object_distances[hit_iter]

                    # If this ray hit the object earlier than it hit the target, reject the ray.
                    if hit_dist <= target_dist_map[hit_ray]:
                        occluded_rays.add(hit_ray)

                candidate_rays = candidate_rays - occluded_rays

                ## DEBUG ##
                # Show occluded and non occluded rays from this object
                if debug:
                    occluded_vertices = [
                        visibleDistance * np.array(vec) + position.coordinates
                        for vec in occluded_rays
                    ]
                    clear_vertices = [
                        visibleDistance * np.array(vec) + position.coordinates
                        for vec in candidate_rays
                    ]
                    vertices = occluded_vertices + clear_vertices
                    vertices = [position.coordinates] + vertices
                    lines = [
                        trimesh.path.entities.Line([0, v])
                        for v in range(1, len(vertices))
                    ]
                    occluded_colors = [(255, 0, 0, 255) for line in occluded_vertices]
                    clear_colors = [(0, 255, 0, 255) for line in clear_vertices]
                    colors = occluded_colors + clear_colors
                    render_scene = trimesh.scene.Scene()
                    render_scene.add_geometry(
                        trimesh.path.Path3D(
                            entities=lines,
                            vertices=vertices,
                            process=False,
                            colors=colors,
                        )
                    )
                    render_scene.add_geometry(target.occupiedSpace.mesh)
                    render_scene.add_geometry(occ_obj.occupiedSpace.mesh)
                    render_scene.show()

            if len(candidate_rays) > 0:
                return True

        # No rays hit the object and are not occluded, so the object is not visible
        return False

    elif isinstance(target, (Point, Vector)):
        target_loc = toVector(target)

        # First check if the distance to the point is less than or equal to the visible distance. If not, the object cannot
        # be visible.
        target_distance = position.distanceTo(target_loc)
        if target_distance > visibleDistance:
            return False

        # Create the single candidate ray and check that it's within viewAngles.
        if orientation is not None:
            target_loc = orientation._inverseRotation.apply([target_loc])[0]

        target_vertex = target_loc - position
        candidate_ray = target_vertex / np.linalg.norm(target_vertex)

        candidate_ray_list = np.array([candidate_ray])

        azimuth = (
            np.mod(
                np.arctan2(candidate_ray[1], candidate_ray[0]) - math.pi / 2 + np.pi,
                2 * np.pi,
            )
            - np.pi
        )
        altitude = np.arcsin(candidate_ray[2])

        ## DEBUG ##
        # Show all original candidate rays
        if debug:
            vertices = [
                visibleDistance * vec + position.coordinates for vec in candidate_ray_list
            ]
            vertices = [position.coordinates] + vertices
            lines = [trimesh.path.entities.Line([0, v]) for v in range(1, len(vertices))]
            colors = [(0, 0, 255, 255) for line in lines]

            render_scene = trimesh.scene.Scene()
            render_scene.add_geometry(
                trimesh.path.Path3D(
                    entities=lines, vertices=vertices, process=False, colors=colors
                )
            )
            render_scene.add_geometry(
                SpheroidRegion(position=target_loc, dimensions=(0.1, 0.1, 0.1))
            )
            for i in list(occludingObjects):
                render_scene.add_geometry(i.occupiedSpace.mesh)
            render_scene.show()

        # Check if this ray is within our view cone.
        if not (-viewAngles[0] / 2 <= azimuth <= viewAngles[0] / 2) or not (
            -viewAngles[1] / 2 <= altitude <= viewAngles[1] / 2
        ):
            return False

        # Now check if occluding objects block sight to target
        if orientation is not None:
            candidate_ray_list = orientation.getRotation().apply(candidate_ray_list)

        for occ_obj in occludingObjects:
            # Test all candidate rays against this occluding object
            object_hit_info = occ_obj.occupiedSpace.mesh.ray.intersects_location(
                ray_origins=[position.coordinates for ray in candidate_ray_list],
                ray_directions=candidate_ray_list,
            )

            for hit_iter in range(len(object_hit_info[0])):
                ray = tuple(candidate_ray_list[object_hit_info[1][hit_iter]])
                occ_distance = position.distanceTo(
                    Vector(*object_hit_info[0][hit_iter, :])
                )

                if occ_distance <= target_distance:
                    # The ray is occluded
                    return False

        return True
    else:
        assert False, target
