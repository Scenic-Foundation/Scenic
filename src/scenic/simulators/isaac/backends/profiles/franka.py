"""Franka Panda + built-in parallel gripper."""

from dataclasses import dataclass
from typing import Optional

from scenic.simulators.isaac.backends.profiles.base import ManipulatorProfile, _arr


@dataclass(frozen=True, eq=False)
class FrankaProfile(ManipulatorProfile):
    # Optional, so it can have a default (see the note in base.py).
    gripperActionDeltas: Optional[tuple] = None


FRANKA_PROFILE = FrankaProfile(
    usdPath="Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd",
    usdVariants=(("Gripper", "AlternateFinger"), ("Mesh", "Performance")),
    armDofNames=(
        "panda_joint1",
        "panda_joint2",
        "panda_joint3",
        "panda_joint4",
        "panda_joint5",
        "panda_joint6",
        "panda_joint7",
    ),
    gripperDofNames=("panda_finger_joint1", "panda_finger_joint2"),
    controlLinkName="panda_hand",
    endEffectorPrim="panda_hand",
    gripperFramePrim="panda_rightfinger",
    defaultArmPose=_arr([0.012, -0.568, 0.0, -2.811, 0.0, 3.037, 0.741]),
    downwardOrientation=_arr([0.0, 1.0, 0.0, 0.0]),
    tcpOffset=_arr([0.0, 0.0, 0.0877]),
    openGripperPositions=_arr([0.05, 0.05]),
    closedGripperPositions=_arr([0.01, 0.01]),
    gripperStyle="franka_hand",
    gripperControlMode="position",
    supportsPickPlace=True,
    ikDamping=0.05,
    ikStepScale=1.0,
    rmpflowPolicyName="Franka",
    rmpflowUsesTcpOffset=False,
    gripperActionDeltas=(0.01, 0.01),
)
