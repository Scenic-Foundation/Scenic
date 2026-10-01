"""Utilities used throughout the test suite."""

import functools
from importlib import metadata
import importlib.metadata
import inspect
import math
import multiprocessing
import re
import sys
import types
import weakref

import numpy
import pytest
import scipy.sparse
import shapely
import trimesh.caching

from scenic import scenarioFromString
from scenic.core.distributions import RejectionException
from scenic.core.simulators import DummySimulator, RejectSimulationException
from scenic.core.utils import DefaultIdentityDict
import scenic.syntax.veneer as veneer

## Scene generation utilities

# Compilation


def compileScenic(code, removeIndentation=True, scenario=None, mode2D=False, params={}):
    if removeIndentation:
        # to allow indenting code to line up with test function
        code = inspect.cleandoc(code)
    checkVeneerIsInactive()
    scenario = scenarioFromString(code, scenario=scenario, mode2D=mode2D, params=params)
    checkVeneerIsInactive()
    return scenario


# Static scenes


def sampleScene(scenario, maxIterations=1):
    return generateChecked(scenario, maxIterations)[0]


def sampleSceneFrom(code, maxIterations=1, scenario=None):
    scenario = compileScenic(code, scenario=scenario)
    return sampleScene(scenario, maxIterations=maxIterations)


def sampleEgo(scenario, maxIterations=1):
    scene, iterations = generateChecked(scenario, maxIterations)
    return scene.egoObject


def sampleEgoFrom(code, maxIterations=1, mode2D=False):
    scenario = compileScenic(code, mode2D=mode2D)
    return sampleEgo(scenario, maxIterations=maxIterations)


def sampleParamP(scenario, maxIterations=1):
    scene, iterations = generateChecked(scenario, maxIterations)
    return scene.params["p"]


def sampleParamPFrom(code, maxIterations=1):
    scenario = compileScenic(code)
    return sampleParamP(scenario, maxIterations=maxIterations)


def checkIfSamples(code, maxIterations=1):
    scenario = compileScenic(code)
    try:
        sampleScene(scenario, maxIterations=maxIterations)
    except RejectionException:
        return False

    return True


# Dynamic simulations


def sampleEgoActions(
    scenario, maxIterations=1, maxSteps=1, maxScenes=1, singleAction=True, timestep=1
):
    allActions = sampleActions(
        scenario,
        maxIterations,
        maxSteps,
        maxScenes,
        singleAction,
        asMapping=False,
        timestep=timestep,
    )
    return [
        actions[0] if actions else (None if singleAction else tuple())
        for actions in allActions
    ]


def sampleEgoActionsFromScene(
    scene, maxIterations=1, maxSteps=1, singleAction=True, timestep=1
):
    allActions = sampleActionsFromScene(
        scene,
        maxIterations=maxIterations,
        maxSteps=maxSteps,
        singleAction=singleAction,
        asMapping=False,
        timestep=timestep,
    )
    if allActions is None:
        return None
    return [
        actions[0] if actions else (None if singleAction else tuple())
        for actions in allActions
    ]


def sampleActions(
    scenario,
    maxIterations=1,
    maxSteps=1,
    maxScenes=1,
    singleAction=True,
    asMapping=False,
    timestep=1,
):
    for i in range(maxScenes):
        scene, iterations = generateChecked(scenario, maxIterations)
        actions = sampleActionsFromScene(
            scene,
            maxIterations=maxIterations,
            maxSteps=maxSteps,
            singleAction=singleAction,
            asMapping=asMapping,
            timestep=timestep,
        )
        if actions is not None:
            return actions
    raise RejectSimulationException(
        f"unable to find successful simulation over {maxScenes} scenes"
    )


def sampleActionsFromScene(
    scene, maxIterations=1, maxSteps=1, singleAction=True, asMapping=False, timestep=1
):
    sim = DummySimulator()
    simulation = sim.simulate(
        scene,
        maxSteps=maxSteps,
        maxIterations=maxIterations,
        timestep=timestep,
    )
    if not simulation:
        return None
    return getActionsFrom(simulation, singleAction=singleAction, asMapping=asMapping)


def sampleTrajectory(
    scenario,
    maxIterations=1,
    maxSteps=1,
    maxScenes=1,
    raiseGuardViolations=False,
    timestep=1,
):
    for i in range(maxScenes):
        scene, iterations = generateChecked(scenario, maxIterations)
        trajectory = sampleTrajectoryFromScene(
            scene,
            maxIterations=maxIterations,
            maxSteps=maxSteps,
            raiseGuardViolations=raiseGuardViolations,
            timestep=timestep,
        )
        if trajectory is not None:
            return trajectory
    raise RejectSimulationException(
        f"unable to find successful simulation over {maxScenes} scenes"
    )


def sampleResult(
    scenario, maxIterations=1, maxSteps=1, maxScenes=1, timestep=1, simulator=None
):
    for i in range(maxScenes):
        scene, iterations = generateChecked(scenario, maxIterations)
        result = sampleResultFromScene(
            scene,
            maxIterations=maxIterations,
            maxSteps=maxSteps,
            timestep=timestep,
            simulator=simulator,
        )
        if result is not None:
            return result
    raise RejectSimulationException(
        f"unable to find successful simulation over {maxScenes} scenes"
    )


def sampleResultOnce(scenario, maxSteps=1, timestep=1, simulator=None):
    scene = sampleScene(scenario)
    sim = DummySimulator() if simulator is None else simulator
    return sim.simulate(scene, maxSteps=maxSteps, maxIterations=1, timestep=timestep)


def sampleResultFromScene(
    scene,
    maxIterations=1,
    maxSteps=1,
    raiseGuardViolations=False,
    timestep=1,
    simulator=None,
):
    sim = DummySimulator() if simulator is None else simulator
    simulation = sim.simulate(
        scene,
        maxSteps=maxSteps,
        maxIterations=maxIterations,
        raiseGuardViolations=raiseGuardViolations,
        timestep=timestep,
    )
    if not simulation:
        return None
    return simulation.result


def sampleTrajectoryFromScene(
    scene, maxIterations=1, maxSteps=1, raiseGuardViolations=False, timestep=1
):
    result = sampleResultFromScene(
        scene,
        maxIterations=maxIterations,
        maxSteps=maxSteps,
        raiseGuardViolations=raiseGuardViolations,
        timestep=timestep,
    )
    if not result:
        return None
    return result.trajectory


# Helpers


def generateChecked(scenario, maxIterations):
    checkVeneerIsInactive()
    scene, iterations = scenario.generate(maxIterations=maxIterations)
    checkVeneerIsInactive()
    return scene, iterations


stopFlag = False


def checkVeneerIsInactive():
    global stopFlag
    if stopFlag:
        pytest.exit("veneer corrupted by last test", returncode=1)
    stopFlag = True
    assert veneer.activity == 0
    assert not veneer.scenarioStack
    assert not veneer.currentScenario
    assert not veneer.evaluatingRequirement
    assert not veneer.evaluatingGuard
    assert not veneer.scenarios
    assert not veneer._globalParameters
    assert not veneer.lockedParameters
    assert not veneer.lockedModel
    assert not veneer.currentSimulation
    assert not veneer.currentBehavior
    assert not veneer.mode2D
    stopFlag = False


def getActionsFrom(simulation, singleAction=True, asMapping=False):
    actionSequence = simulation.result.actions
    if singleAction:
        for i, allActions in enumerate(actionSequence):
            for agent, actions in allActions.items():
                assert len(actions) <= 1
                allActions[agent] = actions[0] if actions else None
    if asMapping:
        return actionSequence
    else:
        return [tuple(actions.values()) for actions in actionSequence]


def getEgoActionsFrom(simulation, singleAction=True):
    allActions = getActionsFrom(simulation, singleAction=singleAction)
    return [actions[0] for actions in allActions]


## Error checking utilities


def checkErrorLineNumber(line, exc_info=None):
    if exc_info is None:
        tb = sys.exc_info()[2]
    else:
        tb = exc_info.tb
    while tb.tb_next is not None:
        tb = tb.tb_next
    assert tb.tb_lineno == line


## Subprocess support

multiprocessing.set_start_method("spawn", force=True)


def runInSubprocess(func, *args, **kwargs):
    proc = multiprocessing.Process(target=func, args=args, kwargs=kwargs)
    proc.start()
    proc.join()
    assert proc.exitcode == 0


## Pickling

# TODO make pickling work with plain old pickle, rather than dill?
# (currently pickle chokes on various decorators and local functions)

try:
    import dill
except ModuleNotFoundError:
    dill = None
    dill_version = None
else:
    dill_version = metadata.version("dill")
pickle_test = pytest.mark.skipif(not dill, reason="dill required for pickling tests")


def tryPickling(thing, checkEquivalence=True, pickler=dill):
    checkVeneerIsInactive()
    pickled = pickler.dumps(thing)
    checkVeneerIsInactive()
    unpickled = pickler.loads(pickled)
    checkVeneerIsInactive()
    if checkEquivalence:
        assert areEquivalent(unpickled, thing)
    return unpickled


def areEquivalent(a, b, cache=None, debug=False, ignoreCacheAttrs=False, extraIgnores=()):
    """Whether two objects are equivalent, i.e. have the same properties.

    This is only used for debugging, e.g. to check that a Distribution is the
    same before and after pickling. We don't want to define __eq__ for such
    objects since for example two values sampled with the same distribution are
    equivalent but not semantically identical: the code::

        X = Range(0, 1)
        Y = Range(0, 1)

    does not make X and Y always have equal values!

    A further difference with __eq__ is that NaN compares unequal with itself,
    but we want all NaNs to be considered equal so that identical-in-memory
    data structures containing NaN count as equivalent.
    """
    if a is b:
        return True
    if cache is None:
        cache = DefaultIdentityDict()
    old = cache[a]
    if old is b:
        return True
    cache[a] = b  # prospectively assume equivalent, for recursive calls
    if areEquivalentInner(a, b, cache, debug, ignoreCacheAttrs, extraIgnores):
        return True
    else:
        cache[a] = old  # guess was wrong; revert cache
        return False


def areEquivalentInner(a, b, cache, debug, ignoreCacheAttrs, extraIgnores):
    if ignoreCacheAttrs:

        def ignorable(attr):
            return (
                attr == "__slotnames__"
                or attr.startswith("_cached_")
                or attr in extraIgnores
            )

    else:
        ignorable = lambda attr: False
    fail = breakpoint if debug else lambda: False

    from scenic.core.distributions import needsLazyEvaluation, needsSampling

    if not areEquivalent(type(a), type(b), cache, debug):
        fail()
        return False
    elif isinstance(a, (list, tuple)):
        if len(a) != len(b):
            fail()
            return False
        for x, y in zip(a, b):
            if not areEquivalent(x, y, cache, debug):
                fail()
                return False
    elif isinstance(a, (set, frozenset)):
        if len(a) != len(b):
            fail()
            return False
        mb = set(b)
        for x in a:
            found = False
            for y in mb:
                if areEquivalent(x, y, cache, debug=False):
                    found = True
                    break
            if not found:
                fail()
                return False
            mb.remove(y)
    elif isinstance(a, (dict, types.MappingProxyType)):
        kb = {k for k in b if not ignorable(k)}
        for x, v in a.items():
            if ignorable(x):
                continue
            found = False
            if x in kb:  # fast path
                y = x
            else:
                for y in kb:
                    if areEquivalent(x, y, cache, debug=False):
                        found = True
                        break
                if not found:
                    fail()
                    return False
            if not areEquivalent(v, b[y], cache, debug):
                fail()
                return False
            kb.remove(y)
        if kb:
            fail()
            return False
    elif inspect.isfunction(a):
        # These attributes we can check with simple equality
        attrs = ("__doc__", "__name__", "__qualname__", "__module__", "__code__")
        if any(getattr(a, attr) != getattr(b, attr) for attr in attrs):
            fail()
            return False
        # These attributes need a full equivalence check
        attrs = ("__defaults__", "__kwdefaults__", "__dict__", "__annotations__")
        for attr in attrs:
            if not areEquivalent(getattr(a, attr), getattr(b, attr), cache, debug):
                fail()
                return False
        # Lastly, we need to check that free variables are bound to equivalent objects
        # (effectively handling __closure__ and __globals__)
        if not areEquivalent(
            inspect.getclosurevars(a), inspect.getclosurevars(b), cache, debug
        ):
            fail()
            return False
    elif inspect.ismethod(a):
        # These attributes we can check with simple equality
        attrs = ("__doc__", "__name__", "__qualname__", "__module__")
        if any(getattr(a, attr) != getattr(b, attr) for attr in attrs):
            fail()
            return False
        # These attributes need a full equivalence check
        for attr in ("__func__", "__self__"):
            if not areEquivalent(getattr(a, attr), getattr(b, attr), cache, debug):
                fail()
                return False
    elif isinstance(a, property):
        for attr in ("fget", "fset", "fdel", "__doc__"):
            if not areEquivalent(getattr(a, attr), getattr(b, attr), cache, debug):
                fail()
                return False
    elif isinstance(a, types.GetSetDescriptorType):
        for attr in ("__name__", "__objclass__", "__doc__"):
            if not areEquivalent(getattr(a, attr), getattr(b, attr), cache, debug):
                fail()
                return False
    elif isinstance(a, weakref.ref):
        if not areEquivalent(a(), b(), cache, debug):
            fail()
            return False
        if not areEquivalent(a.__callback__, b.__callback__, cache, debug):
            fail()
            return False
    elif inspect.isclass(a):
        # These attributes we can check with simple equality
        attrs = ("__doc__", "__name__")
        if any(getattr(a, attr) != getattr(b, attr) for attr in attrs):
            fail()
            return False
        # The __module__ attribute can be checked with simple equality, but we allow
        # certain mismatches to work around https://github.com/uqfoundation/dill/issues/612
        if a.__module__ != b.__module__ and (
            a.__module__ != "dill._dill" or dill_version != "0.3.7"
        ):
            fail()
            return False
        # These attributes need a full equivalence check
        if not areEquivalent(a.__bases__, b.__bases__, cache, debug):
            fail()
            return False
        if not areEquivalent(
            a.__dict__,
            b.__dict__,
            cache,
            debug,
            ignoreCacheAttrs=True,
            extraIgnores=(
                "__module__",
                "_abc_impl",
                "_abc_registry",
                "_abc_cache",
                "_abc_negative_cache",
                "_abc_negative_cache_version",
            ),
        ):
            fail()
            return False
        # Checking annotations depends on Python version, unfortunately
        if sys.version_info >= (3, 10):
            if not areEquivalent(
                inspect.get_annotations(a), inspect.get_annotations(b), cache, debug
            ):
                fail()
                return False
        else:
            # No need to explicitly check annotations: they are included in __dict__ for
            # Python 3.9 and earlier.
            pass
    elif isinstance(a, numpy.ndarray):
        if a.dtype != b.dtype or len(a) != len(b):
            fail()
            return False
        if a.dtype.kind == "O":
            # The equal_nan option below raises an exception for certain types of
            # objects, so for object arrays we'll do the comparison ourselves.
            for x, y in zip(a, b):
                if not areEquivalent(x, y, cache, debug):
                    fail()
                    return False
        elif not numpy.array_equal(a, b, equal_nan=True):
            fail()
            return False
    elif isinstance(a, scipy.sparse.spmatrix):
        return areEquivalent(a.toarray(), b.toarray(), cache, debug)
    elif isinstance(a, shapely.STRtree):
        return areEquivalent(a.geometries, b.geometries, cache, debug)
    elif isinstance(a, trimesh.Trimesh):
        # Avoid testing cached info which is determined by `_data` and tends to
        # contain nasty `ctypes` objects which can't be compared.
        return areEquivalent(a._data, b._data, cache, debug)
    elif isinstance(a, trimesh.caching.DataStore):
        # Special case needed since DataStore's implementation of __eq__ fails
        return areEquivalent(a.data, b.data, cache, debug)
    elif not needsSampling(a) and not needsLazyEvaluation(a) and a == b:
        # This is not just a shortcut: there can be values whose internal attributes
        # differ but which nevertheless compare equal.
        return True
    elif isinstance(a, float) and math.isnan(a):
        # Special case since NaN is not equal to itself, but we consider it equivalent.
        if not math.isnan(b):
            fail()
            return False
    else:
        # This is a type we know nothing about; require equivalence of all of its attributes that
        # we can find statically. (Objects hiding state in funny places, or with internal
        # attributes that aren't preserved by pickling & unpickling, had better define __eq__.)
        hasDict = hasattr(a, "__dict__")
        if hasDict and not areEquivalent(
            a.__dict__, b.__dict__, cache, debug, ignoreCacheAttrs=True
        ):
            fail()
            return False
        slots = set()
        for cls in type(a).__mro__:
            slots.update(getattr(cls, "__slots__", ()))
        sentinel = object()
        for slot in slots:
            if not areEquivalent(
                getattr(a, slot, sentinel), getattr(b, slot, sentinel), cache, debug
            ):
                fail()
                return False
        # If the object has no attributes at all, we have to fall back on __eq__
        if not hasDict and not slots:
            if not a == b:
                fail()
                return False
    return True


def deprecationTest(removalVersion):
    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            m_ver = tuple(re.split(r"\D+", removalVersion)[:3])
            c_ver = tuple(re.split(r"\D+", importlib.metadata.version("scenic"))[:3])
            assert (
                m_ver > c_ver
            ), "Maximum version exceeded. The tested functionality and the test itself should be removed."

            with pytest.deprecated_call():
                return function(*args, **kwargs)

        return wrapper

    return decorator
