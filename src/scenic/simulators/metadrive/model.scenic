"""Scenic world model for traffic scenarios in MetaDrive.

The model currently supports vehicles and pedestrians. It implements the
basic :obj:`~scenic.domains.driving.model.Car` and `Pedestrian` classes from the :obj:`scenic.domains.driving` domain. 'Bicycle' is implemented as a subclass of 'Pedestrian'.
Vehicles and pedestrians support the basic actions and behaviors from the driving domain.

The model defines several global parameters, whose default values can be overridden
in scenarios using the ``param`` statement or on the command line using the
:option:`--param` option:

Global Parameters:
    sumo_map (str or Path): Path to the SUMO map (``.net.xml`` file) to use in the simulation.
        This map should correspond to the **map** file used in the scenario. See the documentation in
        :doc:`scenic.domains.driving.model` for details.
    timestep (float): The interval (in seconds) between each simulation step. This determines how often Scenic
        interrupts MetaDrive to run behaviors, check requirements, and update the simulation state.
        The default value is 0.1 seconds.
    render (bool): Whether to render the simulation screen. If True (default), it will open a screen and render
        the simulation. If False, rendering is disabled.
    render3D (bool): Whether to render the simulation in 3D. If True, it will render the simulation in 3D.
        If False (default), it will render in 2D.
    real_time (bool): If True (default), the simulation will run in real time, ensuring each step takes at least
        as long as the specified timestep. If False, the simulation runs as fast as possible.
    screen_record (bool): Whether to record a screen capture of the simulation (as a GIF).
        Only supported in 2D rendering mode (requires ``render=True`` and ``render3D=False``).
        Default is False.
    screen_record_filename (str or None): Name of the GIF file to save. If not specified (default),
        a timestamp will be used for each scenario recording.
    screen_record_path (str): Directory where the GIFs will be saved. Defaults to "metadrive_gifs".
        If not customized, recordings are grouped into this folder using timestamps for filenames.
"""
import pathlib

from scenic.domains.driving.model import *
from scenic.domains.driving.actions import *
from scenic.domains.driving.behaviors import *

from scenic.core.errors import InvalidScenarioError

# Sensor imports
from scenic.simulators.metadrive.sensors import MetaDriveRGBSensor as RGBSensor
from scenic.simulators.metadrive.sensors import MetaDriveSSSensor as SSSensor


try:
    from scenic.simulators.metadrive.simulator import MetaDriveSimulator
    from scenic.simulators.metadrive.utils import scenicToMetaDriveHeading, scenicToMetaDrivePosition
except ModuleNotFoundError:
    # for convenience when testing without the metadrive package
    from scenic.core.simulators import SimulatorInterfaceWarning
    import warnings
    warnings.warn('The "metadrive-simulator" package is not installed; '
                  'will not be able to run dynamic simulations',
                  SimulatorInterfaceWarning)

    def MetaDriveSimulator(*args, **kwargs):
        """Dummy simulator to allow compilation without the 'metadrive-simulator' package.

        :meta private:
        """
        raise RuntimeError('the "metadrive-simulator" package is required to run simulations '
                           'from this scenario')

if "sumo_map" not in globalParameters:
    sumo_map_path = str(pathlib.Path(globalParameters.map).with_suffix(".net.xml"))

    if not pathlib.Path(sumo_map_path).exists():
        raise InvalidScenarioError(
            f"Missing SUMO map: Expected '{sumo_map_path}' but the file does not exist.\n"
            "The SUMO map should have the same base name as the 'map' parameter, with the '.net.xml' extension.\n"
            "Ensure that the corresponding '.net.xml' file is located in the same directory as the '.xodr' file."
        )
else:
    sumo_map_path = globalParameters.sumo_map

param sumo_map = sumo_map_path
param timestep = 0.1
param render = 1
param render3D = 0
param real_time = 1
param screen_record = 0
param screen_record_filename = None
param screen_record_path = "metadrive_gifs"

if bool(globalParameters.screen_record) and bool(globalParameters.render3D):
    raise InvalidScenarioError(
        "screen_record=True is only supported with 2D rendering. Set render3D=False."
    )

if bool(globalParameters.screen_record) and not bool(globalParameters.render):
    raise InvalidScenarioError(
        "screen_record=True requires render=True. Cannot record when rendering is disabled."
    )

simulator MetaDriveSimulator(
    sumo_map=globalParameters.sumo_map,
    xodr_map=globalParameters.map,
    timestep=float(globalParameters.timestep),
    render=bool(globalParameters.render),
    render3D=bool(globalParameters.render3D),
    real_time=bool(globalParameters.real_time),
    screen_record=bool(globalParameters.screen_record),
    screen_record_filename=globalParameters.screen_record_filename,
    screen_record_path=globalParameters.screen_record_path,
)

class MetaDriveActor(DrivingObject):
    """Abstract class for MetaDrive objects.

    This class serves as a base for objects in the MetaDrive simulator. It provides essential
    functionality for associating Scenic objects with their corresponding MetaDrive simulation objects.

    Properties:
        metaDriveActor: A reference to the MetaDrive actor (e.g., vehicle or pedestrian) associated
                        with this Scenic object. This is set when the object is created in the simulator.
                        It allows interaction with MetaDrive's simulation environment, such as applying actions
                        or retrieving simulation data (position, velocity, etc.).
    """
    metaDriveActor: None

    def setPosition(self, pos, elevation):
        position = scenicToMetaDrivePosition(pos, simulation().scenic_offset)
        self.metaDriveActor.set_position(position)

    def setVelocity(self, vel):
        self.metaDriveActor.set_velocity(vel)


class Vehicle(Vehicle, Steers, MetaDriveActor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._control = {"steer": 0.0, "throttle": 0.0, "brake": 0.0}
        self._reverse = False
        self._handbrake = False

    def setThrottle(self, throttle):
        self._control["throttle"] = throttle

    def setSteering(self, steering):
        self._control["steer"] = steering

    def setBraking(self, braking):
        self._control["brake"] = braking

    def setReverse(self, reverse):
        self._reverse = reverse

    def setHandbrake(self, handbrake):
        self._handbrake = handbrake

    def _prepare_action(self):
        # MetaDrive uses the opposite convention: positive steer turns left
        steer = -self._control["steer"]

        # Handbrake overrides everything: disable reverse, full brake.
        if self._handbrake:
            self.metaDriveActor.enable_reverse = False
            return [steer, -1.0]

        # MetaDrive uses a single combined throttle/brake value
        throttle_brake = self._control["throttle"] - self._control["brake"]

        # Enable reverse only if requested AND there’s forward drive effort.
        enable_reverse = self._reverse and (throttle_brake > 0.0)
        self.metaDriveActor.enable_reverse = enable_reverse
        if enable_reverse:
            throttle_brake = -throttle_brake  # negative drives backward
        return [steer, throttle_brake]


class Car(Vehicle):
    @property
    def isCar(self):
        return True

class Pedestrian(Pedestrian, MetaDriveActor, Walks):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._walking_direction = None
        self._walking_speed = None

    @property
    def isPedestrian(self):
        return True

    @property
    def isBicycle(self):
        return False

    def setWalkingDirection(self, heading):
        self._walking_direction = scenicToMetaDriveHeading(heading)

    def setWalkingSpeed(self, speed):
        self._walking_speed = speed


class Bicycle(Pedestrian):
    @property
    def isBicycle(self):
        return True