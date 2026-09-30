"""Support for values which are sampled outside of Scenic.

External Samplers in General
============================

External samplers provide a mechanism to use different types of sampling
techniques, like optimization or quasi-random sampling, from within a Scenic
program. Ordinary random values in Scenic are instances of `Distribution`;
this module defines a special subclass, `ExternalParameter`, representing a
value which is sampled externally. Scenic programs with external parameters
are handled as follows:

    1. During compilation, all instances of `ExternalParameter` are gathered
       together and given to the `ExternalSampler.forParameters` function;
       this function creates an appropriate `ExternalSampler`,
       whose configuration can be controlled using :term:`global parameters`
       (see the function documentation for details).

    2. When sampling a scene, before sampling any other distributions the
       :obj:`~ExternalSampler.sample` method of the `ExternalSampler` is
       called to sample all the external parameters. For active samplers, this
       method passes along the ``feedback`` value given to `Scenario.generate`,
       if any.

    3. Once the external parameters have values, the program is equivalent to
       one without external parameters, and sampling proceeds as usual. As for
       every instance of `Distribution`, the external parameters will have
       their :obj:`~Samplable.sampleGiven` method called once all their
       dependencies have been sampled; by default this method just returns the
       value sampled for this parameter in step (2).

.. note::

    Note that while external parameters, like all instances of `Distribution`,
    are allowed to have dependencies, they are an exception to the usual rule
    that dependencies are always sampled before dependents, because the
    `ExternalSampler.sample` method is called before any other sampling.
    However, as explained above, the :obj:`~Samplable.sampleGiven` method is
    called in the proper order and external samplers which need to do sampling
    based on the values of other distributions can be invoked from it. The
    two-step mechanism with `ExternalSampler.sample` is provided for samplers
    which sample the whole space of external parameters at once (e.g. the
    VerifAI samplers).

Samplers from VerifAI
=====================

The external sampling mechanism is designed to be extensible. The only built-in
`ExternalSampler` is the `VerifaiSampler`, which provides access to the
samplers in the `VerifAI`_ toolkit (which in turn can use Scenic as a modeling
language).

The `VerifaiSampler` supports several types of external parameters corresponding
to the primitive distributions: `VerifaiRange` and `VerifaiDiscreteRange` for
continuous and discrete intervals, and `VerifaiOptions` for discrete sets.
For example, suppose we write::

    ego = new Object at (VerifaiRange(5, 15), 0)

This is equivalent to the ordinary Scenic line :scenic:`ego = new Object at (Range(5, 15), 0)`,
except that the X coordinate of the ego is sampled by VerifAI within the range
(5, 15) instead of being uniformly distributed over it. By default the
`VerifaiSampler` uses VerifAI's `Halton`_ sampler, so the range will still be
covered uniformly but more systematically. If we want to use a different sampler,
we can set the ``verifaiSamplerType`` global parameter::

    param verifaiSamplerType = 'ce'
    ego = new Object at (VerifaiRange(5, 15), 0)

Now the X coordinate will be sampled using VerifAI's `cross-entropy`_ sampler.
If we pass a feedback value to `Scenario.generate` which scores the previous
scene, then the coordinate will not be sampled uniformly but rather converge to
a distribution concentrated on values minimizing the score. Active samplers like
cross-entropy can be used for falsification in this way, driving a system toward
parts of the parameter space where a specification is violated.

The cross-entropy sampler in VerifAI can be started from a non-uniform prior.
Scenic provides a convenient way to define this prior using the ordinary syntax
for distributions::

    param verifaiSamplerType = 'ce'
    ego = new Object at (VerifaiParameter.withPrior(Normal(10, 3)), 0)

Now cross-entropy sampling will start from a normal distribution with mean 10
and standard deviation 3. Priors are restricted to primitive distributions and
in general may be approximated so that VerifAI can handle them -- see
`VerifaiParameter.withPrior` for details.

To set a time bound when using VerifAI's dynamic sampling, set the ``timeBound``
global parameter to value representing the upper bound on the number of timesteps
the sampler should account for. For example::

    param timeBound = 250

This value can also be set directly in VerifAI via the ``maxSteps`` parameter to the
``ScenicSampler``.

For more information on how to customize the sampler, see `VerifaiSampler`.

.. _VerifAI: https://github.com/BerkeleyLearnVerify/VerifAI

.. _Halton: https://en.wikipedia.org/wiki/Halton_sequence

.. _cross-entropy: https://en.wikipedia.org/wiki/Cross-entropy_method

"""

from abc import ABC, abstractmethod
from importlib import metadata
from typing import Tuple
import warnings

from dotmap import DotMap
import numpy

from scenic.core.distributions import Distribution, Samplable
from scenic.core.errors import InvalidScenarioError


class ExternalSampler:
    """Abstract class for objects called to sample values for each external parameter.

    The initializer for this class takes the same arguments as the factory function
    `forParameters` below.

    Attributes:
        rejectionFeedback: Value passed to the `sample` method when the last sample was rejected.
          This value can be chosen by a Scenic scenario using the global parameter
          ``externalSamplerRejectionFeedback``.
    """

    def __init__(self, params, globalParams):
        # feedback value passed to external sampler when the last scene was rejected
        self.rejectionFeedback = globalParams.get("externalSamplerRejectionFeedback")

    @classmethod
    def getExternalParamType(cls):
        return ExternalParameter

    @classmethod
    def getExternalParameterConverter(cls):
        return ExternalParameterConverter(cls, cls.getExternalParamType())

    @staticmethod
    def forParameters(params, globalParams):
        """Create an `ExternalSampler` given the sets of external and global parameters.

        The scenario may explicitly select an external sampler by assigning the
        :term:`global parameter` ``externalSampler`` to a subclass of `ExternalSampler`.
        Otherwise, a `VerifaiSampler` is used by default.

        Args:
            params (tuple): Tuple listing each `ExternalParameter`.
            globalParams (dict): Dictionary of global parameters for the `Scenario`, made
              available here to support sampler customization through setting parameters.
              Note that the values of these parameters may be instances of `Distribution`!

        Returns:
            An `ExternalSampler` configured for the given parameters.
        """
        if len(params) > 0:
            from scenic.core.external_params.verifai import VerifaiSampler

            externalSampler = globalParams.get("externalSampler", VerifaiSampler)
            if not issubclass(externalSampler, ExternalSampler):
                raise InvalidScenarioError(
                    f"externalSampler type {externalSampler}"
                    " not subclass of ExternalSampler"
                )
            return externalSampler(params, globalParams)
        else:
            return None

    def sample(self, feedback):
        """Sample values for all the external parameters.

        Args:
            feedback: Feedback from the last sample (for active samplers).
        """
        self.cachedSample = self.nextSample(feedback)

    def nextSample(self, feedback):
        """Actually do the sampling. Implemented by subclasses."""
        raise NotImplementedError

    def valueFor(self, param):
        """Return the sampled value for a parameter. Implemented by subclasses."""
        raise NotImplementedError


class ExternalParameter(Distribution):
    """A value determined by external code rather than Scenic's internal sampler."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sampler = None
        self.isSeries = False
        import scenic.syntax.veneer as veneer  # TODO improve?

        veneer.registerExternalParameter(self)

    def sampleGiven(self, value):
        """Specialization of  `Samplable.sampleGiven` for external parameters.

        By default, this method simply looks up the value previously sampled by
        `ExternalSampler.sample`.
        """
        assert self.sampler is not None
        return self.sampler.valueFor(self)

    def extractOutput(self, value):
        """
        Given a raw sampled value for a parameter, optionally extract the actual desired value.

        By default just passes the value through unchanged.
        """
        return value


class ExternalParameterConverter:
    def __init__(self, samplerType, paramType):
        self.samplerType = samplerType
        self.paramType = paramType
        self.externalParams = []

    def registerExternalParams(self, dist):
        for d in dist.recursiveDependencies():
            if isinstance(d, self.paramType):
                self.externalParams.append(d)

    def convert(self, samp):
        if not isinstance(samp, Samplable):
            return

        sampCond = samp._conditioned

        if isinstance(sampCond, self.paramType) or not isinstance(sampCond, Distribution):
            for dep in sampCond._dependencies:
                self.convert(dep)
        else:
            try:
                self.convertInner(samp)
            except NotImplementedError:
                warnings.warn(
                    f"Unable to convert {type(sampCond)} to {self.paramType} based distribution."
                )

    def convertInner(self, dist):
        """Condition dist to an equivalent `ExternalParameter` based sampblable.

        If such a conversion is not possible, this function should raise NotImplementedError.
        """
        raise NotImplementedError


class SeriesParameter:
    def __init__(self, callback):
        self._callback = callback
        self._lastSimulation = None
        self._lastTime = -1

    def getSample(self):
        import scenic.syntax.veneer as veneer

        assert veneer.currentSimulation is not None

        if self._lastSimulation is not veneer.currentSimulation:
            self._lastSimulation = veneer.currentSimulation
            self._lastTime = -1

        if veneer.currentSimulation.currentTime <= self._lastTime:
            raise RuntimeError(
                "Attempted `getSample` for a Series external parameter twice in one timestep."
            )

        self._lastTime = veneer.currentSimulation.currentTime
        return self._callback()


def Series(param):
    if not isinstance(param, ExternalParameter):
        raise TypeError("Cannot turn a non `ExternalParameter` into a series")

    param.isSeries = True
    return param
