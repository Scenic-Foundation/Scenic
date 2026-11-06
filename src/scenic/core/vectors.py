"""Scenic vectors and vector fields."""

from __future__ import annotations

import collections
import functools
import importlib.metadata
import itertools
import math
from math import cos, sin
import numbers
import random
import struct
import sys
import typing
import warnings

import numpy
from scipy.spatial.transform import Rotation
import shapely.geometry

from scenic.core.distributions import (
    Distribution,
    MethodDistribution,
    RejectionException,
    Samplable,
    TupleDistribution,
    distributionFunction,
    distributionMethod,
    makeOperatorHandler,
    needsSampling,
)
from scenic.core.geometry import hypot, makeShapelyPoint, normalizeAngle
from scenic.core.lazy_eval import (
    isLazy,
    makeDelayedFunctionCall,
    needsLazyEvaluation,
    valueInContext,
)
from scenic.core.type_support import (
    CoercionFailure,
    canCoerceType,
    coerceToFloat,
    toOrientation,
)
from scenic.core.utils import argsToString, cached_property


class VectorDistribution(Distribution):
    """A distribution over Vectors."""

    _defaultValueType = None  # will be set after Vector is defined

    def toVector(self):
        return self


class VectorOperatorDistribution(VectorDistribution):
    """Vector version of OperatorDistribution."""

    def __init__(self, operator, obj, operands):
        super().__init__(obj, *operands)
        self.operator = operator
        self.object = obj
        self.operands = operands

    def sampleGiven(self, value):
        first = value[self.object]
        rest = (value[child] for child in self.operands)
        op = getattr(first, self.operator)
        return op(*rest)

    def evaluateInner(self, context):
        obj = valueInContext(self.object, context)
        operands = tuple(valueInContext(arg, context) for arg in self.operands)
        return VectorOperatorDistribution(self.operator, obj, operands)

    def __repr__(self):
        return f"{self.object!r}.{self.operator}({argsToString(self.operands)})"


class VectorMethodDistribution(VectorDistribution):
    """Vector version of MethodDistribution."""

    def __init__(self, method, obj, args, kwargs):
        super().__init__(*args, *kwargs.values())
        self.method = method
        self.object = obj
        self.arguments = args
        self.kwargs = kwargs

    def sampleGiven(self, value):
        args = (value[arg] for arg in self.arguments)
        kwargs = {name: value[arg] for name, arg in self.kwargs.items()}
        return self.method(self.object, *args, **kwargs)

    def evaluateInner(self, context):
        obj = valueInContext(self.object, context)
        arguments = tuple(valueInContext(arg, context) for arg in self.arguments)
        kwargs = {name: valueInContext(arg, context) for name, arg in self.kwargs.items()}
        return VectorMethodDistribution(self.method, obj, arguments, kwargs)

    def __repr__(self):
        args = argsToString(self.arguments, self.kwargs)
        return f"{self.object!r}.{self.method.__name__}({args})"


def scalarOperator(method):
    """Decorator for vector operators that yield scalars."""
    op = method.__name__
    setattr(VectorDistribution, op, makeOperatorHandler(op, float))

    @functools.wraps(method)
    def helper(self, *args, **kwargs):
        if any(needsSampling(arg) for arg in itertools.chain(args, kwargs.values())):
            return MethodDistribution(method, self, args, kwargs)
        else:
            return method(self, *args, **kwargs)

    return helper


def makeVectorOperatorHandler(op, zeroIdentity):
    def handler(self, *args):
        # If the zero vector is the identity for this operator, and we can tell
        # that the operand is zero, simplify the expression forest.
        if (
            zeroIdentity
            and not isLazy(args[0])
            and all(coord == 0 for coord in args[0].coordinates)
        ):
            return self

        # The general case.
        return VectorOperatorDistribution(op, self, args)

    return handler


def vectorOperator(method, preservesZero=False, zeroIdentity=False):
    """Decorator for vector operators that yield vectors."""
    op = method.__name__
    setattr(VectorDistribution, op, makeVectorOperatorHandler(op, zeroIdentity))

    @functools.wraps(method)
    def helper(self, *args):
        # If this operator preserves the zero vector, and we can tell that self
        # is zero, simplify the expression forest.
        if (
            preservesZero
            and not needsSampling(self)
            and all(coord == 0 for coord in self.coordinates)
        ):
            return self

        # General cases when the arguments are lazy.
        if any(needsSampling(arg) for arg in args):
            if needsSampling(self):
                return VectorOperatorDistribution(op, self, args)
            return VectorMethodDistribution(method, self, args, {})
        elif any(needsLazyEvaluation(arg) for arg in args):
            # see analogous comment in distributionFunction
            return makeDelayedFunctionCall(helper, args, {})

        # If zero is the identity, simplify when possible (see above).
        if (
            zeroIdentity
            and isinstance(args[0], (Vector, tuple, list, numpy.ndarray))
            and all(coord == 0 for coord in args[0])
        ):
            return self

        # General case when the arguments are not lazy.
        if needsSampling(self):
            return VectorOperatorDistribution(op, self, args)
        else:
            return method(self, *args)

    return helper


def zeroPreservingVectorOperator(method):
    return vectorOperator(method, preservesZero=True)


def zeroIdentityVectorOperator(method):
    return vectorOperator(method, zeroIdentity=True)


def vectorDistributionMethod(method):
    """Decorator for methods that produce vectors. See distributionMethod."""

    @functools.wraps(method)
    def helper(self, *args, **kwargs):
        if any(needsSampling(arg) for arg in itertools.chain(args, kwargs.values())):
            return VectorMethodDistribution(method, self, args, kwargs)
        elif any(
            needsLazyEvaluation(arg) for arg in itertools.chain(args, kwargs.values())
        ):
            # see analogous comment in distributionFunction
            return makeDelayedFunctionCall(helper, (self,) + args, kwargs)
        else:
            return method(self, *args, **kwargs)

    return helper


class Orientation:
    """An orientation in 3D space."""

    def __init__(self, rotation):
        if not isinstance(rotation, Rotation):
            raise TypeError(
                "Orientation's 'rotation' parameter must be a SciPy rotation."
                " Perhaps you want to use a factory method?"
            )
        self.r = rotation
        self.q = rotation.as_quat()

    @classmethod
    def fromQuaternion(cls, quaternion) -> Orientation:
        """Create an `Orientation` from a quaternion (of the form (x,y,z,w))"""
        r = Rotation.from_quat(quaternion)
        return cls(r)

    @classmethod
    @distributionFunction
    def fromEuler(cls, yaw, pitch, roll) -> Orientation:
        """Create an `Orientation` from yaw, pitch, and roll angles (in radians)."""
        return cls._fromEuler(yaw, pitch, roll)

    @classmethod
    def _fromEuler(cls, yaw, pitch, roll) -> Orientation:
        # Inner version of `fromEuler` which doesn't accept distributions.
        r = Rotation.from_euler("ZXY", [yaw, pitch, roll], degrees=False)
        return cls(r)

    @classmethod
    def _fromHeading(cls, heading) -> Orientation:
        # This method is faster than `from_euler` if we only have 1 angle.
        r = Rotation.from_rotvec([0, 0, heading], degrees=False)
        return cls(r)

    @property
    def w(self) -> float:
        return self.q[3]

    @property
    def x(self) -> float:
        return self.q[0]

    @property
    def y(self) -> float:
        return self.q[1]

    @property
    def z(self) -> float:
        return self.q[2]

    @property
    def yaw(self) -> float:
        """Yaw in the global coordinate system."""
        return self.eulerAngles[0]

    @property
    def pitch(self) -> float:
        """Pitch in the global coordinate system."""
        return self.eulerAngles[1]

    @property
    def roll(self) -> float:
        """Roll in the global coordinate system."""
        return self.eulerAngles[2]

    @staticmethod
    def _coerce(thing) -> Orientation:
        if isinstance(thing, (float, int)):  # fast path
            return Orientation._fromHeading(thing)
        elif isinstance(thing, Orientation):
            return thing
        elif hasattr(thing, "toOrientation"):
            return thing.toOrientation()
        elif isinstance(thing, Vector):
            return Orientation._fromEuler(*thing)
        elif isinstance(thing, (tuple, list)):
            if len(thing) != 3:
                raise CoercionFailure(
                    "Cannot coerce a tuple/list of length not 3 to an orientation"
                )
            return Orientation._fromEuler(*thing)
        elif canCoerceType(type(thing), float):
            return Orientation._fromHeading(coerceToFloat(thing))
        else:
            raise CoercionFailure

    @staticmethod
    def _canCoerceType(ty):
        if issubclass(ty, (tuple, list, Vector, Orientation)):
            return True
        return canCoerceType(ty, float) or hasattr(ty, "toOrientation")

    @cached_property
    def eulerAngles(self) -> typing.Tuple[float, float, float]:
        """Global intrinsic Euler angles yaw, pitch, roll."""
        return _getEulerAngles(self.r, "ZXY")

    def _trimeshEulerAngles(self):
        return _getEulerAngles(self.r, "xyz")

    def getRotation(self):
        return self.r

    @cached_property
    def inverse(self) -> Orientation:
        return Orientation(self.r.inv())

    @cached_property
    def _inverseRotation(self):
        return self.r.inv()

    # will be converted to a distributionMethod after the class definition
    def __mul__(self, other) -> Orientation:
        """Apply a rotation to this orientation, yielding a new orientation.

        As we represent orientations as intrinsic rotations, rotation A followed by rotation B is
        given by the quaternion product A*B, not B*A.

        See https://en.wikipedia.org/wiki/Davenport_chained_rotations#Conversion_to_extrinsic_rotations
        for more details.
        """
        if type(other) is not Orientation:
            return NotImplemented
        # Preserve existing orientation objects when possible to help pruning.
        if self == globalOrientation:
            return other
        if other == globalOrientation:
            return self
        return Orientation(self.r * other.r)

    @distributionMethod
    def __add__(self, other) -> Orientation:
        if isinstance(other, (float, int)):
            other = Orientation._fromHeading(other)
        elif type(other) is not Orientation:
            return NotImplemented
        return self * other

    @distributionMethod
    def __radd__(self, other) -> Orientation:
        if isinstance(other, (float, int)):
            other = Orientation._fromHeading(other)
        elif type(other) is not Orientation:
            return NotImplemented
        return other * self

    def __repr__(self):
        return f"Orientation.fromEuler{tuple(self.eulerAngles)!r}"

    def __hash__(self):
        return hash(tuple(self.q)) + hash(tuple(-self.q))

    @distributionFunction
    def localAnglesFor(self, orientation) -> typing.Tuple[float, float, float]:
        """Get local Euler angles for an orientation w.r.t. this orientation.

        That is, considering ``self`` as the parent orientation, find the Euler angles
        expressing the given orientation.
        """
        local = self.inverse * orientation
        return local.eulerAngles

    @distributionFunction
    def globalToLocalAngles(self, yaw, pitch, roll) -> typing.Tuple[float, float, float]:
        """Convert global Euler angles to local angles w.r.t. this orientation.

        Equivalent to `localAnglesFor` but takes Euler angles as input.
        """
        orientation = Orientation.fromEuler(yaw, pitch, roll)
        return self.localAnglesFor(orientation)

    def __eq__(self, other):
        if not isinstance(other, Orientation):
            return NotImplemented
        return numpy.array_equal(self.q, other.q) or numpy.array_equal(self.q, -other.q)

    def approxEq(self, other, tol=1e-10):
        if not isinstance(other, Orientation):
            return NotImplemented
        return abs(numpy.dot(self.q, other.q)) > 1 - tol

    @classmethod
    def encodeTo(cls, orientation, stream):
        stream.write(struct.pack("<dddd", *orientation.q))

    @classmethod
    def decodeFrom(cls, stream):
        # Quaternion constructor does not roundtrip so we manually
        # construct a rotation and pass that in.
        quaternion = struct.unpack("<dddd", stream.read(32))
        rotation = Rotation(quaternion, normalize=False)
        return cls(rotation)


_scipyVer = tuple(int(n) for n in importlib.metadata.version("scipy").split(".")[:2])
if _scipyVer >= (1, 17):

    def _getEulerAngles(rotation, axes, degrees=False):
        return rotation.as_euler(axes, degrees=degrees, suppress_warnings=True)

else:

    def _getEulerAngles(rotation, axes, degrees=False):
        return rotation.as_euler(axes, degrees=degrees)


globalOrientation = Orientation.fromEuler(0, 0, 0)

Orientation.__mul__ = distributionMethod(Orientation.__mul__, identity=globalOrientation)


def alwaysGlobalOrientation(orientation):
    """Whether this orientation is always aligned with the global coordinate system.

    Returns False if the orientation is a distribution or delayed argument, since
    then the value cannot be known at this time.
    """
    return isinstance(orientation, Orientation) and orientation == globalOrientation


class Vector(Samplable, collections.abc.Sequence):
    """A 3D vector, whose coordinates can be distributions."""

    def __init__(self, x, y, z=0):
        self.coordinates = (x, y, z)
        super().__init__(self.coordinates)

    @property
    def x(self) -> float:
        return self.coordinates[0]

    @property
    def y(self) -> float:
        return self.coordinates[1]

    @property
    def z(self) -> float:
        return self.coordinates[2]

    def toVector(self) -> Vector:
        return self

    @staticmethod
    def _canCoerceType(ty):
        return issubclass(ty, (tuple, list, numpy.ndarray)) or hasattr(ty, "toVector")

    @staticmethod
    def _coerce(thing) -> Vector:
        if isinstance(thing, (tuple, list, numpy.ndarray)):
            l = len(thing)
            if not 2 <= l <= 3:
                raise CoercionFailure(
                    "expected 2D/3D vector, got " f"{type(thing).__name__} of length {l}"
                )
            return Vector(*thing)
        else:
            return thing.toVector()

    def sampleGiven(self, value):
        return Vector(*(value[coord] for coord in self.coordinates))

    def evaluateInner(self, context):
        return Vector(*(valueInContext(coord, context) for coord in self.coordinates))

    @vectorOperator
    def applyRotation(self, rotation):
        if not isinstance(rotation, Orientation):
            return TypeError("rotation must be an Orientation")
        r = rotation.getRotation()
        return Vector(*r.apply(self.coordinates))

    @vectorOperator
    def sphericalCoordinates(self):
        """Returns this vector in spherical coordinates (rho, theta, phi)"""
        rho = math.hypot(self.x, self.y, self.z)
        theta = math.atan2(self.y, self.x) - math.pi / 2
        phi = math.atan2(self.z, math.hypot(self.x, self.y))
        return Vector(rho, theta, phi)

    @zeroPreservingVectorOperator
    def rotatedBy(self, angleOrOrientation) -> Vector:
        """Return a vector equal to this one rotated counterclockwise by angle/orientation."""
        if isinstance(angleOrOrientation, Orientation):
            return self.applyRotation(angleOrOrientation)
        x, y, z = self.x, self.y, self.z
        c, s = cos(angleOrOrientation), sin(angleOrOrientation)
        return Vector((c * x) - (s * y), (s * x) + (c * y), z)

    @vectorOperator
    def offsetRotated(self, angleOrOrientation, offset) -> Vector:
        ro = offset.rotatedBy(angleOrOrientation)
        return self + ro

    @vectorOperator
    def offsetLocally(self, orientation, offset) -> Vector:
        # Faster version of `offsetRotated` that only accepts Orientations.
        r = orientation.getRotation()
        ro = r.apply(offset)
        x, y, z = self
        ox, oy, oz = ro
        return Vector(x + ox, y + oy, z + oz)

    @vectorOperator
    def offsetRadially(self, radius, heading) -> Vector:
        return self.offsetRotated(heading, Vector(0, radius))

    @scalarOperator
    def distanceTo(self, other) -> float:
        if not isinstance(other, Vector):
            return other.distanceTo(self)
        dx, dy, dz = other.toVector() - self
        return math.hypot(dx, dy, dz)

    @scalarOperator
    def angleTo(self, other) -> float:
        return self.azimuthTo(other)

    @scalarOperator
    def azimuthTo(self, other) -> float:
        dx, dy, dz = other.toVector() - self
        return normalizeAngle(math.atan2(dy, dx) - (math.pi / 2))

    @scalarOperator
    def altitudeTo(self, other) -> float:
        dx, dy, dz = other.toVector() - self
        return normalizeAngle(math.atan2(dz, math.hypot(dx, dy)))

    @scalarOperator
    def angleWith(self, other) -> float:
        """Compute the signed angle between self and other.

        The angle is positive if other is counterclockwise of self (considering
        the smallest possible rotation to align them).
        """
        x, y = self.x, self.y
        ox, oy = other.x, other.y
        return normalizeAngle(math.atan2(oy, ox) - math.atan2(y, x))

    @scalarOperator
    def norm(self) -> float:
        return hypot(*self.coordinates)

    @scalarOperator
    def dot(self, other) -> float:
        x, y, z = self.x, self.y, self.z
        ox, oy, oz = other.x, other.y, other.z
        return (x * ox) + (y * oy) + (z * oz)

    @vectorOperator
    def cross(self, other) -> Vector:
        ax, ay, az = self.x, self.y, self.z
        bx, by, ba = other.x, other.y, other.z

        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx

        return Vector(cx, cy, cz)

    @vectorOperator
    def normalized(self) -> Vector:
        l = math.hypot(*self.coordinates)

        if l == 0:
            return Vector(0, 0, 0)

        return Vector(*(coord / l for coord in self.coordinates))

    @zeroIdentityVectorOperator
    def __add__(self, other) -> Vector:
        return Vector(self[0] + other[0], self[1] + other[1], self[2] + other[2])

    @zeroIdentityVectorOperator
    def __radd__(self, other) -> Vector:
        return Vector(self[0] + other[0], self[1] + other[1], self[2] + other[2])

    @zeroIdentityVectorOperator
    def __sub__(self, other) -> Vector:
        return Vector(self[0] - other[0], self[1] - other[1], self[2] - other[2])

    @vectorOperator
    def __rsub__(self, other) -> Vector:
        return Vector(other[0] - self[0], other[1] - self[1], other[2] - self[2])

    @vectorOperator
    def __mul__(self, other) -> Vector:
        return Vector(*(coord * other for coord in self.coordinates))

    def __rmul__(self, other) -> Vector:
        return self.__mul__(other)

    @vectorOperator
    def __truediv__(self, other) -> Vector:
        return Vector(*(coord / other for coord in self.coordinates))

    def __len__(self):
        return len(self.coordinates)

    def __getitem__(self, index):
        return self.coordinates[index]

    def __repr__(self):
        return f"Vector({self.x}, {self.y}, {self.z})"

    def __eq__(self, other):
        """Check Vector equality.

        A Vector is equal to another if their coordinates are equal,
        or if the other is a tuple/list that contains the coordinates of
        the Vector. For backwards compatibility a Vector is also equal
        to a tuple/list of length 2 that has a 0 z component if the Vector
        also has a 0 z component and the x and y components are equal.
        """
        if isinstance(other, Vector):
            return other.coordinates == self.coordinates
        elif isinstance(other, (tuple, list)):
            if len(other) == 2:
                return self.x == other[0] and self.y == other[1] and self.z == 0

            return tuple(other) == self.coordinates
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self.coordinates)

    @classmethod
    def encodeTo(cls, vec, stream):
        stream.write(struct.pack("<ddd", *vec.coordinates))

    @classmethod
    def decodeFrom(cls, stream):
        return cls(*struct.unpack("<ddd", stream.read(24)))


VectorDistribution._defaultValueType = Vector


class OrientedVector(Vector):
    def __init__(self, x, y, z, heading):
        super().__init__(x, y, z)
        self.heading = heading

    @staticmethod
    @distributionFunction
    def make(position, heading) -> OrientedVector:
        return OrientedVector(*position, heading)

    def toHeading(self):
        return self.heading

    def evaluateInner(self, context):
        hdg = valueInContext(self.heading, context)
        return OrientedVector(
            *(valueInContext(coord, context) for coord in self.coordinates), hdg
        )

    def __eq__(self, other):
        if type(other) is not OrientedVector:
            return NotImplemented
        return other.coordinates == self.coordinates and other.heading == self.heading

    def __hash__(self):
        return hash((self.coordinates, self.heading))


class VectorField:
    """A vector field, providing an orientation at every point.

    Arguments:
        name (str): name for debugging.
        value: function computing the heading at the given `Vector`.
        minSteps (int): Minimum number of steps for `followFrom`; default 4.
        defaultStepSize (float): Default step size for `followFrom`; default 5.
            This is an upper bound: more steps will be taken as needed to ensure that no
            single step is longer than this value, but if the distance to travel is small
            then the steps may be smaller.
    """

    def __init__(self, name, value, minSteps=4, defaultStepSize=5):
        self.name = name
        self.value = value
        self.valueType = Orientation
        self.minSteps = minSteps
        self.defaultStepSize = defaultStepSize

    @distributionMethod
    def __getitem__(self, pos) -> Orientation:
        val = self.value(pos)
        if isinstance(val, numbers.Real):  # fast path
            return Orientation._fromHeading(val)
        if isLazy(val):
            raise ValueError(f"value function of {self.name} returned lazy value")
        return toOrientation(
            val, f"value function of {self.name} returned non-orientation"
        )

    @vectorDistributionMethod
    def followFrom(self, pos, dist, steps=None, stepSize=None):
        """Follow the field from a point for a given distance.

        Uses the forward Euler approximation, covering the given distance with
        equal-size steps. The number of steps can be given manually, or computed
        automatically from a desired step size.

        Arguments:
            pos (`Vector`): point to start from.
            dist (float): distance to travel.
            steps (int): number of steps to take, or :obj:`None` to compute the number of
                steps based on the distance (default :obj:`None`).
            stepSize (float): length used to compute how many steps to take, or
                :obj:`None` to use the field's default step size.
        """
        if steps is None:
            steps = self.minSteps
            stepSize = self.defaultStepSize if stepSize is None else stepSize
            if stepSize is not None:
                steps = max(steps, math.ceil(dist / stepSize))

        stepSize = dist / steps
        step = numpy.array([0, stepSize, 0])
        for i in range(steps):
            rot = self[pos].getRotation()
            pos += rot.apply(step)

        return Vector(*pos)

    @staticmethod
    def forUnionOf(regions, tolerance=0):
        """Creates a `PiecewiseVectorField` from the union of the given regions.

        If none of the regions have an orientation, returns :obj:`None` instead.
        """
        if any(reg.orientation for reg in regions):
            return PiecewiseVectorField("Union", regions, tolerance=tolerance)
        else:
            return None

    def __str__(self):
        return f"<{type(self).__name__} {self.name}>"


class PolygonalVectorField(VectorField):
    """A piecewise-constant vector field defined over polygonal cells.

    Arguments:
        name (str): name for debugging.
        cells: a sequence of cells, with each cell being a pair consisting of a Shapely
            geometry and a heading. If the heading is :obj:`None`, we call the given
            **headingFunction** for points in the cell instead.
        headingFunction: function computing the heading for points in cells without
            specified headings, if any (default :obj:`None`).
        defaultHeading: heading for points not contained in any cell (default
            :obj:`None`, meaning reject such points).
    """

    def __init__(self, name, cells, headingFunction=None, defaultHeading=None):
        self.cells = tuple(cells)
        if headingFunction is None and defaultHeading is not None:
            headingFunction = lambda pos: defaultHeading
        self.headingFunction = headingFunction
        for cell, heading in self.cells:
            if heading is None and headingFunction is None and defaultHeading is None:
                raise RuntimeError(f"missing heading for cell of PolygonalVectorField")
        self.defaultHeading = defaultHeading
        self.rtree = shapely.STRtree([cell[0] for cell in self.cells])
        super().__init__(name, self.valueAt)

    def valueAt(self, pos):
        point = makeShapelyPoint(pos)
        candidates = self.rtree.query(point, predicate="intersects")
        if len(candidates) > 0:
            first = candidates.min()
            cell, heading = self.cells[first]
            return self.headingFunction(pos) if heading is None else heading
        if self.defaultHeading is not None:
            return self.defaultHeading
        raise RejectionException(f"evaluated PolygonalVectorField at undefined point")


class PiecewiseVectorField(VectorField):
    """A vector field defined by patching together several regions.

    The heading at a point is determined by checking each region in turn to see if it has
    an orientation and contains the point, returning the corresponding heading if so. If
    we get through all the regions, and **tolerance** is nonzero, we try again, this time
    allowing the point to be up to **tolerance** away from each region. If we still fail
    to find a region "containing" the point, then we return the **defaultHeading**, if
    any, and otherwise reject the scene.

    Arguments:
        name (str): name for debugging.
        regions (sequence of `Region` objects): the regions making up the field.
        tolerance (float): maximum distance at which to consider a point as being
            in one of the regions, if it is not otherwise contained (default 0).
        defaultHeading (float): the heading for points not in any region with an
            orientation (default :obj:`None`, meaning reject such points).
    """

    def __init__(self, name, regions, tolerance=0, defaultHeading=None):
        self.regions = tuple(region for region in regions if region.orientation)
        self.tolerance = tolerance
        self.defaultHeading = defaultHeading
        super().__init__(name, self.valueAt)

    def valueAt(self, point):
        for region in self.regions:
            if region.containsPoint(point):
                return region.orientation[point]
        if self.tolerance > 0:
            for region in self.regions:
                if region.distanceTo(point) <= self.tolerance:
                    return region.orientation[point]
        if self.defaultHeading is not None:
            return self.defaultHeading
        raise RejectionException(f"evaluated PiecewiseVectorField at undefined point")


class PolyhedronVectorField(VectorField):
    pass
