import pytest

try:
    import carla
except ModuleNotFoundError:
    pytest.skip("carla package not installed", allow_module_level=True)

from test_actions import getCarlaSimulator

from scenic.simulators.carla import blueprints as bp
from tests.utils import compileScenic, sampleScene

# Known-good spawn points for the CARLA blueprint tests:
# - CARLA 0.10.0 uses Town10HD_Opt
# - CARLA 0.9.x uses Town01
BLUEPRINT_TEST_SPAWNS = {
    "Town10HD_Opt": (-103, 37.6),
    "Town01": (369, -326),
}

# Map class name -> ids dict key
CATEGORY_TO_CLASS = {
    "carModels": "Car",
    "bicycleModels": "Bicycle",
    "motorcycleModels": "Motorcycle",
    "truckModels": "Truck",
    "vanModels": "Van",
    "busModels": "Bus",
    "trashModels": "Trash",
    "coneModels": "Cone",
    "debrisModels": "Debris",
    "vendingMachineModels": "VendingMachine",
    "chairModels": "Chair",
    "busStopModels": "BusStop",
    "advertisementModels": "Advertisement",
    "garbageModels": "Garbage",
    "containerModels": "Container",
    "tableModels": "Table",
    "barrierModels": "Barrier",
    "plantpotModels": "PlantPot",
    "mailboxModels": "Mailbox",
    "gnomeModels": "Gnome",
    "creasedboxModels": "CreasedBox",
    "caseModels": "Case",
    "boxModels": "Box",
    "benchModels": "Bench",
    "barrelModels": "Barrel",
    "atmModels": "ATM",
    "kioskModels": "Kiosk",
    "ironplateModels": "IronPlate",
    "trafficwarningModels": "TrafficWarning",
    "walkerModels": "Pedestrian",
}

# Build the (modelType, modelName) pairs from bp.ids
PARAMS = [
    (model_type, model_name)
    for key, model_type in CATEGORY_TO_CLASS.items()
    for model_name in bp.ids.get(key, [])  # empty lists are fine; they just add no params
]


def model_blueprint(simulator, mapPath, town, modelType, modelName):
    spawn = BLUEPRINT_TEST_SPAWNS[town]
    code = f"""
        param map = r'{mapPath}'
        param carla_map = '{town}'
        param time_step = 1.0/10

        model scenic.simulators.carla.model
        ego = new {modelType} at {spawn},
              with blueprint '{modelName}',
              with regionContainedIn None
        terminate after 1 steps
    """
    scenario = compileScenic(code, mode2D=True)
    scene = sampleScene(scenario)
    simulation = simulator.simulate(scene)
    obj = simulation.objects[0]
    assert obj.blueprint == modelName


@pytest.mark.parametrize("modelType, modelName", PARAMS)
def test_model_blueprints(getCarlaSimulator, modelType, modelName):
    simulator, town, mapPath = getCarlaSimulator()
    model_blueprint(simulator, mapPath, town, modelType, modelName)
