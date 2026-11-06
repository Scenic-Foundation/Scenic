"""Simulator interface for MetaDrive."""

try:
    import metadrive
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "Metadrive is required. Please install the 'metadrive-simulator' package (and sumolib) or use scenic[metadrive]."
    ) from e

from datetime import datetime
import logging
import os
import sys
import time

from metadrive.component.sensors.rgb_camera import RGBCamera
from metadrive.component.sensors.semantic_camera import SemanticCamera
from metadrive.component.traffic_participants.pedestrian import Pedestrian
from metadrive.component.vehicle.vehicle_type import DefaultVehicle

from scenic.core.simulators import InvalidScenarioError, SimulationCreationError
from scenic.domains.driving.actions import *
from scenic.domains.driving.controllers import (
    PIDLateralController,
    PIDLongitudinalController,
)
from scenic.domains.driving.simulators import DrivingSimulation, DrivingSimulator
from scenic.simulators.metadrive.sensors import MetaDriveRGBSensor, MetaDriveSSSensor
import scenic.simulators.metadrive.utils as utils


class MetaDriveSimulator(DrivingSimulator):
    """Implementation of `Simulator` for MetaDrive."""

    def __init__(
        self,
        sumo_map,
        xodr_map,
        timestep=0.1,
        render=True,
        render3D=False,
        real_time=None,
        screen_record=False,
        screen_record_filename=None,
        screen_record_path="metadrive_gifs",
    ):
        super().__init__()
        self.render = render
        self.render3D = render3D if render else False
        self.scenario_number = 0
        self.timestep = timestep
        self.sumo_map = sumo_map
        self.xodr_map = xodr_map
        if real_time is None:
            self.real_time = self.render or self.render3D
        else:
            self.real_time = real_time
        self.screen_record = screen_record
        self.screen_record_filename = screen_record_filename
        self.screen_record_path = screen_record_path
        self.scenic_offset, self.sumo_map_boundary = utils.getMapParameters(
            self.sumo_map, self.xodr_map
        )

        if self.screen_record and self.render3D:
            raise SimulationCreationError(
                "screen_record=True requires 2D rendering: set render3D=False."
            )

        if self.screen_record and not self.render:
            raise SimulationCreationError(
                "screen_record=True requires rendering to be enabled: set render=True."
            )

        if self.render and not self.render3D:
            self.film_size = utils.calculateFilmSize(self.sumo_map_boundary, scaling=5)
        else:
            self.film_size = None

    def createSimulation(self, scene, *, timestep, **kwargs):
        self.scenario_number += 1
        return MetaDriveSimulation(
            scene,
            render=self.render,
            render3D=self.render3D,
            scenario_number=self.scenario_number,
            timestep=self.timestep,
            sumo_map=self.sumo_map,
            real_time=self.real_time,
            screen_record=self.screen_record,
            screen_record_filename=self.screen_record_filename,
            screen_record_path=self.screen_record_path,
            scenic_offset=self.scenic_offset,
            sumo_map_boundary=self.sumo_map_boundary,
            film_size=self.film_size,
            **kwargs,
        )


class MetaDriveSimulation(DrivingSimulation):
    def __init__(
        self,
        scene,
        render,
        render3D,
        scenario_number,
        timestep,
        sumo_map,
        real_time,
        screen_record,
        screen_record_filename,
        screen_record_path,
        scenic_offset,
        sumo_map_boundary,
        film_size,
        **kwargs,
    ):
        if len(scene.objects) == 0:
            raise InvalidScenarioError(
                "Metadrive requires you to define at least one Scenic object."
            )
        if not scene.objects[0].isCar:
            raise InvalidScenarioError(
                "The first object must be a car to serve as the ego vehicle in Metadrive."
            )

        self.render = render
        self.render3D = render3D
        self.scenario_number = scenario_number
        self.defined_ego = False
        self.client = None
        self.timestep = timestep
        self.sumo_map = sumo_map
        self.real_time = real_time
        self.screen_record = screen_record
        self.screen_record_filename = screen_record_filename
        self.screen_record_path = screen_record_path
        self.scenic_offset = scenic_offset
        self.sumo_map_boundary = sumo_map_boundary
        self.film_size = film_size
        super().__init__(scene, timestep=timestep, **kwargs)

    # --- sensor helpers ---
    def _metadrive_sensor_name(self, obj, base_name: str) -> str:
        """Return a unique MetaDrive sensor name by appending the object's index."""
        idx = self.scene.objects.index(obj)
        return f"{base_name}__obj{idx}"

    def _attach_sensors(self, obj):
        """Attach/track all sensors for this object in MetaDrive."""
        if not obj.sensors:
            return
        for base_name, sensor in obj.sensors.items():
            md_name = self._metadrive_sensor_name(obj, base_name)
            md_sensor = self.client.engine.get_sensor(md_name)
            if md_sensor is None:
                raise RuntimeError(
                    f"Metadrive sensor '{md_name}' not found; check setup naming."
                )
            offset = (
                sensor.offset if sensor.offset is not None else obj.visionSensorOffset
            )
            md_sensor.track(obj.metaDriveActor.origin, offset, sensor.rotation)
            sensor.metadrive_sensor = md_sensor

    def setup(self):
        self.drive_env_config = {}

        for obj in self.scene.objects:
            if obj.sensors:
                for base_name, sensor in obj.sensors.items():
                    md_name = self._metadrive_sensor_name(obj, base_name)
                    if isinstance(sensor, MetaDriveRGBSensor):
                        self.drive_env_config[md_name] = [
                            RGBCamera,
                            sensor.width,
                            sensor.height,
                        ]
                    elif isinstance(sensor, MetaDriveSSSensor):
                        self.drive_env_config[md_name] = [
                            SemanticCamera,
                            sensor.width,
                            sensor.height,
                        ]
                    else:
                        raise RuntimeError(f"Unknown sensor type: {type(sensor)}")

        self.using_sensors = bool(self.drive_env_config)
        super().setup()

    def createObjectInSimulator(self, obj):
        """
        Create an object in the MetaDrive simulator.

        If it's the first object, it initializes the client and sets it up for the ego car.
        For additional cars and pedestrians, it spawns objects using the provided position and heading.
        """
        converted_position = utils.scenicToMetaDrivePosition(
            obj.position, self.scenic_offset
        )
        converted_heading = utils.scenicToMetaDriveHeading(obj.heading)

        vehicle_config = {}
        if obj.isVehicle:
            vehicle_config["spawn_position_heading"] = [
                converted_position,
                converted_heading,
            ]
            vehicle_config["spawn_velocity"] = [obj.velocity.x, obj.velocity.y]

        if not self.defined_ego:
            decision_repeat = math.ceil(self.timestep / 0.02)
            physics_world_step_size = self.timestep / decision_repeat

            # Initialize the simulator with ego vehicle
            self.client = utils.DriveEnv(
                dict(
                    decision_repeat=decision_repeat,
                    physics_world_step_size=physics_world_step_size,
                    use_render=self.render3D,
                    vehicle_config=vehicle_config,
                    use_mesh_terrain=False,
                    height_scale=0.0001,
                    log_level=logging.CRITICAL,
                    image_observation=self.using_sensors,
                    sensors=self.drive_env_config,
                )
            )
            self.client.config["sumo_map"] = self.sumo_map
            self.client.reset()

            # Assign the MetaDrive actor to the ego
            metadrive_objects = self.client.engine.get_objects()
            obj.metaDriveActor = list(metadrive_objects.values())[0]
            self.defined_ego = True

            # Attach sensors (if any)
            self._attach_sensors(obj)
            return

        # For additional cars
        if obj.isVehicle:
            metaDriveActor = self.client.engine.agent_manager.spawn_object(
                DefaultVehicle,
                vehicle_config=vehicle_config,
            )
            obj.metaDriveActor = metaDriveActor

            # Attach sensors (if any)
            self._attach_sensors(obj)
            return

        # For pedestrians
        if obj.isPedestrian:
            metaDriveActor = self.client.engine.agent_manager.spawn_object(
                Pedestrian,
                position=converted_position,
                heading_theta=converted_heading,
            )
            obj.metaDriveActor = metaDriveActor

            # Attach sensors (if any)
            self._attach_sensors(obj)

            # Manually initialize pedestrian velocity to Scenic’s starting speed
            direction = [math.cos(converted_heading), math.sin(converted_heading)]
            metaDriveActor.set_velocity(direction, obj.speed)
            return

        # If the object type is unsupported, raise an error
        raise SimulationCreationError(
            f"Unsupported object type: {type(obj)} for object {obj}."
        )

    def executeActions(self, allActions):
        """Execute actions for all vehicles in the simulation."""
        super().executeActions(allActions)

        # Apply control updates to vehicles and pedestrians
        for obj in self.agents:
            if obj is self.objects[0]:  # Skip ego vehicle (it is handled separately)
                continue
            if obj.isVehicle:
                action = obj._prepare_action()
                obj.metaDriveActor.before_step(action)
            else:
                # For Pedestrians
                if obj._walking_direction is None:
                    obj._walking_direction = utils.scenicToMetaDriveHeading(obj.heading)
                if obj._walking_speed is None:
                    obj._walking_speed = obj.speed
                direction = [
                    math.cos(obj._walking_direction),
                    math.sin(obj._walking_direction),
                ]
                obj.metaDriveActor.set_velocity(direction, obj._walking_speed)

    def step(self):
        start_time = time.monotonic()

        # Special handling for the ego vehicle
        ego_obj = self.objects[0]
        action = ego_obj._prepare_action()
        self.client.step(action)

        # Render the scene in 2D if needed
        if self.render and not self.render3D:
            self.client.render(
                mode="topdown",
                semantic_map=True,
                film_size=self.film_size,
                scaling=5,
                screen_record=self.screen_record,
            )

        # If real-time synchronization is enabled, sleep to maintain real-time pace
        if self.real_time:
            end_time = time.monotonic()
            elapsed_time = end_time - start_time
            if elapsed_time < self.timestep:
                time.sleep(self.timestep - elapsed_time)

    def destroy(self):
        if self.screen_record:
            filename = self.screen_record_filename or datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            if not filename.endswith(".gif"):
                filename += ".gif"
            path = os.path.join(self.screen_record_path, filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)

            # Convert timestep (seconds) → milliseconds for GIF duration
            duration_ms = int(round(self.timestep * 1000))

            print(f"Saving screen recording to {path}")
            self.client.top_down_renderer.generate_gif(path, duration=duration_ms)

        if self.client and self.client.engine:
            object_ids = list(self.client.engine._spawned_objects.keys())
            if object_ids:
                self.client.engine.agent_manager.clear_objects(object_ids)
            self.client.close()

        super().destroy()

    def getProperties(self, obj, properties):
        metaDriveActor = obj.metaDriveActor
        position = utils.metadriveToScenicPosition(
            metaDriveActor.position, self.scenic_offset
        )
        velocity = Vector(*metaDriveActor.velocity, 0)
        speed = metaDriveActor.speed
        md_ang_vel = metaDriveActor.body.getAngularVelocity()
        angularVelocity = Vector(*md_ang_vel)
        angularSpeed = math.hypot(*md_ang_vel)
        converted_heading = utils.metaDriveToScenicHeading(metaDriveActor.heading_theta)
        yaw, pitch, roll = obj.parentOrientation.globalToLocalAngles(
            converted_heading, 0, 0
        )
        elevation = 0

        values = dict(
            position=position,
            velocity=velocity,
            speed=speed,
            angularSpeed=angularSpeed,
            angularVelocity=angularVelocity,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            elevation=elevation,
        )

        return values

    def getLaneFollowingControllers(self, agent):
        dt = self.timestep
        if agent.isCar:
            lon_controller = PIDLongitudinalController(K_P=0.5, K_D=0.1, K_I=0.7, dt=dt)
            lat_controller = PIDLateralController(K_P=0.13, K_D=0.3, K_I=0.05, dt=dt)
        else:
            lon_controller = PIDLongitudinalController(
                K_P=0.25, K_D=0.025, K_I=0.0, dt=dt
            )
            lat_controller = PIDLateralController(K_P=0.2, K_D=0.1, K_I=0.0, dt=dt)
        return lon_controller, lat_controller

    def getTurningControllers(self, agent):
        dt = self.timestep
        if agent.isCar:
            lon_controller = PIDLongitudinalController(K_P=0.5, K_D=0.1, K_I=0.7, dt=dt)
            lat_controller = PIDLateralController(K_P=0.2, K_D=0.2, K_I=0.2, dt=dt)
        else:
            lon_controller = PIDLongitudinalController(
                K_P=0.25, K_D=0.025, K_I=0.0, dt=dt
            )
            lat_controller = PIDLateralController(K_P=0.4, K_D=0.1, K_I=0.0, dt=dt)
        return lon_controller, lat_controller

    def getLaneChangingControllers(self, agent):
        dt = self.timestep
        if agent.isCar:
            lon_controller = PIDLongitudinalController(K_P=0.5, K_D=0.1, K_I=0.7, dt=dt)
            lat_controller = PIDLateralController(K_P=0.2, K_D=0.2, K_I=0.02, dt=dt)
        else:
            lon_controller = PIDLongitudinalController(
                K_P=0.25, K_D=0.025, K_I=0.0, dt=dt
            )
            lat_controller = PIDLateralController(K_P=0.1, K_D=0.3, K_I=0.0, dt=dt)
        return lon_controller, lat_controller
