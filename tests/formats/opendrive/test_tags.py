from pathlib import Path

from scenic.formats.opendrive.xodr_parser import Junction, RoadMap

from .conftest import (
    TWO_LANE_SECTIONS,
    assert_road_tags_propagated_to_groups,
    lane_xml,
    parse_scenic_network,
)

JUNCTION_XODR = Path(__file__).with_name("junction_tags.xodr")


def test_map_tags_propagate_to_lane_hierarchy(tmp_path):
    road_extras = '<type s="0" type="motorway"><speed max="120" unit="km/h"/></type>'
    road = parse_scenic_network(tmp_path, road_extras=road_extras).roads[0]
    assert road.tags == frozenset({"motorway"})
    assert_road_tags_propagated_to_groups(road)
    assert road.sections[0].tags == road.tags
    assert road.lanes[0].tags == frozenset({"driving"})
    assert road.lanes[0].sections[0].tags == road.lanes[0].tags


def test_map_tags_from_all_type_segments_propagate(tmp_path):
    road_extras = (
        '<type s="0" type="motorway"><speed max="120" unit="km/h"/></type>'
        '<type s="10" type="town"><speed max="50" unit="km/h"/></type>'
    )
    road = parse_scenic_network(tmp_path, road_extras=road_extras).roads[0]
    assert road.tags == frozenset({"motorway", "town"})
    assert_road_tags_propagated_to_groups(road)
    assert road.sections[0].tags == road.tags
    assert road.lanes[0].tags == frozenset({"driving"})


def test_road_section_tags_follow_type_segments(tmp_path):
    road = parse_scenic_network(
        tmp_path,
        lane_sections_xml=TWO_LANE_SECTIONS,
        road_extras='<type s="0" type="motorway"/><type s="10" type="town"/>',
    ).elements["road7"]
    assert road.tags == frozenset({"motorway", "town"})
    assert road.sections[0].tags == road.tags
    assert road.sections[1].tags == road.tags


def test_lane_type_tags_are_lane_specific(tmp_path):
    road = parse_scenic_network(
        tmp_path,
        lanes_xml="\n".join((lane_xml(-1), lane_xml(-2, type_="onRamp"))),
        road_extras='<type s="0" type="motorway"><speed max="120" unit="km/h"/></type>',
    ).elements["road7"]
    tags = {section.openDriveID: section.tags for section in road.sections[0].lanes}
    assert tags[-1] == frozenset({"driving"})
    assert tags[-2] == frozenset({"onRamp"})
    assert road.tags == frozenset({"motorway"})


def test_junction_type_tags_apply_only_to_connecting_road():
    road_map = RoadMap()
    road_map.parse(JUNCTION_XODR)
    road_map.calculate_geometry(num=5, calc_intersect=True)
    network = road_map.toScenicNetwork()
    connecting = network.elements["road7"]
    incoming = network.elements["road6"]
    tags = {section.openDriveID: section.tags for section in connecting.sections[0].lanes}

    assert connecting.tags == frozenset({"direct", "motorway"})
    assert "direct" not in incoming.tags
    assert incoming.tags == frozenset()
    assert tags[-1] == frozenset({"driving"})
    assert tags[-2] == frozenset({"onRamp"})
    assert "direct" not in tags[-1]
    assert "motorway" not in tags[-1]


def test_junction_tags_from_type():
    assert Junction(1, "Direct junction", "direct").tags == frozenset({"direct"})
    assert Junction(2, None, "default").tags == frozenset()
    assert Junction(3, "J3").tags == frozenset()
    assert Junction(4, "J4", "roundabout").tags == frozenset({"roundabout"})
