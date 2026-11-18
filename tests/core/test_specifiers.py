import itertools

import pytest

from scenic.core.lazy_eval import DelayedArgument
import scenic.core.object_types
from scenic.core.specifiers import ModifyingSpecifier, PropertyDefault, Specifier


def test_modifying_dependencies():
    # Specifier 1 sets foo to 7
    # Specifier 2 modifies foo by doubling the value
    # Specifier 3 sets bar to 10 times foo
    specifier_1 = Specifier("Spec1", {"foo": 1}, {"foo": 7})

    def spec_2_helper(context):
        assert hasattr(context, "foo")
        return {"foo": 2 * context.foo}

    specifier_2 = ModifyingSpecifier(
        "Spec2",
        {"foo": 1},
        DelayedArgument(set(), spec_2_helper),
        modifiable_props={"foo"},
    )

    def spec_3_helper(context):
        return {"bar": 10 * context.foo}

    specifier_3 = Specifier("Spec3", {"bar": 1}, DelayedArgument({"foo"}, spec_3_helper))

    # Try every possible specifier order
    specifier_lists = itertools.permutations([specifier_1, specifier_2, specifier_3])
    for specs in specifier_lists:
        obj = scenic.core.object_types.Object._withSpecifiers(specs)
        assert obj.foo == 14
        assert obj.bar == 140


def test_dynamic_value_requires_dynamic():
    with pytest.raises(RuntimeError) as e:
        PropertyDefault((), {}, lambda self: 0, dynamicValue=lambda self: 1)
    assert "only dynamic properties can have a dynamicValue" in str(e.value)
