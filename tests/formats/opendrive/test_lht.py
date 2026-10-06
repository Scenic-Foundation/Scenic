"""Left-hand traffic OpenDRIVE maps — centerlines and faster/slower lanes."""

from pathlib import Path

import pytest

from scenic.core.distributions import RejectionException
from scenic.domains.driving.roads import Network

pytestmark = pytest.mark.filterwarnings(
    "ignore::scenic.formats.opendrive.OpenDriveWarning"
)

DEMO = Path(__file__).resolve().parents[3] / "assets" / "maps" / "demo" / "lht"

ALL_MAPS = (
    "01_two_lane_oneway.xodr",
    "02_three_lane_speeds.xodr",
    "03_two_way.xodr",
)


def load(name):
    return Network.fromFile(DEMO / name, useCache=False)


def section_by_id(network, od_id):
    for road in network.roads:
        for sec in road.sections:
            if od_id in sec.lanesByOpenDriveID:
                return sec.lanesByOpenDriveID[od_id]
    raise AssertionError(f"no lane section with OpenDRIVE id {od_id}")


def centerline_delta(lane):
    pts = lane.centerline.points
    return pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]


def carriageway_groups(road):
    if road.forwardLanes:
        yield road.forwardLanes
    if road.backwardLanes:
        yield road.backwardLanes


def assert_faster_slower(network, sec, *, faster_id, slower_id):
    faster = section_by_id(network, faster_id) if faster_id else None
    slower = section_by_id(network, slower_id) if slower_id else None
    assert sec._fasterLane is faster
    assert sec._slowerLane is slower
    if faster_id is None:
        with pytest.raises(RejectionException):
            _ = sec.fasterLane
    else:
        assert sec.fasterLane is faster
    if slower_id is None:
        with pytest.raises(RejectionException):
            _ = sec.slowerLane
    else:
        assert sec.slowerLane is slower


@pytest.mark.parametrize(
    "name, n_lanes, oneway",
    [
        ("01_two_lane_oneway.xodr", 2, True),
        ("02_three_lane_speeds.xodr", 3, True),
        ("03_two_way.xodr", 4, False),
    ],
)
def test_lht_network_structure(name, n_lanes, oneway):
    network = load(name)
    road = network.roads[0]

    assert len(network.roads) == 1
    assert len(network.lanes) == n_lanes
    assert road.is1Way is oneway

    for lane in network.lanes:
        assert not lane.polygon.is_empty
        assert lane.polygon.is_valid
        for sec in lane.sections:
            assert sec.containsRegion(sec.centerline, tolerance=0.5)
            assert sec.containsRegion(sec.leftEdge, tolerance=0.5)
            assert sec.containsRegion(sec.rightEdge, tolerance=0.5)


@pytest.mark.parametrize("name", ALL_MAPS)
def test_centerlines_follow_traffic_flow(name):
    """Centerlines point with traffic; orientation matches flow at lane midpoints."""
    road = load(name).roads[0]

    for group in carriageway_groups(road):
        deltas = [centerline_delta(lane) for lane in group.lanes]
        signs = [1 if dx > 0 else -1 if dx < 0 else 0 for dx, _ in deltas]
        assert 0 not in signs, f"{name}: zero-length centerline"
        assert len(set(signs)) == 1, f"{name}: mixed centerline directions {deltas}"

        for lane in group.lanes:
            pt = lane.centerline.pointAlongBy(0.5, normalized=True)
            dirs = road.network.nominalDirectionsAt(pt)
            assert pytest.approx(lane.orientation[pt]) in dirs
            assert lane.containsPoint(pt)

    if not road.is1Way:
        fwd = centerline_delta(road.forwardLanes.lanes[0])[0]
        bwd = centerline_delta(road.backwardLanes.lanes[0])[0]
        assert fwd * bwd < 0


def test_two_lane_faster_slower_toward_median():
    network = load("01_two_lane_oneway.xodr")
    assert_faster_slower(network, section_by_id(network, 2), faster_id=1, slower_id=None)
    assert_faster_slower(network, section_by_id(network, 1), faster_id=None, slower_id=2)


def test_three_lane_faster_slower_chain():
    network = load("02_three_lane_speeds.xodr")
    assert_faster_slower(network, section_by_id(network, 3), faster_id=2, slower_id=None)
    assert_faster_slower(network, section_by_id(network, 2), faster_id=1, slower_id=3)
    assert_faster_slower(network, section_by_id(network, 1), faster_id=None, slower_id=2)


def test_two_way_faster_slower_each_carriageway():
    network = load("03_two_way.xodr")
    assert_faster_slower(network, section_by_id(network, 2), faster_id=1, slower_id=None)
    assert_faster_slower(network, section_by_id(network, 1), faster_id=None, slower_id=2)
    assert_faster_slower(
        network, section_by_id(network, -2), faster_id=-1, slower_id=None
    )
    assert_faster_slower(
        network, section_by_id(network, -1), faster_id=None, slower_id=-2
    )


@pytest.mark.parametrize("name", ALL_MAPS)
def test_lane_adjacency_helpers(name):
    """shiftedBy, faster/slower neighbors, and same-direction constraints."""
    network = load(name)
    for road in network.roads:
        for sec in road.sections:
            for lane_sec in sec.lanes:
                neighbors = {lane_sec._laneToLeft, lane_sec._laneToRight} - {None}
                if lane_sec._laneToLeft:
                    assert lane_sec.shiftedBy(1) is lane_sec._laneToLeft
                    if lane_sec._laneToLeft.isForward == lane_sec.isForward:
                        assert lane_sec._laneToLeft.shiftedBy(-1) is lane_sec
                if lane_sec._laneToRight:
                    assert lane_sec.shiftedBy(-1) is lane_sec._laneToRight
                    if lane_sec._laneToRight.isForward == lane_sec.isForward:
                        assert lane_sec._laneToRight.shiftedBy(1) is lane_sec
                if lane_sec._fasterLane:
                    assert lane_sec._fasterLane in neighbors
                    assert lane_sec._fasterLane.isForward == lane_sec.isForward
                if lane_sec._slowerLane:
                    assert lane_sec._slowerLane in neighbors
                    assert lane_sec._slowerLane.isForward == lane_sec.isForward

    if name == "03_two_way.xodr":
        road = network.roads[0]
        assert road.forwardLanes._opposite is road.backwardLanes
        assert road.backwardLanes.opposite is road.forwardLanes
