"""Actions for Isaac Sim robots.

Each action performs one simulation step of control; behaviors loop over
them. The actions call methods of the robot classes in ``model.scenic``, which
dispatch to the active backend.
"""

from scenic.core.simulators import Action


class ManipulatorTimeout(Exception):
    """Raised when a manipulator end-effector move does not converge within maxSteps."""


class _Robot:
    """Marker mixin for robots that can take a `RobotAction`."""


class _ManipulatorRobot(_Robot):
    """Marker mixin for robots that can take a `ManipulatorRobotAction`."""


class RobotAction(Action):
    """Base class for actions which can only be taken by a robot."""

    def canBeTakenBy(self, agent):
        return isinstance(agent, _Robot)


class ManipulatorRobotAction(Action):
    """Base class for actions which can only be taken by a manipulator robot."""

    def canBeTakenBy(self, agent):
        return isinstance(agent, _ManipulatorRobot)


class ApplyControllerAction(RobotAction):
    """Feed a command to the robot's controller (e.g. [linear, angular] speeds)."""

    def __init__(self, command):
        self.command = command

    def applyTo(self, obj, sim):
        obj.move(sim, self.command)


class ApplyPickPlaceControllerAction(ManipulatorRobotAction):
    """Advance the backend's built-in pick-and-place controller by one step."""

    def __init__(
        self,
        targetObject,
        goalPosition,
        endEffectorOffset=None,
        endEffectorOrientation=None,
    ):
        self.targetObject = targetObject
        self.goalPosition = goalPosition
        self.endEffectorOffset = endEffectorOffset
        self.endEffectorOrientation = endEffectorOrientation

    def applyTo(self, obj, sim):
        obj.move(
            sim,
            self.targetObject,
            self.goalPosition,
            self.endEffectorOffset,
            self.endEffectorOrientation,
        )


class MoveToEEPoseAction(ManipulatorRobotAction):
    """Take one IK step moving the end effector toward a world pose.

    ``orientation`` is an Isaac wxyz quaternion, or None to use the profile's
    default (a downward-facing grasp).
    """

    def __init__(self, position, orientation=None):
        self.position = position
        self.orientation = orientation

    def applyTo(self, obj, sim):
        obj.moveToPose(sim, self.position, self.orientation)


class SetArmJointPoseAction(ManipulatorRobotAction):
    """Command explicit arm joint position targets."""

    def __init__(self, jointPositions):
        self.jointPositions = jointPositions

    def applyTo(self, obj, sim):
        obj.setJointPositions(sim, self.jointPositions)


class OpenGripperAction(ManipulatorRobotAction):
    def applyTo(self, obj, sim):
        obj.setGripper(sim, True)


class CloseGripperAction(ManipulatorRobotAction):
    def applyTo(self, obj, sim):
        obj.setGripper(sim, False)


class HoldPositionAction(ManipulatorRobotAction):
    """Hold the current arm targets so the arm settles in place."""

    def applyTo(self, obj, sim):
        obj.holdPosition(sim)
