"""Parser for OpenDRIVE (.xodr) files."""

import abc
from collections import defaultdict
import itertools
import math
import warnings
import xml.etree.ElementTree as ET

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq
from shapely.geometry import GeometryCollection, MultiPoint, MultiPolygon, Point, Polygon
from shapely.ops import snap, unary_union

from scenic.core.geometry import (
    averageVectors,
    cleanChain,
    cleanPolygon,
    plotPolygon,
    polygonUnion,
    removeHoles,
)
from scenic.core.regions import PolygonalRegion, PolylineRegion
from scenic.core.vectors import Vector
from scenic.domains.driving import roads as roadDomain


class OpenDriveWarning(UserWarning):
    pass


def warn(message):
    warnings.warn(message, OpenDriveWarning, stacklevel=2)


def buffer_union(polys, tolerance=0.01):
    return polygonUnion(polys, buf=tolerance, tolerance=tolerance)


def separate(polyA, polyB):
    if not polyA.overlaps(polyB):
        return polyA, polyB

    # Shrink the larger polygon to try to avoid losing fiddly bits
    if polyA.area >= polyB.area:
        polyA = polyA.difference(polyB).buffer(-1e-6)
    else:
        polyB = polyB.difference(polyA).buffer(-1e-6)

    assert not polyA.overlaps(polyB)
    return polyA, polyB


class Poly3:
    """Cubic polynomial."""

    def __init__(self, a, b, c, d):
        self.a = a
        self.b = b
        self.c = c
        self.d = d

    def eval_at(self, x):
        return self.a + self.b * x + self.c * x**2 + self.d * x**3

    def grad_at(self, x):
        return self.b + 2 * self.c * x + 3 * self.d * x**2


class Curve:
    """Geometric elements which compose road reference lines.
    See the OpenDRIVE Format Specification for coordinate system details."""

    def __init__(self, x0, y0, hdg, length):
        self.x0 = x0
        self.y0 = y0
        self.hdg = hdg  # In radians counterclockwise, 0 at positive x-axis.
        self.cos_hdg, self.sin_hdg = math.cos(hdg), math.sin(hdg)
        self.length = length

    def to_points(self, num, extra_points=[]):
        """Sample NUM evenly-spaced points from curve.

        Points are tuples of (x, y, s) with (x, y) absolute coordinates
        and s the arc length along the curve. Additional points at s values in
        extra_points are included if they are contained in the curve (unless
        they are extremely close to one of the equally-spaced points).
        """
        s_vals = []
        extras = itertools.chain(extra_points, itertools.repeat(float("inf")))
        next_extra = next(extras)
        last_s = 0
        for s in np.linspace(0, self.length, num=num):
            while next_extra <= s:
                if last_s + 1e-6 < next_extra < s - 1e-6:
                    s_vals.append(next_extra)
                next_extra = next(extras)
            s_vals.append(s)
            last_s = s
        return [self.point_at(s) for s in s_vals]

    @abc.abstractmethod
    def point_at(self, s):
        """Get an (x, y, s) point along the curve at the given s coordinate."""
        return

    def rel_to_abs(self, point):
        """Convert from relative coordinates of curve to absolute coordinates.
        I.e. rotate counterclockwise by self.hdg and translate by (x0, x1)."""
        x, y, s = point
        return (
            self.x0 + self.cos_hdg * x - self.sin_hdg * y,
            self.y0 + self.sin_hdg * x + self.cos_hdg * y,
            s,
        )


class Cubic(Curve):
    """A curve defined by the cubic polynomial a + bu + cu^2 + du^3.
    The curve starts at (X0, Y0) in direction HDG, with length LENGTH."""

    def __init__(self, x0, y0, hdg, length, a, b, c, d):
        super().__init__(x0, y0, hdg, length)
        self.poly = Poly3(a, b, c, d)
        # Crude upper bound for u (used to bracket u for a given s in point_at)
        if d != 0:
            self.ubound = max(
                2 * abs(c / d), abs(b / d) ** 0.5, (3 * length / abs(d)) ** (1 / 3)
            )
        elif c != 0:
            self.ubound = max(abs(b / c), (2 * length / abs(c)) ** 0.5)
        else:
            self.ubound = length / abs(b)

    def arclength(self, u):
        d_arc = lambda x: np.sqrt(1 + self.poly.grad_at(x) ** 2)
        return quad(d_arc, 0, u)[0]

    def point_at(self, s):
        # Use Brent's method to find parameter u corresponding to arclength s;
        # (N.B. Brent's method proved to be faster than Newton's and has no potential
        # convergence issues.)
        root_func = lambda x: self.arclength(x) - s
        u = float(brentq(root_func, 0, self.ubound))
        pt = (s, self.poly.eval_at(u), s)
        return self.rel_to_abs(pt)


class ParamCubic(Curve):
    """A curve defined by the parametric equations
    u = a_u + b_up + c_up^2 + d_up^3,
    v = a_v + b_vp + c_vp^2 + d_up^3,
    with p in [0, p_range].
    The curve starts at (X0, Y0) in direction HDG, with length LENGTH."""

    def __init__(self, x0, y0, hdg, length, au, bu, cu, du, av, bv, cv, dv, p_range=1):
        super().__init__(x0, y0, hdg, length)
        self.u_poly = Poly3(au, bu, cu, du)
        self.v_poly = Poly3(av, bv, cv, dv)
        self.p_range = p_range

    def arclength(self, p):
        d_arc = lambda x: math.hypot(self.u_poly.grad_at(x), self.v_poly.grad_at(x))
        return quad(d_arc, 0, p)[0]

    def point_at(self, s):
        root_func = lambda x: self.arclength(x) - s
        # we expand the upper bound slightly to ensure a zero is bracketed even
        # with numerical error
        p = float(brentq(root_func, 0, self.p_range + 1e-9))
        p = min(p, self.p_range)
        pt = (self.u_poly.eval_at(p), self.v_poly.eval_at(p), s)
        return self.rel_to_abs(pt)


class Clothoid(Curve):
    """An Euler spiral with curvature varying linearly between CURV0 and CURV1.
    The spiral starts at (X0, Y0) in direction HDG, with length LENGTH."""

    def __init__(self, x0, y0, hdg, length, curv0, curv1):
        super().__init__(x0, y0, hdg, length)
        # Initial and final curvature.
        self.curv0 = curv0
        self.curv1 = curv1
        self.curve_rate = 0 if length == 0 else (curv1 - curv0) / length
        self.a = abs(curv0)
        self.r = 1 / self.a if curv0 != 0 else 1  # value not used if curv0 == 0
        self.ode_init = np.array([x0, y0, hdg])

    def point_at(self, s):
        # Generate a origin-centered clothoid with zero curvature at origin,
        # then translate/rotate the relevant segment.
        # Arcs are just a degenerate clothoid:
        if self.curv0 == self.curv1:
            if self.curv0 == 0:
                pt = (s, 0, s)
            else:
                r = self.r
                th = s * self.a
                if self.curv0 > 0:
                    pt = (r * math.sin(th), r - r * math.cos(th), s)
                else:
                    pt = (r * math.sin(th), -r + r * math.cos(th), s)
            return self.rel_to_abs(pt)
        else:

            def clothoid_ode(s, state):
                x, y, theta = state
                return np.array(
                    [math.cos(theta), math.sin(theta), self.curv0 + (self.curve_rate * s)]
                )

            sol = solve_ivp(clothoid_ode, (0, s), self.ode_init)
            x, y, hdg = sol.y[:, -1]
            return (x, y, s)


class Line(Curve):
    """A line segment between (x0, y0) and (x1, y1)."""

    def __init__(self, x0, y0, hdg, length):
        super().__init__(x0, y0, hdg, length)
        # Endpoints of line.
        self.x1 = x0 + length * math.cos(hdg)
        self.y1 = y0 + length * math.sin(hdg)

    def point_at(self, s):
        return self.rel_to_abs((s, 0, s))


def makeCurve(x0, y0, hdg, length, curve_elem):
    """Create a reference-line curve from an OpenDRIVE geometry element.

    The given length is the effective length Scenic should use, which may
    differ from the length declared in the map if the planView is inconsistent.
    """
    suspicion = None
    if curve_elem.tag == "line":
        curve = Line(x0, y0, hdg, length)
    elif curve_elem.tag == "arc":
        # Arc is clothoid of constant curvature.
        curv = float(curve_elem.get("curvature"))
        curve = Clothoid(x0, y0, hdg, length, curv, curv)
    elif curve_elem.tag == "spiral":
        curv0 = float(curve_elem.get("curvStart"))
        curv1 = float(curve_elem.get("curvEnd"))
        if length and abs(curv0 - curv1) / length > 50:
            suspicion = f"spiral with very high curvature rate (length {length:.3g})"
        curve = Clothoid(x0, y0, hdg, length, curv0, curv1)
    elif curve_elem.tag == "poly3":
        a, b, c, d = (
            float(curve_elem.get("a")),
            float(curve_elem.get("b")),
            float(curve_elem.get("c")),
            float(curve_elem.get("d")),
        )
        curve = Cubic(x0, y0, hdg, length, a, b, c, d)
    elif curve_elem.tag == "paramPoly3":
        au, bu, cu, du, av, bv, cv, dv = (
            float(curve_elem.get("aU")),
            float(curve_elem.get("bU")),
            float(curve_elem.get("cU")),
            float(curve_elem.get("dU")),
            float(curve_elem.get("aV")),
            float(curve_elem.get("bV")),
            float(curve_elem.get("cV")),
            float(curve_elem.get("dV")),
        )
        p_range_attr = curve_elem.get("pRange")
        if p_range_attr == "arcLength":
            p_range = length
        elif p_range_attr in (None, "normalized"):
            p_range = 1
        else:
            raise NotImplementedError(
                f"unsupported pRange for paramPoly3: {p_range_attr}"
            )
        curve = ParamCubic(x0, y0, hdg, length, au, bu, cu, du, av, bv, cv, dv, p_range)
    else:
        raise NotImplementedError(f'unhandled OpenDRIVE geometry type "{curve_elem.tag}"')

    if length < 1e-6:
        suspicion = f"geometry of length {length:.3g}"
    return curve, suspicion


class Lane:
    def __init__(self, id_, type_, pred=None, succ=None):
        self.id_ = id_
        self.width = []  # List of tuples (Poly3, int) for width and s-offset.
        self.type_ = type_
        self.pred = pred
        self.succ = succ
        self.left_bounds = []  # to be filled in later
        self.right_bounds = []
        self.centerline = []
        self.poly = None
        self.parent_lane_poly = None

    def width_at(self, s):
        # S here is relative to start of LaneSection this lane is in.
        ind = 0
        while ind + 1 < len(self.width) and self.width[ind + 1][1] <= s:
            ind += 1
        assert self.width[ind][1] <= s, "No matching width entry found."
        w_poly, s_off = self.width[ind]
        w = w_poly.eval_at(s - s_off)
        if w < -1e-3:  # allow for numerical error
            warn("OpenDRIVE lane has negative width; clamping to zero")
        return max(w, 0)


class LaneSection:
    def __init__(self, s0, left_lanes={}, right_lanes={}):
        self.s0 = s0
        self.left_lanes = left_lanes
        self.right_lanes = right_lanes
        self.left_lane_ids = sorted(self.left_lanes.keys())
        self.right_lane_ids = sorted(self.right_lanes.keys(), reverse=True)
        self.lanes = dict(list(left_lanes.items()) + list(right_lanes.items()))

    def get_lane(self, id_):
        if id_ in self.left_lanes:
            return self.left_lanes[id_]
        elif id_ in self.right_lanes:
            return self.right_lanes[id_]
        elif id_ == 0:
            return Lane(0, "none")
        else:
            raise RuntimeError("Lane with id", id_, "not found")

    def get_offsets(self, s):
        """Returns dict of lane id and offset from
        reference line of lane boundary at coordinate S along line.
        By convention, left lanes have positive width offset and right lanes
        have negative."""
        assert s >= self.s0, "Input s is before lane start position."
        offsets = {}
        for lane_id in self.left_lane_ids:
            if lane_id - 1 in self.left_lane_ids:
                offsets[lane_id] = offsets[lane_id - 1] + self.left_lanes[
                    lane_id
                ].width_at(s - self.s0)
            else:
                offsets[lane_id] = self.left_lanes[lane_id].width_at(s - self.s0)
        for lane_id in self.right_lane_ids:
            if lane_id + 1 in self.right_lane_ids:
                offsets[lane_id] = offsets[lane_id + 1] - self.right_lanes[
                    lane_id
                ].width_at(s - self.s0)
            else:
                offsets[lane_id] = -self.right_lanes[lane_id].width_at(s - self.s0)
        return offsets


class RoadLink:
    """Indicates Roads a and b, with ids id_a and id_b respectively, are connected."""

    def __init__(self, id_a, id_b, contact_a, contact_b):
        self.id_a = id_a
        self.id_b = id_b
        # contact_a and contact_b should be of value "start" or "end"
        # and indicate which end of each road is connected to the other.
        self.contact_a = contact_a
        self.contact_b = contact_b


class Junction:
    class Connection:
        def __init__(self, incoming_id, connecting_id, connecting_contact, lane_links):
            self.incoming_id = incoming_id
            # id of connecting road
            self.connecting_id = connecting_id
            # contact point ('start' or 'end') on connecting road
            self.connecting_contact = connecting_contact
            # dict mapping incoming to connecting lane ids (empty = identity mapping)
            self.lane_links = lane_links

    def __init__(self, id_, name):
        self.id_ = id_
        self.name = name
        self.connections = []
        # Ids of roads that are paths within junction:
        self.paths = []
        self.poly = None

    def add_connection(self, incoming_id, connecting_id, connecting_contact, lane_links):
        conn = Junction.Connection(
            incoming_id, connecting_id, connecting_contact, lane_links
        )
        self.connections.append(conn)


class Road:
    def __init__(self, name, id_, length, junction, drive_on_right=True):
        self.name = name
        self.id_ = id_
        self.length = length
        self.junction = junction if junction != "-1" else None
        self.predecessor = None
        self.successor = None
        self.signals = []  # List of Signal objects.
        self.lane_secs = []  # List of LaneSection objects.
        self.ref_line = []  # List of Curve objects defining reference line.
        # NOTE: sec_points, sec_polys, sec_lane_polys should be ordered according to lane_secs.
        self.sec_points = []  # List of lists of points, one for each LaneSection.
        self.sec_polys = []  # List of Polygons, one for each LaneSections.
        # List of dict of lane id to Polygon for each LaneSection.
        self.sec_lane_polys = []
        # List of lane polygons. Not a dict b/c lane id is not unique along road.
        self.lane_polys = []
        # Each polygon in lane_polys is the union of connected lane section polygons.
        # Reference line offset:
        self.offset = []  # List of tuple (Poly3, s-coordinate).
        self.drive_on_right = drive_on_right
        # Used to fill in gaps between roads:
        self.start_bounds_left = {}
        self.start_bounds_right = {}
        self.end_bounds_left = {}
        self.end_bounds_right = {}

        self.remappedStartLanes = None  # hack for handling spurious initial lane sections

    def get_ref_line_offset(self, s):
        if not self.offset:
            return 0
        ind = 0
        while ind + 1 < len(self.offset) and self.offset[ind + 1][1] <= s:
            ind += 1
        poly, s0 = self.offset[ind]
        assert s >= s0
        return poly.eval_at(s - s0)

    def get_ref_points(self, num):
        """Returns list of list of points for each piece of ref_line.
        List of list structure necessary because each piece needs to be
        constructed into Polygon separately then unioned afterwards to avoid
        self-intersecting lines."""
        ref_points = []
        transition_points = [sec.s0 for sec in self.lane_secs[1:]]
        last_s = 0
        for piece in self.ref_line:
            target_transition_points = [
                s - last_s for s in transition_points if s >= last_s
            ]
            piece_points = piece.to_points(num, extra_points=target_transition_points)
            assert piece_points, "Failed to get piece points"
            piece_points = [(p[0], p[1], p[2] + last_s) for p in piece_points]
            ref_points.append(piece_points)
            last_s = piece_points[-1][2]

        return ref_points

    def heading_at(self, point):
        # Convert point to shapely Point.
        point = Point(point.x, point.y)
        for i in range(len(self.lane_secs)):
            ref_points = self.sec_points[i]
            poly = self.sec_polys[i]
            if point.within(poly.buffer(1)):
                lane_id = None
                for id_ in self.sec_lane_polys[i].keys():
                    if point.within(self.sec_lane_polys[i][id_].buffer(1)):
                        lane_id = id_
                        break
                assert lane_id is not None, "Point not found in sec_lane_polys."
                min_dist = float("inf")
                for i in range(len(ref_points)):
                    cur_point = Point(ref_points[i][0], ref_points[i][1])
                    if point.distance(cur_point) < min_dist:
                        closest_idx = i
                if closest_idx >= len(ref_points) - 1:
                    closest_idx = len(ref_points) - 2
                dy = ref_points[closest_idx + 1][1] - ref_points[closest_idx][1]
                dx = ref_points[closest_idx + 1][0] - ref_points[closest_idx][0]
                heading = math.atan2(dy, dx)
                # Right lanes have negative lane_id.
                # Flip heading if drive_on_right XOR right lane.
                if self.drive_on_right != (lane_id < 0):
                    heading += math.pi
                # Heading 0 is defined differently between OpenDrive and Scenic(?)
                heading -= math.pi / 2
                return (heading + math.pi) % (2 * math.pi) - math.pi

        raise RuntimeError("Point not found in piece_polys")

    def calc_geometry_for_type(self, lane_types, num, tolerance, calc_gap=False):
        """Given a list of lane types, returns a tuple of:
        - List of lists of points along the reference line, with same indexing as self.lane_secs
        - List of region polygons, with same indexing as self.lane_secs
        - List of dictionary of lane id to polygon, with same indexing as self.lane_secs
        - List of polygons for each lane (not necessarily by id, but respecting lane successor/predecessor)
        - Polygon for entire region.
        If calc_gap=True, fills in gaps between connected roads. This is fairly expensive.
        """
        road_polygons = []
        ref_points = self.get_ref_points(num)
        self.ref_line_points = list(itertools.chain.from_iterable(ref_points))
        cur_lane_polys = {}
        sec_points = []
        sec_polys = []
        sec_lane_polys = []
        lane_polys = []
        last_lefts = None
        last_rights = None
        cur_p = None

        for i in range(len(self.lane_secs)):
            cur_sec = self.lane_secs[i]
            cur_sec_points = []
            if i < len(self.lane_secs) - 1:
                next_sec = self.lane_secs[i + 1]
                s_stop = next_sec.s0
            else:
                s_stop = float("inf")
            left_bounds = defaultdict(list)
            right_bounds = defaultdict(list)
            cur_sec_lane_polys = defaultdict(list)
            cur_sec_polys = []
            end_of_sec = False

            while ref_points and not end_of_sec:
                if not ref_points[0]:
                    ref_points.pop(0)
                if not ref_points or (cur_p and cur_p[2] >= s_stop):
                    # Case 1: We have processed the entire reference line.
                    # Case 2: The s-coordinate has exceeded s_stop, so we should move
                    # onto the next LaneSection.
                    # Either way, we collect all the bound points so far into polygons.
                    end_of_sec = True
                    cur_last_lefts = {}
                    cur_last_rights = {}
                    for id_ in left_bounds:
                        # Polygon for piece of lane:
                        left = left_bounds[id_]
                        right = right_bounds[id_][::-1]
                        bounds = left + right

                        if len(bounds) < 3:
                            warn(
                                f"road {self.id_} section {i} lane {id_} is "
                                "entirely zero-width; skipping it"
                            )
                            continue
                        poly = Polygon(bounds)
                        if not poly.is_valid:
                            poly = cleanPolygon(poly, tolerance)
                            if poly.is_empty:
                                warn(
                                    f"could not generate polygon for road {self.id_} "
                                    f"section {i} lane {id_}; skipping it"
                                )
                                continue
                        assert not poly.is_empty
                        if poly.geom_type == "MultiPolygon":
                            poly = MultiPolygon(
                                [p for p in poly.geoms if not p.is_empty and p.exterior]
                            )
                            cur_sec_polys.extend(poly.geoms)
                        else:
                            cur_sec_polys.append(poly)
                        cur_sec_lane_polys[id_].append(poly)
                        cur_last_lefts[id_] = left_bounds[id_][-1]
                        cur_last_rights[id_] = right_bounds[id_][-1]
                        if i == 0 or not self.start_bounds_left:
                            self.start_bounds_left[id_] = left_bounds[id_][0]
                            self.start_bounds_right[id_] = right_bounds[id_][0]

                    left_bounds = defaultdict(list)
                    right_bounds = defaultdict(list)
                    if cur_last_lefts and cur_last_rights:
                        last_lefts = cur_last_lefts
                        last_rights = cur_last_rights
                else:
                    cur_p = ref_points[0][0]
                    cur_sec_points.append(cur_p)
                    s = min(max(cur_p[2], cur_sec.s0), s_stop - 1e-6)
                    offsets = cur_sec.get_offsets(s)
                    offsets[0] = 0
                    for id_ in offsets:
                        offsets[id_] += self.get_ref_line_offset(s)
                    if len(ref_points[0]) > 1:
                        next_p = ref_points[0][1]
                        tan_vec = (next_p[0] - cur_p[0], next_p[1] - cur_p[1])
                    else:
                        if len(cur_sec_points) >= 2:
                            prev_p = cur_sec_points[-2]
                        else:
                            assert len(sec_points) > 0
                            if sec_points[-1]:
                                assert sec_points[-1][-1] == cur_p
                                prev_p = sec_points[-1][-2]
                            else:
                                prev_p = sec_points[-2][-2]

                        tan_vec = (cur_p[0] - prev_p[0], cur_p[1] - prev_p[1])
                    tan_norm = math.hypot(tan_vec[0], tan_vec[1])
                    assert tan_norm > 1e-10
                    normal_vec = (-tan_vec[1] / tan_norm, tan_vec[0] / tan_norm)
                    if cur_p[2] < s_stop:
                        # if at end of section, keep current point to be included in
                        # the next section as well; otherwise remove it
                        ref_points[0].pop(0)
                    elif len(ref_points[0]) == 1 and len(ref_points) > 1:
                        # also get rid of point if this is the last point of the current geometry and
                        # and there is another geometry following
                        ref_points[0].pop(0)
                    for id_ in offsets:
                        lane = cur_sec.get_lane(id_)
                        if lane.type_ in lane_types:
                            if id_ > 0:
                                prev_id = id_ - 1
                            else:
                                prev_id = id_ + 1

                            if (
                                offsets[id_] == offsets[prev_id]
                                and id_ in left_bounds
                                and left_bounds[id_][-1] == right_bounds[id_][-1]
                            ):
                                # Both the previous and current segments of this lane had
                                # zero width; drop the former to avoid invalid polygons
                                warn(
                                    f"road {self.id_} section {i} lane {id_} has a "
                                    "zero-width segment; skipping it"
                                )
                                left_bounds[id_].pop()
                                right_bounds[id_].pop()
                                lane.left_bounds.pop()
                                lane.right_bounds.pop()
                                lane.centerline.pop()
                            left_bound = [
                                cur_p[0] + normal_vec[0] * offsets[id_],
                                cur_p[1] + normal_vec[1] * offsets[id_],
                            ]
                            right_bound = [
                                cur_p[0] + normal_vec[0] * offsets[prev_id],
                                cur_p[1] + normal_vec[1] * offsets[prev_id],
                            ]
                            if id_ < 0:
                                left_bound, right_bound = right_bound, left_bound
                            halfway = (offsets[id_] + offsets[prev_id]) / 2
                            centerline = [
                                cur_p[0] + normal_vec[0] * halfway,
                                cur_p[1] + normal_vec[1] * halfway,
                            ]
                            left_bounds[id_].append(left_bound)
                            right_bounds[id_].append(right_bound)
                            lane.left_bounds.append(left_bound)
                            lane.right_bounds.append(right_bound)
                            lane.centerline.append(centerline)
            assert len(cur_sec_points) >= 2, i
            sec_points.append(cur_sec_points)
            sec_polys.append(buffer_union(cur_sec_polys, tolerance=tolerance))
            for id_ in cur_sec_lane_polys:
                poly = buffer_union(cur_sec_lane_polys[id_], tolerance=tolerance)
                cur_sec_lane_polys[id_] = poly
                cur_sec.get_lane(id_).poly = poly
            sec_lane_polys.append(dict(cur_sec_lane_polys))
            next_lane_polys = {}
            for id_ in cur_sec_lane_polys:
                pred_id = cur_sec.get_lane(id_).pred
                if pred_id and pred_id in cur_lane_polys:
                    next_lane_polys[id_] = cur_lane_polys.pop(pred_id) + [
                        cur_sec_lane_polys[id_]
                    ]
                else:
                    next_lane_polys[id_] = [cur_sec_lane_polys[id_]]
            for id_ in cur_lane_polys:
                poly = buffer_union(cur_lane_polys[id_], tolerance=tolerance)
                self.lane_secs[i - 1].get_lane(id_).parent_lane_poly = len(lane_polys)
                lane_polys.append(poly)
            cur_lane_polys = next_lane_polys
        for id_ in cur_lane_polys:
            poly = buffer_union(cur_lane_polys[id_], tolerance=tolerance)
            cur_sec.get_lane(id_).parent_lane_poly = len(lane_polys)
            lane_polys.append(poly)
        union_poly = buffer_union(sec_polys, tolerance=tolerance)
        if last_lefts and last_rights:
            self.end_bounds_left.update(last_lefts)
            self.end_bounds_right.update(last_rights)

        # Difference and slightly erode all overlapping polygons
        for i in range(len(sec_polys) - 1):
            sec_polys[i], sec_polys[i + 1] = separate(sec_polys[i], sec_polys[i + 1])

        for polys in sec_lane_polys:
            ids = sorted(polys)  # order adjacent lanes consecutively
            for i in range(len(ids) - 1):
                polys[ids[i]], polys[ids[i + 1]] = separate(
                    polys[ids[i]], polys[ids[i + 1]]
                )

        for i in range(len(lane_polys)):
            # TODO do this later when we have lane adjacency information to avoid
            # considering all possible pairs
            for j in range(i):
                lane_polys[i], lane_polys[j] = separate(lane_polys[i], lane_polys[j])

        # Set parent lane polygon references to corrected polygons
        for sec in self.lane_secs:
            for lane in sec.lanes.values():
                parentIndex = lane.parent_lane_poly
                if isinstance(parentIndex, int):
                    lane.parent_lane_poly = lane_polys[parentIndex]

        return (sec_points, sec_polys, sec_lane_polys, lane_polys, union_poly)

    def calculate_geometry(
        self,
        num,
        tolerance,
        calc_gap,
        drivable_lane_types,
        sidewalk_lane_types,
        shoulder_lane_types,
    ):
        # Note: this also calculates self.start_bounds_left, self.start_bounds_right,
        # self.end_bounds_left, self.end_bounds_right
        (
            self.sec_points,
            self.sec_polys,
            self.sec_lane_polys,
            self.lane_polys,
            self.drivable_region,
        ) = self.calc_geometry_for_type(
            drivable_lane_types, num, tolerance, calc_gap=calc_gap
        )

        for i, sec in enumerate(self.lane_secs):
            sec.drivable_lanes = {}
            sec.sidewalk_lanes = {}
            sec.shoulder_lanes = {}
            for id_, lane in sec.lanes.items():
                ty = lane.type_
                if ty in drivable_lane_types:
                    sec.drivable_lanes[id_] = lane
                elif ty in sidewalk_lane_types:
                    sec.sidewalk_lanes[id_] = lane
                elif ty in shoulder_lane_types:
                    sec.shoulder_lanes[id_] = lane
            if not sec.drivable_lanes:
                continue

            rightmost = None
            for id_ in itertools.chain(reversed(sec.right_lane_ids), sec.left_lane_ids):
                if id_ in sec.drivable_lanes:
                    rightmost = sec.lanes[id_]
                    break
            assert rightmost is not None, i
            leftmost = None
            for id_ in itertools.chain(reversed(sec.left_lane_ids), sec.right_lane_ids):
                if id_ in sec.drivable_lanes:
                    leftmost = sec.lanes[id_]
                    break
            assert leftmost is not None, i
            sec.left_edge = leftmost.left_bounds
            assert len(sec.left_edge) >= 2
            sec.right_edge = rightmost.right_bounds
            assert len(sec.right_edge) >= 2

        _, _, _, _, self.sidewalk_region = self.calc_geometry_for_type(
            sidewalk_lane_types, num, tolerance, calc_gap=calc_gap
        )

        _, _, _, _, self.shoulder_region = self.calc_geometry_for_type(
            shoulder_lane_types, num, tolerance, calc_gap=calc_gap
        )

    def toScenicRoad(self, tolerance):
        assert self.sec_points
        allElements = []
        # Create lane and road sections
        roadSections = []
        last_section = None
        forwardSidewalks, backwardSidewalks = [], []
        forwardShoulders, backwardShoulders = [], []
        for sec, pts, sec_poly, lane_polys in zip(
            self.lane_secs, self.sec_points, self.sec_polys, self.sec_lane_polys
        ):
            pts = [pt[:2] for pt in pts]  # drop s coordinate
            assert sec.drivable_lanes
            laneSections = {}
            for id_, lane in sec.drivable_lanes.items():
                succ = None  # will set this later
                if last_section and lane.pred:
                    if lane.pred in last_section.lanesByOpenDriveID:
                        pred = last_section.lanesByOpenDriveID[lane.pred]
                    else:
                        warn(
                            f"road {self.id_} section {len(roadSections)} "
                            f"lane {id_} has a non-drivable predecessor"
                        )
                        pred = None
                else:
                    pred = lane.pred  # will correct inter-road links later
                left, center, right = lane.left_bounds, lane.centerline, lane.right_bounds
                if id_ > 0:  # backward lane
                    left, center, right = right[::-1], center[::-1], left[::-1]
                    succ, pred = pred, succ
                section = roadDomain.LaneSection(
                    id=f"road{self.id_}_sec{len(roadSections)}_lane{id_}",
                    polygon=lane_polys[id_],
                    centerline=PolylineRegion(cleanChain(center)),
                    leftEdge=PolylineRegion(cleanChain(left)),
                    rightEdge=PolylineRegion(cleanChain(right)),
                    successor=succ,
                    predecessor=pred,
                    lane=None,  # will set these later
                    group=None,
                    road=None,
                    openDriveID=id_,
                    isForward=id_ < 0,
                )
                section._original_lane = lane
                laneSections[id_] = section
                allElements.append(section)
            section = roadDomain.RoadSection(
                id=f"road{self.id_}_sec{len(roadSections)}",
                polygon=sec_poly,
                centerline=PolylineRegion(cleanChain(pts)),
                leftEdge=PolylineRegion(cleanChain(sec.left_edge)),
                rightEdge=PolylineRegion(cleanChain(sec.right_edge)),
                successor=None,
                predecessor=last_section,
                road=None,  # will set later
                lanesByOpenDriveID=laneSections,
            )
            roadSections.append(section)
            allElements.append(section)
            last_section = section

            fss, bss = {}, {}
            for id_, lane in sec.sidewalk_lanes.items():
                if lane.poly is None:  # skip if we could not generate polygon
                    continue
                (fss if id_ < 0 else bss)[id_] = lane
            forwardSidewalks.append(fss)
            backwardSidewalks.append(bss)
            fss, bss = {}, {}
            for id_, lane in sec.shoulder_lanes.items():
                if lane.poly is None:
                    continue
                (fss if id_ < 0 else bss)[id_] = lane
            forwardShoulders.append(fss)
            backwardShoulders.append(bss)

        # Build sidewalks and shoulders
        # TODO improve this!
        def combineSections(sections, name, backward):
            leftPoints, rightPoints = [], []
            allPolys = []
            if backward:
                sections = reversed(sections)
            leftSec, rightSec = None, None
            for section in sections:
                if leftSec is None:
                    if not section:
                        continue
                    leftmost, rightmost = max(section), min(section)
                elif backward:
                    leftmost, rightmost = leftSec.pred, rightSec.pred
                else:
                    leftmost, rightmost = leftSec.succ, rightSec.succ
                if not leftmost or not rightmost:
                    break
                if len(section) != leftmost - rightmost + 1:
                    warn(f"ignoring {name} in the middle of road {self.id_}")
                if leftmost not in section or rightmost not in section:
                    # can happen if successor has a different lane type
                    break

                def hasGap(edge1, edge2):
                    gap = np.linalg.norm(np.asarray(edge1) - edge2)
                    if gap < max(tolerance, 0.01):
                        return False
                    warn(f"road {self.id_} has discontinuous {name}; truncating it")
                    return True

                if leftmost < 0:
                    leftmost = rightmost
                    secPolys = [section[leftmost].poly]
                    while leftmost + 1 in section:
                        leftmost = leftmost + 1
                        secPolys.append(section[leftmost].poly)
                    leftSec, rightSec = section[leftmost], section[rightmost]
                    if leftPoints and hasGap(leftPoints[-1], leftSec.left_bounds[0]):
                        break
                    leftPoints.extend(leftSec.left_bounds)
                    rightPoints.extend(rightSec.right_bounds)
                else:
                    rightmost = leftmost
                    secPolys = [section[rightmost].poly]
                    while rightmost - 1 in section:
                        rightmost = rightmost - 1
                        secPolys.append(section[rightmost].poly)
                    leftSec, rightSec = section[leftmost], section[rightmost]
                    if leftPoints and hasGap(leftPoints[-1], rightSec.right_bounds[-1]):
                        break
                    leftPoints.extend(reversed(rightSec.right_bounds))
                    rightPoints.extend(reversed(leftSec.left_bounds))
                allPolys.extend(secPolys)
            assert allPolys
            leftEdge = PolylineRegion(cleanChain(leftPoints))
            rightEdge = PolylineRegion(cleanChain(rightPoints))

            # Heuristically create some kind of reasonable centerline
            if len(leftPoints) == len(rightPoints):
                centerPoints = list(
                    averageVectors(l, r) for l, r in zip(leftPoints, rightPoints)
                )
            else:
                num = max(len(leftPoints), len(rightPoints))
                centerPoints = []
                for d in np.linspace(0, 1, num):
                    l = leftEdge.lineString.interpolate(d, normalized=True)
                    r = rightEdge.lineString.interpolate(d, normalized=True)
                    centerPoints.append(averageVectors(l.coords[0], r.coords[0]))
            centerline = PolylineRegion(cleanChain(centerPoints))
            union = buffer_union(allPolys, tolerance=tolerance)
            direction = "Backward" if backward else "Forward"
            id_ = f"road{self.id_}_{name}{direction}"
            return id_, union, centerline, leftEdge, rightEdge

        def makeSidewalk(sections, backward=False):
            sections = tuple(sections)
            if not any(sections):
                return None
            id_, union, centerline, leftEdge, rightEdge = combineSections(
                sections, "sidewalk", backward
            )
            sidewalk = roadDomain.Sidewalk(
                id=id_,
                polygon=union,
                centerline=centerline,
                leftEdge=leftEdge,
                rightEdge=rightEdge,
                road=None,
                crossings=(),  # TODO add crosswalks
            )
            allElements.append(sidewalk)
            return sidewalk

        forwardSidewalk = makeSidewalk(forwardSidewalks)
        backwardSidewalk = makeSidewalk(backwardSidewalks, backward=True)

        def makeShoulder(sections, backward=False):
            sections = tuple(sections)
            if not any(sections):
                return None
            id_, union, centerline, leftEdge, rightEdge = combineSections(
                sections, "shoulder", backward
            )
            shoulder = roadDomain.Shoulder(
                id=id_,
                polygon=union,
                centerline=centerline,
                leftEdge=leftEdge,
                rightEdge=rightEdge,
                road=None,
            )
            allElements.append(shoulder)
            return shoulder

        forwardShoulder = makeShoulder(forwardShoulders)
        backwardShoulder = makeShoulder(backwardShoulders, backward=True)

        # Connect sections to their successors
        next_section = None
        for sec, section in reversed(list(zip(self.lane_secs, roadSections))):
            if next_section is None:
                next_section = section
                for id_, lane in sec.drivable_lanes.items():
                    newLane = section.lanesByOpenDriveID[id_]
                    if newLane.isForward:
                        # will correct inter-road links later
                        newLane._successor = lane.succ
                    else:
                        newLane._predecessor = lane.succ
                continue
            section._successor = next_section
            for id_, lane in sec.drivable_lanes.items():
                newLane = section.lanesByOpenDriveID[id_]
                if newLane.isForward:
                    newLane._successor = next_section.lanesByOpenDriveID.get(lane.succ)
                else:
                    newLane._predecessor = next_section.lanesByOpenDriveID.get(lane.succ)
            next_section = section

        # Connect lane sections to adjacent lane sections
        for section in roadSections:
            lanes = section.lanesByOpenDriveID
            for id_, lane in lanes.items():
                if id_ < -1:
                    leftID = id_ + 1
                elif id_ == -1:
                    leftID = 1
                elif id_ == 1:
                    leftID = -1
                else:
                    leftID = id_ - 1
                rightID = id_ - 1 if id_ < 0 else id_ + 1
                lane._laneToLeft = lanes.get(leftID)
                lane._laneToRight = lanes.get(rightID)
                if self.drive_on_right:
                    lane._fasterLane = lane._laneToLeft
                    lane._slowerLane = lane._laneToRight
                else:
                    lane._slowerLane = lane._laneToLeft
                    lane._fasterLane = lane._laneToRight
                if lane._fasterLane and lane._fasterLane.isForward != lane.isForward:
                    lane._fasterLane = None
                if lane._slowerLane and lane._slowerLane.isForward != lane.isForward:
                    lane._slowerLane = None
                adj = []
                if lane._laneToLeft:
                    adj.append(lane._laneToLeft)
                if lane._laneToRight:
                    adj.append(lane._laneToRight)
                lane.adjacentLanes = tuple(adj)

        # Gather lane sections into lanes
        nextID = 0
        forwardLanes, backwardLanes = [], []
        for roadSection in roadSections:
            for laneSection in roadSection.lanes:
                laneSection._visited = False
        for roadSection, sec in zip(roadSections, self.lane_secs):
            for laneSection in roadSection.lanes:
                if not laneSection._visited:  # start of new lane
                    forward = laneSection.isForward
                    sections = []
                    successorLane = None  # lane this one will merge into
                    while True:
                        sections.append(laneSection)
                        laneSection._visited = True
                        assert laneSection.isForward == forward
                        if forward:
                            nextSection = laneSection._successor
                        else:
                            nextSection = laneSection._predecessor
                        if not nextSection or not isinstance(
                            nextSection, roadDomain.LaneSection
                        ):
                            break
                        elif nextSection._visited:
                            successorLane = nextSection.lane
                            break
                        laneSection = nextSection
                    ls = laneSection._original_lane
                    assert ls.parent_lane_poly

                    if not forward:
                        sections = tuple(reversed(sections))
                    leftPoints, rightPoints, centerPoints = [], [], []
                    for section in sections:
                        leftPoints.extend(section.leftEdge.points)
                        rightPoints.extend(section.rightEdge.points)
                        centerPoints.extend(section.centerline.points)
                    leftEdge = PolylineRegion(cleanChain(leftPoints))
                    rightEdge = PolylineRegion(cleanChain(rightPoints))
                    centerline = PolylineRegion(cleanChain(centerPoints))
                    lane = roadDomain.Lane(
                        id=f"road{self.id_}_lane{nextID}",
                        polygon=ls.parent_lane_poly,
                        centerline=centerline,
                        leftEdge=leftEdge,
                        rightEdge=rightEdge,
                        group=None,
                        road=None,
                        sections=tuple(sections),
                        successor=successorLane,  # will correct inter-road links later
                    )
                    nextID += 1
                    for section in sections:
                        section.lane = lane
                    (forwardLanes if forward else backwardLanes).append(lane)
                    allElements.append(lane)
        lanes = forwardLanes + backwardLanes
        assert lanes

        # Compute lane adjacencies
        for lane in lanes:
            adj = []
            for section in lane.sections:
                adj.extend(sec.lane for sec in section.adjacentLanes)
            lane.adjacentLanes = tuple(adj)

        # Create lane groups
        def getEdges(forward):
            if forward:
                sec = roadSections[0]
                startLanes = sec.forwardLanes
            else:
                sec = roadSections[-1]
                startLanes = sec.backwardLanes
            leftPoints = []
            current = startLanes[-1]  # get leftmost lane of the first section
            while current and isinstance(current, roadDomain.LaneSection):
                if current._laneToLeft and current._laneToLeft.isForward == forward:
                    current = current._laneToLeft
                leftPoints.extend(current.leftEdge.points)
                current = current._successor
            leftEdge = PolylineRegion(cleanChain(leftPoints))
            rightPoints = []
            current = startLanes[0]  # get rightmost lane of the first section
            while current and isinstance(current, roadDomain.LaneSection):
                if current._laneToRight and current._laneToRight.isForward == forward:
                    current = current._laneToRight
                rightPoints.extend(current.rightEdge.points)
                current = current._successor
            rightEdge = PolylineRegion(cleanChain(rightPoints))
            middleLane = startLanes[len(startLanes) // 2].lane  # rather arbitrary
            return leftEdge, middleLane.centerline, rightEdge

        if forwardLanes:
            leftEdge, centerline, rightEdge = getEdges(forward=True)
            forwardGroup = roadDomain.LaneGroup(
                id=f"road{self.id_}_forward",
                polygon=buffer_union(
                    (lane.polygon for lane in forwardLanes), tolerance=tolerance
                ),
                centerline=centerline,
                leftEdge=leftEdge,
                rightEdge=rightEdge,
                road=None,
                lanes=tuple(forwardLanes),
                curb=(forwardShoulder.rightEdge if forwardShoulder else rightEdge),
                sidewalk=forwardSidewalk,
                bikeLane=None,
                shoulder=forwardShoulder,
                opposite=None,
            )
            allElements.append(forwardGroup)
        else:
            forwardGroup = None
        if backwardLanes:
            leftEdge, centerline, rightEdge = getEdges(forward=False)
            backwardGroup = roadDomain.LaneGroup(
                id=f"road{self.id_}_backward",
                polygon=buffer_union(
                    (lane.polygon for lane in backwardLanes), tolerance=tolerance
                ),
                centerline=centerline,
                leftEdge=leftEdge,
                rightEdge=rightEdge,
                road=None,
                lanes=tuple(backwardLanes),
                curb=(backwardShoulder.rightEdge if backwardShoulder else rightEdge),
                sidewalk=backwardSidewalk,
                bikeLane=None,
                shoulder=backwardShoulder,
                opposite=forwardGroup,
            )
            allElements.append(backwardGroup)
            if forwardGroup:
                forwardGroup._opposite = backwardGroup
        else:
            backwardGroup = None

        # Create signal
        roadSignals = []
        for i, signal_ in enumerate(self.signals):
            signal = roadDomain.Signal(
                uid=f"signal{signal_.id_}_{self.id_}_{i}",
                openDriveID=signal_.id_,
                country=signal_.country,
                type=signal_.type_,
            )
            roadSignals.append(signal)

        # Create road
        assert forwardGroup or backwardGroup
        if forwardGroup:
            rightEdge = forwardGroup.rightEdge
        else:
            rightEdge = backwardGroup.leftEdge
        if backwardGroup:
            leftEdge = backwardGroup.rightEdge
        else:
            leftEdge = forwardGroup.leftEdge
        centerline = PolylineRegion(tuple(pt[:2] for pt in self.ref_line_points))
        road = roadDomain.Road(
            name=self.name,
            uid=f"road{self.id_}",  # need prefix to prevent collisions with intersections
            id=self.id_,
            polygon=self.drivable_region,
            centerline=centerline,
            leftEdge=leftEdge,
            rightEdge=rightEdge,
            lanes=lanes,
            forwardLanes=forwardGroup,
            backwardLanes=backwardGroup,
            sections=roadSections,
            signals=tuple(roadSignals),
            crossings=(),  # TODO add these!
        )
        allElements.append(road)

        # Set up parent references
        if forwardGroup:
            forwardGroup.road = road
            if forwardGroup._sidewalk:
                forwardGroup._sidewalk.road = road
            if forwardGroup._shoulder:
                forwardGroup._shoulder.road = road
                forwardGroup._shoulder.group = forwardGroup
        if backwardGroup:
            backwardGroup.road = road
            if backwardGroup._sidewalk:
                backwardGroup._sidewalk.road = road
            if backwardGroup._shoulder:
                backwardGroup._shoulder.road = road
                backwardGroup._shoulder.group = backwardGroup
        for section in roadSections:
            section.road = road
        for lane in forwardLanes:
            lane.group = forwardGroup
            lane.road = road
            for sec in lane.sections:
                sec.group = forwardGroup
                sec.road = road
                del sec._original_lane
        for lane in backwardLanes:
            lane.group = backwardGroup
            lane.road = road
            for sec in lane.sections:
                sec.group = backwardGroup
                sec.road = road
                del sec._original_lane

        return road, allElements


class Signal:
    """Traffic lights, stop signs, etc."""

    def __init__(self, id_, country, type_, subtype, orientation, validity=None):
        self.id_ = id_
        self.country = country
        self.type_ = type_
        self.subtype = subtype
        self.orientation = orientation
        self.validity = validity

    def is_valid(self):
        return self.validity is None or self.validity != [0, 0]


class SignalReference:
    def __init__(self, id_, orientation, validity=None):
        self.id_ = id_
        self.validity = validity
        self.orientation = orientation

    def is_valid(self):
        return self.validity is None or self.validity != [0, 0]


class RoadMap:
    defaultTolerance = 0.05

    def __init__(
        self,
        tolerance=None,
        fill_intersections=True,
        drivable_lane_types=(
            "driving",
            "entry",
            "exit",
            "offRamp",
            "onRamp",
            "connectingRamp",
        ),
        sidewalk_lane_types=("sidewalk",),
        shoulder_lane_types=("shoulder", "parking", "stop", "border"),
        elide_short_roads=False,
    ):
        self.tolerance = self.defaultTolerance if tolerance is None else tolerance
        self.roads = {}
        self.road_links = []
        self.junctions = {}
        self.sec_lane_polys = []
        self.lane_polys = []
        self.intersection_region = None
        self.fill_intersections = fill_intersections
        self.drivable_lane_types = drivable_lane_types
        self.sidewalk_lane_types = sidewalk_lane_types
        self.shoulder_lane_types = shoulder_lane_types
        self.elide_short_roads = elide_short_roads

    def calculate_geometry(self, num, calc_gap=False, calc_intersect=True):
        # If calc_gap=True, fills in gaps between connected roads.
        # If calc_intersect=True, calculates intersection regions.
        # These are fairly expensive.
        for road in self.roads.values():
            road.calculate_geometry(
                num,
                calc_gap=calc_gap,
                tolerance=self.tolerance,
                drivable_lane_types=self.drivable_lane_types,
                sidewalk_lane_types=self.sidewalk_lane_types,
                shoulder_lane_types=self.shoulder_lane_types,
            )
            self.sec_lane_polys.extend(road.sec_lane_polys)
            self.lane_polys.extend(road.lane_polys)

        if calc_gap:
            drivable_polys = []
            sidewalk_polys = []
            shoulder_polys = []
            for road in self.roads.values():
                drivable_poly = road.drivable_region
                sidewalk_poly = road.sidewalk_region
                shoulder_poly = road.shoulder_region
                if not (drivable_poly is None or drivable_poly.is_empty):
                    drivable_polys.append(drivable_poly)
                if not (sidewalk_poly is None or sidewalk_poly.is_empty):
                    sidewalk_polys.append(sidewalk_poly)
                if not (shoulder_poly is None or shoulder_poly.is_empty):
                    shoulder_polys.append(shoulder_poly)

            for link in self.road_links:
                road_a = self.roads[link.id_a]
                road_b = self.roads[link.id_b]
                assert link.contact_a in ["start", "end"], "Invalid link record."
                assert link.contact_b in ["start", "end"], "Invalid link record."
                if link.contact_a == "start":
                    a_sec = road_a.lane_secs[0]
                    a_bounds_left = road_a.start_bounds_left
                    a_bounds_right = road_a.start_bounds_right
                else:
                    a_sec = road_a.lane_secs[-1]
                    a_bounds_left = road_a.end_bounds_left
                    a_bounds_right = road_a.end_bounds_right
                if link.contact_b == "start":
                    b_bounds_left = road_b.start_bounds_left
                    b_bounds_right = road_b.start_bounds_right
                else:
                    b_bounds_left = road_b.end_bounds_left
                    b_bounds_right = road_b.end_bounds_right

                for id_, lane in a_sec.lanes.items():
                    if link.contact_a == "start":
                        other_id = lane.pred
                    else:
                        other_id = lane.succ
                    if other_id not in b_bounds_left or other_id not in b_bounds_right:
                        continue
                    if id_ not in a_bounds_left or id_ not in a_bounds_right:
                        continue

                    gap_poly = MultiPoint(
                        [
                            a_bounds_left[id_],
                            a_bounds_right[id_],
                            b_bounds_left[other_id],
                            b_bounds_right[other_id],
                        ]
                    ).convex_hull
                    assert gap_poly.is_valid
                    if gap_poly.geom_type == "Polygon" and not gap_poly.is_empty:
                        if lane.type_ in self.drivable_lane_types:
                            drivable_polys.append(gap_poly)
                        elif lane.type_ in self.sidewalk_lane_types:
                            sidewalk_polys.append(gap_poly)
                        elif lane.type_ in self.shoulder_lane_types:
                            shoulder_polys.append(gap_poly)
        else:
            drivable_polys = [road.drivable_region for road in self.roads.values()]
            sidewalk_polys = [road.sidewalk_region for road in self.roads.values()]
            shoulder_polys = [road.shoulder_region for road in self.roads.values()]

        self.drivable_region = buffer_union(drivable_polys, tolerance=self.tolerance)
        self.sidewalk_region = buffer_union(sidewalk_polys, tolerance=self.tolerance)
        self.shoulder_region = buffer_union(shoulder_polys, tolerance=self.tolerance)

        if calc_intersect:
            self.calculate_intersections()

    def calculate_intersections(self):
        intersect_polys = []
        for junc in self.junctions.values():
            junc_polys = [self.roads[i].drivable_region for i in junc.paths]
            assert junc_polys, junc
            union = buffer_union(junc_polys, tolerance=self.tolerance)
            if self.fill_intersections:
                union = removeHoles(union)
            assert union.is_valid
            junc.poly = union
            intersect_polys.append(union)
        self.intersection_region = buffer_union(intersect_polys, tolerance=self.tolerance)

    def heading_at(self, point):
        """Return the road heading at point."""
        # Convert point to shapely Point.
        point = Point(point.x, point.y)
        for road in self.roads.values():
            if point.within(road.drivable_region.buffer(1)):
                return road.heading_at(point)
        # raise RuntimeError('Point not in RoadMap: ', point)
        return 0

    def __parse_lanes(self, lanes_elem):
        """Lanes_elem should be <left> or <right> element.
        Returns dict of lane ids and Lane objects."""
        lanes = {}
        for l in lanes_elem.iter("lane"):
            id_ = int(l.get("id"))
            type_ = l.get("type")
            link = l.find("link")
            pred = None
            succ = None
            if link is not None:
                pred_elem = link.find("predecessor")
                succ_elem = link.find("successor")
                if pred_elem is not None:
                    pred = int(pred_elem.get("id"))
                if succ_elem is not None:
                    succ = int(succ_elem.get("id"))
            lane = Lane(id_, type_, pred, succ)
            for w in l.iter("width"):
                w_poly = Poly3(
                    float(w.get("a")),
                    float(w.get("b")),
                    float(w.get("c")),
                    float(w.get("d")),
                )
                lane.width.append((w_poly, float(w.get("sOffset"))))
            lanes[id_] = lane
        return lanes

    def __parse_link(self, link_elem, road, contact):
        if link_elem is None:
            return
        road_id = road.id_
        if link_elem.get("elementType") == "road":
            id_b = int(link_elem.get("elementId"))
            contact_b = link_elem.get("contactPoint")
            link = RoadLink(road_id, id_b, contact, contact_b)
            self.road_links.append(link)
            return link
        else:
            assert link_elem.get("elementType") == "junction", "Unknown link type"
            junction = int(link_elem.get("elementId"))
            if junction not in self.junctions:
                return  # junction had no connecting roads, so we skipped it
            if contact == "start":
                road.predecessor = junction
            else:
                road.successor = junction
            connections = self.junctions[junction].connections
            for c in connections:
                if c.incoming_id == road_id:
                    self.road_links.append(
                        RoadLink(road_id, c.connecting_id, contact, c.connecting_contact)
                    )

    def __parse_signal_validity(self, validity_elem):
        if validity_elem is None:
            return None
        return [int(validity_elem.get("fromLane")), int(validity_elem.get("toLane"))]

    def __parse_signal(self, signal_elem):
        return Signal(
            signal_elem.get("id"),
            signal_elem.get("country"),
            signal_elem.get("type"),
            signal_elem.get("subtype"),
            signal_elem.get("orientation"),
            self.__parse_signal_validity(signal_elem.find("validity")),
        )

    def __parse_signal_reference(self, signal_reference_elem):
        return SignalReference(
            signal_reference_elem.get("id"),
            signal_reference_elem.get("orientation"),
            self.__parse_signal_validity(signal_reference_elem.find("validity")),
        )

    def parse(self, path):
        tree = ET.parse(path)
        root = tree.getroot()
        if root.tag != "OpenDRIVE":
            raise ValueError(f"{path} does not appear to be an OpenDRIVE file")

        # parse junctions
        for j in root.iter("junction"):
            junction = Junction(int(j.get("id")), j.get("name"))
            for c in j.iter("connection"):
                ty = c.get("type", "default")
                if ty != "default":
                    raise NotImplementedError(
                        f'unhandled "{ty}" type of junction connection'
                    )
                lane_links = {}
                for l in c.iter("laneLink"):
                    lane_links[int(l.get("from"))] = int(l.get("to"))
                junction.add_connection(
                    int(c.get("incomingRoad")),
                    int(c.get("connectingRoad")),
                    c.get("contactPoint"),
                    lane_links,
                )
                junction.paths.append(int(c.get("connectingRoad")))
            if not junction.paths:
                warn(f"junction {junction.id_} has no connecting roads; skipping it")
                continue
            self.junctions[junction.id_] = junction

        # Creating temporal signals container to resolve referenced signals.
        _temp_signals = {}
        for r in root.iter("road"):
            signals = r.find("signals")
            if signals is not None:
                for s in signals.iter("signal"):
                    signal = self.__parse_signal(s)
                    _temp_signals[signal.id_] = signal

        # parse roads
        self.elidedRoads = {}
        for r in root.iter("road"):
            road = Road(
                r.get("name"), int(r.get("id")), float(r.get("length")), r.get("junction")
            )
            link = r.find("link")
            if link is not None:
                pred_elem = link.find("predecessor")
                succ_elem = link.find("successor")
                pred_link = self.__parse_link(pred_elem, road, "start")
                succ_link = self.__parse_link(succ_elem, road, "end")
            else:
                pred_link = succ_link = None

            if road.length < self.tolerance:
                warn(
                    f"road {road.id_} has length shorter than tolerance;"
                    " geometry may contain artifacts"
                )
                if self.elide_short_roads:
                    warn(f"attempting to elide road {road.id_} of length {road.length}")
                    assert road.junction is None
                    self.elidedRoads[road.id_] = road
                    if pred_link:
                        road.predecessor = pred_link.id_b
                        road.predecessorContact = pred_link.contact_b
                    else:
                        road.predecessorContact = None
                    if succ_link:
                        road.successor = succ_link.id_b
                        road.successorContact = succ_link.contact_b
                    else:
                        road.successorContact = None
                    continue

            # Parse planView:
            plan_view = r.find("planView")
            curveData = []
            for geom in plan_view.iter("geometry"):
                x0 = float(geom.get("x"))
                y0 = float(geom.get("y"))
                s0 = float(geom.get("s"))
                hdg = float(geom.get("hdg"))
                length = float(geom.get("length"))
                curve_elem = geom[0]
                curveData.append((s0, x0, y0, hdg, length, curve_elem))

            if not curveData:
                raise ValueError(f"road {road.id_} has an empty planView")
            if not curveData[0][0] == 0:
                raise ValueError(
                    f"reference line of road {road.id_} does not start at s=0"
                )

            refLine, suspectGeometries = [], []
            for i, (s0, x0, y0, hdg, length, curve_elem) in enumerate(curveData):
                if i + 1 < len(curveData):
                    nextS0 = curveData[i + 1][0]
                    l = nextS0 - s0

                    if l < 0:
                        raise ValueError(f"planView of road {road.id_} is not in order")

                    if abs(length - l) > 1e-3:
                        warn(
                            f"planView of road {road.id_} has inconsistent length: "
                            f"geometry at s={s0} has declared length {length}, "
                            f"but the next geometry starts at s={nextS0}; "
                            f"using length {l}"
                        )
                        length = l

                curve, suspicion = makeCurve(x0, y0, hdg, length, curve_elem)
                if suspicion:
                    suspectGeometries.append((curve, suspicion, length))
                else:
                    refLine.append(curve)

            exonerated = None
            if not refLine:
                # All geometries were suspect, so we need to keep at least one of them.
                # We'll heuristically keep whichever is longest and drop the rest.
                # (Extremely short roads can be removed entirely by road elision above.)
                exonerated = max(suspectGeometries, key=lambda t: t[2])[0]
                refLine.append(exonerated)
            for curve, suspicion, _ in suspectGeometries:
                note = "" if curve is exonerated else "; skipping it"
                warn(f"road {road.id_} reference line has a {suspicion}{note}")

            assert refLine
            road.ref_line = refLine

            # Parse lanes:
            lanes = r.find("lanes")
            for offset in lanes.iter("laneOffset"):
                road.offset.append(
                    (
                        Poly3(
                            float(offset.get("a")),
                            float(offset.get("b")),
                            float(offset.get("c")),
                            float(offset.get("d")),
                        ),
                        float(offset.get("s")),
                    )
                )

            def popLastSectionIfShort(l):
                if l < 1e-6:
                    warn(f"road {road.id_} has a lane section of length {l}; skipping it")

                    # delete the length-0 section and re-link lanes appropriately
                    badSec = road.lane_secs.pop()
                    if road.lane_secs:
                        prev = road.lane_secs[-1]
                        for id_, lane in prev.lanes.items():
                            if lane.succ is not None:
                                lane.succ = badSec.lanes[lane.succ].succ
                    else:
                        if road.remappedStartLanes is None:
                            road.remappedStartLanes = {l: l for l in badSec.lanes}
                        for start, current in road.remappedStartLanes.items():
                            road.remappedStartLanes[start] = badSec.lanes[current].succ
                    return badSec
                else:
                    return None

            last_s = float("-inf")
            for ls_elem in lanes.iter("laneSection"):
                s = float(ls_elem.get("s"))
                l = s - last_s
                assert l >= 0
                badSec = popLastSectionIfShort(l)

                last_s = s
                left = ls_elem.find("left")
                right = ls_elem.find("right")
                left_lanes = {}
                right_lanes = {}

                if left is not None:
                    left_lanes = self.__parse_lanes(left)

                if right is not None:
                    right_lanes = self.__parse_lanes(right)

                lane_sec = LaneSection(s, left_lanes, right_lanes)

                if badSec is not None:  # finish re-linking lanes across deleted section
                    for id_, lane in lane_sec.lanes.items():
                        if lane.pred is not None:
                            lane.pred = badSec.lanes[lane.pred].pred

                road.lane_secs.append(lane_sec)

            # parse signals
            signals = r.find("signals")
            if signals is not None:
                for signal_elem in signals.iter("signal"):
                    signal = self.__parse_signal(signal_elem)
                    if signal.is_valid():
                        road.signals.append(signal)

                for signal_ref_elem in signals.iter("signalReference"):
                    signalReference = self.__parse_signal_reference(signal_ref_elem)
                    if signalReference.is_valid():
                        referencedSignal = _temp_signals[signalReference.id_]
                        signal = Signal(
                            referencedSignal.id_,
                            referencedSignal.country,
                            referencedSignal.type_,
                            referencedSignal.subtype,
                            signalReference.orientation,
                            signalReference.validity,
                        )
                        road.signals.append(signal)

            if len(road.lane_secs) > 1:
                popLastSectionIfShort(road.length - s)
            assert road.lane_secs
            self.roads[road.id_] = road

        # Handle links to/from elided roads
        new_links = []
        for link in self.road_links:
            if link.id_a in self.elidedRoads:
                continue
            if link.id_b in self.elidedRoads:
                elided = self.elidedRoads[link.id_b]
                if link.contact_b == "start":
                    link.id_b = elided.successor
                    link.contact_b = elided.successorContact
                else:
                    link.id_b = elided.predecessor
                    link.contact_b = elided.predecessorContact
                if link.contact_b is None:
                    continue  # link to intersection
            new_links.append(link)
        self.road_links = new_links

    def toScenicNetwork(self):
        assert self.intersection_region is not None

        # Prepare registry of network elements
        allElements = {}

        def register(element):
            assert element.uid is not None
            assert element.uid not in allElements, element.uid
            allElements[element.uid] = element

        def registerAll(elements):
            for elt in elements:
                register(elt)

        # Convert roads
        mainRoads, connectingRoads, roads = {}, {}, {}
        for id_, road in self.roads.items():
            if road.drivable_region.is_empty:
                continue  # not actually a road you can drive on
            newRoad, elts = road.toScenicRoad(tolerance=self.tolerance)
            registerAll(elts)
            (connectingRoads if road.junction else mainRoads)[id_] = newRoad
            roads[id_] = newRoad

        # Hook up inter-road links
        for link in self.road_links:
            if link.id_b in connectingRoads:
                continue  # actually a road-to-junction link; handled later
            if link.id_a not in roads or link.id_b not in roads:
                continue  # may link non-drivable roads we haven't parsed; ignore it

            # Work out connectivity of roads and adjacent sections
            roadA, roadB = roads[link.id_a], roads[link.id_b]
            if link.contact_a == "start":
                secA = roadA.sections[0]
                roadA._predecessor = roadB
                forwardA = True
            else:
                secA = roadA.sections[-1]
                roadA._successor = roadB
                forwardA = False
            if link.contact_b == "start":
                secB = roadB.sections[0]
            else:
                secB = roadB.sections[-1]

            # Connect corresponding lanes
            lanesB = secB.lanesByOpenDriveID
            for laneA in secA.lanes:
                if laneA.isForward == forwardA:
                    pred = laneA._predecessor
                    if pred is None:
                        continue
                    assert pred in lanesB
                    laneB = lanesB[pred]
                    laneA._predecessor = laneB
                    laneA.lane._predecessor = laneB.lane
                    laneA.lane.group._predecessor = laneB.lane.group
                else:
                    succ = laneA._successor
                    if succ is None:
                        continue
                    assert succ in lanesB
                    laneB = lanesB[succ]
                    laneA._successor = laneB
                    laneA.lane._successor = laneB.lane
                    laneA.lane.group._successor = laneB.lane.group

        # Hook up connecting road links and create intersections
        intersections = {}
        for jid, junction in self.junctions.items():
            if not junction.connections:
                continue
            assert junction.poly is not None
            if junction.poly.is_empty:
                warn(f"skipping empty junction {jid}")
                continue

            # Gather all lanes involved in the junction's connections
            allIncomingLanes, allOutgoingLanes = [], []
            allRoads, seenRoads = [], set()
            allSignals, seenSignals = [], set()
            maneuversForLane = defaultdict(list)
            for connection in junction.connections:
                incomingID = connection.incoming_id
                incomingRoad = mainRoads.get(incomingID)
                if not incomingRoad:
                    continue  # incoming road has no drivable lanes; skip it

                connectingID = connection.connecting_id
                connectingRoad = connectingRoads.get(connectingID)
                if not connectingRoad:
                    continue  # connecting road has no drivable lanes; skip it

                for signal in connectingRoad.signals:
                    if signal.openDriveID not in seenSignals:
                        allSignals.append(signal)
                        seenSignals.add(signal.openDriveID)

                # Find possible incoming lanes for this connection
                if incomingID not in seenRoads:
                    allRoads.append(incomingRoad)
                    seenRoads.add(incomingID)
                oldRoad = self.roads[incomingID]
                incomingSection = None
                if oldRoad.predecessor == jid:
                    incomingSection = incomingRoad.sections[0]
                    remapping = self.roads[incomingID].remappedStartLanes  # could be None
                if oldRoad.successor == jid:
                    assert incomingSection is None
                    incomingSection = incomingRoad.sections[-1]
                    remapping = None
                assert incomingSection is not None
                if remapping is None:
                    incomingLaneIDs = incomingSection.lanesByOpenDriveID
                else:
                    incomingLaneIDs = {}
                    newIDs = incomingSection.lanesByOpenDriveID
                    for start, remapped in remapping.items():
                        if remapped in newIDs:
                            incomingLaneIDs[start] = newIDs[remapped]
                    assert len(incomingLaneIDs) == len(newIDs)

                # Connect incoming lanes to connecting road
                if connection.connecting_contact == "start":
                    connectingSection = connectingRoad.sections[0]
                    remapping = self.roads[
                        connectingID
                    ].remappedStartLanes  # could be None
                else:
                    connectingSection = connectingRoad.sections[-1]
                    remapping = None
                if remapping is None:
                    connectingLaneIDs = connectingSection.lanesByOpenDriveID
                else:
                    connectingLaneIDs = {}
                    newIDs = connectingSection.lanesByOpenDriveID
                    for start, remapped in remapping.items():
                        if remapped in newIDs:
                            connectingLaneIDs[start] = newIDs[remapped]
                    assert len(connectingLaneIDs) == len(newIDs)
                lane_links = connection.lane_links
                if not lane_links:  # all lanes connect to that with the same id
                    lane_links = {l: l for l in incomingLaneIDs}
                for fromID, fromLane in incomingLaneIDs.items():
                    # Link incoming lane to connecting road
                    # (we only handle lanes in incomingLaneIDs, thus skipping non-drivable lanes)
                    if fromID not in lane_links:
                        continue  # lane not linked by this connection
                    toID = lane_links[fromID]
                    toLane = connectingLaneIDs[toID]
                    if fromLane.lane not in allIncomingLanes:
                        allIncomingLanes.append(fromLane.lane)
                    fromLane._successor = toLane
                    fromLane.lane._successor = toLane.lane
                    toLane._predecessor = fromLane
                    toLane.lane._predecessor = fromLane.lane

                    # Collect outgoing lane and road
                    # TODO why is it allowed for this not to exist?
                    outgoingLane = toLane.lane._successor
                    if outgoingLane is None:
                        warn(
                            f"connecting road {connectingID} lane {toID} has no successor lane"
                        )
                    else:
                        if outgoingLane not in allOutgoingLanes:
                            allOutgoingLanes.append(outgoingLane)
                        outgoingRoad = outgoingLane.road
                        if outgoingRoad.id not in seenRoads:
                            allRoads.append(outgoingRoad)
                            seenRoads.add(outgoingRoad.id)

                        # TODO future OpenDRIVE extension annotating left/right turns?
                        maneuver = roadDomain.Maneuver(
                            startLane=fromLane.lane,
                            connectingLane=toLane.lane,
                            endLane=outgoingLane,
                            intersection=None,  # will be patched once the Intersection is created
                        )
                        maneuversForLane[fromLane.lane].append(maneuver)

            # Gather maneuvers
            allManeuvers = []
            for lane, maneuvers in maneuversForLane.items():
                assert lane.maneuvers == ()
                lane.maneuvers = tuple(maneuvers)
                allManeuvers.extend(maneuvers)

            # Order connected roads and lanes by adjacency
            def cyclicOrder(elements, contactStart=None):
                points = []
                for element in elements:
                    if contactStart is None:
                        old = self.roads[element.id]
                        assert old.predecessor == jid or old.successor == jid
                        contactStart = old.predecessor == jid
                    point = element.centerline[0 if contactStart else -1]
                    points.append(point)
                centroid = sum(points, Vector(0, 0)) / len(points)
                pairs = sorted(
                    zip(elements, points), key=lambda pair: centroid.angleTo(pair[1])
                )
                return tuple(elem for elem, pt in pairs)

            # Create intersection
            intersection = roadDomain.Intersection(
                polygon=junction.poly,
                name=junction.name,
                uid=f"intersection{jid}",  # need prefix to prevent collisions with roads
                id=jid,
                roads=cyclicOrder(allRoads),
                incomingLanes=cyclicOrder(allIncomingLanes, contactStart=False),
                outgoingLanes=cyclicOrder(allOutgoingLanes, contactStart=True),
                maneuvers=tuple(allManeuvers),
                signals=tuple(allSignals),
                crossings=(),  # TODO add these
            )
            register(intersection)
            intersections[jid] = intersection
            for maneuver in allManeuvers:
                object.__setattr__(maneuver, "intersection", intersection)

        # Hook up road-intersection links
        for rid, oldRoad in self.roads.items():
            if rid not in roads:
                continue  # road does not have any drivable lanes, so we skipped it
            newRoad = roads[rid]
            if (pred := oldRoad.predecessor) and pred in intersections:
                intersection = intersections[pred]
                newRoad._predecessor = intersection
                newRoad.sections[0]._predecessor = intersection
                if newRoad.backwardLanes:
                    newRoad.backwardLanes._successor = intersection
            if (succ := oldRoad.successor) and succ in intersections:
                intersection = intersections[succ]
                newRoad._successor = intersection
                newRoad.sections[-1]._successor = intersection
                if newRoad.forwardLanes:
                    newRoad.forwardLanes._successor = intersection

        # Gather all network elements
        roads = tuple(mainRoads.values())
        connectingRoads = tuple(connectingRoads.values())
        allRoads = roads + connectingRoads
        groups = []
        for road in allRoads:
            if road.forwardLanes:
                groups.append(road.forwardLanes)
            if road.backwardLanes:
                groups.append(road.backwardLanes)
        lanes = [lane for road in allRoads for lane in road.lanes]
        intersections = tuple(intersections.values())
        crossings = ()  # TODO add these
        sidewalks, shoulders = [], []
        for group in groups:
            sidewalk = group._sidewalk
            if sidewalk:
                sidewalks.append(sidewalk)
            shoulder = group._shoulder
            if shoulder:
                shoulders.append(shoulder)

        # Add dummy maneuvers for lanes which merge/turn into another lane
        for lane in lanes:
            if not lane.maneuvers and lane._successor:
                maneuver = roadDomain.Maneuver(
                    type=roadDomain.ManeuverType.STRAIGHT,
                    startLane=lane,
                    endLane=lane._successor,
                )
                lane.maneuvers = (maneuver,)

        def combine(regions):
            return PolygonalRegion.unionAll(regions, buf=self.tolerance)

        return roadDomain.Network(
            elements=allElements,
            roads=roads,
            connectingRoads=connectingRoads,
            laneGroups=tuple(groups),
            lanes=lanes,
            intersections=intersections,
            crossings=crossings,
            sidewalks=tuple(sidewalks),
            shoulders=tuple(shoulders),
            tolerance=self.tolerance,
            roadRegion=combine(roads),
            laneRegion=combine(lanes),
            intersectionRegion=combine(intersections),
            crossingRegion=combine(crossings),
            sidewalkRegion=combine(sidewalks),
        )
