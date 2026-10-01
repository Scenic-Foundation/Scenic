"""Sensors which can gather and save data from simulations."""

import abc
from dataclasses import dataclass
import math
import os.path
import pickle
import sys
from typing import Literal, Tuple

import PIL.Image
import cv2
import numpy as np


class Sensor(abc.ABC):
    @abc.abstractmethod
    def getObservation(self):
        raise NotImplementedError


class RGBSensor(Sensor, abc.ABC):
    """Abstract RGB camera sensor.

    Args:
        offset: Sensor position offset relative to the attached object (x, y, z).
        rotation: Sensor rotation relative to the attached object (yaw, pitch, roll).
        width: Output image width.
        height: Output image height.
        attributes: Simulator-specific options (dict).

    """

    pass


class SSSensor(Sensor, abc.ABC):
    """Abstract semantic segmentation camera sensor.

    Args:
        offset: Sensor position offset relative to the attached object (x, y, z).
        rotation: Sensor rotation relative to the attached object (yaw, pitch, roll).
        width: Output image width.
        height: Output image height.
        attributes: Simulator-specific options (dict).

    """

    pass


NO_OBSERVATION = object()


class CallbackSensor(Sensor):
    def __init__(self, defaultValue=NO_OBSERVATION):
        self._lastObservation = defaultValue

    def getObservation(self):
        if self._lastObservation is NO_OBSERVATION:
            raise RuntimeError(
                f"{type(self).__name__} callback not called before first observation"
            )

        return self._lastObservation

    def onData(self, data):
        self._lastObservation = self.process(data)

    @abc.abstractmethod
    def process(self, data):
        raise NotImplementedError


class GroundTruthSensor(Sensor):
    def __init__(self, value):
        self._value = value

    def getObservation(self):
        return self._value()


# Recorders


@dataclass
class RecordingConfiguration:
    name: str
    period: Tuple[float, Literal["seconds", "steps"]]
    delay: Tuple[float, Literal["seconds", "steps"]]

    recorder: "Optional[Recorder]" = None


class Recorder:
    """A method of saving a :ref:`record <record>` to a file.

    Detailed documentation forthcoming.
    """

    def __init__(self):
        self._recording = False

    def beginRecording(self, config, simulationName, timestep, globalParams, currentTime):
        assert not self._recording
        self._recording = True
        self.simulationName = simulationName
        self.recordName = config.name
        self.timestep = timestep
        self.globalParams = globalParams

        val, unit = config.period
        if unit == "steps":
            assert isinstance(val, int) and val >= 1, val
            self._period = val
        else:  # unit == "seconds"
            assert val > 0, val
            self._period = max(1, math.floor(val / timestep))

        val, unit = config.delay
        assert val >= 0, val
        if unit == "steps":
            assert isinstance(val, int), val
            delay = val
        else:  # unit == "seconds"
            delay = max(0, math.floor(val / timestep))
        self._startTime = currentTime + delay

    def recordValue(self, value, step):
        raise NotImplementedError

    def endRecording(self, canceled):
        assert self._recording
        self._recording = False

    def _record(self, value, step):
        relativeTime = step - self._startTime
        if relativeTime >= 0 and relativeTime % self._period == 0:
            self.recordValue(np.asarray(value), step)

    @staticmethod
    def _forPattern(pattern):
        p0 = Recorder._formatPattern(pattern, "s", 0, 0)
        p1 = Recorder._formatPattern(pattern, "s", 1, 1)
        if p0 != p1:  # pattern depends on step or time
            return Files(pattern)
        else:
            return File(pattern)

    @staticmethod
    def _formatPattern(pattern, simName, step, time):
        return pattern.format(
            simName, step, time, simulation=simName, step=step, time=time
        )

    def makePath(self, step, time):
        path = self.pattern
        if recordFolder := self.globalParams.get("recordFolder"):
            path = os.path.join(recordFolder, path)
        path = self._formatPattern(path, self.simulationName, step, time)
        return path


class AccumulatingRecorder(Recorder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._series = []

    def recordTimeSeries(self, series):
        raise NotImplementedError

    def recordValue(self, value, step):
        self._series.append((step, value))

    def endRecording(self, canceled):
        if not canceled:
            self.recordTimeSeries(self._series)
        self._series.clear()
        super().endRecording(canceled)


valueExtHandlers = {}  #: Handlers for saving individual values to files, by extension
seriesExtHandlers = {}  #: Handlers for saving time series to files, by extension


def prepareImageData(data, intOnly=False):
    shape = data.shape
    noColor = False
    if len(shape) == 2:
        noColor = True
    elif len(shape) != 3 or shape[2] != 3:
        raise TypeError(f"image data must be a 2D array of intensities or RGB triples")
    dtype = data.dtype
    kind = dtype.kind
    if kind == "u" or kind == "i":
        if np.min(data) < 0 or np.max(data) > 255:
            raise ValueError(f"integer pixel data must be in the range 0-255")
        return data.astype("uint8", copy=False)
    elif kind == "f":
        if np.min(data) < 0 or np.max(data) > 1:
            raise ValueError(f"floating-point pixel data must be in the range 0-1")
        if noColor and not intOnly:
            return data.astype("float32", copy=False)
        else:
            # PIL doesn't support RGB floating-point, so round to integers
            return np.round(data * 255).astype("uint8")
    elif kind == "b":
        if intOnly:
            return (data * 255).astype("uint8")
        else:
            return data
    else:
        raise TypeError(f"cannot create image from data with dtype {dtype.name}")


def pilHandler(path, value, options):
    image = PIL.Image.fromarray(prepareImageData(value))
    image.save(path, **options)


for ext, name in PIL.Image.registered_extensions().items():
    if name in PIL.Image.SAVE:
        valueExtHandlers[ext[1:]] = pilHandler


def npyHandler(path, value, options):
    np.save(path, value, **options)


valueExtHandlers["npy"] = npyHandler


def fileHandler(*exts):
    def decorator(handler):
        for ext in exts:
            assert ext and not ext[0] == ".", ext
            seriesExtHandlers[ext] = handler
        return handler

    return decorator


@fileHandler("mkv", "mov", "mp4")
def videoHandler(path, values, timestep, options):
    if not values:
        return  # empty time series
    codec = options.get("codec")
    if codec is None:
        if sys.platform == "darwin":
            # Pragmatic choice for wider playability; may switch to always using AV1 later
            codec = "avc1" if path.endswith((".mp4", ".mov")) else "AV01"
        else:
            codec = "mp4v"
    elif len(codec) != 4:
        raise ValueError("video codec must be a 4-character string (FourCC)")
    fourcc = cv2.VideoWriter_fourcc(*codec)
    height, width = values[0][1].shape[:2]
    writer = cv2.VideoWriter(path, fourcc, 1.0 / timestep, (width, height))
    try:
        for step, value in values:
            frame = cv2.cvtColor(prepareImageData(value, intOnly=True), cv2.COLOR_RGB2BGR)
            writer.write(frame)
    finally:
        writer.release()


@fileHandler("npz")
def npzHandler(path, values, timestep, options):
    timesteps, values = zip(*values) if values else ([], [])
    np.savez_compressed(path, timesteps=timesteps, values=values)


@fileHandler("pickle")
def pickleHandler(path, values, timestep, options):
    with open(path, "wb") as outFile:
        pickle.dump(values, outFile, **options)


class File(AccumulatingRecorder):
    def __init__(self, pattern, /, **options):
        super().__init__()
        self.pattern = pattern
        _, ext = os.path.splitext(pattern)
        handler = seriesExtHandlers.get(ext[1:])
        if handler is None:
            if ext:
                raise ValueError(
                    f'unknown file extension "{ext}" for recording a time series'
                )
            handler = npzHandler
        self.handler = handler
        self.options = options

    def recordTimeSeries(self, series):
        path = self.makePath("series", "series")
        if dirname := os.path.dirname(path):
            os.makedirs(dirname, exist_ok=True)
        self.handler(path, series, self.timestep, self.options)


class Files(Recorder):
    def __init__(self, pattern, /, **options):
        super().__init__()
        self.pattern = pattern
        _, ext = os.path.splitext(pattern)
        if not ext:
            ext = ".npy"
            self.pattern += ".npy"
        self.handler = valueExtHandlers.get(ext[1:])
        if self.handler is None:
            raise ValueError(
                f'unknown file extension "{ext}" for recording a single value'
            )
        self.options = options
        self._paths = []

    def recordValue(self, value, step):
        time = step * self.timestep
        path = self.makePath(step, time)
        self._paths.append(path)
        if dirname := os.path.dirname(path):
            os.makedirs(dirname, exist_ok=True)
        self.handler(path, value, self.options)

    def endRecording(self, canceled):
        if canceled:
            for path in self._paths:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
        self._paths.clear()
        super().endRecording(canceled)
