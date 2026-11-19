"""Dynamic scenarios."""

import ast
from collections import defaultdict
import dataclasses
import functools
import inspect
import sys
import types
import warnings
import weakref

import rv_ltl

import scenic
from scenic.core.distributions import Samplable
import scenic.core.dynamics as dynamics
from scenic.core.errors import InvalidScenarioError, ScenicSyntaxError
from scenic.core.lazy_eval import DelayedArgument, needsLazyEvaluation
from scenic.core.requirements import (
    DynamicRequirement,
    PendingRequirement,
    RequirementType,
)
from scenic.core.utils import alarm, argsToString
from scenic.core.workspaces import Workspace

from .actions import _EndScenarioAction, _EndSimulationAction
from .behaviors import Behavior, Monitor
from .invocables import Invocable
from .utils import RejectSimulationException, StuckBehaviorWarning


class DynamicScenario(Invocable):
    """Internal class for scenarios which can execute during dynamic simulations.

    Provides additional information complementing `Scenario`, which originally only
    supported static scenarios. The two classes should probably eventually be merged.
    """

    def __init_subclass__(cls, *args, **kwargs):
        import scenic.syntax.veneer as veneer

        veneer.registerDynamicScenarioClass(cls)

        target = cls._setup or cls._compose or (lambda self, agent: 0)
        target = functools.partial(target, 0, 0)  # account for Scenic-inserted args
        cls.__signature__ = inspect.signature(target)

    _requirementSyntax = None  # overridden by subclasses
    _simulatorFactory = None
    _globalParameters = None
    _locals = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ego = None
        self._workspace = None
        self._instances = []  # ordered for reproducibility
        # _objects should contain a reference to the most complete version of
        # the objects in this scene (sampled > unsampled)
        self._objects = []  # ordered for reproducibility
        self._sampledObjects = self._objects
        self._externalParameters = []
        self._pendingRequirements = []
        self._requirements = []
        # things needing to be sampled to evaluate the requirements
        self._requirementDeps = set()

        self._agents = []
        self._monitors = []
        self._behaviors = []
        self._monitorRequirements = []
        self._temporalRequirements = []
        self._terminationConditions = []
        self._terminateSimulationConditions = []
        self._recordedExprs = []
        self._recordedInitialExprs = []
        self._recordedFinalExprs = []

        self._subScenarios = []
        self._endWithBehaviors = False
        self._timeLimit = None
        self._timeLimitIsInSeconds = False
        self._prepared = False
        self._delayingPreconditionCheck = False
        self._dummyNamespace = None

        self._timeLimitInSteps = None  # computed at simulation time
        self._elapsedTime = 0
        self._recordedTime = None
        self._eventuallySatisfied = None
        self._overrides = {}

        self._requirementMonitors = None

    @classmethod
    def _dummy(cls, namespace):
        scenario = cls()
        scenario._setup = None
        scenario._compose = None
        scenario._prepared = True
        scenario._dummyNamespace = namespace
        return scenario

    @classmethod
    def _requiresArguments(cls):
        """Whether this scenario cannot be instantiated without arguments."""
        if cls._setup:
            func = cls._setup
        elif cls._compose:
            func = cls._compose
        else:
            return True
        sig = inspect.signature(func)
        try:
            sig.bind(None, None)  # first two arguments are added internally by Scenic
            return False
        except TypeError:
            return True

    @property
    def ego(self):
        if self._ego is None:
            return DelayedArgument((), lambda context: self._ego, _internal=True)
        return self._ego

    @property
    def objects(self):
        return tuple(self._objects)

    def _bindTo(self, scene):
        """Bind this scenario to a sampled scene when starting a new simulation."""
        self._ego = scene.egoObject
        self._workspace = scene.workspace
        self._objects = list(scene.objects)
        self._agents = [obj for obj in scene.objects if obj.behavior is not None]
        self._monitors = list(scene.monitors)
        self._temporalRequirements = scene.temporalRequirements
        self._terminationConditions = scene.terminationConditions
        self._terminateSimulationConditions = scene.terminateSimulationConditions
        self._recordedExprs = scene.recordedExprs
        self._recordedInitialExprs = scene.recordedInitialExprs
        self._recordedFinalExprs = scene.recordedFinalExprs

    def _prepare(self, delayPreconditionCheck=False):
        """Prepare the scenario for execution, executing its setup block."""
        import scenic.syntax.veneer as veneer

        assert not self._prepared
        self._prepared = True

        self._finalizeArguments()  # TODO generalize _prepare for Invocable?

        veneer.prepareScenario(self)
        with veneer.executeInScenario(self, inheritEgo=True):
            # Check preconditions and invariants
            if delayPreconditionCheck:
                self._delayingPreconditionCheck = True
            else:
                self._checkAllPreconditions()

            # Execute setup block
            if self._setup is not None:
                assert not any(needsLazyEvaluation(arg) for arg in self._args)
                assert not any(needsLazyEvaluation(arg) for arg in self._kwargs.values())
                self._setup(None, *self._args, **self._kwargs)
                veneer.finishScenarioSetup(self)

        # Extract requirements, scan for relations used for pruning, and create closures
        self._compileRequirements()

    @classmethod
    def _bindGlobals(cls, globs):
        cls._globalParameters = globs

    def _start(self):
        """Start the scenario, starting its compose block, behaviors, and monitors."""
        import scenic.syntax.veneer as veneer

        super()._start()
        assert self._prepared

        # Check preconditions if they could not be checked earlier
        if self._delayingPreconditionCheck:
            self._checkAllPreconditions()

        # Compute time limit now that we know the simulation timestep
        self._elapsedTime = 0
        self._timeLimitInSteps = self._timeLimit
        timestep = veneer.currentSimulation.timestep
        if self._timeLimitIsInSeconds:
            self._timeLimitInSteps /= timestep

        # create monitors for each requirement used for this simulation
        self._requirementMonitors = [r.toMonitor() for r in self._temporalRequirements]

        veneer.startScenario(self)
        with veneer.executeInScenario(self):
            # Start compose block
            if self._compose is not None:
                if not inspect.isgeneratorfunction(self._compose):
                    raise InvalidScenarioError(
                        '"compose" block does not invoke any scenarios'
                    )
                self._runningIterator = self._compose(None, *self._args, **self._kwargs)

            # Initialize behavior coroutines of agents
            for agent in self._agents:
                behavior = agent.behavior
                assert isinstance(behavior, Behavior), behavior
                behavior._assignTo(agent)
            # Initialize monitor coroutines
            for monitor in self._monitors:
                monitor._start()

        # Prepare recorders
        simName = veneer.currentSimulation.name
        currentTime = veneer.currentSimulation.currentTime
        globalParams = types.MappingProxyType(veneer._globalParameters)
        for req in self._recordedExprs:
            if (recConfig := req.recConfig) and (recorder := recConfig.recorder):
                recorder.beginRecording(
                    recConfig, simName, timestep, globalParams, currentTime
                )

    def _step(self):
        """Execute the (already-started) scenario for one time step.

        Returns:
            `None` if the scenario will continue executing; otherwise a string describing
            why it has terminated.
        """
        import scenic.syntax.veneer as veneer

        super()._step()

        # Check temporal requirements
        for m in self._requirementMonitors:
            result = m.value()
            if result == rv_ltl.B4.FALSE:
                raise RejectSimulationException(str(m))

        # Check if we have reached the time limit, if any
        if (
            self._timeLimitInSteps is not None
            and self._elapsedTime >= self._timeLimitInSteps
        ):
            return self._stop("reached time limit")
        self._elapsedTime += 1

        # Execute compose block, if any
        composeDone = False
        if self._runningIterator is None:
            composeDone = True  # compose block ended in an earlier step
        else:

            def alarmHandler(signum, frame):
                # NOTE: if using pytest-cov, sys.gettrace() may be set by coverage, but we still want timeout warnings enabled
                if sys.gettrace() and "coverage" not in str(type(sys.gettrace())):
                    return  # skip the warning if we're in the debugger
                warnings.warn(
                    f"the compose block of scenario {self} is taking a long time; "
                    'maybe you have an infinite loop with no "wait" statement?',
                    StuckBehaviorWarning,
                )

            timeout = dynamics.stuckBehaviorWarningTimeout
            with veneer.executeInScenario(self), alarm(timeout, alarmHandler):
                try:
                    result = self._runningIterator.send(None)
                    if isinstance(result, (_EndSimulationAction, _EndScenarioAction)):
                        return self._stop(result)
                except StopIteration:
                    self._runningIterator = None
                    composeDone = True

        # If there is a compose block and it has finished, we're done
        if self._compose is not None and composeDone:
            return self._stop("finished compose block")

        # Optionally end when all our agents' behaviors have ended
        if self._endWithBehaviors:
            if all(agent.behavior._isFinished for agent in self._agents):
                return self._stop("all behaviors finished")

        # Check if any termination conditions apply
        for req in self._terminationConditions:
            if req.evaluate():
                return self._stop(req)

        # Scenario will not terminate yet
        return None

    def _stop(self, reason, quiet=False):
        """Stop the scenario's execution, for the given reason."""
        import scenic.syntax.veneer as veneer

        assert self._isRunning

        if not quiet:
            # Record finally-recorded values.
            sim = veneer.currentSimulation
            for rec in self._recordedFinalExprs:
                sim._record(rec.name, rec.evaluate())

            # Record ordinary `record` statements too if they haven't been already.
            self._recordTimeSeries()

        # Stop monitors and subscenarios.
        for monitor in self._monitors:
            if monitor._isRunning:
                monitor._stop()
        self._monitors = []
        for sub in self._subScenarios:
            if sub._isRunning:
                sub._stop("parent scenario ending", quiet=quiet)
        self._runningIterator = None

        # Revert overrides.
        for obj, oldVals in self._overrides.items():
            obj._revert(oldVals)

        # Inform the veneer we have stopped, and mark ourselves finished.
        veneer.endScenario(self, reason, quiet=quiet)
        super()._stop(reason)

        # Check if a temporal requirement was not satisfied.
        rejection = None
        if not quiet:
            for req in self._requirementMonitors:
                if req.lastValue.is_falsy:
                    rejection = str(req)
                    break
        self._requirementMonitors = None

        # Stop recorders.
        cancelRecordings = quiet or rejection is not None
        for req in self._recordedExprs:
            if (recConfig := req.recConfig) and (recorder := recConfig.recorder):
                recorder.endRecording(canceled=cancelRecordings)

        # If a temporal requirement was violated, reject (now that we're cleaned up).
        if rejection is not None:
            raise RejectSimulationException(rejection)

        return reason

    def _invokeInner(self, agent, subs):
        for sub in subs:
            if not isinstance(sub, DynamicScenario):
                raise TypeError(f"expected a scenario, got {sub}")
            sub._prepare()
            sub._start()
        self._subScenarios = list(subs)
        while True:
            newSubs = []
            for sub in self._subScenarios:
                terminationReason = sub._step()
                if isinstance(terminationReason, _EndSimulationAction):
                    yield terminationReason
                    assert False, self  # should never get here since simulation ends
                elif terminationReason is None:
                    newSubs.append(sub)
            self._subScenarios = newSubs
            if not newSubs:
                return
            yield None
            # Check if any sub-scenarios stopped during action execution
            self._subScenarios = [sub for sub in self._subScenarios if sub._isRunning]

    def _updateRecords(self):
        from scenic.syntax.veneer import currentSimulation

        # _step() was called earlier this time step, so at time step 0 we will
        # already have _elapsedTime == 1
        assert self._elapsedTime >= 1
        if self._elapsedTime == 1:
            for rec in self._recordedInitialExprs:
                currentSimulation._record(rec.name, rec.evaluate())

        self._recordTimeSeries()

        for sub in self._subScenarios:
            sub._updateRecords()

    def _recordTimeSeries(self):
        from scenic.syntax.veneer import currentSimulation

        currentTime = currentSimulation.currentTime
        if self._recordedTime == currentTime:
            # This time step was already recorded (e.g. the scenario was terminated
            # by a behavior after the current state was recorded).
            return

        for rec in self._recordedExprs:
            value = rec.evaluate()
            currentSimulation._recordTimeSeries(rec.name, value)
            if (recConfig := rec.recConfig) and (recorder := recConfig.recorder):
                recorder._record(value, currentTime)

        self._recordedTime = currentTime

    def _runMonitors(self):
        terminationReason = None
        endScenario = None
        for monitor in self._monitors:
            action = monitor._step()
            # do not exit early, since subsequent monitors could reject the simulation
            if isinstance(action, _EndSimulationAction):
                terminationReason = action
            elif isinstance(action, _EndScenarioAction):
                assert action.scenario is None
                endScenario = action
        for sub in self._subScenarios:
            subreason = sub._runMonitors()
            if subreason is not None:
                terminationReason = subreason
        if endScenario:
            self._stop(endScenario)
        return terminationReason or endScenario

    def _checkSimulationTerminationConditions(self):
        for req in self._terminateSimulationConditions:
            if req.isTrue().is_truthy:
                return req
        return None

    @property
    def _allAgents(self):
        agents = list(self._agents)
        for sub in self._subScenarios:
            agents.extend(sub._allAgents)
        return agents

    def _inherit(self, other):
        if not self._ego:
            self._ego = other._ego
        if not self._workspace:
            self._workspace = other._workspace
        self._instances.extend(other._instances)
        self._objects.extend(other._objects)
        self._agents.extend(other._agents)
        self._globalParameters.update(other._globalParameters)
        self._externalParameters.extend(other._externalParameters)
        self._requirements.extend(other._requirements)
        self._behaviors.extend(other._behaviors)

    def _registerInstance(self, inst):
        self._instances.append(inst)

    def _registerObject(self, obj):
        self._registerInstance(obj)
        self._objects.append(obj)
        if getattr(obj, "behavior", None) is not None:
            self._agents.append(obj)

        obj._parentScenario = weakref.ref(self)

    def _addRequirement(self, ty, reqID, req, line, name, prob, recConfig=None):
        """Save a requirement defined at compile-time for later processing."""
        preq = PendingRequirement(ty, req, line, prob, name, self._ego, recConfig, self)
        self._pendingRequirements.append((reqID, preq))

    def _addDynamicRequirement(self, ty, req, line, name):
        """Add a requirement defined during a dynamic simulation."""
        dreq = DynamicRequirement(ty, req, line, name)
        self._temporalRequirements.append(dreq)

    def _addMonitor(self, monitor):
        """Add a monitor during a dynamic simulation."""
        assert isinstance(monitor, Monitor)
        self._monitors.append(monitor)
        if self._isRunning:
            monitor._start()

    def _compileRequirements(self):
        namespace = self._dummyNamespace if self._dummyNamespace else self.__dict__
        requirementSyntax = self._requirementSyntax
        assert requirementSyntax is not None
        for reqID, requirement in self._pendingRequirements:
            syntax = requirementSyntax[reqID] if requirementSyntax else None

            # Catch the simple case where someone has most likely forgotten the "monitor"
            # keyword.
            if (
                (not requirement.ty == RequirementType.monitor)
                and isinstance(syntax, ast.Call)
                and isinstance(syntax.func, ast.Name)
                and syntax.func.id in namespace
                and isinstance(namespace[syntax.func.id], type)
                and issubclass(
                    namespace[syntax.func.id], scenic.core.dynamics.behaviors.Monitor
                )
            ):
                raise ScenicSyntaxError(
                    f"Missing 'monitor' keyword after 'require' when instantiating '{syntax.func.id}'"
                )

            compiledReq = requirement.compile(namespace, self, syntax)

            self._registerCompiledRequirement(compiledReq)
            self._requirementDeps.update(compiledReq.dependencies)

    def _registerCompiledRequirement(self, req):
        if req.ty is RequirementType.require:
            place = self._requirements
        elif req.ty is RequirementType.monitor:
            place = self._monitorRequirements
        elif req.ty is RequirementType.terminateWhen:
            place = self._terminationConditions
        elif req.ty is RequirementType.terminateSimulationWhen:
            place = self._terminateSimulationConditions
        elif req.ty is RequirementType.record:
            place = self._recordedExprs
        elif req.ty is RequirementType.recordInitial:
            place = self._recordedInitialExprs
        elif req.ty is RequirementType.recordFinal:
            place = self._recordedFinalExprs
        else:
            raise RuntimeError(f"internal error: requirement {req} has unknown type!")
        place.append(req)

    def _setTimeLimit(self, timeLimit, inSeconds=True):
        self._timeLimit = timeLimit
        self._timeLimitIsInSeconds = inSeconds

    def _override(self, obj, specifiers):
        oldVals = obj._override(specifiers)
        if obj not in self._overrides:
            self._overrides[obj] = oldVals

    def _toScenario(self, namespace):
        assert self._prepared

        if not self._workspace:
            self._workspace = Workspace()  # default empty workspace
        astHash = namespace["_astHash"]
        name = None if self._dummyNamespace else self.__class__.__name__
        options = dataclasses.replace(namespace["_compileOptions"], scenario=name)

        from scenic.core.scenarios import Scenario

        scenario = Scenario(
            self._workspace,
            self._simulatorFactory,
            self._instances,
            self._objects,
            self._ego,
            self._globalParameters,
            self._externalParameters,
            self._requirements,
            self._requirementDeps,
            self._monitorRequirements,
            self._behaviorNamespaces,
            self,
            astHash,
            options,
        )  # TODO unify these!
        return scenario

    def _makeLocalsSnapshot(self):
        locs = {}
        for local in self._locals:
            if local in self.__dict__:
                locs[local] = self.__dict__[local]
        return LocalsSnapshot(locs)

    def __getattr__(self, name):
        if name in self._locals:
            return DelayedArgument(
                (), lambda context: getattr(self, name), _internal=True
            )
        return object.__getattribute__(self, name)

    def __str__(self):
        if self._dummyNamespace:
            return "top-level scenario"
        else:
            args = argsToString(self._args, self._kwargs)
            return f"{self.__class__.__name__}({args})"


class LocalsSnapshot(Samplable):
    def __init__(self, locs):
        self._locs = locs
        self.__dict__.update(locs)
        super().__init__(locs.values())

    def sampleGiven(self, value):
        return LocalsSnapshot({name: value[val] for name, val in self._locs.items()})
