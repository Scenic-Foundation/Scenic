from dataclasses import dataclass, field

from scenic.simulators.isaac.backends.base import IsaacBackend
from scenic.simulators.isaac.backends.experimental_60 import Experimental60Backend


@dataclass
class Experimental51World:
    """Experimental-API objects on top of a Core World (needed to step Isaac Sim 5.1)."""

    core_world: object
    app: object
    timestep: float
    objects: dict = field(default_factory=dict)

    def getObject(self, name):
        return self.objects[name]


class Experimental51Backend(Experimental60Backend):
    """Isaac Sim 5.1 backend using the Core Experimental wrappers."""

    name = "experimental_51"

    def createWorld(self, timestep):
        from isaacsim.core.api import World

        core_world = World(
            stage_units_in_meters=1.0,
            physics_dt=timestep,
            rendering_dt=timestep,
        )
        return Experimental51World(
            core_world=core_world,
            app=self._simulation_app,
            timestep=timestep,
        )

    def runCoroutine(self, coro):
        # SimulationApp has no run_coroutine in 5.1.
        return IsaacBackend.runCoroutine(self, coro)

    def enableExtension(self, name):
        from isaacsim.core.utils.extensions import enable_extension

        enable_extension(name)

    def openEnvironmentStage(self, usd_path):
        import isaacsim.core.experimental.utils.stage as stage_utils

        opened, stage = self._openStage(stage_utils, usd_path)
        if not opened:
            return False
        stage.SetEditTarget(stage.GetSessionLayer())
        return True

    def _openStageForConversion(self, usd_path):
        import isaacsim.core.experimental.utils.stage as stage_utils

        opened, _ = self._openStage(stage_utils, usd_path)
        return opened

    def _openStage(self, stage_utils, usd_path):
        # open_stage returns (opened, stage) in 6.0 but only a bool in 5.1.
        result = stage_utils.open_stage(usd_path)
        if isinstance(result, tuple):
            return result
        stage = stage_utils.get_current_stage() if result else None
        return bool(result), stage

    def initializePhysics(self, world, objects):
        # Referenced assets can enter the loading queue one update after it first empties.
        ready_frames = 0
        while ready_frames < 2:
            world.app.update()
            ready_frames = 0 if self.isStageLoading() else ready_frames + 1
        self._configureManipulatorPickObjectsForWorld(world, objects)
        world.core_world.initialize_physics()
        world.app.update()

    def playWorld(self, world):
        world.core_world.play()

    def stepWorld(self, world):
        world.core_world.step()

    def stopAndClearWorld(self, world):
        world.core_world.stop()
        world.core_world.clear()
        world.objects.clear()

    def releaseWorld(self, world):
        from isaacsim.core.api import World

        World.clear_instance()
