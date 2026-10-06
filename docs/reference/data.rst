..  _data:

***********************************
Data Types Reference
***********************************

This page describes the primitive data types built into Scenic.
In addition to these types, Scenic provides a class hierarchy for `points <Point>`, `oriented points <OrientedPoint>`, and `objects <Object>`: see the :ref:`objects_and_classes`.


.. _Boolean:

Boolean
=======

Booleans represent truth values, and can be `True` or `False`.

.. note::

	These are equivalent to the Python `bool` type.


.. _Scalar:

Scalar
======

Scalars represent distances, angles, etc. as floating-point numbers, which can be sampled from various distributions.

.. note::

	These are equivalent to the Python `float` type; however, any context which accepts a scalar will also allow an `int` or a NumPy numeric type such as `numpy.single` (to be precise, any instance of `numbers.Real` is legal).


.. _Vector:

Vector
======

Vectors represent positions and offsets in space.
They are constructed from coordinates using a length-3 list or tuple (:scenic:`[{X}, {Y}, {Z}]` or :scenic:`({X}, {Y}, {Z})`. Alternatively, they can be constructed with the syntax :scenic:`{X} @ {Y}` (inspired by `Smalltalk <http://stephane.ducasse.free.fr/FreeBooks/BlueBook/Bluebook.pdf>`_) or a length-2 list or tuple, with an implied z value of 0.
By convention, coordinates are in meters, although the semantics of Scenic does not depend on this.

For convenience, instances of `Point` can be used in any context where a vector is expected: so for example if ``P`` is a `Point`, then :scenic:`P offset by (1, 2)` is equivalent to :scenic:`P.position offset by (1, 2)`.

.. versionchanged:: 3.0

    Vectors are now 3 dimensional.

.. _Heading:

Heading
=======
Headings represent yaw in the global XY plane.
Scenic represents headings in radians, measured anticlockwise from North, so that a heading of 0 is due North and a heading of π/2 is due West.
We use the convention that the heading of a local coordinate system is the heading of its Y-axis, so that, for example, the vector :scenic:`-2 @ 3` means 2 meters left and 3 ahead.

For convenience, instances of `OrientedPoint` can be used in any context where a heading is expected: so for example if ``OP`` is an `OrientedPoint`, then :scenic:`relative heading of OP` is equivalent to :scenic:`relative heading of OP.heading`.
Since `OrientedPoint` is a subclass of `Point`, expressions involving two oriented points like :scenic:`OP1 relative to OP2` can be ambiguous: the polymorphic operator :scenic:`relative to` accepts both vectors and headings, and either version could be meant here.
Scenic rejects such expressions as being ambiguous: more explicit syntax like :scenic:`OP1.position relative to OP2` must be used instead.

.. _Orientation:

Orientation
===========
Orientations represent rotations in 3D space. Scenic represents orientations internally using quaternions, though for convenience they can be created using Euler angles. Scenic follows the right hand rule with the Z,X,Y order of rotations. In other words, Euler angles are given as (Yaw, Pitch, Roll), in radians, and applied in that order.

For a more detailed explanation of coordinate systems and rotation composition in Scenic, see the :ref:`coordinates` page.

To help visualize an orientation, consider your right hand with fingers extended orthogonally. The index finger points along the positive X axis, the middle finger along the positive Y axis, and the thumb along the positive Z axis. When you align your right thumb with a positive axis, the way your fingers curl indicates a positive rotation.

.. versionadded:: 3.0

.. _Vector Field:
.. _VectorField:

Vector Field
============

Vector fields associate an orientation to each point in space.
For example, a vector field could represent the shortest paths to a destination, or the nominal traffic direction on a road (e.g. :obj:`scenic.domains.driving.model.roadDirection`).

.. versionchanged:: 3.0

    Vector fields now return an `Orientation` instead of a scalar heading.

.. _Region:

Region
======

Regions represent sets of points in space.
Scenic provides a variety of ways to define regions in 2D and 3D space: meshes, rectangles, circular sectors, line segments, polygons, occupancy grids, and explicit lists of points, among others.

Regions can have an associated vector field giving points in the region :term:`preferred orientations`.
For example, a region representing a lane of traffic could have a preferred orientation aligned with the lane, so that we can easily talk about distances along the lane, even if it curves.
Another possible use of preferred orientations is to give the surface of an object normal vectors, so that other objects placed on the surface face outward by default.

The main operations available for use with all regions are:

* the :sampref:`({vector} | {Object}) in {region}` operator to test containment within a region;
* the :sampref:`visible {region}` operator to get the part of a region which is visible from the :scenic:`ego`;
* the :sampref:`in {region}` specifier to choose a position uniformly at random inside a region;
* the :sampref:`on {region}` specifier to choose a position like :sampref:`in {region}` or to project an existing position onto the region's surface.

If you need to perform more complex operations on regions, or are writing a :term:`world model` and need to define your own regions, you will have to work with the :obj:`~scenic.core.regions.Region` class (which regions are instances of) and its subclasses for particular types of regions. These are listed in the :sampref:`Regions Types <region types>` reference. If you are working on Scenic's internals, see the :mod:`scenic.core.regions` module for full details.

.. _Shape:

Shape
=====

Shapes represent the shape of an object, i.e., the volume it occupies modulo translation, rotation, and scaling.
Shapes are represented by meshes, automatically converted to unit size and centered; Scenic considers the side of the shape facing the positive Y axis to be its front.

Shapes can be created from an arbitrary mesh or using one of the geometric primitives below.
For convenience, a shape created with specified dimensions will set the default dimensions for any `Object` created with that shape.
When creating a `MeshShape`, if no dimensions are provided then dimensions will be inferred from the mesh.
`MeshShape` also takes an optional ``initial_rotation`` parameter, which allows directions other than the positive Y axis to be considered the front of the shape.

.. autoclass:: scenic.core.shapes.MeshShape
    :noindex:
    :no-show-inheritance:
    :members: fromFile

.. autoclass:: scenic.core.shapes.BoxShape
    :noindex:
    :no-show-inheritance:

.. autoclass:: scenic.core.shapes.CylinderShape
    :noindex:
    :no-show-inheritance:

.. autoclass:: scenic.core.shapes.ConeShape
    :noindex:
    :no-show-inheritance:

.. autoclass:: scenic.core.shapes.SpheroidShape
    :noindex:
    :no-show-inheritance:

.. _Sensor:

Sensor
======

Sensors are mounted on objects and produce observations during a simulation.
Scenic provides several built-in sensor types.
See the :ref:`Sensors Reference <sensors>` for available types, API details, and usage examples.
