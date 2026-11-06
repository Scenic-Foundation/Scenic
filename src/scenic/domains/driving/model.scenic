"""Scenic world model for scenarios using the driving domain.

Imports actions and behaviors for dynamic agents from
:doc:`scenic.domains.driving.actions` and :doc:`scenic.domains.driving.behaviors`.

The map file to use for the scenario must be specified before importing this model by
defining the global parameter ``map``. This path is passed to the `Network.fromFile`
function to create a `Network` object representing the road network. Extra options may be
passed to the function by defining the global parameter ``map_options``, which should be
a dictionary of keyword arguments. For example, we could write::

    param map = localPath('mymap.xodr')
    param map_options = { 'tolerance': 0.1 }
    model scenic.domains.driving.model

If you are writing a generic scenario that supports multiple maps, you may leave the
``map`` parameter undefined; then running the scenario will produce an error unless the
user uses the :option:`--param` command-line option to specify the map.

The ``use2DMap`` global parameter determines whether or not maps are generated in 2D. Currently
3D maps are not supported, but are under development. By default, this parameter is `False`
(so that future versions of Scenic will automatically use 3D maps), unless
:ref:`2D compatibility mode` is enabled, in which case the default is `True`. The parameter
can be manually set to `True` to ensure 2D maps are used even if the scenario is not compiled
in 2D compatibility mode.


.. note::

    If you are using a simulator, you may have to also define simulator-specific global
    parameters to tell the simulator which world to load. For example, our LGSVL
    interface uses a parameter ``lgsvl_map`` to specify the name of the Unity scene.
    See the :doc:`documentation <scenic.simulators>` of the simulator interfaces for
    details.
"""

from typing import Optional

from scenic.domains.driving.workspace import DrivingWorkspace
from scenic.domains.driving.roads import (ManeuverType, Network, Road, Lane, LaneSection,
                                          LaneGroup, Intersection, PedestrianCrossing,
                                          NetworkElement)
from scenic.domains.driving.actions import *
from scenic.domains.driving.behaviors import *

from scenic.core.sensors import Sensor
from scenic.core.distributions import RejectionException
from scenic.simulators.utils.colors import Color

## 2D mode flag & checks

def is2DMode():
    from scenic.syntax.veneer import mode2D
    return mode2D

param use2DMap = True if is2DMode() else False

if is2DMode() and not globalParameters.use2DMap:
    raise RuntimeError('in 2D mode, global parameter "use2DMap" must be True')

# Note: The following should be removed when 3D maps are supported
if not globalParameters.use2DMap:
    raise RuntimeError('3D maps not supported at this time.'
        '(to use 2D maps set global parameter "use2DMap" to True)')

## Load map and set up workspace

if 'map' not in globalParameters:
    raise RuntimeError('need to specify map before importing driving model '
                       '(set the global parameter "map")')
param map_options = {}

#: The road network being used for the scenario, as a `Network` object.
network : Network = Network.fromFile(globalParameters.map, **globalParameters.map_options)

workspace = DrivingWorkspace(network)

## Various useful objects and regions

#: The union of all drivable roads, including intersections but not shoulders
#: or parking lanes.
road : Region = network.drivableRegion

#: The union of all curbs.
curb : Region = network.curbRegion

#: The union of all sidewalks.
sidewalk : Region = network.sidewalkRegion

#: The union of all shoulders, including parking lanes.
shoulder : Region = network.shoulderRegion

#: All drivable areas, including both ordinary roads and shoulders.
roadOrShoulder : Region = road.union(shoulder)

#: The union of all intersections.
intersection : Region = network.intersectionRegion

#: A :obj:`VectorField` representing the nominal traffic direction at a given point.
#:
#: Inside intersections or anywhere else where there can be multiple nominal
#: traffic directions, the choice is arbitrary. At such points, the function
#: `Network.nominalDirectionsAt` can be used to get all nominal directions.
roadDirection : VectorField = network.roadDirection

## Standard object types

class DrivingObject:
    """Abstract class for objects in a road network.

    Provides convenience properties for the lane, road, intersection, etc. at the
    object's current position (if any).

    Also defines the ``elevation`` property as a standard way to access the Z
    component of an object's position, since the Scenic built-in property
    ``position`` is only 2D. If ``elevation`` is set to :obj:`None`, the simulator is
    responsible for choosing an appropriate Z coordinate so that the object is
    on the ground, then updating the property. 2D simulators should set the
    property to zero.

    Properties:
        elevation (float or None; dynamic): default ``None`` (see above).
        requireVisible (bool): Default value ``False`` (overriding the default
            from `Object`).
    """

    elevation[dynamic]: None if is2DMode() else float(self.position.z)

    requireVisible: False

    # Semantic category properties

    @property
    def isVehicle(self):
        return False

    @property
    def isPedestrian(self):
        return False

    @property
    def isCar(self):
        return False

    # Convenience properties

    @property
    def lane(self) -> Lane:
        """The `Lane` at the object's current position.

        The simulation is rejected if the object is not in a lane.
        (Use `DrivingObject._lane` to get `None` instead.)
        """
        return network.laneAt(self.position, reject='object is not in a lane')

    @property
    def _lane(self) -> Optional[Lane]:
        """The `Lane` at the object's current position, if any."""
        return network.laneAt(self.position)

    @property
    def laneSection(self) -> LaneSection:
        """The `LaneSection` at the object's current position.

        The simulation is rejected if the object is not in a lane.
        """
        return network.laneSectionAt(self.position, reject='object is not in a lane')

    @property
    def _laneSection(self) -> Optional[LaneSection]:
        """The `LaneSection` at the object's current position, if any."""
        return network.laneSectionAt(self.position)

    @property
    def laneGroup(self) -> LaneGroup:
        """The `LaneGroup` at the object's current position.

        The simulation is rejected if the object is not in a lane.
        """
        return network.laneGroupAt(self.position, reject='object is not in a lane')

    @property
    def _laneGroup(self) -> Optional[LaneGroup]:
        """The `LaneGroup` at the object's current position, if any."""
        return network.laneGroupAt(self.position)

    @property
    def oppositeLaneGroup(self) -> LaneGroup:
        """The `LaneGroup` on the other side of the road from the object.

        The simulation is rejected if the object is not on a two-way road.
        """
        return self.laneGroup.opposite

    @property
    def road(self) -> Road:
        """The `Road` at the object's current position.

        The simulation is rejected if the object is not on a road.
        """
        return network.roadAt(self.position, reject='object is not on a road')

    @property
    def _road(self) -> Optional[Road]:
        """The `Road` at the object's current position, if any."""
        return network.roadAt(self.position)

    @property
    def intersection(self) -> Intersection:
        """The `Intersection` at the object's current position.

        The simulation is rejected if the object is not in an intersection.
        """
        return network.intersectionAt(self.position, reject='object is not in an intersection')

    @property
    def _intersection(self) -> Optional[Intersection]:
        """The `Intersection` at the object's current position, if any."""
        return network.intersectionAt(self.position)

    @property
    def crossing(self) -> PedestrianCrossing:
        """The `PedestrianCrossing` at the object's current position.

        The simulation is rejected if the object is not in a crosswalk.
        """
        return network.crossingAt(self.position, reject='object is not in a crossing')

    @property
    def _crossing(self) -> Optional[PedestrianCrossing]:
        """The `PedestrianCrossing` at the object's current position, if any."""
        return network.crossingAt(self.position)

    @property
    def element(self) -> NetworkElement:
        """The highest-level `NetworkElement` at the object's current position.

        See `Network.elementAt` for the details of how this is determined.
        The simulation is rejected if the object is not in any network element.
        """
        return network.elementAt(self.position, reject='object is not on any network element')

    @property
    def _element(self) -> Optional[NetworkElement]:
        """The highest-level `NetworkElement` at the object's current position, if any."""
        return network.elementAt(self.position)

    # Utility functions

    def distanceToClosest(self, type: type) -> Object:
        """Compute the distance to the closest object of the given type.

        For example, one could write :scenic:`self.distanceToClosest(Car)` in a behavior.
        """
        objects = simulation().objects
        minDist = float('inf')
        for obj in objects:
            if not isinstance(obj, type):
                continue
            d = distance from self to obj
            if 0 < d < minDist:
                minDist = d
        return minDist

    # Simulator interface implemented by subclasses

    def setPosition(self, pos, elevation):
        raise NotImplementedError

    def setVelocity(self, vel):
        raise NotImplementedError

class Vehicle(DrivingObject):
    """Vehicles which drive, such as cars.

    Properties:
        position: The default position is uniformly random over the `road`.
        parentOrientation: The default parentOrientation is aligned with `roadDirection`, plus an offset
            given by **roadDeviation**.
        roadDeviation (float): Relative heading with respect to the road direction at
            the `Vehicle`'s position. Used by the default value for **parentOrientation**.
        regionContainedIn: The default container is :obj:`roadOrShoulder`.
        viewAngle: The default view angle is 90 degrees.
        width: The default width is 2 meters.
        length: The default length is 4.5 meters.
        color (:obj:`Color` or RGB tuple): Color of the vehicle. The default value is a
            distribution derived from car color popularity statistics; see
            :obj:`Color.defaultCarColor`.
        wheelbase: The distance between the front and rear axles of the vehicle. Default value is 0.6
            times the length of the vehicle.
        maxSteeringAngle: The maximum steering angle of the vehicle. The full steering range would be
            two times this value, going from (-maxSteeringAngle, maxSteeringAngle). Default value
            35 degrees.
        wheelDiameter: The diameter of the *entire* wheel (including the tire). Default value is 0.7 meters.
        trackWidth: Distance between the vehicle's wheels when pointed straight ahead. Default value
            is 0.85 times the width of the vehicle.
        groundClearance: The distance between the bottom of the vehicle's chassis and the ground. Default
            value is half the wheel diameter.
        maxSpeed: The maximum rated speed of the vehicle. Default value is 45 meters per second (~100 mph).
            This value is not enforced by Scenic and is provided simply for other tools to reference (e.g.
            exporting to OpenScenarioXML).
        maxAcceleration: The maximum rated acceleration of the vehicle. Default value is 5 meters per second^2.
            This value is not enforced by Scenic and is provided simply for other tools to reference (e.g.
            exporting to OpenScenarioXML).
        maxDeceleration: The maximum rated deceleration of the vehicle. Default value is 10 meters per second^2.
            This value is not enforced by Scenic and is provided simply for other tools to reference (e.g.
            exporting to OpenScenarioXML).
    """
    regionContainedIn: roadOrShoulder
    position: new Point on road
    parentOrientation: (roadDirection at self.position) + self.roadDeviation
    roadDeviation: 0
    viewAngle: 90 deg
    width: 2
    length: 4.5
    color: Color.defaultCarColor()
    wheelbase: 0.6*self.length
    maxSteeringAngle: 35 deg
    wheelDiameter: 0.7
    trackWidth: 0.85*self.width
    groundClearance: 0.5*self.wheelDiameter
    maxSpeed: 45
    maxAcceleration: 5
    maxDeceleration: 10

    @property
    def isVehicle(self):
        return True

class Car(Vehicle):
    """A car."""
    @property
    def isCar(self):
        return True

class NPCCar(Car):
    """Car for which accurate physics is not required."""
    pass

class Pedestrian(DrivingObject):
    """A pedestrian.

    Properties:
        position: The default position is uniformly random over sidewalks and crosswalks.
        parentOrientation: The default parentOrientation has uniformly random yaw.
        viewAngle: The default view angle is 90 degrees.
        width: The default width is 0.75 m.
        length: The default length is 0.75 m.
        color: The default color is turquoise. Pedestrian colors are not necessarily
            used by simulators, but do appear in the debugging diagram.
        mass: Default value is 65 kg.
    """
    regionContainedIn: network.walkableRegion
    position: new Point on network.walkableRegion
    parentOrientation: Range(0, 360) deg
    viewAngle: 90 deg
    width: 0.75
    length: 0.75
    color: [0, 0.5, 1]
    mass: 65

    @property
    def isPedestrian(self):
        return True

## Stub sensor implementations

class SSSensor(Sensor):
    def __init__(self, *args, **kwargs):
        pass

    def getObservation(self):
        raise RuntimeError("This simulator does not support SSSensor")

class RGBSensor(Sensor):
    def __init__(self, *args, **kwargs):
        pass

    def getObservation(self):
        raise RuntimeError("This simulator does not support RGBSensor")

## Utility functions

def withinDistanceToAnyCars(car, thresholdDistance):
    """ returns boolean """
    objects = simulation().objects
    for obj in objects:
        if obj is car or not isinstance(obj, Vehicle):
            continue
        if (distance from car to obj) < thresholdDistance:
            return True
    return False

def withinDistanceToAnyObjs(vehicle, thresholdDistance):
    """ checks whether there exists any obj
    (1) in front of the vehicle, (2) within thresholdDistance """
    objects = simulation().objects
    for obj in objects:
        if not (vehicle can see obj):
            continue
        if (distance from vehicle.position to obj.position) < 0.1:
            # this means obj==vehicle
            pass
        elif (distance from vehicle.position to obj.position) < thresholdDistance:
            return True
    return False

def withinDistanceToAnyPedestrians(vehicle, thresholdDistance):
    """Returns True if any visible pedestrian is within thresholdDistance of the given vehicle."""
    objects = simulation().objects
    for obj in objects:
        if obj is vehicle or not isinstance(obj, Pedestrian):
            continue
        if not (vehicle can see obj):
            continue
        if (distance from obj to front of vehicle) < thresholdDistance:
            return True
    return False

def withinDistanceToObjsInLane(vehicle, thresholdDistance):
    """ checks whether there exists any obj
    (1) in front of the vehicle, (2) on the same lane, (3) within thresholdDistance """
    objects = simulation().objects
    for obj in objects:
        if not (vehicle can see obj):
            continue
        if (distance from vehicle.position to obj.position) < 0.1:
            # this means obj==vehicle
            continue
        inter = network.intersectionAt(vehicle)
        if inter and inter != network.intersectionAt(obj):    # different intersections
            continue
        if not inter and network.laneAt(vehicle) != network.laneAt(obj):    # different lanes
            continue
        if (distance from vehicle to obj) < thresholdDistance:
            return True
    return False
