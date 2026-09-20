"""Library for representing road network geometry and traffic information.

A road network is represented by an instance of the :obj:`Network` class, which can
be created from a map file using :obj:`Network.fromFile`.

.. note::

    This library is a prototype under active development. We will try not to make
    backwards-incompatible changes, but the API may not be entirely stable.
"""

from __future__ import annotations  # allow forward references for type annotations

import bisect
import enum
import gzip
import hashlib
import io
import itertools
import math
import numbers
import pathlib
import pickle
import struct
import time
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple, Union
import warnings
import weakref

import attr
import shapely
from shapely.geometry import MultiPolygon, Point as ShapelyPoint, Polygon

from scenic.core.distributions import (
    RejectionException,
    distributionFunction,
    distributionMethod,
)
import scenic.core.geometry as geometry
from scenic.core.object_types import Point
from scenic.core.regions import PolygonalRegion, PolylineRegion
from scenic.core.serialization import deterministicHash
import scenic.core.type_support as type_support
import scenic.core.utils as utils
from scenic.core.vectors import Orientation, Vector, VectorField
import scenic.syntax.veneer as veneer
from scenic.syntax.veneer import verbosePrint

## Typing and utilities

#: Alias for types which can be interpreted as positions in Scenic.
#:
#: This includes instances of `Point` and `Object`, and pairs of numbers.
Vectorlike = Union[Vector, Point, Tuple[numbers.Real, numbers.Real]]


def _toVector(thing: Vectorlike) -> Vector:
    return type_support.toVector(thing)


def _rejectIfNonexistent(element, name="network element"):
    if element is None:
        raise RejectionException(f"requested {name} does not exist")
    return element


class _ElementReferencer:
    """Mixin class to improve pickling of classes that reference network elements.

    :meta private:
    """

    def __getstate__(self):
        if hasattr(super(), "__getstate__"):
            state = super().__getstate__()
            if state is self.__dict__:
                state = state.copy()
        else:
            state = self.__dict__.copy()
        # replace links to network elements by placeholders to prevent deep
        # recursions during pickling; as a result of this, only entire `Network`
        # objects can be properly unpickled
        for key, value in state.items():
            if isinstance(value, NetworkElement):
                state[key] = _ElementPlaceholder(value.uid)
        return state


class _ElementPlaceholder:
    """Placeholder for a link to a pickled `NetworkElement`.

    :meta private:
    """

    def __init__(self, uid):
        self.uid = uid


## Metadata


@enum.unique
class VehicleType(enum.Enum):
    """A type of vehicle, including pedestrians. Used to classify lanes."""

    CAR = 1
    BICYCLE = 2
    PEDESTRIAN = 3


@enum.unique
class ManeuverType(enum.Enum):
    """A type of `Maneuver`, e.g., going straight or turning left."""

    STRAIGHT = enum.auto()  #: Straight, including one lane merging into another.
    LEFT_TURN = enum.auto()  #: Left turn.
    RIGHT_TURN = enum.auto()  #: Right turn.
    U_TURN = enum.auto()  #: U-turn.

    @staticmethod
    def guessTypeFromLanes(
        start: Lane,
        end: Lane,
        connecting: Union[Lane, None],
        turnThreshold: float = math.radians(20),
    ):
        """For formats lacking turn information, guess it from the geometry.

        Arguments:
            start: starting lane of the maneuver.
            end: ending lane of the maneuver.
            connecting: connecting lane of the maneuver, if any.
            turnThreshold: angle beyond which to consider a maneuver a turn.
        """
        if connecting is None:
            return ManeuverType.STRAIGHT
        if end.road is start.road:
            return ManeuverType.U_TURN

        # Identify turns based on relative heading of start and end of connecting lane
        startDir = connecting.centerline[1] - connecting.centerline[0]
        endDir = connecting.centerline[-1] - connecting.centerline[-2]
        turnAngle = startDir.angleWith(endDir)
        if turnAngle >= turnThreshold:
            return ManeuverType.LEFT_TURN
        elif turnAngle <= -turnThreshold:
            return ManeuverType.RIGHT_TURN
        else:
            return ManeuverType.STRAIGHT


@enum.unique
class SignalTag(enum.Enum):
    """Known control tags for a `Signal`.

    Meanings are Scenic's, so another map format can reuse the same tags.
    Unrecognized source literals are stored on `Signal.otherTags`.
    """

    STOP = "stop"  #: Come to a complete stop, then proceed only when the way is clear.
    FOUR_WAY = "fourWay"  #: All-way stop: every approach must halt.
    YIELD = "yield"  #: Give way to conflicting traffic; stop only if needed.
    TRAFFIC_LIGHT = "trafficLight"
    #: Signalized control; whether to proceed depends on the current indication.
    TURN_ON_RED_ALLOWED = "turnOnRedAllowed"  #: Turning on red is permitted.
    NO_TURN_ON_RED = "noTurnOnRed"  #: Turning on red is forbidden.


@attr.s(auto_attribs=True, kw_only=True, eq=False)
class Maneuver(_ElementReferencer):
    """Maneuver()

    A maneuver which can be taken upon reaching the end of a lane.
    """

    type: ManeuverType = None  #: type of maneuver (straight, left turn, etc.)
    startLane: Lane  #: starting lane of the maneuver
    endLane: Lane  #: ending lane of the maneuver

    # the following attributes are None if startLane directly merges into endLane,
    # rather than connecting via a maneuver through an intersection

    #: connecting lane from the start to the end lane, if any (`None` for lane mergers)
    connectingLane: Union[Lane, None] = None
    #: intersection where the maneuver takes place, if any (`None` for lane mergers)
    intersection: Union[Intersection, None] = None
    #: traffic signal controlling this maneuver, if any (`None` if uncontrolled or unknown)
    signal: Optional[Signal] = None

    def __attrs_post_init__(self):
        assert self.type is ManeuverType.STRAIGHT or self.connectingLane is not None

        if self.type is None:  # unknown maneuver type; need to guess from geometry
            ty = ManeuverType.guessTypeFromLanes(
                self.startLane, self.endLane, self.connectingLane
            )
            object.__setattr__(self, "type", ty)

    @property
    @utils.cached
    def conflictingManeuvers(self) -> Tuple[Maneuver]:
        """Maneuvers whose connecting lanes intersect this one's."""
        if not self.connectingLane:
            return ()
        guideway = self.connectingLane
        start = self.startLane
        conflicts = []
        for maneuver in self.intersection.maneuvers:
            if (
                maneuver.startLane is not start
                and maneuver.connectingLane.centerline.intersects(guideway.centerline)
            ):
                conflicts.append(maneuver)
        return tuple(conflicts)

    @property
    @utils.cached
    def reverseManeuvers(self) -> Tuple[Maneuver]:
        """Maneuvers whose start and end roads are the reverse of this one's."""
        start = self.startLane.road
        end = self.endLane.road
        reverses = []
        for maneuver in self.intersection.maneuvers:
            if maneuver.startLane.road is end and maneuver.endLane.road is start:
                reverses.append(maneuver)
        return tuple(reverses)


## Road networks


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class NetworkElement(_ElementReferencer, PolygonalRegion):
    """NetworkElement()

    Abstract class for part of a road network.

    Includes roads, lane groups, lanes, sidewalks, pedestrian crossings,
    and intersections.

    This is a subclass of `Region`, so you can do things like ``Car in lane``
    or ``Car on road`` if ``lane`` and ``road`` are elements, as well as computing
    distances to an element, etc.
    """

    # from PolygonalRegion
    polygon: Union[Polygon, MultiPolygon]
    orientation: Optional[VectorField] = None

    name: str = ""  #: Human-readable name, if any.
    #: Unique identifier; from underlying format, if possible.
    #: (In OpenDRIVE, for example, ids are not necessarily unique, so we invent our own.)
    uid: str = None
    id: Optional[str] = None  #: Identifier from underlying format, if any.
    network: Network = None  #: Link to parent network.

    ## Traffic info

    #: Which types of vehicles (car, bicycle, etc.) can be here.
    vehicleTypes: FrozenSet[VehicleType] = frozenset([VehicleType.CAR])
    #: Optional speed limit, which may be inherited from parent.
    speedLimit: Union[float, None] = None
    #: Uninterpreted semantic tags, e.g. 'roundabout'.
    tags: FrozenSet[str] = frozenset()

    def __attrs_post_init__(self):
        assert self.uid is not None or self.id is not None
        if self.uid is None:
            self.uid = self.id

        super().__init__(
            polygon=self.polygon, orientation=self.orientation, name=self.name
        )

    @distributionFunction
    def nominalDirectionsAt(self, point: Vectorlike) -> Tuple[Orientation]:
        """Get nominal traffic direction(s) at a point in this element.

        There must be at least one such direction. If there are multiple, we
        pick one arbitrarily to be the orientation of the element as a `Region`.
        (So ``Object in element`` will align by default to that orientation.)
        """
        assert self.orientation, self
        return (self.orientation[_toVector(point)],)

    def __getstate__(self):
        state = super().__getstate__()
        del state["network"]  # do not pickle weak reference to parent network
        return state

    def __eq__(self, other):
        if not isinstance(other, NetworkElement):
            return NotImplemented
        return self.network is other.network and self.uid == other.uid

    def __hash__(self):
        return hash((self.network.__hash__(), self.uid))

    def __repr__(self):
        s = f"<{type(self).__name__} at {hex(id(self))}; "
        if self.name:
            s += f'name="{self.name}", '
        if self.id and self.id != self.uid:
            s += f'id="{self.id}", '
        s += f'uid="{self.uid}">'
        return s


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class LinearElement(NetworkElement):
    """LinearElement()

    A part of a road network with (mostly) linear 1- or 2-way flow.

    Includes roads, lane groups, lanes, sidewalks, and pedestrian crossings,
    but not intersections.

    LinearElements have a direction, namely from the first point on their centerline
    to the last point. This is called 'forward', even for 2-way roads. The 'left' and
    'right' edges are interpreted with respect to this direction.

    The left/right edges are oriented along the direction of traffic near them; so
    for 2-way roads they will point opposite directions.
    """

    # Geometric info (on top of the overall polygon from PolygonalRegion)
    centerline: PolylineRegion
    leftEdge: PolylineRegion
    rightEdge: PolylineRegion

    # Links to next/previous element
    _successor: Union[NetworkElement, None] = None  # going forward
    _predecessor: Union[NetworkElement, None] = None  # going backward

    _successors: Tuple[LinearElement, ...] = ()
    _predecessors: Tuple[LinearElement, ...] = ()

    @property
    def successor(self):
        return _rejectIfNonexistent(self._successor, "successor")

    @property
    def predecessor(self):
        return _rejectIfNonexistent(self._predecessor, "predecessor")

    @property
    def successors(self) -> Tuple[LinearElement, ...]:
        return self._successors

    @property
    def predecessors(self) -> Tuple[LinearElement, ...]:
        return self._predecessors

    def _addSuccessor(self, element):
        if element is None or type(element) is not type(self):
            return
        if element in self._successors:
            return
        self._successors += (element,)

    def _addPredecessor(self, element):
        if element is None or type(element) is not type(self):
            return
        if element in self._predecessors:
            return
        self._predecessors += (element,)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # Check that left and right edges lie inside the element.
        # (don't check centerline here since it can lie inside a median, for example)
        # (TODO reconsider the decision to have polygon only include drivable areas?)
        assert self.containsRegion(self.leftEdge, tolerance=0.5)
        assert self.containsRegion(self.rightEdge, tolerance=0.5)
        if self.orientation is None:
            self.orientation = VectorField(self.name, self._defaultHeadingAt)

    def _defaultHeadingAt(self, point):
        """Default orientation for this LinearElement.

        In general, we align along the nearest segment of the centerline.
        For roads, lane groups, etc., we align along the orientation of the
        lane containing the point.

        :meta private:
        """
        point = _toVector(point)
        start, end = self.centerline.nearestSegmentTo(point)
        return start.angleTo(end)

    @distributionFunction
    def flowFrom(
        self,
        point: Vectorlike,
        distance: float,
        steps: Union[int, None] = None,
        stepSize: float = 5,
    ) -> Vector:
        """Advance a point along this element by a given distance.

        Equivalent to ``follow element.orientation from point for distance``, but
        possibly more accurate. The default implementation uses the forward
        Euler approximation with a step size of 5 meters; subclasses may ignore
        the **steps** and **stepSize** parameters if they can compute the flow
        exactly.

        Arguments:
            point: point to start from.
            distance: distance to travel.
            steps: number of steps to take, or :obj:`None` to compute the
                number of steps based on the distance (default :obj:`None`).
            stepSize: length used to compute how many steps to take, if **steps** is not
                specified (default 5 meters).
        """
        return self.orientation.followFrom(
            _toVector(point), distance, steps=steps, stepSize=stepSize
        )

    # Signal entries are ordered by element-local s, which always increases from
    # the start of this element's centerline to its end. For backward lanes this
    # is travel order, the reverse of OpenDRIVE road-s order.
    SignalEntry = Tuple[
        float,  # element-local s, used for ordering and bisect
        "Signal",  # controlling signal
        float,  # OpenDRIVE road s of the effective stopping position
        float,  # OpenDRIVE road t at this element's centerline
    ]

    #: OpenDRIVE road-s interval covered by this element, if known.
    _roadSRange: Optional[Tuple[float, float]] = None
    _signalEntries: Tuple[SignalEntry, ...] = ()
    _signalSValues: Tuple[float, ...] = ()

    def signalLookup(self) -> Tuple[List[SignalEntry], List[float]]:
        """Return signal entries and their parallel, increasing local-s index."""
        return list(self._signalEntries), list(self._signalSValues)

    def signalsAhead(self, s: float) -> List[SignalEntry]:
        """Return all signals at or after local ``s`` in travel order."""
        index = bisect.bisect_left(self._signalSValues, s)
        return list(self._signalEntries[index:])

    def _projectS(self, point: Vectorlike) -> float:
        """Project a point to element-local s along the centerline."""
        return self.centerline.lineString.project(
            geometry.makeShapelyPoint(_toVector(point))
        )


class _ContainsCenterline:
    """Mixin which asserts that the centerline is contained in the polygon.

    :meta private:
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        assert self.containsRegion(self.centerline, tolerance=0.5)


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Road(LinearElement):
    """Road()

    A road consisting of one or more lanes.

    Lanes are grouped into 1 or 2 instances of `LaneGroup`:

        * **forwardLanes**: the lanes going the same direction as the road
        * **backwardLanes**: the lanes going the opposite direction

    One of these may be None if there are no lanes in that direction.

    Because of splits and mergers, the Lanes of a `Road` do not necessarily start
    or end at the same point as the `Road`. Such intermediate branching points
    cause the `Road` to be partitioned into multiple road sections, within which
    the configuration of lanes is fixed.
    """

    #: All lanes of this road, in either direction.
    #:
    #: The order of the lanes is arbitrary. To access lanes in order according to their
    #: geometry, use `LaneGroup.lanes`.
    lanes: Tuple[Lane]

    #: Group of lanes aligned with the direction of the road, if any.
    forwardLanes: Union[LaneGroup, None]
    #: Group of lanes going in the opposite direction, if any.
    backwardLanes: Union[LaneGroup, None]  # lanes going the other direction

    #: All LaneGroups of this road, with `forwardLanes` being first if it exists.
    laneGroups: Tuple[LaneGroup] = None

    #: All sections of this road, ordered from start to end.
    sections: Tuple[RoadSection]

    signals: Tuple[Signal]

    #: All crosswalks of this road, ordered from start to end.
    crossings: Tuple[PedestrianCrossing] = ()

    #: All sidewalks of this road, with the one adjacent to `forwardLanes` being first.
    sidewalks: Tuple[Sidewalk] = None
    #: Possibly-empty region consisting of all sidewalks of this road.
    sidewalkRegion: PolygonalRegion = None

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        lgs = []
        sidewalks = []
        if self.forwardLanes:
            lgs.append(self.forwardLanes)
            if self.forwardLanes._sidewalk:
                sidewalks.append(self.forwardLanes._sidewalk)
        if self.backwardLanes:
            lgs.append(self.backwardLanes)
            if self.backwardLanes._sidewalk:
                sidewalks.append(self.backwardLanes._sidewalk)
        self.laneGroups = tuple(lgs)
        self.sidewalks = tuple(sidewalks)
        self.sidewalkRegion = PolygonalRegion.unionAll(sidewalks)

    def _lateralOffsetAt(self, s: float, point: Vectorlike) -> float:
        """Signed lateral offset of ``point`` from the reference line at ``s``."""
        point = _toVector(point)
        reference_point = self.centerline.pointAlongBy(s)
        index = bisect.bisect_left(self.centerline.cumulativeLengths, s)
        index = min(index, len(self.centerline.segments) - 1)
        start, end = self.centerline.segments[index]
        tangent_x, tangent_y = end[0] - start[0], end[1] - start[1]
        offset_x = point.x - reference_point.x
        offset_y = point.y - reference_point.y
        distance = math.hypot(offset_x, offset_y)
        cross = tangent_x * offset_y - tangent_y * offset_x
        return distance if cross >= 0 else -distance

    def _propagateSignals(self):
        """Populate signal lookups on this road and its lane hierarchy."""
        tolerance = 1e-6
        pending = {}
        elements = [self, *self.sections, *self.laneGroups, *self.lanes]
        elements.extend(section for lane in self.lanes for section in lane.sections)
        for element in elements:
            element._signalEntries = ()
            element._signalSValues = ()

        road_section_for_lane_section = {
            lane_section: road_section
            for road_section in self.sections
            for lane_section in road_section.lanes
        }

        def add(element, signal, road_s):
            if element is None or element._roadSRange is None:
                return
            road_lo, road_hi = element._roadSRange
            if not road_lo - tolerance <= road_s <= road_hi + tolerance:
                return
            reference_point = self.centerline.pointAlongBy(road_s)
            if element is self:
                element_point = reference_point
                local_s = road_s
                road_t = 0.0
            else:
                element_point = element.centerline.project(reference_point)
                local_s = element._projectS(element_point)
                road_t = self._lateralOffsetAt(road_s, element_point)
            pending.setdefault(element, []).append((local_s, signal, road_s, road_t))

        for signal in self.signals:
            if signal.stoppingS is None:
                continue
            road_s = min(max(signal.stoppingS, 0.0), self.centerline.length)
            add(self, signal, road_s)

            for lane in self.lanes:
                if not signal.affects(lane) or not signal._lane_arrives_at_halt(lane):
                    continue
                effective_s = road_s
                add(lane, signal, effective_s)
                add(lane.group, signal, effective_s)

                matching_sections = [
                    section
                    for section in lane.sections
                    if section._roadSRange is not None
                    and section._roadSRange[0] - tolerance
                    <= effective_s
                    <= section._roadSRange[1] + tolerance
                ]
                if matching_sections:
                    lane_section = matching_sections[0]
                    add(lane_section, signal, effective_s)
                    add(
                        road_section_for_lane_section[lane_section],
                        signal,
                        effective_s,
                    )

        for element, entries in pending.items():
            unique = {}
            for entry in entries:
                unique[(entry[1].uid, entry[2])] = entry
            ordered = sorted(unique.values(), key=lambda entry: (entry[0], entry[1].uid))
            element._signalEntries = tuple(ordered)
            element._signalSValues = tuple(entry[0] for entry in ordered)

    def _defaultHeadingAt(self, point):
        point = _toVector(point)
        group = self.laneGroupAt(point)
        if group:
            return group.orientation[point]
        return super()._defaultHeadingAt(point)

    @distributionFunction
    def sectionAt(self, point: Vectorlike, reject=False) -> Union[RoadSection, None]:
        """Get the `RoadSection` passing through a given point."""
        return self.network.findPointIn(point, self.sections, reject)

    @distributionFunction
    def laneSectionAt(self, point: Vectorlike, reject=False) -> Union[LaneSection, None]:
        """Get the `LaneSection` passing through a given point."""
        point = _toVector(point)
        lane = self.laneAt(point, reject=reject)
        return None if lane is None else lane.sectionAt(point)

    @distributionFunction
    def laneAt(self, point: Vectorlike, reject=False) -> Union[Lane, None]:
        """Get the `Lane` passing through a given point."""
        return self.network.findPointIn(point, self.lanes, reject)

    @distributionFunction
    def laneGroupAt(self, point: Vectorlike, reject=False) -> Union[LaneGroup, None]:
        """Get the `LaneGroup` passing through a given point."""
        return self.network.findPointIn(point, self.laneGroups, reject)

    @distributionFunction
    def crossingAt(
        self, point: Vectorlike, reject=False
    ) -> Union[PedestrianCrossing, None]:
        """Get the :obj:`.PedestrianCrossing` passing through a given point."""
        return self.network.findPointIn(point, self.crossings, reject)

    @distributionFunction
    def shiftLanes(self, point: Vectorlike, offset: int) -> Union[Vector, None]:
        """Find the point equivalent to this one but shifted over some # of lanes."""
        raise NotImplementedError  # TODO implement this

    @property
    def is1Way(self) -> bool:
        return self.forwardLanes is None or self.backwardLanes is None


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class LaneGroup(LinearElement):
    """LaneGroup()

    A group of parallel lanes with the same type and direction.
    """

    road: Road  #: Parent road.
    lanes: Tuple[Lane]  #: Lanes, partially ordered with lane 0 being closest to the curb.

    #: Region representing the associated curb, which is not necessarily adjacent if
    #: there are parking lanes or some other kind of shoulder.
    curb: PolylineRegion

    # associated elements not actually part of this group
    _sidewalk: Union[Sidewalk, None] = None  #: Adjacent sidewalk, if any.
    _bikeLane: Union[Lane, None] = None
    _shoulder: Union[Shoulder, None] = None  #: Adjacent shoulder, if any.
    #: Opposite lane group of the same road, if any.
    _opposite: Union[LaneGroup, None] = None

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # Ensure lanes do not overlap
        for i in range(len(self.lanes) - 1):
            assert not self.lanes[i].polygon.overlaps(self.lanes[i + 1].polygon)

    @property
    def sidewalk(self) -> Sidewalk:
        """The adjacent sidewalk; rejects if there is none."""
        return _rejectIfNonexistent(self._sidewalk, "sidewalk")

    @property
    def bikeLane(self) -> Lane:
        return _rejectIfNonexistent(self._bikeLane, "bike lane")

    @property
    def shoulder(self) -> Shoulder:
        """The adjacent shoulder; rejects if there is none."""
        return _rejectIfNonexistent(self._shoulder, "shoulder")

    @property
    def opposite(self) -> LaneGroup:
        """The opposite lane group of the same road; rejects if there is none."""
        return _rejectIfNonexistent(self._opposite, "opposite lane group")

    def _defaultHeadingAt(self, point):
        point = _toVector(point)
        lane = self.laneAt(point)
        if lane:
            return lane.orientation[point]
        return super()._defaultHeadingAt(point)

    @distributionFunction
    def laneAt(self, point: Vectorlike, reject=False) -> Union[Lane, None]:
        """Get the `Lane` passing through a given point."""
        return self.network.findPointIn(point, self.lanes, reject)


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Lane(_ContainsCenterline, LinearElement):
    """Lane()

    A lane for cars, bicycles, or other vehicles.
    """

    group: LaneGroup  # parent lane group
    road: Road  # grandparent road
    sections: Tuple[LaneSection]  # sections in order from start to end

    adjacentLanes: Tuple[Lane] = ()  # adjacent lanes of same type, if any

    # possible maneuvers upon reaching the end of this lane
    maneuvers: Tuple[Maneuver] = ()

    @distributionFunction
    def sectionAt(self, point: Vectorlike, reject=False) -> Union[LaneSection, None]:
        """Get the LaneSection passing through a given point."""
        return self.network.findPointIn(point, self.sections, reject)

    def haltPositionAhead(
        self, position, lookahead: float = 80.0
    ) -> Optional[Tuple[float, float]]:
        """Effective road ``(s, t)`` of the nearest halt ahead of ``position``."""
        lane_line = self.centerline.lineString
        here = lane_line.project(ShapelyPoint(position.x, position.y))
        best_position = None
        best_ahead = None
        for sig in self.road.signals:
            stop_position = sig.stoppingPositionOn(self)
            if stop_position is None:
                continue
            s, _ = stop_position
            reference_point = self.road.centerline.pointAlongBy(s)
            pt = self.centerline.project(reference_point)
            ahead = lane_line.project(ShapelyPoint(pt.x, pt.y)) - here
            if 0 <= ahead <= lookahead and (best_ahead is None or ahead < best_ahead):
                best_position = stop_position
                best_ahead = ahead
        return best_position


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class RoadSection(LinearElement):
    """RoadSection()

    Part of a road with a fixed number of lanes.

    A RoadSection has a fixed number of lanes: when a lane begins or ends, we
    move to a new section (which will be the successor of the current one).
    """

    road: Road  # parent road
    lanes: Tuple[LaneSection] = ()  # in order, with lane 0 being the rightmost
    forwardLanes: Tuple[LaneSection] = ()  # as above
    backwardLanes: Tuple[LaneSection] = ()  # as above

    lanesByOpenDriveID: Dict[LaneSection]

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if not self.lanes and not self.lanesByOpenDriveID:
            raise RuntimeError("RoadSection created with no lanes")
        if self.lanesByOpenDriveID and not self.lanes:
            forward, backward = [], []
            rightmost = min(self.lanesByOpenDriveID)
            assert rightmost != 0, self.lanesByOpenDriveID
            leftmost = max(self.lanesByOpenDriveID)
            for i in range(rightmost, leftmost + 1):
                if i == 0:
                    continue
                if i not in self.lanesByOpenDriveID:
                    continue
                (forward if i < 0 else backward).append(self.lanesByOpenDriveID[i])
            self.forwardLanes = tuple(forward)
            self.backwardLanes = tuple(backward)
            self.lanes = self.forwardLanes + self.backwardLanes
        elif self.lanes and not self.lanesByOpenDriveID:
            ids = {}
            for i, lane in enumerate(self.forwardLanes, start=1):
                ids[-i] = lane
            for i, lane in enumerate(self.backwardLanes, start=1):
                ids[i] = lane
            self.lanesByOpenDriveID = ids

        # Ensure lanes do not overlap
        for i in range(len(self.lanes) - 1):
            assert not self.lanes[i].polygon.overlaps(self.lanes[i + 1].polygon)

    def _defaultHeadingAt(self, point):
        point = _toVector(point)
        lane = self.laneAt(point)
        if lane:
            return lane.orientation[point]
        return super()._defaultHeadingAt(point)

    @distributionFunction
    def laneAt(self, point: Vectorlike, reject=False) -> Union[LaneSection, None]:
        """Get the lane section passing through a given point."""
        return self.network.findPointIn(point, self.lanes, reject)


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class LaneSection(_ContainsCenterline, LinearElement):
    """LaneSection()

    Part of a lane in a single `RoadSection`.

    Since the lane configuration in a `RoadSection` is fixed, a `LaneSection` can have
    at most one adjacent lane to left or right. These are accessible using the
    `laneToLeft` and `laneToRight` properties, which for convenience reject the
    simulation if the desired lane does not exist. If rejection is not desired (for
    example if you want to handle the case where there is no lane to the left yourself),
    you can use the `_laneToLeft` and `_laneToRight` properties instead.
    """

    lane: Lane  #: Parent lane.
    group: LaneGroup  #: Grandparent lane group.
    road: Road  #: Great-grandparent road.

    #: ID number as in OpenDRIVE (number of lanes to left of center, with 1 being the
    # first lane left of the centerline and -1 being the first lane to the right).
    openDriveID: int
    #: Whether this lane has the same direction as its parent road.
    isForward: bool = True

    #: Adjacent lanes of the same type, if any.
    adjacentLanes: Tuple[LaneSection] = ()

    #: Adjacent lane of same type to the left, if any.
    _laneToLeft: Union[LaneSection, None] = None
    #: Adjacent lane of same type to the right, if any.
    _laneToRight: Union[LaneSection, None] = None

    #: Faster adjacent lane of same type, if any.
    #: Could be to left or right depending on the country.
    _fasterLane: Union[LaneSection, None] = None
    #: Slower adjacent lane of same type, if any.
    _slowerLane: Union[LaneSection, None] = None

    @property
    def laneToLeft(self) -> LaneSection:
        """The adjacent lane of the same type to the left; rejects if there is none."""
        return _rejectIfNonexistent(self._laneToLeft, "lane to left")

    @property
    def laneToRight(self) -> LaneSection:
        """The adjacent lane of the same type to the right; rejects if there is none."""
        return _rejectIfNonexistent(self._laneToRight, "lane to right")

    @property
    def fasterLane(self) -> LaneSection:
        """The faster adjacent lane of the same type; rejects if there is none."""
        return _rejectIfNonexistent(self._fasterLane, "faster lane")

    @property
    def slowerLane(self) -> LaneSection:
        """The slower adjacent lane of the same type; rejects if there is none."""
        return _rejectIfNonexistent(self._slowerLane, "slower lane")

    @distributionFunction
    def shiftedBy(self, offset: int) -> Union[LaneSection, None]:
        """Find the lane a given number of lanes over from this lane."""
        current = self
        for i in range(abs(offset)):
            if offset > 0:
                current = current.laneToLeft
            else:
                current = current.laneToRight
            if current is None:
                return None
        return current


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Sidewalk(_ContainsCenterline, LinearElement):
    """Sidewalk()

    A sidewalk.
    """

    road: Road
    crossings: Tuple[PedestrianCrossing]


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class PedestrianCrossing(_ContainsCenterline, LinearElement):
    """PedestrianCrossing()

    A pedestrian crossing (crosswalk).
    """

    parent: Union[Road, Intersection]
    startSidewalk: Sidewalk
    endSidewalk: Sidewalk


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Shoulder(_ContainsCenterline, LinearElement):
    """Shoulder()

    A shoulder of a road, including parking lanes by default.
    """

    road: Road


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Intersection(NetworkElement):
    """Intersection()

    An intersection where multiple roads meet.
    """

    roads: Tuple[Road]  # in some order, preserving adjacency
    incomingLanes: Tuple[Lane]
    outgoingLanes: Tuple[Lane]
    maneuvers: Tuple[Maneuver]  # all possible maneuvers through the intersection

    signals: Tuple[Signal]

    crossings: Tuple[PedestrianCrossing]  # also ordered to preserve adjacency

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        for maneuver in self.maneuvers:
            assert maneuver.connectingLane, maneuver
            assert self.containsRegion(maneuver.connectingLane, tolerance=0.5)
        if self.orientation is None:
            self.orientation = VectorField(self.name, self._defaultHeadingAt)

    def _defaultHeadingAt(self, point):
        """Default orientation for this Intersection.

        We align along the closest connecting lane.

        :meta private:
        """
        point = _toVector(point)
        man = min(self.maneuvers, key=lambda man: man.connectingLane.distanceTo(point))
        return man.connectingLane.orientation[point]

    @property
    def is3Way(self) -> bool:
        """bool: Whether or not this is a 3-way intersection."""
        return len(self.roads) == 3

    @property
    def is4Way(self) -> bool:
        """bool: Whether or not this is a 4-way intersection."""
        return len(self.roads) == 4

    @property
    def isSignalized(self) -> bool:
        """bool: Whether or not this is a signalized intersection."""
        return len(self.signals) > 0

    @distributionFunction
    def maneuversAt(self, point: Vectorlike) -> List[Maneuver]:
        """Get all maneuvers possible at a given point in the intersection."""
        maneuvers = self.network._findPointInAll(
            point, self.maneuvers, key=lambda m: m.connectingLane
        )
        if maneuvers:
            return maneuvers
        # If we filled holes in intersections when computing the geometry, there
        # might be no maneuvers at some points inside the intersection. We'll pick
        # the closest one.
        man = min(self.maneuvers, key=lambda man: man.connectingLane.distanceTo(point))
        return [man]

    @distributionFunction
    def nominalDirectionsAt(self, point: Vectorlike) -> Tuple[Orientation]:
        point = _toVector(point)
        maneuvers = self.maneuversAt(point)
        assert maneuvers, self
        return tuple(m.connectingLane.orientation[point] for m in maneuvers)


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Signal:
    """Traffic lights, stop signs, etc.

    .. warning::

        Signal parsing is a work in progress and the API is likely to change in the future.
    """

    uid: str = None
    #: Identifier from the source map (OpenDRIVE ``id``; stored as a string).
    openDriveID: str
    #: Deprecated country code; `type` is still the format type identifier.
    _country: str
    #: Type identifier according to the source map.
    type: str
    #: Deprecated country-specific subtype; `type` is still the format type identifier.
    _subtype: Optional[str] = None
    #: Known control tags; see `SignalTag` for meanings.
    tags: FrozenSet[SignalTag] = frozenset()
    #: Source control literals that are not `SignalTag` members.
    otherTags: FrozenSet[str] = frozenset()
    #: Longitudinal station along the parent road used for halt decisions.
    s: Optional[float] = None
    #: Lateral t-coordinate from the reference line (OpenDRIVE ``t``; +t = left).
    t: Optional[float] = None
    #: OpenDRIVE signal orientation: ``"+"``, ``"-"``, or ``"none"``.
    orientation: Optional[str] = None
    #: Station along the parent road where an ego should halt for this signal.
    #: May differ from `s` (e.g. a traffic light's pole vs its stop line).
    #: ``None`` if we cannot derive one.
    stoppingS: Optional[float] = None
    #: Placeholder for a future world-space device/pole position. Halt decisions
    #: intentionally use `stoppingS` and `stoppingPositionOn`, not this field.
    position: Optional[Vector] = None
    #: Maneuvers that require this signal to be green (empty if unknown).
    controlledManeuvers: Tuple[Maneuver, ...] = ()
    #: Incoming or hosting road this signal belongs to.
    road: Optional[Road] = None
    #: Junction this signal controls, if any.
    intersection: Optional[Intersection] = None

    @property
    def country(self) -> str:
        """Deprecated country code.

        Prefer `tags` for control meaning when the map provides them.
        `type` remains the format type identifier (needed for CARLA maps).
        """
        warnings.warn(
            "Signal.country is deprecated; prefer Signal.tags for control "
            "meaning when present. Signal.type remains the type identifier.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._country

    @property
    def subtype(self) -> Optional[str]:
        """Deprecated country-specific subtype.

        Prefer `tags` for control meaning when the map provides them.
        `type` remains the format type identifier (needed for CARLA maps).
        """
        warnings.warn(
            "Signal.subtype is deprecated; prefer Signal.tags for control "
            "meaning when present. Signal.type remains the type identifier.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._subtype

    def hasTag(self, tag: SignalTag) -> bool:
        """Whether this signal carries the given known control tag."""
        return tag in self.tags

    def affects(self, lane: Lane) -> bool:
        """Whether this signal applies to ``lane``.

        A halt at a road end is treated as a junction contact: only the
        arriving direction is kept, because device orientation is often lamp
        facing rather than traffic. Otherwise ``orientation`` is compared to
        whether the lane travels with the road (+s).
        """
        if self._halts_at_road_end(lane.road):
            return self._lane_arrives_at_halt(lane)
        if self.orientation in (None, "none"):
            return True
        is_forward = any(sec.isForward for sec in lane.sections)
        if self.orientation == "+":
            return is_forward
        if self.orientation == "-":
            return not is_forward
        return True

    def _halts_at_road_end(self, road: Optional[Road]) -> bool:
        if road is None or self.stoppingS is None:
            return False
        length = road.centerline.length
        s = self.stoppingS
        return abs(s) <= 1e-4 or abs(s - length) <= 1e-4

    def _isHaltLocation(self) -> bool:
        return self.isStop or self.isYield or self.isFourWay

    def resolveStoppingS(self, plus_contact, minus_contact):
        """Pick the halt station from this signal's ``s`` or a junction contact.

        ``plus_contact`` / ``minus_contact`` are that road's junction stations
        for +s / −s travel, or ``None`` if that end is not a junction.
        """
        if self._isHaltLocation():
            return self.s
        if self.isTrafficLight:
            candidates = [
                contact
                for contact in (plus_contact, minus_contact)
                if contact is not None
            ]
            if not candidates:
                return None
            # CARLA poles sit next to the junction they serve; orientation
            # often names the other end (or a non-junction end).
            if self.s is not None:
                return min(candidates, key=lambda contact: abs(contact - self.s))
            if self.orientation == "+":
                return plus_contact
            if self.orientation == "-":
                return minus_contact
            return candidates[0]
        return None

    def _lane_arrives_at_halt(self, lane: Lane) -> bool:
        """Whether ``lane`` is still traveling toward `stoppingS`.

        A mid-road halt applies to every lane that `affects` already accepted.
        A halt at a road end (``0`` or the reference-line length) is treated as
        a junction contact: only the direction still arriving at that end is
        kept, not the lane that has already left through the junction.
        """
        road = lane.road
        s = self.stoppingS
        if not self._halts_at_road_end(road):
            return True
        is_forward = any(sec.isForward for sec in lane.sections)
        at_start = abs(s) <= 1e-4
        return (not is_forward) if at_start else is_forward

    def stoppingPositionOn(self, lane: Lane) -> Optional[Tuple[float, float]]:
        """Effective road ``(s, t)`` where an ego should halt on ``lane``.

        The returned ``t`` is the signed lateral offset from the road reference
        line to the lane center at `stoppingS` (positive to the left). A
        junction-contact halt is only returned for the direction still arriving
        at that end — not the lane you enter after turning through the light.
        ``None`` if the signal does not `affects` the lane, has no `stoppingS`,
        or does not belong to ``lane.road``.
        """
        if self.stoppingS is None or not self.affects(lane):
            return None
        road = lane.road
        if self not in road.signals:
            return None
        if not self._lane_arrives_at_halt(lane):
            return None
        length = road.centerline.length
        s = min(max(self.stoppingS, 0.0), length)
        reference_point = road.centerline.pointAlongBy(s)
        lane_point = lane.centerline.project(reference_point)
        t = road._lateralOffsetAt(s, lane_point)
        return s, t

    @property
    def isTrafficLight(self) -> bool:
        """Whether this is a signalized control (red/yellow/green or equivalent)."""
        if self.hasTag(SignalTag.TRAFFIC_LIGHT):
            return True
        # CARLA / OpenDRIVE maps encode lights as type codes, not tags.
        return self.type in {
            "1000001",
            "1000008",
            "1000009",
            "1000010",
            "1000011",
            "1000012",
            "1000020",
        }

    @property
    def isStop(self) -> bool:
        """Whether the vehicle must come to a complete stop before proceeding."""
        return self.hasTag(SignalTag.STOP) or self.type == "206"

    @property
    def isYield(self) -> bool:
        """Whether the vehicle must give way; a full stop is not always required."""
        return self.hasTag(SignalTag.YIELD) or self.type == "205"

    @property
    def isFourWay(self) -> bool:
        """Whether every approach must halt (all-way stop)."""
        return self.hasTag(SignalTag.FOUR_WAY)

    @property
    def isNoTurnOnRed(self) -> bool:
        """Whether turning on red is forbidden."""
        return self.hasTag(SignalTag.NO_TURN_ON_RED)

    @property
    def isTurnOnRedAllowed(self) -> bool:
        """Whether turning on red is explicitly permitted."""
        return self.hasTag(SignalTag.TURN_ON_RED_ALLOWED)


@attr.s(auto_attribs=True, kw_only=True, repr=False, eq=False)
class Network:
    """Network()

    A road network.

    Networks are composed of roads, intersections, sidewalks, etc., which are all
    instances of `NetworkElement`.

    Road networks can be loaded from standard formats using `Network.fromFile`.
    """

    #: All network elements, indexed by unique ID.
    elements: Dict[str, NetworkElement]

    #: All ordinary roads in the network (i.e. those not part of an intersection).
    roads: Tuple[Road]
    #: All roads connecting one exit of an intersection to another.
    connectingRoads: Tuple[Road]
    #: All roads of either type.
    allRoads: Tuple[Road] = None

    #: All lane groups in the network.
    laneGroups: Tuple[LaneGroup]
    #: All lanes in the network.
    lanes: Tuple[Lane]

    #: All intersections in the network.
    intersections: Tuple[Intersection]
    #: All traffic signals in the network.
    signals: Tuple[Signal, ...] = None
    #: All pedestrian crossings in the network.
    crossings: Tuple[PedestrianCrossing]
    #: All sidewalks in the network.
    sidewalks: Tuple[Sidewalk]
    #: All shoulders in the network (by default, includes parking lanes).
    shoulders: Tuple[Shoulder]

    #: All sections of ordinary roads in the network.
    roadSections: Tuple[RoadSection] = None
    #: All sections of lanes in the network.
    laneSections: Tuple[LaneSection] = None

    #: Whether or not cars drive on the left in this network.
    driveOnLeft: bool = False
    #: Distance tolerance for testing inclusion in network elements.
    tolerance: float = 0

    # convenience regions aggregated from various types of network elements
    drivableRegion: PolygonalRegion = None
    walkableRegion: PolygonalRegion = None
    roadRegion: PolygonalRegion = None
    laneRegion: PolygonalRegion = None
    intersectionRegion: PolygonalRegion = None
    crossingRegion: PolygonalRegion = None
    sidewalkRegion: PolygonalRegion = None
    curbRegion: PolylineRegion = None
    shoulderRegion: PolygonalRegion = None

    #: Traffic flow vector field aggregated over all roads (0 elsewhere).
    roadDirection: VectorField = None

    def __attrs_post_init__(self):
        proxy = weakref.proxy(self)
        for uid, elem in self.elements.items():
            assert elem.uid == uid
            elem.network = proxy

        self.allRoads = self.roads + self.connectingRoads
        self.roadSections = tuple(sec for road in self.roads for sec in road.sections)
        self.laneSections = tuple(sec for lane in self.lanes for sec in lane.sections)

        ordered, seen = [], set()
        for road in self.roads:
            for signal in road.signals:
                if id(signal) not in seen:
                    ordered.append(signal)
                    seen.add(id(signal))
        for intersection in self.intersections:
            for signal in intersection.signals:
                if id(signal) not in seen:
                    ordered.append(signal)
                    seen.add(id(signal))
        self.signals = tuple(ordered)

        if self.roadRegion is None:
            self.roadRegion = PolygonalRegion.unionAll(self.roads)
        if self.laneRegion is None:
            self.laneRegion = PolygonalRegion.unionAll(self.lanes)
        if self.intersectionRegion is None:
            self.intersectionRegion = PolygonalRegion.unionAll(self.intersections)
        if self.crossingRegion is None:
            self.crossingRegion = PolygonalRegion.unionAll(self.crossings)
        if self.sidewalkRegion is None:
            self.sidewalkRegion = PolygonalRegion.unionAll(self.sidewalks)
        if self.shoulderRegion is None:
            self.shoulderRegion = PolygonalRegion.unionAll(self.shoulders)

        if self.drivableRegion is None:
            self.drivableRegion = PolygonalRegion.unionAll(
                (
                    self.laneRegion,
                    self.roadRegion,  # can contain points slightly outside laneRegion
                    self.intersectionRegion,
                )
            )
        assert self.drivableRegion.containsRegion(
            self.laneRegion, tolerance=self.tolerance
        )
        assert self.drivableRegion.containsRegion(
            self.roadRegion, tolerance=self.tolerance
        )
        assert self.drivableRegion.containsRegion(
            self.intersectionRegion, tolerance=self.tolerance
        )
        if self.walkableRegion is None:
            self.walkableRegion = self.sidewalkRegion.union(self.crossingRegion)
        assert self.walkableRegion.containsRegion(
            self.sidewalkRegion, tolerance=self.tolerance
        )
        assert self.walkableRegion.containsRegion(
            self.crossingRegion, tolerance=self.tolerance
        )

        if self.curbRegion is None:
            edges = []
            for road in self.roads:  # only include curbs of ordinary roads
                if road.forwardLanes:
                    edges.append(road.forwardLanes.curb)
                if road.backwardLanes:
                    edges.append(road.backwardLanes.curb)
            self.curbRegion = PolylineRegion.unionAll(edges)

        if self.roadDirection is None:
            # TODO replace with a PolygonalVectorField for better pruning
            self.roadDirection = VectorField("roadDirection", self._defaultRoadDirection)

        # Build R-tree for faster lookup of roads, etc. at given points
        self._uidForIndex = tuple(self.elements)
        self._rtree = shapely.STRtree([elem.polygons for elem in self.elements.values()])
        self._nominalDirElems = self.intersections + self.roads + self.shoulders
        self._topLevelElements = (
            self.intersections + self.roads + self.shoulders + self.sidewalks
        )
        # NOTE: Order matters here; elementAt resolves in this sequence.

    def _defaultRoadDirection(self, point):
        """Default value for the `roadDirection` vector field.

        :meta private:
        """
        point = _toVector(point)
        elem = self.findPointIn(point, self._nominalDirElems, reject=False)
        return elem.orientation[point] if elem is not None else 0

    #: File extension for cached versions of processed networks.
    pickledExt = ".snet"

    @classmethod
    def _currentFormatVersion(cls):
        """Version number for the road network format.

        Should be incremented whenever attributes of `Network`, `NetworkElement`, etc.,
        attributes of the underlying Regions, or the serialization process itself are
        changed, so that cached networks will be properly regenerated (rather than being
        unpickled in an inconsistent state and causing errors later). Changes to the map
        geometry calculations should be included, even if the format itself is unchanged.

        :meta private:
        """
        return 38

    class DigestMismatchError(Exception):
        """Exception raised when loading a cached map not matching the original file."""

        pass

    @classmethod
    def fromFile(cls, path, useCache: bool = True, writeCache: bool = True, **kwargs):
        """Create a `Network` from a map file.

        This function calls an appropriate parsing routine based on the extension of the
        given file. Supported map formats are:

            * OpenDRIVE (``.xodr``): `Network.fromOpenDrive`

        See the functions listed above for format-specific options to this function.
        If no file extension is given in **path**, this function searches for any file
        with the given name in one of the formats above (in order).

        Args:
            path: A string or other :term:`path-like object` giving a path to a file.
                If no file extension is included, we search for any file type we know how
                to parse.
            useCache: Whether to use a cached version of the map, if one exists
                and matches the given map file (default true; note that if the map file
                changes, the cached version will still not be used).
            writeCache: Whether to save a cached version of the processed map
                after parsing has finished (default true).
            kwargs: Additional keyword arguments specific to particular map formats.

        Raises:
            FileNotFoundError: no readable map was found at the given path.
            ValueError: the given map is of an unknown format.
        """
        path = pathlib.Path(path)
        ext = path.suffix

        handlers = {  # in order of decreasing priority
            ".xodr": cls.fromOpenDrive,  # OpenDRIVE
            # Pickled native representation; this is the lowest priority, since original
            # maps should take precedence, but if the pickled version exists and matches
            # the original, we'll use it.
            cls.pickledExt: cls.fromPickle,
        }

        if not ext:  # no extension was given; search through possible formats
            found = False
            for ext in handlers:
                newPath = path.with_suffix(ext)
                if newPath.exists():
                    path = newPath
                    found = True
                    break
            if not found:
                raise FileNotFoundError(f"no readable maps found for path {path}")
        elif ext not in handlers:
            raise ValueError(f"unknown type of road network file {path}")

        # If we don't have an underlying map file, return the pickled version directly
        if ext == cls.pickledExt:
            return cls.fromPickle(path)

        # Otherwise, hash the underlying file to detect when the pickle is outdated
        with open(path, "rb") as f:
            data = f.read()
        digest = hashlib.blake2b(data).digest()

        # Hash the map options as well so changing them invalidates the cache.
        optionsDigest = deterministicHash(kwargs, digest_size=8)

        # By default, use the pickled version if it exists and is not outdated
        pickledPath = path.with_suffix(cls.pickledExt)
        if useCache and pickledPath.exists():
            try:
                return cls.fromPickle(
                    pickledPath,
                    originalDigest=digest,
                    optionsDigest=optionsDigest,
                )
            except pickle.UnpicklingError:
                verbosePrint("Unable to load cached network (old format or corrupted).")
            except cls.DigestMismatchError:
                verbosePrint(
                    "Cached network does not match original file or map options; ignoring it."
                )

        # Not using the pickled version; parse the original file based on its extension
        network = handlers[ext](path, **kwargs)
        if writeCache:
            verbosePrint(f"Caching road network in {cls.pickledExt} file.")
            network.dumpPickle(
                path.with_suffix(cls.pickledExt),
                digest,
                optionsDigest=optionsDigest,
            )
        return network

    @classmethod
    def fromOpenDrive(
        cls,
        path,
        ref_points: int = 20,
        tolerance: float = 0.05,
        fill_gaps: bool = True,
        fill_intersections: bool = True,
        elide_short_roads: bool = False,
    ):
        """Create a `Network` from an OpenDRIVE file.

        Args:
            path: Path to the file, as in `Network.fromFile`.
            ref_points: Number of points to discretize continuous reference lines
                into.
            tolerance: Tolerance for merging nearby geometries.
            fill_gaps: Whether to attempt to fill gaps between adjacent lanes.
            fill_intersections: Whether to attempt to fill gaps inside
                intersections.
            elide_short_roads: Whether to attempt to fix geometry artifacts by
                eliding roads with length less than **tolerance**.
        """
        import scenic.formats.opendrive.xodr_parser as xodr_parser

        road_map = xodr_parser.RoadMap(
            tolerance=tolerance,
            fill_intersections=fill_intersections,
            elide_short_roads=elide_short_roads,
        )
        startTime = time.time()
        verbosePrint("Parsing OpenDRIVE file...")
        road_map.parse(path)
        verbosePrint("Computing road geometry... (this may take a while)")
        road_map.calculate_geometry(ref_points, calc_gap=fill_gaps, calc_intersect=True)
        network = road_map.toScenicNetwork()
        totalTime = time.time() - startTime
        verbosePrint(f"Finished loading OpenDRIVE map in {totalTime:.2f} seconds.")
        return network

    @classmethod
    def fromPickle(cls, path, originalDigest=None, optionsDigest=None):
        startTime = time.time()
        verbosePrint("Loading cached version of road network...")

        with open(path, "rb") as f:
            # Version field
            versionField = f.read(4)
            if len(versionField) != 4:
                raise pickle.UnpicklingError(f"{cls.pickledExt} file is corrupted")
            version = struct.unpack("<I", versionField)
            if version[0] != cls._currentFormatVersion():
                raise pickle.UnpicklingError(
                    f"{cls.pickledExt} file is too old; "
                    "regenerate it from the original map"
                )

            # Digest of the original map file
            digest = f.read(64)
            if len(digest) != 64:
                raise pickle.UnpicklingError(f"{cls.pickledExt} file is corrupted")
            if originalDigest and originalDigest != digest:
                raise cls.DigestMismatchError(
                    f"{cls.pickledExt} file does not correspond to the original map; "
                    " regenerate it"
                )

            # Digest of the map options used to generate this cache
            cachedOptionsDigest = f.read(8)
            if len(cachedOptionsDigest) != 8:
                raise pickle.UnpicklingError(f"{cls.pickledExt} file is corrupted")
            if optionsDigest and optionsDigest != cachedOptionsDigest:
                raise cls.DigestMismatchError(
                    f"{cls.pickledExt} file does not correspond to the current "
                    "map options; regenerate it"
                )

            # Remaining bytes are the compressed pickle of the Network
            with gzip.open(f) as gf:
                try:
                    network = pickle.load(gf)  # invokes __setstate__ below
                except pickle.UnpicklingError:
                    raise  # propagate unpickling errors
                except Exception as e:
                    # convert various other ways unpickling can fail into a more
                    # standard exception
                    raise pickle.UnpicklingError("unpickling failed") from e

        totalTime = time.time() - startTime
        verbosePrint(f"Loaded cached network in {totalTime:.2f} seconds.")
        return network

    def __setstate__(self, state):
        # Restore our attributes (default behavior when __setstate__ isn't defined)
        self.__dict__.update(state)

        # Reconnect links between network elements
        def reconnect(thing):
            state = thing.__dict__
            for key, value in state.items():
                if isinstance(value, _ElementPlaceholder):
                    state[key] = self.elements[value.uid]

        proxy = weakref.proxy(self)
        for elem in self.elements.values():
            reconnect(elem)
            elem.network = proxy
        for elem in itertools.chain(self.lanes, self.intersections):
            for maneuver in elem.maneuvers:
                reconnect(maneuver)

    def dumpPickle(self, path, digest, optionsDigest):
        path = pathlib.Path(path)
        if not path.suffix:
            path = path.with_suffix(self.pickledExt)
        version = struct.pack("<I", self._currentFormatVersion())
        data = pickle.dumps(self)

        with open(path, "wb") as f:
            f.write(version)  # uncompressed in case we change compression schemes later
            f.write(digest)  # digest of original map file
            f.write(optionsDigest)  # digest of map options

            # The rest of the file is a gzip-compressed pickle of the Network.
            with gzip.open(f, "wb") as gf:
                gf.write(data)

    @distributionMethod
    def findPointIn(
        self, point: Vectorlike, elems: Sequence[NetworkElement], reject: Union[bool, str]
    ) -> Union[NetworkElement, None]:
        """Find the first of the given elements containing the point.

        Elements which *actually* contain the point have priority; if none contain the
        point, then we search again allowing an error of up to **tolerance**. If there
        are still no matches, we return None, unless **reject** is true, in which case we
        reject the current sample.
        """
        point = shapely.geometry.Point(_toVector(point))

        def findElementWithin(distance):
            target = point if distance == 0 else point.buffer(distance)
            indices = self._rtree.query(target, predicate="intersects")
            candidates = {self._uidForIndex[index] for index in indices}
            if candidates:
                for elem in elems:
                    if elem.uid in candidates:
                        return elem
            return None

        # First pass: check for elements containing the point.
        if elem := findElementWithin(0):
            return elem

        # Second pass: check for elements within tolerance of the point.
        if self.tolerance > 0 and (elem := findElementWithin(self.tolerance)):
            return elem

        # No matches found.
        if reject:
            if isinstance(reject, str):
                message = reject
            else:
                message = "requested element does not exist"
            raise RejectionException(message)
        return None

    def _findPointInAll(self, point, things, key=lambda e: e):
        point = _toVector(point)
        found = []
        for thing in things:
            if key(thing).containsPoint(point):
                found.append(thing)
        if not found and self.tolerance > 0:
            for thing in things:
                if key(thing).distanceTo(point) <= self.tolerance:
                    found.append(thing)
        return found

    @distributionMethod
    def elementAt(self, point: Vectorlike, reject=False) -> Union[NetworkElement, None]:
        """Get the highest-level `NetworkElement` at a given point, if any.

        If the point lies in an element, return it.
        Otherwise, if the point lies within ``self.tolerance`` of an element, return the first
        match using this priority order: Intersection → Road → Shoulder → Sidewalk.
        If nothing matches, return `None` (or reject if ``reject=True``).
        """
        point = _toVector(point)
        return self.findPointIn(point, self._topLevelElements, reject)

    @distributionMethod
    def roadAt(self, point: Vectorlike, reject=False) -> Union[Road, None]:
        """Get the `Road` passing through a given point."""
        return self.findPointIn(point, self.allRoads, reject)

    @distributionMethod
    def laneAt(self, point: Vectorlike, reject=False) -> Union[Lane, None]:
        """Get the `Lane` passing through a given point."""
        return self.findPointIn(point, self.lanes, reject)

    @distributionMethod
    def laneSectionAt(self, point: Vectorlike, reject=False) -> Union[LaneSection, None]:
        """Get the `LaneSection` passing through a given point."""
        point = _toVector(point)
        lane = self.laneAt(point, reject=reject)
        return None if lane is None else lane.sectionAt(point)

    @distributionMethod
    def laneGroupAt(self, point: Vectorlike, reject=False) -> Union[LaneGroup, None]:
        """Get the `LaneGroup` passing through a given point."""
        point = _toVector(point)
        road = self.roadAt(point, reject=reject)
        return None if road is None else road.laneGroupAt(point, reject=reject)

    @distributionMethod
    def crossingAt(
        self, point: Vectorlike, reject=False
    ) -> Union[PedestrianCrossing, None]:
        """Get the `PedestrianCrossing` passing through a given point."""
        point = _toVector(point)
        road = self.roadAt(point, reject=reject)
        return None if road is None else road.crossingAt(point, reject=reject)

    @distributionMethod
    def intersectionAt(
        self, point: Vectorlike, reject=False
    ) -> Union[Intersection, None]:
        """Get the `Intersection` at a given point."""
        return self.findPointIn(point, self.intersections, reject)

    @distributionMethod
    def sidewalkAt(self, point: Vectorlike, reject=False) -> Union[Sidewalk, None]:
        """Get the `Sidewalk` at a given point."""
        return self.findPointIn(point, self.sidewalks, reject)

    @distributionMethod
    def shoulderAt(self, point: Vectorlike, reject=False) -> Union[Shoulder, None]:
        """Get the `Shoulder` at a given point."""
        return self.findPointIn(point, self.shoulders, reject)

    @distributionMethod
    def nominalDirectionsAt(self, point: Vectorlike, reject=False) -> Tuple[Orientation]:
        """Get the nominal traffic direction(s) at a given point, if any.

        There can be more than one such direction in an intersection, for example: a car
        at a given point could be going straight, turning left, etc.
        """
        elem = self.findPointIn(point, self._nominalDirElems, reject)
        return elem.nominalDirectionsAt(point) if elem is not None else ()

    def show(self, labelIncomingLanes=False, showCurbArrows=False):
        """Render a schematic of the road network for debugging.

        If you call this function directly, you'll need to subsequently call
        `matplotlib.pyplot.show` to actually display the diagram.

        Args:
            labelIncomingLanes (bool): Whether to label the incoming lanes of
                intersections with their indices in ``incomingLanes``.
            showCurbArrows (bool): Whether to draw arrows along the curb to show orientation
        """
        import matplotlib.pyplot as plt

        self.walkableRegion.show(plt, style="-", color="#00A0FF")
        self.shoulderRegion.show(plt, style="-", color="#606060")
        for road in self.roads:
            road.show(plt, style="r-")
            for lane in road.lanes:  # will loop only over lanes of main roads
                lane.leftEdge.show(plt, style="r--")
                lane.rightEdge.show(plt, style="r--")

                # Draw arrows indicating road direction
                if lane.centerline.length >= 40:
                    pts = lane.centerline.pointsSeparatedBy(20)
                else:
                    pts = [lane.centerline.pointAlongBy(0.5, normalized=True)]
                hs = [lane.centerline.orientation[pt].yaw for pt in pts]
                x, y, _ = zip(*pts)
                u = [math.cos(h + (math.pi / 2)) for h in hs]
                v = [math.sin(h + (math.pi / 2)) for h in hs]
                plt.quiver(
                    x,
                    y,
                    u,
                    v,
                    pivot="middle",
                    headlength=4.5,
                    scale=0.06,
                    units="dots",
                    color="#A0A0A0",
                )

            if showCurbArrows:
                for lg in road.laneGroups:
                    curb = lg.curb
                    if curb.length >= 40:
                        cpts = curb.pointsSeparatedBy(20)
                    else:
                        cpts = [curb.pointAlongBy(0.5, normalized=True)]
                    chs = [curb.orientation[pt].yaw for pt in cpts]
                    cx, cy, _ = zip(*cpts)
                    cu = [math.cos(h + (math.pi / 2)) for h in chs]
                    cv = [math.sin(h + (math.pi / 2)) for h in chs]
                    plt.quiver(
                        cx,
                        cy,
                        cu,
                        cv,
                        pivot="middle",
                        headlength=4.5,
                        scale=0.06,
                        units="dots",
                        color="#606060",
                    )

        for lane in self.lanes:  # draw centerlines of all lanes (including connecting)
            lane.centerline.show(plt, style=":", color="#A0A0A0")
        self.intersectionRegion.show(plt, style="g")
        if labelIncomingLanes:
            for intersection in self.intersections:
                for i, lane in enumerate(intersection.incomingLanes):
                    x, y, _ = lane.centerline[-1]
                    plt.plot([x], [y], "*b")
                    plt.annotate(str(i), (x, y))
