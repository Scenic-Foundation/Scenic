import xml.etree.ElementTree as ET

import pytest

from scenic.formats.opendrive.xodr_parser import OpenDriveWarning, speed_to_mps

from .conftest import TWO_LANE_SECTIONS, lane_xml, parse_scenic_network


def test_type_speeds_are_sorted_and_looked_up_along_the_road(tmp_path):
    road_extras = (
        '<type s="10" type="town"><speed max="30" unit="m/s"/></type>'
        '<type s="0" type="town"><speed max="45" unit="m/s"/></type>'
    )
    network = parse_scenic_network(tmp_path, road_extras=road_extras)
    lane_section = network.elements["road7"].lanes[0].sections[0]
    assert lane_section.speedLimitAt(2.0) == pytest.approx(45.0)
    assert lane_section.speedLimitAt(12.0) == pytest.approx(30.0)


def test_lane_speed_ranges_on_scenic_lane_section(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        lanes_xml=lane_xml(-1, speeds=((0, 20, "m/s"), (5, 30, "m/s"))),
    )
    lane_section = network.elements["road7"].sections[0].lanes[0]

    assert lane_section.speedLimit == pytest.approx(20.0)
    assert lane_section.speedLimitRanges == (
        (0.0, 20.0),
        (5.0, 30.0),
    )
    assert lane_section.speedLimitAt(2.0) == pytest.approx(20.0)
    assert lane_section.speedLimitAt(7.0) == pytest.approx(30.0)

    slow_point = lane_section.centerline.pointAlongBy(2.0)
    fast_point = lane_section.centerline.pointAlongBy(7.0)
    assert network.speedLimitAt(slow_point) == pytest.approx(20.0)
    assert network.speedLimitAt(fast_point) == pytest.approx(30.0)
    assert network.speedLimitAt((1000.0, 1000.0)) is None


def test_unspecified_lane_stretch_uses_road_speed(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        lanes_xml=lane_xml(-1, speeds=((5, 30, "m/s"),)),
        road_extras='<type s="0" type="town"><speed max="20" unit="m/s"/></type>',
    )
    lane_section = network.elements["road7"].sections[0].lanes[0]
    assert lane_section.speedLimitRanges == (
        (0.0, 20.0),
        (5.0, 30.0),
    )
    assert lane_section.speedLimitAt(2.0) == pytest.approx(20.0)
    assert lane_section.speedLimitAt(7.0) == pytest.approx(30.0)


def test_lane_speed_ranges_on_backward_lane(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        lanes_xml=lane_xml(1, speeds=((0, 20, "m/s"), (5, 30, "m/s"))),
        lane_side="left",
    )
    lane_section = network.elements["road7"].sections[0].lanes[0]
    assert lane_section.speedLimitRanges == (
        (0.0, 20.0),
        (5.0, 30.0),
    )
    assert lane_section.speedLimitAt(2.0) == pytest.approx(20.0)
    assert lane_section.speedLimitAt(7.0) == pytest.approx(30.0)


def test_lane_speed_ranges_on_curved_road(tmp_path):
    plan_view = """<planView>
      <geometry s="0" x="0" y="0" hdg="0" length="20">
        <arc curvature="0.05"/>
      </geometry>
    </planView>"""
    network = parse_scenic_network(
        tmp_path,
        plan_view=plan_view,
        lanes_xml=lane_xml(-1, speeds=((0, 20, "m/s"), (10, 30, "m/s"))),
    )
    lane_section = network.elements["road7"].sections[0].lanes[0]
    assert lane_section.speedLimitRanges == (
        (0.0, 20.0),
        (10.0, 30.0),
    )
    before = lane_section.centerline.pointAlongBy(9.0)
    after = lane_section.centerline.pointAlongBy(11.0)
    assert network.speedLimitAt(before) == pytest.approx(20.0)
    assert network.speedLimitAt(after) == pytest.approx(30.0)


def test_network_speed_limit_at_uniform_section(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        road_extras='<type s="0" type="town"><speed max="50" unit="km/h"/></type>',
    )
    point = network.elements["road7"].lanes[0].sections[0].centerline.pointAlongBy(5.0)
    assert network.speedLimitAt(point) == pytest.approx(50 / 3.6)


def test_deprecated_uniform_speed_limit_is_single_range(tmp_path):
    lane_section = parse_scenic_network(tmp_path).elements["road7"].lanes[0].sections[0]
    lane_section.speedLimit = 20.0
    lane_section.speedLimitRanges = ()
    assert lane_section.speedLimitAt(-1.0) == pytest.approx(20.0)
    assert lane_section.speedLimitAt(10.0) == pytest.approx(20.0)


def test_no_limit_speed_sets_ranges_with_none(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        road_extras='<type s="0" type="motorway"><speed max="no limit" unit="km/h"/></type>',
    )
    lane_section = network.elements["road7"].lanes[0].sections[0]
    assert lane_section.speedLimit is None
    assert lane_section.speedLimitRanges == ((0.0, None),)
    point = lane_section.centerline.pointAlongBy(5.0)
    assert network.speedLimitAt(point) is None


def test_unlimited_section_inherits_scalar_road_minimum(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        lane_sections_xml=TWO_LANE_SECTIONS,
        road_extras=(
            '<type s="0" type="town"><speed max="20" unit="m/s"/></type>'
            '<type s="10" type="town"><speed max="no limit" unit="m/s"/></type>'
        ),
    )
    limited_section, unlimited_section = network.elements["road7"].sections
    assert limited_section.speedLimit == pytest.approx(20.0)
    assert unlimited_section.speedLimit == pytest.approx(20.0)
    unlimited_lane_section = unlimited_section.lanes[0]
    assert unlimited_lane_section.speedLimit == pytest.approx(20.0)
    assert unlimited_lane_section.speedLimitRanges == ((0.0, None),)


def test_lane_speed_limit_overrides_when_higher(tmp_path):
    network = parse_scenic_network(
        tmp_path,
        lanes_xml="\n".join(
            (
                lane_xml(-1),
                lane_xml(-2, speeds=((0, 80, "km/h"),)),
                lane_xml(-3, type_="onRamp", speeds=((0, 40, "km/h"),)),
            )
        ),
        road_extras='<type s="0" type="town"><speed max="50" unit="km/h"/></type>',
    )
    road = network.elements["road7"]
    road_limit = 50 / 3.6
    limits = {
        section.openDriveID: section.speedLimit for section in road.sections[0].lanes
    }
    assert road.speedLimit == pytest.approx(road_limit)
    assert limits[-1] == pytest.approx(road_limit)
    assert limits[-2] == pytest.approx(80 / 3.6)
    assert limits[-3] == pytest.approx(40 / 3.6)


def _speed_elem(max_value, unit=None):
    attrs = f'max="{max_value}"'
    if unit is not None:
        attrs += f' unit="{unit}"'
    return ET.fromstring(f"<speed {attrs}/>")


def test_speed_to_mps_unit_conversions():
    assert speed_to_mps(_speed_elem(36, "km/h")) == pytest.approx(10.0)
    assert speed_to_mps(_speed_elem(10, "m/s")) == pytest.approx(10.0)
    assert speed_to_mps(_speed_elem(100, "mph")) == pytest.approx(44.704)
    assert speed_to_mps(_speed_elem(15)) == pytest.approx(15.0)


def test_speed_to_mps_unlimited_returns_none():
    assert speed_to_mps(_speed_elem("no limit", "km/h")) is None
    assert speed_to_mps(_speed_elem("undefined")) is None


def test_speed_to_mps_rejects_unknown_unit():
    with pytest.raises(ValueError, match="unsupported speed unit"):
        speed_to_mps(_speed_elem(50, "furlongs/fortnight"))


def test_section_spanning_multiple_speeds_warns(tmp_path):
    road_extras = (
        '<type s="0" type="town"><speed max="50" unit="km/h"/></type>'
        '<type s="10" type="town"><speed max="30" unit="km/h"/></type>'
    )
    with pytest.warns(OpenDriveWarning, match="spans multiple speed limits"):
        parse_scenic_network(tmp_path, road_extras=road_extras)
