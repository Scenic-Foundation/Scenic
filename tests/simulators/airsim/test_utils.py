import unittest
from unittest.mock import Mock

try:
    import airsim
except ImportError as exc:  # pragma: no cover - depends on optional simulator package
    raise unittest.SkipTest("AirSim is not installed") from exc

from scenic.core.vectors import Vector
from scenic.simulators.airsim import utils
from scenic.simulators.airsim.actions import SetVelocity


class AirSimVectorConversionTests(unittest.TestCase):
    def setUp(self):
        self.oldWorldOffset = utils.worldOffset

    def tearDown(self):
        utils.worldOffset = self.oldWorldOffset

    def test_scenic_to_airsim_vector_ignores_world_offset(self):
        utils.worldOffset = Vector(10, 20, 50)
        cases = (
            (Vector(0, 0, 0), (0, 0, 0)),
            (Vector(1, 2, 3), (1, -2, -3)),
            (Vector(-4, -5, -6), (-4, 5, 6)),
        )

        for scenic_vector, airsim_components in cases:
            with self.subTest(scenic_vector=scenic_vector):
                converted = utils.scenicToAirsimVector(scenic_vector)
                self.assertEqual(
                    (converted.x_val, converted.y_val, converted.z_val),
                    airsim_components,
                )

    def test_airsim_to_scenic_vector_ignores_world_offset(self):
        utils.worldOffset = Vector(10, 20, 50)

        converted = utils.airsimToScenicVector(airsim.Vector3r(1, -2, -3))

        self.assertEqual(converted, Vector(1, 2, 3))

    def test_velocity_vector_round_trip(self):
        original = Vector(1.25, -2.5, 3.75)

        converted = utils.airsimToScenicVector(utils.scenicToAirsimVector(original))

        self.assertEqual(converted, original)

    def test_vector_conversion_matches_position_displacement(self):
        utils.worldOffset = Vector(10, 20, 50)
        position = Vector(7, 11, 13)
        displacement = Vector(1.25, -2.5, 3.75)

        start = utils.scenicToAirsimLocation(position)
        end = utils.scenicToAirsimLocation(position + displacement)
        converted = utils.scenicToAirsimVector(displacement)

        self.assertAlmostEqual(end.x_val - start.x_val, converted.x_val)
        self.assertAlmostEqual(end.y_val - start.y_val, converted.y_val)
        self.assertAlmostEqual(end.z_val - start.z_val, converted.z_val)

    def test_zero_velocity_action_stays_zero(self):
        utils.worldOffset = Vector(0, 0, 50)

        action = SetVelocity(Vector(0, 0, 0))

        self.assertEqual(
            (
                action.newVelocity.x_val,
                action.newVelocity.y_val,
                action.newVelocity.z_val,
            ),
            (0, 0, 0),
        )

        client = Mock()
        action.applyTo(Mock(realObjName="Drone0"), Mock(client=client))
        client.moveByVelocityAsync.assert_called_once_with(
            0,
            0,
            0,
            duration=5,
            vehicle_name="Drone0",
        )
