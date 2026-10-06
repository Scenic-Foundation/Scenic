# AirSim example

This directory contains a minimal Scenic example for controlling a drone in
[Microsoft AirSim](https://github.com/microsoft/AirSim).

The example has been tested with AirSim 1.8.1 on Ubuntu 22.04. AirSim requires
a graphical environment and is not supported on macOS.

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

Download or build an AirSim environment. For example, launch the AirSim 1.8.1
Blocks environment with the settings included in this directory:

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

Run AirSim from a graphical desktop session and leave it open while Scenic is
running.

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
