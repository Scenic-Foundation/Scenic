"""Tests for modular scenarios."""

import inspect
import signal

import pytest

import scenic.core.dynamics as dynamics
from scenic.core.dynamics import InvariantViolation, PreconditionViolation
from scenic.core.errors import InvalidScenarioError, ScenicSyntaxError, SpecifierError
from scenic.core.simulators import DummySimulator, TerminationType
from tests.utils import (
    compileScenic,
    sampleActionsFromScene,
    sampleEgo,
    sampleEgoActions,
    sampleEgoFrom,
    sampleParamPFrom,
    sampleResult,
    sampleResultOnce,
    sampleScene,
    sampleSceneFrom,
    sampleTrajectory,
)

# Basics


def test_single_scenario():
    ego = sampleEgoFrom(
        """
        scenario Blob():
            setup:
                ego = new Object at (1, 2, 3)
        """
    )
    assert tuple(ego.position) == (1, 2, 3)


def test_simple_scenario():
    ego = sampleEgoFrom(
        """
        scenario Main():
            behavior Foo():
                wait
            ego = new Object at (1, 2, 3), with behavior Foo
        """
    )
    assert tuple(ego.position) == (1, 2, 3)


def test_main_scenario():
    scene = sampleSceneFrom(
        """
        scenario Other():
            ego = new Object at (10, 5)
        scenario Main():
            ego = new Object at (1, 2)
        """
    )
    assert len(scene.objects) == 1
    assert tuple(scene.egoObject.position) == (1, 2, 0)


def test_requirement():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object with width Range(1, 3)
                require ego.width > 2
        """
    )
    ws = [sampleEgo(scenario, maxIterations=60).width for i in range(60)]
    assert all(2 < w <= 3 for w in ws)


def test_requirement_local_main():
    scenario = compileScenic(
        """
        scenario Main():
            ego = new Object
            other = new Object at (10, Range(1, 2))
            require other.position.y > 1.5
            other = 42  # should not affect requirement above
        """
    )
    ys = [sampleScene(scenario, maxIterations=60).objects[1].y for i in range(60)]
    assert all(1.5 < y <= 2 for y in ys)


def test_requirement_local_sub():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()

        scenario Sub():
            ego = new Object
            other = new Object at (10, Range(1, 2))
            require other.position.y > 1.5
            other = 42  # should not affect requirement above
        """
    )
    ys = [sampleTrajectory(scenario, maxIterations=60)[0][1][1] for i in range(60)]
    assert all(1.5 < y <= 2 for y in ys)


def test_soft_requirement():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object with width Range(1, 3)
                require[0.9] ego.width >= 2
        """
    )
    ws = [sampleEgo(scenario, maxIterations=60).width for i in range(350)]
    count = sum(w >= 2 for w in ws)
    assert 255 <= count < 350


def test_param():
    p = sampleParamPFrom(
        """
        scenario Main():
            setup:
                param p = Range(3, 5)
        """
    )
    assert 3 <= p <= 5


def test_param_top_level():
    scenario = compileScenic(
        """
        param bar = 1

        class Foo:
            fizz: globalParameters.bar + Range(0,1)

        scenario Main():
            setup:
                ego = new Foo
        """
    )
    ego = sampleEgo(scenario)
    assert 1 <= ego.fizz <= 2


def test_ego_top_level():
    scenario = compileScenic(
        """
        ego = new Object with foo 42

        scenario Main():
            setup:
                assert ego.foo == 42
            compose:
                assert ego.foo == 42
                do Sub()

        scenario Sub():
            assert ego.foo == 42
        """
    )
    sampleResult(scenario, maxSteps=1)


def test_workspace_top_level():
    scenario = compileScenic(
        """
        workspace = Workspace(CircularRegion(0@0, 2))

        scenario Main():
            setup:
                assert workspace.region.radius == 2
                ego = new Object
            compose:
                assert workspace.region.radius == 2
                do Sub()

        scenario Sub():
            assert workspace.region.radius == 2
        """
    )
    sampleResult(scenario, maxSteps=1)


def test_dynamic_object_creation():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                wait
                do Sub()

        scenario Sub():
            new Object with behavior Foo()

        behavior Foo():
            take 42
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2)
    assert tuple(actions) == (None, 42)


def test_object_creation_in_compose():
    with pytest.raises(InvalidScenarioError):
        scenario = compileScenic(
            """
            scenario Main():
                compose:
                    wait
                    new Object
            """
        )
        sampleResultOnce(scenario)


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="need SIGALRM")
@pytest.mark.slow
def test_scenario_stuck(monkeypatch):
    scenario = compileScenic(
        """
        import time
        scenario Main():
            compose:
                time.sleep(1.5)
                wait
        """
    )
    monkeypatch.setattr(dynamics, "stuckBehaviorWarningTimeout", 1)
    with pytest.warns(dynamics.StuckBehaviorWarning):
        sampleResultOnce(scenario)


def test_invalid_scenario_name():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario 101():
                ego = new Object
            """
        )


def test_scenario_inside_behavior():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                scenario Bar():
                    new Object at 10@10
            ego = new Object
            """
        )


# Termination


def test_time_limit():
    scenario = compileScenic(
        """
        scenario Main():
            ego = new Object
        """
    )
    result = sampleResult(scenario, maxSteps=3)
    assert len(result.trajectory) == 4
    assert result.terminationType == TerminationType.timeLimit


def test_terminate_when():
    scenario = compileScenic(
        """
        scenario Main():
            ego = new Object
            terminate when simulation().currentTime > 1
        """
    )
    result = sampleResult(scenario, maxSteps=5)
    assert len(result.trajectory) == 3
    assert result.terminationType == TerminationType.scenarioComplete


def test_terminate_after():
    scenario = compileScenic(
        """
        scenario Main():
            ego = new Object
            terminate after 2 steps
        """
    )
    result = sampleResult(scenario, maxSteps=5)
    assert len(result.trajectory) == 3
    assert result.terminationType == TerminationType.scenarioComplete


def test_terminate_in_behavior():
    scenario = compileScenic(
        """
        scenario Main():
            behavior Foo():
                wait
                terminate
            ego = new Object with behavior Foo
        """
    )
    result = sampleResult(scenario, maxSteps=5)
    assert len(result.trajectory) == 2
    assert result.terminationType == TerminationType.terminatedByBehavior


# Preconditions and invariants


def test_top_level_precondition():
    scenario = compileScenic(
        """
        scenario Main():
            precondition: simulation().currentTime > 0
            setup:
                ego = new Object
        """
    )
    sim = DummySimulator()
    scene = sampleScene(scenario)
    with pytest.raises(PreconditionViolation):
        sim.simulate(scene, maxSteps=1, raiseGuardViolations=True, verbosity=2)


def test_top_level_invariant():
    scenario = compileScenic(
        """
        scenario Main():
            invariant: simulation().currentTime > 0
            setup:
                ego = new Object
        """
    )
    sim = DummySimulator()
    scene = sampleScene(scenario)
    with pytest.raises(InvariantViolation):
        sim.simulate(scene, maxSteps=1, raiseGuardViolations=True)


def test_malformed_precondition():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                precondition hello: True
                setup:
                    ego = new Object
            """
        )


def test_malformed_invariant():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                invariant hello: True
                setup:
                    ego = new Object
            """
        )


# Composition


def test_parallel_composition():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub(1), Sub(5)
        scenario Sub(x):
            ego = new Object at (x, 1, 2)
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 2
    assert tuple(trajectory[1][0]) == (1, 1, 2)
    assert tuple(trajectory[1][1]) == (5, 1, 2)


def test_sequential_composition():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub(1)
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 1 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 3
    assert len(trajectory[0]) == 1
    assert len(trajectory[1]) == 2
    assert len(trajectory[2]) == 2
    assert tuple(trajectory[0][0]) == (1, 0, 0)
    for i in range(1, 3):
        assert tuple(trajectory[i][0]) == (1, 0, 0)
        assert tuple(trajectory[i][1]) == (5, 0, 0)


def test_subscenario_for_steps():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub(1) for 2 steps
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 3 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 4
    assert len(trajectory[0]) == len(trajectory[1]) == 1
    assert len(trajectory[2]) == len(trajectory[3]) == 2
    for i in range(3):
        assert tuple(trajectory[i][0]) == (1, 0, 0)
    for i in range(2, 4):
        assert tuple(trajectory[i][1]) == (5, 0, 0)


def test_subscenario_for_time():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub(1) for 1 seconds
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 3 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3, timestep=0.5)
    assert len(trajectory) == 4
    assert len(trajectory[0]) == len(trajectory[1]) == 1
    assert len(trajectory[2]) == 2
    for i in range(3):
        assert tuple(trajectory[i][0]) == (1, 0, 0)
    assert tuple(trajectory[2][1]) == (5, 0, 0)


def test_subscenario_until():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub(1) until simulation().currentTime == 2
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 3 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 4
    assert len(trajectory[0]) == len(trajectory[1]) == 1
    assert len(trajectory[2]) == 2
    for i in range(3):
        assert tuple(trajectory[i][0]) == (1, 0, 0)
    assert tuple(trajectory[3][1]) == (5, 0, 0)


def test_subscenario_wait_for_steps():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                wait for 2 steps
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 3 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 4
    assert len(trajectory[0]) == len(trajectory[1]) == 0
    assert len(trajectory[2]) == len(trajectory[3]) == 1
    for i in range(2, 4):
        assert tuple(trajectory[i][0]) == (5, 0, 0)


def test_subscenario_wait_for_time():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                wait for 1 seconds
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 3 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3, timestep=0.5)
    assert len(trajectory) == 4
    assert len(trajectory[0]) == len(trajectory[1]) == 0
    assert len(trajectory[2]) == len(trajectory[3]) == 1
    for i in range(2, 4):
        assert tuple(trajectory[i][0]) == (5, 0, 0)


def test_subscenario_wait_until():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                wait until simulation().currentTime == 2
                do Sub(5)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 3 steps
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 4
    assert len(trajectory[0]) == len(trajectory[1]) == 0
    assert len(trajectory[2]) == len(trajectory[3]) == 1
    for i in range(2, 4):
        assert tuple(trajectory[i][0]) == (5, 0, 0)


def test_subscenario_require_eventually():
    """Test that 'require eventually' must be satisfied before the scenario ends.

    Sub() will end at time step 1, while Main() continues to time step 2.
    The 'require eventually' in Sub() needs to be satisfied no later than time
    step 1, but it won't be, so the simulation should be rejected. If the requirement
    is wrongly checked over the whole scenario (rather than just during Sub),
    then it will evaluate to true and the assertion will fail.
    """
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
                wait
        scenario Sub():
            ego = new Object
            require eventually simulation().currentTime == 2
            terminate after 1 steps
        """
    )
    result = sampleResultOnce(scenario, maxSteps=2)
    assert result is None


def test_subscenario_require_eventually_2():
    """Variant of the above test using `terminate when` instead of `terminate after`."""
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
                wait
        scenario Sub():
            ego = new Object
            require eventually simulation().currentTime == 2
            terminate when simulation().currentTime == 1
        """
    )
    result = sampleResultOnce(scenario, maxSteps=2)
    assert result is None


def test_subscenario_require_monitor():
    """Test that monitors invoked in subscenarios terminate with the subscenario."""
    scenario = compileScenic(
        """
        monitor TimeLimit():
            while True:
                require simulation().currentTime <= 2
                wait
        scenario Main():
            compose:
                do Sub()
                wait
        scenario Sub():
            ego = new Object
            require monitor TimeLimit()
            terminate after 2 steps
        """
    )
    result = sampleResultOnce(scenario, maxSteps=3)
    assert result is not None
    assert len(result.trajectory) == 4


def test_subscenario_record():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                record initial simulation().currentTime as mainInitial
                record final simulation().currentTime as mainFinal
                record simulation().currentTime as mainTime
            compose:
                wait for 2 steps
                do Sub()
                wait
        scenario Sub():
            ego = new Object
            record initial -simulation().currentTime as subInitial
            record final -simulation().currentTime as subFinal
            record -simulation().currentTime as subNegTime
            terminate after 2 steps
        """
    )
    result = sampleResult(scenario, maxSteps=5)
    records = result.records
    assert records["mainInitial"] == 0
    assert records["mainFinal"] == 5
    assert tuple(records["mainTime"]) == ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5))
    assert records["subInitial"] == -2
    assert records["subFinal"] == -4
    assert tuple(records["subNegTime"]) == ((2, -2), (3, -3), (4, -4))


def test_subscenario_terminate_when():
    """Test that 'terminate when' is properly handled.

    In particular, this catches a bug where `terminate when` in a subscenario was
    interpreted as defining a requirement instead of a termination condition.
    """
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
                wait
        scenario Sub():
            ego = new Object
            terminate when simulation().currentTime == 1
        """
    )
    result = sampleResultOnce(scenario, maxSteps=3)
    assert result is not None
    assert len(result.trajectory) == 3


def test_subscenario_terminate_with_parent():
    """Test that subscenarios terminate when their parent does."""
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
                assert False  # should never get here
        scenario Sub():
            setup:
                ego = new Object
                terminate after 1 steps
            compose:
                do Bottom()
        scenario Bottom():
            require eventually simulation().currentTime == 2
        """
    )
    result = sampleResultOnce(scenario, maxSteps=2)
    assert result is None


def test_subscenario_terminate_behavior():
    """Test that 'terminate' in a behavior only terminates the parent scenario."""
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
                wait
        scenario Sub():
            behavior Foo():
                take 1
                terminate
            ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2)
    assert tuple(actions) == (1, None)


def test_subscenario_terminate_compose():
    """Test that 'terminate' in a compose block only terminates that scenario."""
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
                wait
        scenario Sub():
            compose:
                do Bottom(0)
                terminate
                do Bottom(10)
        scenario Bottom(x):
            ego = new Object at (x, 0)
            terminate after 1 steps
        """
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 3
    assert len(trajectory[2]) == 1


def test_subscenario_global_param():
    scenario = compileScenic(
        """
        param foo = 10

        scenario Main():
            setup:
                param bar = 20

            compose:
                do Sub1() for 1 steps
                do Sub2() for 1 steps

        scenario Sub1():
            new Object at (globalParameters.foo, 0)

        scenario Sub2():
            new Object at (globalParameters.bar, 0)
        """
    )
    trajectory = sampleTrajectory(scenario, maxSteps=3)
    assert len(trajectory) == 3
    assert len(trajectory[0]) == 1
    assert trajectory[0][0][0] == 10
    assert len(trajectory[1]) == 2
    assert trajectory[1][1][0] == 20


def test_initial_scenario_basic():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub()
        scenario Sub():
            setup:
                if initial scenario:
                    ego = new Object
                new Object left of ego by 5
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 2


def test_initial_scenario_setup():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object
            compose:
                do Sub()
        scenario Sub():
            setup:
                if initial scenario:
                    ego = new Object
                new Object left of ego by 5
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 2


def test_initial_scenario_parallel():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do Sub(2), Sub(5)
        scenario Sub(x):
            setup:
                if initial scenario:
                    ego = new Object
                new Object left of ego by x
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 3


def test_choose_1():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do choose Sub(-1), Sub(3)
        scenario Sub(x):
            precondition: simulation().currentTime >= x
            setup:
                ego = new Object at x @ 0
        """,
        scenario="Main",
    )
    xs = [sampleTrajectory(scenario, maxSteps=1)[1][0][0] for i in range(30)]
    assert all(x == -1 for x in xs)


def test_choose_2():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do choose Sub(-1), Sub(-2), Sub(5)
        scenario Sub(x):
            precondition: simulation().currentTime >= x
            setup:
                ego = new Object at x @ 0
        """,
        scenario="Main",
    )
    xs = [sampleTrajectory(scenario, maxSteps=1)[1][0][0] for i in range(30)]
    assert all(x == -1 or x == -2 for x in xs)
    assert any(x == -1 for x in xs)
    assert any(x == -2 for x in xs)


def test_choose_3():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do choose {Sub(0): 1, Sub(1): 9}
        scenario Sub(x):
            setup:
                ego = new Object at x @ 0
        """,
        scenario="Main",
    )
    xs = [sampleTrajectory(scenario, maxSteps=1)[1][0][0] for i in range(200)]
    assert all(x == 0 or x == 1 for x in xs)
    assert 145 <= sum(xs) < 200


def test_choose_deadlock():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do choose Sub(6), Sub(2)
        scenario Sub(x):
            precondition: simulation().currentTime >= x
            setup:
                ego = new Object at x @ 0
        """,
        scenario="Main",
    )
    result = sampleResultOnce(scenario)
    assert result is None


def test_shuffle_1():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do shuffle Sub(-1), Sub(1)
        scenario Sub(x):
            precondition: simulation().currentTime >= x
            setup:
                ego = new Object at x @ 0
                terminate after 1 steps
        """,
        scenario="Main",
    )
    for i in range(30):
        trajectory = sampleTrajectory(scenario, maxSteps=3)
        assert len(trajectory) == 3
        assert len(trajectory[0]) == 1
        assert len(trajectory[1]) == 2
        assert trajectory[0][0] == (-1, 0, 0)
        assert trajectory[1][1] == (1, 0, 0)


def test_shuffle_2():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do shuffle Sub(1), Sub(3)
        scenario Sub(x):
            ego = new Object at x @ 0
            terminate after 1 steps
        """,
        scenario="Main",
    )
    x1s = []
    for i in range(30):
        trajectory = sampleTrajectory(scenario, maxSteps=3)
        assert len(trajectory) == 3
        assert len(trajectory[0]) == 1
        assert len(trajectory[1]) == 2
        x1 = trajectory[0][0].x
        x2 = trajectory[1][1].x
        assert x1 == 1 or x1 == 3
        assert x2 == 1 or x2 == 3
        assert x1 != x2
        x1s.append(x1)
    assert any(x1 == 1 for x1 in x1s)
    assert any(x1 == 3 for x1 in x1s)


def test_shuffle_3():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do shuffle {Sub(0): 1, Sub(1): 9}
        scenario Sub(x):
            setup:
                ego = new Object at x @ 0
                terminate after 1 steps
        """,
        scenario="Main",
    )
    xs = [sampleTrajectory(scenario, maxSteps=3)[2][0][0] for i in range(200)]
    assert all(x == 0 or x == 1 for x in xs)
    assert 145 <= sum(xs) < 200


def test_shuffle_deadlock():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                do shuffle Sub(-1), Sub(2)
        scenario Sub(x):
            precondition: simulation().currentTime >= x
            setup:
                ego = new Object at x @ 0
                terminate after 1 steps
        """,
        scenario="Main",
    )
    result = sampleResultOnce(scenario, maxSteps=2)
    assert result is None


def test_compose_no_invocations():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object
            compose:
                pass
        """
    )
    with pytest.raises(InvalidScenarioError):
        sampleResult(scenario)


def test_compose_illegal_statement():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                compose:
                    model scenic.domains.driving.model
            """
        )


def test_compose_illegal_yield():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                compose:
                    yield 5
            """
        )
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                compose:
                    yield from []
            """
        )


def test_compose_illegal_action():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                compose:
                    take 1
            """
        )


def test_compose_nested_definition():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                compose:
                    scenario Foo():
                        new Object at 10@10
            """
        )
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                compose:
                    behavior Foo():
                        wait
            """
        )


# Overrides


def test_override_basic():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object with foo 1, with behavior Bar
            compose:
                wait
                do Sub()
                wait
        scenario Sub():
            setup:
                override ego with foo 2
                terminate after 1 steps
        behavior Bar():
            while True:
                take self.foo
        """,
        scenario="Main",
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (1, 2, 1)


def test_override_behavior():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object with behavior Foo
            compose:
                wait
                do Sub() for 2 steps
                wait
        scenario Sub():
            setup:
                override ego with behavior Bar
        behavior Foo():
            x = 1
            while True:
                take x
                x += 1
        behavior Bar():
            x = -1
            while True:
                take x
                x -= 1
        """,
        scenario="Main",
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, -1, -2, 2)


def test_override_none_behavior():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object
            compose:
                wait
                do Sub() for 2 steps
                wait
        scenario Sub():
            setup:
                override ego with behavior Bar
        behavior Bar():
            x = -1
            while True:
                take x
                x -= 1
        """,
        scenario="Main",
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (None, -1, -2, None)


def test_override_leakage():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object with prop 1
            compose:
                do Sub1()
        scenario Sub1():
            setup:
                override ego with prop 2, with behavior Bar
        behavior Bar():
            terminate
        """,
        scenario="Main",
    )
    scene = sampleScene(scenario)
    assert scene.objects[0].prop == 1
    sampleActionsFromScene(scene)
    assert scene.objects[0].prop == 1

    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object with prop 1
            compose:
                do Sub1()
        scenario Sub1():
            setup:
                override ego with prop 2, with behavior Bar
        behavior Bar():
            raise NotImplementedError()
            wait
        """,
        scenario="Main",
    )
    scene = sampleScene(scenario)
    assert scene.objects[0].prop == 1
    with pytest.raises(NotImplementedError):
        sampleActionsFromScene(scene)
    assert scene.objects[0].prop == 1


def test_override_dynamic():
    with pytest.raises(SpecifierError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                    override ego with position 5@5
            """
        )


def test_override_nonexistent():
    with pytest.raises(SpecifierError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                    override ego with blob 'hello!'
            """
        )


def test_override_non_object():
    with pytest.raises(TypeError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                    override True with blob 'hello!'
            """
        )


def test_override_malformed():
    with pytest.raises(TypeError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                    override 101 with blob 'hello!'
            """
        )


def test_override_no_specifiers():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            scenario Main():
                setup:
                    ego = new Object
                    override ego
            """
        )


# Scoping


def test_shared_scope_read():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                y = 3
            compose:
                do Sub(y)
        scenario Sub(x):
            ego = new Object at (x, 1, 2)
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 1
    assert tuple(trajectory[1][0]) == (3, 1, 2)


def test_shared_scope_write():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                y = 3
            compose:
                y = 4
                do Sub(y)
        scenario Sub(x):
            ego = new Object at (x, 1, 2)
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 1
    assert tuple(trajectory[1][0]) == (4, 1, 2)


def test_shared_scope_del():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                y = 3
            compose:
                del y
                do Sub()
        scenario Sub():
            ego = new Object
        """,
        scenario="Main",
    )
    sampleTrajectory(scenario)


def test_delayed_local_argument():
    scenario = compileScenic(
        """
        scenario Foo(obj, y):
            ego = new Object left of obj by (5, y)
        scenario Bar():
            setup:
                ego = new Object
                y = 12
        scenario Main():
            compose:
                s1 = Bar()
                s2 = Foo(s1.ego, s1.y)
                do s1, s2
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario)
    assert len(trajectory) == 2
    assert len(trajectory[1]) == 2
    assert tuple(trajectory[1][0]) == (0, 0, 0)
    assert tuple(trajectory[1][1]) == pytest.approx((-6, 12, 0))


def test_delayed_local_interrupt():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                sc = Sub()
                try:
                    do sc
                interrupt when sc.ego.position.x >= 1:
                    abort
        scenario Sub():
            ego = new Object at (1, 0)
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=2)
    assert len(trajectory) == 2
    assert len(trajectory[0]) == len(trajectory[1]) == 1


def test_delayed_local_until():
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                sc = Sub()
                do sc until sc.ego.position.x >= 1
        scenario Sub():
            ego = new Object at (1, 0)
        """,
        scenario="Main",
    )
    trajectory = sampleTrajectory(scenario, maxSteps=2)
    assert len(trajectory) == 2
    assert len(trajectory[0]) == len(trajectory[1]) == 1


def test_independent_requirements():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                wait
                self.position += DiscreteRange(0, 1) @ 0
        scenario Main():
            compose:
                do Sub(0, 1), Sub(2, 3)
        scenario Sub(start, dest):
            ego = new Object at start @ 0, with behavior Foo
            require eventually ego.position.x >= dest
        """,
        scenario="Main",
    )
    for i in range(30):
        trajectory = sampleTrajectory(scenario, maxSteps=2, maxIterations=100)
        assert tuple(trajectory[2][0]) == (1, 0, 0)
        assert tuple(trajectory[2][1]) == (3, 0, 0)


# Introspection


@pytest.mark.parametrize(
    "body",
    (
        """pass""",
        """setup:
                pass""",
        """compose:
                pass""",
    ),
)
def test_scenario_signature(body):
    ego = sampleEgoFrom(
        f"""
        scenario Blah(foo, *bar, baz=12, **qux):
            {body}
        ego = new Object with thing Blah
        """
    )
    sig = inspect.signature(ego.thing)
    params = tuple(sig.parameters.items())
    assert len(params) == 4
    (name1, p1), (name2, p2), (name3, p3), (name4, p4) = params
    assert name1 == "foo"
    assert p1.default is inspect.Parameter.empty
    assert p1.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert name2 == "bar"
    assert p2.default is inspect.Parameter.empty
    assert p2.kind is inspect.Parameter.VAR_POSITIONAL
    assert name3 == "baz"
    assert p3.default == 12
    assert p3.kind is inspect.Parameter.KEYWORD_ONLY
    assert name4 == "qux"
    assert p4.default is inspect.Parameter.empty
    assert p4.kind is inspect.Parameter.VAR_KEYWORD


# lastActions Property
def test_lastActions_modular():
    scenario = compileScenic(
        """
        scenario Main():
            setup:
                ego = new Object
                record ego.lastActions as lastActions
            compose:
                do Sub1() for 2 steps
                do Sub2() for 2 steps
                do Sub1() for 2 steps
                wait
        scenario Sub1():
            setup:
                override ego with behavior Bar
        scenario Sub2():
            setup:
                override ego with behavior None
        behavior Bar():
            x = -1
            while True:
                take x
                x -= 1
        """,
        scenario="Main",
    )
    result = sampleResult(scenario, maxSteps=6)
    assert tuple(result.records["lastActions"]) == (
        (0, tuple()),
        (1, (-1,)),
        (2, (-2,)),
        (3, tuple()),
        (4, tuple()),
        (5, (-1,)),
        (6, (-2,)),
    )


# Modular scenario global state
def test_mode2D_modular():
    scenario = compileScenic(
        """
        poly = CircularRegion(0@0, 10)

        class Foo:
            position: new Point in poly
            regionContainedIn: poly

        scenario Main():
            setup:
                ego = new Object
                new Foo visible
                require ego.baseOffset == (0,0,0)
            compose:
                do Sub() for 2 steps

        scenario Sub():
            setup:
                foo = new Object
                require foo.baseOffset == (0,0,0)

        """,
        mode2D=True,
    )
    sampleResult(scenario, maxSteps=2, maxIterations=100)
