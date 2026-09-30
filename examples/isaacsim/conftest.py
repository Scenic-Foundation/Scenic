import pytest


@pytest.fixture
def options():
    # Most of these examples load an environment USD, which requires Isaac Sim
    # to convert it into a mesh; skip the whole folder without it.
    pytest.importorskip("isaacsim")
    return {}
