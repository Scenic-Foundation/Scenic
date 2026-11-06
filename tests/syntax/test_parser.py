# pytest: python >= 3.10

from ast import *
from inspect import cleandoc
from typing import Any

import pytest

from scenic.core.errors import ScenicParseError, ScenicSyntaxError
from scenic.syntax.ast import *
from scenic.syntax.parser import parse_string


def parse_string_helper(source: str) -> Any:
    "Parse string and return Scenic AST"
    return parse_string(cleandoc(source), "exec")


def assert_equal_source_ast(source: str, expected: ast.AST) -> bool:
    "Parse string and compare the resulting AST with the given AST"
    mod = parse_string_helper(source)
    stmt = mod.body[0].value
    assert dump(stmt, annotate_fields=False) == dump(expected, annotate_fields=False)


class TestTry:
    def test_try_interrupt_when(self):
        mod = parse_string_helper(
            """
        try:
            foo()
        interrupt when x:
            bar()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case TryInterrupt(
                body=[Expr(Call(Name("foo")))],
                interrupt_when_handlers=[
                    InterruptWhenHandler(cond=Name("x"), body=[Expr(Call(Name("bar")))])
                ],
                except_handlers=[],
                orelse=[],
                finalbody=[],
            ):
                assert True
            case _:
                assert False

    def test_try_interrupt_when_multiple(self):
        mod = parse_string_helper(
            """
        try:
            foo()
        interrupt when x:
            bar()
        interrupt when y:
            baz()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case TryInterrupt(
                body=[Expr(Call(Name("foo")))],
                interrupt_when_handlers=[
                    InterruptWhenHandler(cond=Name("x"), body=[Expr(Call(Name("bar")))]),
                    InterruptWhenHandler(cond=Name("y"), body=[Expr(Call(Name("baz")))]),
                ],
                except_handlers=[],
                orelse=[],
                finalbody=[],
            ):
                assert True
            case _:
                assert False

    def test_try_interrupt_when_except(self):
        mod = parse_string_helper(
            """
        try:
            foo()
        interrupt when x:
            bar()
        except ErrorA:
            baz()
        except ErrorB:
            qux()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case TryInterrupt(
                body=[Expr(Call(Name("foo")))],
                interrupt_when_handlers=[
                    InterruptWhenHandler(cond=Name("x"), body=[Expr(Call(Name("bar")))])
                ],
                except_handlers=[
                    ExceptHandler(type=Name("ErrorA"), body=[Expr(Call(Name("baz")))]),
                    ExceptHandler(type=Name("ErrorB"), body=[Expr(Call(Name("qux")))]),
                ],
                orelse=[],
                finalbody=[],
            ):
                assert True
            case _:
                assert False

    def test_try_interrupt_when_except_else_finally(self):
        mod = parse_string_helper(
            """
        try:
            foo()
        interrupt when x:
            bar()
        except ErrorA:
            baz()
        else:
            qux()
        finally:
            quux()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case TryInterrupt(
                body=[Expr(Call(Name("foo")))],
                interrupt_when_handlers=[
                    InterruptWhenHandler(cond=Name("x"), body=[Expr(Call(Name("bar")))])
                ],
                except_handlers=[
                    ExceptHandler(type=Name("ErrorA"), body=[Expr(Call(Name("baz")))]),
                ],
                orelse=[Expr(Call(Name("qux")))],
                finalbody=[Expr(Call(Name("quux")))],
            ):
                assert True
            case _:
                assert False


class TestTrackedNames:
    def test_ego_assign(self):
        mod = parse_string_helper("ego = 10")
        stmt = mod.body[0]
        match stmt:
            case TrackedAssign(Ego(), Constant(10)):
                assert True
            case _:
                assert False

    def test_ego_assign_with_new(self):
        mod = parse_string_helper("ego = new Object")
        stmt = mod.body[0]
        match stmt:
            case TrackedAssign(Ego(), New("Object")):
                assert True
            case _:
                assert False

    def test_workspace_assign(self):
        mod = parse_string_helper("workspace = Workspace()")
        stmt = mod.body[0]
        match stmt:
            case TrackedAssign(Workspace(), Call(Name("Workspace"))):
                assert True
            case _:
                assert False


class TestAssign:
    def test_tuple_lhs_parses(self):
        mod = parse_string_helper("a, b = 1, 2")
        stmt = mod.body[0]
        match stmt:
            case Assign(
                targets=[Tuple([Name("a"), Name("b")])],
                value=Tuple([Constant(1), Constant(2)]),
            ):
                assert True
            case _:
                assert False


class TestInitialScenario:
    def test_initial_scenario(self):
        mod = parse_string_helper("initial scenario")
        stmt = mod.body[0]
        match stmt:
            case Expr(InitialScenario()):
                assert True
            case _:
                assert False


class TestClass:
    def test_basic(self):
        mod = parse_string_helper(
            """
            class C:
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ClassDef(name="C", bases=[], keywords=[]):
                assert True
            case _:
                assert False

    def test_property_def(self):
        mod = parse_string_helper(
            """
            class C:
                property: value
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ClassDef(
                name="C",
                bases=[],
                keywords=[],
                body=[PropertyDef("property", [], Name("value", Load()))],
            ):
                assert True
            case _:
                assert False

    def test_property_def_with_attr(self):
        mod = parse_string_helper(
            """
            class C:
                property[additive]: value
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ClassDef(
                name="C",
                bases=[],
                keywords=[],
                body=[PropertyDef("property", [Additive()], Name("value", Load()))],
            ):
                assert True
            case _:
                assert False

    def test_property_def_with_multiple(self):
        mod = parse_string_helper(
            """
            class C:
                property[additive, dynamic, final]: value
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ClassDef(
                name="C",
                bases=[],
                keywords=[],
                body=[
                    PropertyDef(
                        "property",
                        [Additive(), Dynamic(), Final()],
                        Name("value", Load()),
                    )
                ],
            ):
                assert True
            case _:
                assert False

    def test_property_def_unknown_attribute_1(self):
        with pytest.raises(ScenicSyntaxError):
            parse_string_helper(
                """
                class C:
                    property[unknown]: value
                """
            )

    def test_property_def_unknown_attribute_2(self):
        # must raise an error even if attribute is not a NAME
        with pytest.raises(ScenicSyntaxError):
            parse_string_helper(
                """
                class C:
                    property[2]: value
                """
            )

    def test_property_def_nested(self):
        # property definition is allowed only on the top level
        mod = parse_string_helper(
            """
            class C:
                if True:
                    property: value
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ClassDef(
                name="C",
                bases=[],
                keywords=[],
                body=[
                    If(
                        Constant(True),
                        [
                            AnnAssign(
                                Name("property", Store()), Name("value", Load()), None
                            )
                        ],
                    )
                ],
            ):
                assert True
            case _:
                assert False


class TestBehaviorDef:
    def test_basic(self):
        mod = parse_string_helper(
            """
            behavior test():
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case BehaviorDef(
                "test",
                arguments([], [], None, [], [], None, []),
                None,
                [],
                [Pass()],
            ):
                assert True
            case _:
                assert False

    def test_no_parentheses(self):
        with pytest.raises(ScenicSyntaxError):
            parse_string_helper(
                """
                behavior test:
                    pass
                """
            )

    def test_parameter(self):
        mod = parse_string_helper(
            """
            behavior test(x, y = "hello"):
                pass
        """
        )
        stmt = mod.body[0]
        match stmt:
            case BehaviorDef(
                "test",
                arguments(args=[arg("x"), arg("y")], defaults=[Constant("hello")]),
                None,
                [],
                [Pass()],
            ):
                assert True
            case _:
                assert False

    def test_precondition(self):
        mod = parse_string_helper(
            """
            behavior test():
                precondition: True
                pass
        """
        )
        stmt = mod.body[0]
        match stmt:
            case BehaviorDef(
                "test",
                arguments(),
                None,
                [Precondition(Constant(True))],
                [Pass()],
            ):
                assert True
            case _:
                assert False

    def test_invariant(self):
        mod = parse_string_helper(
            """
            behavior test():
                invariant: True
                pass
        """
        )
        stmt = mod.body[0]
        match stmt:
            case BehaviorDef(
                "test",
                arguments(),
                None,
                [Invariant(Constant(True))],
                [Pass()],
            ):
                assert True
            case _:
                assert False

    def test_precondition_and_invariant(self):
        mod = parse_string_helper(
            """
            behavior test():
                precondition: True
                invariant: True
                precondition: True
                pass
        """
        )
        stmt = mod.body[0]
        match stmt:
            case BehaviorDef(
                "test",
                arguments(),
                None,
                [
                    Precondition(Constant(True)),
                    Invariant(Constant(True)),
                    Precondition(Constant(True)),
                ],
                [Pass()],
            ):
                assert True
            case _:
                assert False

    def test_invalid_precondition(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper(
                """
                behavior test():
                    hello()
                    precondition: True
                """
            )

    def test_invalid_invariant(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper(
                """
                behavior test():
                    hello()
                    invariant: True
                """
            )

    def test_empty_body(self):
        with pytest.raises(ScenicSyntaxError):
            mod = parse_string_helper(
                """
                behavior test():
                    invariant: True
                """
            )

    def test_docstring(self):
        mod = parse_string_helper(
            """
            behavior test():
                \"\"\"DOCSTRING\"\"\"
                invariant: True
                body()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case BehaviorDef(
                "test",
                arguments(),
                '"""DOCSTRING"""',
                [
                    Invariant(Constant(True)),
                ],
                [Expr(Call(Name("body")))],
            ):
                assert True
            case _:
                assert False


class TestMonitorDef:
    def test_basic(self):
        mod = parse_string_helper(
            """
            monitor Monitor():
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case MonitorDef("Monitor", arguments(), None, [Pass()]):
                assert True
            case _:
                assert False

    def test_arguments(self):
        mod = parse_string_helper(
            """
            monitor Monitor(arg1, arg2=None):
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case MonitorDef(
                "Monitor",
                arguments(args=[arg("arg1"), arg("arg2")], defaults=[Constant(None)]),
                None,
                [Pass()],
            ):
                assert True
            case _:
                assert False

    def test_docstring(self):
        mod = parse_string_helper(
            """
            monitor Monitor():
                \"\"\"DOCSTRING\"\"\"
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case MonitorDef("Monitor", arguments(), '"""DOCSTRING"""', [Pass()]):
                assert True
            case _:
                assert False


class TestScenarioDef:
    def test_basic(self):
        mod = parse_string_helper(
            """
            scenario A:
                precondition: P
                invariant: I
                setup:
                    foo()
                compose:
                    bar()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef(
                "A",
                arguments(),
                None,
                [Precondition(Name("P")), Invariant(Name("I"))],
                [Expr(Call(Name("foo")))],
                [Expr(Call(Name("bar")))],
            ):
                assert True
            case _:
                assert False

    def test_args(self):
        mod = parse_string_helper(
            """
            scenario A(x, y = "hello"):
                setup:
                    foo()
                compose:
                    bar()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef(
                "A",
                arguments(args=[arg("x"), arg("y")], defaults=[Constant("hello")]),
                None,
                [],
                [Expr(Call(Name("foo")))],
                [Expr(Call(Name("bar")))],
            ):
                assert True
            case _:
                assert False

    def test_setup_only(self):
        mod = parse_string_helper(
            """
            scenario A:
                setup:
                    pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef("A", arguments(), None, [], [Pass()], []):
                assert True
            case _:
                assert False

    def test_setup_only_implicit(self):
        mod = parse_string_helper(
            """
            scenario A:
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef("A", arguments(), None, [], [Pass()], []):
                assert True
            case _:
                assert False

    def test_setup_only_implicit_docstring(self):
        mod = parse_string_helper(
            """
            scenario A:
                '''DOCSTRING'''
                pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef("A", arguments(), "'''DOCSTRING'''", [], [Pass()], []):
                assert True
            case _:
                assert False

    def test_compose_only(self):
        mod = parse_string_helper(
            """
            scenario A:
                compose:
                    pass
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef("A", arguments(), None, [], [], [Pass()]):
                assert True
            case _:
                assert False

    def test_docstring(self):
        mod = parse_string_helper(
            """
            scenario A:
                'DOCSTRING'
                precondition: P
                invariant: I
                setup:
                    foo()
                compose:
                    bar()
            """
        )
        stmt = mod.body[0]
        match stmt:
            case ScenarioDef(
                "A",
                arguments(),
                "'DOCSTRING'",
                [Precondition(Name("P")), Invariant(Name("I"))],
                [Expr(Call(Name("foo")))],
                [Expr(Call(Name("bar")))],
            ):
                assert True
            case _:
                assert False


class TestModel:
    def test_basic(self):
        mod = parse_string_helper("model some_model")
        stmt = mod.body[0]
        match stmt:
            case Model("some_model"):
                assert True
            case _:
                assert False

    def test_dotted(self):
        mod = parse_string_helper("model scenic.simulators.carla.model")
        stmt = mod.body[0]
        match stmt:
            case Model("scenic.simulators.carla.model"):
                assert True
            case _:
                assert False


class TestMutate:
    def test_basic(self):
        mod = parse_string_helper("mutate x")
        stmt = mod.body[0]
        match stmt:
            case Mutate([Name("x", Load())]):
                assert True
            case _:
                assert False

    def test_multiple(self):
        mod = parse_string_helper("mutate x, y, z")
        stmt = mod.body[0]
        match stmt:
            case Mutate([Name("x", Load()), Name("y", Load()), Name("z", Load())]):
                assert True
            case _:
                assert False

    def test_ego(self):
        mod = parse_string_helper("mutate ego")
        stmt = mod.body[0]
        match stmt:
            case Mutate([Name("ego", Load())]):
                assert True
            case _:
                assert False

    def test_empty(self):
        mod = parse_string_helper("mutate")
        stmt = mod.body[0]
        match stmt:
            case Mutate([]):
                assert True
            case _:
                assert False

    def test_by(self):
        mod = parse_string_helper("mutate x by y")
        stmt = mod.body[0]
        match stmt:
            case Mutate([Name("x")], Name("y")):
                assert True
            case _:
                assert False

    def mutate_multiple_object_by(self):
        mod = parse_string_helper("mutate x, y, z by s")
        stmt = mod.body[0]
        match stmt:
            case Mutate([Name("x"), Name("y"), Name("z")], Name("s")):
                assert True
            case _:
                assert False

    def test_every_object_by(self):
        mod = parse_string_helper("mutate by y")
        stmt = mod.body[0]
        match stmt:
            case Mutate([], Name("y")):
                assert True
            case _:
                assert False


class TestOverride:
    def test_basic(self):
        mod = parse_string_helper("override obj with foo 1")
        stmt = mod.body[0]
        match stmt:
            case Override(Name("obj"), [WithSpecifier("foo", Constant(1))]):
                assert True
            case _:
                assert False

    def test_multiline(self):
        mod = parse_string_helper(
            """
            override obj with foo 1,
                with bar 2, with baz 3
            """
        )
        stmt = mod.body[0]
        match stmt:
            case Override(
                Name("obj"),
                [
                    WithSpecifier("foo", Constant(1)),
                    WithSpecifier("bar", Constant(2)),
                    WithSpecifier("baz", Constant(3)),
                ],
            ):
                assert True
            case _:
                assert False

    def test_multiline_trailing_comma(self):
        mod = parse_string_helper(
            """
            override obj with foo 1,
                with bar 2,
                with baz 3,
            """
        )
        stmt = mod.body[0]
        match stmt:
            case Override(
                Name("obj"),
                [
                    WithSpecifier("foo", Constant(1)),
                    WithSpecifier("bar", Constant(2)),
                    WithSpecifier("baz", Constant(3)),
                ],
            ):
                assert True
            case _:
                assert False

    def test_no_specifiers(self):
        with pytest.raises(ScenicSyntaxError):
            parse_string_helper("override obj")

    def test_expression_target(self):
        # certain simple expressions (attributes, subscript, etc.) are supported for override targets
        mod = parse_string_helper("override foo.bar with behavior baz")
        stmt = mod.body[0]
        match stmt:
            case Override(
                Attribute(Name("foo"), "bar"), [WithSpecifier("behavior", Name("baz"))]
            ):
                assert True
            case _:
                assert False


class TestAbort:
    def test_basic(self):
        mod = parse_string_helper("abort")
        stmt = mod.body[0]
        match stmt:
            case Abort():
                assert True
            case _:
                assert False


class TestTake:
    def test_single(self):
        mod = parse_string_helper("take 1")
        stmt = mod.body[0]
        match stmt:
            case Take([Constant(1)]):
                assert True
            case _:
                assert False

    def test_multiple(self):
        mod = parse_string_helper(
            "take SetThrottleAction(throttle), SetSteerAction(steering)"
        )
        stmt = mod.body[0]
        match stmt:
            case Take(
                [
                    Call(Name("SetThrottleAction"), [Name("throttle")]),
                    Call(Name("SetSteerAction"), [Name("steering")]),
                ]
            ):
                assert True
            case _:
                assert False


class TestWait:
    def test_wait(self):
        mod = parse_string_helper("wait")
        stmt = mod.body[0]
        match stmt:
            case Wait():
                assert True
            case _:
                assert False

    def test_wait_for_seconds(self):
        mod = parse_string_helper("wait for 3 seconds")
        stmt = mod.body[0]
        match stmt:
            case WaitFor(Seconds(Constant(3))):
                assert True
            case _:
                assert False

    def test_wait_for_steps(self):
        mod = parse_string_helper("wait for 3 steps")
        stmt = mod.body[0]
        match stmt:
            case WaitFor(Steps(Constant(3))):
                assert True
            case _:
                assert False

    def test_wait_for_unitless(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("wait for 3")
        assert "duration must specify a unit" in e.value.msg

    def test_wait_for_expression(self):
        mod = parse_string_helper("wait for 3 + 3 steps")
        stmt = mod.body[0]
        match stmt:
            case WaitFor(Steps(BinOp(Constant(3), Add(), Constant(3)))):
                assert True
            case _:
                assert False

    def test_wait_until(self):
        mod = parse_string_helper("wait until condition")
        stmt = mod.body[0]
        match stmt:
            case WaitUntil(Name("condition")):
                assert True
            case _:
                assert False


class TestTerminate:
    def test_basic(self):
        mod = parse_string_helper("terminate")
        stmt = mod.body[0]
        match stmt:
            case Terminate():
                assert True
            case _:
                assert False


class TestDo:
    def test_do(self):
        mod = parse_string_helper("do foo")
        stmt = mod.body[0]
        match stmt:
            case Do([Name("foo")]):
                assert True
            case _:
                assert False

    def test_do_multiple(self):
        mod = parse_string_helper("do foo, bar")
        stmt = mod.body[0]
        match stmt:
            case Do([Name("foo"), Name("bar")]):
                assert True
            case _:
                assert False

    def test_do_for_seconds(self):
        mod = parse_string_helper("do foo for 3 seconds")
        stmt = mod.body[0]
        match stmt:
            case DoFor([Name("foo")], Seconds(Constant(3))):
                assert True
            case _:
                assert False

    def test_do_for_steps(self):
        mod = parse_string_helper("do foo for 3 steps")
        stmt = mod.body[0]
        match stmt:
            case DoFor([Name("foo")], Steps(Constant(3))):
                assert True
            case _:
                assert False

    def test_do_for_unitless(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("do foo for 3")
        assert "duration must specify a unit" in e.value.msg

    def test_do_for_expression(self):
        mod = parse_string_helper("do foo for 3 + 3 steps")
        stmt = mod.body[0]
        match stmt:
            case DoFor([Name("foo")], Steps(BinOp(Constant(3), Add(), Constant(3)))):
                assert True
            case _:
                assert False

    def test_do_for_multiple(self):
        mod = parse_string_helper("do foo, bar for 5 steps")
        stmt = mod.body[0]
        match stmt:
            case DoFor([Name("foo"), Name("bar")], Steps(Constant(5))):
                assert True
            case _:
                assert False

    def test_do_until(self):
        mod = parse_string_helper("do foo until condition")
        stmt = mod.body[0]
        match stmt:
            case DoUntil([Name("foo")], Name("condition")):
                assert True
            case _:
                assert False

    def test_do_until_multiple(self):
        mod = parse_string_helper("do foo, bar until condition")
        stmt = mod.body[0]
        match stmt:
            case DoUntil([Name("foo"), Name("bar")], Name("condition")):
                assert True
            case _:
                assert False

    def test_do_choose(self):
        mod = parse_string_helper("do choose foo, bar")
        stmt = mod.body[0]
        match stmt:
            case DoChoose([Name("foo"), Name("bar")]):
                assert True
            case _:
                assert False

    def test_do_shuffle(self):
        mod = parse_string_helper("do shuffle foo, bar")
        stmt = mod.body[0]
        match stmt:
            case DoShuffle([Name("foo"), Name("bar")]):
                assert True
            case _:
                assert False


class TestParam:
    def test_basic(self):
        mod = parse_string_helper("param i = v")
        stmt = mod.body[0]
        match stmt:
            case Param([parameter("i", Name("v"))]):
                assert True
            case _:
                assert False

    def test_quoted(self):
        mod = parse_string_helper("param 'i' = v")
        stmt = mod.body[0]
        match stmt:
            case Param([parameter("i", Name("v"))]):
                assert True
            case _:
                assert False

    def test_multiple(self):
        mod = parse_string_helper('param p1=v1, "p2"=v2, "p1"=v3')
        stmt = mod.body[0]
        match stmt:
            case Param(
                [
                    parameter("p1", Name("v1")),
                    parameter("p2", Name("v2")),
                    parameter("p1", Name("v3")),
                ]
            ):
                assert True
            case _:
                assert False


class TestRequire:
    def test_basic(self):
        mod = parse_string_helper("require X")
        stmt = mod.body[0]
        match stmt:
            case Require(Name("X"), None, None):
                assert True
            case _:
                assert False

    def test_chained_comparison(self):
        mod = parse_string_helper("require a < b < c")
        stmt = mod.body[0]
        match stmt:
            case Require(Compare(Name("a"), [Lt(), Lt()], [Name("b"), Name("c")])):
                assert True
            case _:
                assert False

    def test_comparison(self):
        mod = parse_string_helper("require X > Y")
        stmt = mod.body[0]
        match stmt:
            case Require(Compare(Name("X"), [Gt()], [Name("Y")])):
                assert True
            case _:
                assert False

    def test_comparison_atom(self):
        mod = parse_string_helper("require (X) > Y")
        stmt = mod.body[0]
        match stmt:
            case Require(Compare(Name("X"), [Gt()], [Name("Y")])):
                assert True
            case _:
                assert False

    def test_prob(self):
        mod = parse_string_helper("require[0.2] X")
        stmt = mod.body[0]
        match stmt:
            case Require(Name("X"), 0.2, None):
                assert True
            case _:
                assert False

    def test_name(self):
        mod = parse_string_helper("require X as name")
        stmt = mod.body[0]
        match stmt:
            case Require(Name("X"), None, "name"):
                assert True
            case _:
                assert False

    def test_prob_name(self):
        mod = parse_string_helper("require[0.3] X as name")
        stmt = mod.body[0]
        match stmt:
            case Require(Name("X"), 0.3, "name"):
                assert True
            case _:
                assert False

    def test_name_quoted(self):
        mod = parse_string_helper("require X as 'requirement name'")
        stmt = mod.body[0]
        match stmt:
            case Require(Name("X"), None, "requirement name"):
                assert True
            case _:
                assert False

    def test_name_number(self):
        mod = parse_string_helper("require X as 123")
        stmt = mod.body[0]
        match stmt:
            case Require(Name("X"), None, "123"):
                assert True
            case _:
                assert False

    def test_require_always(self):
        mod = parse_string_helper("require always X")
        stmt = mod.body[0]
        match stmt:
            case Require(Always(Name("X")), None, None):
                assert True
            case _:
                assert False

    def test_require_always_with_name(self):
        mod = parse_string_helper("require always X as safety")
        stmt = mod.body[0]
        match stmt:
            case Require(Always(Name("X")), None, "safety"):
                assert True
            case _:
                assert False

    def test_require_eventually(self):
        mod = parse_string_helper("require eventually X")
        stmt = mod.body[0]
        match stmt:
            case Require(Eventually(Name("X")), None, None):
                assert True
            case _:
                assert False

    def test_require_eventually_with_name(self):
        mod = parse_string_helper("require eventually X as liveness")
        stmt = mod.body[0]
        match stmt:
            case Require(Eventually(Name("X")), None, "liveness"):
                assert True
            case _:
                assert False


class TestRecord:
    def test_record(self):
        mod = parse_string_helper("record x")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), None):
                assert True
            case _:
                assert False

    def test_record_named(self):
        mod = parse_string_helper("record x as name")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), "name"):
                assert True
            case _:
                assert False

    def test_record_recorder(self):
        mod = parse_string_helper("record x to file")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), recorder=Name("file")):
                assert True
            case _:
                assert False

    def test_record_delay(self):
        mod = parse_string_helper("record x after 5 seconds")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), delay=Seconds(Constant(5))):
                assert True
            case _:
                assert False

        mod = parse_string_helper("record x after 5 steps")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), delay=Steps(Constant(5))):
                assert True
            case _:
                assert False

    def test_record_period(self):
        mod = parse_string_helper("record x every 0.2 seconds")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), period=Seconds(Constant(0.2))):
                assert True
            case _:
                assert False

        mod = parse_string_helper("record x every 3 steps")
        stmt = mod.body[0]
        match stmt:
            case Record(Name("x"), period=Steps(Constant(3))):
                assert True
            case _:
                assert False

    def test_record_combined(self):
        mod = parse_string_helper("record x every 0.2 seconds after 5 seconds to file")
        stmt = mod.body[0]
        match stmt:
            case Record(
                Name("x"),
                period=Seconds(Constant(0.2)),
                delay=Seconds(Constant(5)),
                recorder=Name("file"),
            ):
                assert True
            case _:
                assert False

    def test_record_initial(self):
        mod = parse_string_helper("record initial x")
        stmt = mod.body[0]
        match stmt:
            case RecordInitial(Name("x"), None):
                assert True
            case _:
                assert False

    def test_record_initial_named(self):
        mod = parse_string_helper("record initial x as name")
        stmt = mod.body[0]
        match stmt:
            case RecordInitial(Name("x"), "name"):
                assert True
            case _:
                assert False

    def test_record_final(self):
        mod = parse_string_helper("record final x")
        stmt = mod.body[0]
        match stmt:
            case RecordFinal(Name("x"), None):
                assert True
            case _:
                assert False

    def test_record_final_named(self):
        mod = parse_string_helper("record final x as name")
        stmt = mod.body[0]
        match stmt:
            case RecordFinal(Name("x"), "name"):
                assert True
            case _:
                assert False


class TestTerminateWhen:
    def test_terminate_when(self):
        mod = parse_string_helper("terminate when x")
        stmt = mod.body[0]
        match stmt:
            case TerminateWhen(Name("x")):
                assert True
            case _:
                assert False

    def test_terminate_simulation_when(self):
        mod = parse_string_helper("terminate simulation when x")
        stmt = mod.body[0]
        match stmt:
            case TerminateSimulationWhen(Name("x")):
                assert True
            case _:
                assert False


class TestTerminateAfter:
    def test_steps(self):
        mod = parse_string_helper("terminate after 3 steps")
        stmt = mod.body[0]
        match stmt:
            case TerminateAfter(Steps(Constant(3))):
                assert True
            case _:
                assert False

    def test_seconds(self):
        mod = parse_string_helper("terminate after 5 seconds")
        stmt = mod.body[0]
        match stmt:
            case TerminateAfter(Seconds(Constant(5))):
                assert True
            case _:
                assert False

    def test_omit_unit(self):
        # `seconds` or `steps` is required
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("terminate after 20")
        assert "duration must specify a unit" in e.value.msg


class TestSimulator:
    def test_simulator(self):
        mod = parse_string_helper("simulator foo")
        stmt = mod.body[0]
        match stmt:
            case Simulator(Name("foo")):
                assert True
            case _:
                assert False


class TestNew:
    def test_basic(self):
        mod = parse_string_helper("new Object")
        stmt = mod.body[0]
        match stmt:
            case Expr(New("Object")):
                assert True
            case _:
                assert False

    def test_specifier_single(self):
        mod = parse_string_helper("new Object with foo 1")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [WithSpecifier("foo", Constant(1))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_multiple(self):
        mod = parse_string_helper("new Object with foo 1, with bar 2, with baz 3")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [
                        WithSpecifier("foo", Constant(1)),
                        WithSpecifier("bar", Constant(2)),
                        WithSpecifier("baz", Constant(3)),
                    ],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_multiline_expr(self):
        mod = parse_string_helper(
            """
            new Object with foo 1,
                with bar 2, with baz 3,
                with qux 4, with quux 5
            """
        )
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [
                        WithSpecifier("foo", Constant(1)),
                        WithSpecifier("bar", Constant(2)),
                        WithSpecifier("baz", Constant(3)),
                        WithSpecifier("qux", Constant(4)),
                        WithSpecifier("quux", Constant(5)),
                    ],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_multiline_assign(self):
        mod = parse_string_helper(
            """
            obj = new Object with foo 1,
                with bar 2, with baz 3,
                with qux 4, with quux 5
            """
        )
        stmt = mod.body[0]
        match stmt:
            case Assign(
                targets=[Name("obj")],
                value=New(
                    "Object",
                    [
                        WithSpecifier("foo", Constant(1)),
                        WithSpecifier("bar", Constant(2)),
                        WithSpecifier("baz", Constant(3)),
                        WithSpecifier("qux", Constant(4)),
                        WithSpecifier("quux", Constant(5)),
                    ],
                ),
            ):
                assert True
            case _:
                assert False

    def test_specifier_multiline_tracked(self):
        mod = parse_string_helper(
            """
            ego = new Object with foo 1,
                with bar 2, with baz 3,
                with qux 4, with quux 5
            """
        )
        stmt = mod.body[0]
        match stmt:
            case TrackedAssign(
                Ego(),
                New(
                    "Object",
                    [
                        WithSpecifier("foo", Constant(1)),
                        WithSpecifier("bar", Constant(2)),
                        WithSpecifier("baz", Constant(3)),
                        WithSpecifier("qux", Constant(4)),
                        WithSpecifier("quux", Constant(5)),
                    ],
                ),
            ):
                assert True
            case _:
                assert False

    def test_specifier_multiline_trailing_comma(self):
        mod = parse_string_helper(
            """
            new Object with foo 1,
                with bar 2, with baz 3,
            """
        )
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [
                        WithSpecifier("foo", Constant(1)),
                        WithSpecifier("bar", Constant(2)),
                        WithSpecifier("baz", Constant(3)),
                    ],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_multiline_two_lines(self):
        mod = parse_string_helper(
            """
            new Object with foo 1,
                with bar 2, with baz 3
            """
        )
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [
                        WithSpecifier("foo", Constant(1)),
                        WithSpecifier("bar", Constant(2)),
                        WithSpecifier("baz", Constant(3)),
                    ],
                )
            ):
                assert True
            case _:
                assert False

    def test_missing_new(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("Object facing x")
        assert "forgot 'new'" in e.value.msg

    def test_in_operator_not_missing_new(self):
        # Regression test for issue #356: "in" is also a specifier keyword, but
        # `x in [0]` must not trigger the "forgot 'new'" error message.
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper(
                """
                x = 0
                x in [0]
                =
                """
            )
        err = e.value
        assert "forgot 'new'" not in err.msg
        assert "invalid syntax" in err.msg
        assert err.lineno == 3

    def test_invalid_specifier_line_number(self):
        # Regression test for issue #345: a malformed position specifier like
        # `offset left` should not trigger the "forgot 'new'" error or be attributed
        # to an earlier valid `... until self in ...` expression.
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper(
                """
                behavior AdvBehavior():
                    do CrossingBehavior(ego) until self in ego.lane
                    while True:
                        take SetWalkingSpeedAction(0)

                SHIFT = Vector(1, 2)
                AdvAgent = new Pedestrian at Truck offset left Truck.heading by SHIFT,
                    with heading Truck.heading
                """
            )
        err = e.value
        assert "forgot 'new'" not in err.msg
        assert "invalid syntax" in err.msg
        assert err.lineno == 7

    def test_invalid_specifier(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("new Object blobbing")
        assert "invalid specifier" in e.value.msg

    def test_specifier_at(self):
        mod = parse_string_helper("new Object at x")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [AtSpecifier(Name("x"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_offset_by(self):
        mod = parse_string_helper("new Object offset by x")
        stmt = mod.body[0]
        match stmt:
            case Expr(New("Object", [OffsetBySpecifier(Name("x"))])):
                assert True
            case _:
                assert False

    def test_specifier_offset_along(self):
        mod = parse_string_helper("new Object offset along x by y")
        stmt = mod.body[0]
        match stmt:
            case Expr(New("Object", [OffsetAlongSpecifier(Name("x"), Name("y"))])):
                assert True
            case _:
                assert False

    def test_specifier_position_left(self):
        mod = parse_string_helper("new Object left of left")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New("Object", [DirectionOfSpecifier(LeftOf(), Name("left"), None)])
            ):
                assert True
            case _:
                assert False

    def test_specifier_position_right(self):
        mod = parse_string_helper("new Object right of right")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New("Object", [DirectionOfSpecifier(RightOf(), Name("right"), None)])
            ):
                assert True
            case _:
                assert False

    def test_specifier_position_ahead(self):
        mod = parse_string_helper("new Object ahead of ahead")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New("Object", [DirectionOfSpecifier(AheadOf(), Name("ahead"), None)])
            ):
                assert True
            case _:
                assert False

    def test_specifier_position_behind(self):
        mod = parse_string_helper("new Object behind behind")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New("Object", [DirectionOfSpecifier(Behind(), Name("behind"), None)])
            ):
                assert True
            case _:
                assert False

    def test_specifier_position_above(self):
        mod = parse_string_helper("new Object above above")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New("Object", [DirectionOfSpecifier(Above(), Name("above"), None)])
            ):
                assert True
            case _:
                assert False

    def test_specifier_position_below(self):
        mod = parse_string_helper("new Object below below")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New("Object", [DirectionOfSpecifier(Below(), Name("below"), None)])
            ):
                assert True
            case _:
                assert False

    def test_specifier_position_by(self):
        mod = parse_string_helper("new Object left of left by distance")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [DirectionOfSpecifier(LeftOf(), Name("left"), Name("distance"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_beyond(self):
        mod = parse_string_helper("new Object beyond position by distance")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [BeyondSpecifier(Name("position"), Name("distance"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_beyond_from(self):
        mod = parse_string_helper("new Object beyond position by d from base")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [BeyondSpecifier(Name("position"), Name("d"), Name("base"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_visible(self):
        mod = parse_string_helper("new Object visible")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [VisibleSpecifier(None)],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_visible_from(self):
        mod = parse_string_helper("new Object visible from base")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [VisibleSpecifier(Name("base"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_not_visible(self):
        mod = parse_string_helper("new Object not visible")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [NotVisibleSpecifier(None)],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_not_visible_from(self):
        mod = parse_string_helper("new Object not visible from base")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [NotVisibleSpecifier(Name("base"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_in(self):
        mod = parse_string_helper("new Object in region")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [InSpecifier(Name("region"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_on(self):
        mod = parse_string_helper("new Object on region")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [OnSpecifier(Name("region"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_contained_in(self):
        mod = parse_string_helper("new Object contained in region")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [ContainedInSpecifier(Name("region"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_following(self):
        mod = parse_string_helper("new Object following field for distance")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FollowingSpecifier(Name("field"), Name("distance"), None)],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_following_from(self):
        mod = parse_string_helper("new Object following field from base for distance")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FollowingSpecifier(Name("field"), Name("distance"), Name("base"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_facing(self):
        mod = parse_string_helper("new Object facing heading")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FacingSpecifier(Name("heading"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_facing_toward(self):
        mod = parse_string_helper("new Object facing toward position")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FacingTowardSpecifier(Name("position"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_facing_away_from(self):
        mod = parse_string_helper("new Object facing away from position")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FacingAwayFromSpecifier(Name("position"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_facing_directly_toward(self):
        mod = parse_string_helper("new Object facing directly toward position")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FacingDirectlyTowardSpecifier(Name("position"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_facing_directly_away_from(self):
        mod = parse_string_helper("new Object facing directly away from position")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [FacingDirectlyAwayFromSpecifier(Name("position"))],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_apparently_facing(self):
        mod = parse_string_helper("new Object apparently facing heading")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [ApparentlyFacingSpecifier(Name("heading"), None)],
                )
            ):
                assert True
            case _:
                assert False

    def test_specifier_apparently_facing_from(self):
        mod = parse_string_helper("new Object apparently facing heading from base")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                New(
                    "Object",
                    [ApparentlyFacingSpecifier(Name("heading"), Name("base"))],
                )
            ):
                assert True
            case _:
                assert False


class TestOperator:
    def test_implies_basic(self):
        mod = parse_string_helper("require x implies y")
        stmt = mod.body[0]
        match stmt:
            case Require(ImpliesOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_implies_precedence(self):
        mod = parse_string_helper("require x implies y or z")
        stmt = mod.body[0]
        match stmt:
            case Require(ImpliesOp(Name("x"), BoolOp(Or(), [Name("y"), Name("z")]))):
                assert True
            case _:
                assert False

    def test_implies_three_operands(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("require x implies y implies z")
        assert "must take exactly two operands" in e.value.msg

    def test_next_implies(self):
        mod = parse_string_helper("require next x implies y")
        stmt = mod.body[0]
        match stmt:
            case Require(Next(ImpliesOp(Name("x"), Name("y")))):
                assert True
            case _:
                assert False

    def test_implies_next(self):
        mod = parse_string_helper("require x implies next y")
        stmt = mod.body[0]
        match stmt:
            case Require(ImpliesOp(Name("x"), Next(Name("y")))):
                assert True
            case _:
                assert False

    def test_until_basic(self):
        mod = parse_string_helper("require x until y")
        stmt = mod.body[0]
        match stmt:
            case Require(UntilOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_until_precedence_1(self):
        mod = parse_string_helper("require x until y or z")
        stmt = mod.body[0]
        match stmt:
            case Require(UntilOp(Name("x"), BoolOp(Or(), [Name("y"), Name("z")]))):
                assert True
            case _:
                assert False

    def test_until_precedence_2(self):
        mod = parse_string_helper("require x implies y until z")
        stmt = mod.body[0]
        match stmt:
            case Require(UntilOp(ImpliesOp(Name("x"), Name("y")), Name("z"))):
                assert True
            case _:
                assert False

    def test_next_until(self):
        mod = parse_string_helper("require next x until y")
        stmt = mod.body[0]
        match stmt:
            case Require(UntilOp(Next(Name("x")), Name("y"))):
                assert True
            case _:
                assert False

    def test_until_next(self):
        mod = parse_string_helper("require x until next y")
        stmt = mod.body[0]
        match stmt:
            case Require(UntilOp(Name("x"), Next(Name("y")))):
                assert True
            case _:
                assert False

    def test_until_three_operands(self):
        with pytest.raises(ScenicSyntaxError) as e:
            parse_string_helper("require x until y until z")
        assert "must take exactly two operands" in e.value.msg

    def test_temporal_boolean_ops(self):
        mod = parse_string_helper("require x and y and not always z")
        stmt = mod.body[0]
        match stmt:
            case Require(
                BoolOp(And(), [Name("x"), Name("y"), UnaryOp(Not(), Always(Name("z")))])
            ):
                assert True
            case _:
                assert False

    def test_temporal_boolean_atom(self):
        mod = parse_string_helper("require ((eventually x) or (always y))")
        stmt = mod.body[0]
        match stmt:
            case Require(BoolOp(Or(), [Eventually(Name("x")), Always(Name("y"))])):
                assert True
            case _:
                assert False

    def test_relative_position(self):
        mod = parse_string_helper("relative position of x")
        stmt = mod.body[0]
        match stmt:
            case Expr(RelativePositionOp(Name("x"))):
                assert True
            case _:
                assert False

    def test_relative_position_base(self):
        mod = parse_string_helper("relative position of x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(RelativePositionOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "relative position of relative position of A from B",
                RelativePositionOp(
                    RelativePositionOp(Name("A", Load()), Name("B", Load()))
                ),
            ),
            (
                "relative position of relative position of A from B from C",
                RelativePositionOp(
                    RelativePositionOp(Name("A", Load()), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "relative position of A from relative position of B from C",
                RelativePositionOp(
                    Name("A", Load()),
                    RelativePositionOp(Name("B", Load()), Name("C", Load())),
                ),
            ),
            (
                "relative position of A << B from C",
                RelativePositionOp(
                    BinOp(Name("A", Load()), LShift(), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "relative position of A from B << C",
                BinOp(
                    RelativePositionOp(Name("A", Load()), Name("B", Load())),
                    LShift(),
                    Name("C", Load()),
                ),
            ),
            (
                "relative position of A + B from C",
                RelativePositionOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "relative position of A from B + C",
                RelativePositionOp(
                    Name("A", Load()),
                    BinOp(Name("B", Load()), Add(), Name("C", Load())),
                ),
            ),
            (
                "relative position of A << B",
                BinOp(RelativePositionOp(Name("A", Load())), LShift(), Name("B", Load())),
            ),
            (
                "relative position of A + B",
                RelativePositionOp(BinOp(Name("A", Load()), Add(), Name("B", Load()))),
            ),
        ],
    )
    def test_relative_position_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_relative_heading(self):
        mod = parse_string_helper("relative heading of x")
        stmt = mod.body[0]
        match stmt:
            case Expr(RelativeHeadingOp(Name("x"))):
                assert True
            case _:
                assert False

    def test_relative_heading_from(self):
        mod = parse_string_helper("relative heading of x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(RelativeHeadingOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "relative heading of relative heading of A from B",
                RelativeHeadingOp(
                    RelativeHeadingOp(Name("A", Load()), Name("B", Load()))
                ),
            ),
            (
                "relative heading of relative heading of A from B from C",
                RelativeHeadingOp(
                    RelativeHeadingOp(Name("A", Load()), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "relative heading of A from relative heading of B from C",
                RelativeHeadingOp(
                    Name("A", Load()),
                    RelativeHeadingOp(Name("B", Load()), Name("C", Load())),
                ),
            ),
            (
                "relative heading of A << B from C",
                RelativeHeadingOp(
                    BinOp(Name("A", Load()), LShift(), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "relative heading of A from B << C",
                BinOp(
                    RelativeHeadingOp(Name("A", Load()), Name("B", Load())),
                    LShift(),
                    Name("C", Load()),
                ),
            ),
            (
                "relative heading of A + B from C",
                RelativeHeadingOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "relative heading of A from B + C",
                RelativeHeadingOp(
                    Name("A", Load()),
                    BinOp(Name("B", Load()), Add(), Name("C", Load())),
                ),
            ),
            (
                "relative heading of A << B",
                BinOp(RelativeHeadingOp(Name("A", Load())), LShift(), Name("B", Load())),
            ),
            (
                "relative heading of A + B",
                RelativeHeadingOp(BinOp(Name("A", Load()), Add(), Name("B", Load()))),
            ),
        ],
    )
    def test_relative_heading_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_apparent_heading(self):
        mod = parse_string_helper("apparent heading of x")
        stmt = mod.body[0]
        match stmt:
            case Expr(ApparentHeadingOp(Name("x"))):
                assert True
            case _:
                assert False

    def test_apparent_heading_from(self):
        mod = parse_string_helper("apparent heading of x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(ApparentHeadingOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "apparent heading of apparent heading of A from B",
                ApparentHeadingOp(
                    ApparentHeadingOp(Name("A", Load()), Name("B", Load()))
                ),
            ),
            (
                "apparent heading of apparent heading of A from B from C",
                ApparentHeadingOp(
                    ApparentHeadingOp(Name("A", Load()), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "apparent heading of A from apparent heading of B from C",
                ApparentHeadingOp(
                    Name("A", Load()),
                    ApparentHeadingOp(Name("B", Load()), Name("C", Load())),
                ),
            ),
            (
                "apparent heading of A << B from C",
                ApparentHeadingOp(
                    BinOp(Name("A", Load()), LShift(), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "apparent heading of A from B << C",
                BinOp(
                    ApparentHeadingOp(Name("A", Load()), Name("B", Load())),
                    LShift(),
                    Name("C", Load()),
                ),
            ),
            (
                "apparent heading of A + B from C",
                ApparentHeadingOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "apparent heading of A from B + C",
                ApparentHeadingOp(
                    Name("A", Load()),
                    BinOp(Name("B", Load()), Add(), Name("C", Load())),
                ),
            ),
            (
                "apparent heading of A << B",
                BinOp(ApparentHeadingOp(Name("A", Load())), LShift(), Name("B", Load())),
            ),
            (
                "apparent heading of A + B",
                ApparentHeadingOp(BinOp(Name("A", Load()), Add(), Name("B", Load()))),
            ),
        ],
    )
    def test_apparent_heading_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_distance_from(self):
        mod = parse_string_helper("distance from x")
        stmt = mod.body[0]
        match stmt:
            case Expr(DistanceFromOp(Name("x"), None)):
                assert True
            case _:
                assert False

    def test_distance_to(self):
        mod = parse_string_helper("distance to x")
        stmt = mod.body[0]
        match stmt:
            case Expr(DistanceFromOp(Name("x"), None)):
                assert True
            case _:
                assert False

    def test_distance_from_to(self):
        mod = parse_string_helper("distance from x to y")
        stmt = mod.body[0]
        match stmt:
            case Expr(DistanceFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_distance_to_from(self):
        mod = parse_string_helper("distance to x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(DistanceFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_min_distance_to(self):
        mod = parse_string_helper("minimum distance to x")
        stmt = mod.body[0]
        match stmt:
            case Expr(MinDistanceFromOp(Name("x"), None)):
                assert True
            case _:
                assert False

    def test_min_distance_from_to(self):
        mod = parse_string_helper("minimum distance from x to y")
        stmt = mod.body[0]
        match stmt:
            case Expr(MinDistanceFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_min_distance_to_from(self):
        mod = parse_string_helper("minimum distance to x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(MinDistanceFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "distance to distance from A to B",
                DistanceFromOp(DistanceFromOp(Name("A", Load()), Name("B", Load()))),
            ),
            (
                "distance to distance from A from B",
                DistanceFromOp(
                    DistanceFromOp(Name("A", Load()), None), Name("B", Load())
                ),
            ),
            (
                "distance to A << B from C << D",
                BinOp(
                    DistanceFromOp(
                        BinOp(Name("A", Load()), LShift(), Name("B", Load())),
                        Name("C", Load()),
                    ),
                    LShift(),
                    Name("D", Load()),
                ),
            ),
            (
                "distance to A + B from C + D",
                DistanceFromOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    BinOp(Name("C", Load()), Add(), Name("D", Load())),
                ),
            ),
            (
                "distance to A + B",
                DistanceFromOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    None,
                ),
            ),
            (
                "distance from A + B",
                DistanceFromOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    None,
                ),
            ),
            (
                "distance to A << B",
                BinOp(
                    DistanceFromOp(Name("A", Load()), None),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
            (
                "distance from A << B",
                BinOp(
                    DistanceFromOp(Name("A", Load()), None),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
        ],
    )
    def test_distance_from_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_distance_past(self):
        mod = parse_string_helper("distance past x")
        stmt = mod.body[0]
        match stmt:
            case Expr(DistancePastOp(Name("x"))):
                assert True
            case _:
                assert False

    def test_distance_past_of(self):
        mod = parse_string_helper("distance past x of y")
        stmt = mod.body[0]
        match stmt:
            case Expr(DistancePastOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "distance past distance past A of B",
                DistancePastOp(DistancePastOp(Name("A", Load()), Name("B", Load()))),
            ),
            (
                "distance past distance past A of B of C",
                DistancePastOp(
                    DistancePastOp(Name("A", Load()), Name("B", Load())),
                    Name("C", Load()),
                ),
            ),
            (
                "distance past A of distance past B of C",
                DistancePastOp(
                    Name("A", Load()),
                    DistancePastOp(Name("B", Load()), Name("C", Load())),
                ),
            ),
            (
                "distance past A << B of C << D",
                BinOp(
                    DistancePastOp(
                        BinOp(
                            Name("A", Load()),
                            LShift(),
                            Name("B", Load()),
                        ),
                        Name("C", Load()),
                    ),
                    LShift(),
                    Name("D", Load()),
                ),
            ),
            (
                "distance past A + B of C + D",
                DistancePastOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    BinOp(Name("C", Load()), Add(), Name("D", Load())),
                ),
            ),
            (
                "distance past A << B",
                BinOp(
                    DistancePastOp(
                        Name("A", Load()),
                    ),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
            (
                "distance past A + B",
                DistancePastOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                ),
            ),
        ],
    )
    def test_distance_past_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_angle_from(self):
        mod = parse_string_helper("angle from x")
        stmt = mod.body[0]
        match stmt:
            case Expr(AngleFromOp(None, Name("x"))):
                assert True
            case _:
                assert False

    def test_angle_to(self):
        mod = parse_string_helper("angle to x")
        stmt = mod.body[0]
        match stmt:
            case Expr(AngleFromOp(Name("x"), None)):
                assert True
            case _:
                assert False

    def test_angle_from_to(self):
        mod = parse_string_helper("angle from x to y")
        stmt = mod.body[0]
        match stmt:
            case Expr(AngleFromOp(Name("y"), Name("x"))):
                assert True
            case _:
                assert False

    def test_angle_to_from(self):
        mod = parse_string_helper("angle to x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(AngleFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "angle to angle from A to B",
                AngleFromOp(AngleFromOp(Name("B", Load()), Name("A", Load()))),
            ),
            (
                "angle to angle from A from B",
                AngleFromOp(AngleFromOp(None, Name("A", Load())), Name("B", Load())),
            ),
            (
                "angle to A << B from C << D",
                BinOp(
                    AngleFromOp(
                        BinOp(Name("A", Load()), LShift(), Name("B", Load())),
                        Name("C", Load()),
                    ),
                    LShift(),
                    Name("D", Load()),
                ),
            ),
            (
                "angle from A + B to C + D",
                AngleFromOp(
                    BinOp(Name("C", Load()), Add(), Name("D", Load())),
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                ),
            ),
            (
                "angle to A + B",
                AngleFromOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    None,
                ),
            ),
            (
                "angle from A + B",
                AngleFromOp(
                    None,
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                ),
            ),
            (
                "angle to A << B",
                BinOp(
                    AngleFromOp(Name("A", Load()), None),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
            (
                "angle from A << B",
                BinOp(
                    AngleFromOp(None, Name("A", Load())),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
        ],
    )
    def test_angle_from_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_altitude_from(self):
        mod = parse_string_helper("altitude from x")
        stmt = mod.body[0]
        match stmt:
            case Expr(AltitudeFromOp(None, Name("x"))):
                assert True
            case _:
                assert False

    def test_altitude_to(self):
        mod = parse_string_helper("altitude to x")
        stmt = mod.body[0]
        match stmt:
            case Expr(AltitudeFromOp(Name("x"), None)):
                assert True
            case _:
                assert False

    def test_altitude_from_to(self):
        mod = parse_string_helper("altitude from x to y")
        stmt = mod.body[0]
        match stmt:
            case Expr(AltitudeFromOp(Name("y"), Name("x"))):
                assert True
            case _:
                assert False

    def test_altitude_to_from(self):
        mod = parse_string_helper("altitude to x from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(AltitudeFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_follow(self):
        mod = parse_string_helper("follow x from y for z")
        stmt = mod.body[0]
        match stmt:
            case Expr(FollowOp(Name("x"), Name("y"), Name("z"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "follow A + B from C + D for E + F",
                FollowOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                    BinOp(Name("C", Load()), Add(), Name("D", Load())),
                    BinOp(Name("E", Load()), Add(), Name("F", Load())),
                ),
            ),
            (
                "follow A << B from C << D for E << F",
                BinOp(
                    FollowOp(
                        BinOp(Name("A", Load()), LShift(), Name("B", Load())),
                        BinOp(Name("C", Load()), LShift(), Name("D", Load())),
                        Name("E", Load()),
                    ),
                    LShift(),
                    Name("F", Load()),
                ),
            ),
        ],
    )
    def test_follow_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_visible(self):
        mod = parse_string_helper("visible x")
        stmt = mod.body[0]
        match stmt:
            case Expr(VisibleOp(Name("x"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "visible A + B",
                VisibleOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                ),
            ),
            (
                "visible A << B",
                BinOp(
                    VisibleOp(Name("A", Load())),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
        ],
    )
    def test_visible_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_not_visible(self):
        mod = parse_string_helper("not visible x")
        stmt = mod.body[0]
        match stmt:
            case Expr(NotVisibleOp(Name("x"))):
                assert True
            case _:
                assert False

    def test_not_visible_inversion(self):
        mod = parse_string_helper("not visible")
        stmt = mod.body[0]
        match stmt:
            case Expr(UnaryOp(Not(), Name("visible"))):
                assert True
            case _:
                assert False

    def test_not_visible_with_not(self):
        mod = parse_string_helper("not not visible x")
        stmt = mod.body[0]
        match stmt:
            case Expr(UnaryOp(Not(), NotVisibleOp(Name("x")))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "not visible A + B",
                NotVisibleOp(
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                ),
            ),
            (
                "not visible A << B",
                BinOp(
                    NotVisibleOp(Name("A", Load())),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
        ],
    )
    def test_visible_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_visible_from(self):
        mod = parse_string_helper("x visible from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(VisibleFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_not_visible_from(self):
        mod = parse_string_helper("x not visible from y")
        stmt = mod.body[0]
        match stmt:
            case Expr(NotVisibleFromOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "position,node",
        [
            ("front", Front),
            ("back", Back),
            ("left", Left),
            ("right", Right),
            ("front left", FrontLeft),
            ("front right", FrontRight),
            ("back left", BackLeft),
            ("back right", BackRight),
        ],
    )
    def test_position_of(self, position, node):
        mod = parse_string_helper(f"{position} of x")
        stmt = mod.body[0]
        match stmt:
            case Expr(PositionOfOp(positionNode, Name("x"))):
                assert isinstance(positionNode, node)
            case _:
                assert False

    @pytest.mark.parametrize(
        "code,expected",
        [
            (
                "front of A + B",
                PositionOfOp(
                    Front(),
                    BinOp(Name("A", Load()), Add(), Name("B", Load())),
                ),
            ),
            (
                "left of A << B",
                BinOp(
                    PositionOfOp(Left(), Name("A", Load())),
                    LShift(),
                    Name("B", Load()),
                ),
            ),
        ],
    )
    def test_visible_precedence(self, code, expected):
        assert_equal_source_ast(code, expected)

    def test_always(self):
        mod = parse_string_helper("require always x")
        stmt = mod.body[0]
        match stmt:
            case Require(Always(Name("x"))):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "boolop,boolopclass,tempop,tempopclass",
        [
            bop + top
            for bop in [("or", Or), ("and", And)]
            for top in [("always", Always), ("eventually", Eventually), ("next", Next)]
        ],
    )
    def test_bool_temporal_prefix(self, boolop, boolopclass, tempop, tempopclass):
        """Parse require statements of the form `require x {boolop} {tempop} y`.

        It should be parsed as `require x {boolop} ({tempop} y)`"""
        mod = parse_string_helper(f"require x {boolop} {tempop} y")
        stmt = mod.body[0]
        match stmt:
            case Require(BoolOp(boolopclass(), [Name("x"), tempopclass(Name("y"))])):
                assert True
            case _:
                assert False

    @pytest.mark.parametrize(
        "boolop,boolopclass,tempop,tempopclass",
        [
            bop + top
            for bop in [("or", Or), ("and", And)]
            for top in [("always", Always), ("eventually", Eventually), ("next", Next)]
        ],
    )
    def test_bool_temporal_prefix_bool(self, boolop, boolopclass, tempop, tempopclass):
        """Parse require statements of the form `require x {boolop} {tempop} y {boolop} z`.

        It should be parsed as `require x {boolop} ({tempop} (y {boolop} z))`"""
        mod = parse_string_helper(f"require x {boolop} {tempop} y {boolop} z")
        stmt = mod.body[0]
        match stmt:
            case Require(
                BoolOp(
                    boolopclass(),
                    [
                        Name("x"),
                        tempopclass(BoolOp(boolopclass(), [Name("y"), Name("z")])),
                    ],
                )
            ):
                assert True
            case _:
                assert False

    def test_eventually(self):
        mod = parse_string_helper("require eventually x")
        stmt = mod.body[0]
        match stmt:
            case Require(Eventually(Name("x"))):
                assert True
            case _:
                assert False

    def test_next(self):
        mod = parse_string_helper("require next x")
        stmt = mod.body[0]
        match stmt:
            case Require(Next(Name("x"))):
                assert True
            case _:
                assert False

    def test_next_atom(self):
        mod = parse_string_helper("require (next (x))")
        stmt = mod.body[0]
        match stmt:
            case Require(Next(Name("x"))):
                assert True
            case _:
                assert False

    def test_next_atom_2(self):
        mod = parse_string_helper("require (y and next (x))")
        stmt = mod.body[0]
        match stmt:
            case Require(BoolOp(And(), [Name("y"), Next(Name("x"))])):
                assert True
            case _:
                assert False

    def test_next_function(self):
        mod = parse_string_helper("next(it)")
        stmt = mod.body[0]
        match stmt:
            case Expr(Call(Name("next"), [Name("it")])):
                assert True
            case _:
                assert False

    def test_deg_1(self):
        mod = parse_string_helper("1 + 2 deg")
        stmt = mod.body[0]
        match stmt:
            case Expr(BinOp(Constant(1), Add(), DegOp(Constant(2)))):
                assert True
            case _:
                assert False

    def test_deg_2(self):
        mod = parse_string_helper("6 * 2 deg")
        stmt = mod.body[0]
        match stmt:
            case Expr(DegOp(BinOp(Constant(6), Mult(), Constant(2)))):
                assert True
            case _:
                assert False

    def test_vector_1(self):
        mod = parse_string_helper("1 + 2 @ 3 * 4")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                BinOp(
                    Constant(1),
                    Add(),
                    BinOp(VectorOp(Constant(2), Constant(3)), Mult(), Constant(4)),
                )
            ):
                assert True
            case _:
                assert False

    def test_vector_2(self):
        mod = parse_string_helper("1 * 2 @ 3 + 4")
        stmt = mod.body[0]
        match stmt:
            case Expr(
                BinOp(
                    VectorOp(BinOp(Constant(1), Mult(), Constant(2)), Constant(3)),
                    Add(),
                    Constant(4),
                )
            ):
                assert True
            case _:
                assert False

    def test_vector_3(self):
        mod = parse_string_helper("1 @ 2 @ 3")
        stmt = mod.body[0]
        match stmt:
            case Expr(VectorOp(VectorOp(Constant(1), Constant(2)), Constant(3))):
                assert True
            case _:
                assert False

    def test_field_at(self):
        mod = parse_string_helper("x at y")
        stmt = mod.body[0]
        match stmt:
            case Expr(FieldAtOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_relative_to(self):
        mod = parse_string_helper("x relative to y")
        stmt = mod.body[0]
        match stmt:
            case Expr(RelativeToOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_offset_by(self):
        mod = parse_string_helper("x offset by y")
        stmt = mod.body[0]
        match stmt:
            case Expr(RelativeToOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_offset_along(self):
        mod = parse_string_helper("x offset along y by z")
        stmt = mod.body[0]
        match stmt:
            case Expr(OffsetAlongOp(Name("x"), Name("y"), Name("z"))):
                assert True
            case _:
                assert False

    def test_can_see(self):
        mod = parse_string_helper("x can see y ")
        stmt = mod.body[0]
        match stmt:
            case Expr(CanSeeOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False

    def test_intersects(self):
        mod = parse_string_helper("x intersects y ")
        stmt = mod.body[0]
        match stmt:
            case Expr(IntersectsOp(Name("x"), Name("y"))):
                assert True
            case _:
                assert False


def test_fstring_conversion_specifiers():
    for conv_char, expected in [("r", ord("r")), ("s", ord("s")), ("a", ord("a"))]:
        mod = parse_string_helper(
            f"""
            x = 3
            param y = f"{{x!{conv_char}}}"
            """
        )
        joined = mod.body[1].elts[0].value
        assert joined.values[0].conversion == expected


def test_fstring_invalid_conversion_specifier():
    with pytest.raises(ScenicParseError, match="invalid conversion character"):
        parse_string_helper('y = f"{x!z}"')
