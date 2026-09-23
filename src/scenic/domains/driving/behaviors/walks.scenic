import collections
import math
import shapely
import itertools
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, MultiLineString, LineString, MultiPoint, Point as ShapelyPoint

import scenic.domains.driving.model as _model
from scenic.core.regions import toShapely
from scenic.core.type_support import toVector
from scenic.domains.driving.actions import *

## Pedestrian Behaviors
def getBugPath(actor, path_ls, backgroundObjects, lookaheadTime, vehBuffer, nonVehBuffer, pathDist):
    """ Refine a walking path using a Bug algorithm approach."""
    assert isinstance(path_ls, LineString)
    self_pt = shapely.force_2d(ShapelyPoint(actor.position))

    # Lambda to compute buffer const.
    baseBuffer = shapely.minimum_bounding_radius(actor._boundingPolygon)
    bufferCalc = lambda obj: baseBuffer + (vehBuffer if obj.isVehicle else nonVehBuffer)

    # Compute the obstacle polygons, accounting for the plan of objects that have already logged it.
    raw_obst_polys = [obj._boundingPolygon.buffer(bufferCalc(obj))
        for obj in backgroundObjects]
    def future_poly_helper(obj):
        planned_path, planned_speed = obj._planData
        otherPlannedDist = planned_speed*lookaheadTime
        if obj._boundingPolygon.distance(self_pt) > pathDist + 2*otherPlannedDist:
            return None
        trimmed_path = shapely.ops.substring(planned_path, 0, otherPlannedDist)
        return trimmed_path.buffer(bufferCalc(obj) + shapely.minimum_bounding_radius(obj._boundingPolygon))
    future_polys = [future_poly_helper(obj) for obj in backgroundObjects
        if not obj.isVehicle and getattr(obj, "_planData", None) is not None]
    future_polys = list(filter(lambda p: p is not None, future_polys))

    obst_multi_poly = shapely.union_all(raw_obst_polys + future_polys)

    if isinstance(obst_multi_poly, MultiPolygon):
        obst_polys = obst_multi_poly.geoms
        assert all(isinstance(geom, Polygon) for geom in obst_polys)
    elif isinstance(obst_multi_poly, Polygon):
        obst_polys = [obst_multi_poly]
    elif obst_multi_poly.is_empty:
        obst_polys = []
    else:
        assert False

    # Drop all obstacles that are not reasonably close
    obst_polys = list(filter(lambda p: p.distance(self_pt) <= pathDist, obst_polys))

    # Refine path around obstacles, going from those with the largest boundary inwards
    # (to account for the rare case where an obstacle poly may be entirely contained in another)
    for obstacle_poly in sorted(obst_polys, key=lambda x: x.boundary.length, reverse=True):
        target_pt = shapely.force_2d(ShapelyPoint(path_ls.coords[-1]))

        # TODO: Better handling so the pedestrian keeps walking towards goal inside a large poly.
        if obstacle_poly.contains(target_pt):
            # Check if target is inside the polygon.
            # If we're too close to the exterior point, return None.
            if obstacle_poly.distance(self_pt) < 0.01:
                return None

            # Otherwise, truncate the path to the closest point on the exterior of the obstacle_poly.
            exterior_intersection = path_ls.intersection(obstacle_poly.exterior)
            stop_pt = shapely.ops.nearest_points(exterior_intersection, self_pt)[0]
            path_ls = shapely.ops.substring(path_ls, 0, path_ls.project(stop_pt, normalized=True), normalized=True)
            continue

        if path_ls.intersects(obstacle_poly):
            # Find intersection points of path with exterior, and extract the first and
            # last with respect to their distance along the path.
            exterior_intersection = path_ls.intersection(obstacle_poly.exterior)
            intersection_points = []

            # If we're inside the obstacle poly, add the closest exterior point to guide us out.
            if obstacle_poly.contains(self_pt):
                intersection_points.append(path_ls.interpolate(path_ls.project(self_pt)))

            if isinstance(exterior_intersection, ShapelyPoint):
                # If we are in the obstacle poly, add the intersection point to help guide us out.
                # Otherwise, our destination is on the border of the poly itself, and we simply should continue.
                if obstacle_poly.contains(self_pt):

                    intersection_points.append(exterior_intersection)
                else:
                    continue
            elif isinstance(exterior_intersection, LineString):
                intersection_points += [
                    ShapelyPoint(exterior_intersection.coords[0]),
                    ShapelyPoint(exterior_intersection.coords[1])
                ]
            elif isinstance(exterior_intersection, (MultiPoint, MultiLineString, GeometryCollection)):
                for geom in exterior_intersection.geoms:
                    if isinstance(geom, ShapelyPoint):
                        intersection_points.append(geom)
                    elif isinstance(geom, LineString):
                        intersection_points += [ShapelyPoint(geom.coords[0]), ShapelyPoint(geom.coords[1])]
            else:
                assert False

            intersection_points.sort(key=lambda x: path_ls.project(x))
            start_pt = intersection_points[0]
            end_pt = intersection_points[-1]

            # Split the exterior ring into two segments at these points
            exterior_ls = LineString(obstacle_poly.exterior)
            start_pt_s = exterior_ls.project(start_pt, normalized=True)
            exterior_ls = LineString(list(shapely.ops.substring(exterior_ls, start_pt_s, 1, normalized=True).coords)
                                     + list(shapely.ops.substring(exterior_ls, 0, start_pt_s, normalized=True).coords))
            exterior_ls = shapely.remove_repeated_points(exterior_ls)
            end_pt_ls = exterior_ls.project(end_pt, normalized=True)
            exterior_segments = [
                shapely.ops.substring(exterior_ls, 0, end_pt_ls, normalized=True),
                shapely.ops.substring(exterior_ls, end_pt_ls, 1, normalized=True)
            ]

            # Patch together the shorter of these exterior segments with the path.
            start_path = shapely.ops.substring(path_ls, 0, path_ls.project(start_pt, normalized=True), normalized=True)
            end_path = shapely.ops.substring(path_ls, path_ls.project(end_pt, normalized=True), 1, normalized=True)
            start_path = shapely.force_2d(start_path)
            end_path = shapely.force_2d(end_path)

            # Extract the mid_path. If paths are very close in length,
            # bias to the right.
            # TODO: Bias to the appropriate driving direction
            if (all(s.length != 0 for s in exterior_segments)
                and 0.95 < exterior_segments[0].length/exterior_segments[1].length < 1.05):
                def angle_helper(ls):
                    return actor.apparentHeadingTo(Vector(*ls.centroid.coords[0]))
                exterior_segments.sort(key=lambda x: angle_helper(x))
            else:
                exterior_segments.sort(key=lambda x: x.length)
            mid_path = exterior_segments[0]
            if isinstance(mid_path, LineString):
                mid_path = shapely.remove_repeated_points(shapely.force_2d(mid_path))

                # Reverse the mid path if needed.
                if (ShapelyPoint(mid_path.coords[0]).distance(start_pt) > ShapelyPoint(mid_path.coords[0]).distance(end_pt)):
                    mid_path = mid_path.reverse()

                # If the closest point on the mid path is very close, cut start path short
                # and aim directly for it. This helps avoid backtracking loop.
                if self_pt.distance(mid_path) < 1:
                    mid_path = shapely.ops.substring(mid_path, mid_path.project(self_pt, normalized=True), 1, normalized=True)
                    start_pt = ShapelyPoint(mid_path.coords[0])
                    start_path = LineString([self_pt, start_pt])
            elif isinstance(mid_path, ShapelyPoint):
                continue
            else:
                assert False, mid_path

            path_ls = LineString(list(start_path.coords) + list(mid_path.coords) + list(end_path.coords))
            path_ls = shapely.remove_repeated_points(path_ls)

    # from scenic.syntax.veneer import simulation
    # if path_ls.intersects(obst_multi_poly.buffer(-0.5)):#simulation().currentRealTime > 8:
    #     import matplotlib.pyplot as plt
    #     plt.gca().set_aspect("equal")
    #     from scenic.core.geometry import plotPolygon
    #     from scenic.syntax.veneer import simulation
    #     simulation().scene.workspace.network.show()
    #     for obj in simulation().objects:
    #         obj.show2D(simulation().scene.workspace, plt)
    #     simulation().scene.workspace.zoomAround(plt, simulation().objects)
    #     plotPolygon(obst_multi_poly, plt, style="c--")
    #     plotPolygon(orig_path_ls, plt, style="y-")
    #     plotPolygon(path_ls, plt, style="g--")
    #     plt.show(block=False)
    #     breakpoint()

    return path_ls

behavior TieBreakingPause():
    take SetWalkingSpeedAction(0)
    wait for Range(0, 0.5) seconds

behavior _WalkPathHelper(path, targetSpeed):
    dist_along = 0
    while True:
        # Determine target point, which will move along the path until we re-plan.
        dist_along += targetSpeed*simulation().timestep
        target_pt = Vector(*path.interpolate(dist_along).coords[0])
        # Set appropriate heading and velocity, calculating actual speed we should aim
        # for, so we don't overshoot if we cut a corner or are at the end of the path.
        actual_speed = min(targetSpeed, (distance from self to target_pt)/simulation().timestep)
        heading = angle from self to target_pt
        take SetWalkingDirectionAction(heading), SetWalkingSpeedAction(actual_speed)

behavior WalkPath(path, targetSpeed, *, avoidObstacles=True,
    terminationThresh=0.1, replanTime=0.5, lookaheadTime=4,
    vehBuffer=1.5, nonVehBuffer=0.2):
    """ Walk a path at targetSpeed, stopping at the end."""
    if not isinstance(path, PolylineRegion):
        raise ValueError("`path` must be a `PolylineRegion`.")

    while distance from self to path.end > terminationThresh:
        path_ls = shapely.force_2d(path.lineString)
        self_pt = (self.position.x, self.position.y)

        # Refine the path by dropping already traversed areas and adding a link to the start.
        start_s = path_ls.project(ShapelyPoint(self_pt), normalized=True)
        path_ls = shapely.ops.substring(path_ls, start_s, 1, normalized=True)
        path_ls =  LineString([self_pt] + list(path_ls.coords))
        path_ls = shapely.remove_repeated_points(path_ls)

        # If our immediate path has us cross through any "dangerous" objects, stop and 
        # wait until it's clear.
        background_objects = [obj for obj in simulation().objects if obj is not self]
        immediate_path = shapely.ops.substring(path_ls, 0, targetSpeed)
        danger_objects = [obj for obj in background_objects if obj.isVehicle and obj.speed > 0.44]
        moving_obj_danger_zone = shapely.union_all(
            [obj._boundingPolygon for obj in danger_objects]
        )
        if immediate_path.intersects(moving_obj_danger_zone):
            do TieBreakingPause()
            continue

        # Modify path to route around objects.
        pathDist = targetSpeed*replanTime*4 # Only path around objects that are reasonably close.
        path_ls = getBugPath(self, path_ls, background_objects, lookaheadTime, vehBuffer, nonVehBuffer, pathDist)
        self._planData = (path_ls, targetSpeed) if path_ls else None

        # If path_ls is None, our goal is inside the danger zone and we can't
        # proceed further right now.
        if path_ls is None:
            do TieBreakingPause()
            continue

        # Follow the path until we replan, terminating early if we reach the end.
        try:
            do _WalkPathHelper(path_ls, targetSpeed) for replanTime seconds
        interrupt when distance from self to Vector(*path_ls.coords[-1]) < terminationThresh:
            take SetWalkingSpeedAction(0)
            abort

        self._planData = None

    take SetWalkingSpeedAction(0)

behavior WalkTo(target, targetSpeed, *, avoidObstacles=True):
    """ Walk towards a given target position at targetSpeed, stopping at the end."""
    path = PolylineRegion(points=(self.position, toVector(target)))
    do WalkPath(path, targetSpeed, avoidObstacles=avoidObstacles)

def pairwise(iterable):
    iterator = iter(iterable)
    a = next(iterator, None)

    for b in iterator:
        yield a, b
        a = b

def noisePath(path, mu, sigma, width, generator, resampleLen=0.5, noiseSampleLen=10):
    if generator is None:
        return path
    
    # Resample the path's points so that the noise is consistently applied.
    numPoints = max(math.ceil(path.length/resampleLen), 2)
    resampleDists = np.linspace(0, path.length, numPoints)
    resampledPoints = [path.pointAlongBy(d) for d in resampleDists]

    # Generate the low frequency noise and map it back onto resampledPoints
    noiseX, noiseY = zip(*[(i*noiseSampleLen, generator.gauss(mu=mu, sigma=sigma)) 
                           for i in range(math.ceil(path.length/noiseSampleLen))])    
    offsets = np.interp(resampleDists, noiseX, noiseY)
    offsetPts = []
    for (pt, next_pt), offset in zip(pairwise(resampledPoints+[None]), offsets):
        if next_pt:
            heading = pt.angleTo(next_pt)
        offsetPts.append(toShapely(pt.offsetRotated(heading, Vector(0.5*width*offset, 0, 0))))

    # if len(resampledPoints) > 4:
    #     print(f"Offset: {mu}")
    #     print(f"Sigma: {sigma}")
    #     from scenic.core.geometry import plotPolygon
    #     import matplotlib.pyplot as plt
    #     plotPolygon(toShapely(path), plt, style="r")
    #     plotPolygon(toShapely(PolylineRegion(polyline=shapely.geometry.LineString(offsetPts))), plt, style="b")
    #     plt.axis('equal')
    #     plt.show()

    return PolylineRegion(polyline=shapely.geometry.LineString(offsetPts))


def appendPath(*geoms):
    return PolylineRegion(
        polyline=shapely.geometry.LineString(
            itertools.chain.from_iterable(geom.lineString.coords for geom in geoms)
        )
    )

behavior Walk(targetSpeed=None, backwards=None,
    avoidObstacles=True, pathHorizon=200,
    relOffsetSigma=0.25, relNoiseSigma=0.05):

    if targetSpeed is None:
        # TODO: Should we move this to a property of pedestrians? (`baseWalkSpeed`?)
        targetSpeed = Range(0.9, 1.8) # From ~2mph to ~4mph

    if backwards is None:
        backwards = Uniform(True, False)

    if relOffsetSigma < 0 or relNoiseSigma < 0:
        raise ValueError("relOffsetSigma and relNoiseSigma must be non-negative.")
    if relOffsetSigma > 0 or relNoiseSigma > 0:
        generator = SeededGenerator()
        relOffset = generator.gauss(mu=0, sigma=relOffsetSigma)
    else:
        generator = None
        offset = 0

    network = _model.network

    # If we're not currently in a walkable region, return to the closest one.
    # Set that element as the first targetElement
    if self.position not in network.walkableRegion:
        closest_pt = network.walkableRegion.closestPointTo(self.position)
        target_element = network.findPointIn(closest_pt, network.walkableRegion, reject=False)
        target_pt = target_element.centerline.project(self.position)
        do WalkTo(target_pt, targetSpeed=targetSpeed, avoidObstacles=avoidObstacles)
        targetElement = network.findPointIn(self.position, network.sidewalks+network.crossings, reject=False)
    else:
        targetElement = network.findPointIn(self.position, network.sidewalks+network.crossings, reject=False)
    assert targetElement is not None

    # Initialize the walking path with the centerline of our target element
    currentPath = targetElement.centerline.reverse() if backwards else targetElement.centerline
    currentPath = noisePath(
        currentPath,
        mu=relOffset,
        sigma=relNoiseSigma,
        width=(distance from targetElement.leftEdge.start to targetElement.rightEdge.start),
        generator=generator,
    )

    # TODO: Have pedestrians bias towards the appropriate side of the sidewalk based off road direction?
    while True:
        ## Trim the path by removing all points before our current projected position
        currentPath = currentPath.substring(
            currentPath.distanceAlong(
                toShapely(self.position),
                normalized=True
            ), 1, normalized=True)

        ## Expand the path till it is at least of length pathHorizon 
        while currentPath.length < pathHorizon:
            # Pick a successor/predecessor to targetElement (depending on whether we are walking `backwards`).
            # TODO: Actually use successor/predecessor information once added.
            nextSidewalk = sorted(
                    [s for s in network.sidewalks if s is not targetElement], 
                    key=lambda x: distance from currentPath.end to x
                )[0]
            if nextSidewalk:
                # If this sidewalk has crossings, then we pick uniformly from the crossings or just walking
                # the length of the sidewalk.
                candidateCrossings = [c for c in nextSidewalk.crossings if c is not targetElement]
                targetCrossing = Uniform(*([None] + candidateCrossings))

                if targetCrossing is None:
                    # Update our target element and direction, and add to our currentPath.
                    targetElement = nextSidewalk
                    backwards = (
                        (distance from targetElement.centerline.end to self) 
                        < (distance from targetElement.centerline.start to self)
                    )
                    currentPath = appendPath(
                        currentPath,
                        noisePath(
                            targetElement.centerline.reverse() if backwards else targetElement.centerline,
                            mu=relOffset,
                            sigma=relNoiseSigma,
                            width=(distance from targetElement.leftEdge.start to targetElement.rightEdge.start),
                            generator=generator,
                        )
                    )
                else:
                    # Walk to the start of the crosswalk
                    sidewalkBackwards = (
                        (distance from nextSidewalk.centerline.end to self) 
                        < (distance from nextSidewalk.centerline.start to self)
                    )
                    intermediatePath = nextSidewalk.centerline.reverse() if sidewalkBackwards else nextSidewalk.centerline
                    intermediatePoint = intermediatePath.closestPointTo(targetCrossing.centerline)
                    intermediatePath = intermediatePath.substring(
                        0,
                        intermediatePath.distanceAlong(intermediatePoint)
                    )
                    currentPath = appendPath(
                        currentPath,
                        noisePath(
                            intermediatePath,
                            mu=relOffset,
                            sigma=relNoiseSigma,
                            width=(distance from nextSidewalk.leftEdge.start to nextSidewalk.rightEdge.start),
                            generator=generator
                        )
                    )

                    # Walk the length of the crosswalk
                    targetElement = targetCrossing
                    backwards = (
                        (distance from targetCrossing.centerline.end to self)
                        < (distance from targetCrossing.centerline.start to self)
                    )
                    currentPath = appendPath(
                        currentPath,
                        noisePath(
                            targetElement.centerline.reverse() if backwards else targetElement.centerline,
                            mu=relOffset,
                            sigma=relNoiseSigma,
                            width=(distance from targetElement.leftEdge.start to targetElement.rightEdge.start),
                            generator=generator
                        )
                    )
            else:
                break

        ## Check if we have reached a dead-end
        if len(currentPath) < 0.1:
            # We have reached the end of the plan, and cannot extend it. Terminate the behavior.
            # TODO: Turn around instead?
            warnings.warn("Walk behavior reached dead end.")
            return

        do WalkPath(currentPath, targetSpeed=targetSpeed, avoidObstacles=avoidObstacles)

# TODO: This uses WalkTowardsAction which doesn't exist.
behavior WalkForwardBehavior():
    """Walk forward behavior for pedestrians.

    It will uniformly randomly choose either end of the sidewalk that
    the pedestrian is on, and have the pedestrian walk towards the endpoint.
    """
    current_sidewalk = _model.network.sidewalkAt(self.position)
    end_point = Uniform(*current_sidewalk.centerline.points)
    end_vec = end_point[0] @ end_point[1]
    normal_vec = Vector.normalized(end_vec)
    take WalkTowardsAction(goal_position=normal_vec), SetSpeedAction(speed=1)
