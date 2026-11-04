"""Integration tests for signal↔maneuver linking via inline OpenDRIVE fixtures."""

from pathlib import Path

from scenic.domains.driving.roads import ManeuverType, Network

# Minimal maps exercised below (same geometries as the local demo/signals maps).
MAP_VALIDITY_LANES = """<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="signal_validity_lanes" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1" rule="RHT">
    <link><successor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
          <lane id="-2" type="driving" level="false">
            <link><successor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1" rule="RHT">
    <link><predecessor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
          <lane id="-2" type="driving" level="false">
            <link><predecessor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="Straight Connector" length="12.0" id="10" junction="100" rule="RHT">
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
          <lane id="-2" type="driving" level="false">
            <link><predecessor id="-2"/><successor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
    <signals>
      <signal s="1.0" t="-1.75" id="101" name="light_lane_m1" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="-1" toLane="-1"/>
      </signal>
      <signal s="1.0" t="-5.25" id="102" name="light_lane_m2" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="-2" toLane="-2"/>
      </signal>
    </signals>
  </road>
  <junction name="StraightSignalized" id="100">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
      <laneLink from="-2" to="-2"/>
    </connection>
  </junction>
</OpenDRIVE>
"""

MAP_APPROACH_SIGNAL = """<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="signal_on_approach" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1" rule="RHT">
    <link><successor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
          <lane id="-2" type="driving" level="false">
            <link><successor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
    <signals>
      <signal s="18.0" t="-3.5" id="201" name="approach_light" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1"/>
    </signals>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1" rule="RHT">
    <link><predecessor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
          <lane id="-2" type="driving" level="false">
            <link><predecessor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="Straight Connector" length="12.0" id="10" junction="100" rule="RHT">
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
          <lane id="-2" type="driving" level="false">
            <link><predecessor id="-2"/><successor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <junction name="ApproachSignalized" id="100">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
      <laneLink from="-2" to="-2"/>
    </connection>
  </junction>
</OpenDRIVE>
"""

MAP_T_JUNCTION = """<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="t_junction_turn_signals" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1" rule="RHT">
    <link><successor elementType="junction" elementId="200"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1" rule="RHT">
    <link><predecessor elementType="junction" elementId="200"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="South Exit" length="20.0" id="3" junction="-1" rule="RHT">
    <link><predecessor elementType="junction" elementId="200"/></link>
    <planView>
      <geometry s="0" x="26.0" y="-6.0" hdg="-1.5707963267948966" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="Straight Connector" length="12.0" id="10" junction="200" rule="RHT">
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
    <signals>
      <signal s="1.0" t="-1.75" id="301" name="straight_light" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="-1" toLane="-1"/>
      </signal>
    </signals>
  </road>
  <road name="Right Turn Connector" length="12.0" id="11" junction="200" rule="RHT">
    <link>
      <predecessor elementType="road" elementId="1" contactPoint="end"/>
      <successor elementType="road" elementId="3" contactPoint="start"/>
    </link>
    <planView>
      <geometry s="0" x="20.0" y="0" hdg="0.0" length="6.0"><line/></geometry>
      <geometry s="6.0" x="26.0" y="0" hdg="-1.5707963267948966" length="6.0"><line/></geometry>
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
    <signals>
      <signal s="1.0" t="-1.75" id="302" name="right_turn_arrow" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1">
        <validity fromLane="-1" toLane="-1"/>
      </signal>
    </signals>
  </road>
  <junction name="TJunctionSignals" id="200">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
    </connection>
    <connection id="1" incomingRoad="1" connectingRoad="11" contactPoint="start">
      <laneLink from="-1" to="-1"/>
    </connection>
  </junction>
</OpenDRIVE>
"""

MAP_UNSIGNALIZED = """<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="unsignalized_straight" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1" rule="RHT">
    <link><successor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
          <lane id="-2" type="driving" level="false">
            <link><successor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1" rule="RHT">
    <link><predecessor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
          <lane id="-2" type="driving" level="false">
            <link><predecessor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="Straight Connector" length="12.0" id="10" junction="100" rule="RHT">
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
          <lane id="-2" type="driving" level="false">
            <link><predecessor id="-2"/><successor id="-2"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <junction name="Unsignalized" id="100">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
      <laneLink from="-2" to="-2"/>
    </connection>
  </junction>
</OpenDRIVE>
"""


def load_network(tmp_path: Path, xml: str) -> Network:
    path = tmp_path / "map.xodr"
    path.write_text(xml)
    return Network.fromFile(path, useCache=False)


def open_drive_id(lane) -> int:
    ids = {sec.openDriveID for sec in lane.sections}
    assert len(ids) == 1, lane
    return next(iter(ids))


def all_maneuvers(network: Network):
    return [m for inter in network.intersections for m in inter.maneuvers]


def assert_bidirectional(maneuver):
    assert maneuver.signal is not None
    assert maneuver in maneuver.signal.controlledManeuvers
    for other in maneuver.signal.controlledManeuvers:
        assert other.signal is maneuver.signal
    assert maneuver.signal in maneuver.startLane.road.signals
    assert maneuver.signal.road is maneuver.startLane.road


def test_validity_lanes_per_lane_signals(tmp_path):
    network = load_network(tmp_path, MAP_VALIDITY_LANES)
    mans = all_maneuvers(network)
    assert len(mans) == 2

    by_start = {open_drive_id(m.startLane): m for m in mans}
    assert set(by_start) == {-1, -2}

    man_inner, man_outer = by_start[-1], by_start[-2]
    assert man_inner.type is ManeuverType.STRAIGHT
    assert man_outer.type is ManeuverType.STRAIGHT
    assert man_inner.signal.openDriveID == "101"
    assert man_outer.signal.openDriveID == "102"
    assert man_inner.signal is not man_outer.signal
    assert man_inner.signal.isTrafficLight
    assert_bidirectional(man_inner)
    assert_bidirectional(man_outer)
    assert man_inner.signal.controlledManeuvers == (man_inner,)
    assert man_outer.signal.controlledManeuvers == (man_outer,)


def test_approach_signal_shared_by_both_lanes(tmp_path):
    network = load_network(tmp_path, MAP_APPROACH_SIGNAL)
    mans = all_maneuvers(network)
    assert len(mans) == 2
    assert mans[0].signal is mans[1].signal
    assert mans[0].signal.openDriveID == "201"
    for man in mans:
        assert_bidirectional(man)
    assert set(mans[0].signal.controlledManeuvers) == set(mans)


def test_t_junction_distinct_signals_per_maneuver(tmp_path):
    network = load_network(tmp_path, MAP_T_JUNCTION)
    mans = all_maneuvers(network)
    assert len(mans) == 2

    by_type = {m.type: m for m in mans}
    assert set(by_type) == {ManeuverType.STRAIGHT, ManeuverType.RIGHT_TURN}
    assert (
        by_type[ManeuverType.STRAIGHT].startLane
        is by_type[ManeuverType.RIGHT_TURN].startLane
    )

    straight, right = by_type[ManeuverType.STRAIGHT], by_type[ManeuverType.RIGHT_TURN]
    assert straight.signal.openDriveID == "301"
    assert right.signal.openDriveID == "302"
    assert straight.signal is not right.signal
    assert_bidirectional(straight)
    assert_bidirectional(right)


def test_unsignalized_maneuvers_have_no_signal(tmp_path):
    network = load_network(tmp_path, MAP_UNSIGNALIZED)
    mans = all_maneuvers(network)
    assert len(mans) == 2
    assert all(m.signal is None for m in mans)
    for road in list(network.roads) + list(network.connectingRoads):
        for sig in road.signals:
            assert sig.controlledManeuvers == ()


def test_intersection_backrefs_consistent(tmp_path):
    for xml in (
        MAP_VALIDITY_LANES,
        MAP_APPROACH_SIGNAL,
        MAP_T_JUNCTION,
        MAP_UNSIGNALIZED,
    ):
        network = load_network(tmp_path, xml)
        for inter in network.intersections:
            for man in inter.maneuvers:
                assert man.intersection is inter
                if man.signal is not None:
                    assert_bidirectional(man)
                    assert man.signal.isTrafficLight
        for road in network.connectingRoads:
            assert road.signals == ()
