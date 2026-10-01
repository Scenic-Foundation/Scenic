
.. _dynamic scenario semantics:

******************************
Execution of Dynamic Scenarios
******************************

As described in our tutorial on `dynamics`, Scenic scenarios can specify the behavior of agents over time, defining a *policy* which chooses :term:`actions` for each agent at each time step.
Having sampled an initial scene from a Scenic program (see `scene generation`), we can run a dynamic simulation by setting up the scene in a simulator and running the policy in parallel to control the agents.
The API for running dynamic simulations is described in `api` (mainly the `Simulator.simulate` method); this page details how Scenic executes such simulations.

The policy for each agent is given by its :term:`dynamic behavior`, which is a coroutine that usually executes like an ordinary function, but is suspended when it takes an action (using :keyword:`take` or :keyword:`wait`) and resumed after the simulation has advanced by one time step.
As a result, behaviors effectively run in parallel with the simulation.
Behaviors are also suspended when they invoke a sub-behavior using :keyword:`do`, and are not resumed until the sub-behavior terminates.

When a behavior is first invoked, its preconditions are checked, and if any are not satisfied, the simulation is rejected, requiring a new simulation to be sampled. [#f1]_
The behavior's invariants are handled similarly, except that they are also checked whenever the behavior is resumed (i.e. after taking an action and after a sub-behavior terminates).

:term:`Monitors` and :keyword:`compose` blocks of :term:`modular scenarios` execute in the same way as behaviors, with :keyword:`compose` blocks also including additional checks to see if any of their :keyword:`terminate when` conditions have been met or their :term:`temporal requirements` violated.

In detail, a single time step of a dynamic simulation is executed according to the following procedure:

1. Execute all currently-running :term:`modular scenarios` for one time step.
   Specifically, for each such scenario:

	a. Check if any of its :term:`temporal requirements` have already been violated [#f2]_; if so, reject the simulation.

	b. Check if the scenario's time limit (if :keyword:`terminate after` has been used) has been reached; if so, go to step (e) below to stop the scenario.

	c. If the scenario is not currently running a sub-scenario (with :keyword:`do`), check its invariants; if any are violated, reject the simulation. [#f1]_

	d. If the scenario has a :keyword:`compose` block, run it for one time step (i.e. resume it until it or a subscenario it is currently running using :keyword:`do` executes :keyword:`wait`).
	   If the block executes a :keyword:`require` statement with a false condition, reject the simulation.
	   If it executes :keyword:`terminate` or :keyword:`terminate simulation`, or finishes executing, go to step (e) below to stop the scenario.

	e. If the scenario is stopping for one of the reasons above, save the values of any :keyword:`record final` statements in the scenario, recursively stop any sub-scenarios it is running, then revert the effects of any :keyword:`override` statements it executed.
	   Next, check if any of its :term:`temporal requirements` were not satisfied: if so, reject the simulation.
	   Otherwise, the scenario returns to its parent scenario if it was invoked using :keyword:`do`; if it was the top-level scenario, or if it executed :keyword:`terminate simulation`, we set a flag indicating the top-level scenario has terminated.
	   (We do not terminate immediately since we still need to check monitors in the next step.)

2. Save the values of all :keyword:`record` statements in currently-running scenarios, as well as :keyword:`record initial` statements for scenarios which have just started.

3. Run each :term:`monitor` instantiated in the currently-running scenarios for one time step (i.e. resume it until it executes :keyword:`wait`).
   If it executes a :keyword:`require` statement with a false condition, reject the simulation.
   If it executes :keyword:`terminate`, stop the scenario which instantiated it as in step (1e) above.
   If it executes :keyword:`terminate simulation`, set the termination flag (and continue running any other monitors).

4. If the termination flag is set, any of the :keyword:`terminate simulation when` conditions are satisfied, or a time limit passed to `Simulator.simulate` has been reached, go to step (10) to terminate the simulation.

5. Execute the :term:`dynamic behavior` of each agent to select its action(s) for the time step.
   Specifically, for each agent's behavior:

	a. If the behavior is not currently running a sub-behavior (with :keyword:`do`), check its invariants; if any are violated, reject the simulation. [#f1]_

	b. Resume the behavior until it (or a subbehavior it is currently running using :keyword:`do`) executes :keyword:`take` or :keyword:`wait`.
	   If the behavior executes a :keyword:`require` statement with a false condition, reject the simulation.
	   If it executes :keyword:`terminate`, stop the scenario which defined the agent as in step (1e) above.
	   If it executes :keyword:`terminate simulation`, go to step (10) to terminate the simulation.
	   Otherwise, save the (possibly empty) set of actions specified for the agent to take.

6. For each agent, execute the :term:`actions` (if any) its behavior chose in the previous step.

7. Run the simulator for one time step.

8. Increment the simulation clock (the ``currentTime`` attribute of `Simulation`).

9. Update every :term:`dynamic property` of every object to its current value in the simulator.

10. If the simulation is stopping for one of the reasons above, stop any remaining scenarios as in step (1e) above (including checking :term:`temporal requirements` and saving the values of :keyword:`record final` statements).


.. rubric:: Footnotes

.. [#f1] By default, violations of preconditions and invariants cause the simulation to be rejected; however, `Simulator.simulate` has an option to treat them as fatal errors instead.

.. [#f2] More precisely, whether it is impossible for the requirement to be satisfied no matter how the simulation continues.
   For example, given the requirement :scenic:`require always X`, if ``X`` is false in the current time step then the whole simulation will certainly violate the requirement and we can reject.
   On the other hand, given the requirement :scenic:`require eventually X`, the fact that ``X`` is currently false does not mean the requirement will necessarily be violated, since ``X`` could become true later.
   For such requirements Scenic will not reject until the simulation has completed, at which point we can tell with certainty whether or not the requirement was satisfied.
