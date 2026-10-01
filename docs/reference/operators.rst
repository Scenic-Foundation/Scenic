..  _operators:

*******************
Operators Reference
*******************

.. figure:: ../images/Operator_Figure.png
  :width: 70%
  :figclass: align-center
  :alt: Diagram illustrating several operators.

  Illustration of several operators.
  Each :scenic:`OrientedPoint` (e.g. ``P``) is shown as a bold arrow.


Scalar Operators
=================

.. _relative heading of {heading} [from {heading}]:

relative heading of *heading* [from *heading*]
----------------------------------------------
The relative heading of the given heading with respect to ego (or the heading provided with the optional from heading)

.. _apparent heading of {OrientedPoint} [from {vector}]:

apparent heading of *OrientedPoint* [from *vector*]
---------------------------------------------------
The apparent heading of the OrientedPoint, with respect to the line of sight from ego (or the position provided with the optional from vector)

.. _apparent heading to {vector} [from {OrientedPoint}]:

apparent heading to *vector* [from *OrientedPoint*]
---------------------------------------------------
The apparent heading to the vector, with respect to the line of sight from ego (or the OrientedPoint provided with the optional from OrientedPoint)

.. _distance [from {vector}] to {vector}:
.. _distance from:

distance [from *vector*] to *vector*
-------------------------------------
The distance to the given position from ego (or the position provided with the optional from vector).

.. note::
	When this operator is passed objects, it treats them as vectors and considers only their positions. If you want to compute the actual distance between the occupied space of two objects, you should use the :ref:`minimum distance from` operator.


.. _minimum distance [from {Object}] to {Object}:
.. _minimum distance from:

minimum distance [from *Object*] to *Object*
--------------------------------------------
The minimum distance to the given Object from ego (or the Object provided with the optional :scenic:`from {Object}`). Unlike :ref:`distance from`, which computes the distance between the :prop:`position` of the objects, this operator takes into account the objects' :prop:`shape` and dimensions.

.. versionadded:: unreleased


.. _angle [from {vector}] to {vector}:

angle [from *vector* ] to *vector*
----------------------------------
The heading (azimuth) to the given position from ego (or the position provided with the optional from vector). For example, if angle to taxi is zero, then taxi is due North of ego

.. _altitude [from {vector}] to {vector}:

altitude [from *vector* ] to *vector*
-------------------------------------
The altitude to the given position from ego (or the position provided with the optional from vector ). For example, if altitude to plane is π, then plane is directly above ego.



Boolean Operators
==================

.. _({Point} | {OrientedPoint}) can see ({vector} | {Object}):
.. _can see:

(*Point* | *OrientedPoint*) can see (*vector* | *Object*)
---------------------------------------------------------
Whether or not a position or `Object` is visible from a `Point` or `OrientedPoint`, accounting for occlusion.

See the :ref:`Visibility System <visibility>` reference for a discussion of the visibility model.

.. _({vector} | {Object}) in {region}:

(*vector* | *Object*) in *region*
----------------------------------
Whether a position or `Object` lies in the `Region`; for the latter, the object must be completely contained in the region.

.. _({Object} | {region}) intersects ({Object} | {region}):

(*Object* | *region*) intersects (*Object* | *region*)
------------------------------------------------------
Whether an `Object`/`Region` intersects another `Object`/`Region`, i.e. whether any portion of the occupied spaces intersect.

When working with 2D regions, it can be useful to check intersection with the :term:`footprint` of a region, e.g. when checking whether a car intersects a given lane. In this case, one would write :scenic:`car intersects lane.footprint` instead of :scenic:`car intersects lane`. For more details, see :term:`footprint`.

.. _{vector} (ahead of | behind | left of | right of) {region}:

*vector* (ahead of | behind | left of | right of) *OrientedPoint*
-----------------------------------------------------------------
Whether a vector is to a respective side of an `OrientedPoint` (i.e. within +- ~90 degrees from that direction), accounting for the heading of the `OrientedPoint`. These operators are convenient shorthand for comparing :sampref:`apparent heading to {vector} [from {OrientedPoint}]` to a range of values.

Note: For vectors very close to a boundary point (i.e. an apparent heading to the vector in (89.99, 90.01) or (-89.99, -90.01) for "ahead of" and "behind"), both operators will resolve to False.

Example: If an `OrientedPoint` had an apparent heading to a vector of 45 degrees, it would be both "ahead of" and "left of" the `OrientedPoint` but not "behind" or "right of".

Orientation Operators
=====================

.. _{scalar} deg:

*scalar* deg
------------
The given angle, interpreted as being in degrees. For example 90 deg evaluates to π/2

.. _{vectorField} at {vector}:

*vectorField* at *vector*
-------------------------
The orientation specified by the vector field at the given position

.. _{direction} relative to {direction}:

(*direction*) relative to (*direction*)
-------------------------------------------------------------------
The orientation obtained by starting in the second direction and then rotating according to the first direction. For example, :scenic:`-5 deg relative to 90 deg` is simply 85 degrees. If either direction is a vector field, then this operator yields an expression depending on the :prop:`position` property of the object being specified. Both operator values must be of type `heading`, `Orientation`, or `vectorField`, not tuples, as tuples are by default intepreted as `Vector` objects.

.. note::
	This operator is not necessarily commutative, for example, when composing two 3D orientations.


Vector Operators
================

.. _{vector} (relative to | offset by) {vector}:

*vector* (relative to | offset by) *vector*
--------------------------------------------
The first vector, interpreted as an offset relative to the second vector (or vice versa).
For example, :scenic:`(5, 5, 5) relative to (100, 200, 300)` is :scenic:`(105, 205, 305)`.
Note that this polymorphic operator has a specialized version for instances of `OrientedPoint`, defined :ref:`below <{vector} relative to {OrientedPoint}>`: so for example :scenic:`(-3, 0, 0) relative to taxi` will not use the version of this operator for vectors (even though the `Object` taxi can be coerced to a vector).

.. _{vector} offset along {direction} by {vector}:

*vector* offset along *direction* by *vector*
----------------------------------------------
The second vector, interpreted in a local coordinate system centered at the first vector and oriented along the given direction (which, if a vector field, is evaluated at the first vector to obtain an orientation)

Region Operators
================

.. _visible {region}:

visible *region*
----------------
The part of the given region which is visible from the ego object (i.e. the intersection of the given region with the :term:`visible region` of the ego).

.. _not visible {region}:

not visible *region*
--------------------
The part of the given region which is *not* visible from the ego object (as above, based on the ego's :term:`visible region`).

.. _{region} visible from ({Point} | {OrientedPoint}):

*region* visible from (*Point* | *OrientedPoint*)
-------------------------------------------------
The part of the given region visible from the given `Point` or `OrientedPoint` (like :scenic:`visible {region}` but from an arbitrary `Point`/`OrientedPoint`).

.. _{region} not visible from ({Point} | {OrientedPoint}):

*region* not visible from (*Point* | *OrientedPoint*)
------------------------------------------------------
The part of the given region not visible from the given `Point` or `OrientedPoint` (like :scenic:`not visible {region}` but from an arbitrary `Point`/`OrientedPoint`).

OrientedPoint Operators
=======================

.. _{vector} relative to {OrientedPoint}:

*vector* relative to *OrientedPoint*
-------------------------------------
The given vector, interpreted in the local coordinate system of the OrientedPoint. So for example :scenic:`(1, 2, 0) relative to ego` is 1 meter to the right and 2 meters ahead of ego.

.. _{OrientedPoint} offset by {vector}:

*OrientedPoint* offset by *vector*
----------------------------------
Equivalent to :scenic:`{vector} relative to {OrientedPoint}` above

.. _(front | back | left | right) of {Object}:

(front | back | left | right | top | bottom) of *Object*
--------------------------------------------------------
The midpoint of the corresponding side of the bounding box of the `Object`, inheriting the Object's orientation.

.. _(front | back) (left | right) of {Object}:

(front | back) (left | right) of *Object*
-----------------------------------------
The midpoint of the corresponding edge of the Object’s bounding box, inheriting the Object's orientation.


.. _(top | bottom) (front | back) (left | right) of {Object}:

(top | bottom) (front | back) (left | right) of *Object*
--------------------------------------------------------
The corresponding corner of the Object’s bounding box, inheriting the Object's orientation.

.. _temporal operators:

Temporal Operators
=======================

Temporal operators can be used inside :keyword:`require` statements to constrain how a dynamic scenario evolves over time.
The semantics of these operators are taken from Linear Temporal Logic (specifically, we use RV-LTL [B10]_ to properly model the finite length of Scenic simulations).

.. _always {condition}:
.. _always:

always *condition*
------------------
Require the given condition to hold throughout the execution of the dynamic scenario.

.. _eventually {condition}:
.. _eventually:

eventually *condition*
----------------------
Require the given condition to hold at some point during the execution of the dynamic scenario.

.. _next {condition}:
.. _next:

next *condition*
----------------
Require the given condition to hold at the next time step of the dynamic scenario.

For example, while :scenic:`require X` requires that ``X`` hold at time step 0 (the start of the simulation), :scenic:`require next X` requires that ``X`` hold at time step 1.
The requirement :scenic:`require always (X implies next X)` says that for every time step :math:`N`, if ``X`` is true at that time step then it is also true at step :math:`N+1`; equivalently, if ``X`` ever becomes true, it must remain true for the rest of the simulation.

.. _{condition} until {condition}:
.. _until:

*condition* until *condition*
-----------------------------
Require the second condition to hold at some point, and the first condition to hold at every time step before then (after which it is unconstrained).

Note that this is the so-called *strong until*, since it requires the second condition to eventually become true.
For the *weak until*, which allows the second condition to never hold (in which case the first condition must *always* hold), you can write :scenic:`require ({X} until {Y}) or (always {X} and not {Y})`.

.. _{condition} implies {condition}:
.. _implies:

*hypothesis* implies *conclusion*
---------------------------------
Require the conclusion to hold if the hypothesis holds.

This is syntactic sugar for :scenic:`not {hypothesis} or {conclusion}`.
It is mainly useful in making requirements that constrain multiple time steps easier to read: for example, :scenic:`require always X implies Y` requires that at every time step when ``X`` holds, ``Y`` must also hold.

.. rubric:: References

.. [B10] Bauer et al., :title:`Comparing LTL Semantics for Runtime Verification`. Journal of Logic and Computation, 2010. `[Online] <https://doi.org/10.1093/logcom/exn075>`_
