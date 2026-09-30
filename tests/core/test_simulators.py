import itertools
import multiprocessing
import random
import time

import pytest

import scenic
from scenic.core.simulators import (
    DummySimulation,
    DummySimulator,
    Simulation,
    SimulatorGroup,
    TerminatedSimulationException,
)
from tests.utils import (
    RejectSimulationException,
    checkVeneerIsInactive,
    compileScenic,
    sampleResult,
    sampleResultFromScene,
    sampleSceneFrom,
)


def test_old_style_simulator():
    with pytest.raises(RuntimeError) as e:

        class MySimulation(Simulation):
            def run(*args, **kwargs):
                assert False

    assert "old-style simulation API" in str(e)

    with pytest.raises(RuntimeError) as e:

        class MySimulation(Simulation):
            def createObject(*args, **kwargs):
                assert False

    assert "old-style simulation API" in str(e)


def test_simulator_destruction():
    sim = DummySimulator()
    scene = sampleSceneFrom("ego = new Object")
    sim.simulate(scene, maxSteps=1)
    sim.destroy()
    with pytest.raises(RuntimeError) as e:
        sim.simulate(scene, maxSteps=1)
    assert "simulator cannot run additional simulations" in str(e)
    with pytest.raises(RuntimeError) as e:
        sim.destroy()
    assert "destroy() called twice" in str(e)


def test_simulator_stepped():
    simulator = DummySimulator()
    scene = sampleSceneFrom("ego = new Object")

    with simulator.simulateStepped(scene, maxSteps=5) as simulation:
        while simulation.result is None:
            simulation.advance()

        assert simulation.result is not None
        assert simulation.currentTime == 5

        # advance() should do nothing but raise an exception
        # if the simulation is already terminated
        with pytest.raises(TerminatedSimulationException):
            simulation.advance()

        assert simulation.currentTime == 5

    # Ensure all values are preserved after leaving the context manager
    assert simulation.result is not None
    assert simulation.currentTime == 5


def test_simulator_set_property():
    class TestSimulation(DummySimulation):
        def createObjectInSimulator(self, obj):
            super().createObjectInSimulator(obj)
            obj.foo = "bar"

    class TestSimulator(DummySimulator):
        def createSimulation(self, scene, **kwargs):
            return TestSimulation(scene, drift=self.drift, **kwargs)

    scenario = compileScenic(
        """
        class TestObj:
            foo: None

        ego = new TestObj

        record ego.foo as test_val_1
        record initial ego.foo as test_val_2
        record final ego.foo as test_val_3
    """
    )

    scene, _ = scenario.generate(maxIterations=1)
    simulator = TestSimulator()
    result = simulator.simulate(scene, maxSteps=2)
    assert result is not None
    assert result.records["test_val_1"] == [(0, "bar"), (1, "bar"), (2, "bar")]
    assert result.records["test_val_2"] == result.records["test_val_3"] == "bar"


def test_simulator_bad_scheduler():
    class TestSimulation(DummySimulation):
        def scheduleForAgents(self):
            # Don't include the last agent
            return self.agents[:-1]

    class TestSimulator(DummySimulator):
        def createSimulation(self, scene, **kwargs):
            return TestSimulation(scene, **kwargs)

    scenario = compileScenic(
        """
        behavior Foo():
            take 1

        class TestObj:
            allowCollisions: True
            behavior: Foo

        for _ in range(5):
            new TestObj
        """
    )

    scene, _ = scenario.generate(maxIterations=1)
    simulator = TestSimulator()
    with pytest.raises(RuntimeError):
        result = simulator.simulate(scene, maxSteps=2)


@pytest.mark.slow
def test_simulator_group():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                require Range(0,1) < 0.99
                wait

        new Object with behavior Foo()
        """
    )

    for numWorkers, serialized, scene_stream, sim_stream in itertools.product(
        [1, 2], [True, False], [True, False], [True, False]
    ):
        if scene_stream:
            scenes = scenario.generateStream(
                200, numWorkers=numWorkers, serialized=serialized, iterationCount=False
            )
        else:
            scenes, _ = scenario.generateBatch(
                200, numWorkers=numWorkers, serialized=serialized
            )

        sim_group = SimulatorGroup(numWorkers=2, simulatorClass=DummySimulator)

        simulate_params = {"maxSteps": 10}

        if sim_stream:
            results = tuple(
                result
                for _, result in sim_group.simulateStream(
                    scenario,
                    scenes,
                    simulateParams=simulate_params,
                    serialized=serialized,
                )
            )
        else:
            results = sim_group.simulateBatch(
                scenario, scenes, simulateParams=simulate_params, serialized=serialized
            )

        assert any(val is None for val in results)
        assert any(val is not None for val in results)


def test_simulator_group_deterministic():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                require Range(0,1) < 0.99
                wait

        new Object with behavior Foo()
        """
    )

    seed = random.getrandbits(32)

    scenic.setSeed(seed)
    scenes, _ = scenario.generateBatch(200, serialized=True)

    sim_group = SimulatorGroup(numWorkers=4, simulatorClass=DummySimulator)
    simulate_params = {"maxSteps": 10}

    results1 = tuple(
        result
        for _, result in sim_group.simulateStream(
            scenario, scenes, simulateParams=simulate_params, deterministic=True
        )
    )

    scenic.setSeed(seed)
    scenes, _ = scenario.generateBatch(200, serialized=True)

    sim_group = SimulatorGroup(numWorkers=4, simulatorClass=DummySimulator)
    simulate_params = {"maxSteps": 10}

    results2 = tuple(
        result
        for _, result in sim_group.simulateStream(
            scenario, scenes, simulateParams=simulate_params, deterministic=True
        )
    )

    assert len(results1) == len(results2)
    assert all((v1 is None) == (v2 is None) for v1, v2 in zip(results1, results2))


class BlockingSimulator(DummySimulator):
    def __init__(self, *args, **kwargs):
        self.cleanupEvent = kwargs.pop("cleanupEvent", None)
        assert self.cleanupEvent is not None
        super().__init__(*args, **kwargs)

    def createSimulation(self, *args, **kwargs):
        return BlockingSimulation(*args, cleanupEvent=self.cleanupEvent, **kwargs)


class BlockingSimulation(DummySimulation):
    def __init__(self, *args, **kwargs):
        self.cleanupEvent = kwargs.pop("cleanupEvent", None)
        assert self.cleanupEvent is not None
        super().__init__(*args, **kwargs)

    def destroy(self):
        self.cleanupEvent.set()
        return super().destroy()


def test_simulator_group_cleanup():
    scenario = compileScenic("ego = new Object")
    scenes, _ = scenario.generateBatch(10, serialized=True)

    class TestException(Exception):
        pass

    cleanupEvent = multiprocessing.Event()

    sim_group = SimulatorGroup(
        numWorkers=1,
        simulatorClass=BlockingSimulator,
        simulatorParams={"cleanupEvent": cleanupEvent},
    )

    with pytest.raises(TestException):
        resultStream = sim_group.simulateStream(
            scenario, scenes, simulateParams={"maxSteps": 10}
        )
        next(resultStream)
        raise TestException

    assert cleanupEvent.is_set()


def test_simulator_createObjectInSimulator_error_cleanup():
    destroy_called = False

    class TestException(Exception):
        pass

    class TestSimulator(DummySimulator):
        def createSimulation(self, scene, **kwargs):
            return TestSimulation(scene, drift=self.drift, **kwargs)

    class TestSimulation(DummySimulation):
        def createObjectInSimulator(self, obj):
            raise TestException()

        def destroy(self):
            nonlocal destroy_called
            destroy_called = True

    simulator = TestSimulator()
    checkVeneerIsInactive()
    with pytest.raises(TestException):
        sampleResult(compileScenic("ego = new Object"), simulator=simulator)
    checkVeneerIsInactive()

    assert destroy_called


def test_simulator_step_error_cleanup():
    destroy_called = False

    class TestException(Exception):
        pass

    class TestSimulator(DummySimulator):
        def createSimulation(self, scene, **kwargs):
            return TestSimulation(scene, drift=self.drift, **kwargs)

    class TestSimulation(DummySimulation):
        def step(self):
            raise TestException()

        def destroy(self):
            nonlocal destroy_called
            destroy_called = True

    simulator = TestSimulator()
    checkVeneerIsInactive()
    with pytest.raises(TestException):
        sampleResult(compileScenic("ego = new Object"), simulator=simulator)
    checkVeneerIsInactive()

    assert destroy_called


def test_simulator_rejection_cleanup():
    destroy_called = False

    class TestException(Exception):
        pass

    class TestSimulator(DummySimulator):
        def createSimulation(self, scene, **kwargs):
            return TestSimulation(scene, drift=self.drift, **kwargs)

    class TestSimulation(DummySimulation):
        def destroy(self):
            nonlocal destroy_called
            destroy_called = True

    simulator = TestSimulator()
    checkVeneerIsInactive()
    with pytest.raises(RejectSimulationException):
        sampleResult(
            compileScenic(
                """
                ego = new Object
                monitor Foo():
                    require False
                    wait
                require monitor Foo()
            """
            ),
            simulator=simulator,
        )
    checkVeneerIsInactive()

    assert destroy_called
