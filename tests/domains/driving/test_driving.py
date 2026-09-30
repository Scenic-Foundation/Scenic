import inspect
import os
import shutil

import pytest

from scenic.core.distributions import RejectionException
from scenic.core.errors import InvalidScenarioError
from scenic.core.geometry import TriangulationError
from scenic.domains.driving.roads import Network
from tests.utils import compileScenic, pickle_test, sampleEgo, sampleScene, tryPickling

# Suppress all warnings from OpenDRIVE parser
pytestmark = pytest.mark.filterwarnings(
    "ignore::scenic.formats.opendrive.OpenDriveWarning"
)

template = inspect.cleandoc(
    """
    param map = r'{map}'
    param map_options = dict(useCache={cache})
    model scenic.domains.driving.model
"""
)

basicScenario = inspect.cleandoc(
    """
    lane = Uniform(*network.lanes)
    ego = new Car in lane
    new Car on visible lane.centerline
"""
)

from tests.domains.driving.conftest import map_params, mapFolder


def compileDrivingScenario(
    cached_maps, code="", useCache=True, path=None, mode2D=True, params={}
):
    if not path:
        path = mapFolder / "CARLA" / "Town01.xodr"
    path = cached_maps[str(path)]
    preamble = template.format(map=path, cache=useCache)
    whole = preamble + "\n" + inspect.cleandoc(code)
    return compileScenic(whole, mode2D=mode2D, params=params)


def test_driving_2D_map(cached_maps):
    compileDrivingScenario(
        cached_maps,
        code=basicScenario,
        useCache=False,
        mode2D=False,
        params={"use2DMap": True},
    )


def test_driving_3D(cached_maps):
    with pytest.raises(RuntimeError):
        compileDrivingScenario(
            cached_maps, code=basicScenario, useCache=False, mode2D=False
        )


@pytest.mark.slow
@pytest.mark.parametrize("path", map_params)
def test_opendrive(path, cached_maps):
    try:
        # First, try the original .xodr file
        scenario = compileDrivingScenario(
            cached_maps, path=path, code=basicScenario, useCache=False
        )
        sampleScene(scenario, maxIterations=1000)
        # Second, try the cached version of the network
        scenario = compileDrivingScenario(
            cached_maps, path=path, code=basicScenario, useCache=True
        )
        sampleScene(scenario, maxIterations=1000)
    except TriangulationError:
        pytest.skip("need better triangulation library to run this test")


def test_elements_at(cached_maps):
    scenario = compileDrivingScenario(
        cached_maps,
        """
        ego = new Car
        posTuple = (ego.position.x, ego.position.y)
        # functions should accept Points, Vectors, and tuples
        for spot in (ego, ego.position, posTuple):
            param element = network.elementAt(spot)
            param road = network.roadAt(spot)
            param lane = network.laneAt(spot)
            param laneSection = network.laneSectionAt(spot)
            param laneGroup = network.laneGroupAt(spot)
            param crossing = network.crossingAt(spot)
            param intersection = network.intersectionAt(spot)
    """,
    )
    scene = sampleScene(scenario, maxIterations=1000)
    ego = scene.egoObject
    for param in (
        "element",
        "road",
        "lane",
        "laneSection",
        "laneGroup",
        "crossing",
        "intersection",
    ):
        val = scene.params[param]
        if val is None:
            with pytest.raises(RejectionException):
                getattr(ego, param)
        else:
            assert val is getattr(ego, param), param


def test_intersection(cached_maps):
    scenario = compileDrivingScenario(
        cached_maps,
        """
        intersection = Uniform(*network.intersections)
        lane = Uniform(*intersection.incomingLanes)
        maneuver = Uniform(*lane.maneuvers)
        ego = new Car on maneuver.connectingLane.centerline
    """,
    )
    for i in range(20):
        ego = sampleEgo(scenario, maxIterations=1000)
        intersection = ego.intersection
        assert intersection is not None
        assert intersection.is3Way == (len(intersection.roads) == 3)
        assert intersection.is4Way == (len(intersection.roads) == 4)
        assert intersection.isSignalized == bool(intersection.signals)
        network = intersection.network
        assert network.elementAt(ego) is intersection
        directions = intersection.nominalDirectionsAt(ego)
        assert directions == network.nominalDirectionsAt(ego)
        assert any(
            ego.heading == pytest.approx(direction.yaw) for direction in directions
        )
        maneuvers = intersection.maneuversAt(ego)
        lane = ego.lane
        assert any(man.connectingLane is lane for man in maneuvers)


def test_curb(cached_maps):
    scenario = compileDrivingScenario(
        cached_maps,
        """
        ego = new Car
        spot = new OrientedPoint on visible curb
        new Car left of spot by 0.25
    """,
    )
    ego = sampleEgo(scenario, maxIterations=1000)
    directions = ego.element.network.nominalDirectionsAt(ego)
    assert any(ego.heading == pytest.approx(direction.yaw) for direction in directions)


@pytest.mark.slow
def test_caching(tmpdir):
    """Test caching of road networks.

    In particular, make sure that links between network elements and maneuvers
    are properly reconnected after unpickling.
    """
    origMap = mapFolder / "CARLA" / "Town01.xodr"
    path = os.path.join(tmpdir, "map.xodr")
    cachedPath = os.path.join(tmpdir, "map" + Network.pickledExt)
    noExtPath = os.path.join(tmpdir, "map")
    shutil.copyfile(origMap, path)
    opts = (
        (False, path),
        (True, cachedPath),
        (True, noExtPath),
        (True, path),
    )
    for useCache, path in opts:
        scenario = compileScenic(
            f"""
            param map = r'{path}'
            param map_options = dict(useCache={useCache})
            model scenic.domains.driving.model
            lanes = filter(lambda l: l._successor, network.lanes)
            lane = Uniform(*lanes)
            ego = new Car on lane, with foo lane.network.lanes
            new Car on ego.lane.successor.centerline, with requireVisible False
            new Car on ego.lane.maneuvers[0].endLane.centerline, with requireVisible False
        """,
            mode2D=True,
        )
        sampleScene(scenario, maxIterations=1000)


@pickle_test
@pytest.mark.slow
def test_pickle(cached_maps):
    scenario = compileDrivingScenario(
        cached_maps,
        """
        ego = new Car with behavior FollowLaneBehavior(target_speed=Range(10, 15))
        new Pedestrian on visible sidewalk
    """,
    )
    unpickled = tryPickling(scenario)
    scene = sampleScene(unpickled, maxIterations=1000)
    tryPickling(scene)


def test_invalid_road_scenario(cached_maps):
    with pytest.raises(InvalidScenarioError):
        scenario = compileDrivingScenario(
            cached_maps,
            """
            ego = new Car at 80.6354425964952@-327.5431187869811
            param foo = ego.oppositeLaneGroup.sidewalk
            """,
        )

    with pytest.raises(InvalidScenarioError):
        # Set regionContainedIn to everywhere to hit driving domain specific code
        # instead of high level not contained in workspace rejection.
        scenario = compileDrivingScenario(
            cached_maps,
            """
            ego = new Car at 10000@10000, with regionContainedIn everywhere
            param foo = ego.lane
            """,
        )
