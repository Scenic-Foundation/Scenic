"""Translator turning Scenic programs into Scenario objects.

The top-level interface to Scenic is provided by two functions:

* `scenarioFromString` -- compile a string of Scenic code;
* `scenarioFromFile` -- compile a Scenic file.

These output a `Scenario` object, from which scenes can be generated.
See the documentation for `Scenario` for details.

When imported, this module hooks the Python import system in order to implement
the :keyword:`import` statement. This is only for the compiler's own use: it is
not allowed to import a Scenic module from Python, and attempting to do so will
fail with a `ModuleNotFoundError`.

Scenic is compiled in two main steps: translating the code into Python, and
executing the resulting Python module to generate a Scenario object encoding
the objects, distributions, etc. in the scenario. For details, see the function
`compileStream` below.
"""

import ast
import builtins
from contextlib import contextmanager
import dataclasses
import hashlib
import importlib
import importlib.abc
import importlib.util
import inspect
import io
import os
import sys
import time
import types
from typing import Optional

from scenic.core.distributions import RejectionException, toDistribution
from scenic.core.dynamics.scenarios import DynamicScenario
import scenic.core.errors as errors
from scenic.core.errors import InvalidScenarioError, PythonCompileError
from scenic.core.lazy_eval import needsLazyEvaluation
import scenic.core.pruning as pruning
from scenic.core.serialization import deterministicHash
from scenic.core.utils import cached_property
from scenic.syntax.compiler import compileScenicAST
from scenic.syntax.parser import parse_string
import scenic.syntax.veneer as veneer

### THE TOP LEVEL: compiling a Scenic program


@dataclasses.dataclass
class CompileOptions:
    """Internal class for capturing options used when compiling a scenario."""

    # N.B. update `_hashMapping` below when adding a new field

    #: Whether or not the scenario uses `2D compatibility mode`.
    mode2D: bool = False
    #: Overridden world model, if any.
    modelOverride: Optional[str] = None
    #: Overridden global parameters.
    paramOverrides: dict = dataclasses.field(default_factory=dict)
    #: Selected modular scenario, if any.
    scenario: Optional[str] = None

    def _hashMapping(self):
        mapping = {"mode2D": self.mode2D}
        if self.modelOverride:
            mapping["modelOverride"] = self.modelOverride
        if self.scenario:
            mapping["scenario"] = self.scenario
        for k, v in self.paramOverrides.items():
            mapping[f"param:{k}"] = v
        return mapping

    @cached_property
    def hash(self):
        """Deterministic hash saved in serialized scenes to catch option mismatches."""
        return deterministicHash(self._hashMapping(), digest_size=4)


def scenarioFromString(
    string,
    params={},
    model=None,
    scenario=None,
    *,
    filename="<string>",
    mode2D=False,
    **kwargs,
):
    """Compile a string of Scenic code into a `Scenario`.

    The optional **filename** is used for error messages.
    Other arguments are as in `scenarioFromFile`.
    """
    stream = io.BytesIO(string.encode())
    options = CompileOptions(modelOverride=model, paramOverrides=params, mode2D=mode2D)
    return _scenarioFromStream(stream, options, filename, scenario=scenario, **kwargs)


def scenarioFromFile(
    path, params={}, model=None, scenario=None, *, mode2D=False, **kwargs
):
    """Compile a Scenic file into a `Scenario`.

    Args:
        path (str): Path to a Scenic file.
        params (dict): :term:`Global parameters` to override, as a dictionary mapping
          parameter names to their desired values.
        model (str): Scenic module to use as :term:`world model`.
        scenario (str): If there are multiple :term:`modular scenarios` in the
          file, which one to compile; if not specified, a scenario called 'Main'
          is used if it exists.
        mode2D (bool): Whether to compile this scenario in `2D compatibility mode`.

    Returns:
        A `Scenario` object representing the Scenic scenario.

    Note for Scenic developers: this function accepts additional keyword
    arguments which are intended for internal use and debugging only.
    See `_scenarioFromStream` for details.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    fullpath = os.path.realpath(path)
    head, extension = os.path.splitext(fullpath)
    if not extension or extension not in scenicExtensions:
        ok = ", ".join(scenicExtensions)
        err = f"Scenic scenario does not have valid extension ({ok})"
        raise RuntimeError(err)
    directory, name = os.path.split(head)

    options = CompileOptions(modelOverride=model, paramOverrides=params, mode2D=mode2D)
    with open(path, "rb") as stream:
        return _scenarioFromStream(
            stream, options, fullpath, scenario=scenario, path=path, **kwargs
        )


def _scenarioFromStream(
    stream, compileOptions, filename, *, scenario=None, path=None, _cacheImports=False
):
    """Compile a stream of Scenic code into a `Scenario`.

    This method is not meant to be called directly by users of Scenic. Use the
    top-level functions `scenarioFromFile` and `scenarioFromString` instead.

    These functions also accept the following keyword arguments, which are
    intended for internal use and debugging only. They should be considered
    unstable and are subject to modification or removal at any time.

    Args:
        _cacheImports (bool): Whether to cache any imported Scenic modules.
          The default behavior is to not do this, so that subsequent attempts
          to import such modules will cause them to be recompiled. If it is
          safe to cache Scenic modules across multiple compilations, set this
          argument to True. Then importing a Scenic module will have the same
          behavior as importing a Python module. See `purgeModulesUnsafeToCache`
          for a more detailed discussion of the internals behind this.
    """
    # Compile the code as if it were a top-level module
    oldModules = list(sys.modules.keys())
    try:
        with topLevelNamespace(path) as namespace:
            veneer.activate(compileOptions, namespace)
            compileStream(stream, namespace, compileOptions, filename, activate=False)
        # Construct a Scenario from the resulting namespace
        return constructScenarioFrom(namespace, scenario)
    finally:
        veneer.deactivate()
        if not _cacheImports:
            purgeModulesUnsafeToCache(oldModules)


@contextmanager
def topLevelNamespace(path=None):
    """Creates an environment like that of a Python script being run directly.

    Specifically, __name__ is '__main__', __file__ is the path used to invoke
    the script (not necessarily its absolute path), and the parent directory is
    added to the path so that 'import blobbo' will import blobbo from that
    directory if it exists there.
    """
    directory = os.getcwd() if path is None else os.path.dirname(path)
    namespace = {"__name__": "__main__"}
    if path is not None:
        namespace["__file__"] = path
    sys.path.insert(0, directory)
    try:
        yield namespace
    finally:
        # Remove directory from sys.path, being a little careful in case the
        # Scenic program modified it (unlikely but possible).
        try:
            sys.path.remove(directory)
        except ValueError:
            pass


def purgeModulesUnsafeToCache(oldModules):
    """Uncache loaded modules which should not be kept after compilation.

    Keeping Scenic modules in `sys.modules` after compilation will cause
    subsequent attempts at compiling the same module to reuse the compiled
    scenario: this is usually not what is desired, since compilation can depend
    on external state (in particular overridden global parameters, used e.g. to
    specify the map for driving domain scenarios).

    Args:
        oldModules: List of names of modules loaded before compilation. These
            will be skipped.
    """
    toRemove = []
    # copy sys.modules in case it mutates during iteration (actually happens!)
    for name, module in sys.modules.copy().items():
        if isinstance(module, ScenicModule) and name not in oldModules:
            toRemove.append(name)
    for name in toRemove:
        parent, _, child = name.rpartition(".")
        parent = sys.modules.get(parent)
        if parent:
            # Remove reference to purged module from parent module. This is necessary
            # so that future imports of the purged module will properly refer to the
            # newly-loaded version of it. See below for a long disquisition on this.
            del parent.__dict__[child]

            # Here are details on why the above line is necessary and the sorry history
            # of my attempts to fix this type of bug (hopefully this note will prevent
            # further self-sabotage). Suppose we have a Python package 'package'
            # with a Scenic submodule 'submodule'. A Scenic program with the line
            #   from package import submodule
            # will import 2 packages, namely package and package.submodule, when first
            # compiled. We will then purge package.submodule from sys.modules, but not
            # package, since it is an ordinary module. So if the program is compiled a
            # second time, the line above will NOT import package.submodule, but simply
            # access the attribute 'submodule' of the existing package 'package'. So the
            # reference to the old version of package.submodule will leak out.
            # (An alternative approach, which I used to use, would be to purge all
            # modules containing even indirect references to Scenic modules, but this
            # opens a can of worms: the implementation of
            #   import parent.child
            # does not set the 'child' attribute of 'parent' if 'parent.child' is already
            # in sys.modules, violating an invariant that Python expects [see
            # https://docs.python.org/3/reference/import.html#submodules] and leading to
            # confusing errors. So if parent is purged because it has some child which is
            # a Scenic module, *all* of its children must then be purged. Since the
            # scenic module itself can contain indirect references to Scenic modules (the
            # world models), this means we have to purge the entire scenic package. But
            # then whoever did 'import scenic' at the top level will be left with a
            # reference to the old version of the Scenic module.)
            #
            # 2023 update: after hitting yet another bug caused by a reference to a
            # Scenic module surviving the purge, I've decided to completely ban importing
            # Scenic modules from Python (except when building the documentation). Any
            # objects needed in both Python and Scenic modules should be defined in a
            # Python module and imported from there.
        del sys.modules[name]


def compileStream(stream, namespace, compileOptions, filename, activate=True):
    """Compile a stream of Scenic code and execute it in a namespace.

    The compilation procedure consists of the following main steps:

        1. Parse the Scenic code into a Scenic AST using the parser generated
           by ``pegen`` from :file:`scenic.gram`.
        2. Compile the Scenic AST into a Python AST with the desired semantics.
           This is done by the compiler, `scenic.syntax.compiler`.
        3. Compile and execute the Python AST.
        4. Extract the global state (e.g. objects).
           This is done by the `storeScenarioStateIn` function.
    """
    if errors.verbosityLevel >= 2:
        veneer.verbosePrint(f"  Compiling Scenic module from {filename}...")
        startTime = time.time()

    if activate:
        veneer.activate(compileOptions, namespace)

    try:
        # Execute preamble
        exec(compile(preamble, "<veneer>", "exec"), namespace)
        namespace[namespaceReference] = namespace

        # Parse the source
        source = stream.read().decode("utf-8")
        scenic_tree = parse_string(source, "exec", filename=filename)

        if dumpScenicAST:
            print(f"### Begin Scenic AST of {filename}")
            print(dump(scenic_tree, include_attributes=False, indent=4))
            print("### End Scenic AST")

        # Compile the Scenic AST into a Python AST
        tree, requirements = compileScenicAST(scenic_tree, filename=filename)
        astHasher = hashlib.blake2b(digest_size=4)
        astHasher.update(ast.dump(tree).encode())

        if dumpFinalAST:
            print(f"### Begin final AST of {filename}")
            print(dump(tree, include_attributes=True, indent=4))
            print("### End final AST")

        pythonSource = astToSource(tree)
        if dumpASTPython:
            if pythonSource is None:
                raise RuntimeError(
                    "dumping the Python equivalent of the AST"
                    " requires the astor package"
                )
            print(f"### Begin Python equivalent of final AST of {filename}")
            print(pythonSource)
            print("### End Python equivalent of final AST")

        # Compile the Python AST tree
        code = compileTranslatedTree(tree, filename)

        # Execute it
        executeCodeIn(code, namespace)

        # Extract scenario state from veneer and store it
        astHash = astHasher.digest()
        storeScenarioStateIn(namespace, requirements, astHash, compileOptions)
    finally:
        if activate:
            veneer.deactivate()

    if errors.verbosityLevel >= 2:
        totalTime = time.time() - startTime
        veneer.verbosePrint(f"  Compiled Scenic module in {totalTime:.4g} seconds.")
    return code, pythonSource


def dump(
    node: ast.AST,
    annotate_fields: bool = True,
    include_attributes: bool = False,
    *,
    indent: int,
):
    if sys.version_info >= (3, 9):
        print(ast.dump(node, annotate_fields, include_attributes, indent=indent))
    else:
        # omit `indent` if not supported
        print(ast.dump(node, annotate_fields, include_attributes))


def astToSource(tree: ast.AST):
    if sys.version_info >= (3, 9):
        return ast.unparse(tree)
    try:
        import astor
    except ModuleNotFoundError:
        return None
    return astor.to_source(tree)


### TRANSLATION PHASE ZERO: definitions of language elements not already in Python

## Options

dumpScenicAST = False
dumpFinalAST = False
dumpASTPython = False
usePruning = True

## Preamble
# (included at the beginning of every module to be translated;
# imports the implementations of the public language features)
preamble = """\
from scenic.syntax.veneer import *
"""

## Get Python names of various elements
## (for checking consistency between the translator and the veneer)

api = set(veneer.__all__)

namespaceReference = "_Scenic_module_namespace"  # used in the implementation of 'model'

### TRANSLATION PHASE ONE: handling imports

## Loader for Scenic files, producing ScenicModules


class ScenicLoader(importlib.abc.InspectLoader):
    def __init__(self, name, filepath):
        self.filepath = filepath

    def create_module(self, spec):
        return ScenicModule(spec.name)

    def exec_module(self, module):
        # Read source file and compile it
        with open(self.filepath, "r") as stream:
            source = stream.read()
        with open(self.filepath, "rb") as stream:
            code, pythonSource = compileStream(
                stream, module.__dict__, CompileOptions(), self.filepath
            )
        # Save code, source, and translated source for later inspection
        module._code = code
        module._source = source
        module._pythonSource = pythonSource

        # If we're in the process of compiling another Scenic module, inherit
        # objects, parameters, etc. from this one
        if veneer.isActive():
            veneer.currentScenario._inherit(module._scenario)

    def is_package(self, fullname):
        return False

    def get_code(self, fullname):
        module = importlib.import_module(fullname)
        assert isinstance(module, ScenicModule), module
        return module._code

    def get_source(self, fullname):
        module = importlib.import_module(fullname)
        assert isinstance(module, ScenicModule), module
        return module._source


class ScenicModule(types.ModuleType):
    def __getstate__(self):
        state = self.__dict__.copy()
        del state["__builtins__"]
        return (self.__name__, state)

    def __setstate__(self, state):
        name, state = state
        self.__init__(name)  # needed to create __dict__
        self.__dict__.update(state)
        self.__builtins__ = builtins.__dict__


# Give instances of ScenicModule a falsy __module__ to prevent Sphinx from
# getting confused. (Autodoc doesn't expect modules to have that attribute,
# and we can't del it.) We only do this during Sphinx runs since it seems to
# sometimes break pickling of the modules.
sphinx = sys.modules.get("sphinx")
buildingDocs = sphinx and getattr(sphinx, "_buildingScenicDocs", False)
if buildingDocs:
    ScenicModule.__module__ = None

## Finder for Scenic (and Python) files

scenicExtensions = (".scenic", ".sc")

import importlib.machinery as machinery

loaders = [
    (machinery.ExtensionFileLoader, machinery.EXTENSION_SUFFIXES),
    (machinery.SourceFileLoader, machinery.SOURCE_SUFFIXES),
    (machinery.SourcelessFileLoader, machinery.BYTECODE_SUFFIXES),
    (ScenicLoader, scenicExtensions),
]


class ScenicFileFinder(importlib.abc.PathEntryFinder):
    def __init__(self, path):
        self._inner = machinery.FileFinder(path, *loaders)

    def find_spec(self, fullname, target=None):
        spec = self._inner.find_spec(fullname, target=target)
        # Disallow imports of Scenic modules from Python modules, unless we are
        # building the documentation (to allow autodoc to introspect them; this
        # requires careful setup in `docs/conf.py`).
        # See `purgeModulesUnsafeToCache` for the rationale.
        if (
            spec
            and spec.origin
            and not (veneer.isActive() or buildingDocs)
            and any(spec.origin.endswith(ext) for ext in scenicExtensions)
        ):
            return None
        return spec

    def invalidate_caches(self):
        self._inner.invalidate_caches()

    # Support pkgutil.iter_modules() (used by Sphinx autosummary's recursive mode);
    # we need to use a subclass of FileFinder since pkgutil's implementation for
    # vanilla FileFinder uses inspect.getmodulename, which doesn't recognize the
    # .scenic file extension.
    def iter_modules(self, prefix):
        # This is mostly copied from pkgutil._iter_file_finder_modules
        yielded = {}
        try:
            filenames = os.listdir(self._inner.path)
        except OSError:
            return
        filenames.sort()
        for fn in filenames:
            modname = inspect.getmodulename(fn)
            if not modname:
                # Check for Scenic modules
                base = os.path.basename(fn)
                for ext in scenicExtensions:
                    if base.endswith(ext):
                        modname = base[: -len(ext)]
                        break
            if modname == "__init__" or modname in yielded:
                continue

            path = os.path.join(self._inner.path, fn)
            ispkg = False

            if not modname and os.path.isdir(path) and "." not in fn:
                modname = fn
                try:
                    dircontents = os.listdir(path)
                except OSError:
                    # ignore unreadable directories like import does
                    dircontents = []
                for fn in dircontents:
                    subname = inspect.getmodulename(fn)
                    if subname == "__init__":
                        ispkg = True
                        break
                else:
                    continue  # not a package

            if modname and "." not in modname:
                yielded[modname] = 1
                yield prefix + modname, ispkg


# Install path hook using our finder
def scenic_path_hook(path):
    if not path:
        path = os.getcwd()
    if not os.path.isdir(path):
        raise ImportError("only directories are supported", path=path)
    return ScenicFileFinder(path)


sys.path_hooks.insert(0, scenic_path_hook)
sys.path_importer_cache.clear()

### Translation phase two to four are done by the parser & compiler

### TRANSLATION PHASE FIVE: AST compilation


def compileTranslatedTree(tree, filename):
    try:
        return compile(tree, filename, "exec")
    except SyntaxError as e:
        raise PythonCompileError(e) from None


### TRANSLATION PHASE SIX: Python execution


def executeCodeIn(code, namespace):
    """Execute the final translated Python code in the given namespace."""
    try:
        exec(code, namespace)
    except RejectionException as e:
        # Determined statically that the scenario has probability zero.
        errors.optionallyDebugRejection(e)
        if errors.showInternalBacktrace:
            raise InvalidScenarioError(e.args[0]) from e
        else:
            raise InvalidScenarioError(e.args[0]).with_traceback(
                e.__traceback__
            ) from None


### TRANSLATION PHASE SEVEN: scenario construction


def storeScenarioStateIn(namespace, requirementSyntax, astHash, options):
    """Post-process an executed Scenic module, extracting state from the veneer."""

    # Save requirement syntax and other module-level information
    namespace["_astHash"] = astHash
    namespace["_compileOptions"] = options
    moduleScenario = veneer.currentScenario
    factory = veneer.simulatorFactory
    bns = gatherBehaviorNamespacesFrom(moduleScenario._behaviors)

    def handle(scenario):
        scenario._requirementSyntax = requirementSyntax
        if isinstance(scenario, type):
            scenario._simulatorFactory = staticmethod(factory)
        else:
            scenario._simulatorFactory = factory
        scenario._behaviorNamespaces = bns

    handle(moduleScenario)
    namespace["_scenarios"] = tuple(veneer.scenarios)
    for scenarioClass in veneer.scenarios:
        handle(scenarioClass)

    # Extract requirements, scan for relations used for pruning, and create closures
    # (only for top-level scenario; modular scenarios will be handled when instantiated)
    moduleScenario._compileRequirements()

    # Save global parameters
    for name, value in veneer._globalParameters.items():
        if needsLazyEvaluation(value):
            raise InvalidScenarioError(
                f"parameter {name} uses value {value}"
                " undefined outside of object definition"
            )
    for scenario in veneer.scenarios:
        scenario._bindGlobals(veneer._globalParameters)
    moduleScenario._bindGlobals(veneer._globalParameters)

    namespace["_scenario"] = moduleScenario


def gatherBehaviorNamespacesFrom(behaviors):
    """Gather any global namespaces which could be referred to by behaviors.

    We'll need to rebind any sampled values in them at runtime.
    """
    behaviorNamespaces = {}

    def registerNamespace(modName, ns):
        oldNS = behaviorNamespaces.get(modName)
        if oldNS:
            # Already registered; just do a consistency check to avoid bizarre
            # bugs from having multiple versions of the same module around.
            if oldNS is not ns:
                raise RuntimeError(
                    f"scenario refers to multiple versions of module {modName}; "
                    "perhaps you imported it before you started compilation?"
                )
            return
        behaviorNamespaces[modName] = ns
        for name, value in ns.items():
            if isinstance(value, ScenicModule):
                registerNamespace(value.__name__, value.__dict__)
            else:
                # Convert values requiring sampling to Distributions
                dval = toDistribution(value)
                if dval is not value:
                    ns[name] = dval

    for behavior in behaviors:
        modName = behavior.__module__
        globalNamespace = behavior.makeGenerator.__globals__
        registerNamespace(modName, globalNamespace)
    return behaviorNamespaces


def constructScenarioFrom(namespace, scenarioName=None):
    """Build a Scenario object from an executed Scenic module."""
    modularScenarios = namespace["_scenarios"]
    topLevelScenario = namespace["_scenario"]

    def isModularScenario(thing):
        return isinstance(thing, type) and issubclass(thing, DynamicScenario)

    if not scenarioName and isModularScenario(namespace.get("Main", None)):
        scenarioName = "Main"
    if scenarioName:
        ty = namespace.get(scenarioName, None)
        if not isModularScenario(ty):
            raise RuntimeError(f'no scenario "{scenarioName}" found')
        if ty._requiresArguments():
            raise RuntimeError(
                f'cannot instantiate scenario "{scenarioName}"' " with no arguments"
            ) from None

        dynScenario = ty()
    elif len(modularScenarios) > 1:
        raise RuntimeError(
            "multiple choices for scenario to run "
            "(specify using the --scenario option)"
        )
    elif modularScenarios and not modularScenarios[0]._requiresArguments():
        dynScenario = modularScenarios[0]()
    else:
        dynScenario = topLevelScenario

    if not dynScenario._prepared:  # true for all except top-level scenarios
        # Inherit ego, workspace, etc. from top level
        dynScenario._inherit(topLevelScenario)

        # Execute setup block (if any) to create objects and requirements;
        # extract any requirements and scan for relations used for pruning
        dynScenario._prepare(delayPreconditionCheck=True)
    scenario = dynScenario._toScenario(namespace)

    # Prune infeasible parts of the space
    if usePruning:
        pruning.prune(scenario, verbosity=errors.verbosityLevel)

    # Validate scenario
    scenario.validate()

    return scenario
