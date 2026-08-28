"""Objects representing distributions that can be sampled from."""

import collections
import functools
import itertools
import math
import numbers
import random
import typing
import warnings

import numpy

from scenic.core.errors import InvalidScenarioError, ScenicError
from scenic.core.lazy_eval import (
    LazilyEvaluable,
    dependencies,
    isLazy,
    makeDelayedFunctionCall,
    needsLazyEvaluation,
    needsSampling,
    requiredProperties,
    valueInContext,
)
from scenic.core.utils import (
    DefaultIdentityDict,
    argsToString,
    cached,
    get_type_hints,
    sqrt2,
)

## Misc


def supportInterval(thing):
    """Lower and upper bounds on this value, if known."""
    if hasattr(thing, "supportInterval"):
        return thing.supportInterval()
    elif isinstance(thing, (int, float)):
        return thing, thing
    else:
        return None, None


def supmin(*vals):
    return None if None in vals else min(vals)


def supmax(*vals):
    return None if None in vals else max(vals)


def unionOfSupports(supports):
    mins, maxes = zip(*supports)
    return supmin(*mins), supmax(*maxes)


def addSupports(sup1, sup2):
    l1, u1 = sup1
    l2, u2 = sup2
    lower = None if l1 is None or l2 is None else l1 + l2
    upper = None if u1 is None or u2 is None else u1 + u2
    return lower, upper


def underlyingFunction(thing):
    """Original function underlying a distribution wrapper."""
    func = getattr(thing, "__wrapped__", thing)
    return getattr(func, "__func__", func)


def canUnpackDistributions(func):
    """Whether the function supports iterable unpacking of distributions."""
    return getattr(func, "_canUnpackDistributions", False)


def unpacksDistributions(func):
    """Decorator indicating the function supports iterable unpacking of distributions."""
    func._canUnpackDistributions = True
    return func


class RejectionException(Exception):
    """Exception used to signal that the sample currently being generated must be rejected."""

    pass


class RandomControlFlowError(ScenicError):
    """Exception indicating illegal conditional control flow depending on a random value.

    This includes trying to iterate over a random value, making a range of random length, etc.
    """

    pass


## Abstract distributions


class Samplable(LazilyEvaluable):
    """Abstract class for values which can be sampled, possibly depending on other values.

    Samplables may specify a proxy object which must have the same distribution as the
    original after conditioning on the scenario's requirements. This allows transparent
    conditioning without modifying Samplable fields of immutable objects.

    Args:
        dependencies: sequence of values that this value may depend on (formally, objects
            for which sampled values must be provided to `sampleGiven`). It is legal to
            include values which are not instances of `Samplable`, e.g. integers.

    Attributes:
        _conditioned: proxy object as described above; set using `conditionTo`.
        _dependencies: tuple of other samplables which must be sampled before this one;
            set by the initializer and subsequently immutable.
    """

    def __init__(self, dependencies):
        deps = []
        props = set()
        for dep in dependencies:
            if isLazy(dep):
                deps.append(dep)
                props.update(requiredProperties(dep))
        super().__init__(props, deps)
        self._conditioned = self  # version (partially) conditioned on requirements

    @staticmethod
    def sampleAll(quantities):
        """Sample all the given Samplables, which may have dependencies in common.

        Reproducibility note: the order in which the quantities are given can affect the
        order in which calls to random are made, affecting the final result.
        """
        subsamples = DefaultIdentityDict()
        for q in quantities:
            if q not in subsamples:
                subsamples[q] = q.sample(subsamples) if needsSampling(q) else q
        return subsamples

    def sample(self, subsamples=None):
        """Sample this value, optionally given some values already sampled."""
        if subsamples is None:
            subsamples = DefaultIdentityDict()
        for child in self._conditioned._dependencies:
            if child not in subsamples:
                subsamples[child] = child.sample(subsamples)
        return self._conditioned.sampleGiven(subsamples)

    def sampleGiven(self, value):
        """Sample this value, given values for all its dependencies.

        Implemented by subclasses.

        Args:
            value (DefaultIdentityDict): dictionary mapping objects to their sampled
                values. Guaranteed to provide values for all objects given in the set of
                dependencies when this `Samplable` was created.
        """
        raise NotImplementedError

    def serializeValue(self, values, serializer):
        for child in self._conditioned._dependencies:
            serializer.writeSamplable(child, values)

    def deserializeValue(self, serializer, values):
        for child in self._conditioned._dependencies:
            serializer.readSamplable(child, values)
        return self._conditioned.sampleGiven(values)

    def conditionTo(self, value):
        """Condition this value to another value with the same conditional distribution."""
        assert isinstance(value, Samplable)
        self._conditioned = value

    def evaluateIn(self, context):
        """See `LazilyEvaluable.evaluateIn`."""
        value = super().evaluateIn(context)
        # Check that all dependencies have been evaluated
        assert all(not needsLazyEvaluation(dep) for dep in value._dependencies)
        return value


class ConstantSamplable(Samplable):
    """A samplable which always evaluates to a constant value.

    Only for internal use.
    """

    def __init__(self, value):
        assert not isLazy(value), value
        self.value = value
        super().__init__(())

    def sampleGiven(self, value):
        return self.value


class Distribution(Samplable):
    """Abstract class for distributions.

    .. note::

        When called during dynamic simulations (vs. scenario compilation), constructors
        for distributions return *actual sampled values*, not `Distribution` objects.

    Args:
        dependencies: values which this distribution may depend on (see `Samplable`).
        valueType: **_valueType** to use (see below), or `None` for the default.

    Attributes:
        _valueType: type of the values sampled from this distribution, or `object` if the
            type is not known.
    """

    #: Default valueType for distributions of this class, when not otherwise specified.
    _defaultValueType = object

    #: Whether this type of distribution is a deterministic function of its dependencies.
    #:
    #: For example, `Options` is implemented as deterministic by using an internal
    #: `DiscreteRange` to select which of its finitely-many options to choose from: the
    #: value of the `Options` is then completely determined by the value of the range and
    #: the values of each of the options. This simplifies serialization because these
    #: dependencies likely have simpler valueTypes than the `Options` itself (e.g. if we
    #: had a random choice between a list and a string, encoding the actual sampled value
    #: would require saving type information).
    _deterministic = False

    def __new__(cls, *args, **kwargs):
        dist = super().__new__(cls)
        # During a simulation, return a sample from the distribution immediately
        import scenic.syntax.veneer as veneer

        if veneer.simulationInProgress():
            dist.__init__(*args, **kwargs)
            sim = veneer.simulation()
            subsamples = DefaultIdentityDict()
            # If we're replaying a previous simulation, use the saved value; otherwise sample one
            if sim.replayCanContinue():
                value = sim.replaySampledValue(dist, subsamples)
            else:
                value = dist.sample(subsamples)
            # Save the value for future replay
            subsamples[dist] = value
            sim.recordSampledValue(dist, subsamples)
            return value
        elif veneer.evaluatingRequirement:
            raise InvalidScenarioError(
                "cannot define distributions inside a requirement"
                " (try moving them outside)"
            )
        else:
            return dist

    def __init__(self, *dependencies, valueType=None):
        super().__init__(dependencies)
        self._needsSampling = True
        self._isLazy = True
        if valueType is None:
            valueType = self._defaultValueType
        self._valueType = valueType

    def clone(self):
        """Construct an independent copy of this Distribution.

        Optionally implemented by subclasses.
        """
        raise NotImplementedError("clone() not supported by this distribution")

    @property
    @cached
    def isPrimitive(self):
        """Whether this is a primitive Distribution."""
        try:
            self.clone()
            return True
        except NotImplementedError:
            return False

    def serializeValue(self, values, serializer):
        """Serialize the sampled value of this distribution.

        This method is used internally by `Scenario.sceneToBytes` and related APIs.
        If you define a new subclass of `Distribution`, you probably don't need to
        override this method. If your distribution has an unusual **valueType** (i.e.
        not `float`, `int`, or `Vector`), see the documentation for `Serializer` for
        instructions on how to support serialization.
        """
        if self._deterministic:
            # It suffices to just serialize our dependencies; this is preferable to
            # saving our sampled value directly, which could be arbitrarily complex.
            super().serializeValue(values, serializer)
        else:
            # Need to save our sampled value, which can't be reconstructed from the
            # values of our dependencies. There is then no need to save the latter.
            serializer.writeValue(values[self], self._valueType)

    def deserializeValue(self, serializer, values):
        if self._deterministic:
            return super().deserializeValue(serializer, values)
        else:
            return serializer.readValue(self._valueType)

    def bucket(self, buckets=None):
        """Construct a bucketed approximation of this Distribution.

        Optionally implemented by subclasses.

        This function factors a given Distribution into a discrete distribution over
        buckets together with a distribution for each bucket. The argument *buckets*
        controls how many buckets the domain of the original Distribution is split into.
        Since the result is an independent distribution, the original must support
        `clone`.
        """
        raise NotImplementedError("bucket() not supported by this distribution")

    def supportInterval(self):
        """Compute lower and upper bounds on the value of this Distribution.

        By default returns :scenic:`(None, None)` indicating that no lower or upper bounds
        are known. Subclasses may override this method to provide more accurate results.
        """
        return None, None

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):  # ignore special attributes
            return object.__getattribute__(self, name)
        return AttributeDistribution(name, self)

    def __call__(self, *args, **kwargs):
        return OperatorDistribution("__call__", self, args, kwargs)

    def __iter__(self):
        raise RandomControlFlowError(f"cannot iterate through a random value")

    def _comparisonError(self, other):
        raise RandomControlFlowError(
            "random values cannot be compared " "(and control flow cannot depend on them)"
        )

    __lt__ = _comparisonError
    __le__ = _comparisonError
    __gt__ = _comparisonError
    __ge__ = _comparisonError
    __eq__ = _comparisonError
    __ne__ = _comparisonError

    def __hash__(self):  # need to explicitly define since we overrode __eq__
        return id(self)

    def __bool__(self):
        raise RandomControlFlowError("control flow cannot depend on a random value")


## Derived distributions


class TupleDistribution(Distribution, collections.abc.Sequence):
    """Distributions over tuples (or namedtuples, or lists)."""

    _deterministic = True

    def __init__(self, *coordinates, builder=tuple):
        super().__init__(*coordinates)
        self.coordinates = coordinates
        self.builder = builder

    def __len__(self):
        return len(self.coordinates)

    def __getitem__(self, index):
        return self.coordinates[index]

    def __iter__(self):
        yield from self.coordinates

    def sampleGiven(self, value):
        return self.builder(value[coordinate] for coordinate in self.coordinates)

    def evaluateInner(self, context):
        coordinates = (valueInContext(coord, context) for coord in self.coordinates)
        return TupleDistribution(*coordinates, builder=self.builder)

    def __repr__(self):
        coords = ", ".join(repr(c) for c in self.coordinates)
        if self.builder is tuple:
            return f"({coords},)"
        elif self.builder is list:
            return f"[{coords}]"
        else:
            return f"TupleDistribution({coords}, builder={self.builder!r})"


class SliceDistribution(Distribution):
    """Distributions over `slice` objects."""

    _deterministic = True

    def __init__(self, start, stop, step):
        super().__init__(start, stop, step, valueType=slice)
        self.start = start
        self.stop = stop
        self.step = step

    def sampleGiven(self, value):
        return slice(value[self.start], value[self.stop], value[self.step])

    def evaluateInner(self, context):
        start = valueInContext(self.start, context)
        stop = valueInContext(self.stop, context)
        step = valueInContext(self.step, context)
        return SliceDistribution(start, stop, step)

    def __repr__(self):
        return f"slice({self.start!r}, {self.stop!r}, {self.step!r})"


def toDistribution(val):
    """Wrap Python data types with Distributions, if necessary.

    For example, tuples containing Samplables need to be converted into TupleDistributions
    in order to keep track of dependencies properly.
    """
    if isinstance(val, (tuple, list)):
        coords = [toDistribution(c) for c in val]
        if any(isLazy(c) for c in coords):
            if isinstance(val, tuple) and hasattr(val, "_fields"):  # namedtuple
                builder = type(val)._make
            else:
                builder = type(val)
            return TupleDistribution(*coords, builder=builder)
    elif isinstance(val, slice):
        attrs = (val.start, val.stop, val.step)
        if any(isLazy(a) for a in attrs):
            return SliceDistribution(*attrs)
    return val


class FunctionDistribution(Distribution):
    """Distribution resulting from passing distributions to a function"""

    _deterministic = True

    def __init__(self, func, args, kwargs, support=None, valueType=None):
        args = tuple(toDistribution(arg) for arg in args)
        kwargs = {name: toDistribution(arg) for name, arg in kwargs.items()}
        if valueType is None:
            valueType = get_type_hints(func).get("return")
        super().__init__(*args, *kwargs.values(), valueType=valueType)
        self.function = func
        self.arguments = args
        self.kwargs = kwargs
        self.support = support

    def sampleGiven(self, value):
        args = []
        for arg in self.arguments:
            if isinstance(arg, StarredDistribution):
                val = value[arg]
                try:
                    iter(val)
                except TypeError:  # TODO improve backtrace
                    raise TypeError(
                        f"'{type(val).__name__}' object on line {arg.lineno} "
                        "is not iterable"
                    ) from None
                args.extend(val)
            else:
                args.append(value[arg])
        kwargs = {name: value[arg] for name, arg in self.kwargs.items()}
        return self.function(*args, **kwargs)

    def evaluateInner(self, context):
        function = valueInContext(self.function, context)
        arguments = tuple(valueInContext(arg, context) for arg in self.arguments)
        kwargs = {name: valueInContext(arg, context) for name, arg in self.kwargs.items()}
        return FunctionDistribution(function, arguments, kwargs)

    def supportInterval(self):
        if self.support is None:
            return None, None
        subsupports = (supportInterval(arg) for arg in self.arguments)
        kwss = {name: supportInterval(arg) for name, arg in self.kwargs.items()}
        return self.support(*subsupports, **kwss)

    def __repr__(self):
        return f"{self.function.__name__}({argsToString(self.arguments, self.kwargs)})"


def distributionFunction(wrapped=None, *, support=None, valueType=None):
    """Decorator for wrapping a function so that it can take distributions as arguments.

    This decorator is mainly for internal use, and is not necessary when defining a
    function in a Scenic file. It is, however, needed when calling external functions
    which contain control flow or other operations that Scenic distribution objects
    (representing random values) do not support.
    """
    if wrapped is None:  # written without arguments as @distributionFunction
        return lambda wrapped: distributionFunction(
            wrapped, support=support, valueType=valueType
        )

    @unpacksDistributions
    @functools.wraps(wrapped)
    def helper(*args, **kwargs):
        args = tuple(toDistribution(arg) for arg in args)
        kwargs = {name: toDistribution(arg) for name, arg in kwargs.items()}
        if any(needsSampling(arg) for arg in itertools.chain(args, kwargs.values())):
            return FunctionDistribution(wrapped, args, kwargs, support, valueType)
        elif any(
            needsLazyEvaluation(arg) for arg in itertools.chain(args, kwargs.values())
        ):
            # recursively call this helper (not the original function), since the
            # delayed arguments may evaluate to distributions, in which case we'll
            # have to make a FunctionDistribution
            return makeDelayedFunctionCall(helper, args, kwargs)
        else:
            return wrapped(*args, **kwargs)

    return helper


def monotonicDistributionFunction(method, valueType=None):
    """Like distributionFunction, but additionally specifies that the function is monotonic."""

    def support(*subsupports, **kwss):
        mins, maxes = zip(*subsupports)
        kwmins = {name: interval[0] for name, interval in kwss.items()}
        kwmaxes = {name: interval[1] for name, interval in kwss.items()}
        l = None if None in mins or None in kwmins else method(*mins, **kwmins)
        r = None if None in maxes or None in kwmaxes else method(*maxes, **kwmaxes)
        return l, r

    return distributionFunction(method, support=support, valueType=valueType)


class StarredDistribution(Distribution):
    """A placeholder for the iterable unpacking operator * applied to a distribution."""

    _deterministic = True

    def __init__(self, value, lineno):
        assert isinstance(value, Distribution)
        self.value = value
        self.lineno = lineno  # for error handling when unpacking fails
        super().__init__(value, valueType=value._valueType)

    def sampleGiven(self, value):
        return value[self.value]

    def evaluateInner(self, context):
        return StarredDistribution(valueInContext(self.value, context), self.lineno)

    def __repr__(self):
        return f"*{self.value!r}"


class MethodDistribution(Distribution):
    """Distribution resulting from passing distributions to a method of a fixed object"""

    _deterministic = True

    def __init__(self, method, obj, args, kwargs, valueType=None):
        args = tuple(toDistribution(arg) for arg in args)
        kwargs = {name: toDistribution(arg) for name, arg in kwargs.items()}
        if valueType is None:
            valueType = get_type_hints(method).get("return")
        super().__init__(*args, *kwargs.values(), valueType=valueType)
        self.method = method
        self.object = obj
        self.arguments = args
        self.kwargs = kwargs

    def sampleGiven(self, value):
        args = []
        for arg in self.arguments:
            if isinstance(arg, StarredDistribution):
                args.extend(value[arg.value])
            else:
                args.append(value[arg])
        kwargs = {name: value[arg] for name, arg in self.kwargs.items()}
        return self.method(self.object, *args, **kwargs)

    def evaluateInner(self, context):
        obj = valueInContext(self.object, context)
        arguments = tuple(valueInContext(arg, context) for arg in self.arguments)
        kwargs = {name: valueInContext(arg, context) for name, arg in self.kwargs.items()}
        return MethodDistribution(self.method, obj, arguments, kwargs)

    def __repr__(self):
        args = argsToString(self.arguments, self.kwargs)
        return f"{self.object!r}.{self.method.__name__}({args})"


def distributionMethod(method=None, *, identity=None):
    """Decorator for wrapping a method so that it can take distributions as arguments."""
    if method is None:
        return lambda method: distributionMethod(method, identity=identity)

    @unpacksDistributions
    @functools.wraps(method)
    def helper(self, *args, **kwargs):
        if identity is not None and self == identity:
            return toDistribution(args[0])
        args = tuple(toDistribution(arg) for arg in args)
        kwargs = {name: toDistribution(arg) for name, arg in kwargs.items()}
        if any(needsSampling(arg) for arg in itertools.chain(args, kwargs.values())):
            return MethodDistribution(method, self, args, kwargs)
        elif any(
            needsLazyEvaluation(arg) for arg in itertools.chain(args, kwargs.values())
        ):
            # see analogous comment in distributionFunction
            return makeDelayedFunctionCall(helper, (self,) + args, kwargs)
        else:
            return method(self, *args, **kwargs)

    return helper


class AttributeDistribution(Distribution):
    """Distribution resulting from accessing an attribute of a distribution"""

    _deterministic = True

    def __init__(self, attribute, obj, valueType=None):
        if valueType is None:
            ty = type_support.underlyingType(obj)
            valueType = self.inferType(ty, attribute)
        super().__init__(obj, valueType=valueType)
        self.attribute = attribute
        self.object = obj

    @staticmethod
    def inferType(ty, attribute):
        """Attempt to infer the type of the given attribute."""
        # If the object's type is known, see if we have an attribute type annotation.
        try:
            hints = get_type_hints(ty)
            attrTy = hints.get(attribute)
            if attrTy:
                return attrTy
        except Exception:
            pass  # couldn't get type annotations

        # Handle unions
        origin = type_support.get_type_origin(ty)
        if origin == typing.Union:
            types = []
            for option in type_support.get_type_args(ty):
                if option is type(None) and not hasattr(None, attribute):
                    # None does not have this attribute; accessing it will raise an
                    # exception, so we can ignore this case for type inference.
                    continue
                res = AttributeDistribution.inferType(option, attribute)
                types.append(res)
            return type_support.unifierOfTypes(types) if types else object

        # Check for a @property defined on the class with a return type
        if (
            ty is not object
            and (func := getattr(ty, attribute, None))
            and isinstance(func, property)
        ):
            return get_type_hints(func.fget).get("return")

        # We can't tell what the attribute type is.
        return object

    def sampleGiven(self, value):
        obj = value[self.object]
        return getattr(obj, self.attribute)

    def evaluateInner(self, context):
        obj = valueInContext(self.object, context)
        return AttributeDistribution(self.attribute, obj)

    def supportInterval(self):
        obj = self.object
        if isinstance(obj, MultiplexerDistribution):
            attrs = (getattr(opt, self.attribute) for opt in obj.options)
            return unionOfSupports(supportInterval(attr) for attr in attrs)
        return None, None

    def __call__(self, *args, **kwargs):
        vty = self.object._valueType
        retTy = None
        if vty is not object:
            func = getattr(vty, self.attribute, None)
            if func:
                if isinstance(func, property):
                    func = func.fget
                retTy = get_type_hints(func).get("return")
        return OperatorDistribution("__call__", self, args, kwargs, valueType=retTy)

    def __repr__(self):
        return f"{self.object!r}.{self.attribute}"


class OperatorDistribution(Distribution):
    """Distribution resulting from applying an operator to one or more distributions"""

    _deterministic = True

    def __init__(self, operator, obj, operands, kwoperands, valueType=None):
        operands = tuple(toDistribution(arg) for arg in operands)
        kwoperands = {key: toDistribution(kwarg) for key, kwarg in kwoperands.items()}
        dependencies = operands + tuple(kwoperands.values())
        if valueType is None:
            ty = type_support.underlyingType(obj)
            valueType = self.inferType(ty, operator, operands, kwoperands)
        super().__init__(obj, *dependencies, valueType=valueType)
        self.operator = operator
        self.object = obj
        self.operands = operands
        self.kwoperands = kwoperands
        self.symbol = allowedReversibleOperators.get(operator)
        if self.symbol:
            if operator[:3] == "__r":
                self.reverse = "__" + operator[3:]
            else:
                self.reverse = "__r" + operator[2:]
        else:
            self.reverse = None

    @staticmethod
    def inferType(ty, operator, operands, kwoperands):
        """Attempt to infer the result type of the given operator application."""
        # If the object's type is known, see if we have a return type annotation.
        origin = type_support.get_type_origin(ty)
        op = getattr(origin if origin else ty, operator, None)
        if op:
            retTy = get_type_hints(op).get("return")
            if retTy:
                return retTy

        # Handle unions
        if origin == typing.Union:
            types = []
            for option in type_support.get_type_args(ty):
                if option is type(None) and not hasattr(None, operator):
                    # None does not support this operator; using it will raise an
                    # exception, so we can ignore this case for type inference.
                    continue
                res = OperatorDistribution.inferType(
                    option, operator, operands, kwoperands
                )
                types.append(res)
            return type_support.unifierOfTypes(types) if types else object

        # The supported arithmetic operations on scalars all return scalars.
        def scalar(thing):
            ty = type_support.underlyingType(thing)
            return type_support.canCoerceType(ty, float)

        if type_support.canCoerceType(ty, float) and all(
            scalar(operand) for operand in operands
        ):
            return float

        # Handle __getitem__ for known container types.
        if operator == "__getitem__" and len(operands) == 1:
            if origin and isinstance(origin, type):  # parametrized ordinary type
                res = object
                index = operands[0]
                ity = type_support.underlyingType(index)
                isSlice = not hasattr(ity, "__index__")
                if issubclass(origin, list):
                    res = ty if isSlice else type_support.get_type_args(ty)[0]
                elif issubclass(origin, tuple):
                    args = type_support.get_type_args(ty)
                    if type_support.is_typing_generic(ty):
                        # If annotation used Tuple instead of tuple, preserve it
                        origin = typing.Tuple
                    if len(args) == 2 and args[1] is ...:
                        # homogeneous variable-length tuple
                        res = ty if isSlice else args[0]
                    elif not needsSampling(index):
                        res = args[index]
                        if isSlice:
                            res = origin[res]
                    else:
                        # can't pin down the index, so cover all possibilities
                        if any(arg is typing.Any for arg in args):
                            return origin if isSlice else object
                        res = typing.Union[args]
                        if isSlice:
                            res = origin[res, ...]
                elif issubclass(origin, (dict, typing.Mapping, collections.abc.Mapping)):
                    res = type_support.get_type_args(ty)[1]
                return object if res is typing.Any else res
            elif not origin:  # ordinary type
                if issubclass(ty, str):
                    return str

        # We can't tell what the result type is.
        return object

    def sampleGiven(self, value):
        first = value[self.object]
        rest = [value[child] for child in self.operands]
        kwargs = {key: value[child] for key, child in self.kwoperands.items()}
        op = getattr(first, self.operator)
        result = op(*rest, **kwargs)
        if result is NotImplemented and self.reverse:
            assert len(rest) == 1 and len(kwargs) == 0
            rop = getattr(rest[0], self.reverse)
            result = rop(first)
        if result is NotImplemented and self.symbol:
            raise TypeError(
                f"unsupported operand type(s) for {self.symbol}: "
                f"'{type(first).__name__}' and '{type(rest[0]).__name__}'"
            )
        return result

    def evaluateInner(self, context):
        obj = valueInContext(self.object, context)
        operands = tuple(valueInContext(arg, context) for arg in self.operands)
        kwoperands = {
            key: valueInContext(kwarg, context) for key, kwarg in self.kwoperands.items()
        }
        return OperatorDistribution(self.operator, obj, operands, kwoperands)

    def supportInterval(self):
        if self.operator in (
            "__add__",
            "__radd__",
            "__sub__",
            "__rsub__",
            "__mul__",
            "__rmul__",
            "__truediv__",
            "__rtruediv__",
        ):
            assert len(self.operands) == 1 and len(self.kwoperands) == 0
            l1, r1 = supportInterval(self.object)
            l2, r2 = supportInterval(self.operands[0])
            if l1 is None or l2 is None or r1 is None or r2 is None:
                return None, None
            if self.operator == "__add__" or self.operator == "__radd__":
                l = l1 + l2
                r = r1 + r2
            elif self.operator == "__sub__":
                l = l1 - r2
                r = r1 - l2
            elif self.operator == "__rsub__":
                l = l2 - r1
                r = r2 - l1
            elif self.operator in ("__mul__", "__rmul__"):
                prods = (l1 * l2, l1 * r2, r1 * l2, r1 * r2)
                l = min(*prods)
                r = max(*prods)
            elif self.operator == "__truediv__":
                if l2 > 0:
                    l = l1 / r2 if l1 >= 0 else l1 / l2
                    r = r1 / l2 if r1 >= 0 else r1 / r2
                else:
                    l, r = None, None  # TODO improve
            elif self.operator == "__rtruediv__":
                if l1 > 0:
                    l = l2 / r1 if l2 >= 0 else l2 / l1
                    r = r2 / l1 if r2 >= 0 else r2 / r1
                else:
                    l, r = None, None
            else:
                raise AssertionError(f"unexpected operator {self.operator}")
            return l, r
        elif self.operator in ("__neg__", "__abs__"):
            assert len(self.operands) == 0 and len(self.kwoperands) == 0
            l, r = supportInterval(self.object)
            if self.operator == "__neg__":
                return -r, -l
            elif self.operator == "__abs__":
                if r < 0:
                    return -r, -l
                elif l < 0:
                    return 0, max(-l, r)
                else:
                    return l, r
            else:
                raise AssertionError(f"unexpected operator {self.operator}")
        return None, None

    def __repr__(self):
        return f"{self.object!r}.{self.operator}({argsToString(self.operands)})"


# Operators which can be applied to distributions.
# Note that we deliberately do not include comparisons and __bool__,
# since Scenic does not allow control flow to depend on random variables.
allowedOperators = (
    "__neg__",
    "__pos__",
    "__abs__",
    "__round__",
    "__getitem__",
    ("__len__", int),
)
allowedReversibleOperators = {
    "__add__": "+",
    "__radd__": "+",
    "__sub__": "-",
    "__rsub__": "-",
    "__mul__": "*",
    "__rmul__": "*",
    "__truediv__": "/",
    "__rtruediv__": "/",
    "__floordiv__": "//",
    "__rfloordiv__": "//",
    "__mod__": "%",
    "__rmod__": "%",
    "__divmod__": "divmod()",
    "__rdivmod__": "divmod()",
    "__pow__": "**",
    "__rpow__": "**",
}


def makeOperatorHandler(op, ty):
    # Various special cases to simplify the expression forest by removing some
    # operations that do nothing (such as adding zero to a random number).
    if op in ("__add__", "__radd__", "__sub__"):

        def handler(self, arg):
            if (
                not isLazy(arg)
                and issubclass(self._valueType, numbers.Number)
                and arg == 0
            ):
                return self
            return OperatorDistribution(op, self, (arg,), {}, valueType=ty)

    elif op in ("__mul__", "__rmul__"):

        def handler(self, arg):
            if not isLazy(arg):
                if issubclass(self._valueType, numbers.Number) and arg == 1:
                    return self
                from scenic.core.vectors import Orientation, globalOrientation

                if issubclass(self._valueType, Orientation) and arg == globalOrientation:
                    return self
            return OperatorDistribution(op, self, (arg,), {}, valueType=ty)

    elif op in ("__truediv__", "__floordiv__", "__pow__"):

        def handler(self, arg):
            if (
                not isLazy(arg)
                and issubclass(self._valueType, numbers.Number)
                and arg == 1
            ):
                return self
            return OperatorDistribution(op, self, (arg,), {}, valueType=ty)

    else:
        # The general case.
        def handler(self, *args):
            return OperatorDistribution(op, self, args, {}, valueType=ty)

    return handler


for data in allowedOperators:
    if isinstance(data, tuple):
        op, ty = data
    else:
        op = data
        ty = None
    setattr(Distribution, op, makeOperatorHandler(op, ty))
for op in allowedReversibleOperators:
    setattr(Distribution, op, makeOperatorHandler(op, None))

import scenic.core.type_support as type_support


class MultiplexerDistribution(Distribution):
    """Distribution selecting among values based on another distribution."""

    _deterministic = True

    def __init__(self, index, options):
        self.index = index
        self.options = tuple(toDistribution(opt) for opt in options)
        assert len(self.options) > 0
        valueType = type_support.unifyingType(self.options)
        super().__init__(index, *self.options, valueType=valueType)

    def sampleGiven(self, value):
        idx = value[self.index]
        assert 0 <= idx < len(self.options), (idx, len(self.options))
        return value[self.options[idx]]

    def serializeValue(self, values, serializer):
        # We override this method to save space: we don't need to serialize all
        # of our options, only the one we're selecting.
        serializer.writeSamplable(self.index, values)
        choice = self.options[values[self.index]]
        serializer.writeSamplable(choice, values)

    def deserializeValue(self, serializer, values):
        serializer.readSamplable(self.index, values)
        choice = self.options[values[self.index]]
        serializer.readSamplable(choice, values)
        return values[choice]

    def evaluateInner(self, context):
        return type(self)(
            valueInContext(self.index, context),
            (valueInContext(opt, context) for opt in self.options),
        )

    def supportInterval(self):
        return unionOfSupports(supportInterval(opt) for opt in self.options)


## Simple distributions


class Range(Distribution):
    """Uniform distribution over a range"""

    def __init__(self, low, high):
        low = type_support.toScalar(low, f"Range endpoint {low} is not a scalar")
        high = type_support.toScalar(high, f"Range endpoint {high} is not a scalar")
        super().__init__(low, high, valueType=float)
        self.low = low
        self.high = high

    def clone(self):
        return type(self)(self.low, self.high)

    def bucket(self, buckets=None):
        if buckets is None:
            buckets = 5
        if not isinstance(buckets, int) or buckets < 1:
            raise ValueError(f"Invalid buckets for Range.bucket: {buckets}")
        if not isinstance(self.low, float) or not isinstance(self.high, float):
            raise RuntimeError(f"Cannot bucket Range with non-constant endpoints")
        endpoints = numpy.linspace(self.low, self.high, buckets + 1)
        ranges = []
        for i, left in enumerate(endpoints[:-1]):
            right = endpoints[i + 1]
            ranges.append(Range(left, right))
        return Options(ranges)

    def sampleGiven(self, value):
        return random.uniform(value[self.low], value[self.high])

    def evaluateInner(self, context):
        low = valueInContext(self.low, context)
        high = valueInContext(self.high, context)
        return Range(low, high)

    def supportInterval(self):
        return unionOfSupports((supportInterval(self.low), supportInterval(self.high)))

    def __repr__(self):
        return f"Range({self.low!r}, {self.high!r})"


class Normal(Distribution):
    """Normal distribution"""

    def __init__(self, mean, stddev):
        mean = type_support.toScalar(mean, f"Normal mean {mean} is not a scalar")
        stddev = type_support.toScalar(stddev, f"Normal stddev {stddev} is not a scalar")
        super().__init__(mean, stddev, valueType=float)
        self.mean = mean
        self.stddev = stddev

    @staticmethod
    def cdf(mean, stddev, x):
        return (1 + math.erf((x - mean) / (sqrt2 * stddev))) / 2

    @staticmethod
    def cdfinv(mean, stddev, x):
        import scipy  # slow import not often needed

        return mean + (sqrt2 * stddev * scipy.special.erfinv(2 * x - 1))

    def clone(self):
        return type(self)(self.mean, self.stddev)

    def bucket(self, buckets=None):
        if not isinstance(self.stddev, float):  # TODO relax restriction?
            raise RuntimeError(
                f"Cannot bucket Normal with non-constant standard deviation"
            )
        if buckets is None:
            buckets = 5
        if isinstance(buckets, int):
            if buckets < 1:
                raise ValueError(f"Invalid buckets for Normal.bucket: {buckets}")
            elif buckets == 1:
                endpoints = []
            elif buckets == 2:
                endpoints = [0]
            else:
                left = self.stddev * (-(buckets - 3) / 2 - 0.5)
                right = self.stddev * ((buckets - 3) / 2 + 0.5)
                endpoints = numpy.linspace(left, right, buckets - 1)
        else:
            endpoints = tuple(buckets)
            for i, v in enumerate(endpoints[:-1]):
                if v >= endpoints[i + 1]:
                    raise ValueError(
                        "Non-increasing bucket endpoints for "
                        f"Normal.bucket: {endpoints}"
                    )
        if len(endpoints) == 0:
            return Options([self.clone()])
        buckets = [(-math.inf, endpoints[0])]
        buckets.extend((v, endpoints[i + 1]) for i, v in enumerate(endpoints[:-1]))
        buckets.append((endpoints[-1], math.inf))
        pieces = []
        probs = []
        for left, right in buckets:
            pieces.append(self.mean + TruncatedNormal(0, self.stddev, left, right))
            prob = Normal.cdf(0, self.stddev, right) - Normal.cdf(0, self.stddev, left)
            probs.append(prob)
        assert math.isclose(math.fsum(probs), 1), probs
        return Options(dict(zip(pieces, probs)))

    def sampleGiven(self, value):
        return random.gauss(value[self.mean], value[self.stddev])

    def evaluateInner(self, context):
        mean = valueInContext(self.mean, context)
        stddev = valueInContext(self.stddev, context)
        return Normal(mean, stddev)

    def __repr__(self):
        return f"Normal({self.mean!r}, {self.stddev!r})"


class TruncatedNormal(Normal):
    """Truncated normal distribution."""

    def __init__(self, mean, stddev, low, high):
        if not isinstance(low, (float, int)) or not isinstance(
            high, (float, int)
        ):  # TODO relax restriction?
            raise ValueError("Endpoints of TruncatedNormal must be constant")
        if low >= high:
            raise ValueError(
                "low endpoint of TruncatedNormal must be below high endpoint"
            )
        super().__init__(mean, stddev)
        self.low = low
        self.high = high

    def clone(self):
        return type(self)(self.mean, self.stddev, self.low, self.high)

    def bucket(self, buckets=None):
        if not isinstance(self.stddev, float):  # TODO relax restriction?
            raise RuntimeError(
                "Cannot bucket TruncatedNormal with " "non-constant standard deviation"
            )
        if buckets is None:
            buckets = 5
        if isinstance(buckets, int):
            if buckets < 1:
                raise ValueError(f"Invalid buckets for TruncatedNormal.bucket: {buckets}")
            endpoints = numpy.linspace(self.low, self.high, buckets + 1)
        else:
            endpoints = tuple(buckets)
            if len(endpoints) < 2:
                raise ValueError(
                    "Too few bucket endpoints for " f"TruncatedNormal.bucket: {endpoints}"
                )
            if endpoints[0] != self.low or endpoints[-1] != self.high:
                raise ValueError(
                    f"TruncatedNormal.bucket endpoints {endpoints} " "do not match domain"
                )
            for i, v in enumerate(endpoints[:-1]):
                if v >= endpoints[i + 1]:
                    raise ValueError(
                        "Non-increasing bucket endpoints for "
                        f"TruncatedNormal.bucket: {endpoints}"
                    )
        pieces, probs = [], []
        for i, left in enumerate(endpoints[:-1]):
            right = endpoints[i + 1]
            pieces.append(TruncatedNormal(self.mean, self.stddev, left, right))
            prob = Normal.cdf(self.mean, self.stddev, right) - Normal.cdf(
                self.mean, self.stddev, left
            )
            probs.append(prob)
        return Options(dict(zip(pieces, probs)))

    def sampleGiven(self, value):
        # TODO switch to method less prone to underflow?
        mean, stddev = value[self.mean], value[self.stddev]
        alpha = (self.low - mean) / stddev
        beta = (self.high - mean) / stddev
        alpha_cdf = Normal.cdf(0, 1, alpha)
        beta_cdf = Normal.cdf(0, 1, beta)
        if beta_cdf - alpha_cdf < 1e-15:
            warnings.warn("low precision when sampling TruncatedNormal")
        unif = random.random()
        p = alpha_cdf + unif * (beta_cdf - alpha_cdf)
        return mean + (stddev * Normal.cdfinv(0, 1, p))

    def evaluateInner(self, context):
        mean = valueInContext(self.mean, context)
        stddev = valueInContext(self.stddev, context)
        return TruncatedNormal(mean, stddev, self.low, self.high)

    def supportInterval(self):
        return self.low, self.high

    def __repr__(self):
        return f"TruncatedNormal({self.mean!r}, {self.stddev!r}, {self.low!r}, {self.high!r})"


class DiscreteRange(Distribution):
    """Distribution over a range of integers."""

    def __init__(self, low, high, weights=None, emptyMessage="empty DiscreteRange"):
        if weights:
            if not isinstance(low, int):
                raise TypeError("weighted DiscreteRange left endpoint must be an integer")
            if not isinstance(high, int):
                raise TypeError(
                    "weighted DiscreteRange right endpoint must be an integer"
                )
            if not low <= high:
                raise ValueError(
                    f"DiscreteRange lower bound {low} is above upper bound {high}"
                )
            self.low, self.high = low, high
            weights = tuple(weights)
            if len(weights) != high - low + 1:
                raise ValueError("weighted DiscreteRange with wrong number of weights")
            self.weights = weights
            self.cumulativeWeights = tuple(itertools.accumulate(weights))
            self.options = tuple(range(low, high + 1))
        else:
            self.low = type_support.toScalar(
                low, "DiscreteRange left endpoint not a scalar"
            )
            self.high = type_support.toScalar(
                high, "DiscreteRange right endpoint not a scalar"
            )
            self.weights = None
        self.emptyMessage = emptyMessage
        super().__init__(self.low, self.high, valueType=int)

    def clone(self):
        return type(self)(self.low, self.high, self.weights, self.emptyMessage)

    def bucket(self, buckets=None):
        return self.clone()  # already bucketed

    def sampleGiven(self, value):
        if self.weights:
            return random.choices(self.options, cum_weights=self.cumulativeWeights)[0]
        left, right = math.ceil(value[self.low]), math.floor(value[self.high])
        if right < left:
            raise RejectionException(self.emptyMessage)
        return random.randint(left, right)

    def supportInterval(self):
        ll, lh = supportInterval(self.low)
        hl, hh = supportInterval(self.high)
        return ll, hh

    def __repr__(self):
        weights = self.weights
        if all(weight == weights[0] for weight in weights):
            return f"DiscreteRange({self.low!r}, {self.high!r})"
        else:
            return f"DiscreteRange({self.low!r}, {self.high!r}, {self.weights})"


class Options(MultiplexerDistribution):
    """Distribution over a finite list of options.

    Specified by a dict giving probabilities; otherwise uniform over a given iterable.
    """

    def __init__(self, opts):
        if isinstance(opts, dict):
            options, weights = [], []
            for opt, prob in opts.items():
                if not isinstance(prob, (float, int)):
                    raise TypeError(
                        f"discrete distribution weight {prob}" " is not a constant number"
                    )
                if prob < 0:
                    raise ValueError(f"discrete distribution weight {prob} is negative")
                if prob == 0:
                    continue
                options.append(opt)
                weights.append(prob)
            self.optWeights = dict(zip(options, weights))
        else:
            weights = None
            options = tuple(opts)
            self.optWeights = None
        if len(options) == 0:
            raise RejectionException(
                "tried to make discrete distribution over empty domain!"
            )

        index = self.makeSelector(len(options) - 1, weights)
        super().__init__(index, options)

    @staticmethod
    def makeSelector(n, weights):
        return DiscreteRange(0, n, weights)

    def clone(self):
        return type(self)(self.optWeights if self.optWeights else self.options)

    def bucket(self, buckets=None):
        return self.clone()  # already bucketed

    def evaluateInner(self, context):
        if self.optWeights is None:
            return type(self)(valueInContext(opt, context) for opt in self.options)
        else:
            return type(self)(
                {valueInContext(opt, context): wt for opt, wt in self.optWeights.items()}
            )

    def __repr__(self):
        if self.optWeights is not None:
            return f"{type(self).__name__}({self.optWeights!r})"
        else:
            args = ", ".join(repr(opt) for opt in self.options)
            return f"{type(self).__name__}({args})"


@unpacksDistributions
def Uniform(*opts):
    """Uniform distribution over a finite list of options.

    Implemented as an instance of :obj:`Options` when the set of options is known
    statically, and an instance of `UniformDistribution` otherwise.
    """
    if any(isinstance(opt, StarredDistribution) for opt in opts):
        return UniformDistribution(opts)
    else:
        return Options(opts)


class UniformDistribution(Distribution):
    """Uniform distribution over a variable number of options.

    See :obj:`Options` for the more common uniform distribution over a fixed number
    of options. This class is for the special case where iterable unpacking is
    applied to a distribution, so that the number of options is unknown at
    compile time.
    """

    _deterministic = True

    def __init__(self, opts):
        self.options = opts
        valueType = type_support.unifyingType(self.options)
        length = 0
        for opt in opts:
            if isinstance(opt, StarredDistribution):
                length += opt.__len__()
            else:
                length += 1
        self.selector = DiscreteRange(
            0, length - 1, emptyMessage="uniform distribution over empty domain"
        )
        super().__init__(*self.options, self.selector, valueType=valueType)

    def clone(self):
        return type(self)(self.options)

    def sampleGiven(self, value):
        index = value[self.selector]
        opts = []
        for opt in self.options:
            if isinstance(opt, StarredDistribution):
                opts.extend(value[opt])
            else:
                opts.append(value[opt])
        assert 0 <= index < len(opts)
        return opts[index]

    def evaluateInner(self, context):
        opts = tuple(valueInContext(opt, context) for opt in self.options)
        return UniformDistribution(opts)

    def __repr__(self):
        return f"UniformDistribution({self.options!r})"
