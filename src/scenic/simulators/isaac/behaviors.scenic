from scenic.simulators.isaac.actions import *
from scenic.simulators.isaac.backends.base import wxyzToRotation
import numpy as np

# for the create3 wheeled robot
behavior KeepMoving():

    threshold = .01
    while True:
        if self.speed < threshold:
            for i in range(100):
                take ApplyControllerAction([-.2, 0])
            for i in range(50):
                take ApplyControllerAction([0, np.pi])
        else:
            take ApplyControllerAction([.2, 0])

# for the jetbot robot
behavior JetbotDrive():
    while True:
        take ApplyControllerAction([.2, 0])

# for the kaya robot
behavior DriveForward():
    while True:
        take ApplyControllerAction([-0.7, 0.0, 0.0])

behavior RandomMovement():
    i = 0
    while True:
        if i < 300:
            take ApplyControllerAction([0.4, 0.0, 0.0])   # forward
        elif i < 600:
            take ApplyControllerAction([-0.4, 0.0, 0.0])  # backward
        elif i < 900:
            take ApplyControllerAction([0.0, 0.2, 0.0])   # strafe one way
        elif i < 1200:
            take ApplyControllerAction([0.0, -0.2, 0.0])  # strafe the other way
        elif i < 1500:
            take ApplyControllerAction([0.0, 0.0, 0.2])   # rotate
        else:
            i = 0
            take ApplyControllerAction([0.0, 0.0, 0.0])

        i += 1

# for the Franka Panda manipulator
behavior PickPlaceObject(targetObject, goalPosition):
    while True:
        take ApplyPickPlaceControllerAction(targetObject, goalPosition)


# Generic manipulator primitives. Scenario-level behaviors should compose these
# with `do ...` so the overall task is visible in the scenario file.

def _quaternionDistance(quaternion_a, quaternion_b):
    """Angle (radians) between two Isaac wxyz quaternions."""
    rotation_a = wxyzToRotation(np.asarray(quaternion_a, dtype=float).flatten()[:4])
    rotation_b = wxyzToRotation(np.asarray(quaternion_b, dtype=float).flatten()[:4])
    return (rotation_a * rotation_b.inv()).magnitude()

def _positionReached(agent, sim, target, threshold):
    ee_pos, _ = agent.getEePose(sim)
    ee = np.array(ee_pos, dtype=float).flatten()[:3]
    return np.linalg.norm(ee - target) <= threshold

def _orientationReached(agent, sim, target, threshold):
    _, ee_orientation = agent.getEePose(sim)
    return _quaternionDistance(ee_orientation, target) <= threshold

def _gripperReached(agent, sim, target, threshold):
    positions = np.array(agent.getGripperPositions(sim), dtype=float)
    positions = positions.flatten()[:len(target)]
    return np.linalg.norm(positions - target) <= threshold

behavior _RepeatAction(action):
    while True:
        take action

behavior _StepRotate(orientation):
    sim = simulation()
    while True:
        ee_pos, _ = self.getEePose(sim)
        take MoveToEEPoseAction(ee_pos, orientation)

behavior MoveEndEffectorTo(position, orientation=None, threshold=0.035, maxSteps=600):
    sim = simulation()
    target = np.array(position, dtype=float).flatten()[:3]
    try:
        do _RepeatAction(MoveToEEPoseAction(position, orientation)) for maxSteps steps
    interrupt when _positionReached(self, sim, target, threshold):
        abort
    if not _positionReached(self, sim, target, threshold):
        raise ManipulatorTimeout(f"MoveEndEffectorTo did not converge within {maxSteps} steps")


behavior RotateEndEffectorTo(orientation, threshold=0.05, maxSteps=600):
    sim = simulation()
    target = np.array(orientation, dtype=float).flatten()[:4]
    try:
        do _StepRotate(orientation) for maxSteps steps
    interrupt when _orientationReached(self, sim, target, threshold):
        abort
    if not _orientationReached(self, sim, target, threshold):
        raise ManipulatorTimeout(f"RotateEndEffectorTo did not converge within {maxSteps} steps")


behavior OpenGripper(threshold=0.002, maxSteps=100):
    sim = simulation()
    target = np.array(self.getGripperTargetPositions(True), dtype=float)
    try:
        do _RepeatAction(OpenGripperAction()) for maxSteps steps
    interrupt when _gripperReached(self, sim, target, threshold):
        abort


behavior CloseGripper(threshold=0.002, maxSteps=100):
    sim = simulation()
    target = np.array(self.getGripperTargetPositions(False), dtype=float)
    try:
        do _RepeatAction(CloseGripperAction()) for maxSteps steps
    interrupt when _gripperReached(self, sim, target, threshold):
        abort


behavior HoldPosition(maxSteps=30):
    do _RepeatAction(HoldPositionAction()) for maxSteps steps
