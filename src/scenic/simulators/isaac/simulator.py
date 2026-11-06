"""Simulator interface running Scenic scenarios directly in Isaac Sim."""

import os
import tempfile
from urllib.parse import urlparse

from scenic.core.regions import MeshVolumeRegion
from scenic.core.simulators import Simulation, SimulationCreationError, Simulator
from scenic.core.vectors import Vector
from scenic.simulators.isaac import utils
from scenic.simulators.isaac.backends import getBackend


def IsaacSimulator(isaacLab=False, **kwargs):
    """Create an `IsaacSimSimulator`, or an `IsaacLabSimulator` if ``isaacLab`` is set."""
    if isaacLab:
        from scenic.simulators.isaac.lab import IsaacLabSimulator

        kwargs.pop("backend", None)
        return IsaacLabSimulator(**kwargs)
    return IsaacSimSimulator(**kwargs)


class IsaacSimSimulator(Simulator):
    """Simulator running scenarios in Isaac Sim through one of the API backends."""

    def __init__(self, headless=False, environmentUSDPath=None, backend=None):
        super().__init__()

        self.backend = getBackend(backend)
        self.client = self.backend.getSimulationApp(headless=headless)
        self.environmentUSDPath = environmentUSDPath
        self.headless = headless

    def createSimulation(self, scene, **kwargs):
        return IsaacSimSimulation(
            scene,
            self.client,
            self.environmentUSDPath,
            self.backend,
            headless=self.headless,
            **kwargs,
        )

    def destroy(self):
        super().destroy()
        self.backend.closeSimulationApp(self.client)


class IsaacSimSimulation(Simulation):
    def __init__(
        self,
        scene,
        client,
        environmentUSDPath,
        backend,
        *,
        headless=False,
        timestep,
        **kwargs,
    ):
        self.backend = backend
        self.client = client
        self.headless = headless
        self.world = None
        self.tmpMeshDir = tempfile.mkdtemp()

        self.backend.enableExtension("omni.kit.asset_converter")
        if environmentUSDPath:
            self.loadEnvironmentStage(environmentUSDPath)

        timestep = 1.0 / 60.0 if timestep is None else timestep
        self.world = self.backend.createWorld(timestep)

        super().__init__(scene, timestep=timestep, **kwargs)

    def loadEnvironmentStage(self, environmentUSDPath):
        usd_path = self.backend.kitUsdPath(environmentUSDPath)

        if not urlparse(usd_path).scheme:
            if not os.path.isfile(usd_path):
                raise SimulationCreationError(
                    f"Isaac Sim environment USD does not exist or is not a file: {usd_path!r}"
                )
            if not os.access(usd_path, os.R_OK):
                raise SimulationCreationError(
                    f"Isaac Sim environment USD is not readable: {usd_path!r}"
                )

        try:
            opened = self.backend.openEnvironmentStage(usd_path)
        except Exception as exc:
            raise SimulationCreationError(
                f"Unable to open Isaac Sim environment USD {usd_path!r}"
            ) from exc

        if not opened:
            raise SimulationCreationError(
                f"Isaac Sim failed to open environment USD {usd_path!r}"
            )

    def setup(self):
        super().setup()

        self.backend.setupLighting(self.headless)
        self.backend.updateApp(self.client)
        self.backend.initializePhysics(self.world, self.objects)
        self.backend.updateApp(self.client)
        self._useMeshCollidersForExistingObjects()
        self.backend.playWorld(self.world)

    def _useMeshCollidersForExistingObjects(self):
        """Make existing environment prims collide with their exact mesh geometry.

        The USD schema defines approximation ``none`` as "use the mesh itself".
        """
        from pxr import UsdPhysics

        for obj in utils.existingObjects():
            self.backend.setMeshCollisionApproximation(
                obj.primPath, UsdPhysics.Tokens.none
            )

    def step(self):
        self.backend.stepWorld(self.world)

    def createObjectInSimulator(self, obj):
        if (
            obj.blueprint == "IsaacSimObject"
            and not obj.usdPath
            and not obj.isaacAssetPath
        ):
            mesh = MeshVolumeRegion(
                mesh=obj.shape.mesh,
                dimensions=(obj.width, obj.length, obj.height),
            ).mesh
            # The asset converter reads OBJ files as Y-up; pre-rotate so the
            # converted USD comes out Z-up like the Scenic mesh.
            obj.usdPath = self.backend.exportMeshToUsd(
                utils.meshToObjFrame(mesh), obj.name, self.tmpMeshDir
            )

        isaac_sim_obj = obj.create()
        if isaac_sim_obj is None:
            return

        try:
            self.backend.addObject(self.world, isaac_sim_obj, scenic_obj=obj)
        except Exception as exc:
            raise SimulationCreationError(f"Unable to add {obj.name} to world") from exc

    def getProperties(self, obj, properties):
        if not obj.physics:
            return {prop: getattr(obj, prop) for prop in properties}

        raw = self.backend.getPhysicsProperties(self.world, obj)
        return dict(
            position=Vector(*raw["position"]),
            velocity=Vector(*raw["velocity"]),
            speed=raw["speed"],
            angularSpeed=raw["angularSpeed"],
            angularVelocity=Vector(*raw["angularVelocity"]),
            yaw=raw["yaw"],
            pitch=raw["pitch"],
            roll=raw["roll"],
        )

    def destroy(self):
        if self.world is not None:
            self.backend.stopAndClearWorld(self.world)
            self.backend.releaseWorld(self.world)
            self.world = None
