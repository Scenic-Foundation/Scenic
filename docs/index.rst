Welcome to Scenic's documentation!
==================================

Scenic is a domain-specific probabilistic programming language for modeling the environments of cyber-physical systems like robots and autonomous cars.
A Scenic program defines a distribution over *scenes*, configurations of physical objects and agents; sampling from this distribution yields concrete scenes which can be simulated to produce training or testing data.
Scenic can also define (probabilistic) policies for dynamic agents, allowing modeling scenarios where agents take actions over time in response to the state of the world.

Scenic was designed and implemented by Daniel J. Fremont, Eric Vin, Edward Kim, Tommaso Dreossi, Shromona Ghosh, Xiangyu Yue, Alberto L. Sangiovanni-Vincentelli, and Sanjit A. Seshia, with contributions from :doc:`many others <credits>`.
For a description of the language and some of its applications, see `our journal paper <https://doi.org/10.1007/s10994-021-06120-5>`_ on Scenic 2, which extends `our PLDI 2019 paper <https://arxiv.org/abs/1809.09310>`_ on Scenic 1; the new features in Scenic 3 are described in `our CAV 2023 paper <https://arxiv.org/abs/2307.03325>`_.
Our :doc:`publications <publications>` page lists additional papers using Scenic.

.. note::

   The syntax of Scenic 3 is not completely backwards-compatible with earlier versions of Scenic, which were used in our papers prior to 2023.
   See :doc:`new` for a list of syntax changes and new features.
   Old code can likely be easily ported; you can also install older releases if necessary from
   `GitHub <https://github.com/Scenic-Foundation/Scenic/releases>`__.

If you have any problems using Scenic, please submit an issue to `our GitHub repository <https://github.com/Scenic-Foundation/Scenic>`_ or ask a question on `our community forum <https://forum.scenic-lang.org/>`_.

Table of Contents
=================

.. toctree::
   :maxdepth: 1
   :caption: Introduction

   quickstart
   install_notes
   new

.. toctree::
   :maxdepth: 1
   :caption: Tutorials

   tutorials/fundamentals
   tutorials/dynamics
   tutorials/composition

.. toctree::
   :maxdepth: 1
   :caption: Language and Tool Reference

   syntax_guide
   language_reference
   options
   api
   developing
   internals

.. toctree::
   :maxdepth: 1
   :caption: Libraries and Simulators

   libraries
   simulators
   new_simulator

.. toctree::
   :maxdepth: 1
   :caption: General Information

   roadmap
   governance
   publications
   credits

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :doc:`glossary`

License
=======

Scenic is distributed under the `3-Clause BSD License <https://opensource.org/licenses/BSD-3-Clause>`_.
