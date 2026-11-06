..  _simulators:

********************
Supported Simulators
********************

Scenic is designed to be easily interfaced to any simulator (see :ref:`new_simulator`).
On this page we list interfaces that we and others have developed; if you have a new interface, let us know and we'll list it here!

Note that not every interface supports all Scenic features: in particular, some interfaces do not support dynamic scenarios.
See the individual entries for details on each interface's capabilities and how to set it up.

.. note::
	While Scenic aims to support multiple Python versions, some simulators may have more limited compatibility.
	Be sure to check the documentation of each simulator to confirm which Python versions are supported.

.. note::
	Scenic also supports outputting data in formats that may be imported into other simulators and tools (e.g. :ref:`xosc_export`).
	For more details, see :ref:`serialization`.

.. contents:: List of Simulators
   :local:

Currently Supported
===================

.. _metadrive_simulator:

MetaDrive
----------------------------

Scenic supports integration with the `MetaDrive <https://metadriverse.github.io/metadrive/>`_ simulator as an optional dependency,
enabling users to describe dynamic simulations of vehicles, pedestrians, and traffic scenarios.
You can install it with:

.. code-block:: console

    python -m pip install scenic[metadrive]

.. note::

   MetaDrive **0.4.3** (the current PyPI release) does **not** support Python 3.12/3.13.
   It also has known issues on macOS Apple Silicon (M-series) with 3D rendering and a
   braking issue where vehicles may not come to a complete stop.

   To use Python 3.12+ **and** get the fixes for the macOS/braking issues, install
   MetaDrive from the GitHub repo:

   .. code-block:: console

      python -m pip install "metadrive-simulator @ git+https://github.com/metadriverse/metadrive.git@main"
      python -m pip install "sumolib >= 1.21.0"

Scenic supports both 2D and 3D rendering modes for MetaDrive simulations.

Scenic uses OpenDRIVE maps, while MetaDrive relies on SUMO maps. Scenic provides corresponding SUMO maps for OpenDRIVE maps under the :file:`assets/maps/CARLA` directory.
Additionally, you can convert your own OpenDRIVE maps to SUMO maps using the `netconvert <https://sumo.dlr.de/docs/Networks/Import/OpenDRIVE.html>`_ tool.
To avoid setting the SUMO map manually, name it the same as your OpenDRIVE file and place it in the same directory.
Otherwise, you can specify it explicitly using the ``sumo_map`` global parameter.

The simulator is compatible with scenarios written using Scenic's :ref:`driving_domain`.
For more information, refer to the documentation of the `scenic.simulators.metadrive` module.


Built-in Newtonian Simulator
----------------------------

To enable debugging of dynamic scenarios without having to install an external simulator, Scenic includes a simple 2D Newtonian physics simulator.
The simulator supports scenarios written using the cross-platform :ref:`driving_domain`, and can render top-down views showing the positions of objects relative to the road network.
See the documentation of the `scenic.simulators.newtonian` module for details.


CARLA
-----

Our interface to the `CARLA <https://carla.org/>`_ simulator enables using Scenic to describe autonomous driving scenarios.
The interface supports dynamic scenarios written using the CARLA world model (:obj:`scenic.simulators.carla.model`) as well as scenarios using the cross-platform :ref:`driving_domain`.
To use the interface, please follow these instructions:

1. Install the latest version of CARLA (we've tested versions 0.9.9 through 0.9.16) from the `CARLA Release Page <https://github.com/carla-simulator/carla/releases>`_.
   Note that CARLA currently only supports Linux and Windows.
2. Install Scenic in your Python virtual environment as instructed in :ref:`quickstart`.
3. Within the same virtual environment, install CARLA's Python API.
   How to do this depends on the CARLA version and whether you built it from source:

	.. tabs::

		.. tab:: 0.9.12+

			Run the following command, replacing ``X.Y.Z`` with the version of CARLA you installed:

			.. code-block:: text

				python -m pip install carla==X.Y.Z

		.. tab:: Older Versions

			For older versions of CARLA, you'll need to install its Python API from the provided ``.egg`` file.
			If your system has the :command:`easy_install` command, you can run:

			.. code-block:: text

				easy_install /PATH_TO_CARLA_FOLDER/PythonAPI/carla/dist/carla-0.9.9-py3.7-linux-x86_64.egg

			The exact name of the ``.egg`` file may vary depending on the version of CARLA you installed; make sure to use the file for Python 3, not 2.
			You may get an error message saying ``Could not find suitable distribution``, which you can ignore.

			The :command:`easy_install` command is deprecated and may not exist if you have a newer version of Python.
			In that case, you can try setting your ``PYTHONPATH`` environment variable to include the egg with a command like:

			.. code-block:: text

				export PYTHONPATH=/PATH_TO_CARLA_FOLDER/PythonAPI/carla/dist/carla-0.9.9-py3.7-linux-x86_64.egg

		.. tab:: Built from Source

			If you built CARLA from source, the process is more involved: see the detailed instructions `here <https://carla.readthedocs.io/en/latest/start_quickstart/#install-client-library>`__.

You can check that the ``carla`` package was correctly installed by running :command:`python -c 'import carla'`: if it prints ``No module named 'carla'``, the installation didn't work.
We suggest upgrading to a newer version of CARLA so that you can use :command:`pip` to install the Python API.

To start CARLA, run the command :command:`./CarlaUE4.sh` in your CARLA folder.
Once CARLA is running, you can run dynamic Scenic scenarios following the instructions in :ref:`the dynamics tutorial <dynamics_running_examples>`.


Grand Theft Auto V
------------------

The interface to `Grand Theft Auto V <https://www.rockstargames.com/V/>`_, used in `our PLDI paper`_, allows Scenic to position cars within the game as well as to control the time of day and weather conditions.
Many examples using the interface (including all scenarios from the paper) can be found in :file:`examples/gta`.
See the paper and `scenic.simulators.gta` for documentation.

Importing scenes into GTA V and capturing rendered images requires a GTA V plugin, which you can find `here <https://github.com/xyyue/scenic2gta>`__.


.. _isaac_sim:

Isaac Sim / Isaac Lab
---------------------

Scenic has an experimental interface to the `Isaac Sim <https://developer.nvidia.com/isaac/sim>`_ and `Isaac Lab <https://developer.nvidia.com/isaac/lab>`_ robotics simulators from NVIDIA.
It has been tested with Isaac Sim 5.1 and 6.0, and Isaac Lab 2.3.
See the :file:`examples/isaacsim` folder for documentation and example Scenic scenarios using the interface.


.. note::

	This interface is experimental and the APIs it provides are subject to change.
	We plan to finalize the interface in the next minor release of Scenic.


Webots
------

We have several interfaces to the `Webots robotics simulator <https://cyberbotics.com/>`_, for different use cases.
Our main interface provides a generic world model that can be used with any Webots world and supports dynamic scenarios.
See the :file:`examples/webots` folder for example Scenic scenarios and Webots worlds using this interface, and `scenic.simulators.webots` for documentation.

Scenic currently interfaces with Webots versions greater than or equal to 2023a.

Scenic also includes more specialized world models for use with Webots:

	* A general model for traffic scenarios, used in `our VerifAI paper`_.
	  Examples using this model can be found in the `VerifAI repository`_; see also the documentation of `scenic.simulators.webots.road`.

.. note::

	The last model above, and the example ``.wbt`` files for it, was written for the R2018 version of Webots.
	Relatively minor changes would be required to make it work with the newer `open source versions of Webots <https://github.com/cyberbotics/webots>`_.
	We may get around to porting them eventually; we'd also gladly accept a pull request!

.. _xplane:

X-Plane
-------

Our interface to the `X-Plane flight simulator <https://www.x-plane.com>`_ enables using Scenic to describe aircraft taxiing scenarios.
This interface is part of the VerifAI toolkit; documentation and examples can be found in the `VerifAI repository`_.

.. _our PLDI paper: https://arxiv.org/abs/1809.09310

.. _our VerifAI paper: https://doi.org/10.1007/978-3-030-25540-4_25

.. _VerifAI repository: https://github.com/BerkeleyLearnVerify/VerifAI

Deprecated
==========

Scenic previously provided interfaces to these simulators, but no longer does.
See individual entries for the last version of Scenic providing the interface and the reason it is no longer supported.

LGSVL
-----

The LGSVL simulator (a.k.a. SVL Simulator) was deprecated in Scenic 3.0, with the last version of Scenic supporting this simulator being 2.1. The original simulator is no longer usable due to LG shutting down its cloud service, but we are open to a PR targeting one of its forks.
