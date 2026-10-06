"""Driving-domain tests on left-hand traffic demo maps."""

import inspect
from pathlib import Path

import pytest

from tests.utils import compileScenic, sampleScene

pytestmark = pytest.mark.filterwarnings(
    "ignore::scenic.formats.opendrive.OpenDriveWarning"
)

LHT = Path(__file__).resolve().parents[3] / "assets" / "maps" / "demo" / "lht"

ALL_MAPS = (
    "01_two_lane_oneway.xodr",
    "02_three_lane_speeds.xodr",
    "03_two_way.xodr",
)

template = inspect.cleandoc(
    """
    param map = r'{map}'
    param map_options = dict(useCache=False)
    model scenic.domains.driving.model
    """
)

basicScenario = inspect.cleandoc(
    """
    lane = Uniform(*network.lanes)
    ego = new Car in lane
    follower = new Car on visible lane.centerline
    """
)

fasterLaneScenario = inspect.cleandoc(
    """
    candidates = [lane for lane in network.lanes if lane.sections[0]._fasterLane]
    require len(candidates) > 0
    lane = Uniform(*candidates)
    ego = new Car in lane
    other = new Car in lane.sections[0].fasterLane.lane
    """
)

slowerLaneScenario = inspect.cleandoc(
    """
    candidates = [lane for lane in network.lanes if lane.sections[0]._slowerLane]
    require len(candidates) > 0
    lane = Uniform(*candidates)
    ego = new Car in lane
    other = new Car in lane.sections[0].slowerLane.lane
    """
)


def _compile(path, code):
    preamble = template.format(map=path)
    return compileScenic(preamble + "\n" + code, mode2D=True)


def _sample_two_car_scene(name, scenario_code):
    scenario = _compile(LHT / name, scenario_code)
    scene = sampleScene(scenario, maxIterations=1000)
    assert len(scene.objects) == 2
    ego, other = scene.objects
    assert ego is scene.egoObject
    return ego, other


@pytest.mark.parametrize("name", ALL_MAPS)
def test_lht_basic_car_placement(name):
    """Ego and a second car can be placed on the same sampled lane."""
    ego, follower = _sample_two_car_scene(name, basicScenario)

    assert ego.lane is follower.lane
    assert ego.laneSection.lane is follower.laneSection.lane
    assert follower.lane.containsPoint(follower.position)


@pytest.mark.parametrize("name", ALL_MAPS)
def test_lht_faster_lane_placement(name):
    """Ego sits on a slower lane; other is placed on its fasterLane neighbor."""
    ego, other = _sample_two_car_scene(name, fasterLaneScenario)

    ego_sec = ego.laneSection
    assert ego_sec._fasterLane is not None
    assert other.lane is ego_sec.fasterLane.lane
    assert other.lane is not ego.lane
    assert other.laneSection.lane is ego_sec.fasterLane.lane


@pytest.mark.parametrize("name", ALL_MAPS)
def test_lht_slower_lane_placement(name):
    """Ego sits on a faster lane; other is placed on its slowerLane neighbor."""
    ego, other = _sample_two_car_scene(name, slowerLaneScenario)

    ego_sec = ego.laneSection
    assert ego_sec._slowerLane is not None
    assert other.lane is ego_sec.slowerLane.lane
    assert other.lane is not ego.lane
    assert other.laneSection.lane is ego_sec.slowerLane.lane
