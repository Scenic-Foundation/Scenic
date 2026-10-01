"""Library of useful behaviors for dynamic agents in driving scenarios.

These behaviors are automatically imported when using the driving domain.
"""

import math
from abc import ABC, abstractmethod
import warnings

import shapely
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, MultiLineString, LineString, MultiPoint, Point as ShapelyPoint

from scenic.core.regions import toShapely
from scenic.core.type_support import toVector
from scenic.domains.driving.actions import *
import scenic.domains.driving.model as _model
from scenic.domains.driving.roads import ManeuverType, Lane

behavior ConstantThrottleBehavior(x):
    while True:
        take SetThrottleAction(x), SetReverseAction(False), SetHandBrakeAction(False)

behavior DriveAvoidingCollisions(target_speed=25, avoidance_threshold=10):
    try:
        do FollowLaneBehavior(target_speed=target_speed)
    interrupt when self.distanceToClosest(_model.Vehicle) <= avoidance_threshold:
        take SetThrottleAction(0), SetBrakeAction(1)

behavior AccelerateForwardBehavior():
    take SetReverseAction(False), SetHandBrakeAction(False), SetThrottleAction(0.5)

behavior ConstantThrottleBehavior(x):
    take SetThrottleAction(x)

def getFollowLanePath(obj, minPathDistance, preferStraight, laneToFollow=None, path_metadata=None):
    import shapely
    import itertools

    if laneToFollow is None:
        laneToFollow = obj.lane
    elif not isinstance(laneToFollow, Lane):
        raise ValueError("`laneToFollow` is not a `Lane`.")

    if path_metadata is None:
        current_lane = laneToFollow
        initial_path = current_lane.centerline.lineString
    else:
        current_lane = path_metadata[0]
        initial_path = path_metadata[1]
    
    assert isinstance(initial_path, shapely.geometry.LineString)
    initial_path = shapely.remove_repeated_points(initial_path)

    def mergeLineStrings(geoms):
        return shapely.geometry.LineString(itertools.chain.from_iterable(geom.coords for geom in geoms))

    ego_pt = shapely.geometry.Point(*obj.position)
    path = shapely.ops.substring(initial_path, initial_path.project(ego_pt), initial_path.length)

    while path.length < minPathDistance:
        straight_manuevers = [m for m in current_lane.maneuvers if m.type == ManeuverType.STRAIGHT]

        if preferStraight and straight_manuevers:
            target_maneuver = Uniform(*straight_manuevers)
        else:
            if len(current_lane.maneuvers) > 0:
                target_maneuver = Uniform(*current_lane.maneuvers)
            else:
                # No more maneuvers. Raise a warning and return centerline as is
                warnings.warn("Could not generate path of desired distance. Returning path as is.")
                break

        if target_maneuver.connectingLane != None:
            path = mergeLineStrings([path, target_maneuver.connectingLane.centerline.lineString, target_maneuver.endLane.centerline.lineString])
        else:
            path = mergeLineStrings([path, target_maneuver.endLane.centerline.lineString])

        current_lane = target_maneuver.endLane

    assert isinstance(path, shapely.geometry.LineString)
    return PolylineRegion(polyline=path), (current_lane, path)

behavior FollowLaneBehavior(target_speed=10, laneToFollow=None, preferStraight=True):
    """
    Follows the lane on which the vehicle is at, unless the laneToFollow is specified.
    Once the vehicle reaches an intersection, by default, the vehicle will take the straight route.
    If straight route is not available, then any availble turn route will be taken, uniformly randomly.
    If turning at the intersection, the vehicle will slow down to make the turn, safely.

    This behavior does not terminate. A recommended use of the behavior is to accompany it with condition,
    e.g. do FollowLaneBehavior() until ...

    :param target_speed: Its unit is in m/s. By default, it is set to 10 m/s
    :param laneToFollow: If the lane to follow is different from the lane that the vehicle is on, this 
        parameter can be used to specify that lane. By default, this variable will be set to None, which
        means that the vehicle will follow the lane that it is currently on.
    """
    
    assert self.longitudinalController is not None
    assert self.lateralController is not None

    path_metadata = None

    while True:
        replan_time = 10
        min_path_distance = max(2*replan_time*target_speed, 50)
        path, path_metadata = getFollowLanePath(self, min_path_distance, 
            preferStraight=preferStraight, laneToFollow=laneToFollow, path_metadata=path_metadata)
        traj = Trajectory.createFixedSpeedTrajectory(path, target_speed, ts=simulation().timestep)
        do FollowTrajectoryBehavior(traj) for replan_time seconds

class Trajectory(object):
    def __init__(self, polyline, ts):
        assert isinstance(polyline, PolylineRegion)

        self.polyline = polyline
        self.ts = ts

    @property
    def start(self):
        return self.polyline.start

    @property
    def end(self):
        return self.polyline.end

    @property
    def duration(self):
        return self.ts * len(self.polyline.points)

    @property
    def length(self):
        return self.polyline.length

    def getRelativeTime(self, pos):
        return toShapely(self.polyline).project(ShapelyPoint(*pos), normalized=True)*self.duration

    def getTimedDistance(self, timeA, timeB):
        return shapely.ops.substring(toShapely(self.polyline), timeA/self.duration, timeB/self.duration, normalized=True).length

    def __getitem__(self, time):
        pt = toShapely(self.polyline).interpolate(time/self.duration, normalized=True)
        return Vector(pt.x, pt.y)

    @staticmethod
    def createFixedSpeedTrajectory(polyline, targetSpeed, ts):
        target_dist = 0
        points = []
        while target_dist < polyline.length:
            points.append(polyline.lineString.interpolate(target_dist))
            target_dist += targetSpeed*ts

        return Trajectory(PolylineRegion(polyline=LineString(points)), ts=ts)

behavior FollowTrajectoryBehavior(trajectory, terminationDistance=1):
    """
    Follows the given Trajectory.
    
    The behavior terminates when either of the following conditions are met the vehicle position is within
        terminationDistance of the end of the trajectory.

    Args:
        trajectory: A Trajectory.
        terminationDistance: The behavior will terminate when the vehicle position is within terminationDistance
            of the end of the trajectory.
    """
    assert isinstance(trajectory, Trajectory)
    assert self.longitudinalController is not None
    assert self.lateralController is not None

    while distance from self.position to trajectory.end > terminationDistance:
        # Compute throttle : Longitudinal Control
        throttle = self.longitudinalController.computeThrottle(trajectory, self)
        if throttle > 0:
            throttle_action = SetThrottleAction(throttle)
        else:
            throttle_action = SetBrakeAction(-throttle)

        # Compute steering : Lateral Control
        steer = self.lateralController.computeSteering(trajectory, self)
        steer_action = SetSteerAction(steer)

        take throttle_action, steer_action

## Legacy Behaviors ##

def concatenateCenterlines(centerlines=[]):
    return PolylineRegion.unionAll(centerlines)

behavior FollowTrajectoryBehaviorOld(target_speed = 10, trajectory = None, turn_speed=None):
    """
    Follows the given trajectory. The behavior terminates once the end of the trajectory is reached.

    :param target_speed: Its unit is in m/s. By default, it is set to 10 m/s
    :param trajectory: It is a list of sequential lanes to track, from the lane that the vehicle is initially on to the lane it should end up on.
    """

    assert trajectory is not None
    assert isinstance(trajectory, list)
    if turn_speed is None:
        turn_speed = target_speed / 2

    brakeIntensity = 1.0
    distanceToEndpoint = 5 # meters

    traj_centerline = [traj.centerline for traj in trajectory]
    trajectory_centerline = concatenateCenterlines(traj_centerline)

    # instantiate longitudinal and lateral controllers
    _lon_controller,_lat_controller = simulation().getLaneFollowingControllers(self)
    past_steer_angle = 0

    if trajectory[-1].maneuvers:
        end_intersection = trajectory[-1].maneuvers[0].intersection
        if end_intersection == None:
            end_intersection = trajectory[-1].centerline[-1]
    else:
        end_intersection = trajectory[-1].centerline[-1]

    while True:
        if self in _model.network.intersectionRegion:
            do TurnBehavior(trajectory_centerline, target_speed=turn_speed)

        if (distance from self to end_intersection) < distanceToEndpoint:
            break

        if self.speed is not None:
            current_speed = self.speed
        else:
            current_speed = 0

        cte = trajectory_centerline.signedDistanceTo(self.position)
        speed_error = target_speed - current_speed

        # compute throttle : Longitudinal Control
        throttle = _lon_controller.run_step(speed_error)

        # compute steering : Latitudinal Control
        current_steer_angle = _lat_controller.run_step(cte)

        take RegulatedControlAction(throttle, current_steer_angle, past_steer_angle)
        past_steer_angle = current_steer_angle

behavior TurnBehavior(trajectory, target_speed=6, controllers=None):
    """
    This behavior uses a controller specifically tuned for turning at an intersection.
    This behavior is only operational within an intersection,
    it will terminate if the vehicle is outside of an intersection.
    """

    if isinstance(trajectory, PolylineRegion):
        trajectory_centerline = trajectory
    else:
        trajectory_centerline = concatenateCenterlines([traj.centerline for traj in trajectory])

    # instantiate longitudinal and lateral controllers
    if controllers:
        _lon_controller, _lat_controller = controllers
    else:
        _lon_controller, _lat_controller = simulation().getTurningControllers(self)

    past_steer_angle = 0

    while self in _model.network.intersectionRegion:
        if self.speed is not None:
            current_speed = self.speed
        else:
            current_speed = 0

        cte = trajectory_centerline.signedDistanceTo(self.position)
        speed_error = target_speed - current_speed

        # compute throttle : Longitudinal Control
        throttle = _lon_controller.run_step(speed_error)

        # compute steering : Latitudinal Control
        current_steer_angle = _lat_controller.run_step(cte)

        take RegulatedControlAction(throttle, current_steer_angle, past_steer_angle)
        past_steer_angle = current_steer_angle


behavior LaneChangeBehavior(laneSectionToSwitch, is_oppositeTraffic=False, target_speed=10):

    """
    is_oppositeTraffic should be specified as True only if the laneSectionToSwitch to has
    the opposite traffic direction to the initial lane from which the vehicle started LaneChangeBehavior
    e.g. refer to the use of this flag in examples/carla/Carla_Challenge/carlaChallenge6.scenic
    """

    brakeIntensity = 1.0
    distanceToEndpoint = 3 # meters

    current_lane = laneSectionToSwitch.lane
    traj_centerline = [current_lane.centerline]
    trajectory_centerline = concatenateCenterlines(traj_centerline)

    if current_lane.maneuvers != ():
        nearby_intersection = current_lane.maneuvers[0].intersection
        if nearby_intersection == None:
            nearby_intersection = current_lane.centerline[-1]
    else:
        nearby_intersection = current_lane.centerline[-1]

    # instantiate longitudinal and lateral controllers
    _lon_controller, _lat_controller = simulation().getLaneChangingControllers(self)

    past_steer_angle = 0

    if not is_oppositeTraffic:
        traj_endpoint = current_lane.centerline[-1]
    else:
        traj_endpoint = current_lane.centerline[0]

    while True:
        if abs(trajectory_centerline.signedDistanceTo(self.position)) < 0.1:
            break
        if (distance from self to nearby_intersection) < distanceToEndpoint:
            straight_manuevers = filter(lambda i: i.type == ManeuverType.STRAIGHT, current_lane.maneuvers)

            if len(straight_manuevers) > 0:
                select_maneuver = Uniform(*straight_manuevers)
            else:
                if len(current_lane.maneuvers) > 0:
                    select_maneuver = Uniform(*current_lane.maneuvers)
                else:
                    take SetBrakeAction(1.0)
                    break

            # assumption: there always will be a maneuver
            if select_maneuver.connectingLane != None:
                trajectory_centerline = concatenateCenterlines([trajectory_centerline, select_maneuver.connectingLane.centerline, \
                    select_maneuver.endLane.centerline])
            else:
                trajectory_centerline = concatenateCenterlines([trajectory_centerline, select_maneuver.endLane.centerline])

            current_lane = select_maneuver.endLane

        if self.speed is not None:
            current_speed = self.speed
        else:
            current_speed = 0

        cte = trajectory_centerline.signedDistanceTo(self.position)
        if is_oppositeTraffic: # [bypass] when crossing over the yellowline to opposite traffic lane
            cte = -cte

        speed_error = target_speed - current_speed

        # compute throttle : Longitudinal Control
        throttle = _lon_controller.run_step(speed_error)

        # compute steering : Latitudinal Control
        current_steer_angle = _lat_controller.run_step(cte)

        take RegulatedControlAction(throttle, current_steer_angle, past_steer_angle)
        past_steer_angle = current_steer_angle
