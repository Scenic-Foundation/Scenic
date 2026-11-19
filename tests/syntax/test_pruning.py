import pytest

from scenic.core.errors import InconsistentScenarioError
from scenic.core.regions import PointInRegionDistribution
from scenic.core.vectors import Vector, VectorOperatorDistribution
from tests.utils import compileScenic, sampleEgo, sampleParamP


def test_containment_in():
    """Test pruning based on object containment."""
    scenario = compileScenic(
        """
        workspace = Workspace(PolygonalRegion([0@0, 2@0, 2@2, 0@2]))
        ego = new Object in workspace
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0.5 <= x <= 1.5 for x in xs)
    assert any(0.5 <= x <= 0.7 or 1.3 <= x <= 1.5 for x in xs)


def test_containment_2d_region():
    """Test pruning based on object containment in a 2D region.

    Specifically tests that vertical portions of baseOffset are not added
    to maxDistance, and that if objects are known to be flat in the plane,
    their height is not considered as part of the minRadius.
    """
    # Tests the effect of the vertical portion of baseOffset in a 2D region.
    scenario = compileScenic(
        """
        workspace = Workspace(PolygonalRegion([0@0, 2@0, 2@2, 0@2]))
        ego = new Object on workspace
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0.5 <= x <= 1.5 for x in xs)
    assert any(0.5 <= x <= 0.7 or 1.3 <= x <= 1.5 for x in xs)

    # Test height's effect in a 2D region.
    scenario = compileScenic(
        """
        workspace = Workspace(PolygonalRegion([0@0, 2@0, 2@2, 0@2]))
        ego = new Object in workspace, with height 0.1
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0.5 <= x <= 1.5 for x in xs)
    assert any(0.5 <= x <= 0.7 or 1.3 <= x <= 1.5 for x in xs)

    # Test both combined, in a slightly more complicated case.
    # Specifically, there is a non vertical component to baseOffset
    # that should be accounted for.
    scenario = compileScenic(
        """
        class TestObject:
            baseOffset: (0.1, 0, self.height/2)

        workspace = Workspace(PolygonalRegion([0@0, 2@0, 2@2, 0@2]))
        ego = new TestObject on workspace, with height 100
        """
    )
    # Sampling should fail ~30.56% of the time, so
    # 34 rejections are allowed to get the failure probability
    # to ~1e-18.
    xs = [sampleEgo(scenario, maxIterations=34).position.x for i in range(60)]
    assert all(0.5 <= x <= 1.5 for x in xs)
    assert any(0.5 <= x <= 0.7 or 1.3 <= x <= 1.5 for x in xs)


def test_containment_in_polyline():
    """As above, but when the object is placed on a polyline."""
    scenario = compileScenic(
        """
        workspace = Workspace(PolygonalRegion([0@0, 2@0, 2@2, 0@2]))
        line = PolylineRegion([0@0, 1@1, 2@0])
        ego = new Object in line, facing 0
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0.5 <= x <= 1.5 for x in xs)
    assert any(0.5 <= x <= 0.7 or 1.3 <= x <= 1.5 for x in xs)


def test_relative_heading_require_visible():
    """Test pruning based on requirements bounding relative headings."""
    scenario = compileScenic(
        """
        r1 = PolygonalRegion([0@0, 10@0, 10@10, 0@10])      # First cell: heading 0 deg
        r2 = PolygonalRegion([20@0, 30@0, 30@10, 20@10])    # Second cell: heading 90 deg
        vf = PolygonalVectorField("Foo", [[r1.polygons, 0], [r2.polygons, 90 deg]])
        union = r1.union(r2)
        ego = new Object in union, facing vf                # Objects can be in either cell
        other = new Object in union, facing vf, with requireVisible True
        require (relative heading of other) >= 60 deg   # Forces ego in cell 1, other in cell 2
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0 <= x <= 10 for x in xs)
    assert any(x > 5 for x in xs)


def test_relative_heading_visible_from():
    """Test pruning based on requirements bounding relative headings."""
    scenario = compileScenic(
        """
        r1 = PolygonalRegion([0@0, 10@0, 10@10, 0@10])      # First cell: heading 0 deg
        r2 = PolygonalRegion([20@0, 30@0, 30@10, 20@10])    # Second cell: heading 90 deg
        vf = PolygonalVectorField("Foo", [[r1.polygons, 0], [r2.polygons, 90 deg]])
        union = r1.union(r2)
        ego = new Object in union, facing vf                # Objects can be in either cell
        other = new Object in union, facing vf, visible from ego
        require (relative heading of other) >= 60 deg   # Forces ego in cell 1, other in cell 2
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0 <= x <= 10 for x in xs)
    assert any(x > 5 for x in xs)


def test_relative_heading_distance():
    """Variant of the above where a distance bound must be inferred from a requirement."""
    scenario = compileScenic(
        """
        r1 = PolygonalRegion([0@0, 10@0, 10@10, 0@10])      # First cell: heading 0 deg
        r2 = PolygonalRegion([20@0, 30@0, 30@10, 20@10])    # Second cell: heading 90 deg
        r3 = PolygonalRegion([50@0, 60@0, 60@10, 50@10])    # Third cell: heading 90 deg
        vf = PolygonalVectorField("Foo", [[r1.polygons, 0], [r2.polygons, 90 deg],
                                           [r3.polygons, 90 deg]])
        union = r1.union(r2).union(r3)
        ego = new Object in union, facing vf, with visibleDistance 100
        other = new Object in union, facing vf
        require (relative heading of other) >= 60 deg       # Forces ego in cell 1, other cell 2/3
        require (distance to other) <= 35                   # Forces other in cell 2
        """
    )
    # Sampling should only require 1 iteration after pruning
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0 <= x <= 10 for x in xs)
    assert any(x > 5 for x in xs)


def test_relative_heading_inconsistent():
    """A special case where we can detect inconsistency of the requirements."""
    with pytest.raises(InconsistentScenarioError):
        scenario = compileScenic(
            """
            ego = new Object
            other = new Object at 10@10
            require abs(relative heading of other) < -1
        """
        )


def test_visibility_pruning():
    """Test visibility pruning in general.

    The following scenarios are equivalent except for how they specify that foo
    must be visible from ego. Without visibility pruning, sampling a valid scene
    would be extremely unlikely because the workspace is enormous compared to ego's
    visible region.

    We check two things. First, sampled positions must remain within distance 2 of
    ego, which is the maximum distance at which the spheroid can still intersect
    ego's visible region. Second, to ensure pruning is not too aggressive, we check
    the conditioned/pruned region directly and verify that it still extends beyond
    distance 1 from ego, so the outer band where the object intersects the view
    region is still available.
    """

    def assert_pruned_region_reaches_outer_band(scenario):
        foo = scenario.objects[1]
        conditioned = foo.position._conditioned

        if isinstance(conditioned, PointInRegionDistribution):
            base = conditioned.region
            offset = Vector(0, 0, 0)
        else:
            assert isinstance(conditioned, VectorOperatorDistribution)
            base = conditioned.object.region
            offset = conditioned.operands[0]

        max_dist = max(
            (Vector(x, y, base.z) + offset).distanceTo(Vector(0, 0, 0))
            for poly in base.polygons.geoms
            for x, y in poly.exterior.coords
        )
        assert max_dist <= 2 + 1e-6
        assert max_dist > 1 + 1e-6

    # requireVisible
    scenario = compileScenic(
        """
        workspace = Workspace(RectangularRegion(0@0, 0, 1e10, 1e10))
        ego = new Object at (0,0,0), with visibleDistance 1, with allowCollisions True
        foo = new Object in workspace,
            with shape SpheroidShape(dimensions=(2,2,2)),
            with allowCollisions True,
            with requireVisible True
        param p = foo.position
        """
    )
    positions = [sampleParamP(scenario, maxIterations=100) for i in range(30)]
    assert all(pos.distanceTo(Vector(0, 0, 0)) <= 2 for pos in positions)
    assert_pruned_region_reaches_outer_band(scenario)

    # visible
    scenario = compileScenic(
        """
        workspace = Workspace(RectangularRegion(0@0, 0, 1e10, 1e10))
        ego = new Object at (0,0,0), with visibleDistance 1, with allowCollisions True
        foo = new Object in workspace, visible,
            with shape SpheroidShape(dimensions=(2,2,2)),
            with allowCollisions True
        param p = foo.position
        """
    )
    positions = [sampleParamP(scenario, maxIterations=100) for i in range(30)]
    assert all(pos.distanceTo(Vector(0, 0, 0)) <= 2 for pos in positions)
    assert_pruned_region_reaches_outer_band(scenario)

    # requireVisible with offset
    baseOffsetVal = 0.0001
    scenario = compileScenic(
        f"""
        workspace = Workspace(RectangularRegion(0@0, 0, 1e10, 1e10))
        ego = new Object at (0,0,0), with visibleDistance 1, with allowCollisions True
        foo = new Object on workspace,
            with shape SpheroidShape(dimensions=(2,2,2)),
            with allowCollisions True,
            with requireVisible True,
            with baseOffset (0,0,{baseOffsetVal}), with contactTolerance 0
        param p = foo.position
        """
    )
    positions = [sampleParamP(scenario, maxIterations=100) for i in range(30)]
    assert all(pos.distanceTo(Vector(0, 0, 0)) <= 2 for pos in positions)
    assert_pruned_region_reaches_outer_band(scenario)
    assert all(pos.z == -baseOffsetVal for pos in positions)

    # visible with offset
    scenario = compileScenic(
        f"""
        workspace = Workspace(RectangularRegion(0@0, 0, 1e10, 1e10))
        ego = new Object at (0,0,0), with visibleDistance 1, with allowCollisions True
        foo = new Object on workspace, visible,
            with shape SpheroidShape(dimensions=(2,2,2)),
            with allowCollisions True,
            with baseOffset (0,0,{baseOffsetVal}), with contactTolerance 0
        param p = foo.position
        """
    )
    positions = [sampleParamP(scenario, maxIterations=100) for i in range(30)]
    assert all(pos.distanceTo(Vector(0, 0, 0)) <= 2 for pos in positions)
    assert_pruned_region_reaches_outer_band(scenario)
    assert all(pos.z == -baseOffsetVal for pos in positions)


def test_visibility_pruning_cyclical():
    """A case where a cyclical dependency could be introduced if pruning is not done carefully."""
    scenario = compileScenic(
        """
        workspace = Workspace(PolygonalRegion([0@0, 100@0, 100@100, 0@100]))
        foo = new Object with requireVisible True, in workspace
        ego = new Object visible from foo, in workspace
        """
    )

    sampleEgo(scenario, maxIterations=100)
