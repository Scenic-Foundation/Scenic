"""Tests that run real simulations in Isaac Sim, skipped when it isn't installed.

Run these through the Python environment Isaac Sim itself provides (see the
"Running Scenic with Isaac Sim" section of the interface's README), e.g.::

    isaac-sim/python.sh -m pytest tests/simulators/isaac/test_isaac_simulation.py

Isaac Sim takes tens of seconds to boot and supports only one
``SimulationApp`` per OS process, with no supported way to close and reopen
one within a process. So `isaacBackend` below is a session-scoped fixture:
every test shares the one `SimulationApp` it boots, and none of them (nor the
fixture) ever closes it -- `IsaacBackend` already registers an ``atexit`` hook
that does so when the interpreter exits.

For the same reason, every test forces the session's single auto-detected
backend, overriding any ``isaacBackend`` an example file sets for itself:
each named backend (``core_51``, ``experimental_60``, ...) independently
launches its own ``SimulationApp`` on first use, so using two different
backends within one process crashes the whole interpreter (segfault) rather
than raising a catchable error.
"""

import os

import pytest

pytest.importorskip("isaacsim")

import scenic
from tests.utils import compileScenic, sampleScene

EXAMPLES = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "examples", "isaacsim"
)


@pytest.fixture(scope="session")
def isaacBackend():
    """The single Isaac Sim backend/``SimulationApp`` shared by every test here."""
    from scenic.simulators.isaac.backends import getBackend

    backend = getBackend()
    backend.getSimulationApp(headless=True)
    return backend


def _simulate(scenario, maxSteps, **kwargs):
    """Sample a scene and run it to completion."""
    scene = sampleScene(scenario, maxIterations=500)
    simulator = scenario.getSimulator()
    simulation = simulator.simulate(scene, maxSteps=maxSteps, verbosity=1, **kwargs)
    assert simulation is not None, "simulation was rejected"
    return simulation


def _loadExample(relpath, isaacBackend, **params):
    params.setdefault("headless", True)
    params.setdefault("isaacBackend", isaacBackend.name)
    return scenic.scenarioFromFile(os.path.join(EXAMPLES, relpath), params=params)


def _compile(code, isaacBackend, **params):
    params.setdefault("headless", True)
    params.setdefault("isaacBackend", isaacBackend.name)
    return compileScenic(code, params=params)


def test_backend_matches_installed_isaac_sim(isaacBackend):
    """The auto-detected backend must actually be usable with the running Isaac Sim.

    Regression test for the "auto" backend only correctly guessing
    experimental_60 by luck of its fallback default: Isaac Sim's own bundled
    Python has no pip metadata for the ``isaacsim`` package, which used to
    make detection silently fall back regardless of the real version.
    """
    from isaacsim.core.version import get_version

    major = get_version()[0]
    expected = {"5": {"core_51", "experimental_51"}, "6": {"experimental_60"}}
    assert isaacBackend.name in expected.get(major, {isaacBackend.name})


def test_wheeled_and_manipulator_robots(isaacBackend, loadLocalScenario):
    """Regression test for the model.scenic/backend attribute-scoping bugs where
    a wheeled or plain object had no ``manipulatorProfile`` and a plain object
    had no ``wheelController``: both crashed with an AttributeError on the very
    first object created, before completing even one simulation step.

    Exercises: a mesh-shaped generic object, the built-in Create3 wheeled
    robot, a custom robot with a hand-written ``control`` function, and a
    FrankaPanda manipulator running the generic end-effector behaviors
    (OpenGripper/MoveEndEffectorTo/CloseGripper/HoldPosition).
    """
    scenario = loadLocalScenario(
        "basic.scenic", params={"headless": True, "isaacBackend": isaacBackend.name}
    )
    simulation = _simulate(scenario, maxSteps=150)
    assert simulation.result.terminationReason is not None


def test_object_falls_under_gravity(isaacBackend):
    """A physics-enabled object dropped above the ground should fall and land on it."""
    scenario = _compile(
        """
        model scenic.simulators.isaac.model

        floor = new GroundPlane with width 6, with length 6
        box = new IsaacSimObject at (0, 0, 2),
            with shape BoxShape(), with width 0.3, with length 0.3, with height 0.3,
            with density 200
        record box.z as BoxHeight
        terminate after 90 steps
        """,
        isaacBackend,
    )
    simulation = _simulate(scenario, maxSteps=90)
    heights = [z for _, z in simulation.result.records["BoxHeight"]]
    assert heights[0] > 1.5, "box did not start in midair"
    assert heights[-1] < 0.5, "box did not fall toward the ground"
    assert heights[-1] > -0.2, "box fell through the ground plane"


def test_wheeled_robot_moves_in_expected_direction(isaacBackend):
    """A wheeled robot's heading determines which way "drive forward" moves
    it, matching Scenic's documented compass convention: heading 0 is north
    (+y), heading 90 degrees is west (-x).

    Regression test for a bug where built-in wheeled robots (Create3, Jetbot,
    Kaya) drove ~90 degrees off from their commanded heading, because their
    USD assets are authored with local +X as "forward" while Scenic's
    convention is local +Y; see the ``initialRotation`` on those classes in
    model.scenic and `IsaacBackend.scenicToIsaacOrientation`.
    """
    scenario = _compile(
        """
        model scenic.simulators.isaac.model

        behavior DriveForward():
            while True:
                take ApplyControllerAction([0.3, 0])

        floor = new GroundPlane with width 8, with length 8
        north = new Create3 on floor, facing 0 deg, with behavior DriveForward
        west = new Create3 on floor, facing 90 deg, with behavior DriveForward
        require distance from north to west > 2
        record (north.x, north.y) as NorthPosition
        record (west.x, west.y) as WestPosition
        terminate after 120 steps
        """,
        isaacBackend,
    )
    simulation = _simulate(scenario, maxSteps=120)
    northPositions = [pos for _, pos in simulation.result.records["NorthPosition"]]
    westPositions = [pos for _, pos in simulation.result.records["WestPosition"]]

    dNorthX = northPositions[-1][0] - northPositions[0][0]
    dNorthY = northPositions[-1][1] - northPositions[0][1]
    dWestX = westPositions[-1][0] - westPositions[0][0]
    dWestY = westPositions[-1][1] - westPositions[0][1]

    # Facing north (heading 0) means forward is +y.
    assert dNorthY > 0.3, "robot facing north did not move forward"
    assert abs(dNorthX) < dNorthY, "robot facing north drifted sideways instead"

    # Facing west (heading 90 deg) means forward is -x.
    assert dWestX < -0.3, "robot facing west did not move forward"
    assert abs(dWestY) < abs(dWestX), "robot facing west drifted sideways instead"


def test_orientation_handles_pitch_and_roll(isaacBackend):
    """Spawned orientation must round-trip correctly for combined yaw, pitch,
    and roll -- not just yaw -- both for a plain object (no
    ``initialRotation``) and for a wheeled robot, which composes its own
    ``initialRotation`` correction on top (see model.scenic).
    """
    scenario = _compile(
        """
        model scenic.simulators.isaac.model
        from scenic.core.vectors import Orientation

        tilted = Orientation.fromEuler(0.4, 0.25, -0.15)

        floor = new GroundPlane with width 6, with length 6
        box = new IsaacSimObject at (0, 0, 1), facing tilted,
            with shape BoxShape(), with width 0.3, with length 0.3, with height 0.3,
            with physics False
        robot = new Create3 at (3, 0, 1), facing tilted
        record box.orientation as BoxOrientation
        record robot.orientation as RobotOrientation
        terminate after 1 steps
        """,
        isaacBackend,
    )
    simulation = _simulate(scenario, maxSteps=1)

    from scenic.core.vectors import Orientation

    tilted = Orientation.fromEuler(0.4, 0.25, -0.15)
    boxOrientation = simulation.result.records["BoxOrientation"][-1][1]
    robotOrientation = simulation.result.records["RobotOrientation"][-1][1]

    assert boxOrientation.approxEq(tilted, tol=1e-3), (
        "a kinematic object's spawned yaw/pitch/roll did not round-trip:"
        f" got {boxOrientation.eulerAngles}, expected {tilted.eulerAngles}"
    )
    assert robotOrientation.approxEq(tilted, tol=1e-2), (
        "a robot's spawned yaw/pitch/roll (composed with its initialRotation"
        f" correction) did not round-trip: got {robotOrientation.eulerAngles},"
        f" expected {tilted.eulerAngles}"
    )


def test_environment_and_compressed_asset_mesh(isaacBackend):
    """Loads and converts an environment USD, places a new object on an
    existing prim using a compressed converted mesh (``.glb.bz2``) as its
    shape.

    Regression test for: flattening a referenced/payloaded USD asset before
    conversion (the old code exported only the root layer, breaking assets
    like this one built from references); the compressed mesh conversion and
    loading pipeline (`usd_conversion.convertUsdToMesh`, `utils.writeMesh`,
    `utils.loadAssetMesh`); and the existing-prim orientation fix (building
    the `Orientation` from the USD transform's rotation matrix instead of
    reinterpreting trimesh's static-XYZ Euler angles as Scenic's intrinsic
    Z-X-Y ones).
    """
    scenario = _loadExample("simple_room_asset_shape.scenic", isaacBackend)
    simulation = _simulate(scenario, maxSteps=10)
    assert simulation.result.terminationReason is not None


def test_manipulator_pick_and_place(isaacBackend):
    """Runs the UR5e Robotiq-gripper pick-and-place example (forcing the
    session's shared backend rather than the file's own ``experimental_51``;
    see module docstring). Regression test for the Robotiq USD authoring
    extracted into ``backends/robotiq.py`` and for the quaternion/Euler-angle
    math rewritten to use scipy's ``Rotation`` and Scenic's ``Orientation``.
    """
    scenario = _loadExample("robot/ur5e_example_experimental.scenic", isaacBackend)
    simulation = _simulate(scenario, maxSteps=150)
    assert simulation.result.terminationReason is not None
