import gymnasium as gym

from scenic.simulators.isaac.terrain_utils import (
    buildScenicTerrainData,
    terrainObjectsFromScene,
)


def _unwrapEnv(env):
    return getattr(env, "unwrapped", env)


def _removeImportedTerrain(terrain, name):
    cfg = getattr(terrain, "cfg", None)
    prim_path = f"{cfg.prim_path}/{name}" if getattr(cfg, "prim_path", None) else None

    if prim_path is not None:
        try:
            from isaacsim.core.utils.prims import delete_prim

            delete_prim(prim_path)
        except Exception:
            pass

    terrain_prim_paths = getattr(terrain, "terrain_prim_paths", None)
    if terrain_prim_paths is not None and prim_path is not None:
        while prim_path in terrain_prim_paths:
            terrain_prim_paths.remove(prim_path)

    for attr in ("meshes", "warp_meshes"):
        mapping = getattr(terrain, attr, None)
        if isinstance(mapping, dict):
            mapping.pop(name, None)


def installScenicTerrain(env, terrain_data):
    unwrapped = _unwrapEnv(env)
    scene = getattr(unwrapped, "scene", None)
    terrain = getattr(scene, "terrain", None) if scene is not None else None
    if terrain is None and scene is not None:
        terrain = getattr(scene, "_terrain", None)
    if terrain is None:
        raise RuntimeError("Isaac Lab environment does not expose a scene terrain")

    cfg = getattr(terrain, "cfg", None)
    _removeImportedTerrain(terrain, "terrain")

    terrain.import_mesh("terrain", terrain_data.terrain_mesh)
    terrain.configure_env_origins(terrain_data.terrain_origins)
    if hasattr(terrain, "_terrain_flat_patches"):
        terrain._terrain_flat_patches = dict(terrain_data.flat_patches)

    if getattr(cfg, "debug_vis", False):
        terrain.set_debug_vis(True)


def configureEnvCfgForScenicTerrain(env_cfg, terrain_data):
    """Point an env cfg's terrain importer at Scenic's terrain mesh.

    The cfg's ``scene.terrain`` is switched to a generated terrain whose
    generator yields the mesh and origins in ``terrain_data``, so that the
    Scenic terrain is in place as the environment is created.
    """
    from isaaclab.terrains import TerrainGeneratorCfg

    from scenic.simulators.isaac.terrain_generator import scenicTerrainGeneratorClass

    terrain_cfg = env_cfg.scene.terrain
    generator_cfg = terrain_cfg.terrain_generator

    num_rows, num_cols = terrain_data.terrain_origins.shape[:2]

    if generator_cfg is None:
        generator_cfg = TerrainGeneratorCfg(
            size=(1.0, 1.0),
            num_rows=int(num_rows),
            num_cols=int(num_cols),
            sub_terrains={},  # important: avoids missing config field validation
        )
        terrain_cfg.terrain_generator = generator_cfg

    terrain_cfg.terrain_type = "generator"
    generator_cfg.class_type = scenicTerrainGeneratorClass(terrain_data)
    generator_cfg.num_rows = int(num_rows)
    generator_cfg.num_cols = int(num_cols)
    generator_cfg.sub_terrains = {}

    if hasattr(env_cfg, "curriculum") and hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None
    if hasattr(terrain_cfg, "max_init_terrain_level"):
        terrain_cfg.max_init_terrain_level = None


class ScenicIsaacLabEnvWrapper(gym.Wrapper):
    def __init__(self, env, scenario, *, terrain_border_width=20.0, max_iterations=2000):
        super().__init__(env)
        self.scenario = scenario
        self.terrain_border_width = terrain_border_width
        self.max_iterations = max_iterations
        self.current_scene = None
        self.current_terrain_data = None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.env, name)

    def _sampleTerrain(self):
        scene, _ = self.scenario.generate(maxIterations=self.max_iterations)
        terrain_data = buildScenicTerrainData(
            terrainObjectsFromScene(scene), border_width=self.terrain_border_width
        )
        self.current_scene = scene
        self.current_terrain_data = terrain_data
        return terrain_data

    def reset(self, *, seed=None, options=None):
        terrain_data = self._sampleTerrain()
        installScenicTerrain(self.env, terrain_data)
        return self.env.reset(seed=seed, options=options)

    def step(self, action):
        return self.env.step(action)
