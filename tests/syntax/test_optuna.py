from tests.utils import compileScenic, sampleEgo


def test_optuna_distributions():
    scenario = compileScenic(
        """
        param externalSampler = OptunaSampler
        ego = new Object with floatProp OptunaRange(-30, 10),
                         with intProp OptunaDiscreteRange(-10, 30),
                         with catProp OptunaOptions(["FOO", "BAR", "FIZZ", "BUZZ"])
        """
    )

    egos = [sampleEgo(scenario) for _ in range(30)]
    floatProps = [ego.floatProp for ego in egos]
    intProps = [ego.intProp for ego in egos]
    catProps = [ego.catProp for ego in egos]

    assert len(set(floatProps)) == 30
    assert all(-30 <= f <= 10 for f in floatProps)

    assert len(set(intProps)) > 1
    assert all(int(i) == i for i in intProps)
    assert all(-10 <= f <= 30 for f in intProps)

    assert len(set(catProps)) > 1
    assert all(c in ["FOO", "BAR", "FIZZ", "BUZZ"] for c in catProps)
