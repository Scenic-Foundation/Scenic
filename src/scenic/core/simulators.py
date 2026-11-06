"""Interface between Scenic and simulators.

This module defines the core classes `Simulator` and `Simulation` which
orchestrate dynamic simulations. Each simulator interface defines subclasses
of these classes for their particular simulator.

Ordinary Scenic users only need to know about the top-level simulation API
`Simulator.simulate` and the attributes of the `Simulation` class (in particular
the ``result`` attribute, which captures information about the result of the
simulation as a `SimulationResult` object).
"""

import abc
from collections import defaultdict
import enum
import math
import numbers
import time
import types

from scenic.core.distributions import RejectionException
from scenic.core.dynamics import GuardViolation, RejectSimulationException
from scenic.core.dynamics.actions import Action, _EndScenarioAction, _EndSimulationAction
import scenic.core.errors as errors
from scenic.core.errors import InvalidScenarioError, optionallyDebugRejection
from scenic.core.object_types import (
    Object2D,
    disableDynamicProxyFor,
    enableDynamicProxyFor,
    setDynamicProxyFor,
)
from scenic.core.requirements import RequirementType
from scenic.core.serialization import Serializer
from scenic.core.vectors import Vector


class SimulatorInterfaceWarning(UserWarning):
    """Warning indicating an issue with the interface to an external simulator."""

    pass


class SimulationCreationError(Exception):
    """Exception indicating a simulation could not be run from the given scene.

    Can also be issued during a simulation if dynamic object creation fails.
    """

    pass


class DivergenceError(Exception):
    """Exception indicating simulation replay failed due to simulator nondeterminism."""

    pass


class Simulator(abc.ABC):
    """A simulator which can execute dynamic simulations from Scenic scenes.

    Simulator interfaces which support dynamic simulations should implement a
    subclass of `Simulator`. An instance of the class represents a connection to
    the simulator suitable for running multiple simulations (not necessarily of
    the same Scenic program). For an example of how to implement this class,
    and its counterpart `Simulation` for individual simulations, see
    :mod:`scenic.simulators.webots.simulator`.

    Users who create an instance of `Simulator` should call its `destroy` method
    when they are finished running simulations to allow the interface to do any
    necessary cleanup.
    """

    def __init__(self):
        self._destroyed = False

    def simulate(
        self,
        scene,
        maxSteps=None,
        maxIterations=1,
        *,
        timestep=None,
        name=None,
        verbosity=None,
        raiseGuardViolations=False,
        replay=None,
        enableReplay=True,
        enableDivergenceCheck=False,
        divergenceTolerance=0,
        continueAfterDivergence=False,
        allowPickle=False,
    ):
        """Run a simulation for a given scene.

        For details on how simulations are run, see `dynamic scenario semantics`.

        Args:
            scene (Scene): Scene from which to start the simulation (sampled using
                `Scenario.generate`).
            maxSteps (int): Maximum number of time steps for the simulation, or `None` to
                not impose a time bound.
            maxIterations (int): Maximum number of rejection sampling iterations.
            timestep (float): Length of a time step in seconds, or `None` to use a
                default provided by the simulator interface. Some interfaces may not
                allow arbitrary time step lengths or may require the timestep to be set
                when creating the `Simulator` and not customized per-simulation.
            name (str): Name of the simulation, if any. Used to identify the simulation
                when saving records to files and in debugging messages.
            verbosity (int): If not `None`, override Scenic's global verbosity level
                (from the :option:`--verbosity` option or `scenic.setDebuggingOptions`).
            raiseGuardViolations (bool): Whether violations of preconditions/invariants
                of scenarios/behaviors should cause this method to raise an exception,
                instead of only rejecting the simulation (the default behavior).
            replay (bytes): If not `None`, must be replay data output by `Simulation.getReplay`:
                we will then replay the saved simulation rather than randomly generating
                one as usual. If **maxSteps** is larger than that of the original
                simulation, then once the replay is exhausted the simulation will continue
                to run in the usual randomized manner.
            enableReplay (bool): Whether to save data from the simulation so that it can
                be serialized for later replay using `Scenario.simulationToBytes` or
                `Simulation.getReplay`. Enabled by default as the overhead is generally low.
            enableDivergenceCheck (bool): Whether to save the values of every
                :term:`dynamic property` at each time step, so that when the simulation is
                replayed, nondeterminism in the simulator (or replaying the simulation in
                the wrong simulator) can be detected. Disabled by default as this option
                greatly increases the size of replay objects (~100 bytes per object per step).
            divergenceTolerance (float): Amount by which a dynamic property can deviate in
                a replay from its original value before we consider the replay to have
                diverged. The default value is zero: no deviation is allowed. If finer
                control over divergences is required, see `Simulation.valuesHaveDiverged`.
            continueAfterDivergence (bool): Whether to continue simulating after a
                divergence is detected instead of raising a `DivergenceError`. If this is
                true, then a divergence ends the replaying of the saved scenario but the
                simulation will continue in the usual randomized manner (i.e., it is as
                if the replay data ran out at the moment of the divergence).
            allowPickle (bool): Whether to use `pickle` to (de)serialize custom object
                types. See `sceneFromBytes` for a discussion of when this may be needed
                (rarely) and its security implications.

        Returns:
            A `Simulation` object representing the completed simulation, or `None` if no
            simulation satisfying the requirements could be found within
            **maxIterations** iterations.

        Raises:
            SimulationCreationError: if an error occurred while trying to run a
                simulation (e.g. some assumption made by the simulator was violated, like
                trying to create an object inside another).
            GuardViolation: if **raiseGuardViolations** is true and a precondition or
                invariant was violated during the simulation.
            DivergenceError: if replaying a simulation (via the **replay** option) and
                the replay has diverged from the original; requires the original simulation
                to have been run with **enableDivergenceCheck**.
            SerializationError: if writing or reading replay data fails. This could happen
                if your scenario uses an unusual custom distribution (see `sceneToBytes`)
                or if the replayed scenario has diverged without divergence-checking
                enabled.

        .. versionchanged:: 3.0

            **maxIterations** is now 1 by default.

        .. versionadded:: 3.0

            The **timestep** argument.
        """

        if self._destroyed:
            raise RuntimeError(
                "simulator cannot run additional simulations "
                "(the destroy() method has already been called)"
            )
        if verbosity is None:
            verbosity = errors.verbosityLevel

        # Repeatedly run simulations until we find one satisfying the requirements
        iterations = 0
        simulation = None
        while not simulation and (maxIterations is None or iterations < maxIterations):
            iterations += 1
            if maxIterations == 1:
                simName = str(name) if name else "1"
            else:
                simName = f"{name}.{iterations}" if name else str(iterations)
            simulation = self._runSingleSimulation(
                scene,
                maxSteps,
                name=simName,
                verbosity=verbosity,
                timestep=timestep,
                raiseGuardViolations=raiseGuardViolations,
                replay=replay,
                enableReplay=enableReplay,
                enableDivergenceCheck=enableDivergenceCheck,
                divergenceTolerance=divergenceTolerance,
                continueAfterDivergence=continueAfterDivergence,
                allowPickle=allowPickle,
            )
        return simulation

    def replay(self, scene, replay, **kwargs):
        """Replay a simulation.

        This convenience method simply calls `simulate` (and so takes all the same
        arguments), but makes the **replay** argument positional so you can write
        ``simulator.replay(scene, replay)`` instead of
        ``simulator.simulate(scene, replay=replay)``.
        """
        return self.simulate(scene, replay=replay, **kwargs)

    def _runSingleSimulation(
        self, scene, maxSteps, *, name, verbosity, raiseGuardViolations=False, **kwargs
    ):
        if verbosity >= 2:
            print(f"  Starting simulation {name}...")
        try:
            simulation = self.createSimulation(
                scene,
                maxSteps=maxSteps,
                name=name,
                verbosity=verbosity,
                **kwargs,
            )
        except (RejectSimulationException, RejectionException, GuardViolation) as e:
            if verbosity >= 2:
                print(
                    f"  Rejected simulation {name} at time step "
                    f"{e.simulation.currentTime} because: {e}"
                )
            if raiseGuardViolations and isinstance(e, GuardViolation):
                raise
            else:
                optionallyDebugRejection(e)
                return None

        # Completed the simulation without violating a requirement
        if not isinstance(simulation, Simulation):
            raise TypeError(f"simulator returned non-Simulation {simulation}")
        if verbosity >= 2:
            print(
                f"  Simulation {name} ended successfully at time step "
                f"{simulation.currentTime} because: {simulation.result.terminationReason}"
            )
        return simulation

    @abc.abstractmethod
    def createSimulation(self, scene, **kwargs):
        """Create a `Simulation` from a Scenic scene.

        This should be overridden by subclasses to return instances of their own
        specialized subclass of `Simulation`. The given **scene** and **kwargs**
        (together making up all the arguments passed to `simulate` except for
        **maxIterations**) should be passed through to the initializer of that
        instance.

        .. versionchanged:: 3.0

            This method is now called with all the arguments to `simulate` except for
            **maxIterations**; these should be passed through as described above.
        """
        return Simulation(scene, **kwargs)

    def destroy(self):
        """Clean up as needed when shutting down the simulator interface.

        Subclasses should call the parent implementation, which will catch this
        method being called twice on the same `Simulator`.
        """
        if self._destroyed:
            raise RuntimeError("Simulator.destroy() called twice")
        self._destroyed = True


class Simulation(abc.ABC):
    """A single simulation run.

    These objects are not manipulated manually, but are created by a `Simulator`.
    Simulator interfaces should subclass this class, implementing various abstract
    methods to call the appropriate simulator APIs. In particular, the following
    methods must be implemented:

        * `createObjectInSimulator`, to create an object;
        * `step`, to run the simulation for one time step;
        * `getProperties`, to read back the new state of an object.

    Other methods can be overridden if necessary, e.g. `setup` for initialization
    at the start of the simulation and `destroy` for cleanup afterward.

    .. versionchanged:: 3.0

        The ``__init__`` method of subclasses should no longer create objects;
        the `createObjectInSimulator` method will be called instead. Other
        initialization which needs to take place after object creation should be
        done in `setup` after calling the superclass implementation.

        The arguments to ``__init__`` are the same as those to `simulate`, except
        that ``maxIterations`` is omitted.

    Attributes:
        currentTime (int): Number of time steps elapsed so far.
        timestep (float): Length of each time step in seconds.
        objects: List of Scenic objects (instances of `Object`) existing in the
            simulation. This list will change if objects are created dynamically.
        agents: List of :term:`agents` in the simulation. An agent is any object that has
            or had a behavior at any point in the simulation. The agents list may have objects
            appended to the end as the simulation progresses (if a non-agent object has its
            behavior overridden), but once an object is in the agents list its position is fixed.
        result (`SimulationResult`): Result of the simulation, or `None` if it has not
            yet completed. This is the primary object which should be inspected to get
            data out of the simulation: the other undocumented attributes of this class
            are for internal use only.

    Raises:
        RejectSimulationException: if a requirement is violated.
    """

    def __init_subclass__(cls):
        super().__init_subclass__()

        if hasattr(cls, "run") or hasattr(cls, "createObject"):
            raise RuntimeError(
                f"{cls.__name__} implements old-style simulation API; "
                "see documentation for how to upgrade to support Scenic 3"
            )

    def __init__(
        self,
        scene,
        *,
        maxSteps,
        name,
        timestep,
        replay=None,
        enableReplay=True,
        allowPickle=False,
        enableDivergenceCheck=False,
        divergenceTolerance=0,
        continueAfterDivergence=False,
        verbosity=0,
    ):
        self.screen = None
        self.result = None
        self.scene = scene
        self.objects = []
        self.trajectory = []
        self.records = defaultdict(list)
        self.currentTime = 0
        self.timestep = 1 if timestep is None else float(timestep)
        self.verbosity = verbosity
        self.name = name
        self.worker_num = 0

        self.actionSequence = []

        # Prepare to save or load a replay.
        self.initializeReplay(replay, enableReplay, enableDivergenceCheck, allowPickle)
        self.divergenceTolerance = divergenceTolerance
        self.continueAfterDivergence = continueAfterDivergence

        # Do the actual setup and execution of the simulation inside a try-finally
        # statement so that we roll back global state even if an error occurs.
        try:
            # Prepare global veneer state for running the simulation.
            import scenic.syntax.veneer as veneer

            veneer.beginSimulation(self)
            dynamicScenario = self.scene.dynamicScenario

            # Create objects and perform simulator-specific initialization.
            self.setup()

            # Initialize the top-level dynamic scenario.
            dynamicScenario._start()

            # Update all objects in case the simulator has adjusted any dynamic
            # properties during setup.
            self.updateObjects()

            # Run the simulation.
            terminationType, terminationReason = self._run(dynamicScenario, maxSteps)

            # Stop all remaining scenarios.
            # (and reject if some 'require eventually' condition was never satisfied)
            for scenario in tuple(reversed(veneer.runningScenarios)):
                scenario._stop("simulation terminated")

            # Record finally-recorded values.
            values = dynamicScenario._evaluateRecordedExprs(
                RequirementType.recordFinal, self.currentTime
            )
            for name, val in values.items():
                self.records[name] = val

            # Package up simulation results into a compact object.
            result = SimulationResult(
                self.trajectory,
                self.actionSequence,
                terminationType,
                terminationReason,
                self.records,
            )
            self.result = result
        except (RejectSimulationException, RejectionException, GuardViolation) as e:
            # This simulation will be thrown out, but attach it to the exception
            # to aid in debugging.
            e.simulation = self
            raise
        finally:
            self.destroy()
            for obj in self.objects:
                disableDynamicProxyFor(obj)
            for agent in self.agents:
                if agent.behavior and agent.behavior._isRunning:
                    agent.behavior._stop()
            # If the simulation was terminated by an exception (including rejections),
            # some scenarios may still be running; we need to clean them up without
            # checking their requirements, which could raise rejection exceptions.
            for scenario in tuple(reversed(veneer.runningScenarios)):
                scenario._stop("exception", quiet=True)
            veneer.endSimulation(self)

    def _run(self, dynamicScenario, maxSteps):
        assert self.currentTime == 0

        while True:
            if self.verbosity >= 3:
                print(f"    Time step {self.currentTime}:")

            # Run compose blocks of compositional scenarios
            # (and check if any requirements defined therein fail)
            # N.B. if the top-level scenario completes, we don't immediately end
            # the simulation since we need to check if any monitors reject first.
            terminationReason = dynamicScenario._step()
            terminationType = TerminationType.scenarioComplete

            # Update observations of objects with sensors
            for obj in self.objects:
                if not obj.sensors:
                    continue
                obj.observations.update(
                    {key: sensor.getObservation() for key, sensor in obj.sensors.items()}
                )

            # Record current state of the simulation
            self.recordCurrentState()

            # Run monitors
            newReason = dynamicScenario._runMonitors()
            if newReason is not None:
                terminationReason = newReason
                terminationType = TerminationType.terminatedByMonitor

            # Check if users manually closed out display for simulator
            if "Dead" in str(self.screen):
                return (
                    TerminationType.terminatedByUser,
                    "user manually terminated simulation",
                )

            # "Always" and scenario-level requirements have been checked;
            # now safe to terminate if the top-level scenario has finished,
            # a monitor requested termination, or we've hit the timeout
            if terminationReason is not None:
                return terminationType, terminationReason
            terminationReason = dynamicScenario._checkSimulationTerminationConditions()
            if terminationReason is not None:
                return TerminationType.simulationTerminationCondition, terminationReason
            if maxSteps and self.currentTime >= maxSteps:
                return TerminationType.timeLimit, f"reached time limit ({maxSteps} steps)"

            # Clear lastActions for all objects
            for obj in self.objects:
                obj.lastActions = tuple()

            # Update agents with any objects that now have behaviors (and are not already agents)
            self.agents += [
                obj for obj in self.objects if obj.behavior and obj not in self.agents
            ]

            # Compute the actions of the agents in this time step
            allActions = defaultdict(tuple)
            schedule = self.scheduleForAgents()
            if not set(self.agents) == set(schedule):
                raise RuntimeError("Simulator schedule does not contain all agents")
            for agent in schedule:
                # If agent doesn't have a behavior right now, continue
                if not agent.behavior:
                    continue

                # Run the agent's behavior to get its actions
                actions = agent.behavior._step()

                # Handle pseudo-actions marking the end of a simulation/scenario
                if isinstance(actions, _EndSimulationAction):
                    return TerminationType.terminatedByBehavior, str(actions)
                elif isinstance(actions, _EndScenarioAction):
                    scenario = actions.scenario
                    if scenario._isRunning:
                        scenario._stop(actions)
                    if scenario is dynamicScenario:
                        # Top-level scenario was terminated, so whole simulation will end.
                        return TerminationType.terminatedByBehavior, str(actions)
                    actions = ()

                # Check ordinary actions for compatibility
                assert isinstance(actions, tuple)
                if len(actions) == 1 and isinstance(actions[0], (list, tuple)):
                    actions = tuple(actions[0])
                if not self.actionsAreCompatible(agent, actions):
                    raise InvalidScenarioError(
                        f"agent {agent} tried incompatible action(s) {actions}"
                    )

                # Save actions for execution below
                allActions[agent] = actions

                # Log lastActions
                agent.lastActions = actions

            # Execute the actions
            if self.verbosity >= 3:
                for agent, actions in allActions.items():
                    print(f"      Agent {agent} takes action(s) {actions}")
            self.actionSequence.append(allActions)
            self.executeActions(allActions)

            # Run the simulation for a single step and read its state back into Scenic
            self.step()
            self.currentTime += 1
            self.updateObjects()

    def setup(self):
        """Set up the simulation to run in the simulator.

        Subclasses may override this method to perform custom initialization,
        but should call the parent implementation to create the objects in the
        initial scene (through `createObjectInSimulator`).
        """
        self.agents = []
        for obj in self.scene.objects:
            self._createObject(obj)

    def initializeReplay(self, replay, enableReplay, enableDivergenceCheck, allowPickle):
        if replay:
            self.replaying = True
            self._replayIn = Serializer(replay, allowPickle=allowPickle, detectEnd=True)
            flags = ReplayMode(self._replayIn.readReplayHeader())
            self._checkDivergence = ReplayMode.checkDivergence in flags
        else:
            self.replaying = False
        if enableReplay:
            self._replayOut = Serializer(allowPickle=allowPickle)
            flags = 0
            if enableDivergenceCheck:
                flags |= ReplayMode.checkDivergence
                self._writeDivergenceData = True
            else:
                self._writeDivergenceData = False
            self._replayOut.writeReplayHeader(flags)
        else:
            self._replayOut = None

    def _createObject(self, obj):
        if self.verbosity >= 3:
            print(f"      Creating object {obj}")

        # Add the new object to our lists.
        self.objects.append(obj)
        if obj.behavior:
            self.agents.append(obj)

        # Enable dynamic proxy for the object so that any mutations will not
        # affect the original object (e.g. if the simulator sets some of its
        # properties below).
        enableDynamicProxyFor(obj)

        # Ask subclass to actually create the object in the simulator.
        # (This may fail by raising an exception.)
        self.createObjectInSimulator(obj)

        # Allow the object to do simulator-specific initialization.
        obj.startDynamicSimulation()

    @abc.abstractmethod
    def createObjectInSimulator(self, obj):
        """Create the given object in the simulator.

        Implemented by subclasses. Should raise `SimulationCreationError` if creating
        the object fails.

        Args:
            obj (Object): the Scenic object to create.

        Raises:
            SimulationCreationError: if unable to create the object in the simulator.
        """
        raise NotImplementedError

    def recordCurrentState(self):
        dynamicScenario = self.scene.dynamicScenario
        records = self.records

        # Record initially-recorded values
        step = self.currentTime
        if step == 0:
            values = dynamicScenario._evaluateRecordedExprs(
                RequirementType.recordInitial, step
            )
            for name, val in values.items():
                records[name] = val

        # Record time-series values
        values = dynamicScenario._evaluateRecordedExprs(RequirementType.record, step)
        for name, val in values.items():
            records[name].append((self.currentTime, val))

        self.trajectory.append(self.currentState())

    def replayCanContinue(self):
        if not self.replaying:
            return False
        self.detectReplayEnd()  # updates self.replaying
        return self.replaying

    def detectReplayEnd(self):
        if not self._replayIn.atEnd():
            return
        self.replaying = False
        if self.verbosity >= 2:
            print(f"    Continuing past end of replay at time step {self.currentTime}")

    def recordSampledValue(self, dist, values):
        if self._replayOut:
            dist.serializeValue(values, self._replayOut)

    def replaySampledValue(self, dist, values):
        return dist.deserializeValue(self._replayIn, values)

    def scheduleForAgents(self):
        """Compute the order for the agents to run in the next time step.

        The default order is the order in which the agents were created.

        Returns:
            An :term:`iterable` which is a permutation of ``self.agents``.
        """
        return self.agents

    def actionsAreCompatible(self, agent, actions):
        """Check whether the given actions can be taken simultaneously by an agent.

        The default is to consider all actions compatible with each other, and to
        call `Action.canBeTakenBy` to determine if an agent can take an action.
        Subclasses should override this method as appropriate.

        Args:
            agent (Object): the agent which wants to take the given actions.
            actions (tuple): tuple of :term:`actions` to be taken.
        """
        for action in actions:
            if not action.canBeTakenBy(agent):
                return False
        return True

    def executeActions(self, allActions):
        """Execute the actions selected by the agents.

        The default implementation calls the `applyTo` method of each `Action` to apply
        it to the appropriate agent.
        Subclasses may override this method to make additional simulator API calls as
        needed, but should call this implementation too or otherwise emulate its
        functionality.

        Args:
            allActions: a :obj:`~collections.defaultdict` mapping each agent to a tuple
                of actions, with the default value being an empty tuple. The order of
                agents in the dict should be respected in case the order of actions matters.
        """
        for agent, actions in allActions.items():
            for action in actions:
                action.applyTo(agent, self)

    @abc.abstractmethod
    def step(self):
        """Run the simulation for one step and return the next trajectory element.

        Implemented by subclasses. This should cause the simulator to simulate physics
        for ``self.timestep`` seconds.
        """
        raise NotImplementedError

    def updateObjects(self):
        """Update the positions and other properties of objects from the simulation.

        Subclasses likely do not need to override this method: they should implement its
        subroutine `getProperties` below.
        """
        for obj in self.objects:
            # Get latest values of dynamic properties from simulation and assign them
            dynTypes = obj._simulatorProvidedProperties
            properties = set(dynTypes)
            values = self.getProperties(obj, properties)
            assert properties == set(values), properties ^ set(values)
            for prop, value in values.items():
                # Check new value has the expected type
                ty = dynTypes[prop]
                if ty is float and isinstance(value, numbers.Real):
                    # Special case for scalars so that we don't penalize simulator interfaces
                    # for returning ints, NumPy scalar types, etc.
                    value = float(value)
                elif ty is type(None):
                    # Special case for properties with initial value None: the simulator sets
                    # their actual initial value, so we'll assume the type is correct here.
                    ty = type(value)
                    dynTypes[prop] = ty
                if not isinstance(value, ty):
                    actual = type(value).__name__
                    expected = ty.__name__
                    raise RuntimeError(
                        f'simulator provided value for property "{prop}" '
                        f"with type {actual} instead of expected {expected}"
                    )

                # Assign the new value
                setattr(obj, prop, value)

            # If saving a replay with divergence-checking support, save all the new values;
            # if running a replay with such support, check for divergence.
            if self._replayOut and self._writeDivergenceData:
                for prop, ty in dynTypes.items():
                    self._replayOut.writeValue(values[prop], ty)
            if self.replayCanContinue() and self._checkDivergence:
                for prop, ty in dynTypes.items():
                    expected = self._replayIn.readValue(ty)
                    actual = values[prop]
                    if self.valuesHaveDiverged(obj, prop, expected, actual):
                        msg = (
                            f'expected "{prop}" of {obj} to have value '
                            f"{expected}, but got {actual}"
                        )
                        if self.continueAfterDivergence:
                            if self.verbosity >= 2:
                                print(
                                    f"    Continuing past divergence at time step "
                                    f"{self.currentTime} ({msg})"
                                )
                            self.replaying = False
                            break
                        else:
                            raise DivergenceError(msg)

            # Recompute dynamic final properties
            obj._recomputeDynamicFinals()

            # Clear caches to ensure that cached properties like visibleRegion, etc.
            # are recomputed
            obj._clearCaches()

    def valuesHaveDiverged(self, obj, prop, expected, actual):
        """Decide whether the value of a dynamic property has diverged from the replay.

        The default implementation considers scalar and vector properties to have diverged
        if the distance between the actual and expected values is greater than
        ``self.divergenceTolerance`` (which is 0 by default); other types of properties
        use the != operator.

        Subclasses may override this function to provide more specialized criteria (e.g.
        allowing some properties to diverge more than others).

        Args:
            obj (Object): The object being considered.
            prop (str): The name of the :term:`dynamic property` being considered.
            expected: The value of the property saved in the replay currently being run.
            actual: The value of the property in the current simulation.

        Returns:
            `True` if the actual value should be considered as having diverged from the
            expected one; otherwise `False`.
        """
        diff = None
        if isinstance(expected, numbers.Real):
            diff = actual - expected
        elif isinstance(expected, Vector):
            diff = (actual - expected).norm()
        if diff:
            return diff > self.divergenceTolerance
        else:
            return actual != expected

    @abc.abstractmethod
    def getProperties(self, obj, properties):
        """Read the values of the given properties of the object from the simulator.

        Implemented by subclasses.

        Args:
            obj (Object): Scenic object in question.
            properties (set): Set of names of properties to read from the simulator.
                It is safe to destructively iterate through the set if you want.

        Returns:
            A `dict` mapping each of the given properties to its current value.
        """
        raise NotImplementedError

    def currentState(self):
        """Return the current state of the simulation.

        The definition of 'state' is up to the simulator; the 'state' is simply saved
        at each time step to define the 'trajectory' of the simulation. Changing this
        method is however discouraged, unless one is adding additional attributes to
        the returned ``SimulationState`` object.

        The default implementation returns a custom ``SimulationState`` object, which is a tuple
        of positions of all objects (for backwards compatibility) and also has two attributes:
        ``positions`` and ``orientations``, which are themselves tuples of the positions and
        orientations of all objects.
        """

        class SimulationState(tuple):
            def __new__(cls, positions, orientations):
                return super().__new__(cls, positions)

            def __init__(self, positions, orientations):
                self.positions = positions
                self.orientations = orientations

        positions = tuple(obj.position for obj in self.objects)
        orientation = tuple(obj.orientation for obj in self.objects)

        return SimulationState(positions, orientation)

    @property
    def currentRealTime(self):
        """Current simulation time, in seconds."""
        return self.currentTime * self.timestep

    def destroy(self):
        """Perform any cleanup necessary to reset the simulator after a simulation.

        The default implementation does nothing by default; it may be overridden
        by subclasses.
        """
        pass

    def getReplay(self):
        """Encode this simulation to a `bytes` object for future replay.

        Requires that the simulation was run with ``enableReplay=True`` (the default).
        """
        if not self._replayOut:
            raise RuntimeError("cannot save replay without replay support enabled")
        return self._replayOut.getBytes()


class ReplayMode(enum.IntFlag):
    checkDivergence = enum.auto()


class DummySimulator(Simulator):
    """Simulator which does (almost) nothing, for testing and debugging purposes.

    To allow testing the change of dynamic properties over time, all objects drift
    upward by **drift** every time step.
    """

    def __init__(self, drift=0):
        super().__init__()
        self.drift = drift

    def createSimulation(self, scene, **kwargs):
        return DummySimulation(scene, drift=self.drift, **kwargs)


class DummySimulation(Simulation):
    """Minimal `Simulation` subclass for `DummySimulator`."""

    def __init__(self, scene, drift=0, **kwargs):
        self.drift = drift
        super().__init__(scene, **kwargs)

    def createObjectInSimulator(self, obj):
        pass

    def actionsAreCompatible(self, agent, actions):
        return True  # Allow non-Action actions for testing purposes

    def executeActions(self, allActions):
        pass

    def step(self):
        for obj in self.objects:
            obj.position += Vector(0, self.drift)

    def getProperties(self, obj, properties):
        vals = dict(
            position=obj.position,
            yaw=obj.yaw,
            pitch=obj.pitch,
            roll=obj.roll,
            velocity=Vector(0, 0, 0),
            angularVelocity=Vector(0, 0, 0),
            speed=0.0,
            angularSpeed=0.0,
        )
        for prop in properties:
            if prop not in vals:
                vals[prop] = None
        return vals


@enum.unique
class TerminationType(enum.Enum):
    """Enum describing the possible ways a simulation can end."""

    #: Simulation reached the specified time limit.
    timeLimit = "reached simulation time limit"

    #: The top-level scenario finished executing.
    #:
    #: (Either its :keyword:`compose` block completed, one of its termination
    #: conditions was met, or it was terminated with :keyword:`terminate`.)
    scenarioComplete = "the top-level scenario finished"

    #: A user-specified simulation termination condition was met.
    simulationTerminationCondition = "a simulation termination condition was met"

    #: A :term:`monitor` used :keyword:`terminate simulation` to end the simulation.
    terminatedByMonitor = "a monitor terminated the simulation"

    #: A :term:`dynamic behavior` used :keyword:`terminate simulation` to end the simulation.
    terminatedByBehavior = "a behavior terminated the simulation"

    #: A user manually intervenes and closes display window
    terminatedByUser = "manually terminated by user"


class SimulationResult:
    """Result of running a simulation.

    Attributes:
        trajectory: A tuple giving for each time step the simulation's 'state': by
            default the positions of every object. See `Simulation.currentState`.
        finalState: The last 'state' of the simulation, as above.
        actions: A tuple giving for each time step a dict specifying for each agent the
            (possibly-empty) tuple of actions it took at that time step.
        terminationType (`TerminationType`): The way the simulation ended.
        terminationReason (str): A human-readable string giving the reason why the
            simulation ended, possibly including debugging info.
        records (dict): For each :keyword:`record` statement, the value or time series of
            values its expression took during the simulation.
    """

    def __init__(self, trajectory, actions, terminationType, terminationReason, records):
        self.trajectory = tuple(trajectory)
        assert self.trajectory
        self.finalState = self.trajectory[-1]
        self.actions = tuple(actions)
        self.terminationType = terminationType
        self.terminationReason = str(terminationReason)
        self.records = dict(records)
