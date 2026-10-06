..  _coordinates:

Coordinate Systems
==================
Scenic's coordinate system consists of a global coordinate system based on intrinsic Euler angles and a local coordinate system
which can built and used via differnt properties and specifiers. We will describe the coordinate systems in the more detail below.

Global Coordinate System
------------------------
All objects in Scenic have an :prop:`orientation` property, which is their orientation in global coordinates.
Scenic represents orientations internally using quaternions, though for convenience they can be created using Euler angles. Scenic follows the right hand rule with the Z,X,Y order of rotations. In other words, Euler angles are given as (Yaw, Pitch, Roll), in radians, and applied in that order.

:prop:`orientation` is derived from the values of 4 other properties, :prop:`parentOrientation`, :prop:`yaw`, :prop:`pitch`, and :prop:`roll`.
The :prop:`parentOrientation` property defines the parent orientation of the object, which is the orientation with respect to which the intrinsic Euler angles :prop:`yaw`, :prop:`pitch`, and :prop:`roll` are interpreted.
Specifically, :prop:`orientation` is obtained as follows:

  1. start from :prop:`parentOrientation`;
  2. apply a yaw (a :abbr:`CCW (counter-clockwise)` rotation around the positive Z axis) of :prop:`yaw`;
  3. apply a pitch (a CCW rotation around the resulting positive X axis) of :prop:`pitch`;
  4. apply a roll (a CCW rotation around the resulting positive Y axis) of :prop:`roll`.

Below is an illustration of the global coordinate system

.. image:: /images/global_coords.jpg
	:width: 75%

By default, :prop:`parentOrientation` is aligned with the global coordinate system, so that :prop:`yaw` for example is just the angle by which to rotate the object around the Z axis.

This corresponds to the :prop:`heading` property in older versions of Scenic. :prop:`heading` represents yaw in the global XY plane. Scenic represents headings in radians, measured anticlockwise from North, so that a heading of 0 is due North and a heading of π/2 is due West.

For more information on orientations and heading please consult:

    * Tutorial on Orientations :ref:`orientations_tutorial`
    * Reference on Orientations: :ref:`Orientation`.
    * Reference on Heading: :ref:`Heading`

.. note::
    When manually composing rotations in Scenic, remember that if rotation **A** is applied first, followed by rotation **B**, the resulting orientation is computed as **A * B**. This multiplication order is reversed relative to the typical extrinsic rotation convention, reflecting Scenic’s use of intrinsic Euler angles. For further details, see the `Conversion to extrinsic rotations <https://en.wikipedia.org/wiki/Davenport_chained_rotations#Conversion_to_extrinsic_rotations>`_ section of the Wikipedia article on Davenport chained rotations.

Local Coordinate System
-----------------------
When specifying an object's coordinate system relative to other objects, several position specifiers can influence its :prop:`parentOrientation`.

- Most position specifiers—such as the :specifier:`ahead of` specifier and the general operator :scenic:`{X} relative to {Y}`—allow you to optionally override the default :prop:`parentOrientation` at level 3 by appending a clause like :specifier:`with parentOrientation {value}`.

- In contrast, the :specifier:`on {region}` specifier automatically sets :prop:`parentOrientation` (at level 2) whenever the region in question has a preferred orientation. The region's associated vector field defines an orientation at each point, which is then used as the default for the object.

.. note::
    When using tuple syntax (e.g. ``(3, 3, 3)``) to specify positions, be aware that these tuples are interpreted as Vectors, which can sometimes yield unintuitive results. For more details, see the :ref:`specifiers` page.

- Additionally, the `OrientedPoint` class encapsulates a position along with an orientation (and its associated properties, including :prop:`parentOrientation`, :prop:`yaw`, etc.), thereby defining a complete local coordinate system.


For more information on defining a local coordinate system, please consult:

    * Tutorial on :scenic:`relative to`: :ref:`dependencies_and_modifying_specifiers`
    * Reference on :scenic:`relative to` for headings: :ref:`operators`
    * Reference on `OrientedPoint`: :ref:`OrientedPoint`
