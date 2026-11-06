..  _whats_new:

What's New in Scenic
====================

This page describes what new features have been added in each version of Scenic, as well as any syntax changes which break backwards compatibility.
Scenic uses semantic versioning, so a program written for Scenic 2.1 should also work in Scenic 2.5, but not necessarily in Scenic 3.0.
You can run :command:`scenic --version` to see which version of Scenic you are using.

Scenic 3.x
++++++++++

The Scenic 3.x series adds native support for 3D geometry, precise modeling of the shapes of objects, and temporal requirements.
It also features a new parser enabling clearer error messages, greater language extensibility, and various improvements to the syntax.

See :ref:`porting to Scenic 3` for tools to help migrate existing 2D scenarios.

Unreleased
------------

Major new features:

	* Added an :ref:`interface <isaac_sim>` to the Isaac Sim and Isaac Lab robotics simulators.

	* Added `toOpenScenario`, which exports completed driving domain simulations as OpenScenarioXML files.


Minor new features:

	* Added a :ref:`minimum distance from` operator which computes the minimum distance between the occupied space of two objects.

Scenic 3.1.1
------------

Minor new features:

	* Added support for Python 3.14.


Scenic 3.1.0
------------

Major new features:

	* Added an :ref:`interface <metadrive_simulator>` to the MetaDrive driving simulator.

	* Added a new experimental sensors API with support for CARLA and MetaDrive (see :ref:`Sensors Reference <sensors>`).

	* Extended the :keyword:`record` statement to support saving time-series data directly to files via the ``to`` clause; see the :ref:`Language Reference <recordFolder>` for details.

	* Introduced :ref:`wait for <wait for {scalar} (seconds | steps)>` and :ref:`wait until <wait until {boolean}>`, which work like :ref:`do ... for <do {behavior/scenario}, {...} for {scalar} (seconds | steps)>` and :ref:`do ... until <do {behavior/scenario}, {...} until {boolean}>` but advance the scenario without taking any actions.

Minor new features:

	* Added support for Python 3.13.

	* Improved Scenic support for ``str``/``int``/``float`` conversions and type checking; these names are now reserved and can't be reassigned.

	* Added a :prop:`render` property to :class:`~scenic.core.object_types.Object` to let objects opt out of the internal visualizer, and fixed handling of face colors for object meshes.

	* Improved visual accuracy in the Newtonian physics simulator and added a ``debugRender`` visualization option (see :mod:`scenic.simulators.newtonian.driving_model`).

	* :class:`~scenic.simulators.carla.actions.SetAutopilotAction` now accepts optional CARLA Traffic Manager settings (ignoring signs/lights/walkers, automatic lane changes, target speed/route, and speed-limit offsets).

	* Added pedestrian movement support in the Newtonian physics simulator.

	* Expanded tested compatibility with CARLA to include version 0.9.16 (Scenic has been tested with CARLA 0.9.9–0.9.16).

	* Added :meth:`Network.shoulderAt <scenic.domains.driving.roads.Network.shoulderAt>` and :meth:`Network.sidewalkAt <scenic.domains.driving.roads.Network.sidewalkAt>`, updated :meth:`Network.elementAt <scenic.domains.driving.roads.Network.elementAt>` to return shoulders and sidewalks, and added a ``showCurbArrows`` option to :meth:`~scenic.domains.driving.roads.Network.show` for visualizing curb orientation in 2D plots.

Notable bug fixes:

	* Fixed :meth:`Network.roadDirection <scenic.domains.driving.roads.Network.roadDirection>` and :meth:`Network.nominalDirectionsAt <scenic.domains.driving.roads.Network.nominalDirectionsAt>` so objects on shoulders or inside intersections inherit the correct maneuver heading instead of defaulting to 0.

	* Fixed the default :prop:`velocity` of :class:`~scenic.core.object_types.Object` so it now derives from :prop:`speed` and :prop:`orientation`, as previously documented, instead of always being :scenic:`(0, 0, 0)`.

Scenic 3.0.0
------------

Backwards-incompatible syntax changes:

	* Objects must be explicitly created using the :keyword:`new` keyword, e.g. :scenic:`new Object at (1, 2)` instead of the old ``Object at (1, 2)``.
	  This removes an ambiguity in the Scenic grammar, and makes non-creation uses of class names like :scenic:`myClasses = [Car, Bicycle, Pedestrian]` clearer.

	* :ref:`Monitor definitions <monitorDef>` must include a parenthesized list of arguments, like behaviors: you should write :scenic:`monitor MyMonitor():` for example instead of the old ``monitor MyMonitor:``.
	  Furthermore, monitors are no longer automatically enforced in the scenario where they are defined: you must explicitly instantiate them with the new :keyword:`require monitor` statement.

	* As the :prop:`heading` property is now derived from the 3D :prop:`orientation` (see below), it can no longer be set directly.
	  Classes providing a default value for :prop:`heading` should instead provide a default value for :prop:`parentOrientation`.
	  Code like :specifier:`with heading 30 deg` should be replaced with the more idiomatic :specifier:`facing 30 deg`.

Backwards-incompatible semantics changes:

	* Objects are no longer required to be visible from the :scenic:`ego` by default.
	  (The :prop:`requireVisible` property is now :scenic:`False` by default.)

	* Visibility checks take occlusion into account by default (see below).
	  The :term:`visible regions` of objects are now 3D regions.

	* Checking containment of objects in regions is now precise (previously, Scenic only checked if all of the corners of the object were contained in the region).

	* While evaluating a precondition or invariant of a behavior or scenario, code that would cause the simulation to be rejected (such as sampling from an empty list) is now considered as simply making the precondition/invariant false.

	* The :sampref:`left of {Object}` specifier and its variants now correctly take into account the dimensions of both the object being created *and* the given object (the implementation previously did not account for the latter, despite the documentation saying otherwise).

	* The :specifier:`offset by` specifier now optionally specifies :prop:`parentOrientation`.

	* The :specifier:`visible` and :specifier:`not visible` specifiers now take into account occlusion and the shapes of objects. In previous versions, they only checked whether the center of the object was visible/not visible, ignoring occlusion.

Backwards-incompatible API changes:

	* The **maxIterations** argument of `Simulator.simulate` now has default value 1, rather than 100.
	  A default value of 1 is the most reasonable in general since it means that when a simulation is rejected, a new scene will have to be generated (instead of trying many simulations from the same starting scene, which might well fail in the same way).

	* For simulator interface writers: the `Simulator.createSimulation` and `Simulation` APIs have changed; initial creation of objects is now done automatically, and other initialization must be done in the new `Simulation.setup` method.
	  See `scenic.core.simulators` for details.

Major new features:

	* Scenic uses 3D geometry.
	  Vectors now have 3 coordinates: if a third coordinate is not provided, it is assumed to be zero, so that scenarios taking place entirely in the z=0 plane will continue to work as before.
	  Orientations of objects in space are represented by a new :prop:`orientation` property (internally a quaternion), which is computed by applying intrinsic :prop:`yaw`, :prop:`pitch`, and :prop:`roll` rotations, given by new properties by those names.
	  These rotations are applied to the object's :prop:`parentOrientation`, which by default aligns with the Scenic global coordinate system but is optionally specified by :keyword:`left of` and similar specifiers; this makes it easy to orient an object with respect to another object.
	  See the relevant section of the :ref:`tutorial <orientations_tutorial>` for examples.

	* Scenic models the precise shapes of objects, rather than simply using bounding boxes for collision detection and visibility checks.
	  Objects have a new :prop:`shape` property (an instance of the `Shape` class) representing their shape; shapes can be created from standard 3D mesh formats such as STL.

	* Visibility checks now take occlusion into account as well as precise shapes of objects.
	  This is done using raytracing: the number of rays can be controlled on a per-object basis using :prop:`viewRayDensity` and related properties.

	* The :keyword:`require` statement accepts arbitrary properties in Linear Temporal Logic (not just the :scenic:`require always` and :scenic:`require eventually` forms previously allowed).

	* Sampled `Scene` objects can now be serialized to short sequences of bytes and restored later.
	  Similarly, executed `Simulation` objects can be saved and replayed.
	  See :ref:`serialization` for details.

	* Scenic syntax highlighters for Sublime Text, Visual Studio Code, and other TextMate-compatible editors are now available: see :doc:`quickstart`.
	  For users of `Pygments <https://pygments.org/>`_, the ``scenic`` package automatically installs a Pygments lexer (and associated style) for Scenic.

Minor new features:

	* It is no longer necessary to define an :scenic:`ego` object.
	  If no :scenic:`ego` is defined, the ``egoObject`` attribute of a sampled `Scene` is `None`.

	* Syntax errors should now always indicate the correct part of the source code.

Scenic 2.x
++++++++++

The Scenic 2.x series is a major new version of Scenic which adds native support for dynamic scenarios, scenario composition, and more.

Scenic 2.1.0
------------

Major new features:

	* Modular scenarios and ways to compose them together, introduced as a prototype in 2.0.0, are now finalized, with many fixes and improvements. See :ref:`composition` for an overview of the new syntax.

	* The :keyword:`record` statement for recording values at every step of dynamic simulations (or only at the start/end).

	* A built-in Newtonian physics simulator for debugging dynamic scenarios without having to install an external simulator (see `scenic.simulators.newtonian`).

	* The interface to the Webots simulator has been greatly generalized, and now supports dynamic scenarios (see `scenic.simulators.webots`).

Minor new features:

	* You can now write :scenic:`require {expr} as {name}` to give a name to a requirement; similarly for :scenic:`require always`, termination conditions, etc.

	* Compatibility with Python 3.7 is restored. Scenic 2 now supports all versions of Python from 3.7 to 3.11.

Scenic 2.0.0
------------

Backwards-incompatible syntax changes:

	* The interval notation :scenic:`(low, high)` for uniform distributions has been removed: use :scenic:`Range(low, high)` instead. As a result of this change, the usual Python syntax for tuples is now legal in Scenic.

	* The :prop:`height` property of `Object`, measuring its extent along the Y axis, has been renamed :prop:`length` to better match its intended use. The name :prop:`height` will be used again in a future version of Scenic with native support for 3D geometry.

Major new features:

	* Scenic now supports writing and executing dynamic scenarios, where agents take actions over time according to behaviors specified in Scenic. See :ref:`dynamics` for an overview of the new syntax.

	* An abstract :ref:`driving_domain` allowing traffic scenarios to be written in a platform-agnostic way and executed in multiple simulators (in particular, both CARLA and LGSVL).
	  This library includes functionality to parse road networks from standard formats (currently OpenDRIVE) and expose information about them for use in Scenic scenarios.

	* A much generalized and improved interface to CARLA. (Many thanks to the CARLA team for contributing this.)

	* An interface to the LGSVL driving simulator. (Many thanks to the LG team for helping develop this interface.)

Minor new features:

	* Operators and specifiers which take vectors as arguments will now accept tuples and lists of length 2; for example, you can write :scenic:`Object at (1, 2)`. The old syntax :scenic:`Object at 1@2` is still supported.

	* The :keyword:`model` statement allows a scenario to specify which :term:`world model` it uses, while being possible to override from the command line with the :option:`--model` option.

	* Global parameters can be overridden from the command line using the :option:`--param` option (e.g. to specify a different map to use for a scenario).

	* The unpacking operator :scenic:`*` can now be used with :scenic:`Uniform` to select a random element of a random list/tuple (e.g. :scenic:`lane = Uniform(*network.lanes); sec = Uniform(*lane.sections)`).

	* The Python built-in function `filter` is now supported, and can be used along with unpacking as above to select a random element of a random list satisfying a given condition (see :ref:`filter_func` for an example).

(Many other minor features didn't make it into this list.)
