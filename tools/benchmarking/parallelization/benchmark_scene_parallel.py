from pathlib import Path
import time
import warnings

import scenic

NUM_WORKERS = 8
BENCHMARKS_BASE_PATH = (Path(__file__).resolve().parent / "benchmarks").resolve()
MAP_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "assets"
    / "maps"
    / "CARLA"
    / "Town05.xodr"
).resolve()
MESH_BASE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "assets" / "meshes"
).resolve()

BENCHMARKS = [
    ("adjacentOpposingPair.scenic", {"mode2D": True, "map": MAP_PATH}),
    ("badlyParkedCarPullingIn.scenic", {"mode2D": True, "map": MAP_PATH}),
    ("bypassing_03.scenic", {"mode2D": True, "map": MAP_PATH}),
    ("city_intersection.scenic", {"meshBasePath": MESH_BASE_PATH}),
    # ("enclosed_occluded.scenic", {}),
    ("enclosed_visible.scenic", {}),
    ("fully_occluded.scenic", {"meshBasePath": MESH_BASE_PATH}),
    ("fully_visible.scenic", {"meshBasePath": MESH_BASE_PATH}),
    ("narrowGoalNew.scenic", {"meshBasePath": MESH_BASE_PATH}),
    ("narrowGoalOld.scenic", {"mode2D": True, "map": MAP_PATH}),
    ("pedestrian_02.scenic", {"mode2D": True, "map": MAP_PATH}),
    ("vacuum.scenic", {"numToys": 0, "meshBasePath": MESH_BASE_PATH}),
    ("vacuum.scenic", {"numToys": 1, "meshBasePath": MESH_BASE_PATH}),
    ("vacuum.scenic", {"numToys": 2, "meshBasePath": MESH_BASE_PATH}),
    ("vacuum.scenic", {"numToys": 4, "meshBasePath": MESH_BASE_PATH}),
    ("vacuum.scenic", {"numToys": 8, "meshBasePath": MESH_BASE_PATH}),
    # ("vacuum.scenic", {"numToys": 16, "meshBasePath": MESH_BASE_PATH}),
]

NUM_SAMPLES = 128


def run_benchmark(path, params):
    scenario = scenic.scenarioFromFile(
        BENCHMARKS_BASE_PATH / path, params=params, mode2D=params.get("mode2D", False)
    )
    for _ in range(NUM_SAMPLES):
        scenario.generate(maxIterations=float("inf"))


def run_benchmark_parallel(path, params, *, numWorkers):
    scenario = scenic.scenarioFromFile(
        BENCHMARKS_BASE_PATH / path, params=params, mode2D=params.get("mode2D", False)
    )
    scenario.generateBatch(NUM_SAMPLES, numWorkers=numWorkers)


if __name__ == "__main__":
    # print("Base Performance (`generate`, numWorkers=0):")
    # for benchmark in BENCHMARKS:
    #     with warnings.catch_warnings():
    #         warnings.simplefilter("ignore")
    #         start = time.time()
    #         run_benchmark(*benchmark)
    #         trial_time = time.time() - start
    #         print(f"{trial_time: 7.2f} | {benchmark}")
    # print()
    # print("Base + Overhead Performance (`generateBatch`, numWorkers=1):")
    # for benchmark in BENCHMARKS:
    #     with warnings.catch_warnings():
    #         warnings.simplefilter("ignore")
    #         start = time.time()
    #         run_benchmark_parallel(*benchmark, numWorkers=1)
    #         trial_time = time.time() - start
    #         print(f"{trial_time: 7.2f} | {benchmark}")
    # print()
    print("Batch Performance (`generateBatch`, numWorkers=8):")
    for benchmark in BENCHMARKS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            run_benchmark_parallel(*benchmark, numWorkers=8)
            trial_time = time.time() - start
            print(f"{trial_time: 7.2f} | {benchmark}")
