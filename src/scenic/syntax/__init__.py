"""The Scenic compiler and associated support code."""

import hashlib as _hashlib
import pathlib as _pathlib
import subprocess as _subprocess
import sys as _sys

_syntaxDir = _pathlib.Path(__file__).parent
_projectRootDir = _syntaxDir.parent.parent.parent
_grammarPath = _syntaxDir / "scenic.gram"
_parserPath = _syntaxDir / "parser.py"
_checksumPath = _syntaxDir / ".parser_checksum"


def buildParser():
    try:
        import pegen
    except ModuleNotFoundError:
        raise RuntimeError(
            f'the "pegen" package is required to build the Scenic parser'
        ) from None
    result = _subprocess.run(
        [
            _sys.executable or "python",
            "-m",
            "pegen",
            str(_grammarPath),
            "-o",
            str(_parserPath),
        ],
        cwd=_projectRootDir,
        capture_output=True,
        text=True,
    )

    with open(_checksumPath, "wb") as f:
        f.write(getGrammarHash())

    return result


def getGrammarHash():
    with open(_grammarPath, "rb") as f:
        data = f.read()
    return _hashlib.blake2b(data).digest()


def checksumValid():
    if not _checksumPath.exists():
        return False

    with open(_checksumPath, "rb") as f:
        checksum = f.read()

    return checksum == getGrammarHash()


if not _parserPath.exists() or not checksumValid():
    _result = buildParser()
    _retcode = _result.returncode
    if _retcode != 0:
        print(f"STDERR FROM PARSER GENERATOR:\n{_result.stderr}", file=_sys.stderr)
        raise RuntimeError(
            f"Failed to generate the Scenic parser (return code {_retcode})"
        )
