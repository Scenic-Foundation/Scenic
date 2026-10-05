from scenic.formats.opendrive.xodr_parser import RoadMap

DEFAULT_PLAN_VIEW = """<planView>
      <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="20.0">
        <line/>
      </geometry>
    </planView>"""

DEFAULT_LANE = """          <lane id="-1" type="driving" level="false">
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
          </lane>"""


def lane_xml(id_, type_="driving", speeds=(), pred=None, succ=None):
    """Build one OpenDRIVE ``<lane>`` element."""
    link_parts = []
    if pred is not None:
        link_parts.append(f'              <predecessor id="{pred}"/>')
    if succ is not None:
        link_parts.append(f'              <successor id="{succ}"/>')
    link = ""
    if link_parts:
        link = "            <link>\n" + "\n".join(link_parts) + "\n            </link>\n"
    speed_xml = "".join(
        f'            <speed sOffset="{s}" max="{max_speed}" unit="{unit}"/>\n'
        for s, max_speed, unit in speeds
    )
    return (
        f'          <lane id="{id_}" type="{type_}" level="false">\n'
        f"{link}"
        '            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>\n'
        f"{speed_xml}"
        "          </lane>"
    )


TWO_LANE_SECTIONS = f"""      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
{lane_xml(-1, succ=-1)}
        </right>
      </laneSection>
      <laneSection s="10">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
{lane_xml(-1, pred=-1)}
        </right>
      </laneSection>"""


def _write_xodr(tmp_path, body):
    path = tmp_path / "test.xodr"
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
{body}
</OpenDRIVE>
"""
    )
    return path


def write_xodr(
    tmp_path,
    road_extras="",
    plan_view=DEFAULT_PLAN_VIEW,
    lanes_xml=DEFAULT_LANE,
    lane_side="right",
    lane_sections_xml=None,
):
    lanes = (
        lane_sections_xml
        if lane_sections_xml is not None
        else f"""      <laneSection s="0.0">
        <center>
          <lane id="0" type="none" level="false"/>
        </center>
        <{lane_side}>
{lanes_xml}
        </{lane_side}>
      </laneSection>"""
    )
    return _write_xodr(
        tmp_path,
        f"""  <road name="Road 7" length="20.0" id="7" junction="-1">
    {road_extras}
    {plan_view}
    <lanes>
      <laneOffset s="0.0" a="0.0" b="0.0" c="0.0" d="0.0"/>
{lanes}
    </lanes>
  </road>""",
    )


def parse_scenic_network(
    tmp_path,
    road_extras="",
    plan_view=DEFAULT_PLAN_VIEW,
    *,
    lanes_xml=None,
    lane_side="right",
    lane_sections_xml=None,
):
    path = write_xodr(
        tmp_path,
        road_extras=road_extras,
        plan_view=plan_view,
        lanes_xml=DEFAULT_LANE if lanes_xml is None else lanes_xml,
        lane_side=lane_side,
        lane_sections_xml=lane_sections_xml,
    )
    road_map = RoadMap()
    road_map.parse(path)
    road_map.calculate_geometry(num=5, calc_intersect=True)
    return road_map.toScenicNetwork()


def assert_road_tags_propagated_to_groups(road):
    """Road-level tags should propagate to the lane groups spanning the road."""
    expected = road.tags
    if road.forwardLanes is not None:
        assert road.forwardLanes.tags == expected
    if road.backwardLanes is not None:
        assert road.backwardLanes.tags == expected
