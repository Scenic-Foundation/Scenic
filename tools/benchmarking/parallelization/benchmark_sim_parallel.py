from pathlib import Path
import time
import warnings

import scenic
from scenic.core.simulators import SimulatorGroup
from scenic.simulators.metadrive.simulator import MetaDriveSimulator

NUM_WORKERS = 8
BENCHMARKS_BASE_PATH = (Path(__file__).resolve().parent / "benchmarks").resolve()
MAP_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "assets"
    / "maps"
    / "CARLA"
    / "Town05.xodr"
).resolve()
SUMO_MAP_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "assets"
    / "maps"
    / "CARLA"
    / "Town05.net.xml"
).resolve()
MESH_BASE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "assets" / "meshes"
).resolve()

BENCHMARKS = [
    ("badlyParkedCarPullingIn.scenic", {"mode2D": True, "map": MAP_PATH}),
    ("bypassing_03.scenic", {"mode2D": True, "map": MAP_PATH}),
]

NUM_SAMPLES = 128


def run_benchmark(path, params):
    simulator = MetaDriveSimulator(
        xodr_map=MAP_PATH, sumo_map=SUMO_MAP_PATH, render=False, real_time=False
    )
    scenario = scenic.scenarioFromFile(
        BENCHMARKS_BASE_PATH / path, params=params, mode2D=params.get("mode2D", False)
    )
    for _ in range(NUM_SAMPLES):
        scene, _ = scenario.generate(maxIterations=float("inf"))
        simulator.simulate(scene)


def run_benchmark_parallel(path, params, *, numWorkers):
    scenario = scenic.scenarioFromFile(
        BENCHMARKS_BASE_PATH / path, params=params, mode2D=params.get("mode2D", False)
    )
    scene_stream = scenario.generateStream(
        NUM_SAMPLES, numWorkers=numWorkers, serialized=True
    )
    sim_group = SimulatorGroup(
        numWorkers=numWorkers,
        simulatorClass=MetaDriveSimulator,
        simulatorParams={
            "xodr_map": MAP_PATH,
            "sumo_map": SUMO_MAP_PATH,
            "render": False,
            "real_time": False,
        },
    )
    sim_group.simulateBatch(scenario=scenario, scenes=scene_stream)


if __name__ == "__main__":
    print("Base Performance (`generate`, numWorkers=0):")
    for benchmark in BENCHMARKS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            run_benchmark(*benchmark)
            trial_time = time.time() - start
            print(f"{trial_time: 7.2f} | {benchmark}")
    print()
    print("Base + Overhead Performance (`generateBatch`, numWorkers=1):")
    for benchmark in BENCHMARKS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            run_benchmark_parallel(*benchmark, numWorkers=1)
            trial_time = time.time() - start
            print(f"{trial_time: 7.2f} | {benchmark}")
    print()
    print("Batch Performance (`generateBatch`, numWorkers=8):")
    for benchmark in BENCHMARKS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            run_benchmark_parallel(*benchmark, numWorkers=8)
            trial_time = time.time() - start
            print(f"{trial_time: 7.2f} | {benchmark}")
