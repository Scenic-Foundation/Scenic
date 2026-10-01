"""Behaviors and monitors."""

import functools
import inspect
import itertools
import sys
import warnings

from scenic.core.distributions import Samplable, toDistribution
import scenic.core.dynamics as dynamics
from scenic.core.errors import InvalidScenarioError
from scenic.core.type_support import CoercionFailure
from scenic.core.utils import alarm

from .invocables import Invocable
from .utils import StuckBehaviorWarning


class Behavior(Invocable, Samplable):
    """Dynamic behaviors of agents.

    Behavior statements are translated into definitions of subclasses of this class.
    """

    _noActionsMsg = (
        'does not take any actions (perhaps you forgot to use "take" or "do"?)'
    )

    def __init_subclass__(cls):
        if "__signature__" in cls.__dict__:
            # We're unpickling a behavior; skip this step.
            return

        if cls.__module__ is not __name__:
            import scenic.syntax.veneer as veneer

            if veneer.currentScenario:
                veneer.currentScenario._behaviors.append(cls)

            target = cls.makeGenerator
            target = functools.partial(target, 0, 0)  # account for Scenic-inserted args
            cls.__signature__ = inspect.signature(target)

    def __init__(self, *args, **kwargs):
        args = tuple(toDistribution(arg) for arg in args)
        kwargs = {name: toDistribution(arg) for name, arg in kwargs.items()}

        # Validate arguments to the behavior
        sig = inspect.signature(self.makeGenerator)
        sig.bind(None, *args, **kwargs)  # raises TypeError on incompatible arguments
        Samplable.__init__(self, itertools.chain(args, kwargs.values()))
        Invocable.__init__(self, *args, **kwargs)

        if not inspect.isgeneratorfunction(self.makeGenerator):
            raise InvalidScenarioError(f"{self} {self._noActionsMsg}")

    @classmethod
    def _canCoerceType(cls, ty):
        return issubclass(ty, cls) or ty in (type, type(None))

    @classmethod
    def _coerce(cls, thing):
        if thing is None or isinstance(thing, cls):
            return thing
        elif issubclass(thing, cls):
            return thing()
        else:
            raise CoercionFailure(f"expected type of behavior, got {thing}")

    def sampleGiven(self, value):
        args = (value[arg] for arg in self._args)
        kwargs = {name: value[val] for name, val in self._kwargs.items()}
        return type(self)(*args, **kwargs)

    def _assignTo(self, agent):
        if self._agent and agent is self._agent._dynamicProxy:
            # Assigned again (e.g. by override) to same agent; do nothing.
            return
        if self._isRunning:
            raise InvalidScenarioError(
                f"tried to reuse behavior object {self} already assigned to {self._agent}"
            )
        self._start(agent)

    def _start(self, agent):
        super()._start()
        self._agent = agent
        self._runningIterator = self.makeGenerator(agent, *self._args, **self._kwargs)
        self._checkAllPreconditions()

    def _step(self):
        import scenic.syntax.veneer as veneer

        super()._step()
        assert self._runningIterator

        def alarmHandler(signum, frame):
            # NOTE: if using pytest-cov, sys.gettrace() set to CTracer(), but we still want timeout warnings enabled
            if sys.gettrace() and "coverage" not in str(type(sys.gettrace())):
                return  # skip the warning if we're in the debugger
            warnings.warn(
                f"the behavior {self} is taking a long time to take an action; "
                "maybe you have an infinite loop with no take/wait statements?",
                StuckBehaviorWarning,
            )

        timeout = dynamics.stuckBehaviorWarningTimeout
        with veneer.executeInBehavior(self), alarm(timeout, alarmHandler):
            try:
                actions = self._runningIterator.send(None)
            except StopIteration:
                return None
        return actions

    def _stop(self, reason=None):
        super()._stop(reason)
        self._agent = None
        self._runningIterator = None

    @property
    def _isFinished(self):
        return self._runningIterator is None

    def _invokeInner(self, agent, subs):
        import scenic.syntax.veneer as veneer

        # Validate all inner behaviors
        for sub in subs:
            if not isinstance(sub, Behavior):
                raise TypeError(f"expected a behavior, got {sub}")
            sub._start(agent)

        # Create a generator for each inner behavior that yields the appropriate actions, cleaning up when done.
        def make_inner_generator(sub):
            try:
                while sub._isRunning:
                    actions = sub._step()
                    if actions is None:
                        return
                    yield actions
            finally:
                if sub._isRunning:
                    sub._stop()

        inner_generators = [make_inner_generator(sub) for sub in subs]

        # Yield from a generator that zips all the inner generators together without padding, until all inner generators have terminated.
        while True:
            try:
                raw_actions_list = next(itertools.zip_longest(*inner_generators))
                yield tuple(
                    filter(
                        lambda x: x is not None,
                        itertools.chain.from_iterable(raw_actions_list),
                    )
                )
            except StopIteration:
                return

    def __repr__(self):
        items = itertools.chain(
            (repr(arg) for arg in self._args),
            (f"{key}={repr(val)}" for key, val in self._kwargs.items()),
        )
        allArgs = ", ".join(items)
        return f"{self.__class__.__name__}({allArgs})"


class Monitor(Behavior):
    """Monitors for dynamic simulations.

    Monitor statements are translated into definitions of subclasses of this class.
    """

    _noActionsMsg = 'does not take any actions (perhaps you forgot to use "wait"?)'

    def _start(self):
        return super()._start(None)
