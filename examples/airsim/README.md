# AirSim example

This directory contains a minimal Scenic example for controlling a drone in
[Microsoft AirSim](https://github.com/microsoft/AirSim).

The example has been tested with AirSim 1.8.1 on Ubuntu 22.04. AirSim is not
supported on macOS.

## Install the Python dependencies

Create and activate a virtual environment, then install Scenic from the
repository:

```bash
python3 -m venv .venv-airsim
source .venv-airsim/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -e .
```

Install the AirSim client and its additional dependencies:

```bash
python -m pip install msgpack-rpc-python promise
python -m pip install --no-build-isolation airsim==1.8.1
```

The following NumPy and OpenCV versions were used during testing:

```bash
python -m pip install --force-reinstall \
  numpy==1.26.4 \
  opencv-contrib-python==4.10.0.84
```

Check the resulting environment:

```bash
python -m pip check
```

## Start AirSim

Download or build an AirSim environment. For example, download and unpack the
AirSim 1.8.1 Blocks environment for Linux (143 MB). The SHA-256 of `Blocks.zip`
is `563e1da1b5d7303b9405c8736243ea92ab0a011b96a561f26f17563d105a404f`.

```bash
wget https://github.com/microsoft/AirSim/releases/download/v1.8.1/Blocks.zip
sha256sum Blocks.zip
unzip Blocks.zip
chmod +x LinuxBlocks1.8.1/LinuxNoEditor/Blocks.sh \
  LinuxBlocks1.8.1/LinuxNoEditor/Blocks/Binaries/Linux/Blocks
```

Launch Blocks with the settings included in this directory:

```bash
/path/to/Blocks.sh \
  -settings="/path/to/Scenic/examples/airsim/settings/simple_drone_settings.json" \
  -windowed \
  -ResX=640 \
  -ResY=480 \
  -NoVSync
```

These window settings are conservative defaults that work well on a remote
desktop. They can be adjusted for the available display and hardware.

Without a desktop session, replace `-windowed -ResX=640 -ResY=480` with
`-RenderOffscreen`, which renders without a window. Blocks renders with Vulkan.
On Ubuntu with Intel or AMD graphics, install Mesa's drivers with
`sudo apt install mesa-vulkan-drivers`. With an NVIDIA GPU, use NVIDIA's
driver. Without a graphics device, also add `-nullrhi`, which disables
rendering. Scenic's AirSim interface does not read camera images, so it does
not need rendering.

Leave AirSim running while Scenic is running. A Blocks process that has been
running for a long time can develop an altitude jump on the first step of each
scene, so restart Blocks before long runs.

Scenic connects to AirSim at `127.0.0.1` on AirSim's RPC port, 41451. To
connect to AirSim at another address, for example from a container or another
machine, set the environment variable `AIRSIM_HOST` to that address.

## Generate world information

The Scenic AirSim model requires information about the objects and assets in
the selected AirSim environment.

Start AirSim first. Then, from the Scenic repository, run:

```bash
python src/scenic/simulators/airsim/generators/generateWorldInfo.py \
  --outputDirectory "/path/to/blocks-world-info"
```

The output directory must not already exist. Generating the meshes may take
several minutes.

The resulting directory contains:

```text
worldInfo.json
objectMeshes/
assets/
```

Keep this generated directory outside the Scenic repository. Pass its location
to Scenic using the `worldInfoPath` parameter.

## Run the patrol example

With AirSim running, open another terminal, activate the Python environment,
and run:

```bash
scenic examples/airsim/patrol.scenic \
  --simulate \
  --count 1 \
  --time 30 \
  --param worldInfoPath "/path/to/blocks-world-info"
```

The example creates one drone and sends it through a fixed sequence of patrol
points.

## Initial drone placement

AirSim drone initialization does not advance simulated time before Scenic trace
state 0. Drones are teleported while physics is paused, AirSim's indefinite
hover task is installed, and their declared poses are reasserted before Scenic
records the initial state. A short wall-clock pause lets the asynchronous
controller command start, but that pause is not part of the simulation trace.

The bridge also validates the physical pose after placement. If AirSim does not
accept a drone's initial pose, simulation creation fails instead of silently
starting a trace from the wrong geometry.

## Simulation steps

Each Scenic time step advances AirSim by `round(timestep / 0.003)` physics
ticks of 3 ms, so a step lasts a whole number of ticks: with the default
`timestep` of 1 s, each step is 333 ticks, about 0.999 s of simulated time.
Scenic issues a `SimulatorInterfaceWarning` if AirSim runs extra ticks in a
step. The `timestep` must be at least 1.5 ms.

With a `PX4Drone`, or with no SimpleFlight vehicle in the AirSim settings, each
step instead calls `simContinueForTime(timestep)`, which can run a varying
number of ticks.

## Starting a drone already in motion

An AirSim pose carries no velocity, so a drone normally comes into existence
hovering. A controller that immediately commands several m/s then spends the
first ticks accelerating into it, and anything measured over those ticks
describes the cold start rather than steady flight. Set `startVelocity` to give
a drone a velocity at the first simulation step:

```scenic
drone = new Drone at (0, -16, 10),
    with startVelocity (0, 3, 0),
    with behavior Follow(leader)
```

The value is a Scenic-frame velocity vector; leave it `None` (the default) to
spawn at rest. It requires `startHovering`, and is not supported for `PX4Drone`,
whose state is owned by the PX4 controller.

This is applied with `simSetKinematics` after the initial pose has been
reasserted and validated. Note that `moveByVelocityAsync` is *not* a substitute:
it issues a velocity *command*, and the drone still has to accelerate into it,
which is the transient `startVelocity` exists to remove.

The `simSetKinematics` call must pass `ignore_collision=True`. With `False`,
AirSim treats the write as a collision-checked teleport: against Blocks 1.8.1 the
drone lands on the ground roughly 14.5 m below its validated spawn pose and its
physics stop advancing altogether, so the episode runs from the wrong state with a
drone that never moves. The symptom appears one step after setup returns, and the
placement validation in setup does not catch it, because the placement itself was
correct. `tests/simulators/airsim/test_simulator.py` pins the flag.
