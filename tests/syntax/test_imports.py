"""Tests for imports of Scenic modules.

Note that this is different from modular scenarios defined using the 'scenario'
statement. This file simply tests imports of old-style Scenic modules; the new
system of modular scenarios is tested in 'test_modular.py'.
"""

import os.path
import sys

import pytest

from scenic import scenarioFromFile
from scenic.core.errors import ScenicSyntaxError
from scenic.syntax.translator import InvalidScenarioError
from tests.utils import compileScenic, sampleResult, sampleScene, sampleSceneFrom


def test_import_top_absolute(request):
    base = os.path.dirname(request.fspath)
    fullpathImports = os.path.join(base, "imports.scenic")
    fullpathHelper = os.path.join(base, "helper.scenic")
    scenario = scenarioFromFile(fullpathImports)
    assert len(scenario.requirements) == 0
    scene, iterations = scenario.generate(maxIterations=1)
    # Top-level and inherited Objects
    assert len(scene.objects) == 2
    ego = scene.egoObject
    assert ego.species == "killer"
    assert scene.objects[1].species == "helpful"
    # Parameter depending on imported Python module
    assert scene.params["thingy"] == 42
    # Parameters depending on import circumstances
    assert scene.params["imports_name"] == "__main__"
    assert scene.params["imports_file"] == fullpathImports
    # Inherited parameters as above
    assert scene.params["helper_name"] == "helper"
    assert scene.params["helper_file"] == fullpathHelper


def test_import_top_relative(request):
    base = os.path.dirname(request.fspath)
    fullpathHelper = os.path.join(base, "helper.scenic")
    oldDirectory = os.getcwd()
    os.chdir(base)
    try:
        scenario = scenarioFromFile("imports.scenic")
        assert len(scenario.requirements) == 0
        scene, iterations = scenario.generate(maxIterations=1)
        assert len(scene.objects) == 2
        ego = scene.egoObject
        assert ego.species == "killer"
        assert scene.objects[1].species == "helpful"
        assert scene.params["thingy"] == 42
        assert scene.params["imports_name"] == "__main__"
        assert scene.params["imports_file"] == "imports.scenic"
        assert scene.params["helper_name"] == "helper"
        assert scene.params["helper_file"] == fullpathHelper
    finally:
        os.chdir(oldDirectory)


def test_module_name_main():
    scenario = compileScenic("param name = __name__\n" "ego = new Object")
    scene, iterations = scenario.generate(maxIterations=1)
    assert scene.params["name"] == "__main__"


def test_inherit_requirements(runLocally):
    with runLocally():
        scenario = compileScenic("import helper3\n" "ego = new Object")
        assert len(scenario.requirements) == 1
        for i in range(50):
            scene, iterations = scenario.generate(maxIterations=100)
            assert len(scene.objects) == 2
            constrainedObj = scene.objects[1]
            assert constrainedObj.position.x > 0


def test_inherit_records(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            import helper_record
            """
        )

        result = sampleResult(scenario, maxSteps=1)
        assert "foo" in result.records
        assert result.records["foo"] == 1


def test_inherit_terminate(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            import helper_terminate
            ego = new Object
            record 1 as "foo"
            terminate after 4 steps
            """
        )

        result = sampleResult(scenario, maxSteps=5)
        assert "foo" in result.records
        assert result.records["foo"] == [(0, 1), (1, 1)]


def test_inherit_require_monitor(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            import helper_require_monitor
            ego = new Object
            record 1 as "foo"
            """
        )

        result = sampleResult(scenario, maxSteps=5)
        assert "foo" in result.records
        assert result.records["foo"] == [(0, 1), (1, 1)]


def test_inherit_constructors(runLocally):
    with runLocally():
        scenario = compileScenic("from helper import Caerbannog\n" "ego = new Caerbannog")


def test_multiple_imports(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            import helper
            import helper
            ego = new Object
            import helper
            """
        )
        assert len(scenario.objects) == 2
        scene = sampleScene(scenario)
        assert len(scene.objects) == 2


def test_import_in_try(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            try:
                from helper import Caerbannog
                x = 12
            finally:
                y = 4
            ego = new Caerbannog at x @ y
            """
        )


def test_import_in_except(runLocally):
    with runLocally():
        scenario = compileScenic(
            """
            try:
                import __non_ex_ist_ent___
            except ImportError:
                from helper import Caerbannog
            ego = new Caerbannog
            """
        )


def test_import_multiline_1():
    compileScenic(
        "from math import factorial, \\\n"
        "    pow\n"
        "ego = new Object with width pow(factorial(4), 2)"
    )


def test_import_multiline_2():
    compileScenic(
        "from math import (factorial,\n"
        "  pow)\n"
        "ego = new Object with width pow(factorial(4), 2)"
    )


def test_import_override_param():
    scene = sampleSceneFrom(
        """
        param helper_file = 'foo'
        import tests.syntax.helper
        ego = new Object
        """
    )
    assert scene.params["helper_file"] != "foo"


def test_module_get_source():
    if sys.version_info < (3, 9):
        pytest.importorskip("astor")
    import scenic.syntax.translator as translator

    try:
        translator.buildingDocs = True
        import tests.syntax.helper4 as h4

        src = h4.__loader__.get_source("tests.syntax.helper4")
        assert src
    finally:
        translator.buildingDocs = False
        sys.modules.pop("tests.syntax.helper4", None)


def test_module_import_from_python():
    with pytest.raises(ModuleNotFoundError):
        import tests.syntax.helper4


def test_model_not_override_param():
    scene = sampleSceneFrom(
        """
        param helper_file = 'foo'
        model tests.syntax.helper
        ego = new Object
        """
    )
    assert scene.params["helper_file"] == "foo"


def test_model_respects_all():
    with pytest.raises(NameError):
        compileScenic(
            """
            model tests.syntax.helper4
            ego = new Object with foo bar
            """
        )


def test_malformed_model():
    with pytest.raises(ScenicSyntaxError):
        compileScenic("model 101")


def test_missing_model():
    with pytest.raises(InvalidScenarioError):
        compileScenic("model __no_such_package__")
