import scenic
from scenic.simulators.isaac.lab_env import (
    ScenicIsaacLabEnvWrapper,
    configureEnvCfgForScenicTerrain,
)
from scenic.simulators.isaac.terrain_utils import (
    buildScenicTerrainData,
    terrainObjectsFromScene,
)


def loadScenicScenario(path, model):
    return scenic.scenarioFromFile(path, model=model, params={"isaacLab": True})


def configureInitialScenicTerrain(env_cfg, scenario, terrain_border_width):
    scene, _ = scenario.generate()
    terrain_data = buildScenicTerrainData(
        terrainObjectsFromScene(scene), border_width=terrain_border_width
    )
    configureEnvCfgForScenicTerrain(env_cfg, terrain_data)
    return scene, terrain_data


def wrapWithScenic(env, scenario, terrain_border_width):
    return ScenicIsaacLabEnvWrapper(
        env, scenario, terrain_border_width=terrain_border_width
    )
