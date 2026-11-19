"""Common exceptions and error handling."""

import importlib
import itertools
import pathlib
import pdb
import sys
import traceback
import types
import warnings

import scenic
import scenic.core
import scenic.syntax

## Configuration


def setDebuggingOptions(
    *, verbosity=0, fullBacktrace=False, debugExceptions=False, debugRejections=False
):
    """Configure Scenic's debugging options.

    Args:
        verbosity (int): Verbosity level. Zero by default, although the command-line
            interface uses 1 by default. See the :option:`--verbosity` option for the
            allowed values.
        fullBacktrace (bool): Whether to include Scenic's innards in backtraces
            (like the :option:`-b` command-line option).
        debugExceptions (bool): Whether to use `pdb` for post-mortem debugging of
            uncaught exceptions (like the :option:`--pdb` option).
        debugRejections (bool): Whether to enter `pdb` when a scene or simulation is
            rejected (like the :option:`--pdb-on-reject` option).
    """
    global verbosityLevel, showInternalBacktrace, postMortemDebugging
    global postMortemRejections
    verbosityLevel = verbosity
    postMortemDebugging = debugExceptions
    postMortemRejections = debugRejections
    if debugExceptions or debugRejections:
        fullBacktrace = True  # partial backtraces would be confusing in the debugger
    showInternalBacktrace = fullBacktrace


#: Verbosity level. See :option:`--verbosity` for the allowed values.
verbosityLevel = 0

#: Whether or not to include Scenic's innards in backtraces.
#:
#: Set to True by default so that any errors during import of the scenic module
#: will get full backtraces; the :mod:`scenic` module's *__init__.py* sets it to False.
showInternalBacktrace = True

#: Whether or not to do post-mortem debugging of uncaught exceptions.
postMortemDebugging = False

#: Whether or not to do "post-mortem" debugging of rejected scenes/simulations.
postMortemRejections = False

# fmt: off
#: Folders elided from backtraces when :obj:`showInternalBacktrace` is false.
#:
#: :meta hide-value:
hiddenFolders = [
    pathlib.Path(scenic.core.__file__).parent,      # scenic.core submodules
    pathlib.Path(scenic.syntax.__file__).parent,    # scenic.syntax submodules
    '<frozen importlib._bootstrap>',                # parts of importlib used internally
    pathlib.Path(importlib.__file__).parent,
]
# fmt: on

## Exceptions


class ScenicError(Exception):
    """An error produced during Scenic compilation, scene generation, or simulation."""

    pass


class ScenicSyntaxError(ScenicError):
    """An error produced by attempting to parse an invalid Scenic program.

    This is intentionally not a subclass of SyntaxError so that pdb can be used
    for post-mortem debugging of the parser. Our custom excepthook below will
    arrange to still have it formatted as a SyntaxError, though.
    """

    pass


class ParseCompileError(ScenicSyntaxError):
    """Error occurring during Scenic/Python parsing or compilation."""

    def __init__(self, exc):
        self.msg = exc.args[0]
        self.filename, self.lineno = exc.filename, exc.lineno
        self.end_lineno = getattr(exc, "end_lineno", None)  # added in Python 3.10
        end_offset = getattr(exc, "end_offset", None)  # ditto
        self.text, self.offset, self.end_offset = getText(
            self.filename, self.lineno, exc.text, exc.offset, end_offset
        )
        super().__init__(self.msg)
        self.with_traceback(exc.__traceback__)


class ScenicParseError(ParseCompileError):
    """Error occuring during Scenic parsing or compilation."""

    pass


class PythonCompileError(ParseCompileError):
    """Error occuring during Python compilation of translated Scenic code."""

    pass


class ASTParseError(ScenicSyntaxError):
    """Parse error occuring during modification of the Python AST."""

    def __init__(self, node, message, filename):
        self.msg = message
        self.lineno = node.lineno
        self.end_lineno = getattr(node, "end_lineno", None)  # not always present
        end_offset = getattr(node, "end_col_offset", None)  # ditto
        self.filename = filename
        self.text, self.offset, self.end_offset = getText(
            filename, node.lineno, offset=node.col_offset, end_offset=end_offset
        )
        super().__init__(message)


class InvalidScenarioError(ScenicError):
    """Error raised for syntactically-valid but otherwise problematic Scenic programs."""

    pass


class InconsistentScenarioError(InvalidScenarioError):
    """Error for scenarios with inconsistent requirements."""

    def __init__(self, line, message):
        self.lineno = line
        super().__init__("Inconsistent requirement on line " + str(line) + ": " + message)


class SpecifierError(ScenicError):
    """Error for illegal uses of specifiers."""

    pass


## Scenic backtraces


def excepthook(ty, value, tb):
    if sys.version_info >= (3, 11) and issubclass(ty, BaseExceptionGroup):
        # Use the default mechanism since we don't handle ExceptionGroups
        sys.__excepthook__(ty, value, tb)
    else:
        displayScenicException(value)

    if postMortemDebugging:
        print("Uncaught exception. Entering post-mortem debugging")
        import pdb

        pdb.post_mortem(tb)


def displayScenicException(exc, seen=None):
    """Print a Scenic exception, cleaning up the traceback if desired.

    If ``showInternalBacktrace`` is False, this hides frames inside Scenic itself.
    """
    ty = type(exc)
    tb = exc.__traceback__

    # Recursively print the cause/context for this exception, if any.
    # (This code is adapted from IDLE.)
    if seen is None:
        seen = set()
    seen.add(id(exc))
    cause = exc.__cause__
    context = exc.__context__
    if cause is not None and id(cause) not in seen:
        displayScenicException(cause, seen)
        print(
            "\nThe above exception was the direct cause of the following exception:\n",
            file=sys.stderr,
        )
    elif context is not None and not exc.__suppress_context__ and id(context) not in seen:
        displayScenicException(context, seen)
        print(
            "\nDuring handling of the above exception, another exception occurred:\n",
            file=sys.stderr,
        )

    if showInternalBacktrace:
        strings = ["Traceback (most recent call last):\n"]
    else:
        strings = [
            "Traceback (most recent call last; use -b to show Scenic internals):\n"
        ]

    # Work out how to present the exception type
    pseudoSyntaxError = issubclass(ty, ScenicSyntaxError)
    if issubclass(ty, ScenicError):
        if issubclass(ty, ScenicSyntaxError) and not showInternalBacktrace:
            name = "ScenicSyntaxError"
        else:
            name = ty.__name__
        if pseudoSyntaxError:
            # hack to get format_exception_only to format this like a bona fide SyntaxError
            bases = (SyntaxError,)
        else:
            bases = ty.__bases__
        formatTy = type(name, bases, {})
        if not showInternalBacktrace:
            formatTy.__module__ = "__main__"  # hide qualified name of the exception
    else:
        formatTy = ty

    if issubclass(ty, SyntaxError) or (pseudoSyntaxError and not showInternalBacktrace):
        pass  # no backtrace for these types of errors
    elif loc := getattr(exc, "_scenic_location", None):
        strings.extend(traceback.format_list([loc]))
    else:
        summary = traceback.extract_tb(tb)
        if showInternalBacktrace:
            filtered = summary
        else:
            filtered = []
            skip = False
            for frame in summary:
                if skip:
                    skip = False
                    continue
                if frame.name == "callBeginningScenicTrace":
                    filtered = []
                    skip = True
                elif includeFrame(frame):
                    filtered.append(frame)
        if filtered:
            strings.extend(traceback.format_list(filtered))
        else:
            strings.append("  <Scenic internals>\n")
    # Note: we can't directly call traceback.format_exception_only any more,
    # since as of Python 3.10 it ignores the exception class passed in and
    # uses type(exc) instead, foiling our formatTy hack.
    tbe = traceback.TracebackException(formatTy, exc, None)
    strings.extend(tbe.format_exception_only())
    message = "".join(strings)
    print(message, end="", file=sys.stderr)


def includeFrame(frame):
    if frame.filename in hiddenFolders:
        return False
    parents = pathlib.Path(frame.filename).parents
    return not any(folder in parents for folder in hiddenFolders)


# Install our excepthook if nobody else has already installed one;
# we specially allow overwriting excepthooks from the following modules,
# which are known to not cause problems:
#   - exceptiongroup (PEP 654 backport for pre-3.11)
#   - apport_python_hook (Ubuntu crash reporting system)
if sys.excepthook is not sys.__excepthook__ and not sys.excepthook.__module__.startswith(
    ("exceptiongroup", "apport_python_hook")
):
    warnings.warn("unable to install sys.excepthook to format Scenic backtraces")
else:
    sys.excepthook = excepthook


def callBeginningScenicTrace(func):
    """Call the given function, starting the Scenic backtrace at that point.

    This function is just a convenience to make Scenic backtraces cleaner when
    running Scenic programs from the command line.
    """
    return func()


def saveErrorLocation():
    stack = traceback.extract_stack()
    for frame in reversed(stack):
        if includeFrame(frame):
            return frame
    return None


## Utilities


def optionallyDebugRejection(exc=None):
    if not postMortemRejections:
        return
    print("Scene/simulation rejected. Entering debugger...")
    if exc:
        pdb.post_mortem(exc.__traceback__)
    else:
        debugger = pdb.Pdb()
        debugger.set_trace(sys._getframe().f_back)  # TODO more portable way to do this?


def getText(filename, lineno, line="", offset=0, end_offset=None):
    """Attempt to recover the text of an error from the original Scenic file."""
    if not filename or filename in {"<stream>", "<string>", "<unknown>"}:
        return line, offset, end_offset  # don't bother with the filesystem
    try:
        with open(filename, "r") as f:
            line = list(itertools.islice(f, lineno - 1, lineno))
        line = line[0] if line else ""
        # TODO improve reconstruction of error position?
        # (see TracebackException._format_syntax_error for spaces calculation below)
        rline = line.rstrip("\n")
        lline = rline.lstrip(" \n\f")
        spaces = len(rline) - len(lline)
        if end_offset is not None:
            adj_end_offset = min(end_offset, len(line) + 1)
            offset = max(spaces + 1, adj_end_offset - (end_offset - offset))
            end_offset = adj_end_offset
        else:
            offset = min(offset, len(line))
    except OSError:
        pass
    return line, offset, end_offset
