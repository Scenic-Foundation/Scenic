import math
import typing
import warnings

import numpy.linalg
import pytest
import scipy.stats

from scenic.core.distributions import (
    DiscreteRange,
    Normal,
    OperatorDistribution,
    Options,
    Range,
    TruncatedNormal,
    distributionFunction,
    distributionMethod,
    supportInterval,
    unionOfSupports,
)
from scenic.core.lazy_eval import DelayedArgument, LazilyEvaluable
from scenic.core.type_support import underlyingType

# Properties of distributions


def test_primitive():
    assert Range(0, 1).isPrimitive
    assert Normal(0, 1).isPrimitive
    assert TruncatedNormal(0, 1, 0, 1).isPrimitive
    assert DiscreteRange(0, 10).isPrimitive
    assert Options([1, 4, 9]).isPrimitive
    assert Options({1: 1, 2: 4, 3: 9}).isPrimitive
    x = Range(0, 1) * Range(0, 1)
    assert not x.isPrimitive


def test_support_basic():
    assert supportInterval(Range(-3, 5)) == (-3, 5)
    assert supportInterval(Normal(5, 5)) == (None, None)
    assert supportInterval(TruncatedNormal(5, 5, -3, -1)) == (-3, -1)
    assert supportInterval(DiscreteRange(-2, 4)) == (-2, 4)
    assert supportInterval("blah") == (None, None)


def test_support_options():
    a = Range(3, 5)
    b = Range(-1, 2)
    assert supportInterval(Options([a, b])) == (-1, 5)
    c = Normal(0, 1)
    assert supportInterval(Options([a, b, c])) == (None, None)


def test_support_options_attribute():
    class Blob:
        def __init__(self, x):
            self.x = x

    a = Blob(Range(1, 2))
    b = Blob(Range(3, 5))
    c = Options([a, b])
    assert supportInterval(c.x) == (1, 5)


def test_support_operators():
    a = Range(1, 2)
    assert supportInterval(a + 1) == pytest.approx((2, 3))
    assert supportInterval(2 + a) == pytest.approx((3, 4))
    assert supportInterval(a + a) == pytest.approx((2, 4))
    assert supportInterval(a - 1) == pytest.approx((0, 1))
    assert supportInterval(2 - a) == pytest.approx((0, 1))
    assert supportInterval(a - a.clone()) == pytest.approx((-1, 1))
    assert supportInterval(a * 2) == pytest.approx((2, 4))
    assert supportInterval(-3 * a) == pytest.approx((-6, -3))
    assert supportInterval(a * a) == pytest.approx((1, 4))
    assert supportInterval(a * a) == pytest.approx((1, 4))
    assert supportInterval(-a * a) == pytest.approx((-4, -1))
    assert supportInterval(a / 2) == pytest.approx((0.5, 1))
    assert supportInterval(4 / a) == pytest.approx((2, 4))
    assert supportInterval(a / a.clone()) == pytest.approx((0.5, 2))
    assert supportInterval(abs(a)) == pytest.approx((1, 2))
    assert supportInterval(abs(Range(-1, 2))) == pytest.approx((0, 2))
    assert supportInterval(abs(Range(-5, 2))) == pytest.approx((0, 5))
    assert supportInterval(abs(Range(-5, -2))) == pytest.approx((2, 5))


# Bucketing


@pytest.fixture
def similarDistributions(pytestconfig):
    samples = 3000 if pytestconfig.getoption("--fast") else 100000

    def checker(d1, d2, p=1e-5):
        s1 = [d1.sample() for i in range(samples)]
        s2 = [d2.sample() for i in range(samples)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                assert scipy.stats.epps_singleton_2samp(s1, s2).pvalue > p, p
            except numpy.linalg.LinAlgError:
                assert scipy.stats.ks_2samp(s1, s2).pvalue > p, p

    return checker


def test_bucketed_range(similarDistributions):
    r = Range(-3, 7)
    similarDistributions(r, r.bucket())
    similarDistributions(r, r.bucket(buckets=100))
    with pytest.raises(ValueError):
        r.bucket(buckets=0)
    with pytest.raises(RuntimeError):
        Range(r, 10).bucket()


def test_bucketed_normal(similarDistributions):
    n = Normal(22, 5)
    similarDistributions(n, n.bucket())
    similarDistributions(n, n.bucket(buckets=1))
    similarDistributions(n, n.bucket(buckets=2))
    similarDistributions(n, n.bucket(buckets=15))
    similarDistributions(n, n.bucket(buckets=[0, 20, 23, 50]))
    with pytest.raises(ValueError):
        n.bucket(buckets=0)
    with pytest.raises(ValueError):
        n.bucket(buckets=[0, 10, 5])
    with pytest.raises(RuntimeError):
        Normal(10, n).bucket()


def test_bucketed_truncated_normal(similarDistributions):
    n = TruncatedNormal(-10, 3, -1, 5)
    similarDistributions(n, n.bucket())
    similarDistributions(n, n.bucket(buckets=15))
    similarDistributions(n, n.bucket(buckets=[-1, -0.5, 4, 5]))
    with pytest.raises(ValueError):
        n.bucket(buckets=0)
    with pytest.raises(ValueError):
        n.bucket(buckets=[-1])
    with pytest.raises(ValueError):
        n.bucket(buckets=[-1, 10, 5])
    with pytest.raises(ValueError):
        n.bucket(buckets=[-1, 5, 10])
    with pytest.raises(RuntimeError):
        TruncatedNormal(10, n, 0, 10).bucket()


def test_bucketed_discrete_range(similarDistributions):
    r = DiscreteRange(-3, 7)
    similarDistributions(r, r.bucket())


def test_bucketed_options(similarDistributions):
    o = Options({0: 1, 1: 3})
    similarDistributions(o, o.bucket())


# Decorators for supporting random arguments


def test_function_decorator():
    @distributionFunction
    def myfunc(x, y):
        if x > 0:
            return (x, y)
        else:
            return (x, -y)

    res = myfunc(Range(-1, 1), 42)
    assert supportInterval(res) == (None, None)
    for i in range(30):
        z, w = res.sample()
        assert w == 42 if z > 0 else w == -42


def test_function_decorator_builtin():
    myprint = distributionFunction(print)
    res = myprint(Options([7, 9]))
    res()
    myhypot = distributionFunction(math.hypot)
    res = myhypot(4, Options([-3, 3]))
    for i in range(30):
        assert res.sample() == pytest.approx(5)


def test_function_decorator_annotations():
    @distributionFunction
    def myfunc(x: float) -> float:
        return 2 * x

    assert typing.get_type_hints(myfunc) == {"x": float, "return": float}


def test_function_decorator_type_explicit():
    @distributionFunction(valueType=str)
    def myfunc(x):
        return str(x)

    a = Range(0, 1)
    b = myfunc(a)
    assert underlyingType(b) is str


def test_function_decorator_type_annotation():
    @distributionFunction
    def myfunc(x) -> str:
        return str(x)

    a = Range(0, 1)
    b = myfunc(a)
    assert underlyingType(b) is str


def test_function_decorator_support():
    def support(x, y=(1, 1)):
        lx, hx = x
        ly, hy = y
        if lx >= hy:
            return x
        elif hx < ly:
            return (-hx, -lx)
        else:
            return unionOfSupports((x, (max(-hx, -hy), -lx)))

    @distributionFunction(support=support)
    def myfunc(x, y=1):
        return x if x >= y else -x

    assert supportInterval(myfunc(Range(2, 3))) == (2, 3)
    assert supportInterval(myfunc(Range(0, 2))) == (-1, 2)
    assert supportInterval(myfunc(Range(0, 1), y=2)) == (-1, 0)
    assert supportInterval(myfunc(Range(0, 1), Range(0, 1))) == (-1, 1)


def test_method_decorator():
    class Foo:
        def __init__(self, x):
            self.x = x

        @distributionMethod
        def method(self, y: float, z: float) -> float:
            if y > 0:
                return self.x + z
            else:
                return self.x - z

    assert typing.get_type_hints(Foo.method) == {"y": float, "z": float, "return": float}
    res = Foo(4).method(Range(-1, 1), 2)
    vals = [res.sample() for i in range(60)]
    assert all(val == 6 or val == 2 for val in vals)
    assert any(val == 6 for val in vals)
    assert any(val == 2 for val in vals)


def test_method_decorator_builtin():
    class MyStr(str):
        index = distributionMethod(str.index)

    s = MyStr("blobbo")
    i = s.index(Options(["b", "o"]))
    vals = [i.sample() for _ in range(60)]
    assert all(val == 0 or val == 2 for val in vals)
    assert any(val == 0 for val in vals)
    assert any(val == 2 for val in vals)


# Attributes


def test_attribute_distribution():
    class Foo:
        def __init__(self, x):
            self.x = x

        @property
        def thing(self) -> str:
            return str(self.x)

    a = Options([Foo(1), Foo(2)]).thing
    vals = [a.sample() for _ in range(60)]
    assert all(val == "1" or val == "2" for val in vals)
    assert any(val == "1" for val in vals)
    assert any(val == "2" for val in vals)


def test_operator_distribution_lazy_keyword_argument():
    def scaled(value, factor=1):
        return value * factor

    call = OperatorDistribution(
        "__call__",
        scaled,
        (10,),
        {"factor": DelayedArgument((), lambda context: 3)},
    )
    context = LazilyEvaluable.makeContext()
    evaluated = call.evaluateInner(context)
    assert evaluated.kwoperands["factor"] == 3
