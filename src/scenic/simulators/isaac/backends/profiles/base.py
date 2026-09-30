"""Base manipulator profile consumed by the generic backend manipulator code."""

from dataclasses import dataclass
from typing import Optional

import numpy as np


def _arr(values):
    return np.array(values, dtype=float)


#: Fields the backends read on the ``gripper_style == "robotiq_2f85"`` path
#: (declared by ``UR5eProfile``, the reference implementation).
ROBOTIQ_2F85_REQUIRED_FIELDS = (
    "gripperPrim",
    "gripperFullyClosedPosition",
    "gripperContactMaterialPath",
    "objectContactMaterialPath",
    "gripperStaticFriction",
    "gripperDynamicFriction",
    "objectStaticFriction",
    "objectDynamicFriction",
    "contactOffset",
    "restOffset",
    "pickObjectMassKg",
    "gripperMaxForce",
    "gripperStiffness",
    "gripperDamping",
    "gripperMaxJointVelocityDegPerSec",
    "mimicNaturalFrequency",
    "mimicDampingRatio",
    "outerFingerParallelStiffness",
)


# N.B. no ``kw_only=True``: it needs Python 3.10, and Scenic supports 3.8+.
# Fields are therefore ordered with the required ones first, and subclasses
# must give their extra fields defaults (validating them in ``__post_init__``
# if they are in fact required); profiles should always be built with keyword
# arguments.
#
# ``eq=False`` since several fields are arrays: the generated ``__eq__`` would
# raise on them ("truth value of an array... is ambiguous"), and the generated
# ``__hash__`` would too (arrays are unhashable). Profiles are constants, so
# identity comparison and hashing are what we want anyway.
@dataclass(frozen=True, eq=False)
class ManipulatorProfile:
    """Immutable, typed description of a manipulator robot (a frozen dataclass).

    Field groups: asset (``usd_path``/``usd_variants``), kinematics
    (``*DofNames``, ``*Prim``, ``default_arm_pose``), gripper
    (``*gripper*``), motion tuning (``ik*``, ``rmpflow*``), capability flags
    (``supports_pick_place``).

    ``gripper_style`` selects the backend gripper path: ``"robotiq_2f85"``
    uses the closed-loop Robotiq authoring and requires the fields in
    ``ROBOTIQ_2F85_REQUIRED_FIELDS``; any other value is treated as a plain
    parallel gripper (``gripper_action_deltas`` optional, e.g. Franka).
    ``supports_pick_place`` currently assumes a Franka-style position-mode
    parallel gripper.

    New robots need no Scenic-internal edits: define a profile instance in
    your own module and attach it to a ``ManipulatorRobot`` subclass in your
    scenario (see "Adding a Custom Robot" in the README).
    """

    usdPath: str
    usdVariants: tuple
    armDofNames: tuple
    gripperDofNames: tuple
    controlLinkName: str
    endEffectorPrim: str
    gripperFramePrim: str
    defaultArmPose: np.ndarray
    downwardOrientation: np.ndarray
    tcpOffset: np.ndarray
    openGripperPositions: np.ndarray
    closedGripperPositions: np.ndarray
    gripperStyle: str
    gripperOpenVelocity: Optional[float] = None
    gripperCloseVelocity: Optional[float] = None
    gripperControlMode: str = "position"
    supportsPickPlace: bool = False
    ikDamping: float = 0.05
    ikStepScale: float = 1.0
    rmpflowPolicyName: Optional[str] = None
    rmpflowUsesTcpOffset: bool = False

    def __post_init__(self):
        if self.gripperControlMode == "velocity" and (
            self.gripperOpenVelocity is None or self.gripperCloseVelocity is None
        ):
            raise ValueError(
                "gripper_control_mode='velocity' requires gripper_open_velocity"
                " and gripper_close_velocity"
            )
        if self.gripperStyle == "robotiq_2f85":
            missing = [
                name
                for name in ROBOTIQ_2F85_REQUIRED_FIELDS
                if getattr(self, name, None) is None
            ]
            if missing:
                raise ValueError(
                    "gripper_style='robotiq_2f85' requires fields"
                    f" {missing} (see UR5eProfile)"
                )
