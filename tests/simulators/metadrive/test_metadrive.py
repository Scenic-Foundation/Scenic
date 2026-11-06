from importlib.metadata import PackageNotFoundError, distribution, version
import json
import math
import os
from urllib.error import URLError

import numpy as np
import pytest

try:
    import metadrive
    from metadrive.pull_asset import pull_asset

    # Make sure MetaDrive assets are available.
    # On CI, if the asset server is down or unreachable, skip this whole file.
    try:
        pull_asset(update=False)
    except URLError as e:
        pytest.skip(
            f"MetaDrive assets could not be pulled ({e}); skipping MetaDrive tests",
            allow_module_level=True,
        )

    from scenic.simulators.metadrive import MetaDriveSimulator
except ModuleNotFoundError:
    pytest.skip("MetaDrive package not installed", allow_module_level=True)

from tests.utils import compileScenic, pickle_test, sampleScene, tryPickling

WINDOW_ERR = "Could not open window"


def metadrive_installed_from_git():
    # Git installs still report version "0.4.3"; PEP 610 direct_url.json lets us tell PyPI vs GitHub.
    try:
        direct = distribution("metadrive-simulator").read_text("direct_url.json")
    except PackageNotFoundError:
        return False
    if not direct:
        return False
    try:
        return "vcs_info" in json.loads(direct)
    except json.JSONDecodeError:
        return False


metadrive_pkg_version = version("metadrive-simulator")

xfail_md_brake_bug = pytest.mark.xfail(
    metadrive_pkg_version == "0.4.3" and not metadrive_installed_from_git(),
    reason="Known MetaDrive 0.4.3 (PyPI) braking/handbrake bug; install MetaDrive from GitHub for the fix.",
    strict=False,
)


# Helper to run a simulation but skip cleanly on CI.
# MetaDrive (Panda3D) tries to open a window on GitHub runners
# and fails with "Could not open window", while Newtonian (pygame) works fine.
# We still attempt the run (in case it succeeds or gets fixed), but if we hit
# that specific error we skip instead of failing the whole CI job.
def simulate_or_skip(simulator, scene):
    try:
        return simulator.simulate(scene)
    except Exception as e:
        if WINDOW_ERR in str(e):
            pytest.skip("MetaDrive (Panda3D) cannot open a window on this platform/CI")
        else:
            raise


def test_basic(loadLocalScenario):
    scenario = loadLocalScenario("basic.scenic", mode2D=True)
    scenario.generate(maxIterations=1000)


@pickle_test
@pytest.mark.slow
def test_pickle(loadLocalScenario):
    scenario = tryPickling(loadLocalScenario("basic.scenic", mode2D=True))
    tryPickling(sampleScene(scenario, maxIterations=1000))


@pytest.fixture(scope="package")
def getMetadriveSimulator(getAssetPath):
    base = getAssetPath("maps/CARLA")

    def _getMetadriveSimulator(
        town, *, render=False, render3D=False, real_time=False, **kwargs
    ):
        openDrivePath = os.path.join(base, f"{town}.xodr")
        sumoPath = os.path.join(base, f"{town}.net.xml")
        simulator = MetaDriveSimulator(
            sumo_map=sumoPath,
            xodr_map=openDrivePath,
            render=render,
            render3D=render3D,
            real_time=real_time,
            **kwargs,
        )
        return simulator, openDrivePath, sumoPath

    yield _getMetadriveSimulator


def test_throttle(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        behavior DriveWithThrottle():
            while True:
                take SetThrottleAction(1)

        ego = new Car at (369, -326), with behavior DriveWithThrottle
        record ego.speed as CarSpeed
        terminate after 5 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    speeds = simulation.result.records["CarSpeed"]
    assert speeds[len(speeds) // 2][1] < speeds[-1][1]


@xfail_md_brake_bug
def test_brake(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        behavior DriveWithThrottle():
            while True:
                take SetThrottleAction(1)

        behavior Brake():
            while True:
                take SetThrottleAction(0), SetBrakeAction(1)

        behavior DriveThenBrake():
            do DriveWithThrottle() for 2 steps
            do Brake() for 6 steps

        ego = new Car at (369, -326),
            with behavior DriveThenBrake
        record final ego.speed as CarSpeed
        terminate after 8 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    finalSpeed = simulation.result.records["CarSpeed"]
    assert finalSpeed == pytest.approx(0.0, abs=1e-1)


def test_reverse_and_brake(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        behavior Reverse():
            while True:
                take SetReverseAction(True), SetThrottleAction(1), SetBrakeAction(0)

        behavior Brake():
            while True:
                take SetThrottleAction(0), SetBrakeAction(1)

        behavior ReverseThenBrake():
            do Reverse() for 3 steps
            do Brake() for 10 steps

        ego = new Car at (369, -326), with behavior ReverseThenBrake

        record initial ego.heading as Heading
        record ego.velocity as Vel
        record final ego.speed as Speed

        terminate after 13 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)

    h = simulation.result.records["Heading"]
    fwd = (-math.sin(h), math.cos(h))
    vx, vy, _ = simulation.result.records["Vel"][2][1]
    proj = vx * fwd[0] + vy * fwd[1]
    assert proj < -0.02, f"Expected reverse velocity (negative proj), got {proj}"

    finalSpeed = simulation.result.records["Speed"]
    assert finalSpeed == pytest.approx(0.0, abs=0.5)


@xfail_md_brake_bug
def test_handbrake(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        behavior HandbrakeAndThrottle():
            while True:
                take SetHandBrakeAction(True), SetThrottleAction(1)

        ego = new Car at (369, -326), with behavior HandbrakeAndThrottle
        record initial ego.position as InitialPos
        record final ego.position as FinalPos
        record final ego.speed as Speed
        terminate after 6 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)

    p0 = simulation.result.records["InitialPos"]
    p1 = simulation.result.records["FinalPos"]
    finalSpeed = simulation.result.records["Speed"]

    assert p0 == pytest.approx(p1, abs=0.05)
    assert finalSpeed == pytest.approx(0.0, abs=0.1)


def test_set_position(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        behavior Teleport():
            wait
            take SetPositionAction(Vector(120, -56))

        ego = new Car at (30, 2), with behavior Teleport
        record initial ego.position as InitialPos
        record final ego.position as FinalPos
        terminate after 2 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    p0 = simulation.result.records["InitialPos"]
    p1 = simulation.result.records["FinalPos"]

    assert p0 != p1
    assert p1 == pytest.approx((120, -56, 0), abs=0.01)


def test_initial_velocity_movement(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        # Car should move 5 m/s west
        ego = new Car at (30, 2), with velocity (-5, 0)
        record initial ego.position as InitialPos
        record final ego.position as FinalPos
        terminate after 1 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    initialPos = simulation.result.records["InitialPos"]
    finalPos = simulation.result.records["FinalPos"]
    dx = finalPos[0] - initialPos[0]
    assert dx < -0.1, f"Expected car to move west (negative dx), but got dx = {dx}"


def test_pedestrian_movement(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        behavior WalkForward():
            while True:
                take SetWalkingDirectionAction(self.heading), SetWalkingSpeedAction(0.5)

        behavior StopWalking():
            while True:
                take SetWalkingSpeedAction(0)

        behavior WalkThenStop():
            do WalkForward() for 2 steps
            do StopWalking() for 2 steps

        ego = new Car at (30, 2)
        pedestrian = new Pedestrian at (50, 6), with behavior WalkThenStop

        record pedestrian.position as Pos
        terminate after 4 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    series = simulation.result.records["Pos"]
    initialPos = series[0][1]
    finalPos = series[-1][1]
    assert initialPos != finalPos


@pytest.mark.slow
@pytest.mark.graphical
def test_static_pedestrian(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator(
        "Town01", render=True, render3D=True
    )
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        ego = new Car at (266.21, -59.57)
        pedestrian = new Pedestrian at (275, -59.57), with regionContainedIn None
        record initial pedestrian.position as InitialPos
        record final pedestrian.position as FinalPos
        terminate after 5 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulate_or_skip(simulator, scene)

    initialPos = simulation.result.records["InitialPos"]
    finalPos = simulation.result.records["FinalPos"]
    assert initialPos == finalPos, (
        f"Expected pedestrian to remain stationary (default speed=0), "
        f"but moved from {initialPos} to {finalPos}"
    )


@pytest.mark.graphical  # TODO temporary until MetaDrive issue fixed in new release
def test_duplicate_sensor_names(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        ego = new Car at (369, -326),
            with sensors {{
                "front_rgb": RGBSensor(offset=(1.6, 0, 1.7), width=64, height=64)
            }}

        # ensure a different view so frames shouldn't match
        other = new Car at (385, -326),
            with sensors {{
                "front_rgb": RGBSensor(offset=(1.6, 0, 1.7), rotation=(45, 0, 0), width=64, height=64)
            }}

        record ego.observations["front_rgb"] as EgoRGB
        record other.observations["front_rgb"] as OtherRGB
        terminate after 3 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulate_or_skip(simulator, scene)

    ego_series = simulation.result.records["EgoRGB"]
    other_series = simulation.result.records["OtherRGB"]
    assert len(ego_series) > 0 and len(other_series) > 0

    img0 = ego_series[-1][1]
    img1 = other_series[-1][1]
    assert img0.shape == (64, 64, 3)
    assert img1.shape == (64, 64, 3)
    assert not np.array_equal(img0, img1)


def test_steer(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'
        model scenic.simulators.metadrive.model

        behavior TurnRight():
            while True:
                take SetThrottleAction(0.5), SetSteerAction(1)

        # Ego facing west
        ego = new Car at (300, -55), with behavior TurnRight

        record initial ego.heading as InitialHeading
        record final ego.heading as FinalHeading
        terminate after 3 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    sim = simulator.simulate(scene)
    initial_heading = sim.result.records["InitialHeading"]
    final_heading = sim.result.records["FinalHeading"]
    assert (
        initial_heading > final_heading
    ), "Positive steer should turn right (heading must decrease)."


def test_composed_scenario(getMetadriveSimulator):
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'
        model scenic.simulators.metadrive.model

        scenario Sub():
            setup:
                other = new Car at (190, -196), with behavior FollowLaneBehavior()
                terminate after 3 steps

        scenario Main():
            setup:
                ego = new Car at (129, -196), with behavior FollowLaneBehavior()
            compose:
                do Sub()
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    traj = simulation.result.trajectory

    assert len(traj[0]) == 2, f"expected 2 objects, got {len(traj[0])}"
    assert traj[0][0] != traj[-1][0], f"ego car did not move."
    assert traj[0][1] != traj[-1][1], f"subscenario car did not move."


def test_render_2D_saves_gif(getMetadriveSimulator, tmp_path):
    outdir = tmp_path / "md_gifs"
    outdir.mkdir()

    simulator, openDrivePath, sumoPath = getMetadriveSimulator(
        "Town01",
        render=True,
        screen_record=True,
        screen_record_filename="render2d.gif",
        screen_record_path=str(outdir),
    )

    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        ego = new Car at (30, 2)
        terminate after 2 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulator.simulate(scene)

    assert (outdir / "render2d.gif").exists()


def test_follow_lane(getMetadriveSimulator):
    # Exercise MetaDrive's getLaneFollowingControllers via FollowLaneBehavior:
    # car should stay on a lane and actually accelerate.
    simulator, openDrivePath, sumoPath = getMetadriveSimulator("Town01")
    code = f"""
        param map = r'{openDrivePath}'
        param sumo_map = r'{sumoPath}'

        model scenic.simulators.metadrive.model

        ego = new Car with behavior FollowLaneBehavior(target_speed=8)

        record final (ego._lane is not None) as OnLane
        record final ego.speed as FinalSpeed
        terminate after 8 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario, maxIterations=1000)
    simulation = simulator.simulate(scene)
    assert simulation.result.records[
        "OnLane"
    ], "Vehicle left the lane under FollowLaneBehavior."
    assert (
        simulation.result.records["FinalSpeed"] > 0.2
    ), "Vehicle did not accelerate along the lane."
