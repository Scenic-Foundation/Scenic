from pathlib import Path

import pytest

from scenic.core.distributions import RejectionException
from scenic.domains.driving.roads import Intersection, Network
from tests.domains.driving.conftest import mapFolder

# Suppress all warnings from OpenDRIVE parser
pytestmark = pytest.mark.filterwarnings(
    "ignore::scenic.formats.opendrive.OpenDriveWarning"
)


def test_network_invalid():
    with pytest.raises(ValueError):
        Network.fromFile("blogobloggo_zoggle.foobar")  # unknown file extension
    with pytest.raises(FileNotFoundError):
        Network.fromFile("blogobloggo_zoggle")  # search all known formats


@pytest.mark.graphical
def test_show2D(network):
    import matplotlib.pyplot as plt

    network.show(labelIncomingLanes=True, showCurbArrows=True)

    plt.show(block=False)
    plt.close()


def test_element_tolerance(cached_maps, pytestconfig):
    path = cached_maps[str(mapFolder / "CARLA" / "Town01.xodr")]
    tol = 0.05
    network = Network.fromFile(path, tolerance=tol)
    drivable = network.drivableRegion
    toofar = drivable.buffer(2 * tol).difference(drivable.buffer(1.5 * tol))
    top_level_region = drivable.union(network.shoulderRegion).union(
        network.sidewalkRegion
    )
    outside_top_level = top_level_region.buffer(2 * tol).difference(
        top_level_region.buffer(1.5 * tol)
    )
    road = network.roads[0]
    nearby = road.region.buffer(tol).difference(road)
    rounds = 30 if pytestconfig.getoption("--fast") else 300
    for i in range(rounds):
        pt = None
        while not pt or pt in drivable:
            pt = nearby.uniformPointInner()
        assert network.elementAt(pt) is not None
        assert network.roadAt(pt) is not None
        pt = toofar.uniformPointInner()
        assert network.roadAt(pt) is None
        with pytest.raises(RejectionException):
            network.roadAt(pt, reject=True)
        pt = outside_top_level.uniformPointInner()
        assert network.elementAt(pt) is None
        with pytest.raises(RejectionException):
            network.elementAt(pt, reject=True)


def test_orientation_consistency(network):
    for i in range(30):
        pt = network.drivableRegion.uniformPointInner()
        dirs = network.nominalDirectionsAt(pt)
        elem = network.elementAt(pt)
        if isinstance(elem, Intersection):
            assert len(dirs) >= 1
            connectors = set()
            for maneuver in elem.maneuvers:
                cl = maneuver.connectingLane
                if cl.containsPoint(pt):
                    assert pytest.approx(cl.orientation[pt]) in dirs
                    connectors.add(cl)
            if not connectors:
                # Not on any connecting lane; orientation should be given by
                # whichever one is closest.
                man = min(
                    elem.maneuvers, key=lambda man: man.connectingLane.distanceTo(pt)
                )
                assert pytest.approx(man.connectingLane.orientation[pt]) in dirs
            else:
                lane = network.laneAt(pt)
                assert lane in connectors
        else:
            assert len(dirs) == 1
            d = dirs[0]
            road = network.roadAt(pt)
            assert road is elem
            assert road.orientation[pt] == pytest.approx(d)
            roadSec = road.sectionAt(pt)
            assert roadSec.orientation[pt] == pytest.approx(d)
            group = network.laneGroupAt(pt)
            assert road.laneGroupAt(pt) is group
            assert group.orientation[pt] == pytest.approx(d)
            lane = network.laneAt(pt)
            assert road.laneAt(pt) is lane
            assert lane.orientation[pt] == pytest.approx(d)
            laneSec = network.laneSectionAt(pt)
            assert road.laneSectionAt(pt) is laneSec
            assert laneSec.orientation[pt] == pytest.approx(d)


def test_linkage(network):
    for road in network.roads:
        if not road.forwardLanes and not road.backwardLanes:
            continue  # Ignore roads without drivable lanes.
        assert road.is1Way == (not (road.forwardLanes and road.backwardLanes))
        seenLanes = set()

        def checkGroup(group):
            assert group.road is road
            if group._sidewalk:
                sidewalk = group._sidewalk
                assert group.sidewalk is group._sidewalk
                assert sidewalk.road is road
                for crossing in sidewalk.crossings:
                    assert crossing.parent is road
                    assert sidewalk in (crossing.startSidewalk, crossing.endSidewalk)
            else:
                with pytest.raises(RejectionException):
                    group.sidewalk
            if group._shoulder:
                shoulder = group._shoulder
                assert group.shoulder is shoulder
                assert shoulder.road is road
            else:
                with pytest.raises(RejectionException):
                    group.shoulder
            if group._bikeLane:
                bikeLane = group._bikeLane
                assert group.bikeLane is bikeLane
                assert bikeLane.road is road
            else:
                with pytest.raises(RejectionException):
                    group.bikeLane
            for lane in group.lanes:
                assert lane not in seenLanes
                seenLanes.add(lane)
                assert lane.group is group
                assert lane.road is road
                for section in lane.sections:
                    assert section.lane is lane
                    assert section.group is group
                    assert section.road is road
                    assert section.isForward == (group is road.forwardLanes)
                    for i in range(30):
                        pt = section.uniformPointInner()
                        assert lane.sectionAt(pt) is section
                    fastSlow = (section._fasterLane, section._slowerLane)
                    leftRight = (section._laneToLeft, section._laneToRight)
                    if section._fasterLane:
                        assert section.fasterLane is section._fasterLane
                        assert section.fasterLane in leftRight
                    if section._slowerLane:
                        assert section.slowerLane is section._slowerLane
                        assert section.slowerLane in leftRight
                    if section._laneToLeft:
                        left = section._laneToLeft
                        assert section.laneToLeft is left
                        assert section.shiftedBy(1) is left
                        assert left is not section._laneToRight
                        if section.isForward == left.isForward:
                            assert fastSlow.count(left) == 1
                            assert left.laneToRight is section
                            assert left.shiftedBy(-1) is section
                        else:
                            assert left.laneToLeft is section
                            assert left.shiftedBy(1) is section
                    else:
                        with pytest.raises(RejectionException):
                            section.laneToLeft
                    if section._laneToRight:
                        right = section._laneToRight
                        assert section.laneToRight is right
                        assert section.shiftedBy(-1) is right
                        assert right is not section._laneToLeft
                        if section.isForward == right.isForward:
                            assert fastSlow.count(right) == 1
                            assert right.laneToLeft is section
                            assert right.shiftedBy(1) is section
                        else:
                            assert right.laneToRight is section
                            assert right.shiftedBy(-1) is section
                    else:
                        with pytest.raises(RejectionException):
                            section.laneToRight
                for maneuver in lane.maneuvers:
                    assert maneuver.startLane is lane
                for i in range(30):
                    pt = lane.uniformPointInner()
                    assert group.laneAt(pt) is lane

        if road.forwardLanes:
            checkGroup(road.forwardLanes)
            assert road.forwardLanes._opposite is road.backwardLanes
            if road.backwardLanes:
                assert road.forwardLanes.opposite is road.backwardLanes
        else:
            with pytest.raises(RejectionException):
                road.backwardLanes.opposite
        if road.backwardLanes:
            checkGroup(road.backwardLanes)
            assert road.backwardLanes._opposite is road.forwardLanes
            if road.forwardLanes:
                assert road.backwardLanes.opposite is road.forwardLanes
        else:
            with pytest.raises(RejectionException):
                road.forwardLanes.opposite
        assert set(road.lanes) == seenLanes

    for intersection in network.intersections:
        allManeuvers = intersection.maneuvers
        allConnecting = set(man.connectingLane for man in allManeuvers)
        for incoming in intersection.incomingLanes:
            assert incoming.road in intersection.roads
            assert incoming.successor in allConnecting
            maneuvers = incoming.maneuvers
            for maneuver in maneuvers:
                assert maneuver in allManeuvers
                assert maneuver.startLane is incoming
                assert maneuver.intersection is intersection
                connecting = maneuver.connectingLane
                assert connecting is not None
                assert connecting in allConnecting
                outgoing = connecting.successor
                assert outgoing in intersection.outgoingLanes
                assert outgoing.road in intersection.roads
                for conf in maneuver.conflictingManeuvers:
                    assert conf is not maneuver
                    assert connecting.intersects(conf.connectingLane)
                for rev in maneuver.reverseManeuvers:
                    assert rev is not maneuver
                    assert rev.startLane.road is maneuver.endLane.road
                    assert rev.endLane.road is maneuver.startLane.road


def test_shoulder(network):
    sh = network.shoulders[0]
    for _ in range(30):
        pt = sh.uniformPointInner()
        assert network.shoulderAt(pt) is sh
        assert network.elementAt(pt) is sh
        so_yaw = sh.orientation[pt].yaw
        rd_yaw = network.roadDirection[pt].yaw
        assert rd_yaw == pytest.approx(so_yaw)
        dirs = network.nominalDirectionsAt(pt)
        assert len(dirs) == 1
        assert dirs[0].yaw == pytest.approx(so_yaw)


def test_sidewalk(network):
    sw = network.sidewalks[0]
    for _ in range(30):
        pt = sw.uniformPointInner()
        assert network.sidewalkAt(pt) is sw
        assert network.elementAt(pt) is sw


# --- Tests for cached network pickles ---


def _read_options_digest(pickled_path: Path) -> bytes:
    """Return the optionsDigest bytes from a cached .snet header.

    Header layout:
      - 4 bytes: version
      - 64 bytes: originalDigest
      - 8 bytes: optionsDigest
    """
    with open(pickled_path, "rb") as f:
        header = f.read(76)  # 4 + 64 + 8
    return header[68:76]  # skip version (4) + originalDigest (64)


def test_dump_pickle_from_pickle(tmp_path, network):
    """dumpPickle/fromPickle should rebuild the Network when digests match"""
    digest = b"x" * 64  # fake original map digest
    options_digest = b"y" * 8  # fake map options digest
    path = tmp_path / "net.snet"

    # Write the cache using the new format.
    network.dumpPickle(path, digest, options_digest)

    # Read it back with matching digests.
    loaded = Network.fromPickle(
        path,
        originalDigest=digest,
        optionsDigest=options_digest,
    )

    # Sanity checks
    assert isinstance(loaded, Network)
    assert loaded.elements.keys() == network.elements.keys()


def test_from_pickle_digest_mismatch(tmp_path, network):
    """fromPickle should reject files whose digests don't match."""
    digest = b"x" * 64
    options_digest = b"y" * 8
    path = tmp_path / "net.snet"

    network.dumpPickle(path, digest, options_digest)

    wrong_digest = b"z" * 64
    wrong_options = b"w" * 8

    # Wrong originalDigest -> DigestMismatchError.
    with pytest.raises(Network.DigestMismatchError):
        Network.fromPickle(
            path,
            originalDigest=wrong_digest,
            optionsDigest=options_digest,
        )

    # Wrong optionsDigest -> DigestMismatchError.
    with pytest.raises(Network.DigestMismatchError):
        Network.fromPickle(
            path,
            originalDigest=digest,
            optionsDigest=wrong_options,
        )

    # No digests supplied -> allowed (standalone .snet use case).
    Network.fromPickle(path)


def test_cache_regenerated_when_options_change(cached_maps):
    """Changing map options should invalidate and rewrite the cached .snet file."""
    # Get the temp copy of Town01 from cached_maps.
    xodr_loc = cached_maps[str(mapFolder / "CARLA" / "Town01.xodr")]
    xodr_path = Path(str(xodr_loc))
    pickled_path = xodr_path.with_suffix(Network.pickledExt)

    # First load: cache with one tolerance value
    Network.fromFile(
        xodr_path,
        useCache=True,
        writeCache=True,
        tolerance=0.05,
    )
    options_digest1 = _read_options_digest(pickled_path)

    # Second load: same map, different tolerance.
    Network.fromFile(
        xodr_path,
        useCache=True,
        writeCache=True,
        tolerance=0.123,
    )
    options_digest2 = _read_options_digest(pickled_path)

    # If the options changed, the cache header should also change.
    assert options_digest1 != options_digest2
