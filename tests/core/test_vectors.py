import pytest

from scenic.core.distributions import Options, underlyingFunction
from scenic.core.lazy_eval import (
    DelayedArgument,
    LazilyEvaluable,
    needsLazyEvaluation,
    valueInContext,
)
from scenic.core.vectors import *


def test_vector_equality():
    v = Vector(1, 4)
    assert v == Vector(1, 4)
    assert v == Vector(1, 4, 0)
    assert v != Vector(1, 5)
    assert v != Vector(1, 4, 9)
    assert v == (1, 4, 0)
    assert v != (1,)
    assert v != (1, 4, 9)
    assert v == [1, 4, 0]
    assert v != [1]
    assert v != [1, 4, 9]
    assert v == (1, 4)


def test_vector_cross():
    assert Vector(1, 0, 0).cross(Vector(0, 1, 0)) == Vector(0, 0, 1)


def test_orientation_equality():
    o1 = Orientation.fromEuler(math.pi, math.pi, math.pi)
    o2 = Orientation.fromEuler(-math.pi, -math.pi, -math.pi)
    o3 = Orientation.fromEuler(math.pi, math.pi, 0)

    assert o1 == o1 and o1.approxEq(o1)
    assert o1.approxEq(o2)
    assert o1 != o3 and not o1.approxEq(o3)


def test_orientation_localAnglesFor():
    parent = Orientation.fromEuler(math.pi / 4, math.pi / 4, 0)
    target = Orientation.fromEuler(-3 * math.pi / 4, math.pi / 4, math.pi / 4)
    angles = parent.localAnglesFor(target)
    assert angles == pytest.approx((-3 * math.pi / 4, math.pi / 2, 0))

    for i in range(100):
        parent = Orientation.fromEuler(
            *[random.uniform(-math.pi, math.pi) for _ in range(3)]
        )
        target = Orientation.fromEuler(
            *[random.uniform(-math.pi, math.pi) for _ in range(3)]
        )
        local = Orientation.fromEuler(*parent.localAnglesFor(target))
        assert target.approxEq(parent * local)


def test_distribution_method_encapsulation():
    vf = VectorField("Foo", lambda pos: 0)
    pt = vf.followFrom(Vector(0, 0), Options([1, 2]), steps=1)
    assert isinstance(pt, VectorMethodDistribution)
    assert pt.method is underlyingFunction(vf.followFrom)


def test_distribution_method_encapsulation_lazy():
    vf = VectorField("Foo", lambda pos: 0)
    da = DelayedArgument(set(), lambda context: Options([1, 2]))
    pt = vf.followFrom(Vector(0, 0), da, steps=1)
    assert isinstance(pt, DelayedArgument)
    context = LazilyEvaluable.makeContext()
    evpt = valueInContext(pt, context)
    assert not needsLazyEvaluation(evpt)
    assert isinstance(evpt, VectorMethodDistribution)
    assert evpt.method is underlyingFunction(vf.followFrom)
