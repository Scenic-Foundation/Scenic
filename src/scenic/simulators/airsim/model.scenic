import trimesh
import json
import os
import numpy as np
import scipy

from scenic.simulators.airsim.simulator import AirSimSimulator
from scenic.simulators.airsim.actions import *
from scenic.simulators.airsim.behaviors import *
from scenic.simulators.airsim.utils import _addPrexistingObj, getPrexistingObj
from scenic.core.simulators import SimulationCreationError
from scenic.core.distributions import distributionFunction

import scenic.simulators.airsim.utils as airsimUtils
from scenic.simulators.airsim.utils import (
    airsimToScenicLocation,
    airsimToScenicOrientation,
    scenicToAirsimOrientation,
    scenicToAirsimScale,
    scenicToAirsimLocation
)



# ---------- global parameters ----------

# setting Default global parameters for any missing parameters
param timestep = 1
param airsimWorldInfoPth = None
param idleStoragePos = (1000,1000,1000)
param worldInfoPath = ""
param worldOffset = Vector(0,0,0)
worldInfoPath = globalParameters.worldInfoPath
worldOffset = globalParameters.worldOffset

airsimUtils.worldOffset = globalParameters.worldOffset

# ---------- helper functions ----------


@distributionFunction
def createMeshShape(subFolder, assetName):
    objFile = assetName+".obj"

    tmesh = trimesh.load(worldInfoPath+subFolder+"/"+objFile)


    center = (tmesh.bounds[0] + tmesh.bounds[1]) / 2


    rotation_matrix = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
    tmesh.apply_transform(rotation_matrix)


    center = (tmesh.bounds[0] + tmesh.bounds[1]) / 2
    center *= 100 #extra multiplication to fix center after coords get divided by 100 in scenic

    # The .obj files are exported in Unreal units (centimetres) and Scenic works
    # in metres, the same factor of 100 that scenicToAirsimLocation applies to
    # positions.
    extents = tmesh.bounding_box.extents / 100
    dimensions = Vector(extents[0], extents[1], extents[2])

    # MeshShape takes the converted dimensions; an object's default size comes
    # from its shape rather than from the `dims` property.
    return MeshShape(tmesh, dimensions=dimensions), center, dimensions




# ---------- simulator creation ----------
simulator AirSimSimulator(timestep=globalParameters.timestep,idleStoragePos=globalParameters.idleStoragePos)


# ---------- simulator getter funcs ----------

def getAssetNames():
    return self.client.simListAssets()

# ---------- base classes ----------
class AirSimPreExisting:
    name: None
    shape: None
    allowCollisions: True
    blueprint: "AirSimPreExisting"



class AirSimActor:
    name: None
    realObjName: None
    assetName: None
    blueprint: None


    # override
    _shapeData: createMeshShape("assets",self.assetName)
    shape: self._shapeData[0]
    centerOffset: self._shapeData[1] #offset in unreal coords
    dims: self._shapeData[2] #save original dims before scenic scales mesh

    def __str__(self):
        return self.assetName


# ---------- inherited classes ----------
class Drone(AirSimActor):
    blueprint: "Drone"
    assetName: "Quadrotor1"
    startHovering: True
    # Scenic-frame velocity the drone has at the first simulation step, or None
    # to spawn at rest. Requires startHovering.
    startVelocity: None
    _startPos: None

class PX4Drone(Drone):
    blueprint: "PX4Drone"
    startHovering: True
    _startPos: None


class StaticObj(AirSimActor):
    blueprint: "StaticObj"
    physEnabled: False
    materialName: None



# ---------- body ----------



# ensure worldInfoPath is set
if not worldInfoPath:
    raise SimulationCreationError('\nworldInfoPath not set, use:\n param worldInfoPath = "[YOUR PATH HERE]" \n\n more information on creating and using worldInfo in docs')
else:
    worldInfoPath += "/"


# Create prexisiting airsim objs
prexisitingObjs = {}
with open(
    worldInfoPath+"worldInfo.json",
    "r",
) as inFile:
    meshDatas = json.load(inFile)
    for meshData in meshDatas:

        actorName = meshData["name"]
        meshShape,centerOffset,dims = createMeshShape("objectMeshes",actorName)

        # convert unreal position to airsim position
        position = Vector(meshData["position"][0],meshData["position"][1],meshData["position"][2]) #unreal position

        # get orientation
        rot = meshData["orientation"]
        pitch,roll,yaw = rot[0] , rot[1],rot[2]
        angles = (-yaw - 90, pitch,roll)
        r = scipy.spatial.transform.Rotation.from_euler(
            seq="ZXY", angles=angles, degrees=True
        )
        orientation =  Orientation(r)

        scenicLoc = airsimToScenicLocation(airsim.Vector3r(position.x, position.y, position.z),centerOffset,fromPose=False)
        newObj = new AirSimPreExisting with shape meshShape, with name actorName,
            at scenicLoc,
            facing orientation # pitch, roll, yaw


        _addPrexistingObj(newObj)


# generate list of assets
assets = []
for filename in os.listdir(worldInfoPath+"/assets"):
    if filename.endswith(".obj"):
        # append the obj name without the .obj extension
        assets.append(filename[:-4])


param assets = assets
