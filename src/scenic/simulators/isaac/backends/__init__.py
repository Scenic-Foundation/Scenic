"""Isaac Sim API backends.

Each backend wraps one flavor of the Isaac Sim Python API (the 5.1 Core API,
the 5.1/6.0 Core Experimental APIs, or Isaac Lab) behind the common
`IsaacBackend` interface. Backends are singletons: `getBackend` creates each
one on first use and returns the same instance afterwards, since a backend
owns the running ``SimulationApp``.

Isaac Sim supports only one ``SimulationApp`` per OS process. Since each
backend independently launches its own, using two different backends (e.g.
``core_51`` and ``experimental_60``) within one process crashes the whole
interpreter rather than raising a catchable error. This is normally moot: a
single Isaac Sim install only supports one API generation, so ``auto``
detection (or an explicit, consistent ``isaacBackend`` override) always picks
the same backend for every scenario run in that install. It matters mainly
for test suites or tooling that might otherwise mix explicit backends within
one Python process.
"""

from importlib import import_module
import os

_BACKENDS = {
    "core_51": "scenic.simulators.isaac.backends.core_51:Core51Backend",
    "experimental_51": "scenic.simulators.isaac.backends.experimental_51:Experimental51Backend",
    "experimental_60": "scenic.simulators.isaac.backends.experimental_60:Experimental60Backend",
    "lab": "scenic.simulators.isaac.backends.lab:LabBackend",
}
_INSTANCES = {}

#: Backend chosen for each installed Isaac Sim major version when the
#: ``isaacBackend`` parameter is ``"auto"``.
_VERSION_BACKENDS = {"5": "core_51", "6": "experimental_60"}
#: Backend used when the Isaac Sim version cannot be read (e.g. it is not
#: pip-installed, or Scenic is running outside the Isaac environment).
FALLBACK_BACKEND_NAME = "experimental_60"
DEFAULT_BACKEND_NAME = "auto"


def _majorVersionFromPipMetadata():
    """The installed ``isaacsim`` package's major version, via pip metadata.

    Works for a pip-installed Isaac Sim (as described in the README); raises
    for Isaac Sim's own bundled Python (e.g. ``isaac-sim/python.sh``), which
    has no pip package metadata for ``isaacsim``.
    """
    from importlib.metadata import version

    return version("isaacsim").split(".", 1)[0]


def _majorVersionFromVersionFile():
    """The Isaac Sim install's major version, via its top-level ``VERSION`` file.

    Isaac Sim submodules (e.g. ``isaacsim.core.version``) cannot be imported
    before a ``SimulationApp`` exists, so this looks for the plain-text
    ``VERSION`` file (e.g. ``6.1.0-rc.26+...``) NVIDIA ships at the root of
    every Isaac Sim install, walking up from the ``isaacsim`` package's
    location since that root is not otherwise exposed to Python.
    """
    import isaacsim

    directory = os.path.dirname(os.path.abspath(isaacsim.__file__))
    for _ in range(6):
        version_file = os.path.join(directory, "VERSION")
        if os.path.isfile(version_file):
            with open(version_file) as f:
                return f.read().split(".", 1)[0].strip()
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def detectBackend():
    """Pick a backend from the installed Isaac Sim version."""
    for getMajorVersion in (_majorVersionFromPipMetadata, _majorVersionFromVersionFile):
        try:
            major = getMajorVersion()
        except Exception:
            continue
        if major is not None:
            return _VERSION_BACKENDS.get(major, FALLBACK_BACKEND_NAME)
    return FALLBACK_BACKEND_NAME


def getBackend(name=DEFAULT_BACKEND_NAME):
    """Return the (singleton) backend with the given name.

    ``"auto"`` or `None` selects the backend matching the installed Isaac Sim
    version (see `detectBackend`).
    """
    name = DEFAULT_BACKEND_NAME if name is None else str(name)
    if name == DEFAULT_BACKEND_NAME:
        name = detectBackend()
    if name not in _BACKENDS:
        available = ", ".join(sorted(_BACKENDS))
        raise ValueError(
            f"unknown Isaac backend {name!r}; available backends: {available}"
        )
    if name not in _INSTANCES:
        module_name, class_name = _BACKENDS[name].split(":")
        module = import_module(module_name)
        _INSTANCES[name] = getattr(module, class_name)()
    return _INSTANCES[name]


def articulationAction(**kwargs):
    """Build a backend-independent articulation action.

    An action is a dict which may contain ``joint_positions``,
    ``joint_velocities`` and/or ``joint_efforts``, each paired with the DOF
    indices it applies to (``joint_position_indices`` etc., or a shared
    ``joint_indices``). Backends translate it to their native action type.
    """
    return dict(kwargs)
