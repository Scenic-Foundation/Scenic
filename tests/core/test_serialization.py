"""Tests for various ways to serialize Scenic scenes/scenarios.

For pickling, see ``test_pickle.py`` and many other tests marked with
`pickle_test` throughout the test suite.
"""

import io
import math
import random

import numpy
import pytest

import scenic
from scenic.core.serialization import SerializationError, Serializer, deterministicHash
from scenic.core.simulators import DivergenceError, DummySimulator
from tests.simulators.metadrive.test_metadrive import getMetadriveSimulator
from tests.utils import (
    areEquivalent,
    compileScenic,
    getEgoActionsFrom,
    runInSubprocess,
    sampleEgoActionsFromScene,
    sampleScene,
    sampleSceneFrom,
)

# Utilities

simpleScenario = """
    ego = new Object at Range(3, 5) @ 2,
        with foo Uniform('zoggle', 'buggle'),
        with name "egoObject"
    new Object at 10@10,
        facing toward ego,
        with foo Options({Range(1,2): 1, Range(3,4): 2}),
        with name "otherObject"
    param qux = ego.position
    param baz = ({'a', 'b', 'c', 'd'}, frozenset({'e', 'f', 'g', 'h'}))
"""


def skeleton(scene):
    # Simple picklable representation of the main parameters of the scene
    objs = [(o.position, o.heading, getattr(o, "foo", 0)) for o in scene.objects]
    return {"objects": objs, "params": scene.params}


def assertSceneEquivalence(scene1, scene2, ignoreScenario=False):
    assert skeleton(scene1) == skeleton(scene2)
    # Samples may not be equivalent since we only serialize random values which actually
    # get used in the scene; so need to delete them before checking equivalence.
    del scene1.sample, scene2.sample
    if ignoreScenario:
        del scene1.scenario, scene2.scenario
        del scene1.dynamicScenario, scene2.dynamicScenario
    for obj in scene1.objects + scene2.objects:
        del obj._sampleParent
        if ignoreScenario:
            del obj._constProps
            del obj._parentScenario
    assert areEquivalent(scene1, scene2)


# Exporting scenes to Scenic code


class TestExportToScenicCode:
    def test_simple(self):
        scene1 = sampleSceneFrom(simpleScenario)
        stream = io.StringIO()
        scene1.dumpAsScenicCode(stream)
        code = stream.getvalue()
        scene2 = sampleSceneFrom(code)
        assertSceneEquivalence(
            scene1,
            scene2,
            ignoreScenario=True,
        )


# Serializing scenes and simulations given a compiled scenario


def checkReconstruction(code, n=20):
    # Repeat the test several times to catch nondeterminism due to hash
    # randomization, for example
    for i in range(n):
        seed = random.randint(0, 1000000)
        scenario = compileScenic(code)
        random.seed(seed)
        numpy.random.seed(seed)
        scene = sampleScene(scenario)
        skel = skeleton(scene)
        data = scenario.sceneToBytes(scene)
        runInSubprocess(subprocessHelper, code, seed, data, skel)


def subprocessHelper(code, seed, data, skel):
    import scenic.core.errors as errors

    errors.showInternalBacktrace = True
    scenario = compileScenic(code)
    print(scenario.astHash)
    scene1 = scenario.sceneFromBytes(data)
    assert scenario.sceneToBytes(scene1) == data
    assert skeleton(scene1) == skel
    random.seed(seed)
    numpy.random.seed(seed)
    scene2 = sampleScene(scenario)
    assert scenario.sceneToBytes(scene2) == data
    assert skeleton(scene2) == skel
    assertSceneEquivalence(scene1, scene2)


def checkValueEncoding(val, ty, allowPickle=False):
    enc = Serializer(allowPickle=allowPickle)
    enc.writeValue(val, ty)
    data = enc.getBytes()
    dec = Serializer(data, allowPickle=allowPickle)
    val2 = dec.readValue(ty)
    assert areEquivalent(val, val2)


class Thingy:
    def __init__(self, x):
        self.x = x


class TestExportToBytes:
    def test_int(self):
        checkValueEncoding(0, int)
        checkValueEncoding(42, int)
        checkValueEncoding(-42, int)
        checkValueEncoding(256, int)
        checkValueEncoding(-1724, int)
        checkValueEncoding(123456, int)
        checkValueEncoding(-123456, int)
        checkValueEncoding(2**32 - 1, int)
        checkValueEncoding(2**32, int)
        checkValueEncoding(2**64 - 1, int)
        checkValueEncoding(2**64, int)
        checkValueEncoding(3**30, int)
        checkValueEncoding(-(5**21), int)

    def test_huge_int(self):
        # Check that this fails with a SerializationError rather than silently
        # failing to encode the value properly.
        with pytest.raises(SerializationError):
            checkValueEncoding(256**256, int)

    def test_bool(self):
        checkValueEncoding(False, bool)
        checkValueEncoding(True, bool)

    def test_float(self):
        checkValueEncoding(3.14159, float)
        checkValueEncoding(-2.71828, float)
        checkValueEncoding(4.123e50, float)
        checkValueEncoding(7.89e-50, float)
        checkValueEncoding(float("inf"), float)
        checkValueEncoding(float("nan"), float)

    def test_bytes(self):
        checkValueEncoding(b"", bytes)
        checkValueEncoding(b"\x00", bytes)
        checkValueEncoding(b"\xff", bytes)
        checkValueEncoding(b"\x00123456", bytes)

    def test_str(self):
        checkValueEncoding("", str)
        checkValueEncoding("0", str)
        checkValueEncoding("123456", str)
        checkValueEncoding("squeamish ossifrage", str)

    def test_object_with_encodeTo(self):
        from scenic.simulators.utils.colors import Color

        checkValueEncoding(Color(0.5, 1.0, 0.2), Color)
        from scenic.core.vectors import Orientation, Vector

        checkValueEncoding(Vector(-7.5, 42), Vector)
        checkValueEncoding(
            Orientation.fromEuler(0.2 * math.pi, 0.6 * math.pi, 0), Orientation
        )

        class Foo:
            def __init__(self, x):
                self.x = x

            @staticmethod
            def encodeTo(value, stream):
                stream.write(bytes([1, 2, value.x, 4]))

            @staticmethod
            def decodeFrom(stream):
                data = stream.read(4)
                return Foo(data[2])

        checkValueEncoding(Foo(13), Foo)

    def test_object_pickle(self):
        checkValueEncoding(Thingy(42), object, allowPickle=True)
        checkValueEncoding(Thingy("foo"), Thingy, allowPickle=True)

    def test_simple_scene(self):
        scenario = compileScenic(simpleScenario)
        scene1 = sampleScene(scenario)
        data = scenario.sceneToBytes(scene1)
        scene2 = scenario.sceneFromBytes(data)
        assert scenario.sceneToBytes(scene2) == data
        assertSceneEquivalence(scene1, scene2)

    def test_scene_random_orientation(self):
        program = """
            box = BoxRegion(dimensions=(5,5,5))
            new Object in box, facing (Range(0,360) deg, Range(0,360) deg, Range(0,360) deg)
            new Object on box.getSurfaceRegion()
        """
        scenario = compileScenic(program)
        scene1 = sampleScene(scenario, maxIterations=10)
        data = scenario.sceneToBytes(scene1)
        scene2 = scenario.sceneFromBytes(data)
        assert scenario.sceneToBytes(scene2) == data
        assertSceneEquivalence(scene1, scene2)

    def test_scene_comment(self):
        """Adding comments to a scenario should not break deserialization."""
        sc1 = compileScenic(simpleScenario)
        sc2 = compileScenic(simpleScenario + "    # this shouldn't change anything")
        scene1 = sampleScene(sc1)
        data = sc1.sceneToBytes(scene1)
        scene2 = sc2.sceneFromBytes(data)
        assert sc2.sceneToBytes(scene2) == data
        assertSceneEquivalence(scene1, scene2, ignoreScenario=True)

    def test_scene_different_scenario(self):
        sc1 = compileScenic(simpleScenario)
        sc2 = compileScenic(simpleScenario + "\n    mutate")
        scene1 = sampleScene(sc1)
        data = sc1.sceneToBytes(scene1)
        with pytest.raises(SerializationError):
            sc2.sceneFromBytes(data)

    def test_scene_different_scenario_modular(self):
        code = """
            scenario Main():
                ego = new Object
            scenario Foo():
                ego = new Object at (10, 10)
        """
        sc1 = compileScenic(code)
        sc2 = compileScenic(code, scenario="Foo")
        scene1 = sampleScene(sc1)
        data = sc1.sceneToBytes(scene1)
        with pytest.raises(SerializationError):
            sc2.sceneFromBytes(data)

    def test_scene_inconsistent_mode(self):
        sc1 = compileScenic(simpleScenario)
        sc2 = compileScenic(simpleScenario, mode2D=True)
        scene1 = sampleScene(sc1)
        data = sc1.sceneToBytes(scene1)
        with pytest.raises(SerializationError):
            sc2.sceneFromBytes(data)

    def test_scene_inconsistent_params(self):
        code = """
            ego = new Object
            param x = 1
        """
        sc1 = compileScenic(code, params={"x": 1})
        sc2 = compileScenic(code, params={"x": 2})
        scene1 = sampleScene(sc1)
        data = sc1.sceneToBytes(scene1)
        with pytest.raises(SerializationError):
            sc2.sceneFromBytes(data)

    def test_scene_behavior(self):
        scenario = compileScenic(
            """
            glob = Range(1, 2)
            behavior Foo(x):
                take glob
                take x
            ego = new Object with behavior Foo(Range(3, 4))
        """
        )
        scene1 = sampleScene(scenario)
        a11, a12 = sampleEgoActionsFromScene(scene1, maxSteps=2)
        assert 1 <= a11 <= 2
        assert 3 <= a12 <= 4
        data = scenario.sceneToBytes(scene1)
        scene2 = scenario.sceneFromBytes(data)
        a21, a22 = sampleEgoActionsFromScene(scene2, maxSteps=2)
        assert a21 == a11
        assert a22 == a12
        print(a11, a21, a12, a22)

    behaviorLocalsScenario = """
        behavior Foo(x):
            a = 1; b = 2; c = 3; d = 4
            take a+b+c+d+x
        ego = new Object with behavior Foo(Range(0, 1))
    """

    def test_scene_behavior_locals(self):
        scenario = compileScenic(self.behaviorLocalsScenario)
        scene1 = sampleScene(scenario)
        a1 = sampleEgoActionsFromScene(scene1, maxSteps=1)[0]
        assert 10 <= a1 <= 11
        data = scenario.sceneToBytes(scene1)
        scene2 = scenario.sceneFromBytes(data)
        a2 = sampleEgoActionsFromScene(scene2, maxSteps=1)[0]
        assert a2 == a1

    @pytest.mark.slow
    def test_separate_interpreters(self):
        checkReconstruction(simpleScenario)

    @pytest.mark.slow
    def test_separate_interpreters_locals(self):
        checkReconstruction(self.behaviorLocalsScenario)


class TestSimulationReplay:
    def simulateReplayFrom(self, code, steps=1, steps2=None, maxIterations=1, **kwargs):
        if not steps2:
            steps2 = steps
        scene = sampleSceneFrom(code)
        simulator = DummySimulator()
        sim1 = simulator.simulate(
            scene, maxSteps=steps, maxIterations=maxIterations, **kwargs
        )
        replay = sim1.getReplay()
        sim2 = simulator.replay(
            scene, replay, maxSteps=steps2, maxIterations=maxIterations, **kwargs
        )
        return sim1, sim2

    def checkReplay(self, code, steps=1, **kwargs):
        sim1, sim2 = self.simulateReplayFrom(code, steps, **kwargs)
        actions = getEgoActionsFrom(sim1)
        assert actions == getEgoActionsFrom(sim2)
        return actions

    def test_basic(self):
        self.checkReplay(
            """
            behavior Foo():
                take Range(1, 2)
                take 42
                take Uniform('refuge', 'umbrage', 'a hike')
            ego = new Object with behavior Foo
        """,
            steps=3,
        )

    def test_global(self):
        self.checkReplay(
            """
            x = Range(1, 2)
            behavior Foo():
                take x
            ego = new Object with behavior Foo
        """
        )

    def test_argument(self):
        self.checkReplay(
            """
            behavior Foo(x):
                take x
            ego = new Object with behavior Foo(Range(-1, 1))
        """
        )

    @pytest.mark.slow
    def test_soft_requirement(self):
        for i in range(100):
            self.checkReplay(
                """
                checkCount = 0
                def check(x):
                    global checkCount
                    checkCount += 1
                    return x >= 1
                behavior Foo():
                    while True:
                        x = Range(0, 2)
                        require[0.9] check(x)
                        take checkCount
                ego = new Object with behavior Foo
            """,
                steps=2,
                maxIterations=100,
            )

    def test_continue_after_replay(self):
        sim1, sim2 = self.simulateReplayFrom(
            """
            behavior Foo():
                while True:
                    take Range(0, 1)
            ego = new Object with behavior Foo
        """,
            steps=2,
            steps2=4,
        )
        a1 = getEgoActionsFrom(sim1)
        assert len(a1) == 2
        a2 = getEgoActionsFrom(sim2)
        assert len(a2) == 4
        assert a1[:2] == a2[:2]
        assert a2[2] not in a2[:2]
        assert a2[3] not in a2[:2]

    def divergenceHelper(self, drift, maxSteps=1):
        scene = sampleSceneFrom(
            """
            behavior Foo():
                while True:
                    take Range(0, 1)
            ego = new Object with behavior Foo
            new Object at (10, 0)
        """
        )
        simulator1 = DummySimulator(drift=drift)
        sim1 = simulator1.simulate(
            scene, maxSteps=maxSteps, maxIterations=1, enableDivergenceCheck=True
        )
        replay = sim1.getReplay()
        return scene, replay

    def test_divergence_basic(self):
        scene, replay = self.divergenceHelper(drift=1.0)
        sim = DummySimulator(drift=1.1)
        with pytest.raises(DivergenceError):
            sim.replay(scene, replay, maxSteps=1)

    def test_divergence_none(self):
        scene, replay = self.divergenceHelper(drift=1.0)
        sim = DummySimulator(drift=1.0)
        sim.replay(scene, replay, maxSteps=1)

    def test_divergence_tolerance_met(self):
        scene, replay = self.divergenceHelper(drift=1.0, maxSteps=5)
        sim = DummySimulator(drift=1.001)
        sim.replay(scene, replay, maxSteps=5, divergenceTolerance=0.01)

    def test_divergence_tolerance_met_continue(self):
        scene, replay = self.divergenceHelper(drift=1.0, maxSteps=5)
        sim = DummySimulator(drift=1.001)
        sim.replay(scene, replay, maxSteps=50, divergenceTolerance=0.01)

    def test_divergence_tolerance_exceeded(self):
        scene, replay = self.divergenceHelper(drift=1.0, maxSteps=5)
        sim = DummySimulator(drift=1.001)
        with pytest.raises(DivergenceError):
            sim.replay(scene, replay, maxSteps=5, divergenceTolerance=0.004)

    def test_divergence_continue(self):
        scene = sampleSceneFrom(
            """
            behavior Foo():
                while True:
                    take Range(0, 1)
            ego = new Object with behavior Foo
            new Object at (10, 0)
        """
        )
        simulator1 = DummySimulator(drift=1.0)
        sim1 = simulator1.simulate(
            scene, maxSteps=1, maxIterations=1, enableDivergenceCheck=True
        )
        replay = sim1.getReplay()
        simulator2 = DummySimulator(drift=1.1)
        sim2 = simulator2.replay(
            scene, replay, maxSteps=2, continueAfterDivergence=True, verbosity=3
        )
        a1, a2 = getEgoActionsFrom(sim1), getEgoActionsFrom(sim2)
        assert len(a1) == 1
        assert len(a2) == 2
        assert a2[0] == a1[0]
        assert a2[1] != a1[0]

    def test_combined_serialization(self):
        scenario = compileScenic(
            """
            behavior Foo():
                take Range(0, 1)
            ego = new Object with behavior Foo
        """
        )
        scene = sampleScene(scenario)
        simulator = DummySimulator()
        sim1 = simulator.simulate(scene, maxSteps=1, maxIterations=1)
        data = scenario.simulationToBytes(sim1)
        sim2 = scenario.simulationFromBytes(data, simulator, maxSteps=1)
        assert getEgoActionsFrom(sim1) == getEgoActionsFrom(sim2)

    def test_staged_serialization(self):
        scenario = compileScenic(
            """
            behavior Foo():
                take Range(0, 1) + self.bar
            ego = new Object with behavior Foo, with bar Range(0,1)
        """
        )
        seed = random.getrandbits(32)
        sceneOrig = sampleScene(scenario)
        simulator = DummySimulator()

        sceneBytes = scenario.sceneToBytes(sceneOrig)
        sceneRestored = scenario.sceneFromBytes(sceneBytes)
        scenic.setSeed(seed)
        simOrig = simulator.simulate(sceneOrig, maxSteps=1, maxIterations=1)
        scenic.setSeed(seed)
        simRestored = simulator.simulate(sceneRestored, maxSteps=1, maxIterations=1)
        simBytes = scenario.simulationToBytes(simRestored)
        simRestoredRestored = scenario.simulationFromBytes(
            simBytes, simulator, maxSteps=1
        )
        assert (
            getEgoActionsFrom(simOrig)
            == getEgoActionsFrom(simRestored)
            == getEgoActionsFrom(simRestoredRestored)
        )


def test_deterministic_hash_non_scalar_values():
    class Foo:
        pass

    mapping1 = {"a": Foo()}
    mapping2 = {"a": Foo()}  # different instance, still non-scalar

    digest1 = deterministicHash(mapping1)
    digest2 = deterministicHash(mapping2)
    # Non-scalar values should hash in a stable way, independent of identity.
    assert digest1 == digest2
