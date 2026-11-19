import inspect
import signal
import sys

import pytest

import scenic.core.dynamics as dynamics
from scenic.core.errors import InvalidScenarioError, ScenicSyntaxError
from scenic.core.simulators import RejectSimulationException, TerminationType
from tests.utils import (
    checkErrorLineNumber,
    compileScenic,
    sampleActions,
    sampleActionsFromScene,
    sampleEgoActions,
    sampleEgoActionsFromScene,
    sampleEgoFrom,
    sampleResult,
    sampleResultFromScene,
    sampleResultOnce,
    sampleScene,
)

## Dynamic state


def test_dynamic_property():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.position = self.position + 1@0
                wait
        ego = new Object with behavior Foo
        terminate when ego.position.x >= 3
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert len(actions) == 3


def test_dynamic_final_property():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.yaw = self.yaw + 0.1
                wait
        ego = new Object with behavior Foo
        terminate when ego.heading >= 0.25
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert len(actions) == 3


def test_dynamic_cached_property():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.position = self.position + 0@1
                wait
        ego = new Object with behavior Foo
        terminate when ego.left.position.y >= 3
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert len(actions) == 3


def test_dynamic_cached_method():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.position = self.position + 0@1
                wait
        ego = new Object with behavior Foo
        terminate when ego.distanceTo(0@4) < 1
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert len(actions) == 3


## Simulation properties


def test_current_time():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take simulation().currentTime
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (0, 1, 2)


def test_no_simulation():
    with pytest.raises(InvalidScenarioError):
        compileScenic("ego = new Object with foo simulation()")


## Behaviors

# Basic


def test_behavior_actions():
    scenario = compileScenic(
        """
        behavior Foo():
            take 3
            take 5
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2)
    assert tuple(actions) == (3, 5)


def test_behavior_multiple_actions():
    scenario = compileScenic(
        """
        behavior Foo():
            take 1, 4, 9
            take 5
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2, singleAction=False)
    assert tuple(actions) == ((1, 4, 9), (5,))


def test_behavior_tuple_actions():
    scenario = compileScenic(
        """
        behavior Foo():
            take (1, 4, 9)
            take 5
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2, singleAction=False)
    assert tuple(actions) == ((1, 4, 9), (5,))


def test_behavior_list_actions():
    scenario = compileScenic(
        """
        behavior Foo():
            take [1, 4, 9]
            take 5
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2, singleAction=False)
    assert tuple(actions) == ((1, 4, 9), (5,))


def test_behavior_take_none():
    scenario = compileScenic(
        """
        behavior Foo():
            take None
            take 7
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2)
    assert tuple(actions) == (None, 7)


def test_behavior_take_empty_tuple():
    scenario = compileScenic(
        """
        behavior Foo():
            take ()
            take 7
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2)
    assert tuple(actions) == (None, 7)


# Various errors


def test_invalid_behavior_name():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior 101():
                wait
            ego = new Object
            """
        )


def test_behavior_no_actions():
    with pytest.raises(InvalidScenarioError):
        compileScenic(
            """
            behavior Foo():
                take 1
            behavior Bar():
                Foo()   # forgot to use 'do'
            ego = new Object with behavior Bar
            """
        )


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="need SIGALRM")
@pytest.mark.slow
def test_behavior_stuck(monkeypatch):
    scenario = compileScenic(
        """
        import time
        behavior Foo():
            time.sleep(1.5)
            wait
        ego = new Object with behavior Foo
        """
    )
    monkeypatch.setattr(dynamics, "stuckBehaviorWarningTimeout", 1)
    with pytest.warns(dynamics.StuckBehaviorWarning):
        sampleResultOnce(scenario)


def test_behavior_create_object():
    with pytest.raises(InvalidScenarioError):
        scenario = compileScenic(
            """
            behavior Bar():
                new Object at 10@10
                wait
            ego = new Object with behavior Bar
            """
        )
        sampleResultOnce(scenario)


def test_behavior_define_param():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Bar():
                param foo = 3
                wait
            ego = new Object with behavior Bar
            """
        )


def test_behavior_illegal_yield():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                yield 1
                wait
            ego = new Object with behavior Foo
            """
        )
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                yield from []
                wait
            ego = new Object with behavior Foo
            """
        )


def test_behavior_nested_defn():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                wait
                behavior Bar():
                    wait
            ego = new Object with behavior Foo
            """
        )


# Arguments


def test_behavior_random_argument():
    scenario = compileScenic(
        "behavior Foo(arg):\n"
        "    take arg\n"
        "ego = new Object with behavior Foo(Range(10, 25))"
    )
    scene = sampleScene(scenario)
    actions1 = sampleEgoActionsFromScene(scene)
    assert 10 <= actions1[0] <= 25
    actions2 = sampleEgoActionsFromScene(scene)
    assert actions1 == actions2
    scene2 = sampleScene(scenario)
    actions3 = sampleEgoActionsFromScene(scene2)
    assert actions1 != actions3


def test_behavior_random_argument_list():
    scenario = compileScenic(
        "behavior Foo(arg):\n"
        "    take arg[1]\n"
        "ego = new Object with behavior Foo([-5, Range(10, 25)])"
    )
    scene = sampleScene(scenario)
    actions1 = sampleEgoActionsFromScene(scene)
    assert 10 <= actions1[0] <= 25
    actions2 = sampleEgoActionsFromScene(scene)
    assert actions1 == actions2
    scene2 = sampleScene(scenario)
    actions3 = sampleEgoActionsFromScene(scene2)
    assert actions1 != actions3


def test_behavior_object_argument():
    scenario = compileScenic(
        """
        behavior Foo(obj):
            while True:
                take obj.flag
        behavior Bar():
            self.flag = 1
            wait
        other = new Object with flag 0, with behavior Bar
        ego = new Object at (10, 0), with behavior Foo(other)
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2)
    assert actions[1] == 1


# Globals


def test_behavior_globals_read():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take other.position.x
        ego = new Object with behavior Foo
        other = new Object at Range(10, 20) @ 15
        """
    )
    actions1 = sampleEgoActions(scenario, maxSteps=2)
    assert len(actions1) == 2
    assert 10 <= actions1[0] <= 20
    assert actions1[0] == actions1[1]
    actions2 = sampleEgoActions(scenario, maxSteps=1)
    assert len(actions2) == 1
    assert actions2[0] != actions1[0]


def test_behavior_globals_read_module(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            import helper4
            behavior Foo():
                while True:
                    take helper4.foo
            ego = new Object with behavior Foo
            """
        )
        actions1 = sampleEgoActions(scenario, maxSteps=2)
        assert len(actions1) == 2
        assert 0 <= actions1[0] <= 1
        assert actions1[0] == actions1[1]
        actions2 = sampleEgoActions(scenario, maxSteps=1)
        assert len(actions2) == 1
        assert actions2[0] != actions1[0]


def test_behavior_globals_read_list():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take foo[1]
        ego = new Object with behavior Foo
        foo = [5, Range(10, 20)]
        """
    )
    actions1 = sampleEgoActions(scenario, maxSteps=2)
    assert len(actions1) == 2
    assert 10 <= actions1[0] <= 20
    assert actions1[0] == actions1[1]
    actions2 = sampleEgoActions(scenario, maxSteps=1)
    assert len(actions2) == 1
    assert actions2[0] != actions1[0]


def test_behavior_globals_write():
    scenario = compileScenic(
        """
        glob = 0
        behavior Foo():
            global glob
            while True:
                take 0
                glob = 2
        behavior Bar():
            while True:
                take (glob < 1)
        other = new Object with behavior Foo
        ego = new Object at 10@10, with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert len(actions) == 3
    assert actions[0] == True
    assert actions[2] == False


def test_behavior_namespace_interference(runLocally):
    """Test that namespaces of behaviors are isolated acrosss compilations.

    This checks a rather nasty bug wherein under certain complex circumstances
    involving circular imports, a reference to a Scenic module in the global
    namespace of a behavior could leak from one compilation to another.
    """
    with runLocally():
        for i in range(2):
            scenario = compileScenic(
                f"""
                import submodule.subsub as sub
                sub.myglobal = {i}
                behavior Foo():
                    take sub.subsub.myglobal
                ego = new Object with behavior Foo
                """
            )
            actions = sampleEgoActions(scenario)
            assert len(actions) == 1
            assert actions[0] == i


# Implicit self


def test_behavior_self():
    scenario = compileScenic(
        """
        behavior Foo():
            take self.bar
        ego = new Object with behavior Foo, with bar 3
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=1)
    assert tuple(actions) == (3,)


def test_behavior_lazy():
    scenario = compileScenic(
        """
        vf = VectorField("Foo", lambda pos: pos.x)
        behavior Foo():
            take (1 relative to vf).yaw
        ego = new Object at 0.5@0, with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=1)
    assert tuple(actions) == (pytest.approx(1.5),)


def test_behavior_lazy_nested():
    scenario = compileScenic(
        """
        vf = VectorField("Foo", lambda pos: pos.x)
        behavior Foo():
            do Bar()
            take (-1 relative to vf).yaw
        behavior Bar():
            take (1 relative to vf).yaw
        behavior Baz():
            do Bar(); do Bar()
        new Object at -1.25@0, with behavior Baz
        ego = new Object at 0.5@0, with behavior Foo
        """
    )
    actions = sampleActions(scenario, maxSteps=2)
    assert tuple(actions) == (pytest.approx((1.5, -0.25)), pytest.approx((-0.5, -0.25)))


def test_obj_equals_self_inside_behavior():
    scenario = compileScenic(
        """
        behavior Foo():
            for obj in simulation().objects:
                take (obj == self, obj is self)

        ego = new Object with behavior Foo
        other = new Object at 10@10
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=2, singleAction=False)
    assert tuple(actions) == ((True, True), (False, False))


# Termination


def test_behavior_end_early():
    scenario = compileScenic(
        """
        behavior Foo():
            take 5
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (5, None, None)


def test_terminate():
    scenario = compileScenic(
        """
        behavior Foo():
            take 1
            terminate
            take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (1,)


def test_terminate_when():
    scenario = compileScenic(
        """
        flag = False
        behavior Foo():
            global flag
            take 1
            flag = True
            take 2
        ego = new Object with behavior Foo
        terminate when flag as termCond
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (1, 2)


# Reuse


def test_behavior_reuse():
    scenario = compileScenic(
        "behavior Foo(arg):\n"
        "    take arg\n"
        "ego = new Object with behavior Foo(3)\n"
        "new Object at 10@10, with behavior Foo(5)"
    )
    actions = sampleActions(scenario)
    assert len(actions) == 1
    assert tuple(actions[0]) == (3, 5)


def test_behavior_reuse_2():
    scenario = compileScenic(
        "behavior Foo():\n"
        "    take Range(-10, 10)\n"
        "ego = new Object with behavior Foo\n"
        "new Object at 10@10, with behavior Foo"
    )
    actions = sampleActions(scenario)
    assert len(actions) == 1
    action1, action2 = actions[0]
    assert action1 != action2


# Ordering


def test_behavior_ordering_default():
    scenario = compileScenic(
        """
        count = 0
        behavior Foo():
            global count
            count += 1
            take count
        new Object with name 'A', with behavior Foo
        new Object with name 'B', at 10@0, with behavior Foo
        ego = new Object with name 'C', at 20@0, with behavior Foo
        """
    )
    scene = sampleScene(scenario)
    objsByName = {}
    for obj in scene.objects:
        objsByName[obj.name] = obj
    actions = sampleActionsFromScene(scene, asMapping=True)
    assert len(actions) == 1
    actions = actions[0]
    assert actions[objsByName["C"]] == 1
    assert actions[objsByName["A"]] == 2
    assert actions[objsByName["B"]] == 3
    assert tuple(actions.keys()) == scene.objects


# Nesting (sub-behaviors)


def test_behavior_nesting():
    scenario = compileScenic(
        """
        behavior Foo(a):
            take a
            take a
        behavior Bar():
            take 1
            do Foo(2)
            take 3
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 2, 2, 3)


def test_subbehavior_for_steps():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take 1
        behavior Bar():
            do Foo() for 3 steps
            take 2
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 1, 1, 2)


def test_subbehavior_for_time():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take 1
        behavior Bar():
            do Foo() for 3 seconds
            take 2
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=7, timestep=0.5)
    assert tuple(actions) == (1, 1, 1, 1, 1, 1, 2)


def test_subbehavior_until():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take 1
        behavior Bar():
            do Foo() until simulation().currentTime == 2
            take 2
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 1, 2, None)


def test_subbehavior_incompatible_modifiers():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                take 5
            behavior Bar():
                do Foo() for 5 steps until False
            ego = new Object with behavior Bar
            """
        )


def test_subbehavior_misplaced_modifier():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                take 5
            behavior Bar():
                do Foo() for 5 steps, Foo()
            ego = new Object with behavior Bar
            """
        )


def test_subbehavior_wait_for_steps():
    scenario = compileScenic(
        """
        behavior Foo():
            wait for 3 steps
            take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (None, None, None, 2)


def test_subbehavior_wait_for_time():
    scenario = compileScenic(
        """
        behavior Foo():
            wait for 3 seconds
            take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=7, timestep=0.5)
    assert tuple(actions) == (None, None, None, None, None, None, 2)


def test_subbehavior_wait_until():
    scenario = compileScenic(
        """
        behavior Foo():
            wait until simulation().currentTime == 2
            take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (None, None, 2, None)


def test_subbehavior_wait_incompatible_modifiers():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                wait for 5 steps until False
            ego = new Object with behavior Foo
            """
        )


def test_behavior_invoke_mistyped():
    scenario = compileScenic(
        """
        behavior Foo():
            do 12
        ego = new Object with behavior Foo
        """
    )
    with pytest.raises(TypeError):
        sampleActions(scenario)


def test_behavior_invoke_multiple():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                take 5
            behavior Bar():
                do Foo(), Foo()
            ego = new Object with behavior Bar
            """
        )


def test_behavior_tuple_invalid():
    scenario = compileScenic(
        """
        behavior Foo():
            take 1
        behavior Bar():
            take 2
        behavior Baz():
            do (Foo(), Bar())
        ego = new Object with behavior Baz
        """
    )
    with pytest.raises(TypeError):
        sampleEgoActions(scenario, maxSteps=1)


def test_behavior_calls():
    """Ordinary function calls inside behaviors should still work."""
    scenario = compileScenic(
        """
        def func(a, *b, c=0, d=1, **e):
            return [a, len(b), c, d, len(e)]
        behavior Foo():
            take [func(4, 5, 6, blah=4, c=10)]
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=1)
    assert tuple(actions) == ([4, 2, 10, 1, 1],)


def test_behavior_calls_nested():
    """Nested function calls inside behaviors should still work."""
    scenario = compileScenic(
        """
        def funcA(x):
            return x+1
        def funcB(x):
            return x*2
        behavior Foo():
            take funcA(funcB(5))
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=1)
    assert tuple(actions) == (11,)


def test_behavior_calls_side_effects():
    scenario = compileScenic(
        """
        x = 0
        def func():
            global x
            x += 1
            return x
        behavior Foo():
            while True:
                take func()
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 2, 3, 4)


# Preconditions and invariants


def test_behavior_precondition():
    scenario = compileScenic(
        """
        behavior Foo():
            precondition: self.position.x > 0
            take self.position.x
        ego = new Object at Range(-1, 1) @ 0, with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=1, maxIterations=1, maxScenes=50)
        assert actions[0] > 0


def test_behavior_invariant():
    scenario = compileScenic(
        """
        behavior Foo():
            invariant: self.position.x > 0
            while True:
                take self.position.x
                self.position -= Range(0, 2) @ 0
        ego = new Object at 1 @ 0, with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=3, maxIterations=50)
        assert actions[1] > 0


def test_precondition_rejection():
    scenario = compileScenic(
        """
        box_region = BoxRegion(position=(0,0,0), dimensions=(1,1,1)).getSurfaceRegion()

        # This behavior should work properly since it has no preconditions/invariants
        behavior BehaviorA():
            take 1

        # This behavior should never execute since the precondition will reject,
        # which should be converted to a PreconditionViolation
        behavior BehaviorB():
            precondition: box_region.orientation[self.position].yaw < float('inf')

            take 2

        behavior MetaBehavior():
            while True:
                try:
                    do BehaviorB()
                except PreconditionViolation:
                    do BehaviorA()

        ego = new Object at (0,0,0), with foo 0, with bar 0,
            with behavior MetaBehavior()
        """
    )
    scene = sampleScene(scenario)
    results = [sampleEgoActions(scenario, maxSteps=1) for _ in range(40)]
    assert all(result == [1] for result in results)


def test_invariant_rejection():
    scenario = compileScenic(
        """
        box_region = BoxRegion(position=(0,0,0), dimensions=(1,1,1)).getSurfaceRegion()

        # This behavior should work properly since it has no preconditions/invariants
        behavior BehaviorA():
            ego.foo += 1
            wait

        # This behavior should never execute since the invariant will reject,
        # which should be converted to a PreconditionViolation
        behavior BehaviorB():
            invariant: box_region.orientation[self.position].yaw < float('inf')

            ego.bar += 1
            wait

        behavior MetaBehavior():
            while True:
                try:
                    do BehaviorB()
                except InvariantViolation:
                    do BehaviorA()

        ego = new Object at (0,0,0), with foo 0, with bar 0,
            with behavior MetaBehavior()

        record final (ego.foo, ego.bar) as test_val
        """
    )
    scene = sampleScene(scenario)
    result = sampleResultFromScene(scene, maxSteps=20)
    assert result is not None
    assert result.records["test_val"] == (20, 0)


def test_precondition_rejection_choose():
    scenario = compileScenic(
        """
        box_region = BoxRegion(position=(0,0,0), dimensions=(1,1,1)).getSurfaceRegion()

        # This behavior should work properly since it has no preconditions/invariants
        behavior BehaviorA():
            ego.foo += 1
            wait

        # This behavior should never execute since the precondition will reject,
        # which should be converted to a PreconditionViolation
        behavior BehaviorB():
            precondition: box_region.orientation[self.position].yaw < float('inf')

            ego.bar += 1
            wait

        behavior MetaBehavior():
            while True:
                do choose BehaviorA(), BehaviorB()

        ego = new Object at (0,0,0), with foo 0, with bar 0,
            with behavior MetaBehavior()

        record final (ego.foo, ego.bar) as test_val
        """
    )
    scene = sampleScene(scenario)
    result = sampleResultFromScene(scene, maxSteps=20)
    assert result is not None
    assert result.records["test_val"] == (20, 0)


def test_invariant_rejection_choose():
    scenario = compileScenic(
        """
        box_region = BoxRegion(position=(0,0,0), dimensions=(1,1,1)).getSurfaceRegion()

        # This behavior should work properly since it has no preconditions/invariants
        behavior BehaviorA():
            ego.foo += 1
            wait

        # This behavior should never execute since the invariant will reject,
        # which should be converted to a PreconditionViolation
        behavior BehaviorB():
            invariant: box_region.orientation[self.position].yaw < float('inf')

            ego.bar += 1
            wait

        behavior MetaBehavior():
            while True:
                do choose BehaviorA(), BehaviorB()

        ego = new Object at (0,0,0), with foo 0, with bar 0,
            with behavior MetaBehavior()

        record final (ego.foo, ego.bar) as test_val
        """
    )
    scene = sampleScene(scenario)
    result = sampleResultFromScene(scene, maxSteps=20)
    assert result is not None
    assert result.records["test_val"] == (20, 0)


def test_precondition_rejection_shuffle():
    scenario = compileScenic(
        """
        box_region = BoxRegion(position=(0,0,0), dimensions=(1,1,1)).getSurfaceRegion()

        # This behavior should work properly since it has no preconditions/invariants
        behavior BehaviorA():
            ego.foo += 1
            wait

        # This behavior should never execute since the precondition will reject,
        # which should be converted to a PreconditionViolation
        behavior BehaviorB():
            precondition: box_region.orientation[self.position].yaw < float('inf')

            ego.bar += 1
            wait

        behavior MetaBehavior():
            while True:
                do shuffle BehaviorA(), BehaviorB()

        ego = new Object at (0,0,0), with foo 0, with bar 0,
            with behavior MetaBehavior()

        record final (ego.foo, ego.bar) as test_val
        """
    )
    for _ in range(20):
        scene = sampleScene(scenario)
        result = sampleResultFromScene(scene, maxSteps=1)
        assert result is not None
        assert result.records["test_val"] == (1, 0)


def test_invariant_rejection_shuffle():
    scenario = compileScenic(
        """
        box_region = BoxRegion(position=(0,0,0), dimensions=(1,1,1)).getSurfaceRegion()

        # This behavior should work properly since it has no preconditions/invariants
        behavior BehaviorA():
            ego.foo += 1
            wait

        # This behavior should never execute since the invariant will reject,
        # which should be converted to a PreconditionViolation
        behavior BehaviorB():
            invariant: box_region.orientation[self.position].yaw < float('inf')

            ego.bar += 1
            wait

        behavior MetaBehavior():
            while True:
                do shuffle BehaviorA(), BehaviorB()

        ego = new Object at (0,0,0), with foo 0, with bar 0,
            with behavior MetaBehavior()

        record final (ego.foo, ego.bar) as test_val
        """
    )
    for _ in range(20):
        scene = sampleScene(scenario)
        result = sampleResultFromScene(scene, maxSteps=1)
        assert result is not None
        assert result.records["test_val"] == (1, 0)


def test_precondition_multiline():
    scenario = compileScenic(
        """
        behavior Foo():
            precondition: (
                self.position.x > 0
                and self.position.y == 0
            )
            take self.position.x
        ego = new Object at Range(-1, 1) @ 0, with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=1, maxIterations=1, maxScenes=50)
        assert actions[0] > 0


def test_invariant_multiline():
    scenario = compileScenic(
        """
        behavior Foo():
            invariant: (
                self.position.x > 0
                and self.position.y == 0
            )
            while True:
                take self.position.x
                self.position -= Range(0, 2) @ 0
        ego = new Object at 1 @ 0, with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=3, maxIterations=50)
        assert actions[1] > 0


# Random selection of sub-behaviors


def test_choose_1():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                do choose Bar(1), Bar(2)
        behavior Bar(x):
            take x
        ego = new Object with behavior Foo
        """
    )
    ts = [sampleEgoActions(scenario, maxSteps=2) for i in range(40)]
    assert any(t[0] == 1 for t in ts)
    assert any(t[0] == 2 for t in ts)
    assert any(t[0] == t[1] for t in ts)
    assert any(t[0] != t[1] for t in ts)


def test_choose_2():
    scenario = compileScenic(
        """
        behavior Foo():
            do choose Bar(1), Bar(2)
            terminate
        behavior Bar(p):
            precondition: self.position.x == p
            take (self.position.x == p)
        ego = new Object at Uniform(1, 2) @ 0, with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=2)
        assert len(actions) == 1
        assert actions[0] == True


def test_choose_3():
    scenario = compileScenic(
        """
        behavior Foo():
            do choose {Sub(0): 1, Sub(1): 9}
        behavior Sub(x):
            take x
        ego = new Object with behavior Foo
        """
    )
    xs = [sampleEgoActions(scenario)[0] for i in range(200)]
    assert all(x == 0 or x == 1 for x in xs)
    assert 145 <= sum(xs) < 200


def test_choose_deadlock():
    scenario = compileScenic(
        """
        behavior Foo():
            do choose Bar(1), Bar(2)
        behavior Bar(p):
            precondition: self.position.x == p
            wait
        ego = new Object at 3 @ 0, with behavior Foo
        """
    )
    result = sampleResultOnce(scenario)
    assert result is None


def test_shuffle_1():
    scenario = compileScenic(
        """
        behavior Foo():
            do shuffle Sub(-1), Sub(1)
            terminate
        behavior Sub(x):
            precondition: simulation().currentTime >= x
            take x
        ego = new Object with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=3)
        assert tuple(actions) == (-1, 1)


def test_shuffle_2():
    scenario = compileScenic(
        """
        behavior Foo():
            do shuffle Sub(1), Sub(3)
        behavior Sub(x):
            take x
        ego = new Object with behavior Foo
        """
    )
    ts = [sampleEgoActions(scenario, maxSteps=2) for i in range(30)]
    assert all(tuple(t) == (1, 3) or tuple(t) == (3, 1) for t in ts)
    assert any(tuple(t) == (1, 3) for t in ts)
    assert any(tuple(t) == (3, 1) for t in ts)


def test_shuffle_3():
    scenario = compileScenic(
        """
        behavior Foo():
            do shuffle {Sub(0): 1, Sub(1): 9}
        behavior Sub(x):
            take x
        ego = new Object with behavior Foo
        """
    )
    ts = [sampleEgoActions(scenario, maxSteps=2) for i in range(200)]
    assert all(tuple(t) == (0, 1) or tuple(t) == (1, 0) for t in ts)
    assert 145 <= sum(t[0] for t in ts) < 200


def test_shuffle_deadlock():
    scenario = compileScenic(
        """
        behavior Foo():
            do shuffle Sub(), Sub()
        behavior Sub():
            precondition: simulation().currentTime == 0
            wait
        ego = new Object with behavior Foo
        """
    )
    result = sampleResultOnce(scenario, maxSteps=2)
    assert result is None


# Requirements


def test_behavior_require():
    scenario = compileScenic(
        """
        behavior Foo():
            x = Range(-1, 1)
            while True:
                take x
                require x < 0
        ego = new Object with behavior Foo
        """
    )
    for i in range(50):
        actions = sampleEgoActions(scenario, maxSteps=2, maxIterations=50, maxScenes=1)
        assert len(actions) == 2
        assert actions[0] < 0
        assert actions[0] == actions[1]


def test_behavior_require_scene():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take self.foo
                require self.foo < 0
        ego = new Object with foo Range(-1, 1), with behavior Foo
        """
    )
    for i in range(50):
        actions = sampleEgoActions(scenario, maxSteps=2, maxIterations=1, maxScenes=50)
        assert len(actions) == 2
        assert actions[0] < 0
        assert actions[0] == actions[1]


def test_behavior_require_call():
    scenario = compileScenic(
        """
        behavior Foo():
            x = Uniform([], [1, 2])
            require len(x) > 0
            take [x]
        ego = new Object with behavior Foo
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=1, maxIterations=30)
        assert actions[0] == [1, 2]


def test_behavior_require_soft():
    scenario = compileScenic(
        """
        behavior Foo():
            x = Range(-1, 1)
            require[0.9] x >= 0
            take x
        ego = new Object with behavior Foo
        """
    )
    xs = []
    for i in range(350):
        actions = sampleEgoActions(scenario, maxSteps=1, maxIterations=50, maxScenes=1)
        assert len(actions) == 1
        xs.append(actions[0])
    count = sum(x >= 0 for x in xs)
    assert 255 <= count < 350


## Temporal requirements


def test_require_always():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take self.blah
                self.blah += DiscreteRange(0, 1)
        ego = new Object with behavior Foo, with blah 0
        require always ego.blah < 1
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=2, maxIterations=50)
        assert tuple(actions) == (0, 0)


def test_require_always_invalid():
    with pytest.raises(ScenicSyntaxError):
        compileScenic("require (always (x)) > 5")


def test_require_eventually():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take self.blah
                self.blah += DiscreteRange(0, 1)
        ego = new Object with behavior Foo, with blah 0
        require eventually ego.blah > 0
        """
    )
    for i in range(30):
        actions = sampleEgoActions(scenario, maxSteps=2, maxIterations=50)
        assert tuple(actions) == (0, 1)


def test_require_eventually_2():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take self.blah
                self.blah += 1
        ego = new Object with behavior Foo, with blah 0
        require eventually ego.blah == 0
        require eventually ego.blah == 1
        require eventually ego.blah == 2
        """
    )
    sampleEgoActions(scenario, maxSteps=3)


def test_require_eventually_3():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take self.blah
                self.blah += 1
        ego = new Object with behavior Foo, with blah 0
        require eventually ego.blah == -1
        """
    )
    with pytest.raises(RejectSimulationException):
        sampleEgoActions(scenario, maxSteps=3)


def test_require_next_1():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require next ego.blah == 1
        """
    )
    sampleEgoActions(scenario, maxSteps=5)


def test_require_next_2():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require next next ego.blah == 2
        """
    )
    sampleEgoActions(scenario, maxSteps=5)


def test_require_next_invalid():
    with pytest.raises(ScenicSyntaxError):
        compileScenic("require (next (x)) > 5")


def test_require_until():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require ego.blah < 3 until ego.blah >= 3
        """
    )
    sampleEgoActions(scenario, maxSteps=5)


def test_require_until_2():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require False until ego.blah > 3
        """
    )
    with pytest.raises(RejectSimulationException):
        sampleEgoActions(scenario, maxSteps=5)


def test_require_until_3():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require True until False
        """
    )
    with pytest.raises(RejectSimulationException):
        sampleEgoActions(scenario, maxSteps=5)


def test_require_implies_1():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require ego.blah == 3 implies ego.blah % 2 == 1
        """
    )
    sampleEgoActions(scenario, maxSteps=5)


def test_require_implies_2():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require always ego.blah % 2 == 0 implies next ego.blah % 2 == 1
        """
    )
    sampleEgoActions(scenario, maxSteps=5)


def test_require_implies_3():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                self.blah += 1
                take self.blah
        ego = new Object with behavior Foo, with blah 0
        require always ego.blah % 2 == 0 implies ego.blah == 0
        """
    )
    result = sampleResultOnce(scenario, maxSteps=5)
    assert result is None


## Monitors


def test_monitor():
    scenario = compileScenic(
        """
        monitor Monitor():
            while True:
                if ego.blah >= 3:
                    terminate
                wait
        require monitor Monitor()
        behavior Foo():
            while True:
                take self.blah
                self.blah += 1
        ego = new Object with blah 0, with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=5)
    assert tuple(actions) == (0, 1, 2, 3)


def test_monitor_arguments():
    scenario = compileScenic(
        """
        monitor Monitor(x):
            while True:
                if ego.blah >= x:
                    terminate
                wait
        require monitor Monitor(x=3)
        require monitor Monitor(x=2)
        behavior Foo():
            while True:
                take self.blah
                self.blah += 1
        ego = new Object with blah 0, with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=5)
    assert tuple(actions) == (0, 1, 2)


def test_monitor_samplable_arguments():
    scenario = compileScenic(
        """
        monitor Monitor(x):
            while True:
                if ego.blah >= x:
                    terminate
                wait
        limit = DiscreteRange(1, 2)
        require monitor Monitor(limit)
        behavior Foo():
            while True:
                take self.blah
                self.blah += 1
        ego = new Object with blah 0, with behavior Foo
        """
    )
    lengths = [len(sampleEgoActions(scenario, maxSteps=5)) for i in range(60)]
    assert all(2 <= length <= 3 for length in lengths)
    assert any(length == 2 for length in lengths)
    assert any(length == 3 for length in lengths)


def test_require_monitor_invalid():
    with pytest.raises(TypeError):
        scenario = compileScenic(
            """
            ego = new Object
            require monitor ego
        """
        )
        sampleScene(scenario)
    with pytest.raises(TypeError):
        scenario = compileScenic(
            """
            behavior Foo():
                wait
            ego = new Object with behavior Foo
            require monitor Foo()
        """
        )
        sampleScene(scenario)


def test_require_monitor_error():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            monitor Monitor():
                wait
            ego = new Object
            require Monitor()
        """
        )


def test_old_style_monitor():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            monitor Monitor:
                wait
            ego = new Object
        """
        )


def test_invalid_monitor_name():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            monitor 101():
                wait
            ego = new Object
        """
        )


def test_invalid_monitor_start():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            monitor Foo()
                wait
            ego = new Object
        """
        )


## Introspection


@pytest.mark.parametrize("ty", ("behavior", "monitor"))
def test_invocable_signature(ty):
    ego = sampleEgoFrom(
        f"""
        {ty} Blah(foo, *bar, baz=12, **qux):
            wait
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


## Interrupts

# Basic


def test_interrupt():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                while True:
                    take 1
            interrupt when simulation().currentTime % 3 == 2:
                take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=6)
    assert tuple(actions) == (1, 1, 2, 1, 1, 2)


def test_interrupt_first():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                while True:
                    take 1
            interrupt when simulation().currentTime == 0:
                take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (2, 1, 1)


def test_interrupt_priority():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                while True:
                    take 1
            interrupt when simulation().currentTime <= 1:
                take 2
            interrupt when simulation().currentTime == 0:
                take 3
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (3, 2, 1)


def test_interrupt_interrupted():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                while True:
                    take 1
            interrupt when simulation().currentTime <= 1:
                take 2
                take 3
            interrupt when simulation().currentTime == 1:
                take 4
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=5)
    assert tuple(actions) == (2, 4, 3, 1, 1)


def test_interrupt_actionless():
    scenario = compileScenic(
        """
        behavior Foo():
            i = 0
            try:
                for i in range(3):
                    take 1
            interrupt when i == 1:
                i = 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=5)
    assert tuple(actions) == (1, 1, 1, None, None)


def test_interrupt_define_local():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                i = 1
            interrupt when False:
                pass
            take i
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=1)
    assert tuple(actions) == (1,)


def test_interrupt_define_local_2():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                pass
            interrupt when True:
                i = 1
                abort
            take i
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=1)
    assert tuple(actions) == (1,)


# Exception handling


def test_interrupt_no_handlers():
    """Test a try-except statement that isn't actually a try-interrupt statement."""
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                for i in range(3):
                    take 1
                    raise Exception
            except Exception:
                take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=3)
    assert tuple(actions) == (1, 2, None)


def test_interrupt_except():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                for i in range(3):
                    take 1
            interrupt when simulation().currentTime == 1:
                take 2
                raise Exception
                take 3
            except Exception:
                take 4
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 2, 4, None)


def test_interrupt_except_else():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                for i in range(3):
                    take 1
            interrupt when simulation().currentTime == 1:
                take 2
                take 3
            except Exception:
                take 4
            else:
                take 5
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=7)
    assert tuple(actions) == (1, 2, 3, 1, 1, 5, None)


def test_interrupt_invariant_after_actions():
    scenario = compileScenic(
        """
        behavior Foo():
            invariant: ego.bar == 0
            try:
                for i in range(3):
                    take 1
            interrupt when simulation().currentTime == 1:
                take 2
                ego.bar = 1
            except InvariantViolation:
                ego.bar = 0
                take 4
        ego = new Object with bar 0, with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 2, 4, None)


# Nesting


def test_interrupt_nested():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                for i in range(3):
                    take 1
            interrupt when 1 <= simulation().currentTime <= 2:
                take 2
        behavior Bar():
            try:
                do Foo()
            interrupt when simulation().currentTime == 1:
                take 3
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=6)
    assert tuple(actions) == (1, 3, 2, 1, 1, None)


def test_interrupt_nested_2():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                for i in range(3):
                    take 1
            interrupt when simulation().currentTime == 1:
                take 2
                take 3
        behavior Bar():
            try:
                do Foo()
            interrupt when simulation().currentTime == 2:
                take 4
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=7)
    assert tuple(actions) == (1, 2, 4, 3, 1, 1, None)


def test_interrupt_nested_3():
    scenario = compileScenic(
        """
        behavior Bar():
            try:
                try:
                    for i in range(3):
                        take 1
                interrupt when 1 <= simulation().currentTime <= 2:
                    take 2
            interrupt when simulation().currentTime == 1:
                take 3
        ego = new Object with behavior Bar
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=6)
    assert tuple(actions) == (1, 3, 2, 1, 1, None)


# Control flow statements


def test_interrupt_break():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                try:
                    for i in range(3):
                        take 1
                interrupt when simulation().currentTime == 2:
                    take 2
                    break
                    take 3
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 1, 2, None)


def test_interrupt_break_2():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                try:
                    for i in range(3):
                        take 1
                interrupt when simulation().currentTime == 1:
                    for i in range(3):
                        take 2
                        break
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (1, 2, 1, 1)


def test_interrupt_continue():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take 4
                try:
                    for i in range(2):
                        take 1
                interrupt when simulation().currentTime == 2:
                    take 2
                    continue
                    take 3
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=7)
    assert tuple(actions) == (4, 1, 2, 4, 1, 1, 4)


def test_interrupt_continue_2():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                try:
                    for i in range(3):
                        take 1
                interrupt when simulation().currentTime == 1:
                    for i in range(3):
                        if i == 0:
                            continue
                        take 2
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=5)
    assert tuple(actions) == (1, 2, 2, 1, 1)


def test_interrupt_abort():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take 3
                try:
                    for i in range(3):
                        take 1
                interrupt when simulation().currentTime == 2:
                    for i in range(3):
                        take 2
                        abort
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=8)
    assert tuple(actions) == (3, 1, 2, 3, 1, 1, 1, 3)


def test_interrupt_misplaced_abort():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                abort
            ego = new Object with behavior Foo
        """
        )


def test_interrupt_return():
    scenario = compileScenic(
        """
        behavior Foo():
            while True:
                take 3
                try:
                    for i in range(3):
                        take 1
                interrupt when simulation().currentTime == 2:
                    for i in range(3):
                        take 2
                        return
        ego = new Object with behavior Foo
        """
    )
    actions = sampleEgoActions(scenario, maxSteps=4)
    assert tuple(actions) == (3, 1, 2, None)


# Errors


def test_interrupt_missing_colon():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                try:
                    take 1
                interrupt when False
                    wait
            ego = new Object with behavior Foo
        """
        )


def test_interrupt_extra_arguments():
    with pytest.raises(ScenicSyntaxError):
        compileScenic(
            """
            behavior Foo():
                try:
                    take 1
                interrupt when False, False:
                    wait
            ego = new Object with behavior Foo
        """
        )


def test_interrupt_unassigned_local():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                i = 0
                take 1
            interrupt when i == 1:
                i = 2
        ego = new Object with behavior Foo
        """
    )
    if sys.version_info >= (3, 10, 3):  # see veneer.executeInBehavior
        exc_type = NameError
    else:
        exc_type = AttributeError
    with pytest.raises(exc_type) as exc_info:
        sampleEgoActions(scenario, maxSteps=1)
    checkErrorLineNumber(5, exc_info)


def test_interrupt_guard_subbehavior():
    scenario = compileScenic(
        """
        behavior Foo():
            try:
                take 1
            interrupt when Foo():
                wait
        ego = new Object with behavior Foo
        """
    )
    with pytest.raises(InvalidScenarioError):
        sampleEgoActions(scenario, maxSteps=1)


## Simulation results


def test_termination_reason_time():
    scenario = compileScenic(
        """
        ego = new Object
        """
    )
    result = sampleResult(scenario, maxSteps=2)
    assert result.terminationType == TerminationType.timeLimit


def test_termination_reason_condition_1():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.position = self.position + 1@0
                wait
        ego = new Object with behavior Foo
        terminate when ego.position.x >= 1
        """
    )
    result = sampleResult(scenario, maxSteps=2)
    assert result.terminationType == TerminationType.scenarioComplete


def test_termination_reason_condition_2():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.position = self.position + 1@0
                wait
        ego = new Object with behavior Foo
        terminate simulation when ego.position.x >= 1
        """
    )
    result = sampleResult(scenario, maxSteps=2)
    assert result.terminationType == TerminationType.simulationTerminationCondition


def test_termination_reason_behavior():
    scenario = compileScenic(
        """
        behavior Foo():
            terminate
        ego = new Object with behavior Foo
        """
    )
    result = sampleResult(scenario, maxSteps=2)
    assert result.terminationType == TerminationType.terminatedByBehavior


def test_termination_reason_monitor():
    scenario = compileScenic(
        """
        monitor Foo():
            terminate
        require monitor Foo()
        ego = new Object
        """
    )
    result = sampleResult(scenario, maxSteps=2)
    assert result.terminationType == TerminationType.terminatedByMonitor


## Recording
# (see also `test_recording.py`)


def test_record():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(3):
                self.position = self.position + 2@0
                wait
        ego = new Object with behavior Foo
        terminate when ego.position.x >= 6
        record initial ego.position as initial
        record final ego.position as final
        record ego.position as position
        """
    )
    result = sampleResult(scenario, maxSteps=4)
    assert result.records["initial"] == (0, 0, 0)
    assert result.records["final"] == (6, 0, 0)
    assert tuple(result.records["position"]) == (
        (0, (0, 0, 0)),
        (1, (2, 0, 0)),
        (2, (4, 0, 0)),
        (3, (6, 0, 0)),
    )


## lastActions Property
def test_lastActions():
    scenario = compileScenic(
        """
        behavior Foo():
            for i in range(4):
                take i
        ego = new Object with behavior Foo, with allowCollisions True
        other = new Object with allowCollisions True
        record ego.lastActions as ego_lastActions
        record other.lastActions as other_lastActions
        """
    )
    result = sampleResult(scenario, maxSteps=4)
    assert tuple(result.records["ego_lastActions"]) == (
        (0, tuple()),
        (1, (0,)),
        (2, (1,)),
        (3, (2,)),
        (4, (3,)),
    )
    assert tuple(result.records["other_lastActions"]) == (
        (0, tuple()),
        (1, tuple()),
        (2, tuple()),
        (3, tuple()),
        (4, tuple()),
    )
