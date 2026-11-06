"""Conversion of USD stages/assets into meshes Scenic can reason about."""

import json
import os
import tempfile

import numpy as np
import trimesh

import scenic.simulators.isaac.utils as scenic_utils


def removeGroundPlane(file_path, output_path):
    """Write a flattened copy of the USD at ``file_path`` with any ground plane disabled.

    The stage is flattened so that references and payloads of the asset are
    still resolved once the copy lives in a different directory.
    """
    from pxr import Usd

    stage = Usd.Stage.Open(file_path)
    if stage is None:
        raise RuntimeError(f"could not open USD file: {file_path}")
    for prim in stage.Traverse():
        if "groundplane" in str(prim.GetPath()).lower():
            prim.SetActive(False)
    stage.Flatten().Export(output_path)


def flattenUsd(file_path, output_path):
    from pxr import Usd

    stage = Usd.Stage.Open(file_path)
    if stage is None:
        raise RuntimeError(f"could not open USD file for flattening: {file_path}")
    flattened_layer = stage.Flatten()
    flattened_layer.Export(output_path)


def decomposeMatrix(mat):
    from pxr import Gf

    reversed_ident_mtx = reversed(Gf.Matrix3d())
    translate = mat.ExtractTranslation()
    scale = Gf.Vec3d(*(v.GetLength() for v in mat.ExtractRotationMatrix()))
    mat.Orthonormalize()
    rotate = Gf.Vec3d(*reversed(mat.ExtractRotation().Decompose(*reversed_ident_mtx)))
    return translate, rotate, scale


def computeBbox(prim):
    from pxr import Usd, UsdGeom

    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    return cache.ComputeWorldBound(prim).ComputeAlignedBox()


def computeLocalMeshBbox(prim):
    from pxr import UsdGeom

    mesh = UsdGeom.Mesh(prim)
    points = mesh.GetPointsAttr().Get()

    if not points:
        raise RuntimeError(f"mesh prim has no points: {prim.GetPath()}")

    points_np = np.array([[p[0], p[1], p[2]] for p in points], dtype=float)
    local_min = points_np.min(axis=0)
    local_max = points_np.max(axis=0)
    local_center = (local_min + local_max) * 0.5
    local_size = local_max - local_min

    return local_min, local_max, local_center, local_size


def vec3ToList(vec):
    return [float(vec[0]), float(vec[1]), float(vec[2])]


def getMeshInfo(usd_path, output_path, info_path, open_stage_func=None):
    import omni
    from pxr import Usd, UsdGeom

    if open_stage_func is None:
        from isaacsim.core.utils.stage import open_stage

        open_stage_func = open_stage

    transforms = {}
    open_stage_func(usd_path)
    usd_context = omni.usd.get_context()
    stage = usd_context.get_stage()

    mesh_prims = [
        prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh) and prim.IsValid()
    ]
    if not mesh_prims:
        raise RuntimeError(f"no mesh prims found in environment USD: {usd_path}")

    mesh_infos = []
    for count, prim in enumerate(mesh_prims):
        new_name = f"prim_{count}"
        prim_path = prim.GetPath()
        parent_path = prim_path.GetParentPath()
        new_path = parent_path.AppendChild(new_name)

        bbox = computeBbox(prim)

        world_min = bbox.GetMin()
        world_max = bbox.GetMax()
        world_center = (world_min + world_max) * 0.5
        world_size = world_max - world_min

        local_min, local_max, local_center, local_size = computeLocalMeshBbox(prim)

        xformable = UsdGeom.Xformable(prim)
        matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        _, rot, scale = decomposeMatrix(matrix)

        scale_np = np.abs(np.array(scale, dtype=float))
        local_size_scaled = np.array(local_size, dtype=float) * scale_np

        mesh_infos.append(
            (
                new_name,
                str(prim_path),
                str(new_path),
                world_center,
                rot,
                world_min,
                world_max,
                world_size,
                local_size_scaled,
            )
        )

    for (
        new_name,
        prim_path,
        new_path,
        world_center,
        rot,
        world_min,
        world_max,
        world_size,
        local_size_scaled,
    ) in mesh_infos:
        omni.kit.commands.execute(
            "MovePrim",
            path_from=prim_path,
            path_to=new_path,
        )

        transforms[new_name] = {
            "full_path": prim_path,
            "orientation": np.array(rot).tolist(),
            "position": vec3ToList(world_center),
            "world_bbox_center": vec3ToList(world_center),
            "world_bbox_min": vec3ToList(world_min),
            "world_bbox_max": vec3ToList(world_max),
            "world_bbox_size": vec3ToList(world_size),
            # This is used for the dimensions parameter in MeshShape(..., dimensions=...).
            "usd_dimensions": vec3ToList(local_size_scaled),
        }

    omni.usd.get_context().save_as_stage(output_path)

    with open(info_path, "w") as out_file:
        json.dump(transforms, out_file, indent=2)

    print(f"---Added {info_path}")


def _describeGltf(gltf_path):
    """Summarize a glTF file for error messages."""
    try:
        with open(gltf_path, "r") as in_file:
            gltf = json.load(in_file)
    except Exception as exc:
        return f"unreadable glTF: {type(exc).__name__}: {exc}"
    counts = ", ".join(
        f"{len(gltf.get(key, []))} {key}"
        for key in ("nodes", "meshes", "accessors", "buffers")
    )
    extensions = gltf.get("extensionsRequired") or gltf.get("extensionsUsed") or []
    if extensions:
        counts += f", extensions {extensions}"
    return counts


def convertUsdToMesh(backend, usd_path, mesh_path, *, load_materials=False):
    """Convert a USD to a mesh file at ``mesh_path`` via Isaac's asset converter.

    The converter writes glTF with external buffers (and textures, if
    materials are loaded); the result is re-exported with trimesh into the
    single file named by ``mesh_path`` (e.g. ``foo.glb.bz2``, see
    `scenic.simulators.isaac.utils.writeMesh`), keeping the node names.
    """
    tmp_dir = tempfile.mkdtemp()
    gltf_path = os.path.join(tmp_dir, f"{scenic_utils.assetStem(usd_path)}.gltf")
    if not backend.convertSync(usd_path, gltf_path, load_materials=load_materials):
        raise RuntimeError(f"failed to convert USD to glTF: {usd_path}")

    scene = trimesh.load(gltf_path, force="scene")
    if not scene.geometry:
        raise RuntimeError(
            f"converted mesh has no geometry: {usd_path}. "
            f"The converter's glTF was kept at {gltf_path} ({_describeGltf(gltf_path)}). "
            "If this is an environment, make sure the source USD is flattened."
        )
    scenic_utils.writeMesh(scene, mesh_path)
    print(f"---Added {mesh_path}")
    return mesh_path


def convertedDirForFolder(folder):
    return os.path.join(folder, "_converted")


def convertEnvironmentUsd(
    usd_path,
    mesh_path,
    info_path,
    *,
    backend,
    load_materials=False,
    open_stage_func=None,
):
    """Convert an environment USD into a mesh plus a JSON file of prim metadata.

    The stage is flattened, every mesh prim is renamed to ``prim_N`` (so mesh
    node names are unique and can be mapped back to USD paths), and the JSON
    records each prim's original path, world bbox, and dimensions.
    """
    os.makedirs(os.path.dirname(os.path.abspath(info_path)), exist_ok=True)

    tmp_dir = tempfile.mkdtemp()
    model_name = scenic_utils.assetStem(usd_path) or "environment"

    flattened_usd = os.path.join(tmp_dir, f"{model_name}_flattened.usd")
    flattenUsd(usd_path, flattened_usd)

    renamed_usd = os.path.join(tmp_dir, f"{model_name}_renamed.usd")
    getMeshInfo(flattened_usd, renamed_usd, info_path, open_stage_func=open_stage_func)

    convertUsdToMesh(backend, renamed_usd, mesh_path, load_materials=load_materials)


def assetConvert(args, backend):
    """Batch-convert the USD assets in ``args.folders`` to meshes (see ``usd_to_mesh.py``)."""
    import omni.client

    tmp_dir = tempfile.mkdtemp()
    for folder in args.folders:
        print(f"\nConverting folder {folder}...")
        local_asset_output = args.output or convertedDirForFolder(folder)
        os.makedirs(local_asset_output, exist_ok=True)

        _, models = omni.client.list(folder)
        for i, entry in enumerate(models):
            if i >= args.max_models:
                print(f"max models ({args.max_models}) reached, exiting conversion")
                break

            model = str(entry.relative_path)
            model_name = os.path.splitext(model)[0]
            model_format = os.path.splitext(model)[1][1:]
            print(
                f"Model: {model}, Model Name: {model_name}, model_format: {model_format}"
            )
            if model_format != "usd":
                continue

            input_model_path = folder + "/" + model
            mesh_path, info_path = scenic_utils.convertedMeshPaths(
                model, local_asset_output
            )
            if not args.overwrite and os.path.exists(mesh_path):
                print(f"---Skipping existing {mesh_path}")
                continue

            if model in args.environments:
                convertEnvironmentUsd(
                    input_model_path,
                    str(mesh_path),
                    str(info_path),
                    backend=backend,
                    load_materials=args.load_materials,
                )
            else:
                usd_without_ground = os.path.join(tmp_dir, f"{model}.usd")
                removeGroundPlane(input_model_path, usd_without_ground)
                convertUsdToMesh(
                    backend,
                    usd_without_ground,
                    str(mesh_path),
                    load_materials=args.load_materials,
                )
