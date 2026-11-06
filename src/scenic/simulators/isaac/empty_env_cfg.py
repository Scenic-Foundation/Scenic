from __future__ import annotations

from isaaclab.envs import ManagerBasedEnvCfg
from isaaclab.managers import (
    ObservationGroupCfg as ObsGroup,
    ObservationTermCfg as ObsTerm,
)
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.utils import configclass
import torch


def zeroObs(env):
    """Dummy observation so ManagerBasedEnv has a valid policy observation."""
    return torch.zeros((env.num_envs, 1), device=env.device)


@configclass
class ScenicSceneCfg(InteractiveSceneCfg):
    """Initially empty scene.

    The Scenic Isaac Lab backend will dynamically add scene fields here before
    constructing the ManagerBasedEnv.
    """

    pass


@configclass
class ActionsCfg:
    pass


@configclass
class ObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        zero = ObsTerm(func=zeroObs)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()


@configclass
class EventsCfg:
    pass


@configclass
class ScenicEmptyEnvCfg(ManagerBasedEnvCfg):
    scene: ScenicSceneCfg = ScenicSceneCfg(num_envs=1, env_spacing=10.0)
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    events: EventsCfg = EventsCfg()

    def __post_init__(self):
        self.decimation = 1
        self.sim.dt = 0.01

        self.viewer.eye = [7.0, 7.0, 6.0]
        self.viewer.lookat = [0.0, 0.0, 0.0]
