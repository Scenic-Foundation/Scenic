..  _api:

Using Scenic Programmatically
=============================

While Scenic is most easily invoked as a command-line tool, it also provides a Python API
for compiling Scenic programs, sampling scenes from them, and running dynamic
simulations.

Compiling Scenarios and Generating Scenes
-----------------------------------------

The top-level interface to Scenic is provided by two functions in the ``scenic`` module
which compile a Scenic program:

.. autofunction:: scenic.scenarioFromFile

.. autofunction:: scenic.scenarioFromString

The resulting `Scenario` object represents the abstract scenario defined by the Scenic
program. To sample concrete scenes from this object, you can call the `Scenario.generate`
method, which returns a `Scene`. If you are only using static scenarios, you can extract
the sampled values for all the global parameters and objects in the scene from the
`Scene` object. For example:

.. testsetup::

	import os
	os.chdir('..')

.. testcode::

	import random, scenic
	random.seed(12345)
	scenario = scenic.scenarioFromString('ego = new Object with foo Range(0, 5)')
	scene, numIterations = scenario.generate()
	print(f'ego has foo = {scene.egoObject.foo}')

.. testoutput::

	ego has foo = 2.083099362726706

Running Dynamic Simulations
---------------------------

To run dynamic scenarios, you must instantiate an instance of the `Simulator` class for
the particular simulator you want to use. Each simulator interface that supports dynamic
simulations defines a subclass of `Simulator`; for example, `NewtonianSimulator` for the
simple Newtonian simulator built into Scenic. These subclasses provide simulator-specific
functionality, and have different requirements for their use: see the specific
documentation of each interface under `scenic.simulators` for details.

Once you have an instance of `Simulator`, you can ask it to run a simulation from a
`Scene` by calling the `Simulator.simulate` method. If Scenic is able to run a simulation
that satisfies all the requirements in the Scenic program (potentially after multiple
attempts -- Scenic uses rejection sampling), this method will return a `Simulation`
object. Results of the simulation can then be obtained by inspecting its ``result``
attribute, which is an instance of `SimulationResult` (simulator-specific subclasses of
`Simulation` may also provide additional information). For example:

.. testcode::

	import scenic
	from scenic.simulators.newtonian import NewtonianSimulator
	scenario = scenic.scenarioFromFile('examples/driving/badlyParkedCarPullingIn.scenic',
	                                   model='scenic.simulators.newtonian.driving_model',
	                                   mode2D=True)
	scene, _ = scenario.generate()
	simulator = NewtonianSimulator()
	simulation = simulator.simulate(scene, maxSteps=10)
	if simulation:	# `simulate` can return None if simulation fails
		result = simulation.result
		for i, state in enumerate(result.trajectory):
			egoPos, parkedCarPos = state
			print(f'Time step {i}: ego at {egoPos}; parked car at {parkedCarPos}')

.. testoutput::
	:hide:
	:options: +ELLIPSIS

	Time step 0: ego at ...; parked car at ...
	Time step 1: ego at ...; parked car at ...
	Time step 2: ego at ...; parked car at ...
	Time step 3: ego at ...; parked car at ...
	Time step 4: ego at ...; parked car at ...
	Time step 5: ego at ...; parked car at ...
	Time step 6: ego at ...; parked car at ...
	Time step 7: ego at ...; parked car at ...
	Time step 8: ego at ...; parked car at ...
	Time step 9: ego at ...; parked car at ...
	Time step 10: ego at ...; parked car at ...

If you want to monitor data from simulations to see if the system you are testing
violates its specfications, you may want to use `VerifAI`_ instead of implementing your
own code along the lines above. VerifAI supports running tests from Scenic programs,
specifying system specifications using temporal logic or arbitrary Python monitor
functions, actively searching the space of parameters in a Scenic program to find
concrete scenarios where the system violates its specs [#f1]_, and more. See the VerifAI
documentation for details.

.. _serialization:

Storing Scenes/Simulations for Later Use
----------------------------------------

`Scene` and `Simulation` objects are heavyweight and not themselves suitable for bulk
storage or transmission over a network [#f2]_. However, Scenic provides serialization
routines which can encode such objects into relatively short sequences of bytes. Compact
encodings are achieved by storing only the sampled values of the primitive random
variables in the scenario: all non-random information is obtained from the original
Scenic file.

Having compiled a Scenic scenario into a `Scenario` object, any scenes you generate from
the scenario can be encoded as bytes using the `Scenario.sceneToBytes` method. For
example, to save a scene to a file one could use code like the following:

.. testcode::

	import scenic, tempfile, pathlib
	scenario = scenic.scenarioFromFile('examples/gta/parkedCar.scenic', mode2D=True)
	scene, _ = scenario.generate()
	data = scenario.sceneToBytes(scene)
	with open(pathlib.Path(tempfile.gettempdir()) / 'test.scene', 'wb') as f:
		f.write(data)
	print(f'ego car position = {scene.egoObject.position}')

.. testoutput::
	:hide:

	ego car position = ...

Then you could restore the scene in another process, obtaining the same position for the ego car:

.. testcode::

	import scenic, tempfile, pathlib
	scenario = scenic.scenarioFromFile('examples/gta/parkedCar.scenic', mode2D=True)
	with open(pathlib.Path(tempfile.gettempdir()) / 'test.scene', 'rb') as f:
		data = f.read()
	scene = scenario.sceneFromBytes(data)
	print(f'ego car position = {scene.egoObject.position}')

.. testoutput::
	:hide:

	ego car position = ...

.. testcleanup::

	import pathlib, tempfile
	path = pathlib.Path(tempfile.gettempdir()) / 'test.scene'
	path.unlink()
	os.chdir('docs')

Notice how we need to compile the scenario a second time in order to decode the scene,
if the original `Scenario` object is not available. If you need to send a large number
of scenes from one computer to another, for example, it suffices to send the Scenic file
for the underlying scenario, plus the encodings of each of the scenes.

You can encode and decode simulations run from a `Scenario` in a similar way, using the
`Scenario.simulationToBytes` and `Scenario.simulationFromBytes` methods. One additional
concern when replaying a serialized simulation is that if your simulator is not
deterministic (or you change the simulator configuration), the original simulation and
its replay can diverge, leading to unexpected behavior or exceptions. Scenic can attempt
to detect such divergences by saving the exact history of the simulation and comparing
it to the replay, but this greatly increases the size of the encoded simulation. See
`Simulator.simulate` for the available options.

.. note::

	The serialization format used for scenes and simulations is suitable for long-term
	storage (for instance if you want to save all the simulations you've run so that you
	can return to one later for further analysis), but it is not guaranteed to be
	compatible across major versions of Scenic.

.. _xosc_export:

OpenScenarioXML Export
----------------------

Scenic provides experimental support for exporting completed simulations via `toOpenScenario`.
This function currently only supports cars and pedestrians, and may be subject to breaking changes
in the future.

.. versionadded:: unreleased

.. seealso:: If you get exceptions or unexpected behavior when using the API, Scenic provides various debugging features: see :ref:`debugging`.

.. rubric:: Footnotes

.. [#f1] VerifAI's active samplers can be used directly from Scenic when VerifAI is
	installed. See `scenic.core.external_params`.

.. [#f2] If you really do need to store/transmit such objects, you may be able to do so
	using `dill`_, a drop-in replacement for Python's standard `pickle` library. Be aware
	that pickling will produce much larger encodings than Scenic's own APIs, as they need
	to include all the information present in the original Scenic file and its associated
	resources (e.g. for driving scenarios, the entire road map). Unpickling malicious
	files can also trigger arbitrary code execution, while Scenic's deserialization APIs
	can be used with untrusted data (as long as you trust the Scenic program you're
	running, of course).

.. _VerifAI: https://verifai.readthedocs.io/

.. _dill: https://pypi.org/project/dill/
