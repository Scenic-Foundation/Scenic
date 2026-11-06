import math

import pytest

from scenic.core.errors import InvalidScenarioError
from scenic.core.vectors import Orientation
from tests.utils import (
    checkIfSamples,
    compileScenic,
    sampleEgoFrom,
    sampleParamP,
    sampleParamPFrom,
    sampleSceneFrom,
)

## Scalar operators


# Relative Heading
def test_relative_heading():
    p = sampleParamPFrom(
        """
        ego = new Object facing 30 deg
        other = new Object facing 65 deg, at 10@10
        param p = relative heading of other
        """
    )
    assert p == pytest.approx(math.radians(65 - 30))


def test_relative_heading_no_ego():
    with pytest.raises(InvalidScenarioError):
        compileScenic(
            """
            other = new Object
            ego = new Object at 2@2, facing relative heading of other
            """
        )


def test_relative_heading_from():
    ego = sampleEgoFrom("ego = new Object facing relative heading of 70 deg from -10 deg")
    assert ego.heading == pytest.approx(math.radians(70 + 10))


# Apparent heading
def test_apparent_heading():
    p = sampleParamPFrom(
        """
        ego = new Object facing 30 deg
        other = new Object facing 65 deg, at 10@10
        param p = apparent heading of other
        """
    )
    assert p == pytest.approx(math.radians(65 + 45))


def test_apparent_heading_no_ego():
    with pytest.raises(InvalidScenarioError):
        compileScenic(
            """
            other = new Object
            ego = new Object at 2@2, facing apparent heading of other
            """
        )


def test_apparent_heading_from():
    ego = sampleEgoFrom(
        """
        OP = new OrientedPoint at 10@15, facing -60 deg
        ego = new Object facing apparent heading of OP from 15@10
        """
    )
    assert ego.heading == pytest.approx(math.radians(-60 - 45))


# Angle
def test_angle():
    p = sampleParamPFrom(
        """
        ego = new Object facing 30 deg
        other = new Object facing 65 deg, at 10@10
        param p = angle to other
        """
    )
    assert p == pytest.approx(math.radians(-45))


def test_angle_3d():
    p = sampleParamPFrom(
        """
        ego = new Object facing (30 deg, 0 deg, 30 deg)
        other = new Object facing (65 deg, 0 deg, 65 deg), at (10, 10, 10)
        param p = angle to other
        """
    )
    assert p == pytest.approx(math.radians(-45))


def test_angle_no_ego():
    with pytest.raises(InvalidScenarioError):
        compileScenic(
            """
            other = new Object
            ego = new Object at 2@2, facing angle to other
        """
        )


def test_angle_from():
    ego = sampleEgoFrom("ego = new Object facing angle from 2@4 to 3@5")
    assert ego.heading == pytest.approx(math.radians(-45))


def test_angle_from_3d():
    ego = sampleEgoFrom("ego = new Object facing angle from (2, 4, 5) to (3, 5, 6)")
    assert ego.heading == pytest.approx(math.radians(-45))


# Altitude
def test_altitude_to():
    ego = sampleEgoFrom(
        "ego = new Object at (0,0,0)\n"
        "ego = new Object at (2,2,2), facing altitude to (1, 0, 1)"
    )
    assert ego.heading == pytest.approx(math.radians(45))


def test_altitude_from_to():
    ego = sampleEgoFrom("ego = new Object facing altitude from (0,0,0) to (1, 0, 1)")
    assert ego.heading == pytest.approx(math.radians(45))


# Distance
def test_distance():
    p = sampleParamPFrom(
        """
        ego = new Object at 5@10
        other = new Object at 7@-4
        param p = distance to other
        """
    )
    assert p == pytest.approx(math.hypot(7 - 5, -4 - 10))


def test_distance_3d():
    p = sampleParamPFrom(
        """
        ego = new Object at (5, 10, 20)
        other = new Object at (7, -4, 15)
        param p = distance to other
        """
    )
    assert p == pytest.approx(math.hypot(7 - 5, -4 - 10, 15 - 20))


def test_distance_no_ego():
    with pytest.raises(InvalidScenarioError):
        compileScenic(
            """
            other = new Object
            ego = new Object at 2@2, facing distance to other
        """
        )


def test_distance_from():
    ego = sampleEgoFrom("ego = new Object with wobble distance from -3@2 to 4@5")
    assert ego.wobble == pytest.approx(math.hypot(4 - -3, 5 - 2))


def test_distance_from_3d():
    ego = sampleEgoFrom(
        "ego = new Object with wobble distance from (-3, 2, 1) to (4, 5, 6)"
    )
    assert ego.wobble == pytest.approx(math.hypot(4 - -3, 5 - 2, 6 - 1))


def test_distance_to_region():
    p = sampleParamPFrom(
        """
        r = CircularRegion(10@5, 3)
        ego = new Object at 13@9
        param p = distance to r
        """
    )
    assert p == pytest.approx(2)


# Minimum Distance
def test_minimum_distance():
    p = sampleParamPFrom(
        """
        ego = new Object at (1.5, 2, 2.5),
            with width 1, with length 2, with height 3
        other = new Object at (-10, -10, -10),
            with width 2, with length 2, with height 2
        param p = minimum distance to other
        """
    )
    assert p == pytest.approx(math.hypot(10, 10, 10))


def test_minimum_distance_from():
    p = sampleParamPFrom(
        """
        foo = new Object at (1.5, 2, 2.5),
            with width 1, with length 2, with height 3
        bar = new Object at (-10, -10, -10),
            with width 2, with length 2, with height 2
        param p = minimum distance from foo to bar
        """
    )
    assert p == pytest.approx(math.hypot(10, 10, 10))


def test_minimum_distance_no_ego():
    with pytest.raises(InvalidScenarioError):
        sampleParamPFrom(
            """
            other = new Object at (-10, -10, -10),
                with width 2, with length 2, with height 2
            param p = minimum distance to other
            """
        )


def test_minimum_distance_2d():
    p = sampleParamPFrom(
        """
        ego = new Object at (1.5, 2),
            with width 1, with length 2
        other = new Object at (-10, -10),
            with width 2, with length 2
        param p = minimum distance to other
        """
    )
    assert p == pytest.approx(math.hypot(10, 10))


# Distance past


def test_distance_past():
    p = sampleParamPFrom(
        """
        ego = new Object at 5@10, facing 45 deg
        other = new Object at 2@3
        param p = distance past other
        """
    )
    assert p == pytest.approx(2 * math.sqrt(2))


def test_distance_past_of():
    p = sampleParamPFrom(
        """
        ego = new Object at 1@2, facing 30 deg
        op = new OrientedPoint at 3@-6, facing -45 deg
        param p = distance past ego of op
        """
    )
    assert p == pytest.approx(-3 * math.sqrt(2))


## Boolean operators ##


# Can See
def test_point_can_see_vector():
    p = []
    for target in ["8@19", "10@26"]:
        p.append(
            checkIfSamples(
                f"""
            ego = new Object
            pt = new Point at 10@20, with visibleDistance 5
            require pt can see {target}
        """
            )
        )
    assert p == [True, False]


def test_point_can_see_vector_3d():
    p = []
    for target in ["(8,19,0)", "(10,26,0)", "(10,20,4)"]:
        p.append(
            checkIfSamples(
                f"""
            ego = new Object
            pt = new Point at (10,20,0), with visibleDistance 5
            require pt can see {target}
        """
            )
        )
    assert p == [True, False, True]


def test_point_can_see_point():
    p = []
    for target in ["(new Point at 8@19)", "new Point at 10@26"]:
        p.append(
            checkIfSamples(
                f"""
            ego = new Object
            pt = new Point at (10,20,0), with visibleDistance 5
            require pt can see {target}
        """
            )
        )
    assert p == [True, False]


def test_point_can_see_object():
    p = []
    for target in ["ego", "other"]:
        p.append(
            checkIfSamples(
                f"""
            ego = new Object with width 10, with length 10
            other = new Object at 35@10
            pt = new Point at 15@10, with visibleDistance 15
            require pt can see {target}
        """
            )
        )
    assert p == [True, False]


def test_oriented_point_can_see_vector():
    p = []
    for target in ["2@2", "4@4", "1@0"]:
        p.append(
            checkIfSamples(
                f"""
            ego = new Object facing -45 deg, with visibleDistance 5, with viewAngle 20 deg
            require ego can see {target}
        """
            )
        )
    assert p == [True, False, False]


def test_oriented_point_can_see_object():
    p = []
    for target in ["other", "other2"]:
        p.append(
            checkIfSamples(
                f"""
            ego = new Object facing -45 deg, with visibleDistance 5, with viewAngle 20 deg
            other = new Object at 4@4, with width 2, with length 2
            other2 = new Object at 4@0, with requireVisible False
            require ego can see {target}
        """
            )
        )
    assert p == [True, False]


@pytest.mark.slow
def test_can_see_occlusion():
    p = checkIfSamples(
        """
        workspace_region = RectangularRegion(0 @ 0, 0, 40, 40)
        workspace = Workspace(workspace_region)

        ego = new Object with visibleDistance 30,
            at (0,0,1),
            with width 5,
            with length 5,
            with height 5,
            with pitch 45 deg,
            with viewAngles (340 deg, 60 deg),
            with rayDensity 1

        target_obj = new Object at (0,10,5),
            with width 2,
            with height 2,
            with length 2,
            with name "targetObject"

        new Object at (0,5,4),
            with width 10,
            with length 0.5,
            with height 6,
            with name "wall",
            with occluding False

        require ego can see target_obj
        """
    )
    assert p == True

    p = checkIfSamples(
        """
        workspace_region = RectangularRegion(0 @ 0, 0, 40, 40)
        workspace = Workspace(workspace_region)

        ego = new Object with visibleDistance 30,
            at (0,0,1),
            with width 5,
            with length 5,
            with height 5,
            with pitch 45 deg,
            with viewAngles (340 deg, 60 deg),
            with rayDensity 1

        target_obj = new Object at (0,10,5),
            with width 2,
            with height 2,
            with length 2,
            with name "targetObject"

        new Object at (0,5,4),
            with width 10,
            with length 0.5,
            with height 6,
            with name "wall"

        require ego can see target_obj
        """
    )
    assert p == False


@pytest.mark.slow
def test_can_see_distance_scaling():
    # First test with no occlusion
    p = checkIfSamples(
        """
        ego = new Object with visibleDistance 1000000,
            with viewAngles(45 deg, 45 deg),
            with viewRayDistanceScaling True

        target_obj = new Object at (0, 100000, 0)

        require ego can see target_obj
        """
    )

    assert p == True

    # Second test with occluding object
    p = checkIfSamples(
        """
        ego = new Object with visibleDistance 1000000,
            with viewAngles(45 deg, 45 deg),
            with viewRayDistanceScaling True

        target_obj = new Object at (0, 100000, 0)

        occluding_obj = new Object at (0,0,0),
            on target_obj.backSurface, with onDirection (0,1,0),
            with width 0.75, with length 0.75, with height 0.75

        require ego can see target_obj
        """
    )

    assert p == True


@pytest.mark.slow
def test_can_see_altitude_optimization():
    for roll in (0, 90, 180, 270):
        p = checkIfSamples(
            f"""
            import trimesh

            foo = new Object with roll {roll} deg,
                with viewAngles(360 deg, 180 deg), with viewRayDensity 5

            bar = new Object at (0,5,0), with width 100, with height 100

            obstacle_shape = trimesh.creation.box(extents=(1,1,1)).difference(\
                trimesh.creation.box(extents=(0.5,2,0.3),\
                transform=trimesh.transformations.translation_matrix((0,0,0.5))))
            new Object at (0,3.9,0), with width 100, with height 100,
                with shape MeshShape(mesh=obstacle_shape)

            require foo can see bar
        """
        )

        assert p == True, roll


def test_can_see_top_level():
    with pytest.raises(InvalidScenarioError):
        sampleSceneFrom(
            """
            ego = new Object
            foo = new Object at Range(0,3) @ 2
            v = ego can see foo
        """
        )


# In
def test_point_in_region_2d():
    p = sampleParamPFrom(
        """
        ego = new Object
        reg = RectangularRegion(10@5, 0, 4, 2)
        ptA = new Point at 11@4.5
        ptB = new Point at 11@3.5
        ptC = new Point at (11, 4.5, 1)
        param p = (9@5.5 in reg, 9@7 in reg, (11, 4.5, -1) in reg, ptA in reg, ptB in reg, ptC in reg)
        """
    )
    assert p == (True, False, True, True, False, True)


def test_object_in_region_2d():
    p = sampleParamPFrom(
        """
        reg = RectangularRegion(10@5, 0, 4, 2)
        ego = new Object at 11.5@5.5, with width 0.25, with length 0.25
        other_1 = new Object at 9@4.5, with width 2.5
        other_2 = new Object at (11.5, 5.5, 2), with width 0.25, with length 0.25
        param p = (ego in reg, other_1 in reg, other_2 in reg)
        """
    )
    assert p == (True, False, True)


def test_point_in_region_3d():
    p = sampleParamPFrom(
        """
        ego = new Object
        reg = BoxRegion()
        ptA = new Point at (0.25,0.25,0.25)
        ptB = new Point at (1,1,1)
        param p = ((0,0,0) in reg, (0.49,0.49,0.49) in reg, (0.5,0.5,0.5) in reg, (0.51,0.51,0.51) in reg, ptA in reg, ptB in reg)
        """
    )
    assert p == (True, True, True, False, True, False)


def test_object_in_region_3d():
    p = sampleParamPFrom(
        """
        ego = new Object
        reg = BoxRegion(dimensions=(2,2,2))
        obj_1 = new Object at (0,0,0), with allowCollisions True
        obj_2 = new Object at (0.49, 0.49, 0.49), with allowCollisions True
        obj_3 = new Object at (0.75, 0.75, 0.75), with allowCollisions True
        obj_4 = new Object at (3,3,3), with allowCollisions True
        param p = (obj_1 in reg, obj_2 in reg, obj_3 in reg, obj_4 in reg)
        """
    )
    assert p == (True, True, False, False)


# Intersects
def test_intersects_obj_obj():
    p = sampleParamPFrom(
        """
        obj1 = new Object at (-1,0,0.1), with allowCollisions True
        obj2 = new Object at (1,0,0), with allowCollisions True
        obj3 = new Object with width 10, with length 10, with height 10, with allowCollisions True
        param p = (obj1 intersects obj2, obj1 intersects obj3, obj2 intersects obj3)
        """
    )
    assert p == (False, True, True)

    # Case where neither corners or centers intersect, but
    # Objects still intersect.
    p = sampleParamPFrom(
        """
        obj1 = new Object at (10,0,0), with width 30, with allowCollisions True
        obj2 = new Object at (0,10,0), with length 30, with allowCollisions True
        param p = (obj1 intersects obj2,
            obj1.position in obj2.occupiedSpace, obj2.position in obj1.occupiedSpace,
            any((c in obj2.occupiedSpace) for c in obj1.corners),
            any((c in obj1.occupiedSpace) for c in obj2.corners))
        """
    )
    assert p == (True, False, False, False, False)


def test_intersects_region_region():
    p = sampleParamPFrom(
        """
        reg1 = BoxRegion(position=(-1,0,0.1))
        reg2 = BoxRegion(position=(1,0,0))
        reg3 = BoxRegion(dimensions=(10,10,10))
        param p = (reg1 intersects reg2, reg1 intersects reg3, reg2 intersects reg3)
        """
    )
    assert p == (False, True, True)


def test_intersects_obj_region():
    p = sampleParamPFrom(
        """
        reg1 = BoxRegion(position=(-1,0,0.1))
        obj2 = new Object at (1,0,0), with allowCollisions True
        obj3 = new Object with width 10, with length 10, with height 10, with allowCollisions True
        param p = (reg1 intersects obj2, obj2 intersects reg1,
            reg1 intersects obj3, obj3 intersects reg1)
        """
    )
    assert p == (False, False, True, True)


def test_intersects_2d():
    p = sampleParamPFrom(
        """
        obj1 = new Object at (0.2,0,0), with allowCollisions True
        obj2 = new Object at (-0.2,0,0), with allowCollisions True
        reg = RectangularRegion((0,0,0), 0, 10, 10)
        param p = (obj1 intersects obj2, obj1 intersects reg)
        """
    )
    assert p == (True, True)


def test_intersects_non_0_z():
    p = sampleParamPFrom(
        """
        obj1 = new Object at (0.2,0,1), with allowCollisions True
        obj2 = new Object at (-0.2,0,1), with allowCollisions True
        reg = RectangularRegion((0,0,1), 0, 10, 10)
        param p = (obj1 intersects obj2, obj1 intersects reg)
        """
    )
    assert p == (True, True)


def test_intersects_overlap():
    p = sampleParamPFrom(
        """
        obj = new Object at (0,0,0), with allowCollisions True
        reg = RectangularRegion((0.5,0,0), 0, 1, 1)
        param p = obj intersects reg
        """
    )
    assert p == True


def test_intersects_diff_z():
    p = sampleParamPFrom(
        """
        obj1 = new Object at (0,0,0.1), with allowCollisions True
        obj2 = new Object at (0,0,10), with allowCollisions True
        reg = RectangularRegion((0,0,0), 0, 10, 10)
        param p = (obj1 intersects reg, obj2 intersects reg, obj1 intersects obj2)
        """
    )
    assert p == (True, False, False)


## Heading operators


# At
def test_field_at_vector():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: (3 * pos.x) + pos.y)
        ego = new Object facing (vf at 0.02 @ -1)
        """
    )
    assert ego.heading == pytest.approx((3 * 0.02) - 1)


def test_field_at_vector_3d():
    ego = sampleEgoFrom(
        'vf = VectorField("Foo", lambda pos: (pos.x deg, pos.y deg, pos.z deg))\n'
        "ego = new Object facing (vf at (1, 5, 3))"
    )
    assert ego.heading == pytest.approx(
        Orientation.fromEuler(math.radians(1), math.radians(5), math.radians(3)).yaw
    )


# Relative To
def test_heading_relative_to_field():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 3 * pos.x)
        ego = new Object at 0.07 @ 0, facing 0.5 relative to vf
        """
    )
    assert ego.heading == pytest.approx(0.5 + (3 * 0.07))


def test_field_relative_to_heading():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 3 * pos.x)
        ego = new Object at 0.07 @ 0, facing vf relative to 0.5
        """
    )
    assert ego.heading == pytest.approx(0.5 + (3 * 0.07))


def test_field_relative_to_field():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 3 * pos.x)
        ego = new Object at 0.07 @ 0, facing vf relative to vf
        """
    )
    assert ego.heading == pytest.approx(2 * (3 * 0.07))


def test_vector_relative_to_vector():
    ego = sampleEgoFrom("ego = new Object at (1,2,3) relative to (4,5,6)")
    assert ego.position == (5, 7, 9)


def test_heading_relative_to_heading():
    ego = sampleEgoFrom("ego = new Object facing 0.5 relative to -0.3")
    assert ego.heading == pytest.approx(0.5 - 0.3)


def test_heading_relative_to_heading_lazy():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 0.5)
        ego = new Object facing 0.5 relative to (0.5 relative to vf)
        """
    )
    assert ego.heading == pytest.approx(1.5)


def test_orientation_relative_to_orientation():
    ego = sampleEgoFrom(
        """
        o1 = Orientation.fromEuler(90 deg, 0, 0)
        o2 = Orientation.fromEuler(0, 90 deg, 0)
        ego = new Object facing o2 relative to o1
        """
    )
    assert ego.orientation.approxEq(Orientation.fromEuler(math.pi / 2, math.pi / 2, 0))


def test_orientation_relative_to_orientation2():
    ego = sampleEgoFrom(
        """
        ego = new Object facing (Orientation.fromEuler(-135 deg, 45 deg, 0)
            relative to Orientation.fromEuler(90 deg, 0, 0))
        """
    )
    assert ego.yaw == pytest.approx(math.radians(-45))
    assert ego.pitch == pytest.approx(math.radians(45))
    assert ego.roll == pytest.approx(0)
    assert ego.orientation.approxEq(
        Orientation.fromEuler(math.radians(-45), math.radians(45), 0)
    )


def test_heading_relative_to_orientation():
    ego = sampleEgoFrom(
        """
        h1 = 90 deg
        o2 = Orientation.fromEuler(0, 90 deg, 0)
        ego = new Object facing o2 relative to h1
        """
    )
    assert ego.orientation.approxEq(Orientation.fromEuler(math.pi / 2, math.pi / 2, 0))


def test_orientation_relative_to_heading():
    ego = sampleEgoFrom(
        """
        o1 = Orientation.fromEuler(90 deg, 0, 0)
        h2 = 90 deg
        ego = new Object facing h2 relative to o1
        """
    )
    assert ego.orientation.approxEq(Orientation.fromEuler(math.pi, 0, 0))


def test_tuple_relative_to_orientation():
    with pytest.raises(TypeError):
        compileScenic(
            """
            o1 = Orientation.fromEuler(90 deg, 0, 0)
            v2 = (0, 90 deg, 0)
            ego = new Object facing v2 relative to o1
        """
        )


def test_mistyped_relative_to():
    with pytest.raises(TypeError):
        compileScenic("ego = new Object facing 0 relative to 1@2")


def test_mistyped_relative_to_lazy():
    with pytest.raises(TypeError):
        compileScenic(
            """
            vf = VectorField("Foo", lambda pos: 0.5)
            ego = new Object facing 1@2 relative to (0 relative to vf)
        """
        )


def test_relative_to_ambiguous():
    with pytest.raises(TypeError):
        compileScenic(
            """
            ego = new Object
            thing = ego relative to ego
        """
        )


## Vector operators


# Relative To
def test_relative_to_vector():
    ego = sampleEgoFrom("ego = new Object at 3@2 relative to -4@10")
    assert tuple(ego.position) == pytest.approx((-1, 12, 0))


def test_relative_to_vector_3d():
    ego = sampleEgoFrom("ego = new Object at (3, 2, 1) relative to (-4, 10, 5)")
    assert tuple(ego.position) == pytest.approx((-1, 12, 6))


def test_relative_to_oriented_point():
    ego = sampleEgoFrom(
        "op = new OrientedPoint at (12,13,14), facing (90 deg, 0, 0)\n"
        "ego = new Object at ((1,0,0) relative to op)"
    )
    assert tuple(ego.position) == pytest.approx((12, 14, 14))


# Offset By
def test_offset_by():
    ego = sampleEgoFrom("ego = new Object at 3@2 offset by -4@10")
    assert tuple(ego.position) == pytest.approx((-1, 12, 0))


def test_offset_by_3d():
    ego = sampleEgoFrom("ego = new Object at (3, 2, 1) offset by (-4, 10, 5)")
    assert tuple(ego.position) == pytest.approx((-1, 12, 6))


# Offset Along
def test_offset_along_heading():
    ego = sampleEgoFrom("ego = new Object at 3@2 offset along 45 deg by -4@10")
    d = 1 / math.sqrt(2)
    assert tuple(ego.position) == pytest.approx(
        (3 - 10 * d - 4 * d, 2 + 10 * d - 4 * d, 0)
    )


def test_offset_along_heading_3d():
    ego = sampleEgoFrom(
        "ego = new Object at (3, 2, 7) offset along (90 deg, 0 deg, 90 deg) by (4, 10, 5)"
    )
    assert tuple(ego.position) == pytest.approx((-7, 7, 3))


def test_offset_along_field():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 3 deg * pos.x)
        ego = new Object at 15@7 offset along vf by 2@-3
        """
    )
    d = 1 / math.sqrt(2)
    assert tuple(ego.position) == pytest.approx(
        (15 + 3 * d + 2 * d, 7 - 3 * d + 2 * d, 0)
    )


def test_offset_along_field_3d():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 3 deg * pos.x) 
        ego = new Object at (15, 7, 5) offset along vf by (2, -3, 4) 
        """
    )
    d = 1 / math.sqrt(2)
    assert tuple(ego.position) == pytest.approx(
        (15 + 3 * d + 2 * d, 7 - 3 * d + 2 * d, 9)
    )


# Follow
def test_follow():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 90 deg * (pos.x + pos.y - 1),
                         minSteps=4, defaultStepSize=1)
        p = follow vf from 1@1 for 4
        ego = new Object at p, facing p.heading
        """
    )
    assert tuple(ego.position) == pytest.approx((-1, 3, 0))
    assert ego.heading == pytest.approx(math.radians(90))


def test_follow_3d():
    ego = sampleEgoFrom(
        """
        vf = VectorField("Foo", lambda pos: 90 deg * (pos.x + pos.y - 1),
                         minSteps=4, defaultStepSize=1)
        p = follow vf from (1, 1, 1) for 4
        ego = new Object at p, facing p.heading
        """
    )
    assert tuple(ego.position) == pytest.approx((-1, 3, 1))
    assert ego.heading == pytest.approx(math.radians(90))


# relative position


def test_relative_position():
    p = sampleParamPFrom(
        """
        ego = new Object at 1@2
        param p = relative position of 5@1
        """
    )
    assert tuple(p) == (4, -1, 0)


def test_relative_position_from():
    p = sampleParamPFrom(
        """
        ego = new Object at 1@2
        param p = relative position of ego from 5@1
        """
    )
    assert tuple(p) == (-4, 1, 0)


## Region operators


# Visible
def test_visible():
    scenario = compileScenic(
        """
        ego = new Object at 100 @ 200, facing -45 deg,
                     with visibleDistance 10, with viewAngle 90 deg
        reg = RectangularRegion(100@205, 0, 10, 20)
        param p = new Point in visible reg
        """
    )
    for i in range(30):
        p = sampleParamP(scenario, maxIterations=10)
        assert p.x >= 100
        assert p.y >= 200
        assert math.hypot(p.x - 100, p.y - 200) <= 10


def test_not_visible():
    scenario = compileScenic(
        """
        ego = new Object at 100 @ 200, facing -45 deg,
                     with visibleDistance 30, with viewAngle 90 deg
        reg = RectangularRegion(100@200, 0, 10, 10)
        param p = new Point in not visible reg
        """
    )
    ps = [sampleParamP(scenario, maxIterations=10) for i in range(50)]
    assert all(p.x <= 100 or p.y <= 200 for p in ps)
    assert any(p.x > 100 for p in ps)
    assert any(p.y > 200 for p in ps)


# visible from


def test_visible_from():
    scenario = compileScenic(
        """
        ego = new Object at 100 @ 200, facing -45 deg,
                     with visibleDistance 10, with viewAngle 90 deg
        reg = RectangularRegion(100@205, 0, 10, 20)
        param p = new Point in reg visible from ego
        """
    )
    for i in range(30):
        p = sampleParamP(scenario, maxIterations=10)
        assert p.x >= 100
        assert p.y >= 200
        assert math.hypot(p.x - 100, p.y - 200) <= 10


# not visible from
def test_not_visible_from():
    scenario = compileScenic(
        """
        ego = new Object at 100 @ 200, facing -45 deg,
                     with visibleDistance 30, with viewAngle 90 deg
        reg = RectangularRegion(100@200, 0, 10, 10)
        param p = new Point in reg not visible from ego
        """
    )
    ps = [sampleParamP(scenario, maxIterations=10) for i in range(50)]
    assert all(p.x <= 100 or p.y <= 200 for p in ps)
    assert any(p.x > 100 for p in ps)
    assert any(p.y > 200 for p in ps)


# Directional Operators
# NOTE: The following don't account for rotation.
DIRECTION_LOCS = {
    "front": (0, 0.5, 0),
    "back": (0, -0.5, 0),
    "right": (0.5, 0, 0),
    "left": (-0.5, 0, 0),
    "top": (0, 0, 0.5),
    "bottom": (0, 0, -0.5),
    "front right": (0.5, 0.5, 0),
    "front left": (-0.5, 0.5, 0),
    "back right": (0.5, -0.5, 0),
    "back left": (-0.5, -0.5, 0),
    "top front right": (0.5, 0.5, 0.5),
    "top front left": (-0.5, 0.5, 0.5),
    "top back right": (0.5, -0.5, 0.5),
    "top back left": (-0.5, -0.5, 0.5),
    "bottom front right": (0.5, 0.5, -0.5),
    "bottom front left": (-0.5, 0.5, -0.5),
    "bottom back right": (0.5, -0.5, -0.5),
    "bottom back left": (-0.5, -0.5, -0.5),
}


@pytest.mark.parametrize("direction,loc", DIRECTION_LOCS.items())
def test_direction_ops(direction, loc):
    p = sampleParamPFrom(
        f"""
        ego = new Object facing (0, 180 deg, 0)
        param p = {direction} of ego
        """
    )
    oriented_loc = (loc[0], -loc[1], -loc[2])
    assert tuple(p.position) == pytest.approx(oriented_loc)
