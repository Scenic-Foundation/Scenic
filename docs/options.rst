..  _options:

Command-Line Options
====================

The :command:`scenic` command supports a variety of options. Run :command:`scenic -h` for a full list
with short descriptions; we elaborate on some of the most important options below.

Options may be given before and after the path to the Scenic file to run, so the syntax of the command is:

.. code-block:: console

	$ scenic [options] FILE [options]

General Scenario Control
------------------------

.. option:: -m <model>, --model <model>

	Specify the :term:`world model` to use for the scenario, overriding any :keyword:`model` statement
	in the scenario. The argument must be the fully :term:`qualified name` of a Scenic module
	found on your :envvar:`PYTHONPATH` (it does not necessarily need to be built into
	Scenic).
	This allows scenarios written using a generic model, like that provided by the :ref:`driving_domain`, to be executed in a particular simulator (see the :ref:`dynamic scenarios tutorial <dynamics_running_examples>` for examples).

	The equivalent of this option for the Python API is the ``model`` argument to `scenic.scenarioFromFile`.

.. option:: -p <param> <value>, --param <param> <value>

	Specify the value of a :term:`global parameter`. This assignment overrides any
	:keyword:`param` statements in the scenario. If the given value can be interpreted as an
	`int` or `float`, it is; otherwise it is kept as a string.

	The equivalent of this option for the Python API is the ``params`` argument to `scenic.scenarioFromFile` (which, however, does not attempt to convert strings to numbers).

.. option:: --count <number>

	Number of successful scenes to generate or simulations to run (i.e., not counting rejected scenes/simulations).
	The default is to run forever.

.. option:: -s <seed>, --seed <seed>

	Specify the random seed used by Scenic, to make sampling deterministic.

	This option sets the seed for the Python random number generator :mod:`random`
	and the :mod:`numpy` random number generator :mod:`numpy.random`, so
	external Python code called from within Scenic can also be made deterministic
	(although :mod:`random` and :mod:`numpy.random` should not be used in place of
	Scenic's own sampling constructs in Scenic code).

	The seed can be set programatically using `scenic.setSeed`.

.. option:: --scenario <scenario>

	If the given Scenic file defines multiple scenarios, select which one to run.
	The named :term:`modular scenario` must not require any arguments.

	The equivalent of this option for the Python API is the ``scenario`` argument to `scenic.scenarioFromFile`.

.. option:: --2d

	Compile the scenario in :ref:`2D compatibility mode`.

	The equivalent of this option for the Python API is the ``mode2D`` argument to `scenic.scenarioFromFile`.

Dynamic Simulations
-------------------

.. option:: -S, --simulate

	Run dynamic simulations from scenes instead of plotting scene diagrams. This option
	will only work for scenarios which specify a simulator, which is done automatically
	by the :term:`world models` for the simulator interfaces that support dynamic scenarios, e.g.
	`scenic.simulators.carla.model` and `scenic.simulators.lgsvl.model`. If your scenario
	is written for an abstract domain, like `scenic.domains.driving`, you will need to
	use the :option:`--model` option to specify the specific model for the simulator you
	want to use.

.. option:: --time <steps>

	Maximum number of time steps to run each simulation (the default is infinity).
	Simulations may end earlier if termination criteria defined in the scenario are met (see :keyword:`terminate when` and :keyword:`terminate`).

Debugging
---------

.. option:: --version

	Show which version of Scenic is being used.

.. option:: -v <verbosity>, --verbosity <verbosity>

	Set the verbosity level, from 0 to 3 (default 1):

		0
			Nothing is printed except error messages and
			:doc:`warnings <python:library/warnings>` (to ``stderr``). Warnings can be
			suppressed using the :envvar:`PYTHONWARNINGS` environment variable.
		1
			The main steps of compilation and scene generation are indicated, with timing
			statistics.
		2
			Additionally, details on which modules are being compiled and the reasons for
			any scene/simulation rejections are printed.
		3
			Additionally, the :term:`actions` taken by each agent at each time step of a dynamic
			simulation are printed.

	This option can be configured from the Python API using `scenic.setDebuggingOptions`.

.. option:: --show-params

	Show values of :term:`global parameters` for each generated scene.

.. option:: --show-records

	Show recorded values (see :keyword:`record`) for each dynamic simulation.

.. option:: -b, --full-backtrace

	Include Scenic's internals in backtraces printed for uncaught exceptions.
	This information will probably only be useful if you are developing Scenic.

	This option can be enabled from the Python API using `scenic.setDebuggingOptions`.

.. option:: --pdb

	If an error occurs, enter the Python interactive debugger :mod:`pdb`.
	Implies the :option:`-b` option.

	This option can be enabled from the Python API using `scenic.setDebuggingOptions`.

.. option:: --pdb-on-reject

	If a scene/simulation is rejected (so that another must be sampled), enter :mod:`pdb`.
	Implies the :option:`-b` option.

	This option can be enabled from the Python API using `scenic.setDebuggingOptions`.

.. option:: --gather-stats

	Collect timing statistics over a specified number of scenes, rather than rendering
	diagrams. If the number is negative, it is considered a number of rejection sampling
	iterations rather than scenes (useful to reduce variability, and if the number of
	iterations required to generate a scene is very large).
