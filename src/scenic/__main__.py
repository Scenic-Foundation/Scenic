### Top-level functionality of the scenic package as a script:
### load a scenario and generate scenes in an infinite loop.

import argparse
from importlib import metadata
import random
import sys
import time
import warnings

import numpy

import scenic
from scenic.core.distributions import RejectionException
import scenic.core.errors as errors
from scenic.core.simulators import SimulationCreationError
import scenic.syntax.translator as translator

parser = argparse.ArgumentParser(
    prog="scenic",
    add_help=False,
    usage="scenic [-h | --help] [options] FILE [options]",
    description="Sample from a Scenic scenario, optionally "
    "running dynamic simulations.",
)

mainOptions = parser.add_argument_group("main options")
mainOptions.add_argument(
    "-S",
    "--simulate",
    action="store_true",
    help="run dynamic simulations from scenes "
    "instead of simply showing diagrams of scenes",
)
mainOptions.add_argument("-s", "--seed", help="random seed", type=int)
mainOptions.add_argument(
    "-v",
    "--verbosity",
    help="verbosity level (default 1)",
    type=int,
    choices=(0, 1, 2, 3),
    default=1,
)
mainOptions.add_argument(
    "-p",
    "--param",
    help="override a global parameter",
    nargs=2,
    default=[],
    action="append",
    metavar=("PARAM", "VALUE"),
)
mainOptions.add_argument(
    "--count",
    help="number of successful scenes to generate or simulations to run (default infinity)",
    type=int,
    default=0,
)
mainOptions.add_argument(
    "-m", "--model", help="specify a Scenic world model", default=None
)
mainOptions.add_argument(
    "--scenario", default=None, help="name of scenario to run (if file contains multiple)"
)
mainOptions.add_argument(
    "--2d", default=True, action="store_true", help="run Scenic in 2D compatibility mode"
)

# Simulation options
simOpts = parser.add_argument_group("dynamic simulation options")
simOpts.add_argument(
    "--time", help="time bound for simulations (default none)", type=int, default=None
)

simOpts.add_argument(
    "--max-sims-per-scene",
    type=int,
    default=1,
    metavar="N",
    help="max # of rejected simulations before sampling a new scene (default 1)",
)

# Interactive rendering options
intOptions = parser.add_argument_group("static scene diagramming options")
intOptions.add_argument(
    "-d",
    "--delay",
    type=float,
    help="loop automatically with this delay (in seconds) "
    "instead of waiting for the user to close the diagram",
)
intOptions.add_argument(
    "-z",
    "--zoom",
    type=float,
    default=1,
    help="zoom expansion factor, or 0 to show the whole workspace (default 1)",
)
intOptions.add_argument(
    "--axes", help="display the global coordinate axes", action="store_true"
)

# Debugging options
debugOpts = parser.add_argument_group("debugging options")
debugOpts.add_argument(
    "--show-params", help="show values of global parameters", action="store_true"
)
debugOpts.add_argument(
    "--show-records", help="show values of recorded expressions", action="store_true"
)
debugOpts.add_argument(
    "-b", "--full-backtrace", help="show full internal backtraces", action="store_true"
)
debugOpts.add_argument(
    "--pdb",
    action="store_true",
    help='enter interactive debugger on errors (implies "-b")',
)
debugOpts.add_argument(
    "--pdb-on-reject",
    action="store_true",
    help='enter interactive debugger on rejections (implies "-b")',
)
ver = metadata.version("scenic")
debugOpts.add_argument(
    "--version",
    action="version",
    version=f"Scenic {ver}",
    help="print Scenic version information and exit",
)
debugOpts.add_argument("--dump-scenic-ast", help="dump Scenic AST", action="store_true")
debugOpts.add_argument("--dump-ast", help="dump final AST", action="store_true")
debugOpts.add_argument(
    "--dump-python", help="dump Python equivalent of final AST", action="store_true"
)
debugOpts.add_argument("--no-pruning", help="disable pruning", action="store_true")
debugOpts.add_argument(
    "--gather-stats",
    type=int,
    metavar="N",
    help="collect timing statistics over this many scenes"
    " (or iterations, if negative)",
)

parser.add_argument(
    "-h", "--help", action="help", default=argparse.SUPPRESS, help=argparse.SUPPRESS
)

# Positional arguments
parser.add_argument("scenicFile", help="a Scenic file to run", metavar="FILE")

# Parse arguments and set up configuration
args = parser.parse_args()
delay = args.delay
mode2D = getattr(args, "2d")

if not mode2D:
    if args.delay is not None:
        warnings.warn("Delay parameter is not supported by the 3D viewer.")
    if args.zoom != 1:
        warnings.warn("Zoom parameter is not supported by the 3D viewer.")

scenic.setDebuggingOptions(
    verbosity=args.verbosity,
    fullBacktrace=args.full_backtrace,
    debugExceptions=args.pdb,
    debugRejections=args.pdb_on_reject,
)
params = {}
for name, value in args.param:
    # Convert params to ints or floats if possible
    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            pass
    params[name] = value
translator.dumpScenicAST = args.dump_scenic_ast
translator.dumpFinalAST = args.dump_ast
translator.dumpASTPython = args.dump_python
translator.usePruning = not args.no_pruning
if args.seed is not None:
    if args.verbosity >= 1:
        print(f"Using random seed = {args.seed}")

    random.seed(args.seed)
    numpy.random.seed(args.seed)

# Load scenario from file
if args.verbosity >= 1:
    print("Beginning scenario construction...")
startTime = time.time()
scenario = errors.callBeginningScenicTrace(
    lambda: translator.scenarioFromFile(
        args.scenicFile,
        params=params,
        model=args.model,
        scenario=args.scenario,
        mode2D=mode2D,
    )
)
totalTime = time.time() - startTime
if args.verbosity >= 1:
    print(f"Scenario constructed in {totalTime:.2f} seconds.")

if args.simulate:
    simulator = errors.callBeginningScenicTrace(scenario.getSimulator)


def generateScene(maxIterations=2000):
    startTime = time.time()
    scene, iterations = errors.callBeginningScenicTrace(
        lambda: scenario.generate(maxIterations=maxIterations, verbosity=args.verbosity)
    )
    if args.verbosity >= 1:
        totalTime = time.time() - startTime
        print(f"  Generated scene in {iterations} iterations, {totalTime:.4g} seconds.")
        if args.show_params:
            for param, value in scene.params.items():
                print(f'    Parameter "{param}": {value}')
    return scene, iterations


def runSimulation(scene, sceneCount):
    startTime = time.time()
    if args.verbosity >= 1:
        print(f"  Beginning simulation of {scene.dynamicScenario}...")
    try:
        simulation = errors.callBeginningScenicTrace(
            lambda: simulator.simulate(
                scene,
                maxSteps=args.time,
                name=str(sceneCount),
                verbosity=args.verbosity,
                maxIterations=args.max_sims_per_scene,
            )
        )
    except SimulationCreationError as e:
        if args.verbosity >= 1:
            print(f"  Failed to create simulation: {e}")
        return False
    if args.verbosity >= 1:
        totalTime = time.time() - startTime
        print(f"  Ran simulation in {totalTime:.4g} seconds.")
    if simulation and args.show_records:
        for name, value in simulation.result.records.items():
            if isinstance(value, list):
                print(f'    Record "{name}": (time series)')
                for step, subval in value:
                    print(f"      {step:4d}: {subval}")
            else:
                print(f'    Record "{name}": {value}')
    return simulation is not None


try:
    if args.gather_stats is None:
        # Generate scenes interactively until killed/count reached
        if not args.simulate:  # will need matplotlib to draw scene schematic
            import matplotlib
            import matplotlib.pyplot as plt

            if matplotlib.get_backend().lower() == "agg":
                raise RuntimeError(
                    "need an interactive matplotlib backend to display scenes\n"
                    "(try installing python3-tk)"
                )

        sceneCount = 0
        successCount = 0
        while True:
            scene, _ = generateScene()
            sceneCount += 1
            if args.simulate:
                success = runSimulation(scene, sceneCount)
                if success:
                    successCount += 1
            else:
                successCount += 1
                if mode2D:
                    if delay is None:
                        scene.show2D(zoom=args.zoom)
                    else:
                        scene.show2D(zoom=args.zoom, block=False)
                        plt.pause(delay)
                        plt.clf()
                else:
                    scene.show(axes=args.axes)

            if 0 < args.count <= successCount:
                break

    else:  # Gather statistics over the specified number of scenes/iterations
        its = []
        maxIterations = 2000
        iterations = 0
        totalIterations = 0
        if args.gather_stats >= 0:  # scenes

            def keepGoing():
                return len(its) < args.gather_stats

        else:  # iterations
            maxIterations = -args.gather_stats

            def keepGoing():
                global maxIterations
                maxIterations -= iterations
                return maxIterations > 0

        startTime = time.time()
        while keepGoing():
            try:
                scene, iterations = generateScene(maxIterations=maxIterations)
            except RejectionException:
                if args.gather_stats >= 0:
                    raise
                iterations = maxIterations
            else:
                its.append(iterations)
            totalIterations += iterations
        totalTime = time.time() - startTime

        count = len(its) if its else float("nan")
        print(f"Sampled {len(its)} scenes in {totalTime:.2f} seconds.")
        print(f"Average iterations/scene: {totalIterations/count}")
        print(f"Average time/iteration: {totalTime/totalIterations:.2g} seconds.")
        print(f"Average time/scene: {totalTime/count:.2f} seconds.")

except KeyboardInterrupt:
    pass

finally:
    if args.simulate:
        simulator.destroy()


def dummy():  # for the 'scenic' entry point to call after importing this module
    pass
