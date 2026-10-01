..  _functions:

****************************
Built-in Functions Reference
****************************

These functions are built into Scenic and may be used without needing to import any modules.

.. _gen_lifted_funcs:

Miscellaneous Python Functions
------------------------------

The following functions work in the same way as their Python counterparts except that they accept random values:

* :obj:`~math.sin`, :obj:`~math.cos`, :obj:`~math.tan`, :obj:`~math.hypot` (from the Python `math` module)
* `len`, `max`, `min`, `round`
* `float`, `int`, `str`

The other Python built-in functions (e.g. `enumerate`, `range`, `open`) are available but do not accept random arguments.

.. note::

	If in the definition of a scene you would like to pass random values into some other function from the Python standard library (or any other Python package), you will need to wrap the function with the `distributionFunction` decorator. This is not necessary when calling external functions inside requirements or dynamic behaviors.

.. _filter_func:

filter
------

The `filter` function works as in Python except it is now able to operate over random lists.
This feature can be used to work around Scenic's lack of support for randomized control flow in certain cases.
In particular, Scenic does not allow iterating over a random list, but it is still possible to select a random element satisfying a desired criterion using `filter`::

	mylist = Uniform([-1, 1, 2], [-3, 4])    # pick one of these lists 50/50
	filtered = filter(lambda e: e > 0, y)    # extract only the positive elements
	x = Uniform(*filtered)                   # pick one of them at random

In the last line, we use Python's `unpacking operator * <https://docs.python.org/3.6/reference/expressions.html#expression-lists>`_ to use the elements of the chosen list which pass the filter as arguments to :ref:`Uniform <Uniform({value}, {...})>`; thus ``x`` is sampled as a uniformly-random choice among such elements. [#f1]_

For an example of this idiom in a realistic scenario, see :file:`examples/driving/OAS_scenarios/oas_scenario_28.scenic`.

.. _resample_func:
.. _resample:

resample
--------
The `resample` function takes a distribution and samples a new value from it, conditioned on the values of its parameters, if any.
This is useful in cases where you have a complicated distribution that you want multiple samples from.

For example, in the program

.. code-block:: scenic

	x = Uniform(0, 5)
	y = Range(x, x+1)
	z = resample(y)

with probability 1/2 both ``y`` and ``z`` are independent uniform samples from the interval :math:`(0, 1)`, and with probability 1/2 they are independent uniform samples from :math:`(5, 6)`.
It is never the case that :math:`y \in (0, 1)` and :math:`z \in (5, 6)` or vice versa, which would require inconsistent assignments to ``x``.

.. note::

	This function can only be applied to the basic built-in distributions (see the :ref:`distributions`).
	Resampling a more complex expression like :scenic:`x + y` where ``x`` and ``y`` are distributions would be ambiguous (what if ``x`` and ``y`` are used elsewhere?) and so is not allowed.

.. _localPath_func:

localPath
---------
The `localPath` function takes a relative path with respect to the directory containing the ``.scenic`` file where it is used, and converts it to an absolute path. Note that the path is returned as a `pathlib.Path` object.

.. versionchanged:: 3.0

    This function now returns a `pathlib.Path` object instead of a string.

.. _verbosePrint_func:

verbosePrint
------------
The `verbosePrint` function operates like `print` except that it you can specify at what verbosity level (see :option:`--verbosity`) it should actually print.
If no level is specified, it prints at all levels except verbosity 0.

Scenic libraries intended for general use should use this function instead of `print` so that all non-error messages from Scenic can be silenced by setting verbosity 0.

.. _simulation_func:

simulation
----------
The `simulation` function, available for use in dynamic behaviors and scenarios, returns the currently-running `Simulation`.
This allows access to global information about the simulation, e.g. :scenic:`simulation().currentTime` to find the current time step; however, it is provided primarily so that scenarios written for a specific simulator may use simulator-specific functionality (by calling custom methods provided by that simulator's subclass of `Simulation`).

.. [#f1] If there are no such elements, i.e., the filtered list is empty, then Scenic will reject the scenario and try sampling again.
