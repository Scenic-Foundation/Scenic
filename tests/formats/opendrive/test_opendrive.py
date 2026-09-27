import glob
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import pytest

from scenic.core.geometry import TriangulationError
from scenic.formats.opendrive import OpenDriveWorkspace
from scenic.formats.opendrive.xodr_parser import (
    Cubic,
    OpenDriveWarning,
    ParamCubic,
    RoadMap,
    makeCurve,
)

oldDir = os.getcwd()
os.chdir(Path("tests") / "formats" / "opendrive")
mapPath = Path("maps") / "**" / "*.xodr"
maps = glob.glob(str(mapPath))
os.chdir(oldDir)


@pytest.mark.slow
@pytest.mark.filterwarnings("ignore::scenic.formats.opendrive.OpenDriveWarning")
@pytest.mark.parametrize("path", maps)
def test_map(path, runLocally, pytestconfig):
    with runLocally():
        try:
            odw = OpenDriveWorkspace(path, n=10)
        except TriangulationError:
            pytest.skip("need better triangulation library to run this test")
        pt = odw.drivable_region.uniformPointInner()
        odw.road_direction[pt]
        if not pytestconfig.getoption("--no-graphics"):
            odw.show(plt)
            plt.show(block=False)
            plt.close()


def write_xodr(tmp_path, plan_view):
    path = tmp_path / "test.xodr"
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <road name="Road 7" length="20.0" id="7" junction="-1">
    {plan_view}
    <lanes>
      <laneOffset s="0.0" a="0.0" b="0.0" c="0.0" d="0.0"/>
      <laneSection s="0.0">
        <center>
          <lane id="0" type="none" level="false"/>
        </center>
        <right>
          <lane id="-1" type="driving" level="false">
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
"""
    )
    return path


def test_inconsistent_planview_length_warns(tmp_path):
    path = write_xodr(
        tmp_path,
        """<planView>
      <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="12.0">
        <line/>
      </geometry>
      <geometry s="10.0" x="10.0" y="0.0" hdg="0.0" length="10.0">
        <line/>
      </geometry>
    </planView>""",
    )

    road_map = RoadMap()

    with pytest.warns(
        OpenDriveWarning,
        match="planView of road 7 has inconsistent length",
    ):
        road_map.parse(path)

    road = road_map.roads[7]
    assert len(road.ref_line) == 2
    assert road.ref_line[0].length == pytest.approx(10.0)
    assert road.ref_line[1].length == pytest.approx(10.0)


def test_empty_planview_rejected(tmp_path):
    path = write_xodr(tmp_path, "<planView/>")

    road_map = RoadMap()

    with pytest.raises(ValueError, match="road 7 has an empty planView"):
        road_map.parse(path)


def test_planview_must_start_at_zero(tmp_path):
    path = write_xodr(
        tmp_path,
        """<planView>
      <geometry s="1.0" x="0.0" y="0.0" hdg="0.0" length="10.0">
        <line/>
      </geometry>
    </planView>""",
    )

    road_map = RoadMap()

    with pytest.raises(
        ValueError, match="reference line of road 7 does not start at s=0"
    ):
        road_map.parse(path)


def test_planview_must_be_in_order(tmp_path):
    path = write_xodr(
        tmp_path,
        """<planView>
      <geometry s="0.0" x="0.0" y="0.0" hdg="0.0" length="10.0">
        <line/>
      </geometry>
      <geometry s="-1.0" x="10.0" y="0.0" hdg="0.0" length="10.0">
        <line/>
      </geometry>
    </planView>""",
    )

    road_map = RoadMap()

    with pytest.raises(ValueError, match="planView of road 7 is not in order"):
        road_map.parse(path)


def test_make_curve_poly3():
    curve_elem = ET.fromstring('<poly3 a="0.0" b="1.0" c="0.0" d="0.0"/>')

    curve, susp = makeCurve(0.0, 0.0, 0.0, 10.0, curve_elem)

    assert isinstance(curve, Cubic)
    assert curve.length == pytest.approx(10.0)
    assert not susp


def test_make_curve_param_poly3():
    curve_elem = ET.fromstring(
        '<paramPoly3 aU="0.0" bU="1.0" cU="0.0" dU="0.0" '
        'aV="0.0" bV="0.0" cV="0.0" dV="0.0" pRange="normalized"/>'
    )

    curve, susp = makeCurve(0.0, 0.0, 0.0, 10.0, curve_elem)

    assert isinstance(curve, ParamCubic)
    assert curve.p_range == pytest.approx(1.0)
    assert curve.length == pytest.approx(10.0)
    assert not susp


def test_make_curve_param_poly3_default_p_range():
    curve_elem = ET.fromstring(
        '<paramPoly3 aU="0.0" bU="1.0" cU="0.0" dU="0.0" '
        'aV="0.0" bV="0.0" cV="0.0" dV="0.0"/>'
    )

    curve, susp = makeCurve(0.0, 0.0, 0.0, 10.0, curve_elem)

    assert isinstance(curve, ParamCubic)
    assert curve.p_range == pytest.approx(1.0)
    assert not susp


def test_make_curve_param_poly3_rejects_unknown_p_range():
    curve_elem = ET.fromstring(
        '<paramPoly3 aU="0.0" bU="1.0" cU="0.0" dU="0.0" '
        'aV="0.0" bV="0.0" cV="0.0" dV="0.0" pRange="unknown"/>'
    )

    with pytest.raises(NotImplementedError, match="unsupported pRange for paramPoly3"):
        makeCurve(0.0, 0.0, 0.0, 10.0, curve_elem)


def test_make_curve_param_poly3_arc_length():
    curve_elem = ET.fromstring(
        '<paramPoly3 aU="0.0" bU="1.0" cU="0.0" dU="0.0" '
        'aV="0.0" bV="0.0" cV="0.0" dV="0.0" pRange="arcLength"/>'
    )

    curve, susp = makeCurve(0.0, 0.0, 0.0, 10.0, curve_elem)

    assert isinstance(curve, ParamCubic)
    assert curve.p_range == pytest.approx(10.0)
    assert curve.length == pytest.approx(10.0)
    assert not susp


def test_bs_schwarzer_berg_parse(getAssetPath):
    path = getAssetPath("maps/misc/bs-schwarzer-berg.xodr")
    road_map = RoadMap()
    road_map.parse(path)
    assert len(road_map.roads) == 257
    assert len(road_map.junctions) == 31


def test_bs_schwarzer_berg_param_poly3(getAssetPath):
    path = getAssetPath("maps/misc/bs-schwarzer-berg.xodr")
    tree = ET.parse(path)
    count = 0
    for geom in tree.iter("geometry"):
        for child in geom:
            if child.tag != "paramPoly3":
                continue
            curve, susp = makeCurve(
                float(geom.get("x", 0)),
                float(geom.get("y", 0)),
                float(geom.get("hdg", 0)),
                float(geom.get("length", 0)),
                child,
            )
            assert isinstance(curve, ParamCubic)
            if child.get("pRange") == "arcLength":
                assert curve.p_range == pytest.approx(float(geom.get("length", 0)))
            assert not susp
            count += 1
    assert count == 1799


def test_make_curve_param_poly3_arc_length_matches_normalized():
    length = 10.0
    au, bu, cu, du = 0.0, 1.0, 0.1, -0.02
    av, bv, cv, dv = 0.0, 0.0, 0.05, -0.01
    arc_elem = ET.fromstring(
        f'<paramPoly3 aU="{au}" bU="{bu}" cU="{cu}" dU="{du}" '
        f'aV="{av}" bV="{bv}" cV="{cv}" dV="{dv}" pRange="arcLength"/>'
    )
    norm_elem = ET.fromstring(
        f'<paramPoly3 aU="{au}" bU="{bu * length}" cU="{cu * length**2}" '
        f'dU="{du * length**3}" aV="{av}" bV="{bv * length}" '
        f'cV="{cv * length**2}" dV="{dv * length**3}" pRange="normalized"/>'
    )

    arc_curve, _ = makeCurve(0.0, 0.0, 0.0, length, arc_elem)
    norm_curve, _ = makeCurve(0.0, 0.0, 0.0, length, norm_elem)

    for s in (0.0, length * 0.25, length * 0.5, length * 0.75, length):
        arc_pt = arc_curve.point_at(s)
        norm_pt = norm_curve.point_at(s)
        assert arc_pt[0] == pytest.approx(norm_pt[0])
        assert arc_pt[1] == pytest.approx(norm_pt[1])
        assert arc_pt[2] == pytest.approx(norm_pt[2])


def test_make_curve_rejects_unknown_geometry_type():
    curve_elem = ET.fromstring("<unknown/>")

    with pytest.raises(NotImplementedError, match="unhandled OpenDRIVE geometry type"):
        makeCurve(0.0, 0.0, 0.0, 10.0, curve_elem)
