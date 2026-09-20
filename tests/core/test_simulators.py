import pytest

from scenic.core.object_types import Object
from scenic.core.simulators import DummySimulation, DummySimulator, Simulation
from scenic.core.specifiers import PropertyDefault
from scenic.core.vectors import Orientation
from tests.utils import (
    OrientationSimulation,
    OrientationSimulator,
    compileScenic,
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


# Simulators providing orientation directly


def test_provides_orientation():
    scene = sampleSceneFrom(
        """
        ego = new Object
        record ego.orientation as orientation
        record ego.yaw as yaw
        record ego.pitch as pitch
        record ego.roll as roll
        record ego.heading as heading
        """
    )
    result = OrientationSimulator(spin=0.1).simulate(scene, maxSteps=2)
    for step in range(3):
        expected = Orientation._fromEuler(0.1 * step, 0.2, 0.3)
        assert result.records["orientation"][step][1] == expected
        assert result.records["yaw"][step][1] == pytest.approx(0.1 * step)
        assert result.records["pitch"][step][1] == pytest.approx(0.2)
        assert result.records["roll"][step][1] == pytest.approx(0.3)
        assert result.records["heading"][step][1] == pytest.approx(0.1 * step)


def test_provides_orientation_local():
    """Euler angles are derived in the frame of the parent orientation."""
    scene = sampleSceneFrom(
        """
        ego = new Object with parentOrientation (0, 0.2, 0.3)
        record ego.yaw as yaw
        record ego.pitch as pitch
        record ego.roll as roll
        record ego.orientation as orientation
        """
    )
    result = OrientationSimulator().simulate(scene, maxSteps=1)
    # The simulator reports the same orientation as the parent orientation, so the
    # local angles are all zero.
    assert result.records["orientation"][1][1] == Orientation._fromEuler(0, 0.2, 0.3)
    for prop in ("yaw", "pitch", "roll"):
        assert result.records[prop][1][1] == pytest.approx(0, abs=1e-12)


def test_derived_properties_are_lazy():
    """Derived properties are recomputed only when actually used."""
    present = []

    class LazySimulation(OrientationSimulation):
        def updateObjects(self):
            super().updateObjects()
            obj = self.objects[0]
            present.append({prop for prop in props if prop in obj.__dict__})

    class LazySimulator(DummySimulator):
        def createSimulation(self, scene, **kwargs):
            return LazySimulation(scene, **kwargs)

    props = ("orientation", "yaw", "pitch", "roll")
    scene = sampleSceneFrom("ego = new Object")
    LazySimulator().simulate(scene, maxSteps=2)
    # `orientation` is provided by the simulator, while nothing reads the Euler
    # angles, so they should never be recomputed.
    assert present == [{"orientation"}] * 3


def test_cyclic_derivation():
    """Deriving a property from itself is an error, not an infinite recursion."""
    obj = Object._with()
    # Simulate an interface providing neither `orientation` nor the Euler angles,
    # which are derived from each other.
    obj._invalidateDerivedProperties(givenOrientation=True)
    obj._invalidateDerivedProperties(givenOrientation=False)
    with pytest.raises(RuntimeError) as e:
        obj.yaw
    assert "cyclic derivation" in str(e.value)


def test_failed_derivation():
    """A failed derivation can be retried, rather than looking like a cycle."""
    fail = False

    def recompute(self):
        if fail:
            raise ValueError("no value available")
        return 42

    class TestObj(Object):
        _scenic_properties = {"foo": PropertyDefault((), {"dynamic", "final"}, recompute)}

    obj = TestObj._with()
    fail = True
    obj._invalidateDerivedProperties()
    with pytest.raises(ValueError):
        obj.foo
    fail = False
    assert obj.foo == 42


def test_unknown_property():
    """Deriving properties on demand must not change the error for unknown ones."""
    obj = Object._with()
    with pytest.raises(AttributeError) as e:
        obj.notAProperty
    assert "'Object' object has no attribute 'notAProperty'" in str(e.value)
