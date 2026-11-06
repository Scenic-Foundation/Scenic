from isaaclab.terrains.terrain_generator import TerrainGenerator

from scenic.simulators.isaac.terrain_utils import ScenicTerrainData


class ScenicTerrainGenerator(TerrainGenerator):
    def __init__(self, cfg, device="cpu", *, terrain_data: ScenicTerrainData):
        self.cfg = cfg
        self.device = device
        self.terrain_mesh = terrain_data.terrain_mesh.copy()
        self.terrain_meshes = [self.terrain_mesh]
        self.terrain_origins = terrain_data.terrain_origins.copy()
        self.flat_patches = dict(terrain_data.flat_patches)


def scenicTerrainGeneratorClass(terrain_data):
    class _ScenicTerrainGenerator(ScenicTerrainGenerator):
        def __init__(self, cfg, device="cpu"):
            super().__init__(cfg, device=device, terrain_data=terrain_data)

    return _ScenicTerrainGenerator
