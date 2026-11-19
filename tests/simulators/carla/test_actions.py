from importlib.metadata import version
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import pytest

try:
    import carla

    from scenic.simulators.carla import CarlaSimulator
except ModuleNotFoundError:
    pytest.skip("carla package not installed", allow_module_level=True)

from tests.utils import compileScenic, sampleScene

carla_pkg_version = version("carla")
is_carla_0_10 = carla_pkg_version.startswith("0.10")


def checkCarlaPath():
    CARLA_ROOT = os.environ.get("CARLA_ROOT")
    if not CARLA_ROOT:
        pytest.skip("CARLA_ROOT env variable not set.")
    path = Path(CARLA_ROOT)
    if not path.exists():
        pytest.skip("CARLA_ROOT set to nonexistent folder")
    return path


def isCarlaServerRunning(host="localhost", port=2000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError):
            return False


@pytest.fixture(scope="package")
def getCarlaSimulator(getAssetPath):
    carla_process = None
    if not isCarlaServerRunning():
        CARLA_ROOT = checkCarlaPath()
        # decide which startup script to use
        ue_script = (
            "CarlaUnreal.sh"
            if (CARLA_ROOT / "CarlaUnreal.sh").exists()
            else "CarlaUE4.sh"
        )
        # and which binary to kill later
        exec_name = (
            "CarlaUnreal-Linux-Shipping"
            if ue_script == "CarlaUnreal.sh"
            else "CarlaUE4-Linux-Shipping"
        )

        carla_process = subprocess.Popen(
            f"bash {CARLA_ROOT / ue_script} -RenderOffScreen",
            shell=True,
        )

        # CARLA 0.10.0 can take up to 10 minutes to start on the first launch in CI
        for _ in range(900):
            if isCarlaServerRunning():
                break
            time.sleep(1)
        else:
            pytest.fail("Unable to connect to CARLA.")

        # Extra 10 seconds to ensure server startup
        time.sleep(10)

    base = getAssetPath("maps/CARLA")

    # CARLA 0.10.0 only works with Town10HD_Opt
    def _getCarlaSimulator(town=None):
        if town is None:
            town = "Town10HD_Opt" if is_carla_0_10 else "Town01"
        path = os.path.join(base, f"{town}.xodr")
        simulator = CarlaSimulator(map_path=path, carla_map=town, timeout=180)
        return simulator, town, path

    yield _getCarlaSimulator

    if carla_process:
        subprocess.run(f"killall -9 {exec_name}", shell=True)


def test_throttle(getCarlaSimulator):
    simulator, town, mapPath = getCarlaSimulator()
    code = f"""
        param map = r'{mapPath}'
        param carla_map = '{town}'
        param time_step = 1.0/10

        model scenic.simulators.carla.model

        behavior DriveWithThrottle():
            while True:
                take SetThrottleAction(1)

        ego = new Car at (2, -17), with behavior DriveWithThrottle
        record ego.speed as CarSpeed
        terminate after 5 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    records = simulation.result.records["CarSpeed"]
    assert records[len(records) // 2][1] < records[-1][1]


def test_brake(getCarlaSimulator):
    simulator, town, mapPath = getCarlaSimulator()
    code = f"""
        param map = r'{mapPath}'
        param carla_map = '{town}'
        param time_step = 1.0/10

        model scenic.simulators.carla.model

        behavior DriveWithThrottle():
            while True:
                take SetThrottleAction(1)

        behavior Brake():
            while True:
                take SetThrottleAction(0), SetBrakeAction(1)

        behavior DriveThenBrake():
            do DriveWithThrottle() for 2 steps
            do Brake() for 6 steps

        ego = new Car at (2, -17),
            with blueprint 'vehicle.nissan.patrol',
            with behavior DriveThenBrake
        record final ego.speed as CarSpeed
        terminate after 8 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    finalSpeed = simulation.result.records["CarSpeed"]
    assert finalSpeed == pytest.approx(0.0, abs=2e-1)


def test_reverse(getCarlaSimulator):
    simulator, town, mapPath = getCarlaSimulator()
    code = f"""
        param map = r'{mapPath}'
        param carla_map = '{town}'
        param time_step = 1.0/10

        model scenic.simulators.carla.model

        behavior DriveInReverse():
            while True:
                take SetReverseAction(True), SetThrottleAction(1)

        ego = new Car at (2, -17), with behavior DriveInReverse
        record initial ego.heading as Heading
        record final ego.velocity as Vel
        terminate after 5 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    h = simulation.result.records["Heading"]
    fwd_x, fwd_y = -math.sin(h), math.cos(h)
    vx, vy, _ = simulation.result.records["Vel"]
    proj = vx * fwd_x + vy * fwd_y
    assert proj < -0.02, f"Expected reverse velocity (negative proj), got {proj}"


def test_steer(getCarlaSimulator):
    simulator, town, mapPath = getCarlaSimulator()
    code = f"""
        param map = r'{mapPath}'
        param carla_map = '{town}'
        param time_step = 1.0/10

        model scenic.simulators.carla.model

        behavior TurnRight():
            while True:
                take SetThrottleAction(0.5), SetSteerAction(1)

        # Ego facing west
        ego = new Car at (2, -17), with behavior TurnRight

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


def test_track_waypoints(getCarlaSimulator):
    simulator, town, mapPath = getCarlaSimulator()
    target_speed = 6.0
    if is_carla_0_10:
        waypoints = [(62, 68), (52, 68), (42, 68)]
    else:
        waypoints = [(-2, -13), (-2, -23), (-2, -33)]

    code = f"""
        param map = r'{mapPath}'
        param carla_map = '{town}'
        param time_step = 1.0/10

        model scenic.simulators.carla.model

        # Short straight segment, starting from a known-good spawn point.
        waypoints = {waypoints}

        behavior FollowPath():
            while True:
                take TrackWaypointsAction(waypoints, cruising_speed={target_speed})

        ego = new Car at waypoints[0],
            with behavior FollowPath

        record initial (distance from ego to waypoints[-1]) as InitialDist
        record final (distance from ego to waypoints[-1]) as FinalDist
        record final ego.speed as FinalSpeed

        terminate after 20 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    sim = simulator.simulate(scene)

    initial_dist = sim.result.records["InitialDist"]
    final_dist = sim.result.records["FinalDist"]
    final_speed = sim.result.records["FinalSpeed"]

    assert final_dist < initial_dist

    # CARLA 0.10 uses different UE5 vehicle physics, so vehicles accelerate more
    # slowly in this scenario than in CARLA 0.9.x. For 0.10, only require
    # meaningful forward motion rather than reaching the old cruising-speed band.
    if is_carla_0_10:
        assert final_speed > 3.0
    else:
        assert final_speed == pytest.approx(target_speed, abs=2.0)
