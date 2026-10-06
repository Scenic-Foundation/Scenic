# standard libs
import asyncio
from cmath import atan, pi, tan
import math
from math import copysign, degrees, radians, sin
import subprocess
import threading
import time

# third party libs
import airsim
import numpy as np
import scipy

# scenic libs
from scenic.core.simulators import (
    Simulation,
    SimulationCreationError,
    Simulator,
    SimulatorInterfaceWarning,
)
from scenic.core.type_support import toVector
from scenic.core.vectors import Orientation, Vector
from scenic.syntax.veneer import verbosePrint

from .utils import (
    airsimToScenicLocation,
    airsimToScenicOrientation,
    airsimToScenicVector,
    scenicToAirsimLocation,
    scenicToAirsimOrientation,
    scenicToAirsimScale,
    scenicToAirsimVector,
)

# Constants
PX4_DRONE = "PX4Drone"

# Wall-clock time allowed for AirSim's asynchronous hover RPC to install its
# controller setpoint.  The simulation remains paused, so this does not advance
# physics or become part of the Scenic trace.
CONTROLLER_STARTUP_TIME = 0.1

# A successful AirSim reset should leave SimpleFlight vehicles stationary.
# Allow a small numerical tolerance, but reject any meaningful residual motion
# before it can enter a Scenic trace.
RESET_LINEAR_SPEED_TOLERANCE = 0.05
RESET_ANGULAR_SPEED_TOLERANCE = 0.05


class AirSimSimulator(Simulator):
    def __init__(self, timestep, idleStoragePos=(0, 0, 0)):
        # start airsim client
        try:
            client = airsim.MultirotorClient()
            client.confirmConnection()
            client.simPause(True)
        except Exception:
            raise RuntimeError("Airsim must be running on before executing scenic")

        # init properties
        self.client = client
        self.idleStoragePos = idleStoragePos
        self.timestep = timestep

        verbosePrint(
            "\n\nAll Asset Names:\n",
            [name for name in self.client.simListAssets()],
            level=2,
        )
        # call super
        super().__init__()

    def createSimulation(self, scene, **kwargs):
        return AirSimSimulation(self, scene, self.client, **kwargs)

    def destroy(self):
        super().destroy()


class AirSimSimulation(Simulation):
    # ------------------- Required Methods -------------------

    def __init__(self, simulator, scene, client, **kwargs):
        # init properties
        self.simulator = simulator
        self.client = client
        self.joinables = []  # used in waitforjoinables
        self.objTrove = []  # objs to delete on simulation complete
        self.objs = {}  # obj name to objrealname dict
        self.drones = {}  # obj name to objrealname dict only for drones
        self.startVelocities = {}  # objrealname to initial Scenic velocity vector
        self.initialDronePoses = {}
        self.PX4Drone = None
        self.startDrones = None
        self.nextDroneIndex = 0

        super().__init__(scene, **kwargs)

    def setup(self):
        self.startDrones = self._resetForNewEpisode()
        self._setWindForNewEpisode()

        # Move all drones (except the PX4 drone) to an offscreen position while
        # the simulation remains paused.  They do not need a flight command
        # here: used drones receive one when they are placed below, and unused
        # drones can safely fall offscreen.
        for i, drone in enumerate(self.startDrones):
            newPose = airsim.Pose(
                position_val=scenicToAirsimLocation(
                    toVector(self.simulator.idleStoragePos), Vector(0, 0, 0)
                )
                + airsim.Vector3r(i, 0, 0)
            )
            self.client.enableApiControl(True, drone)
            self.client.simSetVehiclePose(
                vehicle_name=drone, pose=newPose, ignore_collision=False
            )

        # Create objects without starting their asynchronous hover tasks yet.
        # Starting a hover while an earlier offscreen pose is still visible to
        # AirSim can make the controller capture that stale pose as its target.
        self._settingUp = True
        try:
            super().setup()
        finally:
            self._settingUp = False

        for realObjName, (pose, startHovering) in self.initialDronePoses.items():
            if startHovering:
                self.client.hoverAsync(vehicle_name=realObjName)

        # Give the asynchronous hover RPCs time to install their controller
        # setpoints.  Keep physics paused: advancing a hidden settling interval
        # here would move the drones before Scenic records trace state 0.
        time.sleep(CONTROLLER_STARTUP_TIME)

        # Reassert the declared poses after the controllers are active.  This
        # removes any state change made while arming without running a hidden
        # physics interval before trace state 0.
        for realObjName, (pose, _) in self.initialDronePoses.items():
            self.client.simSetVehiclePose(
                vehicle_name=realObjName, pose=pose, ignore_collision=True
            )
            actual = self.client.simGetGroundTruthKinematics(realObjName).position
            error = math.sqrt(
                (actual.x_val - pose.position.x_val) ** 2
                + (actual.y_val - pose.position.y_val) ** 2
                + (actual.z_val - pose.position.z_val) ** 2
            )
            if error > 1:
                raise SimulationCreationError(
                    f"AirSim failed to place {realObjName} at its initial pose "
                    f"(error {error:.3f} m)"
                )

        # drones spawn at rest, so launch any drone declared already in motion
        self.applyStartVelocities()

    def _resetForNewEpisode(self):
        """Reset and validate the reusable SimpleFlight vehicles.

        Cleanup at the end of a prior Scenic simulation is best-effort: the
        client may have crashed or been interrupted before it ran.  Establish
        the episode boundary here instead, before any sampled pose or controller
        command is installed.  AirSim reset disables API control and may change
        pause state, so setup reacquires both explicitly afterward.
        """
        try:
            self.client.simPause(True)
            self.client.reset()
            self.client.simPause(True)
            vehicles = self.client.listVehicles()

            for vehicle in vehicles:
                # PX4 owns its state in an external flight controller and is not
                # part of the reusable SimpleFlight vehicle pool below.
                if vehicle == PX4_DRONE:
                    continue

                kinematics = self.client.simGetGroundTruthKinematics(vehicle)
                linear = kinematics.linear_velocity
                angular = kinematics.angular_velocity
                components = (
                    linear.x_val,
                    linear.y_val,
                    linear.z_val,
                    angular.x_val,
                    angular.y_val,
                    angular.z_val,
                )
                if not all(math.isfinite(value) for value in components):
                    raise SimulationCreationError(
                        f"AirSim reset returned non-finite motion for {vehicle}: "
                        f"linear={components[:3]}, angular={components[3:]}"
                    )

                linearSpeed = math.hypot(linear.x_val, linear.y_val, linear.z_val)
                angularSpeed = math.hypot(angular.x_val, angular.y_val, angular.z_val)
                if (
                    linearSpeed > RESET_LINEAR_SPEED_TOLERANCE
                    or angularSpeed > RESET_ANGULAR_SPEED_TOLERANCE
                ):
                    raise SimulationCreationError(
                        f"AirSim reset left {vehicle} moving: "
                        f"linear speed {linearSpeed:.6g} m/s "
                        f"(limit {RESET_LINEAR_SPEED_TOLERANCE:.6g}), "
                        f"angular speed {angularSpeed:.6g} rad/s "
                        f"(limit {RESET_ANGULAR_SPEED_TOLERANCE:.6g})"
                    )
        except SimulationCreationError:
            raise
        except Exception as exc:
            raise SimulationCreationError(
                f"AirSim failed to reset for a new Scenic episode: {exc}"
            ) from exc

        return [vehicle for vehicle in vehicles if vehicle != PX4_DRONE]

    def _setWindForNewEpisode(self):
        """Install the scene's global wind after reset and before placement.

        AirSim keeps wind in world state across vehicle resets.  Every Scenic
        episode therefore writes a wind vector, including an explicit zero for
        scenarios which do not specify one.
        """
        wind = self.scene.params.get("wind", Vector(0, 0, 0))
        try:
            wind = toVector(wind)
            components = (wind.x, wind.y, wind.z)
            if not all(math.isfinite(value) for value in components):
                raise ValueError(f"non-finite Scenic wind vector {components}")
            self.client.simSetWind(scenicToAirsimVector(wind))
        except Exception as exc:
            raise SimulationCreationError(
                f"AirSim failed to set episode wind from {wind!r}: {exc}"
            ) from exc

    def applyStartVelocities(self):
        """Give each drone with a `startVelocity` that velocity instantaneously.

        Spawning only ever sets a pose, and an AirSim pose carries no velocity,
        so a drone always comes into existence hovering.  A controller that
        immediately commands several m/s then spends the first ticks
        accelerating into it, and anything measured over those ticks describes
        the cold start rather than steady flight.

        This runs after setup has installed the hover controllers, reasserted
        the declared poses, and validated the physical placements.  Its
        velocity command replaces the hover setpoint before the velocity is
        forced, so simple_flight does not immediately brake back to a hover.
        """
        for realObjName, velocity in self.startVelocities.items():
            airsimVelocity = scenicToAirsimVector(velocity)

            # Move the controller setpoint to match the state we are about to
            # force; otherwise simple_flight is still holding the hover
            # setpoint and brakes out of the velocity on the first step.  The
            # duration only has to cover that step, after which the scenario's
            # own actions take over.
            self.client.moveByVelocityAsync(
                airsimVelocity.x_val,
                airsimVelocity.y_val,
                airsimVelocity.z_val,
                self.simulator.timestep,
                vehicle_name=realObjName,
            )

            # simSetKinematics sets the velocity instantaneously; moveByVelocityAsync
            # is a command the drone has to accelerate into.
            #
            # The whole state is read back and only the linear velocity changed, which
            # preserves the placement above exactly.  Against Blocks 1.8.1 a NaN
            # position is written through and the physics engine turns the entire state,
            # velocity included, into NaN on the next step, and simGetVehiclePose is
            # stale while the simulator is paused.
            #
            # With `ignore_collision` False, AirSim resolves the write as a
            # collision-checked teleport, dropping the vehicle to the ground and
            # freezing its physics ~14.5 m below its spawn pose.  The reassertion of the
            # declared poses above also ignores collision.
            kinematics = self.client.simGetGroundTruthKinematics(realObjName)
            kinematics.linear_velocity = airsimVelocity
            self.client.simSetKinematics(kinematics, True, vehicle_name=realObjName)

    def createObjectInSimulator(self, obj):
        # create AirSimPreExisting
        if obj.blueprint == "AirSimPreExisting":
            self.objs[obj.name] = obj.name
            return

        # set obj name if no name specified
        if not obj.name:
            obj.name = str(hash(obj))

        # ensure obj isn't already in world
        if obj.name in self.objs:
            raise RuntimeError(
                "there is already an object of the name " + obj.name + " in the simulator"
            )

        # set default realObjName
        realObjName = obj.name + str(hash(obj))

        # set object airsim pose
        pose = airsim.Pose(
            position_val=scenicToAirsimLocation(obj.position, obj.centerOffset),
            orientation_val=scenicToAirsimOrientation(obj.orientation),
        )

        # create obj in airsim
        if obj.blueprint == "Drone":
            realObjName = "Drone" + str(self.nextDroneIndex)
            obj._startPos = obj.position

            # if there is an avalible drone, take it, else create one
            if self.nextDroneIndex < len(self.startDrones):
                realObjName = self.startDrones[self.nextDroneIndex]
                obj.realObjName = realObjName
            else:
                self.client.simAddVehicle(
                    vehicle_name=realObjName, vehicle_type="simpleflight", pose=pose
                )

            self.nextDroneIndex += 1

            # save the drone name
            obj.realObjName = realObjName
            self.objs[obj.name] = realObjName
            self.drones[obj.name] = realObjName

            # start the drone and place it in the world
            self.client.enableApiControl(True, realObjName)
            self.client.armDisarm(True, realObjName)
            self.client.simSetVehiclePose(
                vehicle_name=realObjName, pose=pose, ignore_collision=True
            )

            self.initialDronePoses[realObjName] = (pose, obj.startHovering)

            # Set propellers on or off. During initial setup hover is deferred
            # until every drone has its final pose, so the controller cannot
            # capture the temporary offscreen pose.
            if obj.startHovering and not getattr(self, "_settingUp", False):
                # AirSim's hover command holds position until another task
                # cancels it.  A finite zero-velocity movement task is not the
                # same position-holding operation and races setup.
                self.client.hoverAsync(vehicle_name=realObjName)
            elif not obj.startHovering:
                # shut off drone propellers
                self.client.moveByVelocityAsync(0, 0, 0, -1, vehicle_name=realObjName)

            # Defer until setup has stabilized and validated the initial pose.
            if obj.startVelocity is not None:
                if not obj.startHovering:
                    raise RuntimeError(
                        "drone "
                        + obj.name
                        + " has a startVelocity but startHovering is False;"
                        " a drone with its propellers off cannot hold a velocity"
                    )
                self.startVelocities[realObjName] = toVector(obj.startVelocity)

        elif obj.blueprint == "PX4Drone":
            realObjName = PX4_DRONE

            if self.PX4Drone:
                raise RuntimeError("more than 1 px4 drone is not currently supported")

            if obj.startVelocity is not None:
                raise RuntimeError(
                    "startVelocity is not supported for PX4 drones; their state is"
                    " owned by the PX4 controller, not by simSetKinematics"
                )

            self.PX4Drone = PX4_DRONE
            self.client.simSetVehiclePose(
                vehicle_name=realObjName, pose=pose, ignore_collision=True
            )

            obj.realObjName = realObjName
            self.objs[obj.name] = realObjName

        elif obj.blueprint == "StaticObj":
            # ensure user is creating an object that uses an existing asset
            if not (obj.assetName in self.client.simListAssets()):
                raise RuntimeError(
                    "no asset of name found: "
                    + obj.assetName
                    + "\n use one of these assets:\n"
                    + self.client.simListAssets()
                )

            # create obj in airsim
            realObjName = self.client.simSpawnObject(
                object_name=realObjName,
                asset_name=obj.assetName,
                pose=pose,
                scale=scenicToAirsimScale(
                    Vector(obj.width, obj.length, obj.height), obj.dims
                ),
                physics_enabled=obj.physEnabled,
                is_blueprint=False,
            )

            if obj.materialName:
                self.client.simSetObjectMaterial(realObjName, obj.materialName)

            # add obj to sim lists
            obj.realObjName = realObjName
            self.objs[obj.name] = realObjName
            self.objTrove.append(realObjName)

        else:
            raise RuntimeError("object blueprint does not exist", obj.blueprint)

    def step(self):
        self.client.simContinueForTime(self.simulator.timestep)

    # ------------------- Other Simulator methods -------------------

    def destroy(self):
        # reinstantiate client
        client = self.client
        client.client._loop.stop()  # stop any running tasks to prevent errors

        client.simPause(True)

        # destroy all objs
        for obj_name in self.objTrove:
            client.simDestroyObject(obj_name)

        for droneName, realDroneName in self.drones.items():
            client.cancelLastTask(vehicle_name=realDroneName)
            client.moveByVelocityAsync(0, 0, 0, -1, vehicle_name=realDroneName)

        # Best-effort cleanup for a normally completed episode.  Correctness
        # does not rely on this running: the next setup performs and validates
        # its own authoritative reset before placing any vehicle.
        client.reset()

        super().destroy()
        print("canceled simulation")

    def getProperties(self, obj, properties):
        if obj.blueprint == "AirSimPreExisting":
            return dict(
                position=obj.position,
                velocity=Vector(0, 0, 0),
                speed=0,
                angularSpeed=0,
                angularVelocity=Vector(0, 0, 0),
                yaw=0,
                pitch=0,
                roll=0,
            )
        objName = self.objs[obj.name]

        pose = None
        velocity, speed, angularSpeed, angularVelocity = None, None, None, None

        # get obj data
        if obj.blueprint == "Drone" or obj.blueprint == "PX4Drone":
            kinematics = self.client.simGetGroundTruthKinematics(objName)
            # simGetVehiclePose can lag behind simSetVehiclePose while AirSim is
            # paused, which made Scenic record a stale location at trace state
            # 0.  Ground-truth kinematics updates synchronously with the
            # teleport and provides the same vehicle-relative pose frame.
            pose = airsim.Pose(
                position_val=kinematics.position,
                orientation_val=kinematics.orientation,
            )
            velocity = airsimToScenicVector(kinematics.linear_velocity)

            angularVelocity = airsimToScenicVector(kinematics.angular_velocity)

        elif obj.blueprint == "StaticObj" or obj.blueprint == "AirSimPreExisting":
            pose = self.client.simGetObjectPose(objName)

            # static objs don't have velocity
            velocity = Vector(0, 0, 0)
            angularVelocity = Vector(0, 0, 0)
        else:
            raise RuntimeError("object blueprint does not exist", obj.blueprint)

        # convert values
        globalOrientation = airsimToScenicOrientation(pose.orientation)
        yaw, pitch, roll = obj.parentOrientation.localAnglesFor(globalOrientation)

        if (
            obj.blueprint == "Drone"
            and self.currentTime == 0
            and obj._startPos is not None
        ):
            # The ground-truth kinematics pose is the vehicle's center of mass,
            # which differs slightly from the Scenic mesh origin.  State 0 is
            # the declared, validated spawn pose; subsequent states come from
            # AirSim.
            location = obj._startPos
        else:
            location = airsimToScenicLocation(pose.position, obj.centerOffset)

        speed = math.hypot(velocity.x, velocity.y, velocity.z)
        angularSpeed = math.hypot(angularVelocity.x, angularVelocity.y, angularVelocity.z)

        values = dict(
            position=location,
            velocity=velocity,
            speed=speed,
            angularSpeed=angularSpeed,
            angularVelocity=angularVelocity,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
        )

        return values
