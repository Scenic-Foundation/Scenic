..  _statements:

***********************************
Statements Reference
***********************************

Compound Statements
===================

.. _classDef:

Class Definition
----------------

.. code-block:: scenic-grammar

    class <name>[(<superclass>)]:
        [<property>: <value>]*

Defines a Scenic class.
If a superclass is not explicitly specified, `Object` is used (see :ref:`objects_and_classes`).
The body of the class defines a set of properties its objects have, together with default values for each property.
Properties are inherited from superclasses, and their default values may be overridden in a subclass.
Default values may also use the special syntax :scenic:`self.{property}` to refer to one of the other properties of the same object, which is then a *dependency* of the default value.
The order in which to evaluate properties satisfying all dependencies is computed (and cyclic dependencies detected) during :ref:`specifier resolution`.

Scenic classes may also define attributes and methods in the same way as Python classes.

.. _behaviorDef:

Behavior Definition
--------------------

.. code-block:: scenic-grammar

    behavior <name>(<arguments>):
        [precondition: <boolean>]*
        [invariant: <boolean>]*
        <statement>+

Defines a :term:`dynamic behavior`, which can be assigned to a Scenic object by setting its :prop:`behavior` property using the :scenic:`with behavior {behavior}` specifier; this makes the object an :term:`agent`.
See our tutorial on :ref:`dynamics` for examples of how to write behaviors.

Behavior definitions have a similar form to function definitions, with an argument list and a body consisting of one or more statements.
A behavior may not use top-level definitional statements such as :keyword:`param`, :keyword:`mutate`, and :keyword:`terminate when`, and it cannot create Objects with :keyword:`new`.
However, the :keyword:`require` statement *is* allowed, as are ordinary control-flow constructs and function definitions.
In addition, there are many special statements allowed in behaviors to take actions, invoke sub-behaviors, etc.: see :ref:`dynamic_statements`.

The body of a behavior may optionally begin with definitions of preconditions and invariants.
Preconditions are checked when a behavior is started, and invariants are checked at every time step of the simulation while the behavior is executing (including time step zero, like preconditions, but *not* including time spent inside sub-behaviors: this allows sub-behaviors to break and restore invariants before they return).

The body of a behavior executes in parallel with the simulation: in each time step, it must either :keyword:`take` specified action(s) or :keyword:`wait` and perform no actions.
After each :keyword:`take` or :keyword:`wait` statement, the behavior's execution is suspended, the simulation advances one step, and the behavior is then resumed.
It is thus an error for a behavior to enter an infinite loop which contains no :keyword:`take` or :keyword:`wait` statements (or :keyword:`do` statements invoking a sub-behavior; see below): the behavior will never yield control to the simulator and the simulation will stall.

Behaviors end naturally when their body finishes executing (or if they :scenic:`return`): if this happens, the agent performing the behavior will take no actions for the rest of the scenario.
Behaviors may also :keyword:`terminate` the current scenario, ending it immediately.

Behaviors may invoke sub-behaviors, optionally for a limited time or until a desired condition is met, using :keyword:`do` statements.
It is also possible to (temporarily) interrupt the execution of a sub-behavior under certain conditions and resume it later, using :ref:`try-interrupt <try>` statements.

.. _monitorDef:

Monitor Definition
------------------

.. code-block:: scenic-grammar

    monitor <name>(<arguments>):
        <statement>+

Defines a type of :term:`monitor`, which can be run in parallel with the simulation like a :term:`dynamic behavior`.
Monitors are not associated with an `Object` and cannot take actions, but can :keyword:`wait` to wait for the next time step (or use :keyword:`terminate` or :keyword:`terminate simulation` to end the scenario/simulation).
A monitor can be instantiated in a scenario with the :keyword:`require monitor` statement.

The main purpose of monitors is to evaluate complex temporal properties that are not expressible using the temporal operators available for :sampref:`require {LTL formula}` statements.
They can maintain state and use :keyword:`require` to enforce requirements depending on that state.
For examples of monitors, see our tutorial on :ref:`dynamics`.

.. versionchanged:: 3.0
    Monitors may take arguments, and must be explicitly instantiated using a :keyword:`require monitor` statement.

.. _modularScenarioDef:
.. _scenario-stmt:
.. _setup:
.. _compose:

Modular Scenario Definition
---------------------------

.. code-block:: scenic-grammar

    scenario <name>(<arguments>):
        [precondition: <boolean>]*
        [invariant: <boolean>]*
        [setup:
            <statement>+]
        [compose:
            <statement>+]

.. code-block:: scenic-grammar

    scenario <name>(<arguments>):
        <statement>+

Defines a Scenic :term:`modular scenario`.
Scenario definitions, like :ref:`behavior definitions <behaviorDef>`, may include preconditions and invariants.
The body of a scenario consists of two optional parts: a ``setup`` block and a ``compose`` block.
The ``setup`` block contains code that runs once when the scenario begins to execute, and is a list of statements like a top-level Scenic program (so it may create objects, define requirements, etc.).
The ``compose`` block orchestrates the execution of sub-scenarios during a dynamic scenario, and may use :keyword:`do` and any of the other statements allowed inside a :ref:`behavior <behaviorDef>` (except :keyword:`take`, which only makes sense for an individual :term:`agent`).
The constructs illegal in behaviors, such as defining global parameters and creating Objects with :keyword:`new`, are also illegal in ``compose`` blocks: they can be placed in the ``setup`` block of a sub-scenario instead.

If a modular scenario does not use preconditions, invariants, or sub-scenarios (i.e., it only needs a ``setup`` block) it may be written in the second form above, where the entire body of the ``scenario`` comprises the ``setup`` block.

.. seealso:: Our tutorial on :ref:`composition` gives many examples of how to use modular scenarios.

.. _tryInterruptStmt:
.. _try-interrupt:

Try-Interrupt Statement
-----------------------

.. code-block:: scenic-grammar

    try:
        <statement>+
    [interrupt when <boolean>:
        <statement>+]*
    [except <exception> [as <name>]:
        <statement>+]*

A ``try-interrupt`` statement can be placed inside a behavior (or :keyword:`compose` block of a :term:`modular scenario`) to run a series of statements, including invoking sub-behaviors with :keyword:`do`, while being able to interrupt at any point if given conditions are met.
When a ``try-interrupt`` statement is encountered, the statements in the ``try`` block are executed.
If at any time step one of the ``interrupt`` conditions is met, the corresponding ``interrupt`` block (its *handler*) is entered and run.
Once the interrupt handler is complete, control is returned to the statement that was being executed under the ``try`` block.

If there are multiple ``interrupt`` clauses, successive clauses take precedence over those which precede them; furthermore, during execution of an interrupt handler, successive ``interrupt`` clauses continue to be checked and can interrupt the handler.
Likewise, if ``try-interrupt`` statements are nested, the outermost statement takes precedence and can interrupt the inner statement at any time.
When one handler interrupts another and then completes, the original handler is resumed (and it may even be interrupted again before control finally returns to the ``try`` block).

The ``try-interrupt`` statement may conclude with any number of ``except`` blocks, which function identically to their :ref:`Python counterparts <except>` (though Scenic does not allow ``except*`` blocks).

Simple Statements
=================

The following statements can occur throughout a Scenic program unless otherwise stated.

.. _model {name}:
.. _model:

model *name*
------------
Select a :term:`world model` to use for this scenario.
The statement :scenic:`model {X}` is equivalent to :scenic:`from {X} import *` except that :scenic:`{X}` can be replaced using the :option:`--model` command-line option or the ``model`` keyword argument to the top-level APIs.
When writing simulator-agnostic scenarios, using the :scenic:`model` statement is preferred to a simple :scenic:`import` since a more specific world model for a particular simulator can then be selected at compile time.

.. _import {module}:
.. _import:

import *module*
----------------
Import a Scenic or Python module. This statement behaves :ref:`as in Python <import>`, but when importing a Scenic module it also imports any objects created and requirements imposed in that module.
Scenic also supports the form :scenic:`from {module} import {identifier}, {...}` , which as in Python imports the module plus one or more identifiers from its namespace.

.. _param {name} = {value}, {...}:
.. _param:

param *name* = *value*, . . .
---------------------------------------
Defines one or more :term:`global parameters` of the scenario.
These have no semantics in Scenic, simply having their values included as part of the generated `Scene`, but provide a general-purpose way to encode arbitrary global information.

If multiple :scenic:`param` statements define parameters with the same name, the last statement takes precedence, except that Scenic world models imported using the :keyword:`model` statement do not override existing values for global parameters.
This allows models to define default values for parameters which can be overridden by particular scenarios.
Global parameters can also be overridden at the command line using the :option:`--param` option, or from the top-level API using the ``params`` argument to `scenic.scenarioFromFile`.

To access global parameters within the scenario itself, you can read the corresponding attribute of the :scenic:`globalParameters` object.
For example, if you declare :scenic:`param weather = 'SUNNY'`, you could then access this parameter later in the program via :scenic:`globalParameters.weather`.
If the parameter was not overridden, this would evaluate to :scenic:`'SUNNY'`; if Scenic was run with the command-line option ``--param weather SNOW``, it would evaluate to :scenic:`'SNOW'` instead.

Some simulators provide global parameters whose names are not valid identifiers in Scenic.
To support giving values to such parameters without renaming them, Scenic allows the names of global parameters to be quoted strings, as in this example taken from an :ref:`X-Plane <xplane>` scenario::

    param simulation_length = 30
    param 'sim/weather/cloud_type[0]' = DiscreteRange(0, 5)
    param 'sim/weather/rain_percent' = 0

.. _require {boolean}:
.. _require:

require *boolean*
------------------
Defines a hard requirement, requiring that the given condition hold in all instantiations of the scenario.
This is equivalent to an "observe" statement in other probabilistic programming languages.

.. _require[{number}] {boolean}:
.. _soft-requirements:

require[*number*] *boolean*
---------------------------
Defines a soft requirement; like :keyword:`require` above but enforced only with the given probability, thereby requiring that the given condition hold with at least that probability (which must be a literal number, not an expression).
For example, :scenic:`require[0.75] ego in parking_lot` would require that the ego be in the parking lot at least 75% percent of the time.

.. _require {LTL formula}:

require *LTL formula*
---------------------
Defines a :term:`temporal requirement`, requiring that the given Linear Temporal Logic formula hold in a dynamic scenario.
See :ref:`temporal operators` for the list of supported LTL operators.

Note that an expression that does not use any temporal operators is evaluated only in the current time step.
So for example:

* :scenic:`require A and always B` will only require that ``A`` hold at time step zero, while ``B`` must hold at every time step (note that this is the same behavior you would get if you wrote :scenic:`require A` and :scenic:`require always B` separately);
* :scenic:`require (always A) implies B` requires that if ``A`` is true at every time step, then ``B`` must be true at time step zero;
* :scenic:`require always A implies B` requires that in *every* time step when ``A`` is true, ``B`` must also be true (since ``B`` is within the scope of the :keyword:`always` operator).

.. _require monitor {monitor}:
.. _require monitor:

require monitor *monitor*
-------------------------
Require a condition encoded by a :term:`monitor` hold during the scenario.
See :ref:`monitorDef` for how to define types of monitors.

It is legal to create multiple instances of a monitor with varying parameters.
For example::

    monitor ReachesBefore(obj1, region, obj2):
        reached = False
        while not reached:
            if obj1 in region:
                reached = True
            else:
                require obj2 not in region
                wait

    require monitor ReachesBefore(ego, goal, racecar2)
    require monitor ReachesBefore(ego, goal, racecar3)

.. _terminate when {boolean}:
.. _terminate when:

terminate when *boolean*
------------------------
Terminates the scenario when the provided condition becomes true.
If this statement is used in a :term:`modular scenario` which was invoked from another scenario, only the current scenario will end, not the entire simulation.

.. _terminate simulation when {boolean}:
.. _terminate simulation when:

terminate simulation when *boolean*
-----------------------------------
The same as :keyword:`terminate when`, except terminates the entire simulation even when used inside a sub-scenario (so there is no difference between the two statements when used at the top level).

.. _terminate after {scalar} (seconds | steps):
.. _terminate after:

terminate after *scalar* (seconds | steps)
------------------------------------------
Like :keyword:`terminate when` above, but terminates the scenario after the given amount of time.
The time limit can be an expression, but must be a non-random value.

.. _mutate {identifier}, {...} [by {number}]:
.. _mutate:

mutate *identifier*, . . . [by *scalar*]
-----------------------------------------
Enables mutation of the given list of objects (any `Point`, `OrientedPoint`, or `Object`), with an optional scale factor (default 1).
If no objects are specified, mutation applies to every `Object` already created.

The default mutation system adds Gaussian noise to the :prop:`position` and :prop:`heading` properties, with standard deviations equal to the scale factor times the :prop:`positionStdDev` and :prop:`headingStdDev` properties.

.. note::

    User-defined classes may specify custom mutators to allow mutation to apply to properties other than :prop:`position` and :prop:`heading`.
    This is done by providing a value for the :prop:`mutator` property, which should be an instance of `Mutator`.
    Mutators inherited from superclasses (such as the default :prop:`position` and :prop:`heading` mutators from `Point` and `OrientedPoint`) will still be applied unless the new mutator disables them; see `Mutator` for details.

.. _record [initial | final] {value} {...}:
.. _record:
.. _record initial:
.. _record final:

record [initial | final] *value* [as *name*]
----------------------------------------------
Record the value of an expression during each simulation.
The value can be recorded at the start of the scenario (``initial``), at the end of the scenario (``final``), or at every time step during the scenario (if neither ``initial`` nor ``final`` is specified).
The recorded values are available in the ``records`` dictionary of `SimulationResult`: its keys are the given names of the records (or synthesized names if not provided), and the corresponding values are either the value of the recorded expression or a tuple giving its value at each time step as appropriate.
For debugging, the records can also be printed out using the :option:`--show-records` command-line option.

When recording an entire time series (i.e. not using ``initial`` or ``final``), additional options are available, described below.

.. _recordFolder:

record *value* [every *duration*] [after *duration*] [as *name*] [to *recorder*]
--------------------------------------------------------------------------------
Record the value of an expression as a time series.
The ``every`` clause allows specifying the interval between entries of the series, either in ``steps`` or ``seconds`` (the latter being rounded down to a whole number of time steps).
Likewise, the ``after`` clause allows specifying an initial delay before recording starts.
The ``as`` clause gives the name of the record in the final `SimulationResult` as above.

The ``to`` clause allows records to be directly saved to files in common formats.
In the most basic usage, you can pass a string giving the filename to save the time series to: the format will be determined automatically based on the file extension.
For example, the clause ``to "foo.mp4"`` will save the data as an MP4 video file (assuming the given value can be interpreted as an image).
The string can use Python :ref:`formatstrings` to refer to 3 replacement fields:

    * ``simulation``: the name of the current simulation
    * ``step``: the current simulation time step
    * ``time``: the current simulation time in seconds

Thus for example you can write ``to "out/{simulation}/foo{step}.jpg"`` to save a series of images called ``foo0.jpg``, ``foo1.jpg``, ``foo2.jpg``, in a new folder for each simulation, all contained in a folder called ``out``.
To avoid having to repeat a prefix like ``out/{simulation}``, you can set the :term:`global parameter` ``recordFolder``, which will be used as the base folder for all ``record`` statements.
For a complete example, see :ref:`sensors`.

If you need to customize the way files are saved (e.g. to specify a specific video codec), you may pass a `Recorder` object to the ``to`` clause instead of a string.


.. _dynamic_statements:

Dynamic Statements
==================

The following statements are valid only in :term:`dynamic behaviors`, :term:`monitors`, and :keyword:`compose` blocks.

.. _take {action}, {...}:
.. _take:

take *action*, ...
------------------
Takes the action(s) specified and pass control to the simulator until the next time step.
Unlike :keyword:`wait`, this statement may not be used in monitors or :term:`modular scenarios`, since these do not take actions.

.. _wait:

wait
----
Take no actions this time step.

.. _wait for {scalar} (seconds | steps):

wait for *scalar* (seconds | steps)
-----------------------------------
Take no actions for a set number of simulation seconds/time steps.

.. _wait until {boolean}:

wait until *boolean*
--------------------
Take no actions until the given condition becomes true.

.. _terminate:

terminate
---------
Immediately end the scenario.
As for :keyword:`terminate when`, if this statement is used in a :term:`modular scenario` which was invoked from another scenario, only the current scenario will end, not the entire simulation.
Inside a :term:`behavior` being run by an agent, the "current scenario" for this purpose is the scenario which created the agent.

.. _terminate simulation:

terminate simulation
--------------------
Immediately end the entire simulation.

.. _do {behavior/scenario}, {...}:
.. _do:

do *behavior/scenario*, ...
-------------------------------
Run one or more sub-behaviors or sub-scenarios in parallel.
This statement does not return until all invoked sub-behaviors/scenarios have completed.

.. _do {behavior/scenario}, {...} until {boolean}:
.. _do-until:

do *behavior/scenario*, ... until *boolean*
-------------------------------------------
As above, except the sub-behaviors/scenarios will terminate when the condition is met.

.. _do {behavior/scenario}, {...} for {scalar} (seconds | steps):

do *behavior/scenario* for *scalar* (seconds | steps)
-----------------------------------------------------
Run sub-behaviors/scenarios for a set number of simulation seconds/time steps.
This statement can return before that time if all the given sub-behaviors/scenarios complete.

.. _do choose {behavior/scenario}, {...}:
.. _do choose:

do choose *behavior/scenario*, ...
----------------------------------
Randomly pick one of the given behaviors/scenarios whose preconditions are satisfied, and run it.
If no choices are available, the simulation is rejected.

This statement also allows the more general form :scenic:`do choose { {behaviorOrScenario}: {weight}, {...} }`, giving weights for each choice (which need not add up to 1).
Among all choices whose preconditions are satisfied, this picks a choice with probability proportional to its weight.

.. _do shuffle {behavior/scenario}, {...}:
.. _do shuffle:

do shuffle *behavior/scenario*, ...
-----------------------------------
Like :keyword:`do choose` above, except that when the chosen sub-behavior/scenario completes, a different one whose preconditions are satisfied is chosen to run next, and this repeats until all the sub-behaviors/scenarios have run once.
If at any point there is no available choice to run (i.e. we have a deadlock), the simulation is rejected.

This statement also allows the more general form :scenic:`do shuffle \{ {behaviorOrScenario}: {weight}, {...} }`, giving weights for each choice (which need not add up to 1).
Each time a new sub-behavior/scenario needs to be selected, this statement finds all choices whose preconditions are satisfied and picks one with probability proportional to its weight.

.. _abort:

abort
-----
Used in an interrupt handler to terminate the current :keyword:`try-interrupt` statement.

.. _override {object} {specifier}, {...}:
.. _override:

override *object* *specifier*, ...
------------------------------------
Override one or more properties of an object, e.g. its :prop:`behavior`, for the duration of the current scenario.
The properties will revert to their previous values when the current scenario terminates.
It is illegal to override :term:`dynamic properties`, since they are set by the simulator each time step and cannot be mutated manually.
