import ast
import functools
import inspect
import operator
import sys
import typing
from typing import Any, ForwardRef, Optional, Union


class AST(ast.AST):
    """Scenic AST base class.

    N.B. The attributes ``_fields`` and ``_field_types`` expected in subclasses
    of `ast.AST` are synthesized automatically from a dataclass-like syntax:
    see below for many examples.
    """

    _attributes = ("lineno", "col_offset", "end_lineno", "end_col_offset")

    def __init_subclass__(cls):
        super().__init_subclass__()
        fts = _getFields(cls)
        if sys.version_info[:2] == (3, 13):
            # The Python 3.13 ast.AST initializer expects types like X | None, but we
            # use Optional[X] for compatibility; convert the latter into the former.
            # (In 3.14+, Optional[X] and X | None are identical at runtime.)
            optionalTy = type(Optional[str])
            for field, ty in fts.items():
                if isinstance(ty, optionalTy):
                    args = typing.get_args(ty)
                    if any(isinstance(arg, ForwardRef) for arg in args):
                        # ForwardRef doesn't support | in 3.13, so simplify to Any
                        newTy = Any | None
                    else:
                        newTy = functools.reduce(operator.or_, args)
                    fts[field] = newTy
        cls._field_types = fts
        cls._fields = tuple(cls._field_types)
        cls.__match_args__ = tuple(cls._fields)


if sys.version_info >= (3, 10):
    _getFields = inspect.get_annotations
else:
    # We won't bother with un-stringizing annotations: they won't be used anyway
    _getFields = lambda cls: cls.__dict__.get("__annotations__", {})


# special statements


class TryInterrupt(AST):
    """Scenic AST node that represents try-interrupt statements"""

    body: typing.List[ast.stmt]
    interrupt_when_handlers: typing.List["InterruptWhenHandler"]
    except_handlers: typing.List[ast.ExceptHandler]
    orelse: typing.List[ast.stmt]
    finalbody: typing.List[ast.AST]


class InterruptWhenHandler(AST):
    cond: ast.AST
    body: typing.List[ast.AST]


class TrackedAssign(AST):
    target: Union["Ego", "Workspace"]
    value: ast.AST


class Ego(AST):
    """`ego` tracked assign target"""

    functionName = "ego"


class Workspace(AST):
    """:term:`workspace` tracked assign target"""

    functionName = "workspace"


class InitialScenario(AST):
    pass


class PropertyDef(AST):
    property: str
    attributes: typing.List[Union["Additive", "Dynamic", "Final"]]
    value: ast.AST


class Additive(AST):
    keyword = "additive"


class Dynamic(AST):
    keyword = "dynamic"


class Final(AST):
    keyword = "final"


# behavior / monitor


class BehaviorDef(AST):
    name: str
    args: ast.arguments
    docstring: Optional[str]
    header: typing.List[Union["Precondition", "Invariant"]]
    body: typing.List[ast.AST]


class MonitorDef(AST):
    name: str
    args: ast.arguments
    docstring: Optional[str]
    body: typing.List[ast.AST]


class Precondition(AST):
    value: ast.AST


class Invariant(AST):
    value: ast.AST


# modular scenarios


class ScenarioDef(AST):
    name: str
    args: ast.arguments
    docstring: Optional[str]
    header: Optional[typing.List[Union[Precondition, Invariant]]]
    setup: typing.List[ast.AST]
    compose: typing.List[ast.AST]


# simple statements


class Model(AST):
    name: str


class Param(AST):
    """:keyword:`param` statements"""

    elts: typing.List["parameter"]


class parameter(AST):
    """Represents a parameter that is defined with `param` statements"""

    identifier: str
    value: ast.AST


class Require(AST):
    cond: ast.AST
    prob: Optional[float] = None
    name: Optional[str] = None


class RequireMonitor(AST):
    monitor: ast.AST
    name: Optional[str] = None


class Always(AST):
    value: ast.AST


class Eventually(AST):
    value: ast.AST


class Next(AST):
    value: ast.AST


class Record(AST):
    value: ast.AST
    name: Optional[str] = None
    recorder: Optional[Any] = None
    period: Optional[Union["Seconds", "Steps"]] = None
    delay: Optional[Union["Seconds", "Steps"]] = None


class RecordInitial(AST):
    value: ast.AST
    name: Optional[str] = None


class RecordFinal(AST):
    value: ast.AST
    name: Optional[str] = None


class Mutate(AST):
    elts: typing.List[ast.Name]
    scale: Optional[ast.AST] = None


class Override(AST):
    target: ast.AST
    specifiers: typing.List[ast.AST]


class Abort(AST):
    pass


class Take(AST):
    elts: typing.List[ast.AST]


class Wait(AST):
    pass


class WaitFor(AST):
    duration: Union["Seconds", "Steps"]


class WaitUntil(AST):
    cond: ast.AST


class Terminate(AST):
    pass


class TerminateSimulation(AST):
    pass


class TerminateSimulationWhen(AST):
    cond: ast.AST
    name: Optional[str] = None


class TerminateWhen(AST):
    cond: ast.AST
    name: Optional[str] = None


class TerminateAfter(AST):
    duration: Union["Seconds", "Steps"]


class DoFor(AST):
    elts: typing.List[ast.AST]
    duration: Union["Seconds", "Steps"]


class Seconds(AST):
    unitStr = "seconds"

    value: ast.AST


class Steps(AST):
    unitStr = "steps"

    value: ast.AST


class DoUntil(AST):
    elts: typing.List[ast.AST]
    cond: ast.AST


class DoChoose(AST):
    elts: typing.List[ast.AST]


class DoShuffle(AST):
    elts: typing.List[ast.AST]


class Do(AST):
    elts: typing.List[ast.AST]


class Simulator(AST):
    value: ast.AST


# Instance Creation


class New(AST):
    className: str
    specifiers: Optional[typing.List[ast.AST]]

    def __init__(self, className, specifiers, **kwargs):
        specs = specifiers if specifiers is not None else []
        super().__init__(className, specs, **kwargs)


# Specifiers


class WithSpecifier(AST):
    prop: str
    value: ast.AST


class AtSpecifier(AST):
    position: ast.AST


class OffsetBySpecifier(AST):
    offset: ast.AST


class OffsetAlongSpecifier(AST):
    direction: ast.AST
    offset: ast.AST


class DirectionOfSpecifier(AST):
    direction: Union["LeftOf", "RightOf", "AheadOf", "Behind"]
    position: ast.AST
    distance: Optional[ast.AST] = None


class LeftOf(AST):
    pass


class RightOf(AST):
    pass


class AheadOf(AST):
    pass


class Behind(AST):
    pass


class Above(AST):
    pass


class Below(AST):
    pass


class BeyondSpecifier(AST):
    position: ast.AST
    offset: ast.AST
    base: Optional[ast.AST] = None


class VisibleSpecifier(AST):
    base: Optional[ast.AST] = None


class NotVisibleSpecifier(AST):
    base: Optional[ast.AST] = None


class InSpecifier(AST):
    region: ast.AST


class OnSpecifier(AST):
    region: ast.AST


class ContainedInSpecifier(AST):
    region: ast.AST


class FollowingSpecifier(AST):
    field: ast.AST
    distance: ast.AST
    base: Optional[ast.AST] = None


class FacingSpecifier(AST):
    heading: ast.AST


class FacingTowardSpecifier(AST):
    position: ast.AST


class FacingAwayFromSpecifier(AST):
    position: ast.AST


class FacingDirectlyTowardSpecifier(AST):
    position: ast.AST


class FacingDirectlyAwayFromSpecifier(AST):
    position: ast.AST


class ApparentlyFacingSpecifier(AST):
    heading: ast.AST
    base: Optional[ast.AST] = None


# Operators


class ImpliesOp(AST):
    hypothesis: ast.AST
    conclusion: ast.AST


class UntilOp(AST):
    left: ast.AST
    right: ast.AST


class RelativePositionOp(AST):
    target: ast.AST
    base: Optional[ast.AST] = None


class RelativeHeadingOp(AST):
    target: ast.AST
    base: Optional[ast.AST] = None


class ApparentHeadingOp(AST):
    target: ast.AST
    base: Optional[ast.AST] = None


class DistanceFromOp(AST):
    # because `to` and `from` are symmetric, the first operand will be `target` and the second will be `base`
    target: ast.AST
    base: Optional[ast.AST] = None


class MinDistanceFromOp(AST):
    # because `to` and `from` are symmetric, the first operand will be `target` and the second will be `base`
    target: ast.AST
    base: Optional[ast.AST] = None


class DistancePastOp(AST):
    target: ast.AST
    base: Optional[ast.AST] = None


class AngleFromOp(AST):
    target: Optional[ast.AST] = None
    base: Optional[ast.AST] = None


class AltitudeFromOp(AST):
    target: Optional[ast.AST] = None
    base: Optional[ast.AST] = None


class FollowOp(AST):
    target: ast.AST
    base: ast.AST
    distance: ast.AST


class VisibleOp(AST):
    region: ast.AST


class NotVisibleOp(AST):
    region: ast.AST


class VisibleFromOp(AST):
    region: ast.AST
    base: ast.AST


class NotVisibleFromOp(AST):
    region: ast.AST
    base: ast.AST


class PositionOfOp(AST):
    position: Union[
        "Front",
        "Back",
        "Left",
        "Right",
        "Top",
        "Bottom",
        "FrontLeft",
        "FrontRight",
        "BackLeft",
        "BackRight",
        "TopFrontLeft",
        "TopFrontRight",
        "TopBackLeft",
        "TopBackRight",
        "BottomFrontLeft",
        "BottomFrontRight",
        "BottomBackLeft",
        "BottomBackRight",
    ]
    target: ast.AST


class Front(AST):
    """Represents position of :scenic:`front of` operator"""

    functionName = "Front"


class Back(AST):
    """Represents position of :scenic:`back of` operator"""

    functionName = "Back"


class Left(AST):
    """Represents position of :scenic:`left of` operator"""

    functionName = "Left"


class Right(AST):
    """Represents position of :scenic:`right of` operator"""

    functionName = "Right"


class Top(AST):
    """Represents position of :scenic:`top of` operator"""

    functionName = "Top"


class Bottom(AST):
    """Represents position of :scenic:`bottom of` operator"""

    functionName = "Bottom"


class FrontLeft(AST):
    """Represents position of :scenic:`front left of` operator"""

    functionName = "FrontLeft"


class FrontRight(AST):
    """Represents position of :scenic:`front right of` operator"""

    functionName = "FrontRight"


class BackLeft(AST):
    """Represents position of :scenic:`back left of` operator"""

    functionName = "BackLeft"


class BackRight(AST):
    """Represents position of :scenic:`back right of` operator"""

    functionName = "BackRight"


class TopFrontLeft(AST):
    """Represents position of :scenic:`top front left of` operator"""

    functionName = "TopFrontLeft"


class TopFrontRight(AST):
    """Represents position of :scenic:`top front right of` operator"""

    functionName = "TopFrontRight"


class TopBackLeft(AST):
    """Represents position of :scenic:`top back left of` operator"""

    functionName = "TopBackLeft"


class TopBackRight(AST):
    """Represents position of :scenic:`top back right of` operator"""

    functionName = "TopBackRight"


class BottomFrontLeft(AST):
    """Represents position of :scenic:`bottom front left of` operator"""

    functionName = "BottomFrontLeft"


class BottomFrontRight(AST):
    """Represents position of :scenic:`bottom front right of` operator"""

    functionName = "BottomFrontRight"


class BottomBackLeft(AST):
    """Represents position of :scenic:`bottom back left of` operator"""

    functionName = "BottomBackLeft"


class BottomBackRight(AST):
    """Represents position of :scenic:`bottom back right of` operator"""

    functionName = "BottomBackRight"


class DegOp(AST):
    operand: ast.AST


class VectorOp(AST):
    left: ast.AST
    right: ast.AST


class FieldAtOp(AST):
    left: ast.AST
    right: ast.AST


class RelativeToOp(AST):
    left: ast.AST
    right: ast.AST


class OffsetAlongOp(AST):
    base: ast.AST
    direction: ast.AST
    offset: ast.AST


class CanSeeOp(AST):
    left: ast.AST
    right: ast.AST


class IntersectsOp(AST):
    left: ast.AST
    right: ast.AST
