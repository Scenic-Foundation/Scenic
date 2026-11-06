[<img src="https://docs.scenic-lang.org/en/latest/_static/logo-full.svg" alt="Scenic Logo" height="100">](https://scenic-lang.org/)

[![Documentation Status](https://readthedocs.org/projects/scenic-lang/badge/?version=latest)](https://docs.scenic-lang.org/en/latest/?badge=latest)
[![Tests Status](https://github.com/Scenic-Foundation/Scenic/actions/workflows/run-tests.yml/badge.svg)](https://github.com/Scenic-Foundation/Scenic/actions/workflows/run-tests.yml)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

A compiler and scenario generator for Scenic, a domain-specific probabilistic programming language for modeling the environments of cyber-physical systems.
Please see the [documentation](https://docs.scenic-lang.org/) for installation instructions, as well as tutorials and other information about the Scenic language, its implementation, and its interfaces to various simulators.

For an overview of the language and some of its applications, see our [2022 journal paper](https://link.springer.com/article/10.1007/s10994-021-06120-5) on Scenic 2, which extends our [PLDI 2019 paper](https://arxiv.org/abs/1809.09310) on Scenic 1.
The new syntax and features of Scenic 3 are described in our [CAV 2023 paper](https://arxiv.org/abs/2307.03325).
Our [Publications](https://docs.scenic-lang.org/en/latest/publications.html) page lists additional relevant publications.

Scenic was initially designed and implemented at UC Berkeley by Daniel J. Fremont, Tommaso Dreossi, Shromona Ghosh, Xiangyu Yue, Alberto L. Sangiovanni-Vincentelli, and Sanjit A. Seshia.
Subsequent work has been done primarily at UC Berkeley and UC Santa Cruz: in particular, Edward Kim made major contributions to Scenic 2, and Eric Vin, Shun Kashiwa, Matthew Rhea, and Ellen Kalvan to Scenic 3.
Please see our [Credits](https://docs.scenic-lang.org/en/latest/credits.html) page for details and more contributors.

If you have any problems using Scenic, please submit an issue to [our GitHub repository](https://github.com/Scenic-Foundation/Scenic) or start a conversation on our [community forum](https://forum.scenic-lang.org/).

The repository is organized as follows:

* the _src/scenic_ directory contains the package proper;
* the _examples_ directory has many examples of Scenic programs;
* the _assets_ directory contains meshes and other resources used by the examples and tests;
* the _docs_ directory contains the sources for the documentation;
* the _tests_ directory contains tests for the Scenic tool.
