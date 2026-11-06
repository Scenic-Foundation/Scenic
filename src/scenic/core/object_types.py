"""Implementations of the built-in Scenic classes.

Defines the 3 Scenic classes `Point`, `OrientedPoint`, and `Object`, and associated
helper code (notably their base class `Constructible`, which implements the handling of
property definitions and :ref:`specifier resolution`).

.. warning::

    In :ref:`2D compatibility mode`, these classes are overwritten with 2D analogs. While
    we make an effort to map imports to the correct class, this only works if imports
    use the form ``import scenic.core.object_types as object_types`` followed by accessing
    ``object_types.Object``. If you instead use ``from scenic.core.object_types import Object``,
    you may get the wrong class.

"""

from abc import ABC, abstractmethod
import collections
import functools
import inspect
import math
import random
import typing
import warnings

import numpy as np
import shapely
import shapely.affinity
import trimesh

from scenic.core.distributions import (
    FunctionDistribution,
    MultiplexerDistribution,
    RandomControlFlowError,
    Samplable,
    distributionFunction,
    distributionMethod,
    needsSampling,
    supportInterval,
    toDistribution,
)
from scenic.core.errors import InvalidScenarioError, SpecifierError
from scenic.core.geometry import (
    averageVectors,
    hypot,
    max,
    min,
    normalizeAngle,
    pointIsInCone,
)
from scenic.core.lazy_eval import (
    LazilyEvaluable,
    isLazy,
    needsLazyEvaluation,
    valueInContext,
)
from scenic.core.regions import (
    BoxRegion,
    CircularRegion,
    EmptyRegion,
    IntersectionRegion,
    MeshSurfaceRegion,
    MeshVolumeRegion,
    PolygonalRegion,
    Region,
    SectorRegion,
    SpheroidRegion,
    ViewRegion,
    convertToFootprint,
)
from scenic.core.serialization import dumpAsScenicCode
from scenic.core.shapes import BoxShape, MeshShape, Shape
from scenic.core.specifiers import ModifyingSpecifier, PropertyDefault, Specifier
from scenic.core.type_support import (
    toHeading,
    toOrientation,
    toScalar,
    toType,
    toVector,
    underlyingType,
)
from scenic.core.utils import DefaultIdentityDict, cached, cached_method, cached_property
from scenic.core.vectors import (
    Orientation,
    Vector,
    alwaysGlobalOrientation,
    globalOrientation,
)
from scenic.core.visibility import canSee

## Types
#: Type alias for an interval (a pair of floats).
Interval = typing.Tuple[float, float]
#: Type alias for limits on dimensions (a triple of intervals).
DimensionLimits = typing.Tuple[Interval, Interval, Interval]

## Abstract base class


class Constructible(Samplable):
    """Abstract base class for Scenic objects.

    Scenic objects, which are constructed using specifiers, are implemented
    internally as instances of ordinary Python classes. This abstract class
    implements the procedure to resolve specifiers and determine values for
    the properties of an object, as well as several common methods supported
    by objects.

    .. warning::

        This class is an implementation detail, and none of its methods should be
        called directly from a Scenic program.
    """

    _dynamicProperties = {}

    def __init_subclass__(cls):
        super().__init_subclass__()

        if "_defaults" in cls.__dict__:
            # This class is being unpickled by value; the pickled class already was
            # transformed by __init_subclass__, so we skip it now.
            return

        # Identify cached properties/methods which will need to be cleared
        # each time step during dynamic simulations.
        clearers = {}
        for attr, value in cls.__dict__.items():
            if isinstance(value, property):
                value = value.fget
            if clearer := getattr(value, "_scenic_cache_clearer", None):
                clearers[attr] = clearer
        for sc in cls.__mro__:
            if sclearers := getattr(sc, "_cache_clearers", None):
                for attr, clearer in sclearers.items():
                    if attr not in clearers:
                        clearers[attr] = clearer
        cls._cache_clearers = clearers

        # Find all defaults provided by the class or its superclasses
        allDefs = collections.defaultdict(list)

        for sc in cls.__mro__:
            if issubclass(sc, Constructible) and hasattr(sc, "_scenic_properties"):
                for prop, value in sc._scenic_properties.items():
                    allDefs[prop].append(PropertyDefault.forValue(value))

        # Resolve conflicting defaults and gather dynamic properties
        resolvedDefs = {}
        dyns = []
        finals = []
        dynFinals = {}
        for prop, defs in allDefs.items():
            primary, rest = defs[0], defs[1:]
            spec = primary.resolveFor(prop, rest)
            resolvedDefs[prop] = spec

            if isDynamic := any(defn.isDynamic for defn in defs):
                dyns.append(prop)
            if primary.isFinal:
                finals.append(prop)
                if isDynamic:
                    dynFinals[prop] = primary.value
        cls._defaults = resolvedDefs
        cls._finalProperties = frozenset(finals)

        # Determine types of dynamic properties
        dynTypes = {}
        defaultValues = None  # compute only if necessary
        for prop in dyns:
            ty = super(cls, cls)._dynamicProperties.get(prop)
            if not ty:
                # First time this property has been defined; get the type of
                # its default value.
                if not defaultValues:
                    # N.B. Here we evaluate the default value expressions, which is
                    # risky since global state like the workspace may not have been set
                    # up yet. For this reason we only compute default values when they
                    # are actually needed; a better solution would be to have syntax for
                    # annotating the types of dynamic properties.
                    defaultValues, _ = cls._resolveSpecifiers(())
                ty = underlyingType(defaultValues[prop])
            dynTypes[prop] = ty
        cls._dynamicProperties = dynTypes
        cls._simulatorProvidedProperties = {
            prop: val
            for prop, val in cls._dynamicProperties.items()
            if prop not in cls._finalProperties
        }

        # Extract order in which to recompute dynamic final properties each time step
        if defaultValues:
            recomputers = {}
            for prop in defaultValues:  # order is that from specifier resolution
                if prop in dynFinals:
                    recomputers[prop] = dynFinals[prop]
            cls._dynamicFinalProperties = recomputers
        else:
            # No new dynamic properties: just inherit the order from the superclass
            pass

    def __new__(cls, *args, _internal=False, **kwargs):
        if not _internal:
            # Catch users trying to instantiate a Scenic class like a Python class
            raise InvalidScenarioError('Scenic classes must be instantiated with "new"')
        return super().__new__(cls)

    def __getnewargs_ex__(self):
        return ((), dict(_internal=True))

    def __init__(self, properties, constProps=frozenset(), _internal=False):
        for prop, value in properties.items():
            assert not needsLazyEvaluation(value), (prop, value)
            object.__setattr__(self, prop, value)
        super().__init__(properties.values())
        self.properties = tuple(sorted(properties.keys()))
        self._propertiesSet = set(self.properties)
        self._constProps = constProps
        self._sampleParent = None

    @classmethod
    def _withProperties(cls, properties, constProps=None):
        """Create an instance with the given property values.

        Values of unspecified properties are determined by specifier resolution
        as usual.
        """
        specs = []
        for prop, val in properties.items():
            specs.append(Specifier(f"<internal({prop})>", {prop: 1}, {prop: val}))
        return cls._withSpecifiers(specs, constProps=constProps, register=False)

    @classmethod
    def _with(cls, **properties):
        # Shorthand form of _withProperties
        return cls._withProperties(properties)

    @classmethod
    def _withSpecifiers(cls, specifiers, constProps=None, register=True):
        """Create an instance from the given specifiers."""
        # Resolve specifiers
        newspecs = cls._prepareSpecifiers(specifiers)
        properties, consts = cls._resolveSpecifiers(newspecs)
        if constProps is None:
            constProps = consts

        # Catch properties which would conflict with ordinary attributes
        for prop in properties:
            if hasattr(cls, prop):
                raise SpecifierError(
                    f"Property {prop} would overwrite an attribute with the same name."
                )

        # Create the object
        obj = cls(properties, constProps=constProps, _internal=True)

        # Possibly register this object
        if register:
            obj._register()

        return obj

    @classmethod
    def _prepareSpecifiers(cls, specifiers):
        # This is a hook for subclasses to modify the specifier list.
        return specifiers

    @classmethod
    def _resolveSpecifiers(cls, specifiers, defaults=None, overriding=False):
        specifiers = list(specifiers)

        # Declare properties dictionary which maps properties to the specifier
        # that will specify that property.
        properties = dict()

        # Declare modifying dictionary, which maps properties to a specifier
        # that will modify that property.
        modifying = dict()

        # Dictionary mapping properties set so far to the priority with which they have
        # been set.
        priorities = dict()

        # Extract default property values dictionary and set of final properties,
        # unless defaults is overriden.
        if defaults is None:
            defaults = cls._defaults

        finals = cls._finalProperties

        # Check for incompatible specifier combinations
        specifiers_count = collections.Counter(spec.name for spec in specifiers)

        for spec in specifiers_count:
            if specifiers_count[spec] > 1:
                raise SpecifierError(f"Cannot use {spec} specifier to modify itself.")

        # Split the specifiers into two groups, normal and modifying. Normal specifiers set all relevant properties
        # first. Then modifying specifiers can modify or set additional properties
        normal_specifiers = [
            spec for spec in specifiers if not isinstance(spec, ModifyingSpecifier)
        ]
        modifying_specifiers = [
            spec for spec in specifiers if isinstance(spec, ModifyingSpecifier)
        ]

        # For each property specified by a normal specifier:
        #   - If not in properties specified, properties[p] = specifier
        #   - Otherwise, if property specified, check if specifier's priority is higher. If so, replace it with specifier

        # Priorties are inversed: A lower priority number means semantically that it has a higher priority level
        for spec in normal_specifiers:
            assert isinstance(spec, Specifier), (name, spec)

            # Iterate over each property.
            for prop in spec.priorities:
                # Check if this is a final property that has been specified.
                if prop in finals:
                    raise SpecifierError(
                        f'property "{prop}" cannot be directly specified'
                    )

                if prop in properties:
                    # This property already exists. Check that it has not already been specified
                    # at equal priority level. Then if it was previously specified at a lower priority
                    # level, override it with the value that this specifier sets.
                    if spec.priorities[prop] == priorities[prop]:
                        raise SpecifierError(
                            f'property "{prop}" specified twice with the same priority'
                        )
                    if spec.priorities[prop] < priorities[prop]:
                        properties[prop] = spec
                        priorities[prop] = spec.priorities[prop]
                else:
                    # This property has not already been specified, so we should initialize it.
                    properties[prop] = spec
                    priorities[prop] = spec.priorities[prop]

        # If a modifying specifier specifies the property with a higher priority,
        # set the object's property to be specified by the modifying specifier. Otherwise,
        # if the property exists and has already been specified at a higher or equal priority,
        # then the resulting value is modified by the modifying specifier.

        # If the property is not yet being specified, the modifying specifier will
        # act as a normal specifier for that property.
        for spec in modifying_specifiers:
            for prop in spec.priorities:
                # Now we check if the propert has already been specified
                if prop in properties:
                    # This property has already been specified, so we should either modify
                    # it or specify it.
                    if spec.priorities[prop] < priorities[prop]:
                        # Higher priority level, so it specifies
                        properties[prop] = spec
                        priorities[prop] = spec.priorities[prop]
                    elif prop in spec.modifiable_props:
                        # This specifer can modify this prop, so we set it to do so after
                        # first checking it has not already been modified.
                        if prop in modifying:
                            raise SpecifierError(
                                f'property "{prop}" of {name} modified twice.'
                            )

                        modifying[prop] = spec
                else:
                    # This property has not been specified, so we should specify it.
                    properties[prop] = spec
                    priorities[prop] = spec.priorities[prop]

        # Add any default specifiers needed
        _defaultedProperties = set()
        for prop, default_spec in defaults.items():
            if prop not in priorities:
                specifiers.append(default_spec)
                properties[prop] = default_spec
                _defaultedProperties.add(prop)

        # Create the actual_props dictionary, which maps each specifier to a set of properties
        # it is actually specifying or modifying.
        actual_props = {spec: [] for spec in specifiers}
        for prop in properties:
            # Extract the specifier that is specifying this prop and add it to the
            # specifier's entry in actual_props
            specifying_spec = properties[prop]
            actual_props[specifying_spec].append(prop)

            # If a specifier modifies this property, add this prop to the specifiers
            # actual_props list.
            if prop in modifying:
                modifying_spec = modifying[prop]
                actual_props[modifying_spec].append(prop)

        # Create an inversed modifying dictionary that specifiers to the properties they
        # are modifying.
        modifying_inv = {spec: prop for prop, spec in modifying.items()}

        # Topologically sort specifiers. Specifiers become vertices and the properties
        # those specifiers depend on become the in-edges of each vertex. The specifiers
        # are then sorted topologically according to this graph.
        order = []
        for spec in specifiers:
            spec._dfs_state = 0

        def dfs(spec):
            if spec._dfs_state == 2:  # finished processing this specifier
                return
            elif spec._dfs_state == 1:  # specifier is being processed
                raise SpecifierError(f"specifier {spec.name} depends on itself")
            spec._dfs_state = 1

            # Recurse on dependencies
            for dep in spec.requiredProperties:
                child = modifying.get(dep)
                if not child:
                    child = properties.get(dep)

                if child is None:
                    raise SpecifierError(
                        f"property {dep} required by "
                        f"specifier {spec} is not specified"
                    )
                else:
                    dfs(child)

            # If this is a modifying specifier, recurse on the specifier
            # that specifies the property being modified.
            if spec in modifying_inv:
                specifying_spec = properties[modifying_inv[spec]]
                dfs(specifying_spec)

            order.append(spec)
            spec._dfs_state = 2

        for spec in specifiers:
            dfs(spec)
        assert len(order) == len(specifiers)
        for spec in specifiers:
            del spec._dfs_state

        context = LazilyEvaluable.makeContext()
        for spec in order:
            specifiedValues = spec.getValuesFor(context)
            for prop in actual_props[spec]:
                assert not hasattr(context, prop) or prop in modifying, (prop, spec)
                value = toDistribution(specifiedValues[prop])
                cls._specify(context, prop, value)
        properties = LazilyEvaluable.getContextValues(context)

        constProps = frozenset(
            {prop for prop in _defaultedProperties if not needsSampling(properties[prop])}
        )
        return properties, constProps

    def _recomputeDynamicFinals(self):
        # Evaluate default value expression for each dynamic final property
        # and assign the obtained value
        for prop, recomputer in self._dynamicFinalProperties.items():
            rawVal = recomputer(self)
            value = valueInContext(rawVal, self)
            self._specify(self, prop, value)

    @classmethod
    def _specify(cls, context, prop, value):
        # Normalize types of some built-in properties
        if prop in (
            "position",
            "velocity",
            "cameraOffset",
            "positionStdDev",
            "orientationStdDev",
        ):
            value = toVector(value, f'"{prop}" of {cls.__name__} not a vector')
        elif prop in (
            "width",
            "length",
            "visibleDistance",
            "viewAngle",
            "speed",
            "angularSpeed",
            "yaw",
            "pitch",
            "roll",
            "mutationScale",
        ):
            value = toScalar(value, f'"{prop}" of {cls.__name__} not a scalar')

        if prop in ["yaw", "pitch", "roll"]:
            value = normalizeAngle(value)

        if prop == "parentOrientation":
            value = toOrientation(value)

        if prop == "regionContainedIn":
            # 2D regions can't contain objects, so we automatically use their footprint.
            value = convertToFootprint(value)

        if prop == "color" and value is not None and not isLazy(value):
            if any(not (0 <= v <= 1) for v in value):
                raise ValueError(
                    "Color property contains value not between 0 and 1 (inclusive)."
                )

            if not 3 <= len(value) <= 4:
                raise ValueError(f"Color property has incorrect length {len(value)}.")

        object.__setattr__(context, prop, value)

    def _register(self):
        import scenic.syntax.veneer as veneer  # TODO improve?

        veneer.registerInstance(self)

    def _override(self, specifiers):
        assert not needsSampling(self)
        # Validate properties being overridden and gather their old values
        oldVals = {}
        for spec in specifiers:
            for prop in spec.priorities:
                if prop in self._dynamicProperties:
                    raise SpecifierError(f'cannot override dynamic property "{prop}"')
                if prop not in self._propertiesSet:
                    raise SpecifierError(f'object has no property "{prop}" to override')
                oldVals[prop] = getattr(self, prop)

        # Perform specifier resolution to find the new values of all properties
        defs = {
            prop: Specifier("OverrideDefault", {prop: -1}, {prop: getattr(self, prop)})
            for prop in self.properties
        }
        newprops, _ = self._resolveSpecifiers(specifiers, defaults=defs)

        # Apply the new values
        for prop, val in newprops.items():
            object.__setattr__(self, prop, val)

        # If we assigned a new dynamic behavior, it might need to be started.
        if behavior := newprops["behavior"]:
            behavior._assignTo(self)

        return oldVals

    def _revert(self, oldVals):
        for prop, val in oldVals.items():
            object.__setattr__(self, prop, val)

    def sampleGiven(self, value):
        if not needsSampling(self):
            return self
        props = {prop: value[getattr(self, prop)] for prop in self.properties}
        obj = type(self)(props, constProps=self._constProps, _internal=True)
        obj._sampleParent = self
        return obj

    def _allProperties(self):
        return {prop: getattr(self, prop) for prop in self.properties}

    def _copyWith(self, **overrides):
        """Copy this object, possibly overriding some of its properties."""
        # Copy all properties except for final values, which will retain their default values
        props = {
            prop: val
            for prop, val in self._allProperties().items()
            if prop not in self._finalProperties
        }
        props.update(overrides)
        constProps = self._constProps.difference(overrides)
        return self._withProperties(props, constProps=constProps)

    def _clearCaches(self):
        for clearer in self._cache_clearers.values():
            clearer(self)

    def dumpAsScenicCode(self, stream, skipConstProperties=True):
        stream.write(f"new {self.__class__.__name__}")
        first = True
        for prop in self.properties:
            if skipConstProperties and prop in self._constProps:
                continue
            if prop in self._finalProperties:
                continue
            if prop == "position":
                spec = "at"
            else:
                spec = f"with {prop}"
            if first:
                stream.write(" ")
                first = False
            else:
                stream.write(",\n    ")
            stream.write(f"{spec} ")
            dumpAsScenicCode(getattr(self, prop), stream)

    def __str__(self):
        if hasattr(self, "properties") and "name" in self._propertiesSet:
            return self.name
        else:
            return f"unnamed {self.__class__.__name__}"

    def __repr__(self):
        if hasattr(self, "properties"):
            allProps = {prop: getattr(self, prop) for prop in self.properties}
        else:
            allProps = "<under construction>"
        return f"{type(self).__name__}({allProps})"


def precomputed_property(func):
    """A @property which can be precomputed if its dependencies are not random.

    Converts a function inside a subclass of `Constructible` into a method; the
    function's arguments must correspond to the properties of the object needed
    to compute this property. If any of those dependencies have random values,
    this property will evaluate to `None`; otherwise it will be computed once
    the first time it is needed and then reused across samples.
    """
    deps = tuple(inspect.signature(func).parameters)

    @cached
    @functools.wraps(func)
    def method(self):
        args = [getattr(self, prop) for prop in deps]
        if any(needsSampling(arg) for arg in args):
            return None
        return func(*args)

    @functools.wraps(func)
    def wrapper(self):
        parent = self._sampleParent or self
        return method(parent)

    wrapper._scenic_cache_clearer = method._scenic_cache_clearer

    return property(wrapper)


## Mutators


class Mutator:
    """An object controlling how the :keyword:`mutate` statement affects an `Object`.

    A `Mutator` can be assigned to the ``mutator`` property of an `Object` to
    control the effect of the :keyword:`mutate` statement. When mutation is enabled
    for such an object using that statement, the mutator's `appliedTo` method
    is called to compute a mutated version. The `appliedTo` method can also decide
    whether to apply mutators inherited from superclasses.
    """

    def appliedTo(self, obj):
        """Return a mutated version of the given object. Implemented by subclasses.

        The mutator may inspect the ``mutationScale`` attribute of the given object
        to scale its effect according to the scale given in ``mutate O by S``.

        Returns:
            A pair consisting of the mutated version of the object together with a
            Boolean indicating whether the mutator inherited from the superclass
            (if any) should also be applied.
        """
        raise NotImplementedError


class PositionMutator(Mutator):
    """Mutator adding Gaussian noise to ``position``. Used by `Point`.

    Attributes:
        stddevs (tuple[float,float,float]): standard deviation of noise for each dimension (x,y,z).
    """

    def __init__(self, stddevs):
        self.stddevs = tuple(stddevs)

    def appliedTo(self, obj):
        noise = Vector(
            random.gauss(0, self.stddevs[0] * obj.mutationScale),
            random.gauss(0, self.stddevs[1] * obj.mutationScale),
            random.gauss(0, self.stddevs[2] * obj.mutationScale),
        )
        obj.position += noise
        return (obj, True)  # allow further mutation

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return other.stddevs == self.stddevs

    def __hash__(self):
        return hash(self.stddevs)


class OrientationMutator(Mutator):
    """Mutator adding Gaussian noise to ``yaw``, ``pitch``, and ``roll``. Used by `OrientedPoint`.

    Attributes:
        stddevs (tuple[float,float,float]): standard deviation of noise for each angle (yaw, pitch, roll).
    """

    def __init__(self, stddevs):
        self.stddevs = tuple(stddevs)

    def appliedTo(self, obj):
        obj.yaw += random.gauss(0, self.stddevs[0] * obj.mutationScale)
        obj.pitch += random.gauss(0, self.stddevs[1] * obj.mutationScale)
        obj.roll += random.gauss(0, self.stddevs[2] * obj.mutationScale)

        return (obj, True)  # allow further mutation

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return other.stddevs == self.stddevs

    def __hash__(self):
        return hash(self.stddevs)


## Point


class Point(Constructible):
    """The Scenic base class ``Point``.

    The default mutator for `Point` adds Gaussian noise to ``position`` with
    a standard deviation given by the ``positionStdDev`` property.

    Properties:
        position (`Vector`; dynamic): Position of the point. Default value is the origin (0,0,0).
        width (float): Default value 0 (only provided for compatibility with
          operators that expect an `Object`).
        length (float): Default value 0.
        height (float): Default value 0.
        baseOffset (`Vector`): Only provided for compatibility with the `on` specifier.
          Default value is (0,0,0).
        contactTolerance (float): Only provided for compatibility with the specifiers
          that expect an `Object`. Default value 0.
        onDirection (`Vector`): The direction used to determine where to place
          this `Point` on a region, when using the modifying :keyword:`on` specifier.
          See the :sampref:`on {region}` page for more details. Default value is None,
          indicating the direction will be inferred from the region this object is being placed on.
        visibleDistance (float): Distance used to determine the visible range of this object.
          Default value 50.
        viewRayDensity (float): By default determines the number of rays used during visibility checks.
          This value is the density of rays per degree of visible range in one dimension. The total
          number of rays sent will be this value squared per square degree of this object's view angles.
          This value determines the default value for ``viewRayCount``, so if ``viewRayCount`` is overwritten
          this value is ignored. Default value 5.
        viewRayCount (None | tuple[float, float]): The total number of horizontal and vertical view angles
          to be sent, or None if this value should be computed automatically. Default value ``None``.
        viewRayDistanceScaling (bool): Whether or not the number of rays should scale with the distance to the
          object. Ignored if ``viewRayCount`` is passed. Default value ``False``.
        mutationScale (float): Overall scale of mutations, as set by the
          :keyword:`mutate` statement. Default value 0 (mutations disabled).
        positionStdDev (tuple[float, float, float]): Standard deviation of Gaussian noise
          for each dimension (x,y,z) to be added to this object's :prop:`position`
          when mutation is enabled with scale 1. Default value (1,1,0), mutating only the x,y values
          of the point.
    """

    _scenic_properties = {
        "position": PropertyDefault((), {"dynamic"}, lambda self: Vector(0.0, 0.0, 0.0)),
        "width": 0.0,
        "length": 0.0,
        "height": 0.0,
        "baseOffset": Vector(0, 0, 0),
        "contactTolerance": 0,
        "onDirection": None,
        # This property is defined in OrientedPoint, but we provide a default value
        # for Points for implementation convenience.
        "viewAngles": (math.tau, math.pi),
        "visibleDistance": 50,
        "viewRayDensity": 5,
        "viewRayCount": None,
        "viewRayDistanceScaling": False,
        "mutationScale": 0,
        "mutator": PropertyDefault(
            ("positionStdDev",),
            {"additive"},
            lambda self: PositionMutator((self.positionStdDev)),
        ),
        "positionStdDev": (1, 1, 0),
        # This property is defined in Object, but we provide a default empty value
        # for Points for implementation convenience.
        "regionContainedIn": None,
        # These properties are used internally to store entities that must be able to
        # or must be unable to observe (view) this entity.
        "_observingEntity": None,
        "_nonObservingEntity": None,
    }

    @cached_property
    def visibleRegion(self):
        """The :term:`visible region` of this object.

        The visible region of a `Point` is a sphere centered at its ``position`` with
        radius ``visibleDistance``.
        """
        dimensions = (self.visibleDistance, self.visibleDistance, self.visibleDistance)
        return SpheroidRegion(position=self.position, dimensions=dimensions)

    @cached_method
    def canSee(self, other, occludingObjects=tuple(), debug=False) -> bool:
        """Whether or not this `Point` can see ``other``.

        Args:
            other: A `Point`, `OrientedPoint`, or `Object` to check
              for visibility.
            occludingObjects: A list of objects that can occlude visibility.
        """
        return canSee(
            position=self.position,
            orientation=None,
            visibleDistance=self.visibleDistance,
            viewAngles=(math.tau, math.pi),
            rayCount=self.viewRayCount,
            rayDensity=self.viewRayDensity,
            distanceScaling=self.viewRayDistanceScaling,
            target=other,
            occludingObjects=occludingObjects,
            debug=debug,
        )

    @cached_property
    def corners(self):
        return (self.position,)

    def toVector(self) -> Vector:
        return self.position

    def sampleGiven(self, value):
        sample = super().sampleGiven(value)
        if value[self.mutationScale] != 0:
            for mutator in self.mutator:
                if mutator is None:
                    continue
                sample, proceed = mutator.appliedTo(sample)
                if not proceed:
                    break
            sample._recomputeDynamicFinals()
        return sample

    # Points automatically convert to Vectors when needed
    def __getattr__(self, attr):
        if hasattr(Vector, attr):
            return getattr(self.toVector(), attr)
        else:
            self.__getattribute__(attr)


## OrientedPoint


class OrientedPoint(Point):
    """The Scenic class ``OrientedPoint``.

    The default mutator for `OrientedPoint` adds Gaussian noise to ``yaw``, ``pitch``
    and ``roll``, using the three standard deviations (for yaw/pitch/roll respectively)
    given by the  ``orientationStdDev`` property. It then also applies the mutator for `Point`.
    By default the standard deviations for ``pitch`` and ``roll`` are zero so that, by
    default, only ``yaw`` is mutated.

    Properties:
        yaw (float; dynamic): Yaw of the `OrientedPoint` in radians in the local coordinate system
          provided by :prop:`parentOrientation`. Default value 0.
        pitch (float; dynamic): Pitch of the `OrientedPoint` in radians in the local coordinate system
          provided by :prop:`parentOrientation`. Default value 0.
        roll (float; dynamic): Roll of the `OrientedPoint` in radians in the local coordinate system
          provided by :prop:`parentOrientation`. Default value 0.
        parentOrientation (`Orientation`): The local coordinate system that the `OrientedPoint`'s
          :prop:`yaw`, :prop:`pitch`, and :prop:`roll` are interpreted in. Default
          value is the global coordinate system, where an object is flat in the XY plane,
          facing North.
        orientation (`Orientation`; dynamic; final): The orientation of the `OrientedPoint` relative
          to the global coordinate system. Derived from the :prop:`yaw`, :prop:`pitch`,
          :prop:`roll`, and :prop:`parentOrientation` of this `OrientedPoint` and non-overridable.
        heading (float; dynamic; final): Yaw value of this `OrientedPoint` in the global coordinate
          system. Derived from :prop:`orientation` and non-overridable.
        viewAngles (tuple[float,float]): Horizontal and vertical view angles of this `OrientedPoint`
          in radians. Horizontal view angle can be up to 2π and vertical view angle can be
          up to π. Values greater than these will be truncated. Default value is (2π, π)
        orientationStdDev (tuple[float,float,float]): Standard deviation of Gaussian noise to add to this
          object's Euler angles (yaw, pitch, roll) when mutation is enabled with scale 1.
          Default value (5°, 0, 0), mutating only the :prop:`yaw` of this `OrientedPoint`.
    """

    _scenic_properties = {
        "yaw": PropertyDefault((), {"dynamic"}, lambda self: 0),
        "pitch": PropertyDefault((), {"dynamic"}, lambda self: 0),
        "roll": PropertyDefault((), {"dynamic"}, lambda self: 0),
        "parentOrientation": globalOrientation,
        "orientation": PropertyDefault(
            {"yaw", "pitch", "roll", "parentOrientation"},
            {"dynamic", "final"},
            lambda self: (
                self.parentOrientation
                * Orientation.fromEuler(self.yaw, self.pitch, self.roll)
            ),
        ),
        # Heading is equal to orientation.yaw, which is equal to self.yaw if this OrientedPoint's
        # parentOrientation is the global orientation. Defined this way to simplify the value for pruning
        # purposes if possible.
        "heading": PropertyDefault(
            {"orientation"},
            {"dynamic", "final"},
            lambda self: (
                self.yaw
                if alwaysGlobalOrientation(self.parentOrientation)
                else self.orientation.yaw
            ),
        ),
        "viewAngle": math.tau,  # Primarily for backwards compatibility. Set viewAngles instead.
        "viewAngles": PropertyDefault(
            ("viewAngle",), set(), lambda self: (self.viewAngle, math.pi)
        ),
        "mutator": PropertyDefault(
            {"orientationStdDev"},
            {"additive"},
            lambda self: OrientationMutator(self.orientationStdDev),
        ),
        "headingStdDev": math.radians(
            5
        ),  # Primarily for backwards compatibility. Set orientationStdDev instead.
        "orientationStdDev": PropertyDefault(
            ("headingStdDev",), set(), lambda self: (self.headingStdDev, 0, 0)
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.viewAngles[0] > math.tau or self.viewAngles[1] > math.pi:
            warnings.warn(
                "ViewAngles can not have values greater than (math.tau, math.pi). Truncating values..."
            )
            self.viewAngles = (
                min(self.viewAngles[0], math.tau),
                min(self.viewAngles[1], math.pi),
            )

    @cached_property
    def visibleRegion(self):
        """The :term:`visible region` of this object.

        The visible region of an `OrientedPoint` restricts that of `Point` (a sphere with
        radius :prop:`visibleDistance`) based on the value of :prop:`viewAngles`. In
        general, it is a capped rectangular pyramid subtending an angle of
        :scenic:`viewAngles[0]` horizontally and :scenic:`viewAngles[1]` vertically, as
        long as those angles are less than π/2; larger angles yield various kinds of
        wrap-around regions. See `ViewRegion` for details.
        """
        return ViewRegion(
            visibleDistance=self.visibleDistance,
            viewAngles=self.viewAngles,
            position=self.position,
            rotation=self.orientation,
        )

    @cached_method
    def canSee(self, other, occludingObjects=tuple(), debug=False) -> bool:
        """Whether or not this `OrientedPoint` can see ``other``.

        Args:
            other: A `Point`, `OrientedPoint`, or `Object` to check
              for visibility.
            occludingObjects: A list of objects that can occlude visibility.
        """
        return canSee(
            position=self.position,
            orientation=self.orientation,
            visibleDistance=self.visibleDistance,
            viewAngles=self.viewAngles,
            rayCount=self.viewRayCount,
            rayDensity=self.viewRayDensity,
            distanceScaling=self.viewRayDistanceScaling,
            target=other,
            occludingObjects=occludingObjects,
            debug=debug,
        )

    def relativize(self, vec):
        pos = self.relativePosition(vec)
        return OrientedPoint._with(position=pos, parentOrientation=self.orientation)

    def relativePosition(self, vec):
        return self.position.offsetLocally(self.orientation, vec)

    def distancePast(self, vec):
        """Distance past a given point, assuming we've been moving in a straight line."""
        diff = self.position - vec
        return diff.rotatedBy(-self.heading).y

    def toHeading(self) -> float:
        return self.heading

    def toOrientation(self) -> Orientation:
        return self.orientation


## Object


class Object(OrientedPoint):
    """The Scenic class ``Object``.

    This is the default base class for Scenic classes.

    Properties:
        width (float): Width of the object, i.e. extent along its X axis.
          Default value of 1 inherited from the object's :prop:`shape`.
        length (float): Length of the object, i.e. extent along its Y axis.
          Default value of 1 inherited from the object's :prop:`shape`.
        height (float): Height of the object, i.e. extent along its Z axis.
          Default value of 1 inherited from the object's :prop:`shape`.
        shape (`Shape`): The shape of the object, which must be an instance of `Shape`.
          The default shape is a box, with default unit dimensions.
        allowCollisions (bool): Whether the object is allowed to intersect
          other objects. Default value ``False``.
        regionContainedIn (`Region` or ``None``): A `Region` the object is
          required to be contained in. If ``None``, the object need only be
          contained in the scenario's :term:`workspace`.
        baseOffset (`Vector`): An offset from the :prop:`position` of the Object
          to the base of the object, used by the `on` specifier. Default value
          is :scenic:`(0, 0, -self.height/2)`, placing the base of the Object at the bottom
          center of the Object's bounding box.
        contactTolerance (float): The maximum distance this object can be away from a
          surface to be considered on the surface. Objects are placed at half this
          distance away from a point when the `on` specifier or a directional specifier
          like `left of {Object}` is used. Default value 1e-4.
        sideComponentThresholds (`DimensionLimits`): Used to determine the
          various sides of an object (when using the default implementation).
          The three interior 2-tuples represent the maximum and minimum bounds
          for each dimension's (x,y,z) surface. See `defaultSideSurface` for details.
          Default value :scenic:`((-0.5, 0.5), (-0.5, 0.5), (-0.5, 0.5))`.
        cameraOffset (`Vector`): Position of the camera for the :keyword:`can see`
          operator, relative to the object's :prop:`position`. Default :scenic:`(0, 0, 0)`.
        visionSensorOffset (`Vector`): Offset of the default vision sensor mount point,
          relative to the object's :prop:`position`. Defaults to the front-center of the
          bounding box, :scenic:`(0, self.length/2, 0)`.
        requireVisible (bool): Whether the object is required to be visible
          from the ``ego`` object. Default value ``False``.
        occluding (bool): Whether or not this object can occlude other objects. Default
          value ``True``.
        showVisibleRegion (bool): Whether or not to display the visible region in the
          Scenic internal visualizer.
        color (tuple[float, float, float, float] or tuple[float, float, float] or `None`):
          An optional color (with optional alpha) property that is used by the internal
          visualizer, or possibly simulators. All values should be between 0 and 1.
          Default value ``None``
        render (bool): Whether this object is drawn in Scenic's internal visualizer.
          Default value ``True``. Set to ``False`` to hide the object.
        velocity (`Vector`; *dynamic*): Velocity in dynamic simulations. Default value is
          the velocity determined by :prop:`speed` and :prop:`orientation`.
        speed (float; dynamic): Speed in dynamic simulations. Default value 0.
        angularVelocity (`Vector`; *dynamic*):
        angularSpeed (float; dynamic): Angular speed in dynamic simulations. Default
          value 0.
        behavior: Behavior for dynamic agents, if any (see :ref:`dynamics`). Default
          value ``None``.
        lastActions: Tuple of :term:`actions` taken by this agent in the last time step
          (an empty tuple if the object is not an agent or this is the first time step).
        sensors: Dict of ("name": sensor) that populate the observations field every time step
        observations: Dict of ("name": observation) storing the latest observation of the sensor
          with the same name
    """

    _scenic_properties = {
        "width": PropertyDefault(("shape",), {}, lambda self: self.shape.width),
        "length": PropertyDefault(("shape",), {}, lambda self: self.shape.length),
        "height": PropertyDefault(("shape",), {}, lambda self: self.shape.height),
        "shape": BoxShape(),
        "allowCollisions": False,
        "regionContainedIn": None,
        "baseOffset": PropertyDefault(
            ("height",), {}, lambda self: Vector(0, 0, -self.height / 2)
        ),
        "contactTolerance": 1e-4,
        "sideComponentThresholds": ((-0.5, 0.5), (-0.5, 0.5), (-0.5, 0.5)),
        "cameraOffset": Vector(0, 0, 0),
        "visionSensorOffset": PropertyDefault(
            ("length",), {}, lambda self: Vector(0, self.length / 2, 0)
        ),
        "requireVisible": False,
        "occluding": True,
        "showVisibleRegion": False,
        "color": None,
        "render": True,
        "velocity": PropertyDefault(
            ("speed", "orientation"),
            {"dynamic"},
            lambda self: Vector(0, self.speed, 0).rotatedBy(self.orientation),
        ),
        "speed": PropertyDefault((), {"dynamic"}, lambda self: 0),
        "angularVelocity": PropertyDefault((), {"dynamic"}, lambda self: Vector(0, 0, 0)),
        "angularSpeed": PropertyDefault((), {"dynamic"}, lambda self: 0),
        "behavior": None,
        "lastActions": tuple(),
        # weakref to scenario which created this object, for internal use
        "_parentScenario": None,
        # Sensor properties
        "sensors": PropertyDefault((), {}, lambda self: {}),
        "observations": PropertyDefault((), {"final"}, lambda self: {}),
    }

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        # The _dynamicProxy attribute stores a mutable copy of the object used during
        # simulations, intercepting all attribute accesses to the original object;
        # we set this attribute very early to prevent problems during unpickling.
        object.__setattr__(obj, "_dynamicProxy", obj)
        return obj

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hw = hw = self.width / 2
        self.hl = hl = self.length / 2
        self.hh = hh = self.height / 2
        self.radius = hypot(hw, hl, hh)  # circumcircle; for collision detection

        self._relations = []

    @classmethod
    def _specify(cls, context, prop, value):
        # Normalize types of some built-in properties
        if prop == "behavior" and value != None:
            import scenic.syntax.veneer as veneer  # TODO improve?

            value = toType(
                value, veneer.Behavior, f'"behavior" of {cls.__name__} not a behavior'
            )
        super()._specify(context, prop, value)

    def _register(self):
        import scenic.syntax.veneer as veneer  # TODO improve?

        veneer.registerObject(self)

    def __getattribute__(self, name):
        proxy = object.__getattribute__(self, "_dynamicProxy")
        return object.__getattribute__(proxy, name)

    def __setattr__(self, name, value):
        proxy = object.__getattribute__(self, "_dynamicProxy")
        object.__setattr__(proxy, name, value)

    def __delattr__(self, name):
        proxy = object.__getattribute__(self, "_dynamicProxy")
        object.__delattr__(proxy, name)

    def startDynamicSimulation(self):
        """Hook called when the object is created in a dynamic simulation.

        Does nothing by default; provided for objects to do simulator-specific
        initialization as needed.

        .. versionchanged:: 3.0

            This method is called on objects created in the middle of dynamic
            simulations, not only objects present in the initial scene.
        """
        pass

    @cached_method
    def containsPoint(self, point):
        """Whether or not the space this object occupies contains a point"""
        return self.occupiedSpace.containsPoint(point)

    @cached_method
    def distanceTo(self, point):
        """The minimal distance from the space this object occupies to a given point"""
        return self.occupiedSpace.distanceTo(point)

    @cached_method
    def minimumDistanceTo(self, other):
        """The minimal distance between this object and another."""
        if not isinstance(other, Object):
            raise TypeError(
                f"Cannot compute minimum distance between Object and {type(other)} "
            )

        # 2D fast path
        if self._isPlanarBox and other._isPlanarBox and self.z == other.z:
            return self._boundingPolygon.distance(other._boundingPolygon)

        return self.occupiedSpace.minimumDistanceTo(other.occupiedSpace)

    @cached_method
    def intersects(self, other):
        """Whether or not this object intersects another object or region"""
        ## Type Checking ##
        if not isinstance(other, (Object, Region)):
            raise TypeError(
                f"Cannot compute intersection of Scenic Object with {type(other)}."
            )

        ## Heuristic Fast Paths ##
        # For two objects that are boxes and flat, we can take a fast route
        if self._isPlanarBox and (isinstance(other, Object) and other._isPlanarBox):
            if abs(self.position.z - other.position.z) > (self.height + other.height) / 2:
                return False

            self_poly = self._boundingPolygon
            other_poly = other._boundingPolygon
            return self_poly.intersects(other_poly)

        # For an object that is a box and flat with a polygonal region, we can
        # also take a fast route.
        if self._isPlanarBox and (
            isinstance(other, PolygonalRegion)
            and abs(self.position.z - other.z) <= self.height / 2
        ):
            return self._boundingPolygon.intersects(other.polygons)

        ## Default Case
        # Extract other's occupied space if it's an object
        if isinstance(other, Object):
            other_occupied_space = other.occupiedSpace
        else:
            other_occupied_space = other

        if isLazy(self.occupiedSpace) or isLazy(other_occupied_space):
            raise RandomControlFlowError(
                "Cannot compute intersection between Objects with non-fixed values."
            )

        return self.occupiedSpace.intersects(other_occupied_space)

    @cached_property
    def left(self):
        return self.relativize(Vector(-self.hw, 0))

    @cached_property
    def right(self):
        return self.relativize(Vector(self.hw, 0))

    @cached_property
    def front(self):
        return self.relativize(Vector(0, self.hl))

    @cached_property
    def back(self):
        return self.relativize(Vector(0, -self.hl))

    @cached_property
    def top(self):
        return self.relativize(Vector(0, 0, self.hh))

    @cached_property
    def bottom(self):
        return self.relativize(Vector(0, 0, -self.hh))

    @cached_property
    def frontLeft(self):
        return self.relativize(Vector(-self.hw, self.hl))

    @cached_property
    def frontRight(self):
        return self.relativize(Vector(self.hw, self.hl))

    @cached_property
    def backLeft(self):
        return self.relativize(Vector(-self.hw, -self.hl))

    @cached_property
    def backRight(self):
        return self.relativize(Vector(self.hw, -self.hl))

    @cached_property
    def topFrontLeft(self):
        return self.relativize(Vector(-self.hw, self.hl, self.hh))

    @cached_property
    def topFrontRight(self):
        return self.relativize(Vector(self.hw, self.hl, self.hh))

    @cached_property
    def topBackLeft(self):
        return self.relativize(Vector(-self.hw, -self.hl, self.hh))

    @cached_property
    def topBackRight(self):
        return self.relativize(Vector(self.hw, -self.hl, self.hh))

    @cached_property
    def bottomFrontLeft(self):
        return self.relativize(Vector(-self.hw, self.hl, -self.hh))

    @cached_property
    def bottomFrontRight(self):
        return self.relativize(Vector(self.hw, self.hl, -self.hh))

    @cached_property
    def bottomBackLeft(self):
        return self.relativize(Vector(-self.hw, -self.hl, -self.hh))

    @cached_property
    def bottomBackRight(self):
        return self.relativize(Vector(self.hw, -self.hl, -self.hh))

    @cached_property
    def visibleRegion(self):
        """The :term:`visible region` of this object.

        The visible region of an `Object` is the same as that of an `OrientedPoint` (see
        `OrientedPoint.visibleRegion`) except that it is offset by the value of
        :prop:`cameraOffset` (which is the zero vector by default).
        """
        true_position = self.position.offsetLocally(self.orientation, self.cameraOffset)
        return ViewRegion(
            visibleDistance=self.visibleDistance,
            viewAngles=self.viewAngles,
            position=true_position,
            rotation=self.orientation,
        )

    @cached_method
    def canSee(self, other, occludingObjects=tuple(), debug=False) -> bool:
        """Whether or not this `Object` can see ``other``.

        Args:
            other: A `Point`, `OrientedPoint`, or `Object` to check
              for visibility.
            occludingObjects: A list of objects that can occlude visibility.
        """
        true_position = self.position.offsetLocally(self.orientation, self.cameraOffset)
        return canSee(
            position=true_position,
            orientation=self.orientation,
            visibleDistance=self.visibleDistance,
            viewAngles=self.viewAngles,
            rayCount=self.viewRayCount,
            rayDensity=self.viewRayDensity,
            distanceScaling=self.viewRayDistanceScaling,
            target=other,
            occludingObjects=occludingObjects,
            debug=debug,
        )

    @cached_property
    def corners(self):
        """A tuple containing the corners of this object's bounding box"""
        hw, hl, hh = self.hw, self.hl, self.hh
        return (
            self.relativePosition(Vector(hw, hl, hh)),
            self.relativePosition(Vector(-hw, hl, hh)),
            self.relativePosition(Vector(-hw, -hl, hh)),
            self.relativePosition(Vector(hw, -hl, hh)),
            self.relativePosition(Vector(hw, hl, -hh)),
            self.relativePosition(Vector(-hw, hl, -hh)),
            self.relativePosition(Vector(-hw, -hl, -hh)),
            self.relativePosition(Vector(hw, -hl, -hh)),
        )

    @cached_property
    def _corners2D(self):
        hw, hl = self.hw, self.hl
        # Note: 2D show method assumes cyclic order of vertices
        return (
            self.relativePosition(Vector(hw, hl)),
            self.relativePosition(Vector(-hw, hl)),
            self.relativePosition(Vector(-hw, -hl)),
            self.relativePosition(Vector(hw, -hl)),
        )

    @cached_property
    def occupiedSpace(self):
        """A region representing the space this object occupies"""
        if self._sampleParent and self._sampleParent._hasStaticBounds:
            return self._sampleParent.occupiedSpace

        shape = self.shape
        scaledShape = self._scaledShape
        if scaledShape:
            mesh = scaledShape.mesh
            dimensions = None  # mesh does not need to be scaled
            convex = scaledShape.isConvex
        else:
            mesh = shape.mesh
            dimensions = (self.width, self.length, self.height)
            convex = shape.isConvex
        return MeshVolumeRegion(
            mesh=mesh,
            dimensions=dimensions,
            position=self.position,
            rotation=self.orientation,
            centerMesh=False,
            _internal=True,
            _isConvex=convex,
            _shape=shape,
            _scaledShape=scaledShape,
        )

    @precomputed_property
    def _scaledShape(shape, width, length, height):
        return MeshVolumeRegion(
            mesh=shape.mesh,
            dimensions=(width, length, height),
            centerMesh=False,
            _internal=True,
            _isConvex=shape.isConvex,
        )

    @property
    def _isConvex(self):
        """Whether this object's shape is convex"""
        return self.shape.isConvex

    @property
    def _hasStaticBounds(self):
        deps = (
            self.position,
            self.orientation,
            self.shape,
            self.width,
            self.length,
            self.height,
            self.mutationScale,
        )
        return not any(needsSampling(v) for v in deps) and self.mutationScale == 0

    @cached_property
    def boundingBox(self):
        """A region representing this object's bounding box"""
        return MeshVolumeRegion(self.occupiedSpace.mesh.bounding_box, centerMesh=False)

    @cached_property
    def inradius(self):
        """A lower bound on the inradius of this object"""

        # Define a helper function that computes the support of the inradius,
        # given the sub supports.
        def inradiusSupport(width_s, length_s, height_s, shape_s):
            # Unpack the dimension supports (and ignore the shape support)
            min_width, max_width = width_s
            min_length, max_length = length_s
            min_height, max_height = height_s

            if None in [
                min_width,
                max_width,
                min_length,
                max_length,
                min_height,
                max_height,
            ]:
                # Can't get a bound on one or more dimensions, abort
                return None, None

            min_bounds = np.array([min_width, min_length, min_height])
            max_bounds = np.array([max_width, max_length, max_height])

            # Extract a list of possible shapes
            if isinstance(self.shape, Shape):
                shapes = [self.shape]
            elif isinstance(self.shape, MultiplexerDistribution) and all(
                isinstance(opt, Shape) for opt in self.shape.options
            ):
                shapes = self.shape.options
            else:
                # Something we don't recognize, abort
                return None, None

            # Get the inradius for each shape with the min and max bounds
            min_distances = [
                MeshVolumeRegion(mesh=shape.mesh, dimensions=min_bounds).inradius
                for shape in shapes
            ]
            max_distances = [
                MeshVolumeRegion(mesh=shape.mesh, dimensions=max_bounds).inradius
                for shape in shapes
            ]

            distance_range = (min(min_distances), max(max_distances))

            return distance_range

        # Define a helper function that computes the actual inradius
        @distributionFunction(support=inradiusSupport)
        def inradiusActual(width, length, height, shape):
            return MeshVolumeRegion(
                mesh=shape.mesh, dimensions=(width, length, height)
            ).inradius

        # Return the inradius (possibly a distribution) with proper support information
        return inradiusActual(self.width, self.length, self.height, self.shape)

    @cached_property
    def planarInradius(self):
        """A lower bound on the planar inradius of this object.

        This is defined as the inradius of the polygon of the occupiedSpace
        of this object projected into the XY plane, assuming that pitch and
        roll are both 0.
        """

        # Define a helper function that computes the support of the inradius,
        # given the sub supports.
        def planarInradiusSupport(width_s, length_s, shape_s):
            # Unpack the dimension supports (and ignore the shape support)
            min_width, max_width = width_s
            min_length, max_length = length_s

            if None in [min_width, max_width, min_length, max_length]:
                # Can't get a bound on one or more dimensions, abort
                return None, None

            min_bounds = np.array([min_width, min_length, 1])
            max_bounds = np.array([max_width, max_length, 1])

            # Extract a list of possible shapes
            if isinstance(self.shape, Shape):
                shapes = [self.shape]
            elif isinstance(self.shape, MultiplexerDistribution) and all(
                isinstance(opt, Shape) for opt in self.shape.options
            ):
                shapes = self.shape.options
            else:
                # Something we don't recognize, abort
                return None, None

            # Get the inradius of the projected for each shape with the min and max bounds
            min_distances = [
                MeshVolumeRegion(
                    mesh=shape.mesh, dimensions=min_bounds
                ).boundingPolygon.inradius
                for shape in shapes
            ]
            max_distances = [
                MeshVolumeRegion(
                    mesh=shape.mesh, dimensions=max_bounds
                ).boundingPolygon.inradius
                for shape in shapes
            ]

            distance_range = (min(min_distances), max(max_distances))

            return distance_range

        # Define a helper function that computes the actual planarInradius
        @distributionFunction(support=planarInradiusSupport)
        def planarInradiusActual(width, length, shape):
            return MeshVolumeRegion(
                mesh=shape.mesh, dimensions=(width, length, 1)
            ).boundingPolygon.inradius

        # Return the planar inradius (possibly a distribution) with proper support information
        return planarInradiusActual(self.width, self.length, self.shape)

    @cached_property
    def surface(self):
        """A region containing the entire surface of this object"""
        return self.occupiedSpace.getSurfaceRegion()

    @cached_property
    def onSurface(self):
        """The surface used by the ``on`` specifier.

        This region is used to sample position when
        another object is placed ``on`` this object. By default
        the top surface of this object (`topSurface`), but can
        be overwritten by subclasses.
        """
        return self.topSurface

    @cached_property
    def topSurface(self):
        """A region containing the top surface of this object

        For how this surface is computed, see `defaultSideSurface`.
        """
        return defaultSideSurface(
            self.occupiedSpace,
            dimension=2,
            positive=True,
            thresholds=self.sideComponentThresholds,
        )

    @cached_property
    def rightSurface(self):
        """A region containing the right surface of this object

        For how this surface is computed, see `defaultSideSurface`.
        """
        return defaultSideSurface(
            self.occupiedSpace,
            dimension=0,
            positive=True,
            thresholds=self.sideComponentThresholds,
        )

    @cached_property
    def leftSurface(self):
        """A region containing the left surface of this object

        For how this surface is computed, see `defaultSideSurface`.
        """
        return defaultSideSurface(
            self.occupiedSpace,
            dimension=0,
            positive=False,
            thresholds=self.sideComponentThresholds,
        )

    @cached_property
    def frontSurface(self):
        """A region containing the front surface of this object

        For how this surface is computed, see `defaultSideSurface`.
        """
        return defaultSideSurface(
            self.occupiedSpace,
            dimension=1,
            positive=True,
            thresholds=self.sideComponentThresholds,
        )

    @cached_property
    def backSurface(self):
        """A region containing the back surface of this object

        For how this surface is computed, see `defaultSideSurface`.
        """
        return defaultSideSurface(
            self.occupiedSpace,
            dimension=1,
            positive=False,
            thresholds=self.sideComponentThresholds,
        )

    @cached_property
    def bottomSurface(self):
        """A region containing the bottom surface of this object

        For how this surface is computed, see `defaultSideSurface`.
        """
        return defaultSideSurface(
            self.occupiedSpace,
            dimension=2,
            positive=False,
            thresholds=self.sideComponentThresholds,
        )

    def show3D(self, viewer, highlight=False):
        if needsSampling(self):
            raise RuntimeError("tried to show() symbolic Object")

        if not self.render:
            return

        # Render the object
        object_mesh = self.occupiedSpace.mesh.copy()

        if highlight:
            object_mesh.visual.face_colors = [30, 179, 0, 255]
        elif self.color is not None:
            if len(self.color) == 3:
                r, g, b = self.color
                a = 1
            elif len(self.color) == 4:
                r, g, b, a = self.color
            else:
                assert False

            object_mesh.visual.face_colors = [
                int(255 * r),
                int(255 * g),
                int(255 * b),
                int(255 * a),
            ]

        viewer.add_geometry(object_mesh)

        if self.showVisibleRegion:
            view_region_mesh = self.visibleRegion.mesh

            edges = view_region_mesh.face_adjacency_edges[
                view_region_mesh.face_adjacency_angles > np.radians(0.1)
            ]
            vertices = view_region_mesh.vertices

            edge_path = trimesh.path.Path3D(
                **trimesh.path.exchange.misc.edges_to_path(edges, vertices)
            )

            edge_path.colors = [
                [30, 30, 150, 255] for _ in range(len(edge_path.entities))
            ]

            viewer.add_geometry(edge_path)

    def show2D(self, workspace, plt, highlight=False):
        if needsSampling(self):
            raise RuntimeError("tried to show() symbolic Object")
        pos = self.position
        spos = workspace.scenicToSchematicCoords(pos)

        if highlight:
            # Circle around object
            rad = 1.5 * max(self.width, self.length)
            c = plt.Circle(spos, rad, color="g", fill=False)
            plt.gca().add_artist(c)
            # View cone
            ha = self.viewAngle / 2.0
            camera = self.position.offsetRotated(self.heading, self.cameraOffset)
            cpos = workspace.scenicToSchematicCoords(camera)
            for angle in (-ha, ha):
                p = camera.offsetRadially(20, self.heading + angle)
                edge = [cpos, workspace.scenicToSchematicCoords(p)]
                x, y = zip(*edge)
                plt.plot(x, y, "b:")

        corners = [
            workspace.scenicToSchematicCoords(corner) for corner in self._corners2D
        ]
        x, y = zip(*corners)
        color = self.color if hasattr(self, "color") else (1, 0, 0)
        plt.fill(x, y, color=color)

        frontMid = averageVectors(corners[0], corners[1])
        baseTriangle = [frontMid, corners[2], corners[3]]
        triangle = [averageVectors(p, spos, weight=0.5) for p in baseTriangle]
        x, y = zip(*triangle)
        plt.fill(x, y, "w")
        plt.plot(x + (x[0],), y + (y[0],), color="k", linewidth=1)

    @cached_property
    def _isPlanarBox(self):
        """Whether this object is a box aligned with the XY plane."""
        return (
            isinstance(self.shape, BoxShape)
            and self.orientation.pitch == 0
            and self.orientation.roll == 0
        )

    @cached_property
    def _boundingPolygon(self):
        # Fast case for planar boxes
        if self._isPlanarBox:
            width, length = self.width, self.length
            pos = self.position
            yaw = self.orientation.yaw
            cyaw, syaw = math.cos(yaw), math.sin(yaw)
            matrix = [
                width * cyaw,
                -length * syaw,
                width * syaw,
                length * cyaw,
                pos[0],
                pos[1],
            ]
            return shapely.affinity.affine_transform(_unitBox, matrix)

        return self.occupiedSpace._boundingPolygon


_unitBox = shapely.geometry.Polygon(((0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5)))


@distributionFunction
def defaultSideSurface(
    occupiedSpace, dimension, positive, thresholds
) -> MeshSurfaceRegion:
    """Extracts a side surface from the occupiedSpace of an object.

    This function is the default implementation for computing a region
    representing a side surface of an object. This is done by keeping only the
    faces of the object's ``occupiedSpace`` mesh that have normal
    vectors with a large/small enough x,y, or z component. For example,
    for the front surface of an object we would would keep all faces that
    had a normal vector with y component greater than ``thresholds[1][1]``
    and for the back surface of an object we would keep all faces that
    had a normal vector with y component less than ``thresholds[1][0]``.

    Args:
        occupiedSpace: The `occupiedSpace` region of the object to
          extract the side surface from.
        dimension: The target dimension who's component will be checked.
        positive: If `False`, the target component must be less than
          the first value in the appropriate tuple. If `True`, the
          component must be greater than the second value in the
          appropriate tuple.
        thresholds: A 3-tuple of 2-tuples, one for each dimension (x,y,z),
          with each tuple containing the thresholds for a non-positive and
          positive side, respectively, in each dimension.
        on_dimension: The on_dimension to be passed to the created surface.
    """
    # Extract mesh from object
    obj_mesh = occupiedSpace.mesh.copy()

    # Extract appropriate thresholds
    threshold = thresholds[dimension][int(positive)]

    # Drop all faces whose normal vector do not have a sufficiently
    # large component.
    face_normal_vals = obj_mesh.face_normals[:, dimension]
    if positive:
        face_mask = face_normal_vals >= threshold
    else:
        face_mask = face_normal_vals <= threshold

    obj_mesh.faces = obj_mesh.faces[face_mask]
    obj_mesh.remove_unreferenced_vertices()

    # Check if the resulting surface is empty and return an appropriate region.
    if not obj_mesh.is_empty:
        return MeshSurfaceRegion(mesh=obj_mesh, centerMesh=False)
    else:
        return EmptyRegion(name="EmptyTopSurface")


def enableDynamicProxyFor(obj):
    object.__setattr__(obj, "_dynamicProxy", obj._copyWith())


def setDynamicProxyFor(obj, proxy):
    object.__setattr__(obj, "_dynamicProxy", proxy)


def disableDynamicProxyFor(obj):
    object.__setattr__(obj, "_dynamicProxy", obj)


## 2D Compatibility Classes


class Point2D(Point):
    """A 2D version of `Point`, used for backwards compatibility with Scenic 2.0"""

    _scenic_properties = {}
    _3DClass = Point

    @cached_property
    def visibleRegion(self):
        """The :term:`visible region` of this 2D point.

        The visible region of a `Point` is a disc centered at its ``position`` with
        radius ``visibleDistance``.
        """
        return CircularRegion(self.position, self.visibleDistance)

    def _canSee2D(self, other):
        if isinstance(other, Object2D):
            return self.visibleRegion.polygons.intersects(other._boundingPolygon)
        elif isinstance(other, (Vector, Point2D)):
            return self.visibleRegion.containsPoint(toVector(other))
        else:
            assert False, other

    def canSee(self, other, occludingObjects=tuple()):
        # Fast path when there is no occlusion (default in 2D mode).
        if not occludingObjects:
            return self._canSee2D(other)

        # With occlusion, fall back to the general case.
        return self._3DClass.canSee(self, other, occludingObjects)


class OrientedPoint2D(Point2D, OrientedPoint):
    """A 2D version of `OrientedPoint`, used for backwards compatibility with Scenic 2.0"""

    _scenic_properties = {}
    _3DClass = OrientedPoint

    def __init_subclass__(cls):
        if cls.__dict__.get("_props_transformed", False):
            # Can get here when cls is unpickled (the transformed version was pickled)
            pass
        else:
            # Mark class as being transformed.
            # To work around https://github.com/uqfoundation/dill/issues/612,
            # use a different truthy value for each class.
            cls._props_transformed = str(cls)

            props = cls._scenic_properties
            # Raise error if parentOrientation and heading already defined
            if "parentOrientation" in props and "heading" in props:
                raise RuntimeError(
                    f'{cls.__name__} defines both "parentOrientation" and "heading"'
                )

            # Map certain properties to their 3D analog
            if "heading" in props:
                props["parentOrientation"] = props["heading"]
                del props["heading"]

        super().__init_subclass__()

    @classmethod
    def _prepareSpecifiers(cls, specifiers):
        # Map certain specifiers to their 3D analog
        newspecs = []
        for spec in specifiers:
            # Map "with heading x" to "facing x"
            if spec.name == "With(heading)" and tuple(spec.priorities) == ("heading",):
                import scenic.syntax.veneer as veneer

                newspecs.append(veneer.Facing(spec.value["heading"]))
            else:
                newspecs.append(spec)
        return newspecs

    @cached_property
    def visibleRegion(self):
        """The :term:`visible region` of this 2D oriented point.

        The visible region of an `OrientedPoint` is a sector of the disc centered at its
        ``position`` with radius ``visibleDistance``, oriented along ``heading`` and
        subtending an angle of ``viewAngle``.
        """
        return SectorRegion(
            self.position, self.visibleDistance, self.heading, self.viewAngle
        )


class Object2D(OrientedPoint2D, Object):
    """A 2D version of `Object`, used for backwards compatibility with Scenic 2.0"""

    _scenic_properties = {
        "baseOffset": (0, 0, 0),
        "contactTolerance": 0,
        "requireVisible": True,
        "occluding": False,
        "height": PropertyDefault(
            ("width", "length"), {}, lambda self: max(self.width, self.length)
        ),
    }
    _3DClass = Object

    @classmethod
    def _specify(cls, context, prop, value):
        # If position is being set, set z value to 0
        if prop == "position":
            value = toVector(value, f'"{prop}" of {cls.__name__} not a vector')
            if needsSampling(value.z) or value.z != 0:
                # only modify value if necessary, to keep expression forest simpler
                value = toVector((value.x, value.y, 0))

        if prop == "shape" and not isinstance(value, BoxShape):
            raise InvalidScenarioError(
                "non-box shapes not allowed in 2D compatibility mode"
            )

        super()._specify(context, prop, value)

    @cached_property
    def visibleRegion(self):
        """The :term:`visible region` of this 2D object.

        The visible region of a 2D `Object` is a circular sector as for `OrientedPoint`,
        except that the base of the sector may be offset from ``position`` by the
        ``cameraOffset`` property (to allow modeling cameras which are not located at the
        center of the object).
        """
        camera = self.position.offsetRotated(self.heading, self.cameraOffset)
        return SectorRegion(camera, self.visibleDistance, self.heading, self.viewAngle)
