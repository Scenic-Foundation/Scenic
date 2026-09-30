"""Scenic world model for the Isaac Sim / Isaac Lab interface.

See :file:`examples/isaacsim/README.md` for the available global parameters
and object classes.
"""

import json
import os
import uuid
import numpy as np
import trimesh
from trimesh.transformations import decompose_matrix
from scipy.spatial.transform import Rotation

from scenic.core.errors import InvalidScenarioError
from scenic.core.vectors import Orientation
from scenic.simulators.isaac.actions import *
from scenic.simulators.isaac.actions import _Robot, _ManipulatorRobot
from scenic.simulators.isaac.behaviors import *
from scenic.simulators.isaac.backends import DEFAULT_BACKEND_NAME, getBackend
from scenic.simulators.isaac.backends.profiles import FRANKA_PROFILE, UR5E_PROFILE
from scenic.simulators.isaac.simulator import IsaacSimSimulator
from scenic.simulators.isaac.utils import _addExistingObj, EnvironmentMeshCache

# ---------- global parameters ----------

param environmentUSDPath = None
param environmentInfoPath = None
param environmentMeshPath = None
param headless = False
param isaacBackend = DEFAULT_BACKEND_NAME
param isaacLab = False

# Isaac Lab settings (used when isaacLab is set).
param labTask = None
param labEnvCfg = None
param labDevice = "cuda:0"
param labNumEnvs = 1
param labEnvSpacing = 10.0
param labTimestep = 1 / 120
param labDebugLifecycle = False

# Remote mode: `scenic <file> --param isaacRemote 1` runs the scenario on the
# bridge inside an already-running Isaac Sim instead of compiling it locally.
param isaacRemote = False
param isaacRemoteHost = None
param isaacRemotePort = None
if globalParameters.isaacRemote:
    from scenic.simulators.isaac.remote.client import runRemoteFromCompilation
    runRemoteFromCompilation(
        host=globalParameters.isaacRemoteHost,
        port=globalParameters.isaacRemotePort,
    )

isaac_backend = getBackend("lab" if globalParameters.isaacLab else globalParameters.isaacBackend)

# ---------- simulator creation ----------

if globalParameters.isaacLab:
    from scenic.simulators.isaac.lab import IsaacLabSimulator
    simulator IsaacLabSimulator(
        environmentUSDPath=globalParameters.environmentUSDPath,
        headless=globalParameters.headless,
        task=globalParameters.labTask,
        env_cfg_entry_point=globalParameters.labEnvCfg,
        device=globalParameters.labDevice,
        num_envs=globalParameters.labNumEnvs,
        env_spacing=globalParameters.labEnvSpacing,
        timestep=globalParameters.labTimestep,
        debug_lifecycle=globalParameters.labDebugLifecycle,
    )
else:
    simulator IsaacSimSimulator(
        environmentUSDPath=globalParameters.environmentUSDPath,
        headless=globalParameters.headless,
        backend=globalParameters.isaacBackend,
    )

# ---------- base classes ----------

class IsaacSimObject:
    """An object spawned in Isaac Sim.

    With ``usdPath`` or ``isaacAssetPath`` set, the USD asset is spawned and
    scaled to the object's dimensions; otherwise the Scenic shape is converted
    into a USD mesh.
    """
    name: f"Object_{uuid.uuid4().hex[:8]}"
    physics: True
    mass: None
    density: None
    usdPath: None
    isaacAssetPath: None
    initialRotation: None
    blueprint: "IsaacSimObject"

    def create(self):
        return isaac_backend.createGenericObject(self)

class ExistingIsaacSimObject(IsaacSimObject):
    """A prim of the environment USD, created by the model for spatial reasoning."""
    allowCollisions: True
    blueprint: "ExistingIsaacSimObject"
    physics: False
    primPath: None

    def create(self):
        return None

class IsaacSimRobot(IsaacSimObject, _Robot):
    """An articulated robot; see the README for the wheeled-robot and ``control`` metadata."""
    name: f"Robot_{uuid.uuid4().hex[:8]}"
    controller: None
    control: None
    blueprint: "Robot"

    # Set by ManipulatorRobot subclasses; declared here (defaulting to None)
    # so createRobot's dispatch check works for every kind of robot.
    manipulatorProfile: None

    # Wheeled-robot metadata ("differential", "holonomic", or "ackermann").
    wheelController: None
    wheelDofNames: []
    wheelRadius: None
    wheelBase: None
    # Ackermann only.
    trackWidth: None
    steeringDofNames: []
    frontWheelRadius: self.wheelRadius
    backWheelRadius: self.wheelRadius
    # Holonomic only.
    maxLinearSpeed: 0.5
    maxAngularSpeed: 0.8
    maxWheelSpeed: 10.0

    def create(self):
        return isaac_backend.createRobot(self)

    def move(self, sim, command):
        sim.backend.applyRobotControl(sim, self, command)

# These built-in wheeled-robot USD assets are authored (like most of Isaac's
# robot asset library) with local +X as "forward", while Scenic's convention
# is local +Y ("north") at heading 0. `initialRotation` corrects for this fixed
# per-asset offset so a Scenic heading of 0 matches the direction the robot
# actually faces/drives; see `IsaacBackend.scenicToIsaacOrientation`. The
# correction was determined empirically for each asset -- it isn't necessarily
# the same for every USD asset (see e.g. the forklift example, which needs a
# different correction for its own asset).
class Create3(IsaacSimRobot):
    shape: CylinderShape()
    width: 0.335
    length: 0.335
    height: .1
    isaacAssetPath: "Isaac/Robots/iRobot/Create3/create_3.usd"
    initialRotation: (90 deg, 0, 0)

    # Differential-drive metadata.
    wheelRadius: 0.03575
    wheelBase: 0.233
    wheelDofNames: ["left_wheel_joint", "right_wheel_joint"]
    wheelController: "differential"

class Jetbot(IsaacSimRobot):
    width: 0.16
    length: 0.16
    height: 0.12
    isaacAssetPath: "Isaac/Robots/NVIDIA/Jetbot/jetbot.usd"
    initialRotation: (90 deg, 0, 0)

    # Differential-drive metadata.
    wheelRadius: 0.03
    wheelBase: 0.1125
    wheelDofNames: ["left_wheel_joint", "right_wheel_joint"]
    wheelController: "differential"

class Kaya(IsaacSimRobot):
    width: 0.2
    length: 0.2
    height: 0.2
    isaacAssetPath: "Isaac/Robots/NVIDIA/Kaya/kaya.usd"
    initialRotation: (90 deg, 0, 0)

    # Holonomic-drive metadata.
    wheelDofNames: ["axle_0_joint", "axle_1_joint", "axle_2_joint"]
    wheelController: "holonomic"

class ManipulatorRobot(IsaacSimRobot, _ManipulatorRobot):
    """An arm described by a `ManipulatorProfile`; see the README to add new arms."""
    endEffectorOffset: [0.0, 0.0, 0.0]
    endEffectorOrientation: None
    armMaxVelocities: None

    def move(
        self,
        sim,
        targetObject,
        goalPosition,
        endEffectorOffset=None,
        endEffectorOrientation=None,
    ):
        sim.backend.moveManipulatorPickPlace(
            sim,
            self,
            targetObject,
            goalPosition,
            endEffectorOffset,
            endEffectorOrientation,
        )

    def moveToPose(self, sim, position, orientation=None):
        sim.backend.moveManipulatorEndEffector(sim, self, position, orientation)

    def setGripper(self, sim, opened):
        sim.backend.setManipulatorGripper(sim, self, opened)

    def setJointPositions(self, sim, jointPositions):
        sim.backend.setManipulatorArmJointPositions(sim, self, jointPositions)

    def holdPosition(self, sim):
        sim.backend.holdManipulatorPosition(sim, self)

    def getEePose(self, sim):
        return sim.backend.getManipulatorEndEffectorPose(sim, self)

    def getGripperPositions(self, sim):
        return sim.backend.getManipulatorGripperPositions(sim, self)

    def getGripperTargetPositions(self, opened):
        return isaac_backend.manipulatorGripperTargetPositions(
            self.manipulatorProfile, opened
        )

class FrankaPanda(ManipulatorRobot):
    shape: BoxShape()
    width: 0.3
    length: 0.3
    height: 0.9
    manipulatorProfile: FRANKA_PROFILE

class UR5e(ManipulatorRobot):
    shape: BoxShape()
    width: 0.4
    length: 0.4
    height: 0.515
    manipulatorProfile: UR5E_PROFILE

class GroundPlane(IsaacSimObject):
    name: "GroundPlane"
    width: 5
    length: 5
    height: 0.01
    physics: False
    blueprint: "GroundPlane"

    def create(self):
        return isaac_backend.createGroundPlane(self)

# ---------- terrain (Isaac Lab only) ----------
#
# NOTE: the terrain classes below depend on a ``scenic.core.terrain`` module
# (heightfield generators and their Cfg classes) that is not in the
# repository, so they currently cannot be instantiated.

class Terrain:
    """A heightfield terrain patch; the Lab interface merges all patches into one mesh."""
    horizontalScale: 0.1
    verticalScale: 0.005
    width: 10.0
    length: 10.0
    size: (self.width, self.length)
    difficulty: None
    blueprint: "Terrain"
    physics: False
    position: (0, 0, 0)

    # These will be filled by subclasses in create()
    mesh: None
    subterrain: None

class RandomUniformTerrain(Terrain):
    name: f"RandomUniformTerrain_{uuid.uuid4().hex[:8]}"

    noiseRange: (0.0, 1.0)
    noiseStep: 0.01
    downsampledScale: 1.0

    def create(self):
        from scenic.core.terrain import random_uniform_terrain, RandomUniformTerrainCfg, subterrain_to_mesh
        terrain_cfg = RandomUniformTerrainCfg(
            noise_range=self.noiseRange,
            noise_step=self.noiseStep,
            downsampled_scale=self.downsampledScale,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
            border_width=1.0,
            size=self.size,
        )
        subterrain = random_uniform_terrain(cfg=terrain_cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(subterrain)
        self.subterrain = subterrain

class SlopedTerrain(Terrain):
    name: f"SlopedTerrain_{uuid.uuid4().hex[:8]}"
    slope: 0.25

    def create(self):
        from scenic.core.terrain import sloped_terrain, SlopedTerrainCfg, subterrain_to_mesh
        terrain_cfg = SlopedTerrainCfg(
            slope=self.slope,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
            size=self.size,
        )
        subterrain = sloped_terrain(cfg=terrain_cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(subterrain)
        self.subterrain = subterrain

class PyramidSlopedTerrain(Terrain):
    name: f"PyramidSlopedTerrain_{uuid.uuid4().hex[:8]}"
    slope: 0.25
    platformSize: 1.0

    def create(self):
        from scenic.core.terrain import pyramid_sloped_terrain, PyramidSlopedTerrainCfg, subterrain_to_mesh
        terrain_cfg = PyramidSlopedTerrainCfg(
            slope=self.slope,
            platform_size=self.platformSize,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
            size=self.size,
        )
        subterrain = pyramid_sloped_terrain(cfg=terrain_cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(subterrain)
        self.subterrain = subterrain

class DiscreteObstaclesTerrain(Terrain):
    name: f"DiscreteObstaclesTerrain_{uuid.uuid4().hex[:8]}"
    maxHeight: 0.2
    minSize: 0.5
    maxSize: 2.0
    numRects: 5
    platformSize: 1.0

    def create(self):
        from scenic.core.terrain import discrete_obstacles_terrain, DiscreteObstaclesTerrainCfg, subterrain_to_mesh
        terrain_cfg = DiscreteObstaclesTerrainCfg(
            max_height=self.maxHeight,
            min_size=self.minSize,
            max_size=self.maxSize,
            num_rects=self.numRects,
            platform_size=self.platformSize,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
            size=self.size,
        )
        subterrain = discrete_obstacles_terrain(cfg=terrain_cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(subterrain)
        self.subterrain = subterrain

class WaveTerrain(Terrain):
    name: f"WaveTerrain_{uuid.uuid4().hex[:8]}"
    numWaves: 1
    amplitude: 1.0

    def create(self):
        from scenic.core.terrain import wave_terrain, WaveTerrainCfg, subterrain_to_mesh
        cfg = WaveTerrainCfg(
            num_waves=self.numWaves,
            amplitude=self.amplitude,
            size=self.size,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
        )
        sub = wave_terrain(cfg=cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(sub)
        self.subterrain = sub

class StairsTerrain(Terrain):
    name: f"StairsTerrain_{uuid.uuid4().hex[:8]}"
    stepWidth: 1.0
    stepHeight: 0.1

    def create(self):
        from scenic.core.terrain import stairs_terrain, StairsTerrainCfg, subterrain_to_mesh
        cfg = StairsTerrainCfg(
            step_width=self.stepWidth,
            step_height=self.stepHeight,
            size=self.size,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
        )
        sub = stairs_terrain(cfg=cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(sub)
        self.subterrain = sub

class PyramidStairsTerrain(Terrain):
    name: f"PyramidStairsTerrain_{uuid.uuid4().hex[:8]}"
    stepWidth: 1.0
    stepHeight: 0.1
    platformSize: 1.0

    def create(self):
        from scenic.core.terrain import pyramid_stairs_terrain, PyramidStairsTerrainCfg, subterrain_to_mesh
        cfg = PyramidStairsTerrainCfg(
            step_width=self.stepWidth,
            step_height=self.stepHeight,
            platform_size=self.platformSize,
            size=self.size,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
        )
        sub = pyramid_stairs_terrain(cfg=cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(sub)
        self.subterrain = sub

class SteppingStonesTerrain(Terrain):
    name: f"SteppingStonesTerrain_{uuid.uuid4().hex[:8]}"
    stoneSize: 1.0
    stoneDistance: 1.0
    maxHeight: 0.2
    platformSize: 1.0
    depth: -10.0

    def create(self):
        from scenic.core.terrain import stepping_stones_terrain, SteppingStonesTerrainCfg, subterrain_to_mesh
        cfg = SteppingStonesTerrainCfg(
            stone_size=self.stoneSize,
            stone_distance=self.stoneDistance,
            max_height=self.maxHeight,
            platform_size=self.platformSize,
            depth=self.depth,
            size=self.size,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
        )
        sub = stepping_stones_terrain(cfg=cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(sub)
        self.subterrain = sub

class PolesTerrain(Terrain):
    name: f"PolesTerrain_{uuid.uuid4().hex[:8]}"
    difficulty: 1.0

    def create(self):
        from scenic.core.terrain import poles_terrain, PolesTerrainCfg, subterrain_to_mesh
        cfg = PolesTerrainCfg(
            difficulty=self.difficulty,
            size=self.size,
            horizontal_scale=self.horizontalScale,
            vertical_scale=self.verticalScale,
        )
        sub = poles_terrain(cfg=cfg, difficulty=self.difficulty)
        self.mesh = subterrain_to_mesh(sub)
        self.subterrain = sub

# ---------- existing environment objects ----------
#
# When an environment USD is given, convert it (once, cached) into a mesh plus
# per-prim metadata, and create an ExistingIsaacSimObject for each prim so
# scenarios can place objects relative to the environment (see getExistingObj).

if globalParameters.environmentUSDPath:
    try:
        environmentMeshPath, environmentInfoPath = isaac_backend.ensureEnvironmentMeshPaths(
            globalParameters.environmentUSDPath,
            globalParameters.environmentMeshPath,
            globalParameters.environmentInfoPath,
            headless=globalParameters.headless,
        )
    except Exception as exc:
        raise InvalidScenarioError(
            f"Unable to prepare Isaac environment mesh assets for "
            f"{globalParameters.environmentUSDPath!r}: {exc}"
        ) from exc

    if not os.path.isfile(environmentMeshPath):
        raise InvalidScenarioError(
            f"Isaac environment mesh file does not exist: {environmentMeshPath}"
        )
    if not os.path.isfile(environmentInfoPath):
        raise InvalidScenarioError(
            f"Isaac environment info file does not exist: {environmentInfoPath}"
        )

    scene = trimesh.load(environmentMeshPath, force="scene")
    with open(environmentInfoPath, "r") as inFile:
        meshData = json.load(inFile)

    if not scene.geometry:
        raise InvalidScenarioError(
            f"Isaac environment mesh file has no geometry: {environmentMeshPath}. "
            "Regenerate the GLTF and make sure any external GLTF buffer files are present."
        )

    geometry_nodes = list(scene.graph.nodes_geometry)
    if not geometry_nodes:
        raise InvalidScenarioError(
            f"Isaac environment mesh file has geometry but no scene graph nodes: "
            f"{environmentMeshPath}"
        )

    environmentMeshCache = EnvironmentMeshCache(environmentMeshPath, environmentInfoPath)

    for node_name in geometry_nodes:
        if node_name not in meshData:
            available = ", ".join(sorted(meshData))
            raise InvalidScenarioError(
                f"Isaac environment mesh node {node_name!r} is missing from "
                f"{environmentInfoPath}; available nodes: {available}"
            )

        world_transform, geometry_name = scene.graph.get(node_name, "World")
        if geometry_name is None:
            geometry_name = node_name
        mesh = scene.geometry[geometry_name]
        world_transform = np.asarray(world_transform, dtype=float)
        scale = np.abs(np.array(decompose_matrix(world_transform)[0], dtype=float))
        orientation = Orientation(Rotation.from_matrix(world_transform[:3, :3] / scale))

        info = meshData[node_name]
        path = info["full_path"]

        # Prefer authoritative USD bbox data generated before GLTF conversion/repair.
        if "world_bbox_center" in info:
            world_center = np.array(info["world_bbox_center"], dtype=float)
        else:
            local_center = np.append(mesh.bounding_box.centroid, 1.0)
            world_center = np.dot(world_transform, local_center)[:3]

        if "usd_dimensions" in info:
            dimensions = tuple(np.maximum(float(x), 1e-6) for x in info["usd_dimensions"])
        else:
            raw_extents = np.array(mesh.extents, dtype=float)
            dimensions = tuple(np.maximum(raw_extents * scale, 1e-6))

        shape_mesh = environmentMeshCache.get(node_name, mesh)

        newObj = new ExistingIsaacSimObject at world_center,
                    with shape MeshShape(shape_mesh, dimensions=dimensions),
                    with name path,
                    with primPath path,
                    facing orientation

        _addExistingObj(newObj)

    environmentMeshCache.save()
