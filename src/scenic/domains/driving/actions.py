"""Actions for dynamic agents in the driving domain.

These actions are automatically imported when using the driving domain.

The `RegulatedControlAction` is based on code from the `CARLA`_ project, licensed under
the following terms:

    Copyright (c) 2018-2020 CVC.

    This work is licensed under the terms of the MIT license.
    For a copy, see <https://opensource.org/licenses/MIT>.

.. _CARLA: https://carla.org/
"""

import math

from scenic.core.simulators import Action
from scenic.core.vectors import Vector

## Mixin classes indicating support for various types of actions.


class Steers:
    """Mixin protocol for agents which can steer.

    Specifically, agents must support throttling, braking, steering, setting the hand
    brake, and going into reverse.
    """

    def setThrottle(self, throttle):
        raise NotImplementedError

    def setSteering(self, steering):
        raise NotImplementedError

    def setBraking(self, braking):
        raise NotImplementedError

    def setHandbrake(self, handbrake):
        raise NotImplementedError

    def setReverse(self, reverse):
        raise NotImplementedError


class Travels:
    """Mixin protocol for agents which can travel with a given direction and speed.

    We provide a simplistic implementation which directly sets the velocity of the agent.
    This implementation needs to be explicitly opted-into, since simulators may provide a
    more sophisticated API for moving such agents.
    """

    def setTravelDirection(self, heading):
        velocity = Vector(0, self.speed).rotatedBy(heading)
        self.setVelocity(velocity)

    def setTravelSpeed(self, speed):
        velocity = speed * self.velocity.normalized()
        self.setVelocity(velocity)


class Walks(Travels):
    """Mixin protocol for agents which can walk with a given direction and speed.

    This is the pedestrian-facing API used by scenarios and simulator interfaces.
    It is also a backwards-compatible alias layer for `Travels`, so generic
    direction and speed actions can control walkers.

    We provide a simplistic implementation which directly sets the velocity of the agent.
    This implementation needs to be explicitly opted-into, since simulators may provide a
    more sophisticated API that properly animates pedestrians.
    """

    # Legacy pedestrian API (simulator backends often override these).
    def setWalkingDirection(self, heading):
        super().setTravelDirection(heading)

    def setWalkingSpeed(self, speed):
        super().setTravelSpeed(speed)

    # Bridge: ensure Travel actions on walkers go through walking overrides.
    def setTravelDirection(self, heading):
        self.setWalkingDirection(heading)

    def setTravelSpeed(self, speed):
        self.setWalkingSpeed(speed)


## Actions available to all agents


class SetPositionAction(Action):
    """Teleport an agent to the given position."""

    def __init__(self, pos: Vector):
        self.pos = pos

    def applyTo(self, obj, sim):
        obj.setPosition(self.pos, obj.elevation)


class OffsetAction(Action):
    """Teleports actor forward (in direction of its heading) by some offset."""

    def __init__(self, offset: Vector):
        self.offset = offset

    def applyTo(self, obj, sim):
        pos = obj.position.offsetRotated(obj.heading, self.offset)
        obj.setPosition(pos, obj.elevation)


class SetVelocityAction(Action):
    """Set the velocity of an agent."""

    def __init__(self, xVel: float, yVel: float, zVel: float = 0):
        self.velocity = (xVel, yVel, zVel)

    def applyTo(self, obj, sim):
        obj.setVelocity(self.velocity)


class SetSpeedAction(Action):
    """Set the speed of an agent (keeping its heading fixed)."""

    def __init__(self, speed: float):
        self.speed = speed

    def applyTo(self, obj, sim):
        vel = Vector(0, self.speed).rotatedBy(obj.heading)
        obj.setVelocity(vel)


## Actions available to vehicles which can steer


class SteeringAction(Action):
    """Abstract class for actions usable by agents which can steer.

    Such agents must implement the `Steers` protocol.
    """

    def canBeTakenBy(self, agent):
        return isinstance(agent, Steers)


class SetThrottleAction(SteeringAction):
    """Set the throttle.

    The throttle setting will remain constant until this action is taken again.

    Arguments:
        throttle: Throttle value between 0 and 1.
    """

    def __init__(self, throttle: float):
        if not 0.0 <= throttle <= 1.0:
            raise RuntimeError("Throttle must be a float in range [0.0, 1.0].")
        self.throttle = throttle

    def applyTo(self, obj, sim):
        obj.setThrottle(self.throttle)


class SetSteerAction(SteeringAction):
    """Set the steering 'angle'.

    The steering setting will remain constant until this action is taken again.

    Arguments:
        steer: Steering 'angle' between -1 and 1. Positive values steer to the right.
    """

    def __init__(self, steer: float):
        if not -1.0 <= steer <= 1.0:
            raise RuntimeError("Steer must be a float in range [-1.0, 1.0].")
        self.steer = steer

    def applyTo(self, obj, sim):
        obj.setSteering(self.steer)


class SetBrakeAction(SteeringAction):
    """Set the amount of brake.

    The brake setting will remain constant until this action is taken again.

    Arguments:
        brake: Amount of braking between 0 and 1.
    """

    def __init__(self, brake: float):
        if not 0.0 <= brake <= 1.0:
            raise RuntimeError("Brake must be a float in range [0.0, 1.0].")
        self.brake = brake

    def applyTo(self, obj, sim):
        obj.setBraking(self.brake)


class SetHandBrakeAction(SteeringAction):
    """Set or release the hand brake.

    The handbrake setting will remain constant until this action is taken again.

    Arguments:
        handBrake: Whether or not the hand brake is set.
    """

    def __init__(self, handBrake: bool):
        if not isinstance(handBrake, bool):
            raise RuntimeError("Hand brake must be a boolean.")
        self.handbrake = handBrake

    def applyTo(self, obj, sim):
        obj.setHandbrake(self.handbrake)


class SetReverseAction(SteeringAction):
    """Engage or release reverse gear.

    The reverse setting will remain constant until this action is taken again.

    Arguments:
        reverse: Whether or not the car is in reverse.
    """

    def __init__(self, reverse: bool):
        if not isinstance(reverse, bool):
            raise RuntimeError("Reverse must be a boolean.")
        self.reverse = reverse

    def applyTo(self, obj, sim):
        obj.setReverse(self.reverse)


class RegulatedControlAction(SteeringAction):
    """Regulated control of throttle, braking, and steering.

    Controls throttle and braking using one signal that may be positive or negative.
    Useful with simple controllers that output a single value.

    Arguments:
        throttle: Control signal for throttle and braking (will be clamped as below).
        steer: Control signal for steering (also clamped).
        past_steer: Previous steering signal, for regulating abrupt changes.
        max_throttle: Maximum value for **throttle**, when positive.
        max_brake: Maximum (absolute) value for **throttle**, when negative.
        max_steer: Maximum absolute value for **steer**.
    """

    def __init__(
        self,
        throttle: float,
        steer: float,
        past_steer: float,
        max_throttle: float = 0.5,
        max_brake: float = 0.5,
        max_steer: float = 0.8,
    ):
        if throttle > 0:
            throttle = min(throttle, max_throttle)
            brake = 0
        else:
            throttle = 0
            brake = min(abs(throttle), max_brake)

        # Steering regulation: changes cannot happen abruptly, can't steer too much.

        if steer > past_steer + 0.1:
            steer = past_steer + 0.1
        elif steer < past_steer - 0.1:
            steer = past_steer - 0.1

        if steer >= 0:
            steer = min(max_steer, steer)
        else:
            steer = max(-max_steer, steer)

        self.throttle, self.brake, self.steer = throttle, brake, steer

    def applyTo(self, obj, sim):
        obj.setThrottle(self.throttle)
        obj.setBraking(self.brake)
        obj.setSteering(self.steer)


## Actions available to agents that travel by direction and speed


class TravelAction(Action):
    """Abstract class for actions usable by agents which can travel.

    Such agents must implement the `Travels` protocol.
    """

    def canBeTakenBy(self, agent):
        return isinstance(agent, Travels)


class SetTravelDirectionAction(TravelAction):
    """Set the travel direction."""

    def __init__(self, heading):
        self.heading = heading

    def applyTo(self, obj, sim):
        obj.setTravelDirection(self.heading)


class SetTravelSpeedAction(TravelAction):
    """Set the travel speed."""

    def __init__(self, speed):
        self.speed = speed

    def applyTo(self, obj, sim):
        obj.setTravelSpeed(self.speed)


## Actions available to agents that can walk


class WalkingAction(Action):
    """Abstract class for actions usable by agents which can walk.

    Such agents must implement the `Walks` protocol.
    """

    def canBeTakenBy(self, agent):
        return isinstance(agent, Walks)


class SetWalkingDirectionAction(WalkingAction):
    """Set the walking direction."""

    def __init__(self, heading):
        self.heading = heading

    def applyTo(self, obj, sim):
        obj.setTravelDirection(self.heading)


class SetWalkingSpeedAction(WalkingAction):
    """Set the walking speed."""

    def __init__(self, speed):
        self.speed = speed

    def applyTo(self, obj, sim):
        obj.setTravelSpeed(self.speed)
