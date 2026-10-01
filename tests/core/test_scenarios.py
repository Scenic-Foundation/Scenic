import random

import pytest

from scenic.core.distributions import Range
from scenic.core.scenarios import Scene
from scenic.core.utils import setSeed
from tests.utils import compileScenic


def test_nonexistent_scenario_local_1():
    scenario = compileScenic("ego = new Object")
    with pytest.raises(AttributeError):
        scenario.dynamicScenario.blah


def test_nonexistent_scenario_local_2():
    scenario = compileScenic(
        """
        scenario Main():
            ego = new Object
    """
    )
    with pytest.raises(AttributeError):
        scenario.dynamicScenario.blah


def test_condition_scenario_objects():
    scenario = compileScenic(
        """
        new Object facing Range(0, 1)
        ego = new Object at 10@10, facing Range(0, 1)
    """
    )
    sceneA, _ = scenario.generate(maxIterations=1)
    scenario.conditionOn(scene=sceneA, objects=(1,))
    sceneB, _ = scenario.generate(maxIterations=1)
    assert sceneA.objects[0].heading != sceneB.objects[0].heading
    assert sceneA.objects[1].heading == sceneB.objects[1].heading


def test_condition_scenario_params_1():
    scenario = compileScenic(
        """
        ego = new Object
        param x = Range(0, 1)
    """
    )
    scenario.conditionOn(params={"x": 0.6})
    scene, _ = scenario.generate(maxIterations=1)
    assert scene.params["x"] == 0.6


def test_condition_scenario_params_2():
    scenario = compileScenic(
        """
        ego = new Object
        param x = Range(0, 1)
    """
    )
    scenario.conditionOn(params={"x": Range(0.5, 0.51)})
    xs = [scenario.generate(maxIterations=1)[0].params["x"] for i in range(30)]
    assert all(0.5 <= x <= 0.51 for x in xs)
    assert any(0.505 <= x for x in xs)
    assert any(x < 0.505 for x in xs)


def test_generateBatch():
    scenario = compileScenic(
        """
        ego = new Object facing Range(0, 1)
        require ego.heading > 0.5
    """
    )
    scenes, _ = scenario.generateBatch(2, numWorkers=2)

    assert len(scenes) == 2
    assert all(isinstance(scene, Scene) for scene in scenes)
    assert all(0 <= scene.objects[0].heading <= 1 for scene in scenes)
    assert scenes[0].objects[0].heading != scenes[1].objects[0].heading


def test_generateBatch_serialized():
    scenario = compileScenic(
        """
        ego = new Object facing Range(0, 1)
        require ego.heading > 0.5
    """
    )
    scenesBytes, _ = scenario.generateBatch(2, numWorkers=2, serialized=True)
    assert len(scenesBytes) == 2
    assert all(isinstance(b, bytes) for b in scenesBytes)

    scenes = [scenario.sceneFromBytes(b, verify=True) for b in scenesBytes]
    assert all(isinstance(scene, Scene) for scene in scenes)
    assert all(0 <= scene.objects[0].heading <= 1 for scene in scenes)
    assert scenes[0].objects[0].heading != scenes[1].objects[0].heading


def test_generateStream_deterministic():
    seed = random.getrandbits(32)

    scenario = compileScenic(
        """
        ego = new Object facing Range(0, 1)
        require ego.heading > 0.5
    """
    )
    setSeed(seed)
    streamA = tuple(scenario.generateStream(8, numWorkers=2, serialized=True))
    setSeed(seed)
    streamB = tuple(scenario.generateStream(8, numWorkers=2, serialized=True))
    assert len(streamA) == len(streamB) == 8
    bytesSetA = {result[0] for result in streamA}
    bytesSetB = {result[0] for result in streamB}
    assert bytesSetA == bytesSetB

    setSeed(seed)
    streamA = tuple(
        scenario.generateStream(8, numWorkers=2, serialized=True, deterministic=True)
    )
    setSeed(seed)
    streamB = tuple(
        scenario.generateStream(8, numWorkers=2, serialized=True, deterministic=True)
    )
    assert streamA == streamB
