"""Isaac-side bridge that runs Scenic scenarios inside a running Isaac Sim."""

import json
import os
import queue
import socket
import sys
import threading
import traceback

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8793

_VERSION_BACKENDS = {"5": "experimental_51", "6": "experimental_60"}

_bridge = None


class _RunningApp:
    """Minimal SimulationApp-compatible handle over the running kit app."""

    def update(self):
        import omni.kit.app

        omni.kit.app.get_app().update()

    def run_coroutine(self, coro):
        # Named like SimulationApp.run_coroutine, which the experimental backends call.
        import omni.kit.app
        import omni.kit.async_engine

        task = omni.kit.async_engine.run_coroutine(coro)
        app = omni.kit.app.get_app()
        while not task.done():
            app.update()
        return task.result()

    def close(self):
        pass


def detectIsaacVersion():
    from isaacsim.core.version import get_version

    fields = get_version()
    return fields[0], str(fields[2])


def resolveBackend(requested=None):
    if requested and requested != "auto":
        return requested
    _, major = detectIsaacVersion()
    return _VERSION_BACKENDS.get(major, "experimental_60")


class _Tee:
    """Mirror writes to the real stream and forward whole lines to a callback."""

    def __init__(self, stream, callback):
        self._stream = stream
        self._callback = callback
        self._buffer = ""

    def write(self, text):
        self._stream.write(text)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._callback(line + "\n")
        return len(text)

    def flush(self):
        self._stream.flush()


class ScenicBridge:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self._socket = None
        self._jobs = queue.Queue()
        self._running = False
        self._busy = False
        self._update_subscription = None

    def start(self):
        if self._running:
            print(f"[scenic-bridge] already running on {self.host}:{self.port}")
            return self
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(1)
        self._socket = server
        self._running = True
        threading.Thread(target=self._acceptLoop, daemon=True).start()

        import omni.kit.app

        stream = omni.kit.app.get_app().get_update_event_stream()
        self._update_subscription = stream.create_subscription_to_pop(
            self._onUpdate, name="scenic.remote.bridge"
        )
        print(f"[scenic-bridge] listening on {self.host}:{self.port}")
        return self

    def stop(self):
        self._running = False
        self._update_subscription = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        print("[scenic-bridge] stopped")

    def _acceptLoop(self):
        while self._running:
            try:
                connection, _ = self._socket.accept()
            except OSError:
                return
            threading.Thread(
                target=self._receiveRequest, args=(connection,), daemon=True
            ).start()

    def _receiveRequest(self, connection):
        try:
            data = b""
            while b"\n" not in data:
                chunk = connection.recv(65536)
                if not chunk:
                    connection.close()
                    return
                data += chunk
            request = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
            self._jobs.put((request, connection))
        except Exception:
            self._send(
                connection, {"event": "error", "traceback": traceback.format_exc()}
            )
            connection.close()

    def _send(self, connection, event):
        try:
            connection.sendall((json.dumps(event) + "\n").encode("utf-8"))
        except OSError:
            pass

    def _onUpdate(self, _event):
        if self._busy:
            return
        try:
            request, connection = self._jobs.get_nowait()
        except queue.Empty:
            return
        self._busy = True
        try:
            self._runJob(request, connection)
        finally:
            self._busy = False
            connection.close()

    @staticmethod
    def _clearWorldSingleton():
        try:
            from isaacsim.core.api import World

            World.clear_instance()
        except Exception:
            pass

    @staticmethod
    def _resetLeakedScenicState():
        """Clear compiler state leaked by a previously crashed job."""
        import scenic.syntax.veneer as veneer

        if not veneer.activity and not veneer.scenarioStack:
            return
        veneer.activity = 0
        veneer.scenarioStack.clear()
        veneer.runningScenarios.clear()
        veneer.scenarios = []
        veneer.currentSimulation = None
        veneer.currentScenario = None
        veneer.currentBehavior = None
        veneer.simulatorFactory = None
        veneer.loadingModel = False
        veneer.lockedParameters = set()
        veneer.lockedModel = None
        veneer._globalParameters = {}

    @staticmethod
    def _removeKitFastImporter():
        """Bypass kit's fast_importer during a job: it crashes (TypeError) on
        scenario-local top-level imports like ``from lib import *``."""
        removed = [
            finder
            for finder in sys.meta_path
            if "fast_importer" in getattr(finder, "__module__", "")
            or getattr(finder, "__name__", "") == "FastFinder"
        ]
        for finder in removed:
            sys.meta_path.remove(finder)
        return removed

    def _runJob(self, request, connection):
        try:
            scenario_path = request["scenario"]
            if not os.path.isfile(scenario_path):
                raise FileNotFoundError(f"scenario not found: {scenario_path}")
            params = dict(request.get("params") or {})
            backend_name = resolveBackend(params.get("isaacBackend"))
            params["isaacBackend"] = backend_name
            isaac_version, _ = detectIsaacVersion()
            self._send(
                connection,
                {
                    "event": "start",
                    "backend": backend_name,
                    "isaacVersion": isaac_version,
                },
            )

            from scenic.simulators.isaac.backends import getBackend

            getBackend(backend_name).attachSimulationApp(_RunningApp())
            self._clearWorldSingleton()

            import scenic

            log = lambda line: self._send(connection, {"event": "log", "text": line})
            real_out, real_err = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = _Tee(real_out, log), _Tee(real_err, log)
            import builtins

            prior_flag = getattr(builtins, "ISAAC_LAUNCHED_FROM_TERMINAL", None)
            builtins.ISAAC_LAUNCHED_FROM_TERMINAL = False
            simulator = None
            self._resetLeakedScenicState()
            removed_finders = self._removeKitFastImporter()
            try:
                scenario = scenic.scenarioFromFile(scenario_path, params=params)
                results = []
                for _ in range(int(request.get("count") or 1)):
                    scene, _ = scenario.generate()
                    simulator = scenario.getSimulator()
                    simulation = simulator.simulate(
                        scene, maxSteps=request.get("maxSteps")
                    )
                    results.append(
                        str(simulation.result.terminationReason) if simulation else None
                    )
            finally:
                sys.meta_path[:0] = removed_finders
                sys.stdout, sys.stderr = real_out, real_err
                if prior_flag is not None:
                    builtins.ISAAC_LAUNCHED_FROM_TERMINAL = prior_flag
                if simulator is not None:
                    simulator.destroy()

            self._send(
                connection,
                {
                    "event": "result",
                    "success": all(r is not None for r in results),
                    "terminationReasons": results,
                },
            )
        except Exception:
            self._send(
                connection, {"event": "error", "traceback": traceback.format_exc()}
            )


def start(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Start (or return) the bridge inside the running Isaac Sim."""
    global _bridge
    if _bridge is None or not _bridge._running:
        _bridge = ScenicBridge(host, port).start()
    else:
        print(f"[scenic-bridge] already running on {_bridge.host}:{_bridge.port}")
    return _bridge


def stop():
    global _bridge
    if _bridge is not None:
        _bridge.stop()
        _bridge = None
