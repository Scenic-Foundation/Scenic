import pytest

from scenic.domains.driving.openscenario import toOpenScenario
from scenic.simulators.newtonian import NewtonianSimulator
from tests.utils import compileScenic

try:
    import scenariogeneration
except ModuleNotFoundError:
    pytest.skip("scenariogeneration package not installed", allow_module_level=True)


def test_xosc_export(getAssetPath):
    simulator = NewtonianSimulator("Town01")
    code = """
        param render = False
        model scenic.simulators.newtonian.driving_model

        ego = new Car with behavior FollowLaneBehavior()

        immobileCar = new Car visible

        behavior Walk():
            take SetWalkingSpeedAction(1)
        
        new Pedestrian behind ego by 5,
            with regionContainedIn None,
            with behavior Walk()
    """

    scenario = compileScenic(
        code, mode2D=True, params={"map": getAssetPath("maps/CARLA/Town01.xodr")}
    )
    scene, _ = scenario.generate()
    simulation = simulator.simulate(scene, maxSteps=50)
    toOpenScenario(simulation, scenario, scene)


def test_xosc_export_dynamic_objects(getAssetPath):
    simulator = NewtonianSimulator("Town01")
    code = """
        param render = False
        model scenic.simulators.newtonian.driving_model

        scenario SpawnCar():
            setup:
                new Car at 0@0

        scenario Main():
            setup:
                ego = new Car

            compose:
                wait for 1 seconds
                do SpawnCar()
    """
    scenario = compileScenic(
        code, mode2D=True, params={"map": getAssetPath("maps/CARLA/Town01.xodr")}
    )
    scene, _ = scenario.generate()
    simulation = simulator.simulate(scene, maxSteps=50)
    with pytest.raises(RuntimeError, match="(.*)dynamically created objects(.*)"):
        toOpenScenario(simulation, scenario, scene)
