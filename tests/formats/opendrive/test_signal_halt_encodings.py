"""Halt-point encodings: deprecated logical-s, signalReference, and CARLA maps.

Junction-contact traffic lights must stop only the arriving direction. The lane
you turn into at the far side of a green light must not inherit a halt at s=0.
"""

from pathlib import Path

import pytest

from scenic.core.vectors import Vector
from scenic.domains.driving.roads import Network, SignalTag

# Shared two-way section: +1 travels −s, −1 travels +s.
_TWOWAY_LANES = """\
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <left>
          <lane id="1" type="driving" level="false">
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </left>
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
"""

_TWOWAY_TWO_SECTIONS = """\
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <left>
          <lane id="1" type="driving" level="false">
            <link><successor id="1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </left>
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
      <laneSection s="20">
        <left>
          <lane id="1" type="driving" level="false">
            <link><predecessor id="1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </left>
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
"""

# Pre-1.8: @s is the effect station; <positionRoad>/<positionInertial> is the pole.
MAP_DEPRECATED_LOGICAL = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="deprecated_logical_s" version="1.0"/>
  <road name="TwoWay" length="40.0" id="1" junction="-1">
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="40.0"><line/></geometry>
    </planView>
    <lanes>
{_TWOWAY_LANES}
    </lanes>
    <signals>
      <signal s="12.0" t="-1.75" id="10" name="legacy_stop" dynamic="no"
              orientation="-" zOffset="2" type="206" country="OpenDRIVE"
              subtype="-1" value="-1">
        <positionRoad roadId="1" s="16.0" t="-4.0" zOffset="2" hOffset="0"/>
      </signal>
      <signal s="28.0" t="-1.75" id="11" name="legacy_yield" dynamic="no"
              orientation="+" zOffset="2" type="205" country="OpenDRIVE"
              subtype="-1" value="-1">
        <positionInertial x="30.0" y="-4.0" z="2" hdg="0" pitch="0" roll="0"/>
      </signal>
      <signal s="20.0" t="0.0" id="12" name="both_ways_line" dynamic="no"
              orientation="none" zOffset="0" type="-1" country="OpenDRIVE"
              subtype="-1" value="-1">
        <semantics><priority type="stopLine"/></semantics>
      </signal>
    </signals>
  </road>
</OpenDRIVE>
"""

MAP_DEPRECATED_TWO_SECTIONS = MAP_DEPRECATED_LOGICAL.replace(
    _TWOWAY_LANES, _TWOWAY_TWO_SECTIONS
)

# Canonical light on the west approach; same id re-applied on the east road
# (the road you turn into) via <signalReference>.
MAP_SIGNAL_REFERENCE = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="signal_reference_exit" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1">
    <link><successor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
{_TWOWAY_LANES}
    </lanes>
    <signals>
      <signal s="18.0" t="-4.0" id="201" name="canonical_light" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1"/>
    </signals>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1">
    <link><predecessor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
{_TWOWAY_LANES}
    </lanes>
    <signals>
      <signalReference s="1.5" t="4.0" id="201" orientation="-"/>
    </signals>
  </road>
  <road name="Connector" length="12.0" id="10" junction="100">
    <link>
      <predecessor elementType="road" elementId="1" contactPoint="end"/>
      <successor elementType="road" elementId="2" contactPoint="start"/>
    </link>
    <planView>
      <geometry s="0" x="20.0" y="0.0" hdg="0.0" length="12.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <junction name="J" id="100">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
    </connection>
  </junction>
</OpenDRIVE>
"""

# Same geometry as MAP_SIGNAL_REFERENCE, but CARLA-undefined: dummy 0–0 validity
# and lamp-facing orientation (often the opposite of the arriving lane).
MAP_CARLA_TWOWAY = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="carla_twoway_dummy" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1">
    <link><successor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
{_TWOWAY_LANES}
    </lanes>
    <signals>
      <signal s="18.5" t="-4.5" id="362" name="Signal_3Light_Post01" dynamic="yes"
              orientation="-" zOffset="0" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="0" toLane="0"/>
      </signal>
    </signals>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1">
    <link><predecessor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
{_TWOWAY_LANES}
    </lanes>
    <signals>
      <signal s="1.5" t="4.5" id="360" name="Signal_3Light_Post01" dynamic="yes"
              orientation="+" zOffset="0" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="0" toLane="0"/>
      </signal>
    </signals>
  </road>
  <road name="Connector" length="12.0" id="10" junction="100">
    <link>
      <predecessor elementType="road" elementId="1" contactPoint="end"/>
      <successor elementType="road" elementId="2" contactPoint="start"/>
    </link>
    <planView>
      <geometry s="0" x="20.0" y="0.0" hdg="0.0" length="12.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <junction name="J" id="100">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
    </connection>
  </junction>
</OpenDRIVE>
"""

# CARLA-style dummy validity on a <signalReference> (Town10HD hybrid).
MAP_CARLA_SIGNAL_REFERENCE = MAP_SIGNAL_REFERENCE.replace(
    '<signalReference s="1.5" t="4.0" id="201" orientation="-"/>',
    '<signalReference s="1.5" t="4.0" id="201" orientation="+">\n'
    '        <validity fromLane="0" toLane="0"/>\n'
    "      </signalReference>",
)

MAP_CONNECTOR_HOSTED_LIGHT = (
    MAP_CARLA_TWOWAY.replace(
        """    <signals>
      <signal s="18.5" t="-4.5" id="362" name="Signal_3Light_Post01" dynamic="yes"
              orientation="-" zOffset="0" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="0" toLane="0"/>
      </signal>
    </signals>
""",
        "",
    )
    .replace(
        """    <signals>
      <signal s="1.5" t="4.5" id="360" name="Signal_3Light_Post01" dynamic="yes"
              orientation="+" zOffset="0" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="0" toLane="0"/>
      </signal>
    </signals>
""",
        "",
    )
    .replace(
        """      </laneSection>
    </lanes>
  </road>
  <junction name="J" id="100">
""",
        """      </laneSection>
    </lanes>
    <signals>
      <signal s="2.0" t="-4.0" id="500" name="connector_light" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1"/>
    </signals>
  </road>
  <junction name="J" id="100">
""",
    )
)


def load_network(tmp_path: Path, xml: str) -> Network:
    path = tmp_path / "map.xodr"
    path.write_text(xml)
    return Network.fromFile(path, useCache=False)


def od_id(lane) -> int:
    ids = {sec.openDriveID for sec in lane.sections}
    assert len(ids) == 1, lane
    return next(iter(ids))


def lanes_by_id(road):
    return {od_id(lane): lane for lane in road.lanes}


def road_by_id(network, road_id):
    return next(road for road in network.roads if road.id == road_id)


def signal_on(road, open_drive_id):
    matches = [sig for sig in road.signals if str(sig.openDriveID) == str(open_drive_id)]
    assert len(matches) == 1, (road.uid, open_drive_id, matches)
    return matches[0]


def _st(position, s, t, tol=0.15):
    assert position is not None
    actual_s, actual_t = position
    assert abs(actual_s - s) < tol, (actual_s, s)
    assert abs(actual_t - t) < tol, (actual_t, t)


@pytest.mark.parametrize(
    "literal, tag",
    (
        ("4way", SignalTag.FOUR_WAY),
        ("stop", SignalTag.STOP),
        ("yield", SignalTag.YIELD),
        ("trafficLight", SignalTag.TRAFFIC_LIGHT),
        ("turnOnRedAllowed", SignalTag.TURN_ON_RED_ALLOWED),
        ("noTurnOnRed", SignalTag.NO_TURN_ON_RED),
    ),
)
def test_known_opendrive_literals_become_tags(tmp_path, literal, tag):
    xml = MAP_DEPRECATED_LOGICAL.replace(
        '<semantics><priority type="stopLine"/></semantics>',
        f'<semantics><priority type="{literal}"/></semantics>',
    )
    road = road_by_id(load_network(tmp_path, xml), 1)
    signal = signal_on(road, 12)
    assert tag in signal.tags
    assert signal.hasTag(tag)


def test_unknown_opendrive_literals_stay_other_tags(tmp_path):
    xml = MAP_DEPRECATED_LOGICAL.replace(
        '<semantics><priority type="stopLine"/></semantics>',
        """<semantics>
          <priority type="stopLine"/>
          <priority type="keepClearLine"/>
          <priority type="vendorSpecificPriority"/>
        </semantics>""",
    )
    road = road_by_id(load_network(tmp_path, xml), 1)
    signal = signal_on(road, 12)
    assert signal.tags == frozenset()
    assert signal.otherTags == frozenset(
        {"stopLine", "keepClearLine", "vendorSpecificPriority"}
    )
    assert not signal.isStop
    assert not signal.isFourWay
    assert not signal.isYield
    assert not signal.isTrafficLight


def test_four_way_halts_without_being_classified_as_stop(tmp_path):
    four_way = MAP_DEPRECATED_LOGICAL.replace(
        '<semantics><priority type="stopLine"/></semantics>',
        '<semantics><priority type="4way"/></semantics>',
    )
    road = road_by_id(load_network(tmp_path, four_way), 1)
    lanes = lanes_by_id(road)
    signal = signal_on(road, 12)
    assert signal.tags == frozenset({SignalTag.FOUR_WAY})
    assert signal.otherTags == frozenset()
    assert signal.isFourWay
    assert not signal.isStop
    assert signal.stoppingS == 20.0
    _st(signal.stoppingPositionOn(lanes[-1]), 20.0, -1.75)
    _st(signal.stoppingPositionOn(lanes[1]), 20.0, 1.75)

    turn_on_red = MAP_DEPRECATED_LOGICAL.replace(
        '<semantics><priority type="stopLine"/></semantics>',
        '<semantics><priority type="turnOnRedAllowed"/></semantics>',
    )
    road = road_by_id(load_network(tmp_path, turn_on_red), 1)
    signal = signal_on(road, 12)
    assert signal.tags == frozenset({SignalTag.TURN_ON_RED_ALLOWED})
    assert signal.isTurnOnRedAllowed
    assert not signal.isTrafficLight
    assert not signal.isNoTurnOnRed
    assert signal.stoppingS is None


def test_country_and_subtype_warn_in_favor_of_semantic_tags(tmp_path):
    road = road_by_id(load_network(tmp_path, MAP_DEPRECATED_LOGICAL), 1)
    signal = signal_on(road, 12)
    assert signal.tags == frozenset()
    assert signal.otherTags == frozenset({"stopLine"})
    with pytest.warns(DeprecationWarning, match=r"Signal\.country.*Signal\.tags"):
        assert signal.country == "OpenDRIVE"
    with pytest.warns(DeprecationWarning, match=r"Signal\.subtype.*Signal\.tags"):
        assert signal.subtype == "-1"


def test_opendrive_arrow_head_type_is_traffic_light(tmp_path):
    """Arrow icons are traffic lights; red vs green is not a map tag."""
    xml = MAP_SIGNAL_REFERENCE.replace(
        'type="1000001" country="OpenDRIVE"\n              subtype="-1"',
        'type="1000020" country="OpenDRIVE"\n              subtype="10"',
    )
    road = road_by_id(load_network(tmp_path, xml), 1)
    signal = signal_on(road, 201)
    assert signal.type == "1000020"
    assert signal.isTrafficLight
    assert signal.tags == frozenset()
    assert signal.otherTags == frozenset()


# --- deprecated pre-1.8 logical @s ---


def test_deprecated_position_road_halts_at_logical_s_not_pole(tmp_path):
    network = load_network(tmp_path, MAP_DEPRECATED_LOGICAL)
    road = road_by_id(network, 1)
    lanes = lanes_by_id(road)
    stop = signal_on(road, 10)
    assert stop.s == 12.0
    assert stop.stoppingS == 12.0
    assert stop.type == "206"
    assert stop.tags == frozenset()
    assert stop.isStop
    assert stop.stoppingPositionOn(lanes[-1]) is None
    _st(stop.stoppingPositionOn(lanes[1]), 12.0, 1.75)


def test_deprecated_position_inertial_halts_at_logical_s(tmp_path):
    network = load_network(tmp_path, MAP_DEPRECATED_LOGICAL)
    road = road_by_id(network, 1)
    lanes = lanes_by_id(road)
    yield_sig = signal_on(road, 11)
    assert yield_sig.stoppingS == 28.0
    assert yield_sig.type == "205"
    assert yield_sig.tags == frozenset()
    assert yield_sig.isYield
    _st(yield_sig.stoppingPositionOn(lanes[-1]), 28.0, -1.75)
    assert yield_sig.stoppingPositionOn(lanes[1]) is None


def test_unrecognized_stopline_tag_does_not_create_a_halt(tmp_path):
    """Painted-line literals are otherTags; they do not decide stopping yet."""
    network = load_network(tmp_path, MAP_DEPRECATED_LOGICAL)
    road = road_by_id(network, 1)
    lanes = lanes_by_id(road)
    line = signal_on(road, 12)
    assert line.otherTags == frozenset({"stopLine"})
    assert line.tags == frozenset()
    assert line.stoppingS is None
    assert line.stoppingPositionOn(lanes[-1]) is None
    assert line.stoppingPositionOn(lanes[1]) is None


def test_deprecated_halt_s_value_ahead_skips_opposite_direction(tmp_path):
    network = load_network(tmp_path, MAP_DEPRECATED_LOGICAL)
    road = road_by_id(network, 1)
    lanes = lanes_by_id(road)
    # +s traffic: yield at 28. Opposite stop at 12 is behind.
    _st(lanes[-1].haltPositionAhead(Vector(1, -1.75)), 28.0, -1.75)
    assert lanes[-1].haltPositionAhead(Vector(29, -1.75)) is None


def test_signal_lookups_propagate_in_each_elements_travel_order(tmp_path):
    network = load_network(tmp_path, MAP_DEPRECATED_LOGICAL)
    road = road_by_id(network, 1)
    lanes = lanes_by_id(road)

    road_entries, road_s_values = road.signalLookup()
    assert [entry[1].openDriveID for entry in road_entries] == ["10", "11"]
    assert road_s_values == [12.0, 28.0]

    forward_entries, forward_s_values = lanes[-1].signalLookup()
    assert [entry[1].openDriveID for entry in forward_entries] == ["11"]
    assert forward_s_values == [28.0]
    assert [entry[1].openDriveID for entry in lanes[-1].signalsAhead(20.1)] == ["11"]

    backward_entries, backward_s_values = lanes[1].signalLookup()
    assert [entry[1].openDriveID for entry in backward_entries] == ["10"]
    assert backward_s_values == [28.0]
    assert [entry[2] for entry in backward_entries] == [12.0]
    assert [entry[1].openDriveID for entry in lanes[1].signalsAhead(20.1)] == ["10"]

    for lane in lanes.values():
        assert lane.sections[0].signalLookup() == lane.signalLookup()
    section_entries, section_s_values = road.sections[0].signalLookup()
    assert [entry[1].openDriveID for entry in section_entries] == ["10", "11"]
    assert section_s_values == [12.0, 28.0]


def test_signal_propagation_filters_sections_and_resolves_boundary(tmp_path):
    network = load_network(tmp_path, MAP_DEPRECATED_TWO_SECTIONS)
    road = road_by_id(network, 1)
    lanes = lanes_by_id(road)

    forward_sections = lanes[-1].sections
    assert [
        [entry[1].openDriveID for entry in section.signalLookup()[0]]
        for section in forward_sections
    ] == [[], ["11"]]

    backward_sections = lanes[1].sections
    assert [
        [entry[1].openDriveID for entry in section.signalLookup()[0]]
        for section in backward_sections
    ] == [[], ["10"]]

    assert [
        [entry[1].openDriveID for entry in section.signalLookup()[0]]
        for section in road.sections
    ] == [["10"], ["11"]]


# --- <signalReference> (same signal, other road) ---


def test_signal_reference_keeps_this_roads_placement(tmp_path):
    network = load_network(tmp_path, MAP_SIGNAL_REFERENCE)
    west = road_by_id(network, 1)
    east = road_by_id(network, 2)
    canonical = signal_on(west, 201)
    clone = signal_on(east, 201)
    assert canonical.type == clone.type == "1000001"
    assert canonical.s == 18.0
    assert clone.s == 1.5
    assert clone.orientation == "-"
    assert canonical.uid != clone.uid


def test_signal_reference_on_exit_does_not_stop_outgoing(tmp_path):
    """Turning onto the east road must not halt at that road's s≈0 clone."""
    network = load_network(tmp_path, MAP_SIGNAL_REFERENCE)
    west = road_by_id(network, 1)
    east = road_by_id(network, 2)
    west_lanes = lanes_by_id(west)
    east_lanes = lanes_by_id(east)
    canonical = signal_on(west, 201)
    clone = signal_on(east, 201)

    _st(canonical.stoppingPositionOn(west_lanes[-1]), 20.0, -1.75)
    assert canonical.stoppingPositionOn(west_lanes[1]) is None

    # Backward on the east road is still arriving at the junction.
    _st(clone.stoppingPositionOn(east_lanes[1]), 0.0, 1.75)
    # Forward on the east road just left the junction.
    assert clone.stoppingPositionOn(east_lanes[-1]) is None
    assert east_lanes[-1].haltPositionAhead(Vector(33.0, -1.75)) is None


def test_signal_reference_connector_has_no_invented_halt(tmp_path):
    network = load_network(tmp_path, MAP_SIGNAL_REFERENCE)
    connector = next(road for road in network.connectingRoads if road.id == 10)
    for sig in connector.signals:
        for lane in connector.lanes:
            assert sig.stoppingPositionOn(lane) is None


def test_carla_dummy_signal_reference_on_exit(tmp_path):
    """Town10HD-style: dummy validity on the reference still must not stop the exit."""
    network = load_network(tmp_path, MAP_CARLA_SIGNAL_REFERENCE)
    east = road_by_id(network, 2)
    lanes = lanes_by_id(east)
    clone = signal_on(east, 201)
    assert clone.orientation == "+"  # lamp facing; would wrongly pick the exit
    _st(clone.stoppingPositionOn(lanes[1]), 0.0, 1.75)
    assert clone.stoppingPositionOn(lanes[-1]) is None
    assert lanes[-1].haltPositionAhead(Vector(33.0, -1.75)) is None


# --- CARLA / RoadRunner undefined (dummy 0–0, pole only) ---


def test_carla_twoway_arriving_side_halts_leaving_side_does_not(tmp_path):
    network = load_network(tmp_path, MAP_CARLA_TWOWAY)
    west = road_by_id(network, 1)
    east = road_by_id(network, 2)
    west_lanes = lanes_by_id(west)
    east_lanes = lanes_by_id(east)
    west_light = signal_on(west, 362)
    east_light = signal_on(east, 360)

    assert west_light.stoppingS == 20.0
    assert east_light.stoppingS == 0.0
    assert west_light.type == "1000001"
    assert west_light.tags == frozenset()
    assert west_light.isTrafficLight

    # West +s is arriving at the junction.
    _st(west_light.stoppingPositionOn(west_lanes[-1]), 20.0, -1.75)
    assert west_light.stoppingPositionOn(west_lanes[1]) is None

    # East +s is the road you turn into; −s is the opposite approach.
    assert east_light.stoppingPositionOn(east_lanes[-1]) is None
    _st(east_light.stoppingPositionOn(east_lanes[1]), 0.0, 1.75)


def test_carla_green_light_then_no_stop_on_exit_lane(tmp_path):
    """After the west stop, haltPositionAhead on the east exit lane is empty."""
    network = load_network(tmp_path, MAP_CARLA_TWOWAY)
    west = road_by_id(network, 1)
    east = road_by_id(network, 2)
    west_fwd = lanes_by_id(west)[-1]
    east_fwd = lanes_by_id(east)[-1]
    _st(west_fwd.haltPositionAhead(Vector(1.0, -1.75)), 20.0, -1.75)
    assert east_fwd.haltPositionAhead(Vector(33.0, -1.75)) is None
    # Exactly at the east road start (s=0) must not count as a stop either.
    assert east_fwd.haltPositionAhead(Vector(32.0, -1.75)) is None


def test_carla_connector_lights_do_not_invent_a_stop(tmp_path):
    network = load_network(tmp_path, MAP_CARLA_TWOWAY)
    for road in network.connectingRoads:
        assert road.signals == ()


def test_signal_parents_are_hosting_road_and_optional_intersection(tmp_path):
    network = load_network(tmp_path, MAP_DEPRECATED_LOGICAL)
    road = road_by_id(network, 1)
    for sig in road.signals:
        assert sig.road is road
        assert sig.intersection is None
        assert sig in network.signals
    assert set(network.signals) == set(road.signals)

    network = load_network(tmp_path, MAP_CARLA_TWOWAY)
    west = road_by_id(network, 1)
    east = road_by_id(network, 2)
    west_light = signal_on(west, 362)
    east_light = signal_on(east, 360)
    assert west_light.road is west
    assert east_light.road is east
    assert west_light.intersection is east_light.intersection
    assert west_light.intersection is not None
    assert west in west_light.intersection.roads
    assert east in east_light.intersection.roads
    assert west_light in west_light.intersection.signals
    assert east_light in east_light.intersection.signals
    assert west_light in network.signals
    assert east_light in network.signals

    for connector in network.connectingRoads:
        assert connector.signals == ()

    for sig in network.signals:
        assert sig.road is not None
        assert sig in sig.road.signals
        assert sig.road not in network.connectingRoads


def test_connector_signal_parents_incoming_road_and_intersection(tmp_path):
    network = load_network(tmp_path, MAP_CONNECTOR_HOSTED_LIGHT)
    west = road_by_id(network, 1)
    light = signal_on(west, 500)
    assert light is west.signals[-1]
    assert light.road is west
    assert light.intersection is not None
    assert light in light.intersection.signals
    assert light in network.signals
    assert west in light.intersection.roads
    assert light.stoppingS == pytest.approx(west.centerline.length)
    for connector in network.connectingRoads:
        assert connector.signals == ()
        assert light not in connector.signals


@pytest.mark.slow
def test_town01_exit_lane_does_not_halt_at_entry(getAssetPath):
    """Town01 intersection26: road 1 +s leaves the junction and must not stop there."""
    from scenic.core.geometry import TriangulationError

    path = Path(getAssetPath("maps/CARLA/Town01.xodr"))
    if not path.exists():
        pytest.skip("Town01.xodr not shipped")
    try:
        network = Network.fromOpenDrive(path, ref_points=40, tolerance=0.05)
    except TriangulationError:
        pytest.skip("need better triangulation library")

    road1 = road_by_id(network, 1)
    lanes = lanes_by_id(road1)
    # OpenDRIVE +1 is −s (arriving at junction 26); −1 is +s (leaving it).
    arriving = lanes[1]
    leaving = lanes[-1]
    entry_light = next(
        sig
        for sig in road1.signals
        if sig.stoppingS is not None and abs(sig.stoppingS) <= 1e-4
    )
    assert entry_light.stoppingPositionOn(arriving) is not None
    assert entry_light.stoppingPositionOn(leaving) is None
    start = leaving.centerline.pointAlongBy(1.0)
    assert leaving.haltPositionAhead(start, lookahead=15.0) is None
