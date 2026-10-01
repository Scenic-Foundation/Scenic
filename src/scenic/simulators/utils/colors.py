"""A basic color type.

This used for example to represent car colors in the abstract driving domain,
as well as in the interfaces to GTA and Webots.
"""

from collections import namedtuple
import colorsys
import random
import struct

from scenic.core.distributions import Distribution, Normal, Options, Range, toDistribution
from scenic.core.lazy_eval import valueInContext
from scenic.core.object_types import Mutator


class Color(namedtuple("Color", ["r", "g", "b"])):
    """A color as an RGB tuple."""

    @classmethod
    def withBytes(cls, color):
        return cls._make(c / 255.0 for c in color)

    @staticmethod
    def realToByte(color):
        return tuple(int(round(255 * c)) for c in color)

    @staticmethod
    def encodeTo(color, stream):
        stream.write(struct.pack("<ddd", *color))

    @staticmethod
    def decodeFrom(stream):
        return Color(*struct.unpack("<ddd", stream.read(24)))

    @staticmethod
    def uniformColor():
        """Return a uniformly random color."""
        return toDistribution(Color(Range(0, 1), Range(0, 1), Range(0, 1)))

    @staticmethod
    def defaultCarColor():
        """Default color distribution for cars.

        The distribution starts with a base distribution over 9 discrete colors,
        then adds Gaussian HSL noise. The base distribution uses color popularity
        statistics from a `2012 DuPont survey`_.

        .. _2012 DuPont survey: https://web.archive.org/web/20121229065631/http://www2.dupont.com/Media_Center/en_US/color_popularity/Images_2012/DuPont2012ColorPopularity.pdf
        """
        baseColors = {
            (248, 248, 248): 0.24,  # white
            (50, 50, 50): 0.19,  # black
            (188, 185, 183): 0.16,  # silver
            (130, 130, 130): 0.15,  # gray
            (194, 92, 85): 0.10,  # red
            (75, 119, 157): 0.07,  # blue
            (197, 166, 134): 0.05,  # brown/beige
            (219, 191, 105): 0.02,  # yellow/gold
            (68, 160, 135): 0.02,  # green
        }
        converted = {Color.withBytes(color): prob for color, prob in baseColors.items()}
        baseColor = Options(converted)
        # TODO improve this?
        hueNoise = Normal(0, 0.1)
        satNoise = Normal(0, 0.1)
        lightNoise = Normal(0, 0.1)
        return NoisyColorDistribution(baseColor, hueNoise, satNoise, lightNoise)


class NoisyColorDistribution(Distribution):
    """A distribution given by HSL noise around a base color.

    Arguments:
        baseColor (RGB tuple): base color
        hueNoise (float): noise to add to base hue
        satNoise (float): noise to add to base saturation
        lightNoise (float): noise to add to base lightness
    """

    _deterministic = True

    def __init__(self, baseColor, hueNoise, satNoise, lightNoise):
        super().__init__(baseColor, hueNoise, satNoise, lightNoise, valueType=Color)
        self.baseColor = baseColor
        self.hueNoise = hueNoise
        self.satNoise = satNoise
        self.lightNoise = lightNoise

    @staticmethod
    def addNoiseTo(color, hueNoise, lightNoise, satNoise):
        try:
            hue, lightness, saturation = colorsys.rgb_to_hls(*color[:3])
        except ZeroDivisionError:
            hue, lightness, saturation = 0.0, 1.0, 0.0
        hue = max(0, min(1, hue + hueNoise))
        lightness = max(0, min(1, lightness + lightNoise))
        saturation = max(0, min(1, saturation + satNoise))
        return colorsys.hls_to_rgb(hue, lightness, saturation)

    def sampleGiven(self, value):
        bc = value[self.baseColor]
        return Color(
            *self.addNoiseTo(
                bc, value[self.hueNoise], value[self.lightNoise], value[self.satNoise]
            )
        )

    def evaluateInner(self, context):
        self.baseColor = valueInContext(self.baseColor, context)
        self.hueNoise = valueInContext(self.hueNoise, context)
        self.satNoise = valueInContext(self.satNoise, context)
        self.lightNoise = valueInContext(self.lightNoise, context)


class ColorMutator(Mutator):
    """Mutator that adds Gaussian HSL noise to the ``color`` property."""

    def appliedTo(self, obj):
        stddev = 0.05 * obj.mutationScale
        hueNoise = random.gauss(0, stddev)
        satNoise = random.gauss(0, stddev)
        lightNoise = random.gauss(0, stddev)
        obj.color = NoisyColorDistribution.addNoiseTo(
            obj.color, hueNoise, lightNoise, satNoise
        )
        return (obj, True)  # allow further mutation
