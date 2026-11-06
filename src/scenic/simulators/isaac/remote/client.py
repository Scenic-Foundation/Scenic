"""Client that submits a Scenic scenario to the Isaac-side bridge."""

import argparse
import json
import os
import socket
import sys

from scenic.simulators.isaac.remote.bridge import DEFAULT_HOST, DEFAULT_PORT


def _coerce(value):
    for parse in (int, float):
        try:
            return parse(value)
        except ValueError:
            continue
    return value


def runRemote(
    scenario,
    params=None,
    count=1,
    maxSteps=None,
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    connect_timeout=10.0,
):
    """Run a scenario on the bridge; streams its output and returns the result event."""
    request = {
        "scenario": os.path.abspath(scenario),
        "params": params or {},
        "count": count,
        "maxSteps": maxSteps,
    }
    with socket.create_connection((host, port), timeout=connect_timeout) as sock:
        sock.settimeout(None)
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        for line in sock.makefile("r", encoding="utf-8"):
            event = json.loads(line)
            kind = event.get("event")
            if kind == "log":
                print(event["text"], end="", flush=True)
            elif kind == "start":
                print(
                    f"[remote] Isaac {event.get('isaacVersion', '?')}, "
                    f"backend {event.get('backend', '?')}",
                    flush=True,
                )
            elif kind == "result":
                print(
                    f"[remote] success={event.get('success')} "
                    f"terminationReasons={event.get('terminationReasons')}",
                    flush=True,
                )
                return event
            elif kind == "error":
                print(event.get("traceback", ""), file=sys.stderr)
                return event
    return {"event": "error", "traceback": "bridge closed the connection early"}


def runRemoteFromCompilation(host=None, port=None):
    """Ship the scenario currently being compiled to the bridge, then exit.

    Called from model.scenic when the ``isaacRemote`` global parameter is set:
    locates the top-level .scenic file on the stack, forwards the other
    CLI-overridden params, and exits the process with the bridge result.
    """
    import inspect

    import scenic.syntax.veneer as veneer

    scenario_path = None
    for frame_info in reversed(inspect.stack()):  # outermost frame first
        if frame_info.filename.endswith(".scenic"):
            scenario_path = frame_info.filename
            break
    if scenario_path is None:
        raise RuntimeError("isaacRemote: could not determine the scenario file")

    control = {"isaacRemote", "isaacRemoteHost", "isaacRemotePort"}
    params = {
        name: value
        for name, value in veneer._globalParameters.items()
        if name in veneer.lockedParameters and name not in control
    }
    result = runRemote(
        scenario_path,
        params=params,
        host=host or DEFAULT_HOST,
        port=port or DEFAULT_PORT,
    )
    sys.exit(0 if result.get("success") else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scenic.simulators.isaac.remote",
        description="Run a Scenic scenario inside an already-running Isaac Sim.",
    )
    parser.add_argument("scenario", help="path to the .scenic file")
    parser.add_argument(
        "--param", nargs=2, action="append", default=[], metavar=("NAME", "VALUE")
    )
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    params = {name: _coerce(value) for name, value in args.param}
    result = runRemote(
        args.scenario,
        params=params,
        count=args.count,
        maxSteps=args.max_steps,
        host=args.host,
        port=args.port,
    )
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
