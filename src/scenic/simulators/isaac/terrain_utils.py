from dataclasses import dataclass, field

import numpy as np
import trimesh


@dataclass(frozen=True)
class ScenicTerrainData:
    terrain_mesh: trimesh.Trimesh
    terrain_origins: np.ndarray
    flat_patches: dict = field(default_factory=dict)


def heightfieldToTrimesh(heightfield, horizontal_scale, vertical_scale):
    rows, cols = heightfield.shape
    xs = np.arange(rows, dtype=np.float32) * horizontal_scale
    ys = np.arange(cols, dtype=np.float32) * horizontal_scale
    grid_x, grid_y = np.meshgrid(xs, ys, indexing="ij")
    vertices = np.column_stack(
        (
            grid_x.ravel(),
            grid_y.ravel(),
            heightfield.astype(np.float32).ravel() * vertical_scale,
        )
    )

    # Two triangles per grid cell: (a, b, c) and (c, b, d) with
    # a = (i, j), b = (i + 1, j), c = (i, j + 1), d = (i + 1, j + 1).
    index = np.arange(rows * cols).reshape(rows, cols)
    a = index[:-1, :-1].ravel()
    b = index[1:, :-1].ravel()
    c = index[:-1, 1:].ravel()
    d = index[1:, 1:].ravel()
    faces = np.stack(
        [np.column_stack((a, b, c)), np.column_stack((c, b, d))], axis=1
    ).reshape(-1, 3)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def buildScenicTerrainData(terrains, *, border_width=20.0):
    terrains = list(terrains)
    if not terrains:
        raise ValueError("Isaac Lab mode requires at least one Scenic Terrain object")

    horizontal_scale = float(terrains[0].horizontalScale)
    vertical_scale = float(terrains[0].verticalScale)
    border_cells = int(round(border_width / horizontal_scale))

    terrain_bounds = []
    x_centers = []
    y_centers = []
    min_x = min_y = 0
    max_x = max_y = 0

    for terrain in terrains:
        if terrain.subterrain is None:
            terrain.create()

        start_x = int(round(float(terrain.position[0]) / horizontal_scale))
        start_y = int(round(float(terrain.position[1]) / horizontal_scale))
        width_cells = int(round(float(terrain.width) / horizontal_scale))
        length_cells = int(round(float(terrain.length) / horizontal_scale))
        end_x = start_x + width_cells
        end_y = start_y + length_cells

        min_x = min(min_x, start_x)
        max_x = max(max_x, end_x)
        min_y = min(min_y, start_y)
        max_y = max(max_y, end_y)
        x_centers.append((start_x + end_x) // 2)
        y_centers.append((start_y + end_y) // 2)
        terrain_bounds.append((terrain, start_x, end_x, start_y, end_y))

    x_origin_cells = sorted(set(x_centers))
    y_origin_cells = sorted(set(y_centers))
    terrain_origins = np.zeros(
        (len(x_origin_cells), len(y_origin_cells), 3), dtype=np.float32
    )

    heightfield = np.zeros(
        (
            max_x - min_x + 2 * border_cells,
            max_y - min_y + 2 * border_cells,
        ),
        dtype=np.float32,
    )

    for terrain, start_x, end_x, start_y, end_y in terrain_bounds:
        target_x0 = start_x - min_x + border_cells
        target_x1 = end_x - min_x + border_cells
        target_y0 = start_y - min_y + border_cells
        target_y1 = end_y - min_y + border_cells
        heightfield[target_x0:target_x1, target_y0:target_y1] = (
            terrain.subterrain.height_field_raw
        )

    x_center_offset = -0.5 * (min_x + max_x) * horizontal_scale
    y_center_offset = -0.5 * (min_y + max_y) * horizontal_scale

    x_index = {value: index for index, value in enumerate(x_origin_cells)}
    y_index = {value: index for index, value in enumerate(y_origin_cells)}
    for x_pos in x_origin_cells:
        for y_pos in y_origin_cells:
            height_x = x_pos - min_x + border_cells
            height_y = y_pos - min_y + border_cells
            terrain_origins[x_index[x_pos], y_index[y_pos], 0] = (
                x_pos * horizontal_scale + x_center_offset
            )
            terrain_origins[x_index[x_pos], y_index[y_pos], 1] = (
                y_pos * horizontal_scale + y_center_offset
            )
            terrain_origins[x_index[x_pos], y_index[y_pos], 2] = (
                heightfield[height_x, height_y] * vertical_scale
            )

    mesh = heightfieldToTrimesh(heightfield, horizontal_scale, vertical_scale)
    mesh.apply_translation(
        (
            min_x * horizontal_scale + x_center_offset - border_width,
            min_y * horizontal_scale + y_center_offset - border_width,
            0,
        )
    )

    return ScenicTerrainData(terrain_mesh=mesh, terrain_origins=terrain_origins)


def terrainObjectsFromScene(scene):
    return [obj for obj in scene.objects if obj.blueprint == "Terrain"]
