"""Support for hard and soft requirements."""

from abc import ABC, abstractmethod
import enum
from functools import reduce
import inspect
import itertools

import fcl
import numpy
import rv_ltl
import trimesh

from scenic.core.distributions import Samplable, needsSampling, toDistribution
from scenic.core.errors import InvalidScenarioError
from scenic.core.lazy_eval import needsLazyEvaluation
from scenic.core.propositions import Atomic, PropositionNode
from scenic.core.utils import DefaultIdentityDict
import scenic.syntax.relations as relations


@enum.unique
class RequirementType(enum.Enum):
    # requirements which must hold during initial sampling
    require = "require"

    # requirements used only during simulation
    monitor = "require monitor"
    terminateWhen = "terminate when"
    terminateSimulationWhen = "terminate simulation when"

    # recorded values, which aren't requirements but are handled similarly
    record = "record"
    recordInitial = "record initial"
    recordFinal = "record final"

    @property
    def constrainsSampling(self):
        return self in (self.require,)


class PendingRequirement:
    def __init__(self, ty, condition, line, prob, name, ego, recConfig, scenario):
        self.ty = ty
        self.condition = condition
        self.line = line
        self.prob = prob
        self.name = name
        self.recConfig = recConfig

        # the translator wrapped the requirement in a lambda to prevent evaluation,
        # so we need to save the current values of all referenced names; we save
        # the ego object too since it can be referred to implicitly

        # condition is an instance of Proposition. Flatten to get a list of atomic propositions.
        atoms = condition.atomics()
        self.globalBindings = {}  # bindings to global/builtin names
        self.closureBindings = {}  # bindings to top-level closure variables
        self.cells = []  # cells used in referenced closures
        atomGlobals = None
        for atom in atoms:
            gbindings, cbindings, closures = getNameBindings(atom.closure)
            self.globalBindings.update(gbindings)
            self.closureBindings.update(cbindings)
            for closure in closures:
                self.cells.extend(closure.__closure__)
            globs = atom.closure.__globals__
            if atomGlobals is not None:
                assert globs is atomGlobals
            else:
                atomGlobals = globs
        for cell in self.cells:
            # save current values of scenario locals (only needed for top-level scenario)
            if cell.cell_contents is scenario:
                cell.cell_contents = scenario._makeLocalsSnapshot()
        self.egoObject = ego

    def compile(self, namespace, scenario, syntax=None):
        """Create a closure testing the requirement in the correct runtime state.

        While we're at it, determine whether the requirement implies any relations
        we can use for pruning, and gather all of its dependencies.
        """
        globalBindings, closureBindings = self.globalBindings, self.closureBindings
        cells, ego, line = self.cells, self.egoObject, self.line
        condition, ty = self.condition, self.ty

        # Convert bound values to distributions as needed
        for name, value in globalBindings.items():
            globalBindings[name] = toDistribution(value)
        for name, value in closureBindings.items():
            closureBindings[name] = toDistribution(value)
        cells = tuple((cell, toDistribution(cell.cell_contents)) for cell in cells)
        allBindings = dict(globalBindings)
        allBindings.update(closureBindings)

        # Check whether requirement implies any relations used for pruning
        canPrune = condition.check_constrains_sampling()
        if canPrune:
            relations.inferRelationsFrom(syntax, allBindings, ego, line)

        # Gather dependencies of the requirement
        deps = set()
        cellVals = (value for cell, value in cells)
        for value in itertools.chain(allBindings.values(), cellVals):
            if needsSampling(value):
                deps.add(value)
            if needsLazyEvaluation(value):
                raise InvalidScenarioError(
                    f"{ty} on line {line} uses value {value}"
                    " undefined outside of object definition"
                )

        # If this requirement contains the CanSee specifier, we will need to sample all objects
        # to meet the dependencies.
        if "CanSee" in globalBindings:
            deps.update(scenario.objects)

        if ego is not None:
            assert isinstance(ego, Samplable)
            deps.add(ego)

        # Construct closure
        def closure(values, monitor=None):
            # rebind any names referring to sampled objects (for require statements,
            # rebind all names, since we want their values at the time the requirement
            # was created)
            # note: need to extract namespace here rather than close over value
            # from above because of https://github.com/uqfoundation/dill/issues/532
            namespace = condition.atomics()[0].closure.__globals__
            for name, value in globalBindings.items():
                if ty == RequirementType.require or value in values:
                    namespace[name] = values[value]
            for cell, value in cells:
                cell.cell_contents = values[value]

            # rebind ego object, which can be referred to implicitly
            boundEgo = None if ego is None else values[ego]
            # evaluate requirement condition, reporting errors on the correct line
            import scenic.syntax.veneer as veneer

            with veneer.executeInRequirement(scenario, boundEgo, values):
                if monitor is None:
                    # if not temporal evaluation
                    result = condition.evaluate()
                else:
                    # if temporal evaluation
                    result = monitor.update()
                assert not needsSampling(result)
                if needsLazyEvaluation(result):
                    raise InvalidScenarioError(
                        f"{ty} on line {line} uses value"
                        " undefined outside of object definition"
                    )
            return result

        return CompiledRequirement(self, closure, deps, condition)


def getNameBindings(req, restrictTo=None):
    """Find all names the given lambda depends on, along with their current bindings."""
    namespace = req.__globals__
    if restrictTo is not None and restrictTo is not namespace:
        return {}, {}, ()
    externals = inspect.getclosurevars(req)
    globalBindings = externals.builtins

    closures = set()
    if externals.nonlocals:
        closures.add(req)

    def handleFunctions(bindings):
        for value in bindings.values():
            if inspect.isfunction(value):
                if value.__closure__ is not None:
                    closures.add(value)
                subglobs, _, _ = getNameBindings(value, restrictTo=namespace)
                for name, value in subglobs.items():
                    if name in globalBindings:
                        assert value is globalBindings[name]
                    else:
                        globalBindings[name] = value

    globalBindings.update(externals.globals)
    handleFunctions(externals.globals)
    handleFunctions(externals.nonlocals)
    return globalBindings, externals.nonlocals, closures


class BoundRequirement:
    def __init__(self, compiledReq, sample, proposition):
        self.ty = compiledReq.ty
        self.closure = compiledReq.closure
        self.line = compiledReq.line
        self.name = compiledReq.name
        self.recConfig = compiledReq.recConfig
        self.sample = sample
        self.compiledReq = compiledReq
        self.proposition = proposition

    def isTrue(self):
        return self.value()

    def value(self):
        one_time_monitor = self.proposition.create_monitor()
        return self.closure(self.sample, one_time_monitor)

    def evaluate(self):
        return self.closure(self.sample)

    def __str__(self):
        if self.name:
            return self.name
        else:
            return f'"{self.ty.value}" on line {self.line}'

    def toMonitor(self):
        return MonitorRequirement(self.compiledReq, self.sample, self.proposition)


class MonitorRequirement(BoundRequirement):
    """MonitorRequirement is a BoundRequirement with temporal proposition monitor"""

    def __init__(self, compiledReq, sample, proposition):
        super().__init__(compiledReq, sample, proposition)
        self.monitor = self.proposition.create_monitor()
        self.lastValue = rv_ltl.B4.TRUE

    def value(self):
        self.lastValue = self.closure(self.sample, self.monitor)
        return self.lastValue


class DynamicRequirement:
    def __init__(self, ty, condition, line, name=None):
        self.ty = ty
        self.line = line
        self.name = name

        import scenic.syntax.veneer as veneer

        scenario = veneer.currentScenario

        def closure(monitor=None):
            with veneer.executeInScenario(scenario):
                if monitor is None:
                    result = self.condition.evaluate()
                else:
                    result = monitor.update()
                return result

        self.closure = closure
        self.condition = condition

    def isTrue(self):
        return self.value()

    def value(self):
        return self.closure()

    def __str__(self):
        if self.name:
            return self.name
        else:
            return f'"{self.ty.value}" on line {self.line}'

    def toMonitor(self):
        return DynamicMonitorRequirement(
            self.closure, self.condition, self.line, self.name
        )


class DynamicMonitorRequirement:
    def __init__(self, closure, condition, line, name):
        self.line = line
        self.closure = closure
        self.name = name
        self.condition = condition
        self.monitor = self.condition.create_monitor()
        self.lastValue = rv_ltl.B4.TRUE

    def isTrue(self):
        return self.value()

    def value(self):
        self.lastValue = self.closure(self.monitor)
        return self.lastValue

    def evaluate(self):
        return self.closure()

    def __str__(self):
        if self.name:
            return self.name
        else:
            return f'"{self.ty.value}" on line {self.line}'


## Builtin Requirements
class SamplingRequirement(ABC):
    """A requirement to be checked to validate a sample.

    Args:
        optional: Whether or not this requirement must be
            checked to validate the sample. Optional samples
            can be checked, and if ``False`` imply that the
            sample is invalid, but do not need to be checked
            if all non-optional requirements are satisfied.
    """

    def __init__(self, optional):
        self.optional = optional
        self.active = True

    @abstractmethod
    def falsifiedByInner(self, sample):
        """Returns False if the requirement is falsifed, True otherwise"""

    def falsifiedBy(self, sample):
        assert self.active
        return self.falsifiedByInner(sample)

    @property
    @abstractmethod
    def violationMsg(self):
        """Message to be printed if the requirement is violated"""
        pass


class IntersectionRequirement(SamplingRequirement):
    """Requirement that a pair of objects do not intersect."""

    def __init__(self, objA, objB, optional=False):
        super().__init__(optional=optional)
        self.objA = objA
        self.objB = objB

    def falsifiedByInner(self, sample):
        objA = sample[self.objA]
        objB = sample[self.objB]
        if objA.allowCollisions or objB.allowCollisions:
            return False
        return objA.intersects(objB)

    @property
    def violationMsg(self):
        return f"Intersection violation: {self.objA} intersects {self.objB}"


class BlanketCollisionRequirement(SamplingRequirement):
    """Requirement that the surfaces of a given set of objects do not intersect.

    We can check for such intersections more quickly than full objects using FCL,
    but since FCL checks for surface intersections rather than volume intersections
    (in general), this requirement being satisfied does not imply that the objects
    do not intersect (one might still be contained in another). Therefore, this
    requirement is intended to quickly check for intersections in the common case
    rather than completely determine whether any objects collide.
    """

    def __init__(self, objects, optional=True):
        super().__init__(optional=optional)
        self.objects = objects
        self._collidingObjects = None

    def falsifiedByInner(self, sample):
        objects = tuple(sample[obj] for obj in self.objects)
        manager = fcl.DynamicAABBTreeCollisionManager()
        objForGeom = {}
        for i, obj in enumerate(objects):
            if obj.allowCollisions:
                continue
            geom, trans = obj.occupiedSpace._fclData
            collisionObject = fcl.CollisionObject(geom, trans)
            objForGeom[geom] = obj
            manager.registerObject(collisionObject)

        manager.setup()
        cdata = fcl.CollisionData()
        manager.collide(cdata, fcl.defaultCollisionCallback)
        collision = cdata.result.is_collision

        if collision:
            contact = cdata.result.contacts[0]
            self._collidingObjects = (objForGeom[contact.o1], objForGeom[contact.o2])

        return collision

    @property
    def violationMsg(self):
        assert self._collidingObjects is not None
        objA, objB = self._collidingObjects
        return f"Blanket Intersection violation: {objA} intersects {objB}"


class ContainmentRequirement(SamplingRequirement):
    def __init__(self, obj, container, optional=False):
        super().__init__(optional=optional)
        self.obj = obj
        self.container = container

    def falsifiedByInner(self, sample):
        obj = sample[self.obj]
        container = sample[self.container]
        return not container.containsObject(obj)

    @property
    def violationMsg(self):
        return f"Containment violation: {self.obj} is not contained in its container"


class VisibilityRequirement(SamplingRequirement):
    def __init__(self, source, target, objects, optional=False):
        super().__init__(optional=optional)
        self.source = source
        self.target = target
        self.potential_occluders = tuple(
            obj for obj in objects if obj is not self.source and obj is not self.target
        )

    def falsifiedByInner(self, sample):
        source = sample[self.source]
        target = sample[self.target]
        potential_occluders = tuple(sample[obj] for obj in self.potential_occluders)
        occluders = tuple(obj for obj in potential_occluders if obj.occluding)
        return not source.canSee(target, occludingObjects=occluders)

    @property
    def violationMsg(self):
        return f"Visibility violation: {self.target} is not visible from {self.source}"


class NonVisibilityRequirement(VisibilityRequirement):
    def falsifiedByInner(self, sample):
        return not super().falsifiedByInner(sample)

    @property
    def violationMsg(self):
        return f"Non-visibility violation: {self.target} is visible from {self.source}"


class CompiledRequirement(SamplingRequirement):
    def __init__(self, pendingReq, closure, dependencies, proposition):
        super().__init__(optional=False)
        self.ty = pendingReq.ty
        self.closure = closure
        self.line = pendingReq.line
        self.name = pendingReq.name
        self.prob = pendingReq.prob
        self.recConfig = pendingReq.recConfig
        self.dependencies = dependencies
        self.proposition = proposition

    @property
    def constrainsSampling(self):
        return self.ty.constrainsSampling

    def falsifiedByInner(self, sample):
        one_time_monitor = self.proposition.create_monitor()
        return self.closure(sample, one_time_monitor) == rv_ltl.B4.FALSE

    def evaluate(self):
        # Used only for `terminate when`, etc. defined in setup blocks of subscenarios
        return self.closure(DefaultIdentityDict())

    def __str__(self):
        if self.name:
            return self.name
        else:
            return f'"{self.ty.value}" on line {self.line}'

    @property
    def violationMsg(self):
        return f"User requirement violation: {self}"
