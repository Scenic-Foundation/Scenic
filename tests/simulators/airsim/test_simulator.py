import unittest
from unittest.mock import Mock, call, patch

try:
    import airsim
except ImportError as exc:  # pragma: no cover - depends on optional simulator package
    raise unittest.SkipTest("AirSim is not installed") from exc

from scenic.core.simulators import Simulation, SimulationCreationError
from scenic.core.vectors import Vector
from scenic.simulators.airsim import utils
from scenic.simulators.airsim.simulator import (
    CONTROLLER_STARTUP_TIME,
    PX4_DRONE,
    RESET_ANGULAR_SPEED_TOLERANCE,
    RESET_LINEAR_SPEED_TOLERANCE,
    AirSimSimulation,
)


def makeKinematics(*, position=(0, 0, 0), linear=(0, 0, 0), angular=(0, 0, 0)):
    kinematics = airsim.KinematicsState()
    kinematics.position = airsim.Vector3r(*position)
    kinematics.orientation = airsim.Quaternionr()
    kinematics.linear_velocity = airsim.Vector3r(*linear)
    kinematics.angular_velocity = airsim.Vector3r(*angular)
    return kinematics


class AirSimSetupTests(unittest.TestCase):
    def test_setup_keeps_physics_paused_during_controller_startup(self):
        client = Mock()
        client.listVehicles.return_value = ["Drone0", PX4_DRONE, "Drone1"]
        pose = airsim.Pose(position_val=airsim.Vector3r(1, 2, 3))
        kinematics = makeKinematics(position=(1, 2, 3))
        client.simGetGroundTruthKinematics.return_value = kinematics

        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.scene = Mock(params={})
        simulation.simulator = Mock(idleStoragePos=(0, 0, 0))
        simulation.startDrones = None
        simulation.initialDronePoses = {"Drone0": (pose, True)}
        simulation.startVelocities = {}

        with (
            patch.object(Simulation, "setup") as coreSetup,
            patch("scenic.simulators.airsim.simulator.time.sleep") as sleep,
        ):
            AirSimSimulation.setup(simulation)

        self.assertEqual(simulation.startDrones, ["Drone0", "Drone1"])
        client.hoverAsync.assert_called_once_with(vehicle_name="Drone0")
        client.simContinueForTime.assert_not_called()
        sleep.assert_called_once_with(CONTROLLER_STARTUP_TIME)
        self.assertEqual(
            [method for method in client.method_calls if method[0] == "simPause"],
            [call.simPause(True), call.simPause(True)],
        )
        client.reset.assert_called_once_with()
        wind = client.simSetWind.call_args.args[0]
        self.assertEqual((wind.x_val, wind.y_val, wind.z_val), (0, 0, 0))
        lifecycle = [
            method[0]
            for method in client.method_calls
            if method[0] in {"simPause", "reset", "listVehicles", "simSetWind"}
        ]
        self.assertEqual(
            lifecycle[:5],
            [
                "simPause",
                "reset",
                "simPause",
                "listVehicles",
                "simSetWind",
            ],
        )
        coreSetup.assert_called_once_with()

    def test_reset_precedes_api_control_arming_and_hover(self):
        client = Mock()
        client.listVehicles.return_value = ["Drone0"]
        client.simGetGroundTruthKinematics.return_value = makeKinematics()

        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.scene = Mock(params={})
        simulation.simulator = Mock(idleStoragePos=(0, 0, 0))
        simulation.startDrones = None
        simulation.nextDroneIndex = 0
        simulation.objs = {}
        simulation.drones = {}
        simulation.initialDronePoses = {}
        simulation.startVelocities = {}

        obj = Mock()
        obj.configure_mock(
            blueprint="Drone",
            position=(0, 0, 0),
            centerOffset=(0, 0, 0),
            orientation=None,
            startHovering=True,
            startVelocity=None,
        )
        obj.name = "scenicDrone"

        with (
            patch.object(
                Simulation,
                "setup",
                side_effect=lambda: simulation.createObjectInSimulator(obj),
            ),
            patch(
                "scenic.simulators.airsim.simulator.scenicToAirsimLocation",
                return_value=airsim.Vector3r(),
            ),
            patch(
                "scenic.simulators.airsim.simulator.scenicToAirsimOrientation",
                return_value=airsim.Quaternionr(),
            ),
            patch("scenic.simulators.airsim.simulator.time.sleep"),
        ):
            AirSimSimulation.setup(simulation)

        methodNames = [method[0] for method in client.method_calls]
        resetIndex = methodNames.index("reset")
        windIndex = methodNames.index("simSetWind")
        self.assertLess(resetIndex, windIndex)
        self.assertLess(windIndex, methodNames.index("enableApiControl"))
        self.assertLess(resetIndex, methodNames.index("enableApiControl"))
        self.assertLess(resetIndex, methodNames.index("armDisarm"))
        self.assertLess(resetIndex, methodNames.index("hoverAsync"))
        client.armDisarm.assert_called_once_with(True, "Drone0")

    def test_wind_is_converted_from_scenic_to_airsim_world_axes(self):
        client = Mock()
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.scene = Mock(params={"wind": Vector(1, 2, 3)})

        simulation._setWindForNewEpisode()

        wind = client.simSetWind.call_args.args[0]
        self.assertEqual((wind.x_val, wind.y_val, wind.z_val), (1, -2, -3))

    def test_missing_wind_explicitly_clears_prior_episode_wind(self):
        client = Mock()
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.scene = Mock(params={"wind": Vector(3, -1, 0.5)})

        simulation._setWindForNewEpisode()
        simulation.scene = Mock(params={})
        simulation._setWindForNewEpisode()

        winds = [
            (arg.x_val, arg.y_val, arg.z_val)
            for (arg,), _ in client.simSetWind.call_args_list
        ]
        self.assertEqual(winds, [(3, 1, -0.5), (0, 0, 0)])

    def test_wind_rejects_nonfinite_components(self):
        client = Mock()
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.scene = Mock(params={"wind": Vector(float("nan"), 0, 0)})

        with self.assertRaisesRegex(
            SimulationCreationError, "non-finite Scenic wind vector"
        ):
            simulation._setWindForNewEpisode()

        client.simSetWind.assert_not_called()

    def test_wind_rpc_failure_is_a_simulation_creation_error(self):
        client = Mock()
        client.simSetWind.side_effect = RuntimeError("wind RPC disconnected")
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.scene = Mock(params={"wind": Vector(1, 0, 0)})

        with self.assertRaisesRegex(
            SimulationCreationError,
            "AirSim failed to set episode wind.*wind RPC disconnected",
        ):
            simulation._setWindForNewEpisode()

    def test_reset_rejects_residual_linear_or_angular_motion(self):
        badStates = (
            (
                "linear",
                makeKinematics(linear=(RESET_LINEAR_SPEED_TOLERANCE + 0.001, 0, 0)),
            ),
            (
                "angular",
                makeKinematics(angular=(RESET_ANGULAR_SPEED_TOLERANCE + 0.001, 0, 0)),
            ),
        )
        for label, kinematics in badStates:
            with self.subTest(label=label):
                client = Mock()
                client.listVehicles.return_value = ["Drone0"]
                client.simGetGroundTruthKinematics.return_value = kinematics
                simulation = object.__new__(AirSimSimulation)
                simulation.client = client

                with self.assertRaisesRegex(
                    SimulationCreationError, "AirSim reset left Drone0 moving"
                ):
                    simulation._resetForNewEpisode()

    def test_reset_rejects_nonfinite_motion(self):
        badStates = (
            ("nan", makeKinematics(linear=(float("nan"), 0, 0))),
            ("infinity", makeKinematics(angular=(0, float("inf"), 0))),
        )
        for label, kinematics in badStates:
            with self.subTest(label=label):
                client = Mock()
                client.listVehicles.return_value = ["Drone0"]
                client.simGetGroundTruthKinematics.return_value = kinematics
                simulation = object.__new__(AirSimSimulation)
                simulation.client = client

                with self.assertRaisesRegex(
                    SimulationCreationError, "non-finite motion for Drone0"
                ):
                    simulation._resetForNewEpisode()

    def test_reset_rpc_failure_is_a_simulation_creation_error(self):
        client = Mock()
        client.reset.side_effect = RuntimeError("RPC disconnected")
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client

        with self.assertRaisesRegex(
            SimulationCreationError,
            "AirSim failed to reset for a new Scenic episode: RPC disconnected",
        ):
            simulation._resetForNewEpisode()

        client.listVehicles.assert_not_called()

    def test_reset_validation_excludes_px4(self):
        client = Mock()
        client.listVehicles.return_value = [PX4_DRONE, "Drone0"]
        client.simGetGroundTruthKinematics.return_value = makeKinematics()
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client

        vehicles = simulation._resetForNewEpisode()

        self.assertEqual(vehicles, ["Drone0"])
        client.simGetGroundTruthKinematics.assert_called_once_with("Drone0")

    def test_start_hovering_uses_hover_task_without_a_timeout(self):
        client = Mock()
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.simulator = Mock()
        simulation.startDrones = ["Drone0"]
        simulation.nextDroneIndex = 0
        simulation.objs = {}
        simulation.drones = {}
        simulation.initialDronePoses = {}
        simulation.startVelocities = {}

        obj = Mock()
        obj.configure_mock(
            blueprint="Drone",
            position=(0, 0, 10),
            centerOffset=(0, 0, 0),
            orientation=None,
            startHovering=True,
            startVelocity=None,
        )
        obj.name = "scenicDrone"

        with (
            patch(
                "scenic.simulators.airsim.simulator.scenicToAirsimLocation",
                return_value=airsim.Vector3r(),
            ),
            patch(
                "scenic.simulators.airsim.simulator.scenicToAirsimOrientation",
                return_value=airsim.Quaternionr(),
            ),
        ):
            simulation.createObjectInSimulator(obj)

        client.hoverAsync.assert_called_once_with(vehicle_name="Drone0")
        client.moveByVelocityAsync.assert_not_called()

    def test_start_velocity_replaces_hover_setpoint_and_kinematics(self):
        kinematics = airsim.KinematicsState()
        kinematics.position = airsim.Vector3r(1, 2, 3)
        kinematics.orientation = airsim.Quaternionr()
        kinematics.linear_velocity = airsim.Vector3r()

        client = Mock()
        client.simGetGroundTruthKinematics.return_value = kinematics

        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.simulator = Mock(timestep=0.1)
        simulation.startVelocities = {"Drone0": Vector(0, 3, 0)}

        simulation.applyStartVelocities()

        client.moveByVelocityAsync.assert_called_once_with(
            0, -3, 0, 0.1, vehicle_name="Drone0"
        )
        self.assertEqual(
            (
                kinematics.linear_velocity.x_val,
                kinematics.linear_velocity.y_val,
                kinematics.linear_velocity.z_val,
            ),
            (0, -3, 0),
        )
        client.simSetKinematics.assert_called_once_with(
            kinematics, True, vehicle_name="Drone0"
        )

    def test_start_velocity_ignores_collision(self):
        """simSetKinematics must ignore collision, or the drone is dropped and frozen.

        With ignore_collision=False AirSim treats the kinematics write as a
        collision-checked teleport: against Blocks 1.8.1 the vehicle lands on the
        ground roughly 14.5 m below its validated spawn pose and its physics stop
        advancing entirely, so the whole episode runs from the wrong state.  This
        asserts the flag directly because the symptom only shows up against a live
        simulator, one step after setup returns.
        """
        kinematics = airsim.KinematicsState()
        kinematics.position = airsim.Vector3r(1, 2, 3)
        kinematics.orientation = airsim.Quaternionr()
        kinematics.linear_velocity = airsim.Vector3r()

        client = Mock()
        client.simGetGroundTruthKinematics.return_value = kinematics

        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.simulator = Mock(timestep=0.1)
        simulation.startVelocities = {"Drone0": Vector(0, 3, 0)}

        simulation.applyStartVelocities()

        _, args, kwargs = client.simSetKinematics.mock_calls[0]
        self.assertIs(args[1], True, "simSetKinematics must ignore collision")
        self.assertEqual(kwargs, {"vehicle_name": "Drone0"})

    def test_drone_position_comes_from_ground_truth_kinematics(self):
        oldWorldOffset = utils.worldOffset
        self.addCleanup(setattr, utils, "worldOffset", oldWorldOffset)
        utils.worldOffset = Vector(0, 0, 0)

        kinematics = airsim.KinematicsState()
        kinematics.position = airsim.Vector3r(1, -2, -3)
        kinematics.orientation = airsim.Quaternionr()
        kinematics.linear_velocity = airsim.Vector3r()
        kinematics.angular_velocity = airsim.Vector3r()

        client = Mock()
        client.simGetGroundTruthKinematics.return_value = kinematics
        client.simGetVehiclePose.return_value = airsim.Pose(
            position_val=airsim.Vector3r(100, 100, 100)
        )

        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.objs = {"scenicDrone": "Drone0"}
        simulation.currentTime = 1

        obj = Mock(
            blueprint="Drone",
            centerOffset=Vector(0, 0, 0),
            parentOrientation=Mock(localAnglesFor=Mock(return_value=(0, 0, 0))),
        )
        obj.name = "scenicDrone"
        obj._startPos = None

        values = simulation.getProperties(obj, set())

        self.assertEqual(values["position"], Vector(1, 2, 3))
        client.simGetVehiclePose.assert_not_called()

    def test_teardown_cancels_tasks_and_resets_as_best_effort_cleanup(self):
        client = Mock()
        simulation = object.__new__(AirSimSimulation)
        simulation.client = client
        simulation.objTrove = ["Cone"]
        simulation.drones = {"scenicDrone": "Drone0"}

        with patch.object(Simulation, "destroy") as coreDestroy:
            AirSimSimulation.destroy(simulation)

        cleanupCalls = [
            method
            for method in client.method_calls
            if method[0]
            in {
                "simPause",
                "simDestroyObject",
                "cancelLastTask",
                "moveByVelocityAsync",
                "reset",
            }
        ]
        self.assertEqual(
            cleanupCalls,
            [
                call.simPause(True),
                call.simDestroyObject("Cone"),
                call.cancelLastTask(vehicle_name="Drone0"),
                call.moveByVelocityAsync(0, 0, 0, -1, vehicle_name="Drone0"),
                call.reset(),
            ],
        )
        coreDestroy.assert_called_once_with()
