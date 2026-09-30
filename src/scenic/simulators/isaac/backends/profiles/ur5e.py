"""UR5e arm + Robotiq 2F-85 gripper (manual closed-loop USD authoring)."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from scenic.simulators.isaac.backends.profiles.base import ManipulatorProfile, _arr


@dataclass(frozen=True, eq=False)
class UR5eProfile(ManipulatorProfile):
    # Robotiq 2F-85 gripper authoring/tuning (the "robotiq_2f85" backend path).
    # Declared optional so they can have defaults (see the note in base.py);
    # ``ManipulatorProfile.__post_init__`` rejects a "robotiq_2f85" profile
    # leaving any of them unset.
    gripperPrim: Optional[str] = None
    gripperFullyClosedPosition: Optional[float] = None
    gripperContactMaterialPath: Optional[str] = None
    objectContactMaterialPath: Optional[str] = None
    gripperStaticFriction: Optional[float] = None
    gripperDynamicFriction: Optional[float] = None
    objectStaticFriction: Optional[float] = None
    objectDynamicFriction: Optional[float] = None
    contactOffset: Optional[float] = None
    restOffset: Optional[float] = None
    pickObjectMassKg: Optional[float] = None
    gripperMaxForce: Optional[float] = None
    gripperStiffness: Optional[float] = None
    gripperDamping: Optional[float] = None
    gripperMaxJointVelocityDegPerSec: Optional[float] = None
    mimicNaturalFrequency: Optional[float] = None
    mimicDampingRatio: Optional[float] = None
    outerFingerParallelStiffness: Optional[float] = None


UR5E_PROFILE = UR5eProfile(
    usdPath="Isaac/Robots/UniversalRobots/ur5e/ur5e.usd",
    usdVariants=(("Gripper", "Robotiq_2f_85"),),
    armDofNames=(
        "shoulder_pan_joint",
        "shoulder_lift_joint",
        "elbow_joint",
        "wrist_1_joint",
        "wrist_2_joint",
        "wrist_3_joint",
    ),
    gripperDofNames=("finger_joint",),
    controlLinkName="wrist_3_link",
    endEffectorPrim="wrist_3_link",
    gripperFramePrim="Gripper/Robotiq_2F_85/base_link",
    defaultArmPose=_arr(
        [-np.pi / 2.0, -np.pi / 2.0, -np.pi / 2.0, -np.pi / 2.0, np.pi / 2.0, 0.0]
    ),
    downwardOrientation=_arr([0.0, 0.70710678, 0.70710678, 0.0]),
    tcpOffset=_arr([0.0, 0.0, 0.135]),
    openGripperPositions=_arr([0.0]),
    closedGripperPositions=_arr([float(np.deg2rad(40.0))]),
    gripperOpenVelocity=float(-np.deg2rad(45.0)),
    gripperCloseVelocity=float(np.deg2rad(90.0)),
    gripperStyle="robotiq_2f85",
    gripperControlMode="velocity",
    supportsPickPlace=False,
    ikDamping=0.08,
    ikStepScale=0.25,
    rmpflowPolicyName="UR5e",
    rmpflowUsesTcpOffset=True,
    gripperPrim="Gripper/Robotiq_2F_85",
    gripperFullyClosedPosition=47.0,
    gripperContactMaterialPath="/World/UR5eRobotiqGripMaterial",
    objectContactMaterialPath="/World/UR5ePickObjectGripMaterial",
    gripperStaticFriction=2.0,
    gripperDynamicFriction=2.0,
    objectStaticFriction=2.0,
    objectDynamicFriction=2.0,
    contactOffset=0.002,
    restOffset=0.0,
    pickObjectMassKg=0.475,
    gripperMaxForce=5.0,
    gripperStiffness=0.0,
    gripperDamping=5000.0,
    gripperMaxJointVelocityDegPerSec=130.0,
    mimicNaturalFrequency=0.0,
    mimicDampingRatio=0.0,
    outerFingerParallelStiffness=0.05,
)
