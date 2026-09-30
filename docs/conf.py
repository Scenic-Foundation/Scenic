# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import warnings

import sphinx

# Hack to signal to Scenic that the docs are being built
# (need to do this before importing the scenic module)
sphinx._buildingScenicDocs = True

from scenic.core.simulators import SimulatorInterfaceWarning
import scenic.syntax.compiler
from scenic.syntax.translator import CompileOptions
import scenic.syntax.veneer as veneer

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
sys.path.insert(0, os.path.abspath("../src"))
sys.path.insert(0, os.path.abspath("."))  # for docs-specific code

# Set up paths for Scenic maps to enable importing the world models
import scenic.simulators.gta.map as gta_map
import scenic.simulators.webots.guideways.intersection as gw_int
import scenic.simulators.webots.road.world as wbt_road_world

gta_map.mapPath = "../tests/simulators/gta/map.npz"
gw_int.intersectionPath = (
    "../tests/simulators/webots/guideways/McClintock_DonCarlos_Tempe.json"
)
wbt_road_world.worldPath = "../tests/simulators/webots/road/simple.wbt"

# Hack to set global parameters needed to import the driving domain models
veneer.activate(
    CompileOptions(
        mode2D=True,
        paramOverrides=dict(
            map="../assets/maps/opendrive.org/CulDeSac.xodr",
            carla_map="blah",
            sumo_map="blah",
            lgsvl_map="blah",
        ),
    )
)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", SimulatorInterfaceWarning)
    import scenic.simulators.carla.model
    import scenic.simulators.lgsvl.model
    import scenic.simulators.metadrive.model
veneer.deactivate()

# Hack to allow importing models which require 2D compatibility mode
veneer.activate(CompileOptions(mode2D=True))
import scenic.simulators.gta.model
import scenic.simulators.webots.guideways.model
import scenic.simulators.webots.road.model

veneer.deactivate()

# -- Project information -----------------------------------------------------

import time

year = time.strftime("%Y", time.gmtime())

project = "Scenic"
copyright = f"2026-{year}, Scenic Foundation"
author = "Scenic Foundation"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_tabs.tabs",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

default_role = "any"
# nitpicky = True

add_module_names = False
autosummary_generate = True
autodoc_inherit_docstrings = False
autodoc_member_order = "bysource"
autodoc_mock_imports = [
    "carla",
    "gymnasium",
    "isaaclab",
    "lgsvl",
    "metadrive",
    # Modules to skip in autosummary
    "scenic.simulators.isaac.empty_env_cfg",
    "scenic.simulators.isaac.remote.__main__",
    "scenic.simulators.isaac.scripts",
]
autodoc_typehints = "description"
autodoc_type_aliases = {
    "Vectorlike": "`scenic.domains.driving.roads.Vectorlike`",
}
napoleon_numpy_docstring = False
napoleon_use_rtype = False
napoleon_use_ivar = True

autodoc_default_options = {
    "members": None,
    # include members starting with underscores by default;
    # we'll install an extension below to skip those with :meta private:
    "private-members": None,
    "show-inheritance": None,
}

from intersphinx_config import intersphinx_mapping

highlight_language = "scenic"
pygments_style = "scenic.syntax.pygment.ScenicStyle"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_css_files = [
    "custom.css",
]

html_logo = "images/logo-full.svg"
html_favicon = "images/favicon.ico"

html_theme_options = {
    "logo_only": True,
}

# -- Generate lists of keywords for the language reference -------------------

import itertools
import math

from scenic.core.utils import batched
from scenic.syntax.parser import ScenicParser


def maketable(items, columns=5, gap=4):
    items = tuple(sorted(items))
    width = max(len(item) for item in items)
    nrows = math.ceil(len(items) / 5)
    justified = (item.ljust(width) for item in items)
    cols = batched(justified, nrows)
    rows = itertools.zip_longest(*cols, fillvalue="")
    space = " " * gap
    yield from (space.join(row) for row in rows)


os.makedirs("_build", exist_ok=True)
with open("_build/keywords.txt", "w") as outFile:
    for row in maketable(ScenicParser.KEYWORDS):
        outFile.write(row + "\n")
with open("_build/keywords_soft.txt", "w") as outFile:
    for row in maketable(ScenicParser.SOFT_KEYWORDS):
        outFile.write(row + "\n")
with open("_build/builtin_names.txt", "w") as outFile:
    for row in maketable(scenic.syntax.compiler.builtinNames):
        outFile.write(row + "\n")


# -- Monkeypatch ModuleAnalyzer to handle Scenic modules ---------------------

from analyzer import ScenicModuleAnalyzer
import sphinx.pycode as pycode

pycode.ModuleAnalyzer = ScenicModuleAnalyzer

# -- Monkeypatch the Python domain to understand Scenic objects --------------

# (Unfortunately it's easier to do this than create a separate Scenic domain,
# since autosummary for example hard-codes the use of Python domain roles.)

from docutils import nodes
from sphinx import addnodes
from sphinx.domains.python import (
    ObjType,
    PyClasslike,
    PyFunction,
    PythonDomain,
    PyXRefRole,
)
from sphinx.ext.autodoc import ClassDocumenter, FunctionDocumenter

from scenic.core.dynamics.behaviors import Behavior, Monitor
from scenic.core.dynamics.scenarios import DynamicScenario


class ScenicBehavior(PyFunction):
    """Description of a behavior."""

    def get_signature_prefix(self, sig):
        return [nodes.Text("behavior"), addnodes.desc_sig_space()]


class ScenicScenario(PyFunction):
    """Description of a modular scenario."""

    def get_signature_prefix(self, sig):
        return [nodes.Text("scenario"), addnodes.desc_sig_space()]


class ScenicClass(PyClasslike):
    """Description of a Scenic class."""

    def get_signature_prefix(self, sig):
        return [nodes.Text("class"), addnodes.desc_sig_space()]

    def handle_signature(self, sig, signode):
        name = sig.split("(")[0]
        modname = self.options.get("module", self.env.ref_context.get("py:module"))
        classname = self.env.ref_context.get("py:class")
        if classname:
            add_module = False
            fullname = classname + "." + name
        else:
            add_module = True
            classname = ""
            fullname = name

        signode["module"] = modname
        signode["class"] = classname
        signode["fullname"] = fullname

        sig_prefix = self.get_signature_prefix(sig)
        signode += addnodes.desc_annotation(str(sig_prefix), "", *sig_prefix)

        if modname and add_module and self.env.config.add_module_names:
            nodetext = modname + "."
            signode += addnodes.desc_addname(nodetext, nodetext)

        signode += addnodes.desc_name(name, name)
        signode += addnodes.desc_sig_space()
        signode += addnodes.desc_sig_keyword("<specifiers>", "<specifiers>")

        return fullname, ""

    def run(self):
        # Hack to allow self.objtype to be 'class' even though the directive is
        # 'py:scenicclass' in order not to collide with 'py:class'.
        self.name = "py:class"
        return super().run()


PythonDomain.object_types.update(
    {
        "behavior": ObjType("behavior", "behavior", "obj"),
        "scenario": ObjType("scenario", "scenario", "obj"),
    }
)
PythonDomain.directives.update(
    {
        "behavior": ScenicBehavior,
        "scenario": ScenicScenario,
        "scenicclass": ScenicClass,
    }
)
PythonDomain.roles.update(
    {
        "behavior": PyXRefRole(fix_parens=True),
        "scenario": PyXRefRole(fix_parens=True),
    }
)

# These documenters will be installed in setup() below.


class BehaviorDocumenter(FunctionDocumenter):
    objtype = "behavior"
    priority = ClassDocumenter.priority + 1

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return (
            isinstance(member, type)
            and issubclass(member, Behavior)
            and member not in (Behavior, Monitor)
        )


class ScenarioDocumenter(FunctionDocumenter):
    objtype = "scenario"
    priority = ClassDocumenter.priority + 1

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return (
            isinstance(member, type)
            and issubclass(member, DynamicScenario)
            and member is not DynamicScenario
        )


class ScenicClassDocumenter(ClassDocumenter):
    directivetype = "scenicclass"
    priority = ClassDocumenter.priority + 1

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        return (
            isinstance(member, type)
            and issubclass(member, scenic.core.object_types.Constructible)
            and member is not scenic.core.object_types.Constructible
        )


# -- Monkeypatch to resolve ambiguous references -----------------------------

from sphinx.domains.python import PythonDomain

orig_find_obj = PythonDomain.find_obj


def find_obj(self, env, modname, classname, name, type, searchmode, *args, **kwargs):
    results = orig_find_obj(
        self, env, modname, classname, name, type, searchmode, *args, **kwargs
    )
    if len(results) <= 1:
        return results

    def score(res):
        name = res[0]
        if name.startswith("scenic.syntax.veneer"):
            return -1
        elif modname is None:
            return 0
        else:
            # score by length of common prefix
            for i, (c, d) in enumerate(zip(modname, name)):
                if c != d:
                    break
            return i

    scores = [score(res) for res in results]
    highScore = max(scores)
    highest = [res for res, score in zip(results, scores) if score == highScore]
    return highest


PythonDomain.find_obj = find_obj

# -- Monkeypatch to improve formatting of class/instance attributes ----------

# This is based on code suggested by Michael Goerz at:
# https://michaelgoerz.net/notes/extending-sphinx-napoleon-docstring-sections.html

from sphinx.ext.napoleon.docstring import GoogleDocstring


def parse_attributes_section(self, section):
    return self._format_fields("Attributes", self._consume_fields())


GoogleDocstring._parse_attributes_section = parse_attributes_section


def parse_class_attributes_section(self, section):
    return self._format_fields("Class Attributes", self._consume_fields())


GoogleDocstring._parse_class_attributes_section = parse_class_attributes_section


def parse_properties_section(self, section):
    return self._format_fields("Properties", self._consume_fields())


GoogleDocstring._parse_properties_section = parse_properties_section


def parse_global_params_section(self, section):
    return self._format_fields("Global Parameters", self._consume_fields())


GoogleDocstring._parse_global_params_section = parse_global_params_section

orig_parse = GoogleDocstring._parse


def parse(self):
    self._sections["global parameters"] = self._parse_global_params_section
    self._sections["class attributes"] = self._parse_class_attributes_section
    self._sections["properties"] = self._parse_properties_section
    orig_parse(self)


GoogleDocstring._parse = parse

# -- Monkeypatch to add autosummary tables for behaviors, etc. ---------------

from typing import Any, Dict, List, Set, Tuple

import sphinx.ext.autosummary.generate as generate
from sphinx.ext.autosummary.generate import (
    get_documenter,
    logger,
    members_of,
    safe_getattr,
)

from scenic.syntax.translator import ScenicModule

orig_gen_content = generate.generate_autosummary_content


def generate_autosummary_content(
    name,
    obj,
    parent,
    template,
    template_name,
    imported_members,
    app,
    recursive,
    context,
    modname=None,
    qualname=None,
):
    if not isinstance(obj, ScenicModule):
        return orig_gen_content(
            name,
            obj,
            parent,
            template,
            template_name,
            imported_members,
            app,
            recursive,
            context,
            modname,
            qualname,
        )

    def skip_member(obj: Any, name: str, objtype: str) -> bool:
        try:
            return app.emit_firstresult(
                "autodoc-skip-member", objtype, name, obj, False, {}
            )
        except Exception as exc:
            logger.warning(
                __(
                    "autosummary: failed to determine %r to be documented, "
                    "the following exception was raised:\n%s"
                ),
                name,
                exc,
                type="autosummary",
            )
            return False

    def get_module_members(obj: Any) -> Dict[str, Any]:
        members = {}
        for name in members_of(obj, app.config):
            try:
                members[name] = safe_getattr(obj, name)
            except AttributeError:
                continue
        return members

    def get_members(
        obj: Any, types: Set[str], include_public: List[str] = [], imported: bool = True
    ) -> Tuple[List[str], List[str]]:
        items: List[str] = []
        public: List[str] = []

        all_members = get_module_members(obj)
        for name, value in all_members.items():
            documenter = get_documenter(app, value, obj)
            if documenter.objtype in types:
                # skip imported members if expected
                if imported or getattr(value, "__module__", None) == obj.__name__:
                    skipped = skip_member(value, name, documenter.objtype)
                    if skipped is True:
                        pass
                    elif skipped is False:
                        # show the member forcedly
                        items.append(name)
                        public.append(name)
                    else:
                        items.append(name)
                        if name in include_public or not name.startswith("_"):
                            # considers member as public
                            public.append(name)
        return public, items

    assert "behaviors" not in context
    context["behaviors"], context["all_behaviors"] = get_members(
        obj, {"behavior"}, imported=imported_members
    )
    context["scenarios"], context["all_scenarios"] = get_members(
        obj, {"scenario"}, imported=imported_members
    )
    return orig_gen_content(
        name,
        obj,
        parent,
        template,
        template_name,
        imported_members,
        app,
        recursive,
        context,
        modname,
        qualname,
    )


generate.generate_autosummary_content = generate_autosummary_content

# -- Monkeypatch to list private members after public ones -------------------

from sphinx.ext.autodoc import Documenter

orig_sort_members = Documenter.sort_members


def sort_members(self, documenters, order):
    documenters = orig_sort_members(self, documenters, order)

    def key(entry):
        parts = entry[0].name.split("::")
        if len(parts) == 2:
            name = parts[-1]
        else:
            assert len(parts) == 1
            name = parts[0].split(".")[-1]
        return name.startswith("_")

    documenters.sort(key=key)
    return documenters


Documenter.sort_members = sort_members

# -- Monkeypatch to hide private base classes --------------------------------
# N.B. can't use autodoc-process-bases since it doesn't allow suppressing the
# entire "Bases:" line

from sphinx.ext.autodoc import ClassDocumenter

from scenic.core.dynamics.behaviors import Behavior
from scenic.core.dynamics.scenarios import DynamicScenario

orig_add_directive_header = ClassDocumenter.add_directive_header


def add_directive_header(self, sig):
    oldBases = self.object.__bases__
    if oldBases != (object,) and self.options.show_inheritance:
        newBases = [base for base in oldBases if not base.__name__.startswith("_")]
        if newBases:
            self.object.__bases__ = tuple(newBases)
            orig_add_directive_header(self, sig)
            self.object.__bases__ = oldBases
            return
    oldSI = self.options.show_inheritance
    self.options.show_inheritance = False
    orig_add_directive_header(self, sig)
    self.options.show_inheritance = oldSI


ClassDocumenter.add_directive_header = add_directive_header

# -- Monkeypatch to improve formatting of certain values ---------------------

import sphinx.ext.autodoc
import sphinx.util.inspect

import scenic

orig_object_description = sphinx.util.inspect.object_description


def object_description(obj, **kwargs):
    # Accept **kwargs to support Sphinx ≥7.2, which passes the `_seen` argument
    # to object_description. This ensures compatibility across Sphinx versions.
    if obj is scenic.core.regions.nowhere or obj is scenic.core.regions.everywhere:
        return str(obj)
    elif isinstance(
        obj,
        (
            scenic.core.regions.Region,
            scenic.core.vectors.VectorField,
            scenic.domains.driving.roads.Network,
        ),
    ):
        raise ValueError  # prevent rendering of this value
    elif obj is sys.stdout:
        return "sys.stdout"
    elif obj is sys.stderr:
        return "sys.stderr"
    else:
        return orig_object_description(obj, **kwargs)


sphinx.util.inspect.object_description = object_description
sphinx.ext.autodoc.object_description = object_description

# Hack to prevent signatures for certain classes getting quashed by their
# wrapper __new__ methods.
from scenic.core.distributions import Distribution
from scenic.core.object_types import Constructible

classes = (Distribution, Constructible)
for cls in classes:
    func = cls.__new__
    fqname = f"{func.__module__}.{func.__qualname__}"
    sphinx.ext.autodoc._CLASS_NEW_BLACKLIST.append(fqname)

# -- Extension for correctly displaying Scenic code and skipping internals ---


def setup(app):
    app.connect("viewcode-find-source", handle_find_source)
    app.connect("autodoc-skip-member", handle_skip_member)

    # Add documenters for special types of Scenic objects
    app.add_autodocumenter(BehaviorDocumenter)
    app.add_autodocumenter(ScenarioDocumenter)
    # Can't use add_autodocumenter for ScenicClassDocumenter since its objtype
    # is 'class', the same as ClassDocumenter.
    from sphinx.ext.autodoc.directive import AutodocDirective

    app.registry.add_documenter("scenicclass", ScenicClassDocumenter)
    app.add_directive("autoscenicclass", AutodocDirective)

    # Run our own reference resolver before the standard one, to resolve refs to
    # Scenic classes differently in the "Scenic Internals" section than elsewhere
    app.add_post_transform(ScenicRefResolver)

    # To allow either plural or singular forms to be looked up in the glossary:
    app.connect("missing-reference", handle_missing_reference)

    # Hack the highlighter just before viewcode runs to color Scenic modules
    app.connect("html-collect-pages", handle_collect_pages, priority=499)

    # For some reason, the Pygments entry point doesn't work on ReadTheDocs;
    # so we register the custom lexer here.
    import scenic.syntax.pygment as scenic_pygment

    app.add_lexer("scenic", scenic_pygment.ScenicLexer)
    # Install a better Python lexer (e.g. so function calls get better highlighting)
    app.add_lexer("python", scenic_pygment.BetterPythonLexer)
    # Install a lexer for Pegen grammars
    app.add_lexer("pegen", scenic_pygment.PegenLexer)
    # Also add the specialized lexers used for inline code snippets and grammar
    app.add_lexer("scenic-snippet", scenic_pygment.ScenicSnippetLexer)
    app.add_lexer("python-snippet", scenic_pygment.PythonSnippetLexer)
    app.add_lexer("scenic-specifier", scenic_pygment.ScenicSpecifierLexer)
    app.add_lexer("scenic-requirement", scenic_pygment.ScenicRequirementLexer)
    app.add_lexer("scenic-property", scenic_pygment.ScenicPropertyLexer)
    app.add_lexer("scenic-grammar", scenic_pygment.ScenicGrammarLexer)

    # Add :scenic: role which is like :samp: but with Scenic syntax highlighting
    from docutils.parsers.rst import directives
    from docutils.parsers.rst.languages import en
    import docutils.parsers.rst.roles as roles

    code_role, _ = roles.role("code", en, 0, None)
    options = {
        "class": directives.class_option("scenic"),
        "language": "scenic-snippet",
    }
    role = roles.CustomRole("scenic", code_role, options)
    roles.register_local_role("scenic", role)

    # Likewise for :python:
    options = {
        "class": directives.class_option("python"),
        "language": "python-snippet",
    }
    role = roles.CustomRole("python", code_role, options)
    roles.register_local_role("python", role)

    # Add :specifier: role like :scenic: but for specifiers (which aren't usually
    # allowed at the top level)
    options = {
        "class": directives.class_option("specifier"),
        "language": "scenic-specifier",
    }
    role = roles.CustomRole("specifier", code_role, options)
    roles.register_local_role("specifier", role)

    # Ditto for :requirement: (allowing temporal operators)
    options = {
        "class": directives.class_option("requirement"),
        "language": "scenic-requirement",
    }
    role = roles.CustomRole("requirement", code_role, options)
    roles.register_local_role("requirement", role)

    # Add :prop: role like :scenic: but for properties
    # N.B. cannot use :property: since the RTD theme uses a 'property' HTML class
    options = {
        "class": directives.class_option("prop"),
        "language": "scenic-property",
    }
    role = roles.CustomRole("prop", code_role, options)
    roles.register_local_role("prop", role)

    # Add :grammar: role for inline bits of Scenic grammar
    options = {
        "class": directives.class_option("grammar"),
        "language": "scenic-grammar",
    }
    role = roles.CustomRole("grammar", code_role, options)
    roles.register_local_role("grammar", role)

    return {"parallel_read_safe": True}


import importlib

from sphinx.util.docstrings import separate_metadata

from scenic.syntax.translator import ScenicModule

magicPrefix = "SCENIC!"


def handle_find_source(app, modname):
    try:
        module = importlib.import_module(modname)
    except Exception:
        return None
    if not isinstance(module, ScenicModule):
        return None  # no special handling for Python modules

    # Run usual analysis on the translated source to get tag dictionary
    try:
        analyzer = ScenicModuleAnalyzer.for_module(modname)
        analyzer.find_tags()
    except Exception:
        return None  # bail out; viewcode will try analyzing again but oh well

    # Return original Scenic source, plus tags (line numbers will correspond)
    return magicPrefix + module._source, analyzer.tags


def handle_collect_pages(app):
    # Unfortunately viewcode hard-codes the Python lexer for highlighting;
    # rather than use a huge monkeypatch, we hack the choice of lexer:
    hl = app.builder.highlighter
    orig = hl.highlight_block

    def hacked_highlight_block(code, lexer, linenos):
        if code.startswith(magicPrefix):
            code = code[len(magicPrefix) :]
            lexer = "scenic"
        return orig(code, lexer, linenos=linenos)

    hl.highlight_block = hacked_highlight_block
    return
    yield None  # make this a generator function


def handle_skip_member(app, what, name, obj, skip, options):
    if not skip:
        doc = getattr(obj, "__doc__")
        if doc and "private" in separate_metadata(doc)[1]:
            return True
    return None


import inflect

engine = inflect.engine()


def handle_missing_reference(app, env, node, contnode):
    """If a glossary term can't be found, try the opposite plurality."""
    if node.get("refdomain") != "std":
        return None
    if node["reftype"] != "term":
        return None
    prefix, sep, last_word = node["reftarget"].rpartition(" ")
    alternative = engine.singular_noun(last_word)
    if alternative is False:  # word is not a plural noun
        alternative = engine.plural(last_word)
    target = prefix + sep + alternative
    stddomain = env.domains["std"]
    newnode = stddomain.resolve_xref(
        env, node.get("refdoc"), app.builder, "term", target, node, contnode
    )
    return newnode


from sphinx.locale import __
from sphinx.transforms.post_transforms import ReferencesResolver
from sphinx.util import logging

logger = logging.getLogger(__name__)


class ScenicRefResolver(ReferencesResolver):
    default_priority = ReferencesResolver.default_priority - 2

    # The following is copied from ReferencesResolver.resolve_anyref with minor changes
    def resolve_anyref(self, refdoc, node, contnode):
        stddomain = self.env.get_domain("std")
        target = node["reftarget"]
        stdresults = []
        # first, try resolving as :doc:
        doc_ref = stddomain.resolve_xref(
            self.env, refdoc, self.app.builder, "doc", target, node, contnode
        )
        if doc_ref:
            stdresults.append(("doc", doc_ref))
        # next, do the standard domain (makes this a priority)
        stdresults.extend(
            stddomain.resolve_any_xref(
                self.env, refdoc, self.app.builder, target, node, contnode
            )
        )
        domresults = []
        for domain in self.env.domains.values():
            if domain.name == "std":
                continue  # we did this one already
            try:
                domresults.extend(
                    domain.resolve_any_xref(
                        self.env, refdoc, self.app.builder, target, node, contnode
                    )
                )
            except NotImplementedError:
                # the domain doesn't yet support the new interface
                # we have to manually collect possible references (SLOW)
                for role in domain.roles:
                    res = domain.resolve_xref(
                        self.env, refdoc, self.app.builder, role, target, node, contnode
                    )
                    if res and len(res) > 0 and isinstance(res[0], nodes.Element):
                        domresults.append(("%s:%s" % (domain.name, role), res))
        # now, see how many matches we got...
        results = stdresults + domresults
        if not results:
            return None
        if stdresults and domresults:
            # disambiguate based on whether this is internal documentation or not
            results = domresults if refdoc.startswith("modules/") else stdresults
        if len(results) > 1:

            def stringify(name: str, node: nodes.Element) -> str:
                reftitle = node.get("reftitle", node.astext())
                return ":%s:`%s`" % (name, reftitle)

            candidates = " or ".join(stringify(name, role) for name, role in results)
            logger.warning(
                __(
                    "more than one target found for 'any' cross-"
                    "reference %r: could be %s"
                ),
                target,
                candidates,
                location=node,
            )
        res_role, newnode = results[0]
        # Override "any" class with the actual role type to get the styling
        # approximately correct.
        res_domain = res_role.split(":")[0]
        if (
            len(newnode) > 0
            and isinstance(newnode[0], nodes.Element)
            and newnode[0].get("classes")
        ):
            newnode[0]["classes"].append(res_domain)
            newnode[0]["classes"].append(res_role.replace(":", "-"))
        return newnode


# -- Monkeypatch adding a :sampref: role combining :samp: and :ref: ----------
# (necessary since ReST does not allow nested inline markup)

from docutils import nodes
import docutils.parsers.rst.roles
from sphinx.roles import EmphasizedLiteral, XRefRole


class LiteralXRefRole(XRefRole, EmphasizedLiteral):
    def create_xref_node(self):
        self.refdomain, self.reftype = "std", "sampref"
        elem, _ = super().create_xref_node()
        node = elem[0]
        del node[0]
        children = self.parse(self.title)
        node += nodes.literal(
            self.title, "", *children, role="samp", classes=["xref", "ref", "samp"]
        )
        return [node], []


role = LiteralXRefRole(lowercase=True, innernodeclass=nodes.inline, warn_dangling=True)

docutils.parsers.rst.roles.register_local_role("sampref", role)

from sphinx.domains.std import StandardDomain

old_resolve_xref = StandardDomain.resolve_xref


def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
    if typ == "sampref":
        newnode = old_resolve_xref(
            self, env, fromdocname, builder, "ref", target, node, contnode
        )
        if not newnode:
            return newnode
        del newnode[0]
        inner = node[0]
        inner["classes"] = ["std", "std-ref"]
        newnode += inner
    else:
        newnode = old_resolve_xref(
            self, env, fromdocname, builder, typ, target, node, contnode
        )
    return newnode


StandardDomain.resolve_xref = resolve_xref
