"""Utility functions for geometric computation."""

import itertools
import math
import warnings

import numpy as np
import shapely.geometry
import shapely.ops

from scenic.core.distributions import (
    distributionFunction,
    monotonicDistributionFunction,
    needsSampling,
)
from scenic.core.lazy_eval import isLazy
from scenic.core.utils import cached_property


@distributionFunction
def sin(x) -> float:
    return math.sin(x)


@distributionFunction
def cos(x) -> float:
    return math.cos(x)


@monotonicDistributionFunction
def hypot(*args) -> float:
    return math.hypot(*args)


@monotonicDistributionFunction
def max(*args, **kwargs):
    return __builtins__["max"](*args, **kwargs)


@monotonicDistributionFunction
def min(*args, **kwargs):
    return __builtins__["min"](*args, **kwargs)


@distributionFunction
def normalizeAngle(angle) -> float:
    """Normalize *angle* (radians) to the half-open interval [−π, π)."""
    return (angle + math.pi) % math.tau - math.pi


def averageVectors(a, b, weight=0.5):
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    aw, bw = 1.0 - weight, weight
    return (ax * aw + bx * bw, ay * aw + by * bw)


def rotateVector(vector, angle):
    x, y = vector
    c, s = cos(angle), sin(angle)
    return ((c * x) - (s * y), (s * x) + (c * y))


def findMinMax(iterable):
    minv = float("inf")
    maxv = float("-inf")
    for val in iterable:
        if val < minv:
            minv = val
        if val > maxv:
            maxv = val
    return (minv, maxv)


def headingOfSegment(pointA, pointB):
    ax, ay = pointA[:2]
    bx, by = pointB[:2]
    return normalizeAngle(math.atan2(by - ay, bx - ax) - (math.pi / 2.0))


def viewAngleToPoint(point, base, heading):
    x, y, _ = base
    ox, oy, _ = point
    a = math.atan2(oy - y, ox - x) - (heading + (math.pi / 2.0))
    return normalizeAngle(a)


def apparentHeadingAtPoint(point, heading, base):
    x, y = base[:2]
    ox, oy = point[:2]
    a = (heading + (math.pi / 2.0)) - math.atan2(oy - y, ox - x)
    return normalizeAngle(a)


def pointIsInCone(point, base, heading, angle):
    va = viewAngleToPoint(point, base, heading)
    return abs(va) <= angle / 2.0


def distanceToLine(point, a, b):
    lx, ly = b[0] - a[0], b[1] - a[1]
    norm = math.hypot(lx, ly)
    nx, ny = -ly / norm, lx / norm
    px, py = point[0] - a[0], point[1] - a[1]
    return abs((px * nx) + (py * ny))


# Fastest known way to make a Shapely Point from a list/tuple/Vector
makeShapelyPoint = shapely.points


def polygonUnion(polys, buf=0, tolerance=0, holeTolerance=0.002):
    if not polys:
        return shapely.geometry.Polygon()
    polys = list(polys)
    if len(polys) == 1:
        return polys[0]
    buffered = [poly.buffer(buf) for poly in polys]
    # remove empty polys to avoid triggering segfault in GEOS 3.10
    # (see https://github.com/Toblerity/Shapely/issues/1230)
    nonempty = [poly for poly in buffered if not poly.is_empty]
    union = shapely.ops.unary_union(nonempty).buffer(-buf)
    assert union.is_valid, union
    if tolerance > 0:
        union = cleanPolygon(union, tolerance, holeTolerance)
        assert union.is_valid, union
    return union


def cleanPolygon(poly, tolerance, holeTolerance=0, minRelArea=0.05, minHullLenRatio=0.9):
    if holeTolerance == 0:
        holeTolerance = tolerance * tolerance
    if poly.is_empty:
        return poly
    elif isinstance(poly, shapely.geometry.MultiPolygon):
        polys = [cleanPolygon(p, tolerance, holeTolerance) for p in poly.geoms]
        total = sum(poly.area for poly in polys)
        kept = []
        for poly in polys:
            area = poly.area
            if area >= holeTolerance or area >= minRelArea * total:
                kept.append(poly)
        poly = shapely.ops.unary_union(kept)
        assert poly.is_valid, poly
        return poly
    exterior = poly.exterior.simplify(tolerance)
    newExterior = cleanChain(exterior.coords, tolerance)
    if len(newExterior) <= 3:
        # attempt to save very thin polygons that would get reduced to a single point
        hull = exterior.convex_hull
        if hull.length >= minHullLenRatio * exterior.length:
            return hull
        return shapely.geometry.Polygon()
    ints = []
    for interior in poly.interiors:
        interior = interior.simplify(tolerance)
        interior = cleanChain(interior.coords, tolerance)
        if len(interior) >= 4:
            hole = shapely.geometry.Polygon(interior)
            if hole.area > holeTolerance:
                ints.append(interior)
    newPoly = shapely.geometry.Polygon(newExterior, ints)
    if not newPoly.is_valid:
        # last-ditch attempt to salvage polygon by splitting across self-intersections
        ext = splitSelfIntersections(
            newPoly.exterior,
            minArea=holeTolerance,
            minRelArea=minRelArea,
            minHullLenRatio=minHullLenRatio,
        )
        holes = [
            splitSelfIntersections(
                hole,
                minArea=holeTolerance,
                minRelArea=minRelArea,
                minHullLenRatio=minHullLenRatio,
            )
            for hole in newPoly.interiors
        ]
        newPoly = ext.difference(shapely.ops.unary_union(holes))
    assert newPoly.is_valid, newPoly
    return newPoly


def splitSelfIntersections(chain, minArea, minRelArea, minHullLenRatio):
    ls = shapely.geometry.LineString(chain)
    parts = list(shapely.ops.polygonize(shapely.ops.unary_union(ls)))
    total = sum(part.area for part in parts)
    if total < minArea:
        # attempt to save very thin polygons that could get thrown out by polygonize
        hull = ls.convex_hull
        if hull.length >= minHullLenRatio * ls.length:
            return hull
    kept = [
        part
        for part in parts
        if part.area >= minArea or (part.area / total) >= minRelArea
    ]
    return shapely.ops.unary_union(kept)


def cleanChain(chain, tolerance=1e-6, lineTolerance=1e-6):
    closed = tuple(chain[0]) == tuple(chain[-1])
    minLength = 4 if closed else 3
    if len(chain) <= minLength:
        return chain
    tol2 = tolerance * tolerance
    # collapse nearby points (since Shapely's simplify method doesn't always do this)
    a = chain[0]
    newChain = [a]
    for b in chain[1:]:
        dx, dy = b[0] - a[0], b[1] - a[1]
        if (dx * dx) + (dy * dy) > tol2:
            newChain.append(b)
            a = b
    if closed:
        b = chain[0]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if (dx * dx) + (dy * dy) <= tol2:
            newChain.pop()
        newChain.append(chain[0])
    if len(newChain) <= minLength:
        if not closed:
            if len(newChain) > 1:
                newChain.pop()
            newChain.append(chain[-1])
        return newChain
    # collapse collinear points
    chain = newChain
    if closed:
        a = chain[-2]
        b = chain[0]
        ci = 1
        newChain = []
    else:
        a = chain[0]
        b = chain[1]
        ci = 2
        newChain = [a]
    for c in chain[ci:]:
        dx, dy = c[0] - a[0], c[1] - a[1]
        if dx == dy == 0 or distanceToLine(b, a, c) > lineTolerance:
            newChain.append(b)
            a = b
            b = c
        else:
            b = c
    newChain.append(c)
    return newChain


def removeHoles(polygon):
    if polygon.is_empty:
        return polygon
    elif isinstance(polygon, shapely.geometry.MultiPolygon):
        polys = (removeHoles(poly) for poly in polygon.geoms)
        poly = shapely.geometry.MultiPolygon(polys)
        assert poly.is_valid, poly
        return poly
    else:
        return shapely.geometry.Polygon(polygon.exterior)


class TriangulationError(RuntimeError):
    """Signals that the installed triangulation libraries are insufficient."""

    pass


def triangulatePolygon(polygon):
    """Triangulate the given Shapely polygon.

    Note that we can't use ``shapely.ops.triangulate`` since it triangulates
    point sets, not polygons (i.e., it doesn't respect edges). We need an
    algorithm for triangulation of polygons with holes (it doesn't need to be a
    Delaunay triangulation).

    Args:
        polygon (shapely.geometry.Polygon): Polygon to triangulate.

    Returns:
        A list of disjoint (except for edges) triangles whose union is the
        original polygon.
    """
    try:
        return triangulatePolygon_mapbox(polygon)
    except ImportError:
        pass
    raise RuntimeError(
        "no triangulation libraries installed " "(did you uninstall mapbox_earcut?)"
    )


def triangulatePolygon_mapbox(polygon):
    import mapbox_earcut

    vertices, rings = [], []
    ring = polygon.exterior.coords[:-1]  # despite 'ring' name, actually need a chain
    vertices.extend(ring)
    rings.append(len(vertices))
    for interior in polygon.interiors:
        ring = interior.coords[:-1]
        vertices.extend(ring)
        rings.append(len(vertices))
    vertices = np.array(vertices, dtype=np.float64)[:, :2]
    rings = np.array(rings)
    result = mapbox_earcut.triangulate_float64(vertices, rings)

    triangles = []
    points = vertices[result]
    coords = np.split(points, len(points) / 3)
    triangles = shapely.polygons(coords)
    return triangles


def allChains(polygon):
    if polygon.is_empty:
        return
    if isinstance(
        polygon,
        (
            shapely.geometry.MultiPolygon,
            shapely.geometry.MultiLineString,
            shapely.geometry.MultiPoint,
            shapely.geometry.collection.GeometryCollection,
        ),
    ):
        polygons = polygon.geoms
    else:
        polygons = [polygon]
    for polygon in polygons:
        if isinstance(polygon, shapely.geometry.Polygon):
            yield polygon.exterior
            for ring in polygon.interiors:
                yield ring
        elif isinstance(
            polygon,
            (
                shapely.geometry.LineString,
                shapely.geometry.LinearRing,
                shapely.geometry.Point,
            ),
        ):
            yield polygon
        else:
            raise RuntimeError(f"unknown kind of shapely geometry {polygon}")


def plotPolygon(polygon, plt, style="r-", **kwargs):
    for chain in allChains(polygon):
        x, y = chain.xy
        plt.plot(x, y, style, **kwargs)
