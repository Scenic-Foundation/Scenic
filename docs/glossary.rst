:orphan:

Glossary
========

.. glossary::
	:sorted:

	action
		A primitive operation executed by an agent during a single step of a dynamic
		simulation. For example, a car might take an action which sets its throttle, or
		turns on its headlights. Actions are defined by the simulator interfaces (or
		abstract domains like `scenic.domains.driving`) as subclasses of
		`Action`.

	agent
		A Scenic `Object` which has a :term:`dynamic behavior` (set as its :prop:`behavior` property).

	container
		The region specified as the :prop:`regionContainedIn` property of an `object`, or the
		entire :term:`workspace` if it is `None` (the default). A built-in requirement
		enforces that objects are completely contained in their containers: so by default
		all objects fit into the workspace, and particular kinds of objects can define
		more stringent requirements by overriding :prop:`regionContainedIn` (e.g. making cars
		be on roads by default).

	behavior
	dynamic behavior
		A function defining the behavior of an :term:`agent` during a simulation.
		The function runs in parallel with the simulation, taking :term:`actions` at each time step.
		See our tutorial on :ref:`dynamics` for examples.

	dynamic properties
		Properties of Scenic objects which are updated at each time step of a dynamic
		simulation. The built-in properties representing positions, orientations,
		velocities, etc. are all dynamic (see `Object`). See the source code of
		:obj:`scenic.domains.driving.model.DrivingObject` for an example of defining a
		dynamic property.

	external parameters
		Values which are determined by an external tool instead of Scenic's own sampler.
		These allow using optimization or other techniques to explore parameters of
		Scenic scenarios beyond simple random sampling. For how to define external
		parameters or interface to new external samplers, see
		:mod:`scenic.core.external_params`.

	footprint
		The infinite extrusion of a 2D `region` in the positive and negative Z directions.
		Testing containment of an `object` in a 2D region automatically uses its footprint, so that the object is considered contained if and only if its projection into the plane of the region is contained in the region.
		Footprints are represented internally by instances of the `PolygonalFootprintRegion` class, and can be accessed using the ``footprint`` attribute.

	global parameters
		Parameters of a scene like weather or time of day which are not associated with any object.
		These are defined using the :keyword:`param` statement, and can be overridden from the command line with the :option:`--param` option.

	modular scenario
		A scenario defined using the :keyword:`scenario <scenario-stmt>` statement (rather than simply being the content of a Scenic file).
		Such scenarios can take arguments, be instantiated multiple times, and be composed with other scenarios: see :ref:`composition`.

	monitor
		A function which runs in parallel with a simulation, rejecting or terminating the simulation if conditions of interest are met (using the :keyword:`require` and :keyword:`terminate` statements).
		Monitors use similar syntax to :term:`dynamic behaviors`, except that they are not associated with a specific `Object` and do not take actions (only using :keyword:`wait` to advance time).

	preferred orientation
		A `vector field` set as the ``orientation`` attribute of a `Region`, indicating that objects placed within that region should be oriented to align along that vector field unless otherwise specified.
		For example, the :obj:`~scenic.domains.driving.model.road` region provided by the :ref:`driving_domain` has as its preferred orientation the :obj:`~scenic.domains.driving.model.roadDirection` vector field, so that vehicles positioned using the specifier :specifier:`on road` will be facing the nominal traffic direction at their position by default (but an explicit :specifier:`facing {H}` specifier will override it).

	temporal requirement
		A :keyword:`require` statement using one or more temporal operators (:keyword:`always`, :keyword:`until`, etc.) to impose a requirement over an entire simulation rather than just the generated scene.
		For example, :scenic:`require always X` requires not only that the condition ``X`` be true in any scenes sampled from the scenario, but that it remain true at every time step of simulations run from those scenes.
		Note that temporal requirements are evaluated twice before the simulation starts, once before connecting to the simulator, and once after when initial object values are read back from the simulator. This allows the requirements to account for simulators that alter dynamic properties of objects at time 0.

	visible region
		The `Region` which is "visible" from a given `Object`. See the :ref:`Visibility System <visibility>` reference for more details.

	workspace
		The region of space in which a scenario takes place.
		Workspaces are represented as instances of the :obj:`~scenic.core.workspaces.Workspace` class, which extends `Region` with additional methods for rendering schematics of scenes for debugging.
		The default workspace contains all space, so it puts no restrictions on the locations of objects.
		A :term:`world model` can define a more specific workspace to exclude space occupied by fixed objects in the simulated world which aren't otherwise known to Scenic (e.g. buildings in GTA V or CARLA).

	world model
		A Scenic library defining classes, regions, :term:`actions`, helper functions, etc. for use by scenarios targeting a particular simulator or application domain.
		For example, the world model for the :ref:`driving_domain`, `scenic.domains.driving.model`, defines classes for vehicles, actions for steering, and regions for different parts of the road network.
		In the line :scenic:`new Car in intersection`, only the :keyword:`new` keyword and :keyword:`in` specifier are built into Scenic: the class :obj:`~scenic.domains.driving.model.Car` and the region :obj:`~scenic.domains.driving.model.intersection` are defined by the world model.
		A world model can be used through the :keyword:`model` statement, or simply by importing it like any other Scenic module.

		.. seealso:: :ref:`defining_world_model` gives further examples and details on how to write a world model.
