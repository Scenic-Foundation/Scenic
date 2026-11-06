"""CARLA blueprints for cars, pedestrians, etc."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version
import warnings

from scenic.core.distributions import distributionFunction
from scenic.core.errors import InvalidScenarioError

# Import auto-generated blueprint data for all CARLA versions
from ._blueprintData import _DIMS, _IDS

try:
    _CARLA_VER = _pkg_version("carla")
except PackageNotFoundError:
    _CARLA_VER = "0.0.0"  # no carla package; default to newest known blueprints


def _verkey(s: str):
    # Handle '0.9.15', '0.10.0', '1.2' -> (major, minor, patch)
    parts = [int(p) for p in s.split(".")]
    parts += [0] * (3 - len(parts))
    return tuple(parts[:3])


def _pick(vermap, ver):
    """Choose the blueprint map for CARLA version"""
    # 1) Exact match
    if ver in vermap:
        return vermap[ver]
    # 2) If same major.minor, use the newest patch.
    mm = ".".join(ver.split(".")[:2])
    cands = [v for v in vermap if v.startswith(mm + ".")]
    if cands:
        best = max(cands, key=_verkey)
        return vermap[best]
    # 3) Otherwise, use the newest version.
    best = max(vermap.keys(), key=_verkey)
    if ver != "0.0.0":
        warnings.warn(
            f"Unknown CARLA version {ver}; using blueprints for {best}. "
            "Scenic may not have the correct set of blueprints."
        )
    return vermap[best]


oldBlueprintNames = {
    # Map current names to legacy names
    "vehicle.dodge.charger_police": ("vehicle.dodge_charger.police",),
    "vehicle.lincoln.mkz_2017": ("vehicle.lincoln.mkz2017",),
    "vehicle.mercedes.coupe": ("vehicle.mercedes-benz.coupe",),
    "vehicle.mini.cooper_s": ("vehicle.mini.cooperst",),
    "vehicle.ford.mustang": ("vehicle.mustang.mustang",),
}


# Pick blueprint data for current CARLA version
ids = _pick(_IDS, _CARLA_VER)
dims = _pick(_DIMS, _CARLA_VER)


# Backwards-compatible model lists
# Vehicles
carModels = ids["carModels"]
bicycleModels = ids["bicycleModels"]
motorcycleModels = ids["motorcycleModels"]
truckModels = ids["truckModels"]
vanModels = ids["vanModels"]
busModels = ids["busModels"]
# Walkers
walkerModels = ids["walkerModels"]
# Props
trashModels = ids["trashModels"]
coneModels = ids["coneModels"]
debrisModels = ids["debrisModels"]
vendingMachineModels = ids["vendingMachineModels"]
chairModels = ids["chairModels"]
busStopModels = ids["busStopModels"]
advertisementModels = ids["advertisementModels"]
garbageModels = ids["garbageModels"]
containerModels = ids["containerModels"]
tableModels = ids["tableModels"]
barrierModels = ids["barrierModels"]
plantpotModels = ids["plantpotModels"]
mailboxModels = ids["mailboxModels"]
gnomeModels = ids["gnomeModels"]
creasedboxModels = ids["creasedboxModels"]
caseModels = ids["caseModels"]
boxModels = ids["boxModels"]
benchModels = ids["benchModels"]
barrelModels = ids["barrelModels"]
atmModels = ids["atmModels"]
kioskModels = ids["kioskModels"]
ironplateModels = ids["ironplateModels"]
trafficwarningModels = ids["trafficwarningModels"]


def blueprintsInCategory(category):
    """Return all blueprint IDs for a category; raise if none recorded."""
    model = category + "Models"
    models = ids.get(model)
    if models:
        return models
    raise InvalidScenarioError(
        f"Scenic has no '{category}' blueprints recorded for CARLA {_CARLA_VER}."
    )


def _get_dim(bp_id, key, default):
    """Return recorded dimension or ``default`` if missing/0.

    Note: CARLA 0.9.14 bbox returns 0 for some blueprints (see CARLA issue #5841).
    """
    val = dims.get(bp_id, {}).get(key)
    return val if val else default


@distributionFunction
def width(bp_id, default) -> float:
    """Get width for ``bp_id``; return ``default`` if unknown."""
    return _get_dim(bp_id, "width", default)


@distributionFunction
def length(bp_id, default) -> float:
    """Get length for ``bp_id``; return ``default`` if unknown."""
    return _get_dim(bp_id, "length", default)


@distributionFunction
def height(bp_id, default) -> float:
    """Get height for ``bp_id``; return ``default`` if unknown."""
    return _get_dim(bp_id, "height", default)
