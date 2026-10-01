from scenic.core.distributions import Options
from scenic.core.external_params.external_params import *


class VerifaiSampler(ExternalSampler):
    """An external sampler exposing the samplers in the VerifAI toolkit.

    The sampler can be configured using the following Scenic :term:`global parameters`:

        * ``verifaiSamplerType`` -- sampler type (see the ``verifai.server.choose_sampler``
          function); the default is ``'halton'``
        * ``verifaiSamplerParams`` -- ``DotMap`` of options passed to the sampler

    The `VerifaiSampler` supports external parameters which are instances of `VerifaiParameter`.
    """

    def __init__(self, params, globalParams):
        super().__init__(params, globalParams)
        import verifai.features
        import verifai.server

        self._verifaiDynamic = int(metadata.version("verifai").split(".")[0]) > 2

        # construct FeatureSpace
        timeBound = globalParams.get("timeBound", 0)
        usingProbs = False
        self.params = tuple(params)
        for index, param in enumerate(self.params):
            if not isinstance(param, VerifaiParameter):
                raise RuntimeError(
                    f"VerifaiSampler given parameter of wrong type: {param}"
                )
            param.sampler = self
            param.index = index
            if param.probs is not None:
                usingProbs = True

        if not self._verifaiDynamic and any(param.isSeries for param in self.params):
            raise RuntimeError("Series not supported for VerifAI versions < 3.0")

        if timeBound == 0 and any(param.isSeries for param in self.params):
            warnings.warn(
                "Series external parameter used but no global parameter `timeBound` is specified. "
                "(If using VerifAI’s ScenicSampler, set its maxSteps option)."
            )

        fs_kwargs = {}
        if self._verifaiDynamic:
            fs_kwargs["timeBound"] = timeBound

        space = verifai.features.FeatureSpace(
            {
                self.nameForParam(index): (
                    verifai.features.Feature(param.domain)
                    if not param.isSeries
                    else verifai.features.SeriesFeature(param.domain)
                )
                for index, param in enumerate(self.params)
            },
            **fs_kwargs,
        )

        # set up VerifAI sampler
        samplerType = globalParams.get("verifaiSamplerType", "halton")
        samplerParams = globalParams.get("verifaiSamplerParams", None)
        if usingProbs and samplerType == "ce":
            if samplerParams is None:
                samplerParams = DotMap()
            else:
                samplerParams = samplerParams.copy()  # avoid mutating original
            if "cont" in samplerParams or "disc" in samplerParams:
                raise RuntimeError(
                    "CE distributions specified in both VerifaiParameters"
                    " and verifaiSamplerParams"
                )
            cont_buckets = []
            cont_dists = []
            disc_dists = []
            for param in self.params:
                if isinstance(param, VerifaiRange):
                    if param.probs is None:
                        buckets = 5
                        dist = numpy.ones(buckets) / buckets
                    else:
                        dist = numpy.array(param.probs)
                        buckets = len(dist)
                    cont_buckets.append(buckets)
                    cont_dists.append(dist)
                elif isinstance(param, VerifaiDiscreteRange):
                    n = param.high - param.low + 1
                    dist = (
                        numpy.ones(n) / n
                        if param.probs is None
                        else numpy.array(param.probs)
                    )
                    disc_dists.append(dist)
                else:
                    raise RuntimeError(f"Parameter {param} not supported by CE sampler")
            samplerParams.cont.buckets = cont_buckets
            samplerParams.cont.dist = numpy.array(cont_dists)
            samplerParams.disc.dist = numpy.array(disc_dists)
        data = verifai.server.choose_sampler(
            space, samplerType, sampler_params=samplerParams
        )
        if not data:
            raise RuntimeError(f'Unknown VerifAI sampler type "{samplerType}"')
        self.sampler = data[1]

        # default rejection feedback is positive so cross-entropy sampler won't update;
        # for other active samplers an appropriate value should be set manually
        if self.rejectionFeedback is None:
            self.rejectionFeedback = 1
        self.cachedSample = None

        self._lastSample = None
        self._lastInfo = None
        self._lastDynamicSample = None
        self._lastSimulation = None
        self._lastTime = -1

    def nextSample(self, feedback):
        if feedback is not None:
            assert self._lastSample is not None
            if self._verifaiDynamic:
                self._lastSample.complete(feedback)
            else:
                self.sampler.update(self._lastSample, self._lastInfo, feedback)

        if self._verifaiDynamic:
            self._lastSample = self.sampler.getSample()
        else:
            lastSample = self.sampler.getSample()
            self._lastSample = lastSample[0]
            self._lastInfo = lastSample[1]
        return self._lastSample

    def nextDynamicSample(self):
        import scenic.syntax.veneer as veneer

        assert veneer.currentSimulation is not None

        if self._lastSimulation is not veneer.currentSimulation:
            self._lastSimulation = veneer.currentSimulation
            self._lastTime = -1

        if veneer.currentSimulation.currentTime > self._lastTime:
            feedback = veneer.currentSimulation
            self._lastDynamicSample = self.cachedSample.getDynamicSample(feedback)
            self._lastTime = veneer.currentSimulation.currentTime

        return self._lastDynamicSample

    def valueFor(self, param):
        if not param.isSeries:
            if self._verifaiDynamic:
                sampleTarget = self.cachedSample.staticSample
            else:
                sampleTarget = self.cachedSample
            return param.extractOutput(
                getattr(sampleTarget, self.nameForParam(param.index))
            )
        else:
            callback = lambda: param.extractOutput(
                getattr(
                    self.nextDynamicSample(),
                    self.nameForParam(param.index),
                )
            )
            return SeriesParameter(callback)

    @staticmethod
    def nameForParam(i):
        """Parameter name for a given index in the Feature Space."""
        return f"param{i}"


class VerifaiParameter(ExternalParameter):
    """An external parameter sampled using one of VerifAI's samplers."""

    def __init__(self, domain):
        super().__init__()
        self.domain = domain

    @staticmethod
    def withPrior(dist, buckets=None):
        """Creates a `VerifaiParameter` using the given distribution as a prior.

        Since the VerifAI cross-entropy sampler currently only supports piecewise-constant
        distributions, if the prior is not of that form it may be approximated. For most
        built-in distributions, the approximation is exact: for a particular distribution,
        check its `bucket` method.
        """
        if not dist.isPrimitive:
            raise RuntimeError(
                "VerifaiParameter.withPrior called on "
                f"non-primitive distribution {dist}"
            )
        bucketed = dist.bucket(buckets=buckets)
        return VerifaiOptions(
            bucketed.optWeights if bucketed.optWeights else bucketed.options
        )


class VerifaiRange(VerifaiParameter):
    """A :obj:`~scenic.core.distributions.Range` (real interval) sampled by VerifAI."""

    _defaultValueType = float

    def __init__(self, low, high, buckets=None, weights=None):
        import verifai.features

        super().__init__(verifai.features.Box([low, high]))
        if weights is not None:
            weights = tuple(weights)
            if buckets is not None and len(weights) != buckets:
                raise RuntimeError(
                    f"VerifaiRange created with {len(weights)} weights "
                    f"but {buckets} buckets"
                )
        elif buckets is not None:
            weights = [1] * buckets
        else:
            self.probs = None
            return
        total = sum(weights)
        self.probs = tuple(wt / total for wt in weights)

    def extractOutput(self, value):
        assert len(value) == 1
        return value[0]


class VerifaiDiscreteRange(VerifaiParameter):
    """A :obj:`~scenic.core.distributions.DiscreteRange` (integer interval) sampled by VerifAI."""

    _defaultValueType = float

    def __init__(self, low, high, weights=None):
        import verifai.features

        super().__init__(verifai.features.DiscreteBox([low, high]))
        if weights is not None:
            if len(weights) != (high - low + 1):
                raise RuntimeError(
                    f"VerifaiDiscreteRange created with {len(weights)} weights "
                    f"for {high - low + 1} values"
                )
            total = sum(weights)
            self.probs = tuple(wt / total for wt in weights)
        else:
            self.probs = None

    def extractOutput(self, value):
        assert len(value) == 1
        return value[0]


class VerifaiOptions(Options):
    """An :obj:`~scenic.core.distributions.Options` (discrete set) sampled by VerifAI."""

    @staticmethod
    def makeSelector(n, weights):
        return VerifaiDiscreteRange(0, n, weights)
