import math
import sys

import matplotlib.pyplot as plt
import pytest

import scenic
from scenic import scenarioFromString
from scenic.core.errors import (
    InvalidScenarioError,
    ScenicSyntaxError,
    SpecifierError,
    setDebuggingOptions,
)
from scenic.core.object_types import Object
from tests.utils import (
    compileScenic,
    sampleEgo,
    sampleEgoFrom,
    sampleParamPFrom,
    sampleScene,
)


def test_minimal():
    scenario = compileScenic("ego = new Object")
    assert len(scenario.objects) == 1
    obj = scenario.objects[0]
    assert type(obj) is Object
    assert obj is scenario.egoObject
    assert len(scenario.params) == 0
    assert len(scenario.requirements) == 0
    scene = sampleScene(scenario, maxIterations=1)
    assert len(scene.objects) == 1
    obj = scene.objects[0]
    assert type(obj) is Object
    assert obj is scene.egoObject
    assert len(scene.params) == 0


def test_ego_second():
    scenario = compileScenic("new Object\n" "ego = new Object at 0 @ -5")
    assert len(scenario.objects) == 2
    obj = scenario.objects[0]
    assert obj is scenario.egoObject
    scene = sampleScene(scenario, maxIterations=1)
    assert len(scene.objects) == 2
    obj = scene.objects[0]
    assert obj is scene.egoObject


def test_ego_nonobject():
    with pytest.raises(TypeError):
        compileScenic("ego = new Point")
    with pytest.raises(TypeError):
        compileScenic("ego = dict()")


def test_ego_subclass_point():
    with pytest.raises(TypeError):
        compileScenic(
            """
            class Foo(Point):
                pass
            ego = new Foo
            """
        )


def test_ego_subclass_orientedpoint():
    with pytest.raises(TypeError):
        compileScenic(
            """
            class Bar(OrientedPoint):
                pass
            ego = new Bar
            """
        )


def test_ego_undefined():
    with pytest.raises(InvalidScenarioError):
        compileScenic("x = ego\n" "ego = new Object")


def test_no_ego():
    compileScenic("new Object")


def test_new_in_list_expression():
    scenario = compileScenic(
        """
        objs = [new Object with allowCollisions True]
        ego = new Object with allowCollisions True
        """
    )
    assert len(scenario.objects) == 2
    scene = sampleScene(scenario, maxIterations=1)
    assert len(scene.objects) == 2


def test_ego_complex_assignment():
    with pytest.raises(ScenicSyntaxError):
        compileScenic("(ego, thing1), thing2 = ((new Object at 1@1), 2), 3")


def test_list_new():
    scenario = compileScenic("objs = [new Object at 10@10, new Object at 20@20]")
    assert len(scenario.objects) == 2
    scene = sampleScene(scenario, maxIterations=1)
    assert len(scene.objects) == 2
    pos = [obj.position.x for obj in scene.objects]
    assert pos == [10, 20]


def test_dict_new():
    scenario = compileScenic(
        """
        objs = {
            'a': new Object at 10@10,
            'b': new Object at 20@20
        }
        """
    )
    assert len(scenario.objects) == 2
    scene = sampleScene(scenario, maxIterations=1)
    assert len(scene.objects) == 2
    pos = [obj.position.x for obj in scene.objects]
    assert pos == [10, 20]


def test_noninterference():
    scenario = compileScenic("ego = new Object")
    assert len(scenario.objects) == 1
    ego1 = scenario.egoObject
    for i in range(5):
        scene = sampleScene(scenario, maxIterations=1)
    scenario = compileScenic("ego = new Object")
    assert len(scenario.objects) == 1
    ego2 = scenario.egoObject
    assert ego1 is not ego2


def test_param():
    p = sampleParamPFrom("ego = new Object\n" "param p = Range(3, 5)")
    assert 3 <= p <= 5
    p = sampleParamPFrom("ego = new Object\n" "param p = [1, 4, 9]")
    assert type(p) is list
    assert p == [1, 4, 9]
    p = sampleParamPFrom("ego = new Object\n" "param p = (1, 4)")
    assert type(p) is tuple
    assert p == (1, 4)


def test_quoted_param():
    p = sampleParamPFrom("ego = new Object\n" 'param "p" = Range(3, 5)')
    assert 3 <= p <= 5


def test_param_read():
    p = sampleParamPFrom(
        """
        ego = new Object
        param q = Range(3, 5)
        param p = globalParameters.q + 10
        """
    )
    assert 13 <= p <= 15


def test_param_write():
    with pytest.raises(ScenicSyntaxError):
        compileScenic("ego = new Object\n" "globalParameters = {}")


def test_mutate():
    scenario = compileScenic(
        """
        class Thing:
            foo: self.heading

        ego = new Thing at 3@1, facing 0
        mutate
        """
    )
    ego1 = sampleEgo(scenario)
    assert ego1.position.x != pytest.approx(3)
    assert ego1.position.y != pytest.approx(1)
    assert ego1.heading != pytest.approx(0)
    assert ego1.foo == 0


def test_mutate_object():
    scenario = compileScenic(
        """
        ego = new Object at 30@1, facing 0
        other = new Object
        mutate other
        """
    )
    scene = sampleScene(scenario)
    ego, other = scene.objects
    assert ego.position.x == pytest.approx(30)
    assert ego.position.y == pytest.approx(1)
    assert ego.heading == pytest.approx(0)
    assert other.position.x != pytest.approx(0)
    assert other.position.y != pytest.approx(0)
    assert other.heading != pytest.approx(0)


def test_mutate_scaled():
    scenario = compileScenic(
        """
        ego = new Object at 3@1, facing 0
        mutate ego by 4
        """
    )
    ego1 = sampleEgo(scenario)
    assert ego1.position.x != pytest.approx(3)
    assert ego1.position.y != pytest.approx(1)
    assert ego1.heading != pytest.approx(0)


def test_mutate_nonobject():
    with pytest.raises(TypeError):
        compileScenic(
            """
            ego = new Object
            mutate sin
            """
        )


def test_mutate_occupiedSpace():
    scenario = compileScenic(
        """
        ego = new Object at (1,2,3), with foo Range(1,2)
        mutate ego
        """
    )
    ego = sampleEgo(scenario)
    assert tuple(ego.position) == pytest.approx(tuple(ego.occupiedSpace.mesh.center_mass))


def test_verbose():
    for verb in range(4):
        setDebuggingOptions(verbosity=verb)
        compileScenic("ego = new Object")
    setDebuggingOptions(verbosity=1)


def test_dump_ast():
    scenic.syntax.translator.dumpScenicAST = True
    try:
        compileScenic("ego = new Object")
    finally:
        scenic.syntax.translator.dumpScenicAST = False
    scenic.syntax.translator.dumpFinalAST = True
    try:
        compileScenic("ego = new Object")
    finally:
        scenic.syntax.translator.dumpFinalAST = False


def test_dump_final_python():
    if sys.version_info < (3, 9):
        pytest.importorskip("astor")
    scenic.syntax.translator.dumpASTPython = True
    try:
        compileScenic("ego = new Object")
    finally:
        scenic.syntax.translator.dumpASTPython = False


@pytest.mark.graphical
def test_show2D():
    scenario = compileScenic("ego = new Object with color (0.5, 1.0, 0.5)")
    scene = sampleScene(scenario)
    scene.show2D(block=False)
    plt.close()


@pytest.mark.graphical
def test_show2D_zoom():
    scenario = compileScenic(
        """
        ego = new Object
        new Object at 10@20
        """
    )
    scene = sampleScene(scenario)
    scene.show2D(zoom=1, block=False)
    xmin, xmax, ymin, ymax = plt.axis()
    assert xmin < 0 and xmax > 10
    assert ymin < 0 and ymax > 20
    plt.close()


def test_mode2D():
    scenario = compileScenic(
        """
        region = RectangularRegion(0 @ 0, 0, 100, 100)
        p = new Point on region
        op = new OrientedPoint on region
        ego = new Object on region
        test_obj_1 = new Object in p.visibleRegion
        test_obj_2 = new Object in op.visibleRegion
        test_obj_3 = new Object in ego.visibleRegion
        """,
        mode2D=True,
    )
    for _ in range(5):
        scene, _ = scenario.generate()

        for obj in scene.objects:
            assert obj.position[2] == 0


def test_mode2D_heading():
    with pytest.raises(SpecifierError):
        compileScenic("ego = new Object with heading 40 deg")

    scenario = compileScenic("ego = new Object with heading 40 deg", mode2D=True)
    scene, _ = scenario.generate()

    assert scene.egoObject.heading == pytest.approx(math.radians(40))

    with pytest.raises(InvalidScenarioError):
        compileScenic(
            """
            class TestClass:
                heading: 40 deg

            ego = new TestClass
        """
        )

    scenario = compileScenic(
        """
        class TestClass:
            heading: 40 deg

        ego = new TestClass
        """,
        mode2D=True,
    )
    scene, _ = scenario.generate()

    assert scene.egoObject.heading == pytest.approx(math.radians(40))


def test_mode2D_interference():
    program = """
        region = RectangularRegion(0 @ 0, 0, 100, 100)
        p = new Point on region
        op = new OrientedPoint on region
        ego = new Object on region
        test_obj_1 = new Object in p.visibleRegion
        test_obj_2 = new Object in op.visibleRegion
        test_obj_3 = new Object in ego.visibleRegion
        """

    scenario = compileScenic(program, mode2D=True)
    for _ in range(5):
        scene, _ = scenario.generate()

        for obj in scene.objects:
            assert obj.position[2] == 0

    scenario = compileScenic(program)
    for _ in range(5):
        scene, _ = scenario.generate()

        assert any(obj.position[2] != 0 for obj in scene.objects)


def test_mode2D_heading_parentOrientation():
    program = """
            class Foo:
                heading: 0.56

            class Bar(Foo):
                parentOrientation: 1.2

            ego = new Bar
        """

    obj = sampleEgoFrom(program, mode2D=True)
    assert obj.heading == obj.parentOrientation.yaw == 1.2

    program = """
            class Bar:
                parentOrientation: 1.2

            class Foo(Bar):
                heading: 0.56

            ego = new Foo
        """

    obj = sampleEgoFrom(program, mode2D=True)
    assert obj.heading == obj.parentOrientation.yaw == 0.56


def test_simulator_name_binding_executes():
    scenario = compileScenic(
        """
        simulator = 7
        ego = new Object with foo simulator
        """
    )
    ego = sampleEgo(scenario)
    assert ego.foo == 7


def test_setSeed():
    scenic.setSeed(10)
    p1 = sampleParamPFrom("param p = Range(0, 1)")
    scenic.setSeed(10)
    p2 = sampleParamPFrom("param p = Range(0, 1)")
    p3 = sampleParamPFrom("param p = Range(0, 1)")

    assert p1 == p2
    assert p1 != p3
