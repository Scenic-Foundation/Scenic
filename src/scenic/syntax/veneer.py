"""Python implementations of Scenic language constructs.

This module is automatically imported by all Scenic programs. In addition to
defining the built-in functions, operators, specifiers, etc., it also stores
global state such as the list of all created Scenic objects.

.. highlight:: scenic-grammar
"""

__all__ = (
    # Primitive statements and functions
    "ego",
    "workspace",
    "new",
    "require",
    "resample",
    "param",
    "globalParameters",
    "mutate",
    "verbosePrint",
    "localPath",
    "model",
    "simulator",
    "simulation",
    "require_monitor",
    "terminate_when",
    "terminate_simulation_when",
    "terminate_after",
    "check_time",
    "in_initial_scenario",
    "override",
    "record",
    "record_initial",
    "record_final",
    "sin",
    "cos",
    "tan",
    "hypot",
    "max",
    "min",
    "_toStrScenic",
    "_toFloatScenic",
    "_toIntScenic",
    "filter",
    "round",
    "len",
    "range",
    "orientedRegion",
    "unorientedRegion",
    # Prefix operators
    "Visible",
    "NotVisible",
    "Front",
    "Back",
    "Left",
    "Right",
    "FrontLeft",
    "FrontRight",
    "BackLeft",
    "BackRight",
    "Top",
    "Bottom",
    "TopFrontLeft",
    "TopFrontRight",
    "TopBackLeft",
    "TopBackRight",
    "BottomFrontLeft",
    "BottomFrontRight",
    "BottomBackLeft",
    "BottomBackRight",
    "RelativeHeading",
    "ApparentHeadingOf",
    "ApparentHeadingTo",
    "RelativePosition",
    "DistanceFrom",
    "MinDistanceFrom",
    "DistancePast",
    "Follow",
    "AngleTo",
    "AngleFrom",
    "AltitudeTo",
    "AltitudeFrom",
    # Infix operators
    "FieldAt",
    "RelativeTo",
    "OffsetAlong",
    "CanSee",
    "Intersects",
    "Until",
    "Implies",
    "VisibleFromOp",
    "NotVisibleFromOp",
    "AheadOfOp",
    "BehindOp",
    "LeftOfOp",
    "RightOfOp",
    # Primitive types
    "Vector",
    "Orientation",
    "VectorField",
    "PolygonalVectorField",
    "Shape",
    "MeshShape",
    "BoxShape",
    "CylinderShape",
    "ConeShape",
    "SpheroidShape",
    "MeshVolumeRegion",
    "MeshSurfaceRegion",
    "BoxRegion",
    "SpheroidRegion",
    "PathRegion",
    "Region",
    "PointSetRegion",
    "RectangularRegion",
    "CircularRegion",
    "SectorRegion",
    "PolygonalRegion",
    "PolylineRegion",
    "Workspace",
    "Mutator",
    "Range",
    "DiscreteRange",
    "Options",
    "Uniform",
    "Discrete",
    "Normal",
    "TruncatedNormal",
    "SeededGenerator",
    "VerifaiParameter",
    "VerifaiRange",
    "VerifaiDiscreteRange",
    "VerifaiOptions",
    "VerifaiSampler",
    "OptunaRange",
    "OptunaDiscreteRange",
    "OptunaParameter",
    "OptunaOptions",
    "OptunaSampler",
    "TimeSeries",
    "File",
    "Files",
    # Constructible types
    "Point",
    "OrientedPoint",
    "Object",
    # Specifiers
    "With",
    "At",
    "In",
    "ContainedIn",
    "On",
    "Beyond",
    "VisibleFrom",
    "NotVisibleFrom",
    "VisibleSpec",
    "NotVisibleSpec",
    "OffsetBy",
    "OffsetAlongSpec",
    "Facing",
    "ApparentlyFacing",
    "FacingToward",
    "FacingDirectlyToward",
    "FacingAwayFrom",
    "FacingDirectlyAwayFrom",
    "LeftSpec",
    "RightSpec",
    "Ahead",
    "Behind",
    "Above",
    "Below",
    "Following",
    # Constants
    "everywhere",
    "nowhere",
    # Exceptions
    "GuardViolation",
    "PreconditionViolation",
    "InvariantViolation",
    "RejectionException",
    # Internal APIs     # TODO remove?
    "_scenic_default",
    "Behavior",
    "Monitor",
    "_makeTerminationAction",
    "_makeSimulationTerminationAction",
    "BlockConclusion",
    "runTryInterrupt",
    "wrapStarredValue",
    "callWithStarArgs",
    "Modifier",
    "DynamicScenario",
    # Proposition Factories
    "AtomicProposition",
    "PropositionAnd",
    "PropositionOr",
    "PropositionNot",
    "Always",
    "Eventually",
    "Next",
)

# various Python types and functions used in the language but defined elsewhere
from scenic.core.distributions import (
    DiscreteRange,
    Normal,
    Options,
    RandomControlFlowError,
    Range,
    SeededGenerator,
    TruncatedNormal,
    Uniform,
)
from scenic.core.dynamics.behaviors import Behavior, Monitor
from scenic.core.dynamics.guards import (
    GuardViolation,
    InvariantViolation,
    PreconditionViolation,
)
from scenic.core.dynamics.invocables import BlockConclusion, runTryInterrupt
from scenic.core.dynamics.scenarios import DynamicScenario
from scenic.core.external_params import TimeSeries
from scenic.core.external_params.optuna import (
    OptunaDiscreteRange,
    OptunaOptions,
    OptunaParameter,
    OptunaRange,
    OptunaSampler,
)
from scenic.core.external_params.verifai import (
    VerifaiDiscreteRange,
    VerifaiOptions,
    VerifaiParameter,
    VerifaiRange,
    VerifaiSampler,
)
from scenic.core.geometry import cos, hypot, max, min, sin, tan
from scenic.core.object_types import Mutator, Object, OrientedPoint, Point
from scenic.core.regions import (
    BoxRegion,
    CircularRegion,
    MeshSurfaceRegion,
    MeshVolumeRegion,
    PathRegion,
    PointSetRegion,
    PolygonalRegion,
    PolylineRegion,
    RectangularRegion,
    Region,
    SectorRegion,
    SpheroidRegion,
    everywhere,
    nowhere,
)
from scenic.core.sensors import File, Files
from scenic.core.shapes import (
    BoxShape,
    ConeShape,
    CylinderShape,
    MeshShape,
    Shape,
    SpheroidShape,
)
from scenic.core.specifiers import PropertyDefault as _scenic_default
from scenic.core.vectors import PolygonalVectorField, Vector, VectorField
from scenic.core.workspaces import Workspace

Discrete = Options

# isort: split

# everything that should not be directly accessible from the language is imported here:
import builtins
import collections.abc
from contextlib import contextmanager
import functools
import importlib
import math
import numbers
from pathlib import Path
import sys
import traceback
import typing
import warnings

from scenic.core.distributions import (
    Distribution,
    FunctionDistribution,
    MultiplexerDistribution,
    RejectionException,
    StarredDistribution,
    TupleDistribution,
    canUnpackDistributions,
    distributionFunction,
    needsSampling,
    toDistribution,
)
from scenic.core.dynamics.actions import _EndScenarioAction, _EndSimulationAction
import scenic.core.errors as errors
from scenic.core.errors import InvalidScenarioError, ScenicSyntaxError
from scenic.core.external_params import ExternalParameter
from scenic.core.geometry import apparentHeadingAtPoint, normalizeAngle
from scenic.core.lazy_eval import (
    DelayedArgument,
    isLazy,
    needsLazyEvaluation,
    requiredProperties,
    valueInContext,
)
import scenic.core.object_types
from scenic.core.object_types import Constructible, Object2D, OrientedPoint2D, Point2D
import scenic.core.propositions as propositions
from scenic.core.regions import convertToFootprint
import scenic.core.requirements as requirements
from scenic.core.sensors import Recorder, RecordingConfiguration
from scenic.core.simulators import RejectSimulationException
from scenic.core.specifiers import ModifyingSpecifier, Specifier
from scenic.core.type_support import (
    Heading,
    TypecheckedDistribution,
    canCoerce,
    coerce,
    evaluateRequiringEqualTypes,
    isA,
    toHeading,
    toOrientation,
    toScalar,
    toType,
    toTypes,
    toVector,
    underlyingType,
)
from scenic.core.vectors import Orientation, alwaysGlobalOrientation

### Internals

activity = 0
currentScenario = None
scenarioStack = []
scenarios = []
evaluatingRequirement = False
_globalParameters = {}
lockedParameters = set()
lockedModel = None
loadingModel = False
currentSimulation = None
inInitialScenario = True
runningScenarios = []  # in order, oldest first
currentBehavior = None
simulatorFactory = None
evaluatingGuard = False
mode2D = False
_originalConstructibles = (Point, OrientedPoint, Object)
BUFFERING_PITCH = 0.1

## APIs used internally by the rest of Scenic

# Scenic compilation


def isActive():
    """Are we in the middle of compiling a Scenic module?

    The 'activity' global can be >1 when Scenic modules in turn import other
    Scenic modules.
    """
    return activity > 0


def activate(options, namespace=None):
    """Activate the veneer when beginning to compile a Scenic module."""
    global activity, _globalParameters, lockedParameters, lockedModel, currentScenario
    if options.paramOverrides or options.modelOverride:
        assert activity == 0
        _globalParameters.update(options.paramOverrides)
        lockedParameters = set(options.paramOverrides)
        lockedModel = options.modelOverride

    # If we are in 2D mode, set the global flag and replace all classes
    # with their 2D compatibility counterparts.
    if options.mode2D:
        global mode2D, Point, OrientedPoint, Object
        assert mode2D or activity == 0
        mode2D = True
        Point = Point2D
        OrientedPoint = OrientedPoint2D
        Object = Object2D
        scenic.core.object_types.Point = Point
        scenic.core.object_types.OrientedPoint = OrientedPoint
        scenic.core.object_types.Object = Object

    activity += 1
    assert not evaluatingRequirement
    assert not evaluatingGuard
    assert currentSimulation is None
    # placeholder scenario for top-level code
    newScenario = DynamicScenario._dummy(namespace)
    scenarioStack.append(newScenario)
    currentScenario = newScenario


def deactivate():
    """Deactivate the veneer after compiling a Scenic module."""
    global activity, _globalParameters, lockedParameters, lockedModel, mode2D
    global currentScenario, scenarios, scenarioStack, simulatorFactory
    activity -= 1
    assert activity >= 0
    assert not evaluatingRequirement
    assert not evaluatingGuard
    assert currentSimulation is None
    scenarioStack.pop()
    assert len(scenarioStack) == activity
    scenarios = []

    if activity == 0:
        lockedParameters = set()
        lockedModel = None
        currentScenario = None
        simulatorFactory = None
        _globalParameters = {}

        if mode2D:
            global Point, OrientedPoint, Object
            mode2D = False
            Point, OrientedPoint, Object = _originalConstructibles
            scenic.core.object_types.Point = Point
            scenic.core.object_types.OrientedPoint = OrientedPoint
            scenic.core.object_types.Object = Object
    else:
        currentScenario = scenarioStack[-1]


# Instance/Object creation


def registerInstance(inst):
    """Add a Scenic instance to the global list of created objects.

    This is called by the Point/OrientedPoint constructor.
    """
    if currentScenario:
        assert isinstance(inst, Constructible)
        currentScenario._registerInstance(inst)


def registerObject(obj):
    """Add a Scenic object to the global list of created objects.

    This is called by the Object constructor.
    """
    if evaluatingRequirement:
        raise InvalidScenarioError("tried to create an object inside a requirement")
    elif currentBehavior is not None:
        raise InvalidScenarioError("tried to create an object inside a behavior")
    elif activity > 0 or currentScenario:
        assert not evaluatingRequirement
        assert isinstance(obj, Object)
        if currentScenario and currentScenario._isRunning:
            raise InvalidScenarioError("tried to create an object inside a compose block")
        currentScenario._registerObject(obj)
        if currentSimulation:
            currentSimulation._createObject(obj)


# External parameter creation


def registerExternalParameter(value):
    """Register a parameter whose value is given by an external sampler."""
    if activity > 0:
        assert isinstance(value, ExternalParameter)
        currentScenario._externalParameters.append(value)


# Function call support


def wrapStarredValue(value, lineno):
    if isinstance(value, TupleDistribution) or not needsSampling(value):
        return value
    elif isinstance(value, Distribution):
        return [StarredDistribution(value, lineno)]
    else:
        raise TypeError(f"iterable unpacking cannot be applied to {value}")


def callWithStarArgs(_func_to_call, *args, **kwargs):
    if not canUnpackDistributions(_func_to_call):
        # wrap function to delay evaluation until starred distributions are sampled
        _func_to_call = distributionFunction(_func_to_call)
    return _func_to_call(*args, **kwargs)


# Simulations


def instantiateSimulator(factory, params):
    global _globalParameters
    assert not _globalParameters  # TODO improve hack?
    _globalParameters = dict(params)
    try:
        return factory()
    finally:
        _globalParameters = {}


def beginSimulation(sim):
    global currentSimulation, currentScenario, inInitialScenario, runningScenarios
    global _globalParameters
    if isActive():
        raise RuntimeError("tried to start simulation during Scenic compilation!")
    assert currentSimulation is None
    assert currentScenario is None
    assert not scenarioStack
    currentSimulation = sim
    currentScenario = sim.scene.dynamicScenario
    runningScenarios = []  # will be updated by DynamicScenario._start
    inInitialScenario = currentScenario._setup is None
    currentScenario._bindTo(sim.scene)
    _globalParameters = dict(sim.scene.params)

    # If we are in 2D mode, set the global flag and replace all classes
    # with their 2D compatibility counterparts.
    if currentSimulation.scene.compileOptions.mode2D:
        global mode2D, Point, OrientedPoint, Object
        mode2D = True
        Point = Point2D
        OrientedPoint = OrientedPoint2D
        Object = Object2D
        scenic.core.object_types.Point = Point
        scenic.core.object_types.OrientedPoint = OrientedPoint
        scenic.core.object_types.Object = Object

    # rebind globals that could be referenced by behaviors to their sampled values
    for modName, (
        namespace,
        sampledNS,
        originalNS,
    ) in sim.scene.behaviorNamespaces.items():
        namespace.clear()
        namespace.update(sampledNS)


def endSimulation(sim):
    global currentSimulation, currentScenario, currentBehavior, runningScenarios
    global _globalParameters, mode2D
    currentSimulation = None
    currentScenario = None
    runningScenarios = []
    currentBehavior = None
    _globalParameters = {}

    if mode2D:
        global Point, OrientedPoint, Object
        mode2D = False
        Point, OrientedPoint, Object = _originalConstructibles
        scenic.core.object_types.Point = Point
        scenic.core.object_types.OrientedPoint = OrientedPoint
        scenic.core.object_types.Object = Object

    for modName, (
        namespace,
        sampledNS,
        originalNS,
    ) in sim.scene.behaviorNamespaces.items():
        namespace.clear()
        namespace.update(originalNS)


def simulationInProgress():
    return currentSimulation is not None


# Requirements


@contextmanager
def executeInRequirement(scenario, boundEgo, values):
    global evaluatingRequirement, currentScenario
    assert activity == 0
    assert not evaluatingRequirement
    evaluatingRequirement = True

    with executeInScenario(scenario):
        oldEgo = scenario._ego
        oldObjects = scenario._objects

        scenario._objects = tuple(values[obj] for obj in scenario.objects)

        if boundEgo:
            scenario._ego = boundEgo
        try:
            yield
        except RandomControlFlowError as e:
            # Such errors should not be possible inside a requirement, since all values
            # should have already been sampled: something's gone wrong with our rebinding.
            raise AssertionError(
                "internal error: requirement dependency not sampled"
            ) from e
        finally:
            evaluatingRequirement = False
            scenario._ego = oldEgo
            scenario._objects = oldObjects


# Dynamic scenarios


def registerDynamicScenarioClass(cls):
    scenarios.append(cls)


@contextmanager
def executeInScenario(scenario, inheritEgo=False):
    global currentScenario, _globalParameters
    oldScenario = currentScenario
    if inheritEgo and oldScenario is not None:
        scenario._ego = oldScenario._ego  # inherit ego from parent
        scenario._workspace = oldScenario._workspace
    currentScenario = scenario
    oldParams = _globalParameters
    _globalParameters = scenario._globalParameters
    try:
        yield
    except AttributeError as e:
        # Convert confusing AttributeErrors from trying to access nonexistent scenario
        # variables into NameErrors, which is what the user would expect. The information
        # needed to do this was made available in Python 3.10, but unfortunately could be
        # wrong until 3.10.3: see bpo-46940.
        if sys.version_info >= (3, 10, 3) and isinstance(e.obj, DynamicScenario):
            newExc = NameError(f"name '{e.name}' is not defined", name=e.name)
            raise newExc.with_traceback(e.__traceback__)
        else:
            raise
    finally:
        currentScenario = oldScenario
        _globalParameters = oldParams


def prepareScenario(scenario):
    if currentSimulation:
        verbosePrint(f"Starting scenario {scenario}", level=3)


def finishScenarioSetup(scenario):
    global inInitialScenario
    inInitialScenario = False


def startScenario(scenario):
    assert scenario not in runningScenarios
    runningScenarios.append(scenario)


def endScenario(scenario, reason, quiet=False):
    runningScenarios.remove(scenario)
    if not quiet:
        verbosePrint(f"Stopping scenario {scenario} because: {reason}", level=3)


# Dynamic behaviors


@contextmanager
def executeInBehavior(behavior):
    global currentBehavior
    oldBehavior = currentBehavior
    currentBehavior = behavior
    try:
        yield
    except AttributeError as e:
        # See comment for corresponding code in executeInScenario
        if sys.version_info >= (3, 10, 3) and isinstance(e.obj, Behavior):
            newExc = NameError(f"name '{e.name}' is not defined", name=e.name)
            raise newExc.with_traceback(e.__traceback__)
        else:
            raise
    finally:
        currentBehavior = oldBehavior


@contextmanager
def executeInGuard():
    global evaluatingGuard
    assert not evaluatingGuard
    evaluatingGuard = True
    try:
        yield
    finally:
        evaluatingGuard = False


def _makeTerminationAction(agent, line):
    assert activity == 0
    if agent:
        scenario = agent._parentScenario()
        assert scenario is not None
    else:
        scenario = None
    return _EndScenarioAction(scenario, line)


def _makeSimulationTerminationAction(line):
    assert activity == 0
    return _EndSimulationAction(line)


### Parsing support


class Modifier(typing.NamedTuple):
    name: str
    value: typing.Any
    terminator: typing.Optional[str] = None


### Primitive statements and functions


def new(cls, specifiers):
    if not (isinstance(cls, type) and issubclass(cls, Constructible)):
        raise TypeError(f'"{cls.__name__}" is not a Scenic class')
    return cls._withSpecifiers(specifiers)


def ego(obj=None):
    """Function implementing loads and stores to the 'ego' pseudo-variable.

    The translator calls this with no arguments for loads, and with the source
    value for stores.
    """
    egoObject = currentScenario._ego
    if obj is None:
        if egoObject is None:
            raise InvalidScenarioError("referred to ego object not yet assigned")
    elif not isinstance(obj, Object):
        if isinstance(obj, type) and issubclass(obj, Object):
            suffix = " (perhaps you forgot 'new'?)"
        else:
            suffix = ""
        ty = type(obj).__name__
        raise TypeError(f"tried to make non-object (of type {ty}) the ego object{suffix}")
    else:
        currentScenario._ego = obj
        for scenario in runningScenarios:
            if scenario._ego is None:
                scenario._ego = obj
    return egoObject


def workspace(workspace=None):
    """Function implementing loads and stores to the 'workspace' pseudo-variable.

    See `ego`.
    """
    if workspace is None:
        if currentScenario._workspace is None:
            raise InvalidScenarioError("referred to workspace not yet assigned")
    elif not isinstance(workspace, Workspace):
        raise TypeError(f"workspace {workspace} is not a Workspace")
    elif needsSampling(workspace):
        raise InvalidScenarioError("workspace must be a fixed region")
    elif needsLazyEvaluation(workspace):
        raise InvalidScenarioError(
            "workspace uses value undefined " "outside of object definition"
        )
    else:
        currentScenario._workspace = workspace
    return currentScenario._workspace


def require(reqID, req, line, name, prob=1):
    """Function implementing the require statement."""
    if not name:
        name = f"requirement on line {line}"
    if evaluatingRequirement:
        raise InvalidScenarioError("tried to create a requirement inside a requirement")
    if req.has_temporal_operator and prob != 1:
        raise InvalidScenarioError(
            "requirements with temporal operators must have probability of 1"
        )
    if currentSimulation is not None:  # requirement being evaluated at runtime
        if req.has_temporal_operator:
            # support monitors on dynamic requirements and create dynamic requirements
            currentScenario._addDynamicRequirement(
                requirements.RequirementType.require, req, line, name
            )
        else:
            if prob >= 1 or Range(0, 1) <= prob:  # use Range so value can be recorded
                result = req.evaluate()
                assert not needsSampling(result)
                if needsLazyEvaluation(result):
                    raise InvalidScenarioError(
                        f"requirement on line {line} uses value"
                        " undefined outside of object definition"
                    )
                if not result:
                    raise RejectSimulationException(name)
    else:  # requirement being defined at compile time
        currentScenario._addRequirement(
            requirements.RequirementType.require, reqID, req, line, name, prob
        )


def require_monitor(reqID, value, line, name):
    if not name:
        name = f"requirement on line {line}"
    if currentSimulation is not None:
        monitor = value.evaluate()
        assert not needsSampling(monitor)
        if needsLazyEvaluation(monitor):
            raise InvalidScenarioError(
                f"requirement on line {line} uses value"
                " undefined outside of object definition"
            )
        if not isinstance(monitor, Monitor):
            raise TypeError(f'"require monitor X" with X not a monitor on line {line}')
        currentScenario._addMonitor(monitor)
    else:
        currentScenario._addRequirement(
            requirements.RequirementType.monitor, reqID, value, line, name, 1
        )


def record(reqID, value, line, name, recorder=None, period=None, delay=None):
    if not name:
        name = f"record{line}"
    if recorder is not None:
        if isinstance(recorder, str):
            recorder = Recorder._forPattern(recorder)
        if not isinstance(recorder, Recorder):
            raise TypeError(
                f'"record X to Y" on line {line} with Y not a str or Recorder'
            )
    if period is not None:
        val, unit = period
        if not isinstance(val, numbers.Real):
            raise TypeError(
                f'period of "record" statement on line {line} must be a number'
            )
        if val <= 0:
            raise ValueError(
                f'period of "record" statement on line {line} must be positive'
            )
        if unit == "steps" and not isinstance(val, int):
            raise TypeError(
                f'"record every X steps" on line {line} with X not an integer'
            )
    else:
        period = (1, "steps")
    if delay is not None:
        val, unit = delay
        if not isinstance(val, numbers.Real):
            raise TypeError(
                f'delay of "record" statement on line {line} must be a number'
            )
        if val < 0:
            raise ValueError(
                f'delay of "record" statement on line {line} must be nonnegative'
            )
        if unit == "steps" and not isinstance(val, int):
            raise TypeError(
                f'"record after X steps" on line {line} with X not an integer'
            )
    else:
        delay = (0, "steps")
    config = RecordingConfiguration(
        name=name, recorder=recorder, period=period, delay=delay
    )
    makeRequirement(requirements.RequirementType.record, reqID, value, line, name, config)


def record_initial(reqID, value, line, name):
    if not name:
        name = f"record{line}"
    makeRequirement(requirements.RequirementType.recordInitial, reqID, value, line, name)


def record_final(reqID, value, line, name):
    if not name:
        name = f"record{line}"
    makeRequirement(requirements.RequirementType.recordFinal, reqID, value, line, name)


def terminate_when(reqID, req, line, name):
    """Function implementing the 'terminate when' statement."""
    if not name:
        name = f"termination condition on line {line}"
    makeRequirement(requirements.RequirementType.terminateWhen, reqID, req, line, name)


def terminate_simulation_when(reqID, req, line, name):
    """Function implementing the 'terminate simulation when' statement."""
    if not name:
        name = f"termination condition on line {line}"
    makeRequirement(
        requirements.RequirementType.terminateSimulationWhen, reqID, req, line, name
    )


def terminate_after(reqId, req, line, _):
    name = "terminate after on line {line}"
    makeRequirement(requirements.RequirementType.terminateAfter, reqId, req, line, name)


def check_time(timeLimit, terminator=None):
    """Returns True if we have exceeded the time limit."""
    if not isinstance(timeLimit, (builtins.float, builtins.int)):
        raise TypeError('"terminate after N" with N not a number')
    assert terminator in (None, "seconds", "steps")
    inSeconds = terminator != "steps"

    threshold = timeLimit / simulation().timestep if inSeconds else timeLimit
    return currentScenario._inherited._elapsedTime > threshold


def makeRequirement(ty, reqID, req, line, name, recConfig=None):
    if evaluatingRequirement:
        raise InvalidScenarioError(f'tried to use "{ty.value}" inside a requirement')
    elif currentBehavior is not None:
        raise InvalidScenarioError(f'"{ty.value}" inside a behavior on line {line}')
    else:
        currentScenario._addRequirement(ty, reqID, req, line, name, 1, recConfig)


def resample(dist):
    """The built-in resample function."""
    if not isinstance(dist, Distribution):
        return dist
    try:
        return dist.clone()
    except NotImplementedError:
        raise TypeError("cannot resample non-primitive distribution") from None


def verbosePrint(
    *objects, level=1, indent=True, sep=" ", end="\n", file=sys.stdout, flush=False
):
    """Built-in function printing a message only in verbose mode.

    Scenic's verbosity may be set using the :option:`-v` command-line option.
    The simplest way to use this function is with code like
    :scenic:`verbosePrint('hello world!')` or :scenic:`verbosePrint('details here', level=3)`;
    the other keyword arguments are probably only useful when replacing more complex uses
    of the Python `print` function.

    Args:
        objects: Object(s) to print (`str` will be called to make them strings).
        level (int): Minimum verbosity level at which to print. Default is 1.
        indent (bool): Whether to indent the message to align with messages generated by
            Scenic (default true).
        sep, end, file, flush: As in `print`.
    """
    if errors.verbosityLevel >= level:
        if indent:
            if currentSimulation:
                indent = "      " if errors.verbosityLevel >= 3 else "  "
            else:
                indent = "  " * activity if errors.verbosityLevel >= 2 else "  "
            print(indent, end="", file=file)
        print(*objects, sep=sep, end=end, file=file, flush=flush)


def localPath(relpath):
    """Convert a path relative to the calling Scenic file into an absolute path.

    For example, :scenic:`localPath('resource.dat')` evaluates to the absolute path
    of a file called ``resource.dat`` located in the same directory as the
    Scenic file where this expression appears. Note that the path is returned as a
    `pathlib.Path` object.
    """
    filename = traceback.extract_stack(limit=2)[0].filename
    base = Path(filename).parent
    return base.joinpath(relpath).resolve()


def simulation():
    """Get the currently-running `Simulation`.

    May only be called from code that runs at simulation time, e.g. inside
    :term:`dynamic behaviors` and :keyword:`compose` blocks of scenarios.
    """
    if isActive():
        raise InvalidScenarioError("used simulation() outside a behavior")
    assert currentSimulation is not None
    return currentSimulation


def simulator(sim):
    global simulatorFactory
    simulatorFactory = sim


def in_initial_scenario():
    return inInitialScenario


def override(*args):
    if len(args) < 1:
        raise TypeError('"override" missing an object')
    elif len(args) < 2:
        raise TypeError('"override" missing a list of specifiers')
    obj = args[0]
    if not isinstance(obj, Object):
        raise TypeError(f'"override" passed non-Object {obj}')
    specs = args[1:]
    for spec in specs:
        assert isinstance(spec, Specifier), spec

    currentScenario._override(obj, specs)


def model(namespace, modelName):
    global loadingModel
    if loadingModel:
        raise InvalidScenarioError('Scenic world model itself uses the "model" statement')
    if lockedModel is not None:
        modelName = lockedModel
    try:
        loadingModel = True
        module = importlib.import_module(modelName)
    except ModuleNotFoundError as e:
        if e.name == modelName:
            raise InvalidScenarioError(
                f"could not import world model {modelName}"
            ) from None
        else:
            raise
    finally:
        loadingModel = False
    names = module.__dict__.get("__all__", None)
    if names is not None:
        for name in names:
            namespace[name] = getattr(module, name)
    else:
        for name, value in module.__dict__.items():
            if not name.startswith("_"):
                namespace[name] = value


def param(params):
    """Function implementing the param statement."""
    global loadingModel
    if evaluatingRequirement:
        raise InvalidScenarioError(
            "tried to create a global parameter inside a requirement"
        )
    elif currentSimulation is not None:
        raise InvalidScenarioError(
            "tried to create a global parameter during a simulation"
        )
    for name, value in params.items():
        if name not in lockedParameters and (
            not loadingModel or name not in _globalParameters
        ):
            _globalParameters[name] = toDistribution(value)


class ParameterTableProxy(collections.abc.Mapping):
    def __init__(self, map):
        object.__setattr__(self, "_internal_map", map)

    def __getitem__(self, name):
        return self._internal_map[name]

    def __iter__(self):
        return iter(self._internal_map)

    def __len__(self):
        return len(self._internal_map)

    def __getattr__(self, name):
        return self.__getitem__(name)  # allow namedtuple-like access

    def __setattr__(self, name, value):
        raise InvalidScenarioError(
            'cannot modify globalParameters (use "param" statement)'
        )

    def _clone_table(self):
        return ParameterTableProxy(self._internal_map.copy())


def globalParameters():
    return ParameterTableProxy(_globalParameters)


def mutate(*objects, scale=1):
    """Function implementing the mutate statement."""
    if evaluatingRequirement:
        raise InvalidScenarioError("used mutate statement inside a requirement")
    if len(objects) == 0:
        objects = currentScenario._objects
    if not isinstance(scale, (builtins.int, builtins.float)):
        raise TypeError('"mutate X by Y" with Y not a number')
    for obj in objects:
        if not isinstance(obj, Object):
            raise TypeError('"mutate X" with X not an object')
        obj.mutationScale = scale
        # Object will now require sampling even if it has no explicit dependencies.
        obj._needsSampling = True
        obj._isLazy = True


### Prefix operators


def Visible(region):
    """The :grammar:`visible <region>` operator."""
    region = toType(region, Region, '"visible X" with X not a Region')
    return region.intersect(ego().visibleRegion)


def NotVisible(region):
    """The :grammar:`not visible <region>` operator."""
    region = toType(region, Region, '"not visible X" with X not a Region')
    return region.difference(ego().visibleRegion)


# front of <object>, etc.
ops = (
    "front",
    "back",
    "left",
    "right",
    "front left",
    "front right",
    "back left",
    "back right",
    "top",
    "bottom",
    "top front left",
    "top front right",
    "top back left",
    "top back right",
    "bottom front left",
    "bottom front right",
    "bottom back left",
    "bottom back right",
)
template = '''\
def {function}(X):
    """The :grammar:`{syntax} of <object>` operator."""
    if not isinstance(X, Object):
        raise TypeError('"{syntax} of X" with X not an Object')
    return X.{property}
'''
for op in ops:
    func = "".join(word.capitalize() for word in op.split(" "))
    prop = func[0].lower() + func[1:]
    definition = template.format(function=func, syntax=op, property=prop)
    exec(definition)

### Infix operators


def FieldAt(X, Y):
    """The :grammar:`<vector field> at <vector>` operator."""
    if isinstance(X, type) and issubclass(X, Constructible):
        raise TypeError('"X at Y" with X not a vector field. (Perhaps you forgot "new"?)')

    if not isA(X, VectorField):
        raise TypeError('"X at Y" with X not a vector field')
    Y = toVector(Y, '"X at Y" with Y not a vector')
    return X[Y]


def RelativeTo(X, Y) -> typing.Union[Vector, builtins.float, Orientation]:
    """The :scenic:`{X} relative to {Y}` polymorphic operator.

    Allowed forms::

        <value> relative to <value> # with at least one a field, the other a field or heading
        <vector> relative to <oriented point> # and vice versa
        <vector> relative to <vector>
        <heading> relative to <heading>
        <orientation> relative to <orientation>
    """

    # Define lazy RelativeTo helper
    @distributionFunction
    def lazyRelativeTo(X, Y) -> typing.Union[Vector, builtins.float, Orientation]:
        return RelativeTo(X, Y)

    # Define type helpers
    def knownOrientation(thing):
        return isA(thing, Orientation) or (
            (not isLazy(thing))
            and canCoerce(thing, Orientation)
            and (not canCoerce(thing, Vector))
        )

    def knownHeading(thing):
        return isA(thing, numbers.Real) or (
            (not isLazy(thing)) and canCoerce(thing, Heading)
        )

    def knownVector(thing):
        return isA(thing, Vector) or ((not isLazy(thing)) and canCoerce(thing, Vector))

    xf, yf = isA(X, VectorField), isA(Y, VectorField)
    if xf or yf:
        if xf and yf and X.valueType != Y.valueType:
            raise TypeError('"X relative to Y" with X, Y fields of different types')
        fieldType = X.valueType if xf else Y.valueType
        error = '"X relative to Y" with field and value of different types'

        def helper(context):
            pos = context.position.toVector()
            xp = X[pos] if xf else toType(X, fieldType, error)
            yp = Y[pos] if yf else toType(Y, fieldType, error)
            return yp + xp

        return DelayedArgument({"position"}, helper)

    elif isA(X, OrientedPoint) or isA(Y, OrientedPoint):
        # Ensure X and Y aren't both oriented points
        if isA(X, OrientedPoint) and isA(Y, OrientedPoint):
            raise TypeError('"X relative to Y" with X, Y both oriented points')

        # Extract the single oriented point and the other value
        if isA(X, OrientedPoint):
            op = X
            other = Y
        else:
            op = Y
            other = X

        # Check the other value's type
        if isA(other, numbers.Real):
            return op.heading + toHeading(other)
        elif isA(other, Orientation):
            return toOrientation(Y) * toOrientation(X)
        elif knownVector(other):
            other = toVector(other)
            return op.relativize(other)

        # This case doesn't match (for now at least). Fall through.
        pass

    elif knownOrientation(X) and knownOrientation(Y):
        xf = toOrientation(X)
        yf = toOrientation(Y)

        return yf * xf

    elif knownHeading(X) and knownHeading(Y):
        xf = toHeading(X, f'"X relative to Y" with Y a heading but X a {type(X)}')
        yf = toHeading(Y, f'"X relative to Y" with X a heading but Y a {type(Y)}')

        return xf + yf

    elif knownVector(X) or knownVector(Y):
        xf = toVector(X, f'"X relative to Y" with Y a vector but X a {type(X)}')
        yf = toVector(Y, f'"X relative to Y" with X a vector but Y a {type(Y)}')

        return xf + yf

    if isLazy(X) or isLazy(Y):
        # We can't determine what case to use at this point. Try again when things are sampled.
        return lazyRelativeTo(X, Y)

    raise TypeError(
        f'"X relative to Y" with X and Y incompatible types (X a {type(X)}, Y a {type(Y)})'
    )


def OffsetAlong(X, H, Y):
    """The :scenic:`{X} offset along {H} by {Y}` polymorphic operator.

    Allowed forms::

        <vector> offset along <heading> by <vector>
        <vector> offset along <field> by <vector>
    """
    X = toVector(X, '"X offset along H by Y" with X not a vector')
    Y = toVector(Y, '"X offset along H by Y" with Y not a vector')
    if isA(H, VectorField):
        H = H[X]
    H = toOrientation(
        H, '"X offset along H by Y" with H not an orientation or vector field'
    )
    return X.offsetLocally(H, Y)


def RelativePosition(X, Y=None):
    """The :grammar:`relative position of <vector> [from <vector>]` operator.

    If the :grammar:`from <vector>` is omitted, the position of ego is used.
    """
    X = toVector(X, '"relative position of X from Y" with X not a vector')
    if Y is None:
        Y = ego()
    Y = toVector(Y, '"relative position of X from Y" with Y not a vector')
    return X - Y


def RelativeHeading(X, Y=None):
    """The :grammar:`relative heading of <heading> [from <heading>]` operator.

    If the :grammar:`from <heading>` is omitted, the heading of ego is used.
    """
    X = toOrientation(
        X, '"relative heading of X from Y" with X not a heading or orientation'
    )
    if Y is None:
        Y = ego().orientation
    else:
        Y = toOrientation(Y, '"relative heading of X from Y" with Y not a heading')
    return normalizeAngle(X.yaw - Y.yaw)


def ApparentHeadingOf(X, Y=None):
    """The :grammar:`apparent heading of <oriented point> [from <vector>]` operator.

    If the :grammar:`from <vector>` is omitted, the position of ego is used.
    """
    if not isA(X, OrientedPoint):
        raise TypeError('"apparent heading of X from Y" with X not an OrientedPoint')
    if Y is None:
        Y = ego()
    Y = toVector(Y, '"apparent heading of X from Y" with Y not a vector')
    return apparentHeadingAtPoint(X.position, X.heading, Y)


def ApparentHeadingTo(X, Y=None):
    """The :grammar:`apparent heading to <vector> [from <oriented point>]` operator.

    If the :grammar:`from <oriented point>` is omitted, the ego is used.
    """
    X = toVector(X, '"apparent heading to X from Y" with X not a vector')
    if Y is None:
        Y = ego()
    if not isA(Y, OrientedPoint):
        raise TypeError('"apparent heading to X from Y" with Y not an OrientedPoint')
    return Y.apparentHeadingTo(X)


def DistanceFrom(X, Y=None):
    """The :scenic:`distance from {X} to {Y}` polymorphic operator.

    Allowed forms::

        distance from <vector> [to <vector>]
        distance from <region> [to <vector>]
        distance from <vector> to <region>

    If the :grammar:`to <vector>` is omitted, the position of ego is used.
    """
    X = toTypes(
        X, (Vector, Region), '"distance from X to Y" with X neither a vector nor region'
    )
    if Y is None:
        Y = ego()
    Y = toTypes(
        Y, (Vector, Region), '"distance from X to Y" with Y neither a vector nor region'
    )
    return X.distanceTo(Y)


def MinDistanceFrom(X, Y=None):
    """The :grammar:`minimum distance from <object> [to <object>]` operator.

    If the :grammar:`to <object>` is omitted, the ego is used.
    """
    X = toTypes(X, (Object,), '"minimum distance from X to Y" with X not an Object')
    if Y is None:
        Y = ego()
    Y = toTypes(Y, (Object,), '"minimum distance from X to Y" with Y not an Object')
    return X.minimumDistanceTo(Y)


def DistancePast(X, Y=None):
    """The :grammar:`distance past <vector> of <oriented point>` operator.

    If the :grammar:`of {oriented point}` is omitted, the ego object is used.
    """
    X = toVector(X, '"distance past X" with X not a vector')
    if Y is None:
        Y = ego()
    Y = toType(Y, OrientedPoint, '"distance past X of Y" with Y not an OrientedPoint')
    return Y.distancePast(X)


# TODO(shun): Migrate to `AngleFrom`
def AngleTo(X):
    """The :grammar:`angle to <vector>` operator (using the position of ego as the reference)."""
    X = toVector(X, '"angle to X" with X not a vector')
    return ego().angleTo(X)


def AngleFrom(X=None, Y=None):
    """The :grammar:`angle from <vector> to <vector>` operator."""
    assert X is not None or Y is not None
    if X is None:
        X = ego()
    X = toVector(X, '"angle from X to Y" with X not a vector')
    if Y is None:
        Y = ego()
    Y = toVector(Y, '"angle from X to Y" with Y not a vector')
    return X.angleTo(Y)


def AltitudeTo(X):
    """The :grammar:`angle to <vector>` operator (using the position of ego as the reference)."""
    X = toVector(X, '"altitude to X" with X not a vector')
    return ego().altitudeTo(X)


def AltitudeFrom(X=None, Y=None):
    """The :grammar:`altitude from <vector> to <vector>` operator."""
    assert X is not None or Y is not None
    if X is None:
        X = ego()
    X = toVector(X, '"altitude from X to Y" with X not a vector')
    if Y is None:
        Y = ego()
    Y = toVector(Y, '"altitude from X to Y" with Y not a vector')
    return X.altitudeTo(Y)


def Follow(F, X, D):
    """The :grammar:`follow <field> from <vector> for <number>` operator."""
    if not isA(F, VectorField):
        raise TypeError('"follow F from X for D" with F not a vector field')
    X = toVector(X, '"follow F from X for D" with X not a vector')
    D = toScalar(D, '"follow F from X for D" with D not a number')
    pos = F.followFrom(X, D)
    orientation = F[pos]
    return OrientedPoint._with(position=pos, parentOrientation=orientation)


def VisibleFromOp(region, base):
    """The :grammar:`<region> visible from <point>` operator."""
    region = toType(region, Region, '"X visible from Y" with X not a Region')
    if not isA(base, Point):
        raise TypeError('"X visible from Y" with Y not a Point')
    return region.intersect(base.visibleRegion)


def NotVisibleFromOp(region, base):
    """The :grammar:`<region> not visible from <point>` operator."""
    region = toType(region, Region, '"X visible from Y" with X not a Region')
    if not isA(base, Point):
        raise TypeError('"X not visible from Y" with Y not a Point')

    return region.difference(base.visibleRegion)


def AheadOfOp(X, Y):
    """The :grammar:`<vector> ahead of <oriented point>` operator."""
    X = toVector(X, '"X ahead of Y" with X not a vector')
    if not isA(Y, OrientedPoint):
        raise TypeError('"X ahead of Y" with Y not an OrientedPoint')

    return math.radians(-89.99) < ApparentHeadingTo(X, Y) < math.radians(89.99)


def BehindOp(X, Y):
    """The :grammar:`<vector> behind <oriented point>` operator."""
    X = toVector(X, '"X behind Y" with X not a vector')
    if not isA(Y, OrientedPoint):
        raise TypeError('"X behind Y" with Y not an OrientedPoint')

    return ApparentHeadingTo(X, Y) < -math.radians(90.01) or math.radians(
        90.01
    ) < ApparentHeadingTo(X, Y)


def LeftOfOp(X, Y):
    """The :grammar:`<vector> left of <oriented point>` operator."""
    X = toVector(X, '"X left of Y" with X not a vector')
    if not isA(Y, OrientedPoint):
        raise TypeError('"X left of Y" with Y not an OrientedPoint')

    return math.radians(0.01) < ApparentHeadingTo(X, Y) < math.radians(180)


def RightOfOp(X, Y):
    """The :grammar:`<vector> right of <oriented point>` operator."""
    X = toVector(X, '"X right of Y" with X not a vector')
    if not isA(Y, OrientedPoint):
        raise TypeError('"X right of Y" with Y not an OrientedPoint')

    return -math.radians(180) < ApparentHeadingTo(X, Y) < math.radians(-0.01)


def CanSee(X, Y):
    """The :scenic:`{X} can see {Y}` polymorphic operator.

    Allowed forms::

        <point> can see <vector>
        <point> can see <point>
    """
    if isActive():
        raise InvalidScenarioError(
            '"can see" operator prohibited at top level of Scenic programs'
        )

    if not isA(X, Point):
        raise TypeError('"X can see Y" with X not a Point, OrientedPoint, or Object')

    if not canCoerce(Y, Vector):
        raise TypeError('"X can see Y" with Y not a Vector, Point, or Object')

    objects = toDistribution(currentScenario._objects)

    @distributionFunction
    def canSeeHelper(X, Y, objects):
        if not isA(Y, Point):
            Y = toVector(
                Y, '"X can see Y" with X not a Vector, Point, OrientedPoint, or Object'
            )

        occludingObjects = tuple(
            obj for obj in objects if obj.occluding and X is not obj and Y is not obj
        )

        return X.canSee(Y, occludingObjects=occludingObjects)

    return canSeeHelper(X, Y, objects)


@distributionFunction
def Intersects(X, Y):
    """The :scenic:`{X} intersects {Y}` operator."""
    if isA(X, Object):
        return X.intersects(Y)
    else:
        return Y.intersects(X)


### Specifiers


def With(prop, val):
    """The :grammar:`with <property> <value>` specifier.

    Specifies the given property, with no dependencies.
    """
    return Specifier(f"With({prop})", {prop: 1}, {prop: val})


def At(pos):
    """The :grammar:`at <vector>` specifier.

    Specifies :prop:`position`, with no dependencies.
    """
    pos = toVector(pos, 'specifier "at X" with X not a vector')
    return Specifier("At", {"position": 1}, {"position": pos})


def In(region):
    """The :grammar:`in <region>` specifier.

    Specifies :prop:`position`, and optionally, :prop:`parentOrientation` if the given region
    has a preferred orientation, with no dependencies.
    """
    region = toType(region, Region, 'specifier "in R" with R not a Region')
    pos = Region.uniformPointIn(region)
    props = {"position": 1}
    values = {"position": pos}
    if alwaysProvidesOrientation(region):
        props["parentOrientation"] = 3
        values["parentOrientation"] = region.orientation[pos]
    return Specifier("In", props, values)


def ContainedIn(region):
    """The :grammar:`contained in <region>` specifier.

    Specifies :prop:`position`, :prop:`regionContainedIn`, and optionally, :prop:`parentOrientation`
    if the given region has a preferred orientation, with no dependencies.
    """
    region = toType(region, Region, 'specifier "contained in R" with R not a Region')
    pos = Region.uniformPointIn(region)
    props = {"position": 1, "regionContainedIn": 1}
    values = {"position": pos, "regionContainedIn": region}
    if alwaysProvidesOrientation(region):
        props["parentOrientation"] = 3
        values["parentOrientation"] = region.orientation[pos]
    return Specifier("ContainedIn", props, values)


def On(thing):
    """The :specifier:`on {X}` specifier.

    Specifies :prop:`position`, and optionally, :prop:`parentOrientation` if the given region
    has a preferred orientation. Depends on :prop:`onDirection`, :prop:`baseOffset`,
    and :prop:`contactTolerance`.

    Note that while :specifier:`on` can be used with `Region`, `Object` and `Vector`,
    it cannot be used with a distribution containing anything other than `Region`.

    May be used to modify an already-specified :prop:`position` property.

    Allowed forms:
        on <region>
        on <object>
        on <vector>
    """
    if isA(thing, Object):
        # Target is an Object: use its onSurface.
        target = thing.onSurface
    elif canCoerce(thing, Vector, exact=True):
        # Target is a vector
        target = toVector(thing)
    elif canCoerce(thing, Region):
        # Target is a region (or could theoretically be coerced to one),
        # so we can use it as a target.
        target = toType(thing, Region)
    else:
        raise TypeError('specifier "on R" with R not a Region, Object, or Vector')

    props = {"position": 1}

    if isA(target, Region) and alwaysProvidesOrientation(target):
        props["parentOrientation"] = 2

    def helper(context):
        # Pick position based on whether we are specifying or modifying
        if hasattr(context, "position"):
            if isA(target, Vector):
                raise TypeError('Cannot use modifying "on V" with V a vector.')

            pos = projectVectorHelper(target, context.position, context.onDirection)
        elif isA(target, Vector):
            pos = target
        else:
            pos = Region.uniformPointIn(target)

        values = {}

        contactOffset = Vector(0, 0, context.contactTolerance / 2) - context.baseOffset

        if "parentOrientation" in props:
            values["parentOrientation"] = target.orientation[pos]
            contactOffset = contactOffset.rotatedBy(values["parentOrientation"])

        values["position"] = pos + contactOffset

        return values

    return ModifyingSpecifier(
        "On",
        props,
        DelayedArgument({"onDirection", "baseOffset", "contactTolerance"}, helper),
        modifiable_props={"position"},
    )


@distributionFunction
def projectVectorHelper(region, pos, onDirection):
    on_pos = region.projectVector(pos, onDirection=onDirection)

    if on_pos is None:
        raise RejectionException("Unable to place object on surface.")
    else:
        return on_pos


@distributionFunction
def orientedRegion(region):
    return region


@distributionFunction
def unorientedRegion(region):
    return region


def alwaysProvidesOrientation(region):
    """Whether a Region or distribution over Regions always provides an orientation."""
    isOriented = lambda r: (
        isinstance(region, TypecheckedDistribution)
        and isinstance(region._dist, FunctionDistribution)
        and region._dist.function.__name__ == "orientedRegion"  # TODO: IMPROVE THIS!!!
    )

    isUnoriented = lambda r: (
        isinstance(region, TypecheckedDistribution)
        and isinstance(region._dist, FunctionDistribution)
        and region._dist.function.__name__ == "unorientedRegion"  # TODO: IMPROVE THIS!!!
    )

    if isinstance(region, Region):
        return region.orientation is not None
    elif isinstance(region, MultiplexerDistribution) and all(
        alwaysProvidesOrientation(opt) for opt in region.options
    ):
        return True
    elif isOriented(region):
        return True
    elif isUnoriented(region):
        return False
    else:  # TODO improve somehow!
        warnings.warn(
            f"Cannot infer whether or not target always provides orientation.",
            stacklevel=2,
        )
        try:
            sample = region.sample()
            result = sample.orientation is not None or sample is nowhere
            return result
        except RejectionException:
            return False
        except Exception as e:
            warnings.warn(
                f"While sampling internally to determine if a random region provides an orientation, the following exception was raised: {repr(e)}"
            )
            return False


def OffsetBy(offset):
    """The :grammar:`offset by <vector>` specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, with no dependencies.
    """
    offset = toVector(offset, 'specifier "offset by X" with X not a vector')
    value = {
        "position": RelativeTo(offset, ego()).toVector(),
        "parentOrientation": ego().orientation,
    }
    return Specifier("OffsetBy", {"position": 1, "parentOrientation": 3}, value)


def OffsetAlongSpec(direction, offset):
    """The :specifier:`offset along {X} by {Y}` polymorphic specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, with no dependencies.

    Allowed forms::

        offset along <heading> by <vector>
        offset along <field> by <vector>
    """
    pos = OffsetAlong(ego(), direction, offset)
    parentOrientation = ego().orientation
    return Specifier(
        "OffsetAlong",
        {"position": 1, "parentOrientation": 3},
        {"position": pos, "parentOrientation": parentOrientation},
    )


def Beyond(pos, offset, fromPt=None):
    """The :specifier:`beyond {X} by {Y} from {Z}` polymorphic specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, with no dependencies.

    Allowed forms::

        beyond <vector> by <number> [from <vector>]
        beyond <vector> by <vector> [from <vector>]

    If the :grammar:`from <vector>` is omitted, the position of ego is used.
    """
    # Ensure X can be coerced into vector form
    pos = toVector(pos, 'specifier "beyond X by Y" with X not a vector')

    # If no from vector is specified, assume ego
    if fromPt is None:
        fromPt = ego()

    fromPt = toVector(fromPt, 'specifier "beyond X by Y from Z" with Z not a vector')

    dType = underlyingType(offset)

    if dType is builtins.float or dType is builtins.int:
        offset = Vector(0, offset, 0)
    else:
        # offset is not float or int, so try to coerce it into vector form.
        offset = toVector(
            offset, 'specifier "beyond X by Y" with X not a number or vector'
        )

    # If the from vector is oriented, set that to orientation. Else assume global coords.
    if isA(fromPt, OrientedPoint):
        orientation = fromPt.orientation
    else:
        orientation = Orientation.fromEuler(0, 0, 0)

    direction = pos - fromPt
    sphericalCoords = direction.sphericalCoordinates()
    offsetRotation = Orientation.fromEuler(sphericalCoords[1], sphericalCoords[2], 0)

    new_direction = pos + offset.applyRotation(offsetRotation)

    return Specifier(
        "Beyond",
        {"position": 1, "parentOrientation": 3},
        {"position": new_direction, "parentOrientation": orientation},
    )


def VisibleFrom(base):
    """The :grammar:`visible from <point>` specifier.

    Specifies :prop:`_observingEntity` and :prop:`position`, with no dependencies.
    """
    if not isA(base, Point):
        raise TypeError('specifier "visible from O" with O not a Point')

    def helper(self):
        if mode2D:
            position = Region.uniformPointIn(base.visibleRegion)
        else:
            containing_region = (
                currentScenario._workspace.region
                if self.regionContainedIn is None
                and currentScenario._workspace is not None
                else self.regionContainedIn
            )
            position = (
                Region.uniformPointIn(everywhere, tag="visible")
                if containing_region is None
                else Region.uniformPointIn(containing_region)
            )

        return {"position": position, "_observingEntity": base}

    return Specifier(
        "Visible/VisibleFrom",
        {"position": 3, "_observingEntity": 1},
        DelayedArgument({"regionContainedIn"}, helper),
    )


def VisibleSpec():
    """The :specifier:`visible` specifier (equivalent to :specifier:`visible from ego`).

    Specifies :prop:`_observingEntity` and :prop:`position`, with no dependencies.
    """
    return VisibleFrom(ego())


def NotVisibleFrom(base):
    """The :grammar:`not visible from <point>` specifier.

    Specifies :prop:`_nonObservingEntity` and :prop:`position`, depending on :prop:`regionContainedIn`.

    See `VisibleFrom`.
    """
    if not isA(base, Point):
        raise TypeError('specifier "not visible from O" with O not a Point')

    def helper(self):
        region = self.regionContainedIn
        if region is None:
            if currentScenario._workspace is None:
                raise InvalidScenarioError(
                    '"not visible" specifier with no workspace or containing region defined'
                )
            region = currentScenario._workspace.region

        if mode2D:
            position = Region.uniformPointIn(region.difference(base.visibleRegion))
        else:
            # We can't limit the available region since any spot could potentially be occluded.
            position = Region.uniformPointIn(convertToFootprint(region))

        return {"position": position, "_nonObservingEntity": base}

    return Specifier(
        "NotVisible/NotVisibleFrom",
        {"position": 3, "_nonObservingEntity": 1},
        DelayedArgument({"regionContainedIn"}, helper),
    )


def NotVisibleSpec():
    """The :specifier:`not visible` specifier (equivalent to :specifier:`not visible from ego`).

    Specifies :prop:`_nonObservingEntity` and :prop:`position`, depending on :prop:`regionContainedIn`.
    """
    return NotVisibleFrom(ego())


def LeftSpec(pos, dist=None):
    """The :specifier:`left of {X} by {Y}` polymorphic specifier.

    Specifies :prop:`position`, and optionally, :prop:`parentOrientation`, depending on :prop:`width`.

    Allowed forms::

        left of <oriented point> [by <scalar/vector>]
        left of <vector> [by <scalar/vector>]

    If the :grammar:`by <scalar/vector>` is omitted, the object's contact tolerance is used.
    """
    return directionalSpecHelper(
        "Left of",
        pos,
        dist,
        "width",
        lambda dist: (dist, 0, 0),
        lambda self, dims, tol, dx, dy, dz: Vector(
            -self.width / 2 - dx - dims[0] / 2 - tol, dy, dz
        ),
    )


def RightSpec(pos, dist=None):
    """The :specifier:`right of {X} by {Y}` polymorphic specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, depending on :prop:`width`.

    Allowed forms::

        right of <oriented point> [by <scalar/vector>]
        right of <vector> [by <scalar/vector>]

    If the :grammar:`by <scalar/vector>` is omitted, zero is used.
    """
    return directionalSpecHelper(
        "Right of",
        pos,
        dist,
        "width",
        lambda dist: (dist, 0, 0),
        lambda self, dims, tol, dx, dy, dz: Vector(
            self.width / 2 + dx + dims[0] / 2 + tol, dy, dz
        ),
    )


def Ahead(pos, dist=None):
    """The :specifier:`ahead of {X} by {Y}` polymorphic specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, depending on :prop:`length`.

    Allowed forms::

        ahead of <oriented point> [by <scalar/vector>]
        ahead of <vector> [by <scalar/vector>]

    If the :grammar:`by <scalar/vector>` is omitted, the object's contact tolerance is used.
    """
    return directionalSpecHelper(
        "Ahead of",
        pos,
        dist,
        "length",
        lambda dist: (0, dist, 0),
        lambda self, dims, tol, dx, dy, dz: Vector(
            dx, self.length / 2 + dy + dims[1] / 2 + tol, dz
        ),
    )


def Behind(pos, dist=None):
    """The :specifier:`behind {X} by {Y}` polymorphic specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, depending on :prop:`length`.

    Allowed forms::

        behind <oriented point> [by <scalar/vector>]
        behind <vector> [by <scalar/vector>]

    If the :grammar:`by <scalar/vector>` is omitted, the object's contact tolerance is used.
    """
    return directionalSpecHelper(
        "Behind",
        pos,
        dist,
        "length",
        lambda dist: (0, dist, 0),
        lambda self, dims, tol, dx, dy, dz: Vector(
            dx, -self.length / 2 - dy - dims[1] / 2 - tol, dz
        ),
    )


def Above(pos, dist=None):
    """The :specifier:`above {X} by {Y}` polymorphic specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, depending on :prop:`height`.

    Allowed forms::

        above <oriented point> [by <scalar/vector>]
        above <vector> [by <scalar/vector>]

    If the :grammar:`by <scalar/vector>` is omitted, the object's contact tolerance is used.
    """
    return directionalSpecHelper(
        "Above",
        pos,
        dist,
        "height",
        lambda dist: (0, 0, dist),
        lambda self, dims, tol, dx, dy, dz: Vector(
            dx, dy, self.height / 2 + dz + dims[2] / 2 + tol
        ),
    )


def Below(pos, dist=None):
    """The :specifier:`below {X} by {Y}` polymorphic specifier.

    Specifies :prop`position`, and optionally :prop:`parentOrientation`, depending on :prop:`height`.

    Allowed forms::

        below <oriented point> [by <scalar/vector>]
        below <vector> [by <scalar/vector>]

    If the :grammar:`by <scalar/vector>` is omitted, the object's contact tolerance is used.
    """
    return directionalSpecHelper(
        "Below",
        pos,
        dist,
        "height",
        lambda dist: (0, 0, dist),
        lambda self, dims, tol, dx, dy, dz: Vector(
            dx, dy, -self.height / 2 - dz - dims[2] / 2 - tol
        ),
    )


def directionalSpecHelper(syntax, pos, dist, axis, toComponents, makeOffset):
    prop = {"position": 1}
    if dist is None:
        dx = dy = dz = 0
    elif canCoerce(dist, builtins.float):
        dx, dy, dz = toComponents(coerce(dist, builtins.float))
    elif canCoerce(dist, Vector):
        dx, dy, dz = coerce(dist, Vector)
    else:
        raise TypeError(f'"{syntax} X by D" with D not a number or vector')

    @distributionFunction
    def makeContactOffset(dist, ct):
        if dist is None:
            return ct / 2
        else:
            return 0

    if isA(pos, Object):
        prop["parentOrientation"] = 3
        obj_dims = (pos.width, pos.length, pos.height)
        val = lambda self: {
            "position": pos.relativePosition(
                makeOffset(
                    self,
                    obj_dims,
                    makeContactOffset(dist, self.contactTolerance),
                    dx,
                    dy,
                    dz,
                )
            ),
            "parentOrientation": pos.orientation,
        }
        new = DelayedArgument({axis, "contactTolerance"}, val)
    elif isA(pos, OrientedPoint):
        prop["parentOrientation"] = 3
        val = lambda self: {
            "position": pos.relativePosition(makeOffset(self, (0, 0, 0), 0, dx, dy, dz)),
            "parentOrientation": pos.orientation,
        }
        new = DelayedArgument({axis}, val)
    else:
        pos = toVector(pos, f'specifier "{syntax} X" with X not a vector')
        val = lambda self: {
            "position": pos.offsetLocally(
                self.orientation, makeOffset(self, (0, 0, 0), 0, dx, dy, dz)
            )
        }
        new = DelayedArgument({axis, "orientation"}, val)
    return Specifier(syntax, prop, new)


def Following(field, dist, fromPt=None):
    """The :specifier:`following {F} from {X} for {D}` specifier.

    Specifies :prop:`position`, and optionally :prop:`parentOrientation`, with no dependencies.

    Allowed forms::

        following <field> [from <vector>] for <number>

    If the :grammar:`from <vector>` is omitted, the position of ego is used.
    """
    if fromPt is None:
        fromPt = ego()
    field = toType(field, VectorField)
    fromPt = toVector(fromPt, '"following F from X for D" with X not a vector')
    dist = toScalar(dist, '"following F for D" with D not a number')
    pos = field.followFrom(fromPt, dist)
    orientation = field[pos]
    return Specifier(
        "Following",
        {"position": 1, "parentOrientation": 3},
        {"position": pos, "parentOrientation": orientation},
    )


def Facing(heading):
    """The :specifier:`facing {X}` polymorphic specifier.

    Specifies :prop:`yaw`, :prop:`pitch`, and :prop:`roll`, depending on :prop:`parentOrientation`,
    and depending on the form::

        facing <number>     # no further dependencies;
        facing <field>      # depends on 'position'
    """
    if isA(heading, VectorField):

        def helper(context):
            headingAtPos = heading[context.position]
            if alwaysGlobalOrientation(context.parentOrientation):
                orientation = headingAtPos  # simplify expr tree in common case
            else:
                orientation = context.parentOrientation.inverse * headingAtPos
            return {
                "yaw": orientation.yaw,
                "pitch": orientation.pitch,
                "roll": orientation.roll,
            }

        return Specifier(
            "Facing",
            {"yaw": 1, "pitch": 1, "roll": 1},
            DelayedArgument({"position", "parentOrientation"}, helper),
        )
    else:
        orientation = toOrientation(
            heading, "facing x with x not a heading or orientation"
        )
        orientationDeps = requiredProperties(orientation)

        def helper(context):
            target_orientation = valueInContext(orientation, context)
            euler = context.parentOrientation.localAnglesFor(target_orientation)
            return {"yaw": euler[0], "pitch": euler[1], "roll": euler[2]}

        return Specifier(
            "Facing",
            {"yaw": 1, "pitch": 1, "roll": 1},
            DelayedArgument({"parentOrientation"} | orientationDeps, helper),
        )


def FacingToward(pos):
    """The :grammar:`facing toward <vector>` specifier.

    Specifies :prop:`yaw`, depending on :prop:`position` and :prop:`parentOrientation`.
    """
    pos = toVector(pos, 'specifier "facing toward X" with X not a vector')

    def helper(context):
        direction = pos - context.position
        rotated = direction.applyRotation(context.parentOrientation.inverse)
        sphericalCoords = (
            rotated.sphericalCoordinates()
        )  # Ignore the rho, sphericalCoords[0]
        return {"yaw": sphericalCoords[1]}

    return Specifier(
        "FacingToward",
        {"yaw": 1},
        DelayedArgument({"position", "parentOrientation"}, helper),
    )


def FacingDirectlyToward(pos):
    """The :grammar:`facing directly toward <vector>` specifier.

    Specifies :prop:`yaw` and :prop:`pitch`, depends on :prop:`position` and :prop:`parentOrientation`.
    """
    pos = toVector(pos, 'specifier "facing directly toward X" with X not a vector')

    def helper(context):
        """
        Same process as above, except by default also specify the pitch euler angle
        """
        direction = pos - context.position
        rotated = direction.applyRotation(context.parentOrientation.inverse)
        sphericalCoords = rotated.sphericalCoordinates()
        return {"yaw": sphericalCoords[1], "pitch": sphericalCoords[2]}

    return Specifier(
        "FacingDirectlyToward",
        {"yaw": 1, "pitch": 1},
        DelayedArgument({"position", "parentOrientation"}, helper),
    )


def FacingAwayFrom(pos):
    """The :grammar:`facing away from <vector>` specifier.

    Specifies :prop:`yaw`, depending on :prop:`position` and :prop:`parentOrientation`.
    """
    pos = toVector(pos, 'specifier "facing away from X" with X not a vector')

    def helper(context):
        """
        As in FacingToward, except invert the resulting rotation axis
        """
        direction = context.position - pos
        rotated = direction.applyRotation(context.parentOrientation.inverse)
        sphericalCoords = rotated.sphericalCoordinates()
        return {"yaw": sphericalCoords[1]}

    return Specifier(
        "FacingAwayFrom",
        {"yaw": 1},
        DelayedArgument({"position", "parentOrientation"}, helper),
    )


def FacingDirectlyAwayFrom(pos):
    """The :grammar:`facing directly away from <vector>` specifier.

    Specifies :prop:`yaw` and :prop:`pitch`, depending on :prop:`position` and :prop:`parentOrientation`.
    """
    pos = toVector(pos, 'specifier "facing away from X" with X not a vector')

    def helper(context):
        direction = context.position - pos
        rotated = direction.applyRotation(context.parentOrientation.inverse)
        sphericalCoords = rotated.sphericalCoordinates()
        return {"yaw": sphericalCoords[1], "pitch": sphericalCoords[2]}

    return Specifier(
        "FacingDirectlyToward",
        {"yaw": 1, "pitch": 1},
        DelayedArgument({"position", "parentOrientation"}, helper),
    )


def ApparentlyFacing(heading, fromPt=None):
    """The :grammar:`apparently facing <heading> [from <vector>]` specifier.

    Specifies :prop:`yaw`, depending on :prop:`position` and :prop:`parentOrientation`.

    If the :grammar:`from <vector>` is omitted, the position of ego is used.
    """
    heading = toHeading(heading, 'specifier "apparently facing X" with X not a heading')
    if fromPt is None:
        fromPt = ego()
    fromPt = toVector(
        fromPt, 'specifier "apparently facing X from Y" with Y not a vector'
    )

    def helper(context):
        return {"yaw": fromPt.angleTo(context.position) + heading}

    return Specifier(
        "ApparentlyFacing",
        {"yaw": 1},
        DelayedArgument({"position", "parentOrientation"}, helper),
    )


### Primitive internal functions, utilized after compiler conversion


@distributionFunction
def _toStrScenic(*args, **kwargs) -> str:
    return builtins.str(*args, **kwargs)


@distributionFunction
def _toFloatScenic(*args, **kwargs) -> float:
    return builtins.float(*args, **kwargs)


@distributionFunction
def _toIntScenic(*args, **kwargs) -> int:
    return builtins.int(*args, **kwargs)


### Primitive functions overriding Python builtins

# N.B. applying functools.wraps to preserve the metadata of the original
# functions seems to break pickling/unpickling


@distributionFunction
def filter(function, iterable):
    return list(builtins.filter(function, iterable))


@distributionFunction
def round(*args, **kwargs):
    return builtins.round(*args, **kwargs)


def len(obj):
    return obj.__len__()


def range(*args):
    if any(needsSampling(arg) for arg in args):
        raise RandomControlFlowError("cannot construct a range with random parameters")
    return builtins.range(*args)


### Temporal Operators Factories


def AtomicProposition(closure, syntaxId):
    return propositions.Atomic(closure, syntaxId)


def PropositionAnd(reqs):
    return propositions.And(reqs)


def PropositionOr(reqs):
    return propositions.Or(reqs)


def PropositionNot(req):
    return propositions.Not(req)


def Always(req):
    return propositions.Always(req)


def Eventually(req):
    return propositions.Eventually(req)


def Next(req):
    return propositions.Next(req)


def Until(lhs, rhs):
    return propositions.Until(lhs, rhs)


def Implies(lhs, rhs):
    return propositions.Implies(lhs, rhs)
