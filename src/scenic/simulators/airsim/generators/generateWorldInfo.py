import argparse
import json
import os
from warnings import warn

import airsim
import numpy as np
import trimesh

from scenic.core.utils import repairMesh
from scenic.core.vectors import Vector

# get output directory
parser = argparse.ArgumentParser()
parser.add_argument(
    "-o",
    "--outputDirectory",
    type=str,
    help="the directory where the world info should be dumped. This should be a directory that doesn't exist.",
    required=True,
)
args = parser.parse_args()


outputDirectory = args.outputDirectory + "/"


# start airsim client
client = None
try:
    client = airsim.MultirotorClient()
    client.confirmConnection()
    client.simPause(True)
except Exception:
    raise RuntimeError("AirSim must be running before executing this code")


try:
    os.makedirs(args.outputDirectory, exist_ok=False)
except FileExistsError:
    raise RuntimeError("output directory already exists")

os.makedirs(outputDirectory + "assets", exist_ok=True)
os.makedirs(outputDirectory + "objectMeshes", exist_ok=True)


assets = client.simListAssets()

# create objects of the assets
objNameDict = {}

for asset in assets:
    objName = client.simSpawnObject(
        object_name=asset,
        asset_name=asset,
        pose=airsim.Pose(position_val=airsim.Vector3r(0, 0, 0)),
        scale=airsim.Vector3r(1, 1, 1),
    )
    objNameDict[asset] = objName.lower()

print("getting mesh data, this may take a few minutes")
meshes = client.simGetMeshPositionVertexBuffers()

# cleanup
for mesh in objNameDict.values():
    client.simDestroyObject(mesh)

print("collected mesh data")
meshDict = {}
for asset in assets:
    objName = objNameDict[asset]
    for mesh in meshes:
        if mesh.name == objName:
            meshDict[asset] = mesh
            break


def makeTrimsh(mesh):
    vertex_list = np.array(mesh.vertices, dtype=np.float32)
    indices = np.array(mesh.indices, dtype=np.uint32)

    num_vertices = int(len(vertex_list) / 3)
    num_indices = len(indices)

    vertices_reshaped = vertex_list.reshape((num_vertices, 3))
    indices_reshaped = indices.reshape((int(num_indices / 3), 3))
    vertices_reshaped = vertices_reshaped.astype(np.float64)
    indices_reshaped = indices_reshaped.astype(np.int64)

    tmesh = trimesh.Trimesh(
        vertices=vertices_reshaped, faces=indices_reshaped, process=True
    )

    # apply mesh rotation
    rotation_matrix = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    tmesh.apply_transform(rotation_matrix)

    if tmesh.body_count > 1:
        tmesh.fix_normals(multibody=True)
    else:
        tmesh.fix_normals()

    try:
        tmesh = repairMesh(tmesh, verbose=True)
    except Exception as e:
        warn(e)
        print("could not repair mesh:", mesh.name)
        return None

    return tmesh


# function for creating a default mesh if needed
_defaultMesh = None


def defaultMesh():
    global _defaultMesh
    if not _defaultMesh:
        _defaultMesh = trimesh.creation.box((1, 1, 1))
    return _defaultMesh


# save an obj file for each asset
for assetName in assets:
    if not (assetName in meshDict):
        continue
    mesh = meshDict[assetName]
    tmesh = makeTrimsh(mesh)
    if not tmesh:
        tmesh = defaultMesh()

    with open(
        outputDirectory + "assets/" + assetName + ".obj",
        "w",
    ) as outfile:
        outfile.write(trimesh.exchange.obj.export_obj(tmesh))


# ----------------- extract world info


cleanedMeshes = []
for mesh in meshes:
    found = False

    # check if mesh is in the created meshes
    for mesh2 in meshDict.values():
        if mesh.name == mesh2.name:
            found = True
            break

    # check if mesh is a vehicle
    for vehicle in client.listVehicles():
        if mesh.name == vehicle:
            found = True
            break

    # if mesh was not found in checks, add it to cleanedMeshes
    if not found:
        cleanedMeshes.append(mesh)

worldInfo = []
for mesh in cleanedMeshes:
    tmesh = makeTrimsh(mesh)
    objectName = mesh.name

    pose = client.simGetObjectPose(objectName)

    position = pose.position
    position = Vector(
        position.x_val,
        position.y_val,
        position.z_val,
    )
    position *= 100  # divide by 100
    position = Vector(position.x, position.y, -position.z)  # negate z axis

    pitch, roll, yaw = airsim.to_eularian_angles(pose.orientation)

    worldInfo.append(
        dict(
            name=objectName,
            position=(position.x, position.y, position.z),
            orientation=(pitch, roll, yaw),
        ),
    )

    with open(
        outputDirectory + "objectMeshes/" + objectName + ".obj",
        "w",
    ) as outfile:
        outfile.write(trimesh.exchange.obj.export_obj(tmesh))


with open(outputDirectory + "worldInfo.json", "w") as outfile:
    json.dump(worldInfo, outfile, indent=4)

print("created world info at:", outputDirectory + "worldInfo.json")
