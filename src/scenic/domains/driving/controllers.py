"""Low-level controllers useful for vehicles.

The Lateral/Longitudinal PID controllers are adapted from `CARLA`_'s PID controllers,
which are licensed under the following terms:

    Copyright (c) 2018-2020 CVC.

    This work is licensed under the terms of the MIT license.
    For a copy, see <https://opensource.org/licenses/MIT>.


.. _CARLA: https://carla.org/
"""

from abc import ABC, abstractmethod
from collections import deque
import math

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint, Point as ShapelyPoint

from scenic.core.regions import CircularRegion, PolylineRegion, toPolygon
from scenic.core.vectors import Vector


class LongitudinalController(ABC):
    @abstractmethod
    def computeThrottle(self, trajectory, veh):
        pass


class LateralController(ABC):
    @abstractmethod
    def computeSteering(self, trajectory, veh):
        pass


class PIDController:
    def __init__(self, dt, *, K_P, K_D, K_I, wg):
        super().__init__()
        self.dt = dt
        self.kp = K_P
        self.ki = K_I
        self.kd = K_D
        self.i_term = 0
        self.last_error = None
        self.windup_guard = 0.5 / self.ki if self.ki != 0 else 0

    def run_step(self, error):
        # Compute terms
        p_term = error
        self.i_term += error * self.dt
        self.i_term = np.clip(self.i_term, -self.windup_guard, self.windup_guard)
        d_term = (error - self.last_error) / self.dt if self.last_error else 0

        # Remember last error for next calculation
        self.last_error = error

        output = (self.kp * p_term) + (self.ki * self.i_term) + (self.kd * d_term)
        clipped_output = np.clip(output, -1, 1)
        return clipped_output


class PIDLongitudinalController(PIDController, LongitudinalController):
    """Longitudinal control using a PID to reach a target speed.

    Arguments:
        dt: time step
        K_P: Proportional gain
        K_D: Derivative gain
        K_I: Integral gain
        wg: The windup guard's cap on the integral components contribution
            to the total control signal.
    """

    def __init__(self, dt=0.1, *, K_P=0.5, K_D=0.1, K_I=0.2, wg=0.5):
        super().__init__(dt=dt, K_P=K_P, K_D=K_D, K_I=K_I, wg=wg)

    def computeThrottle(self, trajectory, veh):
        curr_time = trajectory.getRelativeTime(veh.position)
        ts_dist = trajectory.getTimedDistance(curr_time, curr_time + trajectory.ts)
        target_speed = ts_dist / trajectory.ts

        cte = target_speed - veh.speed
        return self.run_step(cte)


class PIDLateralController(PIDController, LateralController):
    """Lateral control using a PID to track a trajectory.

    Arguments:
        dt: time step
        K_P: Proportional gain
        K_D: Derivative gain
        K_I: Integral gain
        wg: The windup guard's cap on the integral components contribution
            to the total control signal.
    """

    def __init__(self, dt=0.1, *, K_P=0.3, K_D=0.2, K_I=0, wg=0):
        super().__init__(dt=dt, K_P=K_P, K_D=K_D, K_I=K_I, wg=wg)

    def computeSteering(self, trajectory, veh):
        cte = trajectory.polyline.signedDistanceTo(veh.position)
        steer_angle = self.run_step(cte)
        return steer_angle


class PurePursuitLateralController(LateralController):
    def __init__(self, lookaheadDistance=lambda veh: veh.speed + 1):
        super().__init__()
        self.lookaheadDistance = lookaheadDistance
        self._lastTargetPoint = None

    def _findTargetPoint(self, trajectory, veh, lookaheadDistance):
        traj_line_string = toPolygon(trajectory.polyline)

        # Find candidate target points
        veh_pt = ShapelyPoint(*veh.position)
        veh_traj_dist = traj_line_string.project(veh_pt)
        forward_traj = shapely.ops.substring(
            traj_line_string, veh_traj_dist, traj_line_string.length
        )
        lookahead_circle = toPolygon(
            CircularRegion(forward_traj.coords[0], lookaheadDistance)
        )
        intersection_geometry = lookahead_circle.boundary.intersection(forward_traj)

        if intersection_geometry.is_empty:
            # No viable target points. If we have a last target point, aim for that. Otherwise,
            # aim for the closest point on the trajectory.
            if self._lastTargetPoint:
                target_point = self._lastTargetPoint
            else:
                target_point = trajectory.polyline.project(veh.position)

            # Our target point isn't actually at the correct lookaheadDistance, so we need to update it.
            lookaheadDistance = shapely.distance(veh_pt, target_point)
        elif isinstance(intersection_geometry, ShapelyPoint):
            target_point = intersection_geometry
        elif isinstance(intersection_geometry, MultiPoint):
            # There are multiple candidate target points. Pick the one that appears first on the path.
            target_point = sorted(
                intersection_geometry.geoms, key=lambda pt: traj_line_string.project(pt)
            )[0]
        else:
            # We've gotten something strange. Fall back to a representative point as the target.
            target_point = intersection_geometry.representative_point()

        # Store last target point and return
        self._lastTargetPoint = target_point
        return Vector(target_point.x, target_point.y)

    def computeSteering(self, trajectory, veh):
        # Compute target steering angle
        lookaheadDistance = self.lookaheadDistance(veh)
        targetPoint = self._findTargetPoint(trajectory, veh, lookaheadDistance)
        rw_position = veh.position.offsetRotated(
            veh.heading, Vector(0, -0.5 * veh.wheelbase, 0)
        )
        alpha = rw_position.angleTo(targetPoint) - veh.heading
        delta = -math.atan2(2 * veh.wheelbase * math.sin(alpha), lookaheadDistance)

        # Convert target steering angle to relative value in [-1, 1]
        rel_steering_angle = np.clip(delta / veh.maxSteeringAngle, -1, 1)

        return rel_steering_angle
