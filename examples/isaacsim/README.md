# Scenic to Isaac Sim / Isaac Lab Interface

This repository contains an interface for running Scenic scenarios in NVIDIA
Isaac Sim and Isaac Lab. The direct Isaac Sim path supports both the Isaac Sim
5.1 Core APIs and the Isaac Sim 6.0 Core Experimental APIs. The Isaac Lab path
translates a Scenic sample into an Isaac Lab manager-based environment.

The main example scenarios are under `examples/isaacsim`.

## Compatibility

| Workflow | Python | Isaac Sim | Isaac Lab | Scenic backend |
| --- | --- | --- | --- | --- |
| Direct Isaac Sim 5.1 | 3.11 | 5.1.0 | Not required | `core_51` |
| Direct Isaac Sim 5.1 experimental | 3.11 | 5.1.0 | Not required | `experimental_51` |
| Direct Isaac Sim 6.0 | 3.12 | 6.0 | Not required | `experimental_60` |
| Isaac Lab, recommended/tested path | 3.11 | 5.1.0 | 2.3.x | `lab` |
| Isaac Lab 3.0 beta (not yet supported) | 3.12 | 6.0 | 3.0 beta | `lab` |

> [!WARNING]
> The Isaac Lab integration was developed and tested against the Isaac Lab
> 2.x API used with Isaac Sim 5.1. Isaac Lab 3.0 is a major architectural
> release for Isaac Sim 6.0. Cloning the latest Isaac Lab source may therefore
> break this interface even though the direct Isaac Sim 6.0 backend works.
> Pin Isaac Lab to `v2.3.2` for the known working Lab setup. Isaac Lab
> `v3.0.0-beta` has not been validated and may required a large interface migration.

The release-specific NVIDIA instructions are:

* [Isaac Sim 5.1 pip installation](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_python.html)
* [Isaac Sim 6.0 pip installation](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/install_python.html)
* [Isaac Lab 2.3.2 installation](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/pip_installation.html)
* [Isaac Lab 3.0 beta installation](https://isaac-sim.github.io/IsaacLab/v3.0.0-beta/source/setup/installation/pip_installation.html)

## Installation

Isaac Sim and Isaac Lab have strict dependency requirements. Use a dedicated
environment and install Isaac packages before installing Scenic. The commands
below target Linux x86-64 with CUDA 12.8.

### Prerequisites

* Ubuntu 22.04 or 24.04
* A supported NVIDIA GPU and a current production driver
* GLIBC 2.35 or newer for pip-based Isaac Sim installation
* `git`, `pip`, and Python 3.11 or 3.12 as required below

Check the GLIBC version with:

```bash
ldd --version
```

### Option A: Isaac Sim 5.1.0

Use this environment for `core_51`, `experimental_51`, and the recommended
Isaac Lab 2.3.x setup:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

python -m pip install "isaacsim[all,extscache]==5.1.0" \
  --extra-index-url https://pypi.nvidia.com

python -m pip install -U torch==2.7.0 torchvision==0.22.0 \
  --index-url https://download.pytorch.org/whl/cu128
```

### Option B: Isaac Sim 6.0

Use this environment for `experimental_60`. Make sure to install PyTorch with the correct CUDA version (this example uses CUDA 12):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

python -m pip install torch==2.11.0 \
  --index-url https://download.pytorch.org/whl/cu128

python -m pip install "isaacsim[all,extscache]==6.0.0" \
  --extra-index-url https://pypi.nvidia.com
```

### Install Isaac Lab from source

Isaac Lab is only required for commands that use `--param isaacLab True` or
the Scenic RSL-RL scripts.

For the recommended Isaac Sim 5.1 setup, clone and pin Isaac Lab 2.3.2:

```bash
git clone --branch v2.3.2 --depth 1 \
  https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab

sudo apt install cmake build-essential
./isaaclab.sh -i rsl_rl
```

The Scenic terrain integration requires one small Isaac Lab 2.x source change.
In `source/isaaclab/isaaclab/utils/configclass.py`, find the `_validate`
function and change:

```python
if key.startswith("__"):
```

to:

```python
if key.startswith("__") or key == "class_type":
```

Verify the source installation from the Isaac Lab repository:

```bash
./isaaclab.sh -p scripts/tutorials/00_sim/create_empty.py
```

The experimental Isaac Sim 6.0 setup with Isaac Lab 3.0 has not been validated with the Scenic interface, and will most likely not work with the current interface without modifications.

### Install Scenic

From the root of this repository, with the Isaac environment activated:

```bash
python -m pip install -e . --no-deps
```

`--no-deps` prevents pip from replacing versions required by Isaac Sim or Isaac
Lab. Install any missing Scenic dependencies selectively if they are not
already present in the Isaac environment.

The terrain optimization example uses VerifAI, GPyOpt, and GPy:

```bash
python -m pip install --no-deps "verifai==2.2.0"
python -m pip install --no-deps "GPyOpt==1.2.6"
python -m pip install --no-deps "GPy==1.13.2"
python -m pip install --no-deps "paramz==0.9.6"
```

## Running Scenic with Isaac Sim

Every Isaac scenario must select the Isaac world model:

```scenic
model scenic.simulators.isaac.model
```

Run with the Isaac Sim 5.1 Core backend:

```bash
scenic examples/isaacsim/robot/create3.scenic -S -b \
  --param isaacBackend core_51
```

Run the same scenario with the Isaac Sim 6.0 Core Experimental backend:

```bash
scenic examples/isaacsim/robot/create3.scenic -S -b \
  --param isaacBackend experimental_60
```

Add `--param headless True` to launch without the GUI:

```bash
scenic examples/isaacsim/robot/create3.scenic -S -b \
  --param isaacBackend experimental_60 \
  --param headless True
```

The manipulator examples pin the backend matching the tested Isaac Sim 5.1
setup and run as-is:

```bash
scenic -S -b examples/isaacsim/robot/franka_example_core.scenic
scenic -S -b examples/isaacsim/robot/franka_example_experimental.scenic
scenic -S -b examples/isaacsim/robot/ur5e_example_core.scenic
scenic -S -b examples/isaacsim/robot/ur5e_example_experimental.scenic
scenic -S -b examples/isaacsim/robot/ur5e_example_experimental_side.scenic
```

### Isaac interface parameters

All of the following parameters can be declared in a Scenic file with
`param NAME = VALUE` or overridden on the command line with
`--param NAME VALUE`.

| Parameter | Default | Applies to | Description |
| --- | --- | --- | --- |
| `environmentUSDPath` | `None` | Sim and Lab | Local USD file, URL, or Isaac asset path such as `Isaac/Environments/...`. The interface loads the USD and prepares the mesh metadata Scenic needs for spatial reasoning. |
| `environmentMeshPath` | `None` | Sim and Lab | Override the converted environment mesh file (normally derived from `environmentUSDPath` and cached automatically). |
| `environmentInfoPath` | `None` | Sim and Lab | Override the environment info JSON accompanying the mesh (normally derived and cached with it). |
| `headless` | `False` | Sim and Lab | Launch Isaac Sim without its graphical window. |
| `isaacBackend` | `auto` | Direct Sim | Selects `core_51`, `experimental_51`, or `experimental_60`; `auto` picks one from the installed Isaac Sim version (`core_51` for 5.x, `experimental_60` for 6.x, falling back to `experimental_60`). In remote mode, defaults to the version detected in the running Isaac Sim. |
| `isaacLab` | `False` | Lab | When enabled, delegates simulation to the Isaac Lab manager-based interface. |
| `isaacRemote` | `False` | Remote | Run the scenario on the bridge inside an already-running Isaac Sim instead of launching one locally (see Remote mode). |
| `isaacRemoteHost` | `None` | Remote | Bridge address for `isaacRemote` (default `127.0.0.1`). |
| `isaacRemotePort` | `None` | Remote | Bridge TCP port for `isaacRemote` (default `8793`). |
| `labTask` | `None` | Lab | Registered Isaac Lab task ID, for example `Isaac-Velocity-Rough-H1-v0`. The task must use a manager-based configuration, not a Direct environment. |
| `labEnvCfg` | `None` | Lab | Import string for a custom config class, for example `my_package.env_cfg:MyEnvCfg`. It must produce a `ManagerBasedEnvCfg` or `ManagerBasedRLEnvCfg`. |
| `labDevice` | `cuda:0` | Lab | Isaac Lab simulation device, such as `cuda:0` or `cpu`. |
| `labNumEnvs` | `1` | Lab | Number of parallel Isaac Lab environments. |
| `labEnvSpacing` | `10.0` | Lab | Distance between cloned Isaac Lab environments. |
| `labTimestep` | `1 / 120` | Lab | Physics timestep in seconds. |
| `labDebugLifecycle` | `False` | Lab | Enables periodic lifecycle and controller diagnostics. |


### Loading an Isaac environment

An environment can be selected inside a scenario:

```scenic
param environmentUSDPath = "Isaac/Environments/Simple_Warehouse/warehouse.usd"

model scenic.simulators.isaac.model
```

It can also be overridden from the command line:

```bash
scenic examples/isaacsim/forklift/forklift.scenic -S -b \
  --param isaacBackend experimental_60 \
  --param environmentUSDPath \
    Isaac/Environments/Simple_Warehouse/warehouse.usd
```

Converted environment data (a `NAME_usd.glb.bz2` mesh and `NAME_info.json`)
is cached. Local USD conversions are placed in a `_converted` folder next to
the source USD; Isaac asset and URL conversions are cached under
`~/.cache/scenic/isaac/environments`.

### Remote mode

Remote mode attaches Scenic to an Isaac Sim instance that is already running
instead of launching a new one per run. A bridge inside that instance executes
the full scenario and automatically selects the backend matching its Isaac
version (`--param isaacBackend NAME` forces one).

1. In the running Isaac's Script Editor (Window > Script Editor), start the
   bridge. If Scenic is not installed into Isaac's own Python, put it (and an
   environment providing its dependencies) on `sys.path` first:

   ```python
   import sys
   sys.path.append(r"<path-to-Scenic>\src")
   sys.path.append(r"<python-env-with-scenic-deps>\Lib\site-packages")
   from scenic.simulators.isaac.remote import bridge
   bridge.start()
   ```

2. From any shell with Scenic installed, run scenarios against it by setting
   the `isaacRemote` parameter:

   ```bash
   scenic -S -b examples/isaacsim/robot/ur5e_example_experimental.scenic \
     --param isaacRemote 1
   ```

   Other `--param NAME VALUE` overrides are forwarded to the bridge;
   `--param isaacRemoteHost IP` and `--param isaacRemotePort N` select a
   non-default bridge address. Scenario output streams back to the client.
   (`python -m scenic.simulators.isaac.remote <file>` is the direct client,
   adding `--count N` and `--max-steps N`.)

The bridge listens on `127.0.0.1:8793` by default (`bridge.start(port=...)`
to change) and runs one scenario at a time on Isaac's main update loop; each
run opens the scenario's environment stage in the running editor.
`bridge.stop()` stops it. The bridge host is the address of the machine
running Isaac Sim — the default `127.0.0.1` means the same machine. To run
against a different machine, start the bridge on a routable interface there
(`bridge.start(host="0.0.0.0")`) and pass its IP via
`--param isaacRemoteHost` (or `--host` with the direct client).

## Running Scenic with Isaac Lab

The simplest Lab run uses the built-in empty manager-based environment and
fills it with the sampled Scenic objects:

```bash
scenic examples/isaacsim/robot/create3.scenic -S -b \
  --param isaacLab True \
  --param labNumEnvs 32
```

To add the Scenic scene to a registered Isaac Lab manager-based task:

```bash
scenic examples/isaacsim/robot/create3.scenic -S -b \
  --param isaacLab True \
  --param labTask Isaac-Velocity-Rough-H1-v0 \
  --param labNumEnvs 32
```

To use a custom manager-based configuration instead of a registered task:

```bash
scenic path/to/scenario.scenic -S -b \
  --param isaacLab True \
  --param labEnvCfg my_package.env_cfg:MyManagerBasedEnvCfg \
  --param labNumEnvs 32
```

Specify either `labTask` or `labEnvCfg`. If neither is provided, the interface
uses its minimal empty manager-based configuration.

> [!NOTE]
> The current Lab path samples one Scenic scene and lets Isaac Lab clone that
> configuration across `labNumEnvs`. The parallel environments therefore
> begin with the same Scenic object poses and terrain. Independent Scenic
> sampling per Lab environment is future work.

### Scenic RSL-RL scripts

The interface includes scripts for training and playing RSL-RL policies on
Scenic-generated terrain:

```text
src/scenic/simulators/isaac/scripts/train_scenic.py
src/scenic/simulators/isaac/scripts/play_scenic.py
```

Important shared arguments are:

| Argument | Description |
| --- | --- |
| `--scenario PATH` | Scenic terrain scenario. Defaults to `examples/isaacsim/terrain/random_uniform.scenic`. |
| `--scenic_model MODULE` | Scenic world model. Defaults to `scenic.simulators.isaac.model`. |
| `--terrain_border_width FLOAT` | Border added around the combined Scenic terrain mesh. |
| `--task TASK_ID` | Isaac Lab task to train or play. |
| `--agent ENTRY_POINT` | Agent configuration entry point. |
| `--num_envs N` | Number of parallel environments. |
| `--seed N` | Training or playback seed. |
| `--device DEVICE` | Isaac Lab device supplied by `AppLauncher`. |
| `--headless` | Run without the Isaac Sim GUI. |
| `--video` | Record a video and enable cameras. |
| `--video_length N` | Number of recorded steps. |
| `--checkpoint VALUE` | Checkpoint filename/pattern for training resume, or checkpoint path for playback. |
| `--experiment_name NAME` | Override the RSL-RL experiment name. |
| `--run_name NAME` | Add a name to the generated training run. |
| `--resume` | Resume training from a checkpoint. |
| `--load_run VALUE` | Run directory or run-selection pattern used when resuming. |
| `--logger LOGGER` | Select the external logger. |
| `--log_project_name NAME` | Project name for WandB or Neptune. |

Training additionally supports `--max_iterations`, `--distributed`,
`--video_interval`, and `--export_io_descriptors`. Playback additionally
supports `--use_pretrained_checkpoint`, `--disable_fabric`, and `--real-time`.
The scripts also inherit release-specific `AppLauncher` and Hydra options from
Isaac Lab; run either script with `--help` for the complete list installed in
your pinned Isaac Lab version.

## Writing a Scenic Scenario

A minimal Isaac scenario can use ordinary Scenic geometry:

```scenic
model scenic.simulators.isaac.model

class Crate(IsaacSimObject):
    shape: BoxShape()
    width: 0.5
    length: 0.5
    height: 0.5
    density: 500
    color: (0.8, 0.2, 0.1)

floor = new GroundPlane at (0, 0, -0.005),
    with width 10, with length 10

crate = new Crate on floor

terminate after 10 seconds
```

`IsaacSimObject` supports Scenic shapes as well as USD assets. Common
attributes are:

| Attribute | Description |
| --- | --- |
| `width`, `length`, `height` | Scenic dimensions. Generic object USD assets are scaled to these dimensions. |
| `shape` | Scenic geometry used for placement and collision reasoning. |
| `physics` | Whether the object participates in physics. Defaults to `True`. |
| `mass`, `density` | Optional physical properties. |
| `color` | Display color. |
| `usdPath` | Local USD asset path. |
| `isaacAssetPath` | Isaac content path such as `Isaac/Robots/...`. |
| `initialRotation` | Fixed (yaw, pitch, roll) rotation applied to a robot's USD asset to align it with Scenic coordinates. |

When a scenario loads an existing environment, use `getExistingObj` to refer
to prims already in that USD stage:

```scenic
param environmentUSDPath = "Isaac/Environments/Simple_Warehouse/warehouse.usd"

model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj

floor = getExistingObj("/Root/SM_floor58/SM_floor02")
robot = new Create3 on floor, with behavior KeepMoving

terminate after 20 seconds
```

See [`examples/isaacsim/forklift/forklift.scenic`](examples/isaacsim/forklift/forklift.scenic)
for a complete environment-based scenario.

### Converting USD assets to meshes

Environments given by `environmentUSDPath` are converted automatically. For an
individual USD asset you want to use as the *shape* of an `IsaacSimObject`
(so that Scenic's placement and collision reasoning matches the asset's real
geometry rather than a bounding box), convert it once with the conversion
tool, which runs inside an Isaac Sim Python environment:

```bash
python src/scenic/simulators/isaac/usd_to_mesh.py \
  --folders "$ISAAC_ASSETS/Isaac/Props/KLT_Bin" --output examples/isaacsim/assets/klt_bin
```

Every `.usd` file in each folder is written as a bz2-compressed binary glTF
(`NAME_usd.glb.bz2`) to the `--output` directory (default: a `_converted`
subfolder of the input folder); ground planes in the asset are dropped and
materials are omitted unless `--load-materials` is given, since Scenic only
needs the geometry. Input folders may be URLs, so `$ISAAC_ASSETS` can be the
asset root printed by `isaacsim.storage.native.get_assets_root_path()` or a
[local copy of the Isaac Sim assets](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html#isaac-sim-latest-release).
Add `--environments NAME.usd` to treat a file as an environment, which
additionally produces the JSON prim metadata Scenic uses for existing objects
(this is what the automatic conversion does).

Load such a mesh with `loadAssetMesh` (which repairs it into a volume if
needed) and `MeshShape`, as in
[`examples/isaacsim/simple_room_asset_shape.scenic`](examples/isaacsim/simple_room_asset_shape.scenic),
which places a KLT bin on the table of the `Simple_Room` environment and
expects the mesh at `examples/isaacsim/assets/klt_bin/small_KLT_usd.glb.bz2`.

Compressed files are handled transparently: `trimesh` (and hence `MeshShape`)
reads `.glb.bz2` meshes directly, and a bz2-compressed local USD given as
`environmentUSDPath` or `usdPath` is decompressed into `~/.cache/scenic/isaac`
before Isaac Sim opens it. A compressed USD must be self-contained (flattened),
since the decompressed copy no longer sits next to any files it references.

### Scenic terrain for Isaac Lab

The world model provides the following terrain classes:

* `RandomUniformTerrain`
* `SlopedTerrain`
* `PyramidSlopedTerrain`
* `DiscreteObstaclesTerrain`
* `WaveTerrain`
* `StairsTerrain`
* `PyramidStairsTerrain`
* `SteppingStonesTerrain`
* `PolesTerrain`

Multiple terrain objects can be placed relative to one another. The Lab
interface combines them into one terrain mesh and supplies the corresponding
environment origins to the Isaac Lab terrain importer. See
[`examples/isaacsim/terrain/random_uniform.scenic`](examples/isaacsim/terrain/random_uniform.scenic).

## Adding a Custom Robot

### Wheeled robot

For a differential-drive robot, provide its USD asset and wheel metadata:

```scenic
model scenic.simulators.isaac.model

class MyDifferentialRobot(IsaacSimRobot):
    width: 0.4
    length: 0.5
    height: 0.25
    usdPath: localPath("assets/my_robot.usd")

    wheelController: "differential"
    wheelRadius: 0.06
    wheelBase: 0.32
    wheelDofNames: ["left_wheel_joint", "right_wheel_joint"]

behavior Drive():
    while True:
        take ApplyControllerAction([0.5, 0.0])

floor = new GroundPlane
ego = new MyDifferentialRobot on floor, with behavior Drive
```

The differential command is `[linear_velocity, angular_velocity]`. The same
robot class can be translated into an Isaac Lab `ArticulationCfg`; the Lab
path currently provides built-in command handling for differential drive.

The direct Isaac Sim backends also support:

* Holonomic robots with `wheelController: "holonomic"` and a command of
  `[x_velocity, y_velocity, yaw_velocity]`.
* Ackermann robots with `wheelController: "ackermann"`, drive and steering
  DOF names, wheel base, track width, and wheel radius. The controller command
  is `[steering_angle, steering_angle_velocity, forward_speed, acceleration, dt]`.

The forklift example demonstrates an Ackermann robot with an additional lift
joint:
[`examples/isaacsim/forklift/common.scenic`](examples/isaacsim/forklift/common.scenic).

### Custom articulation control

For a robot that does not fit a built-in wheeled controller, provide a
`control` function that maps the Scenic behavior command to joint targets:

```scenic
model scenic.simulators.isaac.model
from scenic.simulators.isaac.backends import articulationAction

def velocityControl(command):
    return articulationAction(
        joint_velocities=command,
        joint_velocity_indices=[0, 1]
    )

class MyRobot(IsaacSimRobot):
    width: 0.5
    length: 0.5
    height: 0.5
    usdPath: localPath("assets/my_robot.usd")
    control: velocityControl

behavior MoveJoints():
    while True:
        take ApplyControllerAction([1.0, -1.0])
```

An articulation action can provide `joint_positions`, `joint_velocities`, or
`joint_efforts`, together with the corresponding joint index field
(`joint_position_indices` etc., or a shared `joint_indices`). This
controller form is shared by the direct Isaac Sim and Isaac Lab backends.

For a custom Isaac Lab task, define and register a normal manager-based Isaac
Lab configuration, then select it with `labTask` or expose its config class
through `labEnvCfg`. Scenic adds sampled objects to `cfg.scene`; if a Scenic
object name matches an existing scene field, the interface updates that
asset's initial pose instead of adding a duplicate asset.

### Manipulator arm

Manipulator arms are data-driven like the wheeled robots: a model class only
selects a profile, and the backends create and control any arm generically
from it.

```scenic
class FrankaPanda(ManipulatorRobot):
    shape: BoxShape()
    width: 0.3
    length: 0.3
    height: 0.9
    manipulatorProfile: FRANKA_PROFILE
```

A profile is a frozen dataclass (`ManipulatorProfile` in
`src/scenic/simulators/isaac/backends/profiles/base.py`) carrying the values
that cannot be inferred from the USD asset (joint roles, control link, home
pose, TCP offset, grasp orientation, gripper setpoints, drive/contact tuning)
plus dispatch keys:

| Key | Meaning |
| --- | --- |
| `gripperStyle` | Selects gripper-specific USD authoring and wrapper construction. `"robotiq_2f85"` uses the closed-loop Robotiq path and requires the extra fields declared by `UR5eProfile`; any other value is treated as a plain parallel gripper (optional `gripperActionDeltas`, e.g. `"franka_hand"`). |
| `gripperControlMode` | How open/close is commanded (`"position"` or `"velocity"`, the latter requiring the gripper velocity fields). |
| `supportsPickPlace` | Enables the built-in pick-place controller (`PickPlaceObject` behavior). Currently validated only with Franka-style position-mode parallel grippers. |

To add a new arm:

1. Define a profile instance in your own Python module next to your scenario
   (Scenic puts the scenario's directory on the import path). `usdPath` may
   be an Isaac asset reference (`Isaac/...`), a URL, or a local file path.
2. Attach it to a `ManipulatorRobot` subclass in your scenario:

   ```scenic
   model scenic.simulators.isaac.model
   from my_arm_profile import MY_ARM_PROFILE

   class MyArm(ManipulatorRobot):
       width: 0.3
       length: 0.3
       height: 0.8
       manipulatorProfile: MY_ARM_PROFILE
   ```

   The generic manipulator actions (`MoveToEEPoseAction`, gripper actions) and
   behaviors (`MoveEndEffectorTo`, `OpenGripper`, `CloseGripper`,
   `HoldPosition`) are reused unchanged; the end-effector move behaviors raise
   `ManipulatorTimeout` if a move does not converge within `maxSteps`.
3. Only if the arm uses a new gripper *mechanism* (not covered by an existing
   `gripperStyle`): add a `gripperStyle` branch for its USD authoring in the
   backends — the one case that still requires internal edits.
4. To contribute a robot upstream, move the profile to
   `backends/profiles/<arm>.py`, re-export it from
   `backends/profiles/__init__.py`, and add a thin model class in
   `model.scenic` as above.

The two backend families control the arms differently, bypassing the generic
`control` path above:

* `experimental_51` / `experimental_60` run a custom damped-least-squares
  differential-IK step per action with authored gripper drives; their built-in
  pick-place is a hand-rolled phase state machine whose approach/lift geometry
  and per-phase step counts are currently hardcoded in the backend.
* `core_51` uses Isaac's RMPFlow motion policies for end-effector motion and
  Isaac's `PickPlaceController` for the built-in pick-place.

## G1 Rough Locomotion Example

This example workflow trains a Unitree G1 rough-terrain policy in Isaac Lab, evaluates
it on Scenic terrain, optionally continues training on Scenic terrain, and
then evaluates the updated checkpoint.

### 1. Train a baseline G1 policy

From the Isaac Lab repository:

```bash
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py \
  --task Isaac-Velocity-Rough-G1-v0 \
  --num_envs 4096 \
  --headless
```

Isaac Lab writes the checkpoint under a directory such as:

```text
IsaacLab/logs/rsl_rl/g1_rough/<timestamp>/model_<iteration>.pt
```

Reduce `--num_envs` if the GPU does not have enough memory.

### 2. Place the checkpoint in the Scenic log tree

From the Scenic repository:

```bash
mkdir -p logs/rsl_rl/g1_rough/baseline
cp /path/to/model_2999.pt logs/rsl_rl/g1_rough/baseline/
```

### 3. Play the baseline policy on Scenic terrain

```bash
python src/scenic/simulators/isaac/scripts/play_scenic.py \
  --task Isaac-Velocity-Rough-G1-Play-v0 \
  --checkpoint logs/rsl_rl/g1_rough/baseline/model_2999.pt \
  --num_envs 32 \
  --scenario examples/isaacsim/terrain/random_uniform.scenic
```

The scenario combines randomized uniform noise, a pyramid slope, discrete
obstacles, and pyramid stairs. The G1 task keeps its robot, observations,
commands, rewards, and policy interface while its normal terrain generator is
replaced with the sampled Scenic terrain.

### 4. Continue training on Scenic terrain

```bash
python src/scenic/simulators/isaac/scripts/train_scenic.py \
  --task Isaac-Velocity-Rough-G1-v0 \
  --num_envs 4096 \
  --scenario examples/isaacsim/terrain/random_uniform.scenic \
  --resume \
  --load_run baseline \
  --checkpoint model_2999.pt \
  --headless
```

The continued run is written under:

```text
logs/rsl_rl/g1_rough/<new-timestamp>/
```

### 5. Evaluate the continued checkpoint

```bash
python src/scenic/simulators/isaac/scripts/play_scenic.py \
  --task Isaac-Velocity-Rough-G1-Play-v0 \
  --checkpoint logs/rsl_rl/g1_rough/<new-timestamp>/model_5998.pt \
  --num_envs 32 \
  --scenario examples/isaacsim/terrain/random_uniform.scenic
```

Replace the checkpoint names and run directory with the files produced by
your runs. Add `--headless` for non-interactive playback or `--video` to
record the evaluation.

## Known Issues

* Small differences can remain between Scenic geometry and the corresponding
  Isaac USD geometry/colliders, especially for converted or complex assets.
  The backends compensate for USD bounding-box offsets when placing assets,
  but scenarios using `mutate` can still expose unexpected intersections.
* Repairing a complex converted mesh may not produce a reasonable volume.
* Manipulator profiles contain values that cannot be inferred reliably from
  USD: arm/gripper joint roles, control link, TCP, home pose, grasp
  orientation, and open/closed gripper meaning. They are valid only for the
  exact asset and variant named by the profile, and gripper drive/contact
  values may need manual tuning for a different asset or task. Some values
  could in principle be read from the initialized articulation instead (DOF
  names, joint limits, authored drive gains); DOF names are already validated
  against the live articulation. Example clearances and thresholds are
  scenario policy, exposed as Scenic parameters.
* `armMaxVelocities` is honored by the experimental backends (joint-velocity
  clamp); the `core_51` RMPFlow path ignores it.
* A local copy of the Isaac Sim assets can be obtained
  [here](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html#isaac-sim-latest-release).

## Troubleshooting

If Isaac Sim or Isaac Lab stops working after installing Scenic-related
packages, first check whether pip replaced an Isaac dependency:

```bash
python -m pip check
python -m pip freeze | grep -E \
  "isaacsim|isaaclab|torch|numpy|scipy|trimesh|antlr4|opencv"
```

For reference, here is the working Isaac Sim 5.1 environment used at the time of testing:

| Package | Version |
| --- | --- |
| `isaacsim` | `5.1.0.0` |
| `torch` | `2.7.0+cu128` |
| `torchvision` | `0.22.0+cu128` |
| `numpy` | `1.26.0` |
| `scipy` | `1.15.3` |
| `trimesh` | `4.5.1` |
| `antlr4-python3-runtime` | `4.9.3` |
| `opencv-python` | `4.11.0.86` |
| `verifai` | `2.2.0` |
| `GPy` | `1.13.2` |
| `GPyOpt` | `1.2.6` |

Do not apply these 5.1 pins to an Isaac Sim 6.0 environment.

Other common checks:

* Confirm that the selected `isaacBackend` matches the installed Isaac Sim
  release.
* Confirm that an Isaac Lab task is manager-based; Direct task configs are not
  accepted by the general Scenic-to-Lab simulator.
* Apply the `configclass.py` change above if Scenic terrain validation descends
  into `class_type`.
* Expect the first Isaac Sim launch to download and cache extensions and
  assets, which can take several minutes.
* Use `-b` with the Scenic CLI or `--help` with the Lab scripts when diagnosing
  startup and argument issues.
