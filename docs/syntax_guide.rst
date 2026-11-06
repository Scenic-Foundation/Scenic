..  _syntax_guide:

Syntax Guide
============

This page summarizes the syntax of Scenic, excluding the basic syntax of variable assignments, functions, loops, etc., which is identical to Python (see the `Python Tutorial <https://docs.python.org/3/tutorial/>`_ for an introduction).
For more details, click the links for individual language constructs to go to the corresponding section of the `language reference`.


Primitive Data Types
--------------------
============================= ==================================================================
`Booleans <Boolean>`          expressing truth values
`Scalars <Scalar>`            representing distances, angles, etc. as floating-point numbers
`Vectors <Vector>`            representing positions and offsets in space
`Headings <Heading>`   		    representing 2D orientations in the XY plane
`Orientations <Orientation>`  representing 3D orientations in space
`Vector Fields <VectorField>` associating an orientation to each point in space
`Regions <Region>`            representing sets of points in space
`Shapes <Shape>`              representing shapes (regions modulo similarity)
`Sensors <Sensor>`            representing sensors mounted on objects
============================= ==================================================================


Distributions
-------------
================================================================ ==================================
:sampref:`Range({low}, {high})`                                  uniformly-distributed real number in the interval
:sampref:`DiscreteRange({low}, {high})`                          uniformly-distributed integer in the (fixed) interval
:sampref:`Normal({mean}, {stdDev})`                              normal distribution with the given mean and standard deviation
:sampref:`TruncatedNormal({mean}, {stdDev}, {low}, {high})`      normal distribution truncated to the given window
:sampref:`Uniform({value}, {...})`                               uniform over a finite set of values
:sampref:`Discrete(\{{value}: {weight}, {...}\})<DiscreteDistr>` discrete with given values and weights
:sampref:`new Point in {region} <uniform_in_region>`                 uniformly-distributed `Point` in a region
================================================================ ==================================

Statements
----------

Compound Statements
+++++++++++++++++++

.. list-table::
   :header-rows: 1

   * - Syntax
     - Meaning
   * - :sampref:`class {name}[({superclass})]: <classDef>`
     - Defines a Scenic class.
   * - :sampref:`behavior {name}({arguments}): <behaviorDef>`
     - Defines a :term:`dynamic behavior`.
   * - :sampref:`monitor {name}({arguments}): <monitorDef>`
     - Defines a :term:`monitor`.
   * - :sampref:`scenario {name}({arguments}): <modularScenarioDef>`
     - Defines a :term:`modular scenario`.
   * - :sampref:`try: {...} interrupt when {boolean}:<tryInterruptStmt>`
     - Run code with interrupts inside a dynamic behavior or modular scenario.

Simple Statements
+++++++++++++++++

.. list-table::
   :header-rows: 1

   * - Syntax
     - Meaning
   * - :sampref:`model {name}`
     - Select the :term:`world model`.
   * - :sampref:`import {module}`
     - Import a Scenic or Python module.
   * - :sampref:`param {name} = {value}, {...}`
     - Define :term:`global parameters` of the scenario.
   * - :sampref:`require {boolean}`
     - Define a hard requirement.
   * - :sampref:`require[{number}] {boolean}`
     - Define a soft requirement.
   * - :sampref:`require {LTL formula}`
     - Define a dynamic hard requirement.
   * - :sampref:`require monitor {monitor}`
     - Define a dynamic requirement using a monitor.
   * - :sampref:`terminate when {boolean}`
     - Define a termination condition.
   * - :sampref:`terminate after {scalar} (seconds | steps)`
     - Set the scenario to terminate after a given amount of time.
   * - :sampref:`mutate {identifier}, {...} [by {number}]`
     - Enable mutation of the given list of objects.
   * - :sampref:`record [initial | final] {value} {...}`
     - Save initial, final, or time series data from simulations.

Dynamic Statements
++++++++++++++++++

These statements can only be used inside a :term:`dynamic behavior`, :term:`monitor`, or :keyword:`compose` block of a :term:`modular scenario`.

.. list-table::
   :header-rows: 1

   * - Syntax
     - Meaning
   * - :sampref:`take {action}, {...}`
     - Take the action(s) specified.
   * - :sampref:`wait`
     - Take no actions this time step.
   * - :sampref:`wait until {boolean}`
     - Take no actions until a condition is met.
   * - :sampref:`wait for {scalar} (seconds | steps)`
     - Take no actions for a specified period of time.
   * - :sampref:`terminate`
     - Immediately end the scenario.
   * - :sampref:`terminate simulation`
     - Immediately end the entire simulation.
   * - :sampref:`do {behavior/scenario}, {...}`
     - Run one or more sub-behaviors/sub-scenarios until they complete.
   * - :sampref:`do {behavior/scenario}, {...} until {boolean}`
     - Run sub-behaviors/scenarios until they complete or a condition is met.
   * - :sampref:`do {behavior/scenario}, {...} for {scalar} (seconds | steps)`
     - Run sub-behaviors/scenarios for (at most) a specified period of time.
   * - :sampref:`do choose {behavior/scenario}, {...}`
     - Run *one* choice of sub-behavior/scenario whose preconditions are satisfied.
   * - :sampref:`do shuffle {behavior/scenario}, {...}`
     - Run several sub-behaviors/scenarios in a random order, satisfying preconditions.
   * - :sampref:`abort`
     - Break out of the current :keyword:`try-interrupt` statement.
   * - :sampref:`override {object} {specifier}, {...}`
     - Override properties of an object for the duration of the current scenario.

Objects
-------

The syntax :sampref:`new {class} {specifier}, {...} <objectCreate>` creates an instance of a Scenic class.

The Scenic class `Point` provides the basic position properties in the first table below; its subclass `OrientedPoint` adds the orientation properties in the second table.
Finally, the class `Object`, which represents physical objects and is the default superclass of user-defined Scenic classes, adds the properties in the third table.
See the :ref:`objects_and_classes` for details.

=======================  ==============  =============================================================================
   **Property**           **Default**                    **Meaning**
-----------------------  --------------  -----------------------------------------------------------------------------
 position [1]_           (0, 0, 0)       position in global coordinates
 visibleDistance         50              distance for the ‘can see’ operator
 viewRayDensity          5               determines ray count (if ray count is not provided)
 viewRayDistanceScaling  False           whether to scale number of rays with distance (if ray count is not provided)
 viewRayCount            None            tuple of number of rays to send in each dimension.
 mutationScale           0               overall scale of :ref:`mutations <mutate>`
 positionStdDev          (1,1,0)         mutation standard deviation for :prop:`position`
=======================  ==============  =============================================================================

Properties added by `OrientedPoint`:

===================  ==============  ================================================
   **Property**       **Default**                    **Meaning**
-------------------  --------------  ------------------------------------------------
 yaw [1]_             0              yaw in local coordinates
 pitch [1]_           0              pitch in local coordinates
 roll [1]_            0              roll in local coordinates
 parentOrientation    global         basis for local coordinate system
 viewAngles           (2π, π)        angles for visibility calculations
 orientationStdDev    (5°, 0, 0)     mutation standard deviation for :prop:`orientation`
===================  ==============  ================================================

Properties added by `Object`:

======================== ======================= ================================================
   **Property**           **Default**                       **Meaning**
------------------------ ----------------------- ------------------------------------------------
 width                   1                        width of bounding box (X axis)
 length                  1                        length of bounding box (Y axis)
 height                  1                        height of bounding box (Z axis)
 shape                   `BoxShape`               shape of the object
 allowCollisions         `False`                  whether collisions are allowed
 regionContainedIn       `workspace`              `Region` the object must lie within
 baseOffset              (0, 0, -self.height/2)   offset determining the base of the object
 contactTolerance        1e-4                     max distance to be considered on a surface
 sideComponentThresholds (-0.5, 0.5) per side     thresholds to determine side surfaces
 cameraOffset            (0, 0, 0)                position of camera for :keyword:`can see`
 visionSensorOffset      (0, self.length/2, 0)    offset of default vision sensor mount point
 requireVisible          `False`                  whether object must be visible from ego
 occluding               `True`                   whether object occludes visibility
 showVisibleRegion       `False`                  whether to display the visible region
 color                   None                     color of object
 velocity [1]_           from :prop:`speed`       initial (instantaneous) velocity
 speed [1]_              0                        initial (later, instantaneous) speed
 angularVelocity [1]_    (0, 0, 0)                initial (instantaneous) angular velocity
 angularSpeed [1]_       0                        angular speed (change in :prop:`heading`/time)
 behavior                `None`                   :term:`dynamic behavior`, if any
 lastActions             `None`                   tuple of actions taken in last timestamp
 sensors                 {}                       dict of :ref:`sensors <sensors>` the object has
======================== ======================= ================================================

.. [1] These are :term:`dynamic properties`, updated automatically every time step during
    dynamic simulations.

Specifiers
----------

The :sampref:`with {property} {value}` specifier can specify any property, including new properties not built into Scenic.
Additional specifiers for the :prop:`position` and :prop:`orientation` properties are listed below.

.. figure:: images/Specifier_Figure.png
  :width: 60%
  :figclass: align-center
  :alt: Diagram illustrating several specifiers.

  Illustration of the :specifier:`beyond`, :specifier:`behind`, and :specifier:`offset by` specifiers.
  Each :scenic:`OrientedPoint` (e.g. ``P``) is shown as a bold arrow.

.. list-table::
   :header-rows: 1

   * - Specifier for :prop:`position`
     - Meaning
   * - :sampref:`at {vector}`
     - Positions the object at the given global coordinates
   * - :sampref:`in {region}`
     - Positions the object uniformly at random in the given Region
   * - :sampref:`contained in {region}`
     - Positions the object uniformly at random entirely contained in the given Region
   * - :sampref:`on {vector}`
     - Positions the base of the object at the given global coordinates
   * - :sampref:`on ({region} | {Object})`
     - Positions the object uniformly at random or modifies the position so that base of the Object is in the given Region/on the given Object.
   * - :sampref:`offset by {vector}`
     - Positions the object at the given coordinates in the local coordinate system of ego (which must already be defined)
   * - :sampref:`offset along {direction} by {vector}`
     - Positions the object at the given coordinates, in a local coordinate system centered at ego and oriented along the given direction
   * - :sampref:`beyond {vector} by ({vector} | {scalar}) [from ({vector} | {OrientedPoint})]`
     - Positions the object with respect to the line of sight from a point or the ego
   * - :sampref:`visible [from ({Point} | {OrientedPoint})]`
     - Ensures the object is visible from the ego, or from the given Point/OrientedPoint if given, while optionally specifying position to be uniformly random over all positions that result in a visible object.
   * - :sampref:`not visible [from ({Point} | {OrientedPoint})]`
     - Ensures the object is not visible from the ego, or from the given Point/OrientedPoint if given, while optionally specifying position to be uniformly random over all positions that result in a non-visible object.
   * - :sampref:`(left | right) of ({vector} | {OrientedPoint} | {Object}) [by {scalar}] <left of>`
     - Positions the object to the left/right by the given scalar distance.
   * - :sampref:`(ahead of | behind) ({vector} | {OrientedPoint} | {Object}) [by {scalar}] <ahead of>`
     - Positions the object to the front/back by the given scalar distance
   * - :sampref:`(above | below) ({vector} | {OrientedPoint} | {Object}) [by {scalar}] <above>`
     - Positions the object above/below by the given scalar distance
   * - :sampref:`following {vectorField} [from {vector}] for {scalar}`
     - Position by following the given vector field for the given distance starting from ego or the given vector


.. list-table::
   :header-rows: 1

   * - Specifier for :prop:`orientation`
     - Meaning
   * - :sampref:`facing {orientation}`
     - Orients the object along the given orientation in global coordinates
   * - :sampref:`facing {vectorField}`
     - Orients the object along the given vector field at the object’s position
   * - :sampref:`facing (toward | away from) {vector}`
     - Orients the object toward/away from the given position (thereby depending on the object’s position)
   * - :sampref:`facing directly (toward | away from) {vector}`
     - Orients the object *directly* toward/away from the given position (thereby depending on the object’s position)
   * - :sampref:`apparently facing {heading} [from {vector}]`
     - Orients the object so that it has the given heading with respect to the line of sight from ego (or the given vector)


Operators
---------

In the following tables, operators are grouped by the type of value they return.

.. figure:: images/Operator_Figure.png
  :width: 70%
  :figclass: align-center
  :alt: Diagram illustrating several operators.

  Illustration of several operators.
  Each :scenic:`OrientedPoint` (e.g. ``P``) is shown as a bold arrow.

.. list-table::
   :header-rows: 1

   * - Scalar Operators
     - Meaning
   * - :sampref:`relative heading of {heading} [from {heading}]`
     - The relative heading of the given heading with respect to ego (or the ``from`` heading)
   * - :sampref:`apparent heading of {OrientedPoint} [from {vector}]`
     -  The apparent heading of the `OrientedPoint`, with respect to the line of sight from ego (or the given vector)
   * - :sampref:`distance [from {vector}] to {vector}`
     - The distance to the given position from ego (or the ``from`` vector)
   * - :sampref:`minimum distance [from {Object}] to {Object}`
     - The minimum distance to the given object from ego (or the ``from`` object)
   * - :sampref:`angle [from {vector}] to {vector}`
     - The heading (azimuth) to the given position from ego (or the ``from`` vector)
   * - :sampref:`altitude [from {vector}] to {vector}`
     - The altitude to the given position from ego (or the ``from`` vector)

.. list-table::
   :header-rows: 1

   * - Boolean Operators
     - Meaning
   * - :sampref:`({Point} | {OrientedPoint}) can see ({vector} | {Object})`
     - Whether or not a position or `Object` is visible from a `Point` or `OrientedPoint`
   * - :sampref:`({vector} | {Object}) in {region}`
     - Whether a position or `Object` lies in the region
   * - :sampref:`({Object} | {region}) intersects ({Object} | {region})`
     - Whether an `Object`/`Region` intersects an `Object`/`Region`.


.. list-table::
   :header-rows: 1

   * - Orientation Operators
     - Meaning
   * - :sampref:`{scalar} deg`
     - The given angle, interpreted as being in degrees
   * - :sampref:`{vectorField} at {vector}`
     - The orientation specified by the vector field at the given position
   * - :sampref:`{direction} relative to {direction}`
     - The first direction (a heading, orientation, or vector field), interpreted as an offset relative to the second direction


.. list-table::
   :header-rows: 1

   * - Vector Operators
     - Meaning
   * - :sampref:`{vector} (relative to | offset by) {vector}`
     - The first vector, interpreted as an offset relative to the second vector (or vice versa)
   * - :sampref:`{vector} offset along {direction} by {vector}`
     - The second vector, interpreted in a local coordinate system centered at the first vector and oriented along the given direction


.. list-table::
   :header-rows: 1

   * - Region Operators
     - Meaning
   * - :sampref:`visible {region}`
     - The part of the given region visible from ego
   * - :sampref:`not visible {region}`
     - The part of the given region not visible from ego
   * - :sampref:`{region} visible from ({Point} | {OrientedPoint})`
     - The part of the given region visible from the given `Point` or `OrientedPoint`.
   * - :sampref:`{region} not visible from ({Point} | {OrientedPoint})`
     - The part of the given region not visible from the given `Point` or `OrientedPoint`.

.. list-table::
   :header-rows: 1

   * - OrientedPoint Operators
     - Meaning
   * - :sampref:`{vector} relative to {OrientedPoint}`
     - The given vector, interpreted in the local coordinate system of the OrientedPoint
   * - :sampref:`{OrientedPoint} offset by {vector}`
     - Equivalent to :scenic:`vector relative to OrientedPoint` above
   * - :sampref:`(front | back | left | right) of {Object}`
     - The midpoint of the corresponding side of the bounding box of the Object, inheriting the Object's orientation.
   * - :sampref:`(front | back) (left | right) of {Object}`
     - The midpoint of the corresponding edge of the bounding box of the Object, inheriting the Object's orientation.
   * - :sampref:`(front | back) (left | right) of {Object}`
     - The midpoint of the corresponding edge of the bounding box of the Object, inheriting the Object's orientation.
   * - :sampref:`(top | bottom) (front | back) (left | right) of {Object}`
     - The corresponding corner of the bounding box of the Object, inheriting the Object's orientation.

.. list-table::
   :header-rows: 1

   * - Temporal Operators
     - Meaning
   * - :sampref:`always {condition}`
     - Require the condition to hold at every time step.
   * - :sampref:`eventually {condition}`
     - Require the condition to hold at some time step.
   * - :sampref:`next {condition}`
     - Require the condition to hold in the next time step.
   * - :sampref:`{condition} until {condition}`
     - Require the first condition to hold until the second becomes true.
   * - :sampref:`{condition} implies {condition}`
     - Require the second condition to hold if the first condition holds.

Built-in Functions
------------------

.. list-table::
   :header-rows: 1

   * - Function
     - Description
   * - :ref:`Misc Python functions <gen_lifted_funcs>`
     - Various Python functions including :scenic:`min`, :scenic:`max`, :scenic:`open`, etc.
   * - :ref:`filter_func`
     - Filter a possibly-random list (allowing limited randomized control flow).
   * - :ref:`resample_func`
     - Sample a new value from a distribution.
   * - :ref:`localPath_func`
     - Convert a relative path to an absolute path, based on the current directory.
   * - :ref:`verbosePrint_func`
     - Like `print`, but silent at low-enough verbosity levels.
   * - :ref:`simulation_func`
     - Get the the current simulation object.
