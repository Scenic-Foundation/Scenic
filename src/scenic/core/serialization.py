"""Utilities to help serialize Scenic objects.

The functions in this module usually do not need to be used directly.
For high-level serialization APIs, see `Scenario.sceneToBytes`,
`Scenario.simulationToBytes`, and `Scene.dumpAsScenicCode`.
"""

import hashlib
import io
import math
import os
import pickle
import struct
import types
import warnings

from scenic.core.distributions import Samplable, needsSampling
from scenic.core.utils import DefaultIdentityDict


def deterministicHash(mapping, *, digest_size=8):
    """Compute a deterministic hash for a mapping of options.

    Keys are sorted (by their string representation) and encoded with explicit
    separators so that different key/value combinations do not collide under
    simple concatenation.

    Only int/float/str (and bool, as a subclass of int) values are encoded directly; any other value is replaced
    by a generic placeholder byte, to avoid nondeterminism from reprs containing
    memory addresses or other run-specific data.
    """
    hasher = hashlib.blake2b(digest_size=digest_size)
    # Sort by stringified key so we can handle non-string keys deterministically.
    for key in sorted(mapping.keys(), key=str):
        hasher.update(b"\0K")
        hasher.update(str(key).encode())
        hasher.update(b"\0V")
        value = mapping[key]
        if isinstance(value, (int, float, str)):
            hasher.update(str(value).encode())
        else:
            # Unsupported types just contribute a placeholder byte.
            hasher.update(b"\0")
    return hasher.digest()


## JSON


def scenicToJSON(obj):
    """Utility function to help serialize Scenic objects to JSON.

    Suitable for passing as the ``default`` argument to `json.dump`.
    At the moment this only supports very basic types like scalars and vectors:
    it does not allow encoding of an entire `Object`.
    """
    from scenic.core.vectors import Vector

    if isinstance(obj, Vector):
        return list(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


## Scenic code


def dumpAsScenicCode(value, stream):
    """Utility function to help export Scenic objects as Scenic code."""
    if hasattr(value, "dumpAsScenicCode"):
        value.dumpAsScenicCode(stream)
    else:
        stream.write(repr(value))


## Pickles

# If dill is installed, register some custom handlers to improve the pickling
# of Scene and Scenario objects.

try:
    import dill
except Exception:
    pass
else:
    _orig_save_module = dill.Pickler.dispatch[types.ModuleType]

    @dill.register(types.ModuleType)
    def patched_save_module(pickler, obj):
        # Save Scenic's internal modules by reference to avoid inconsistent versions
        # as well as some unpicklable objects (and shrink the size of pickles while
        # we're at it).
        name = obj.__name__
        if name == "scenic" or name.startswith("scenic."):
            pickler.save_reduce(dill._dill._import_module, (name,), obj=obj)
            return
        _orig_save_module(pickler, obj)


## Binary serialization format


class SerializationError(Exception):
    """An error occurring during serialization/deserialization of Scenic objects."""

    pass


class Serializer:
    """Class for (de)serializing scenes, etc.

    Ordinary Scenic users do not need to know about this class: they can use public
    APIs such as `Scenario.sceneToBytes`. If you have defined a custom type of
    `Distribution` whose **valueType** isn't one of the types used by the built-in
    primitive distributions (i.e. `int`, `float`, `Vector`), read on.

    The sampled value of a `Distribution` is encoded as follows:

    1. If the `Distribution` is `_deterministic`, recursively encode the sampled
       values of its dependencies.
    2. If its *valueType* is a type for which we have a "codec" (like `int` or
       `float`), use the encoding function provided by the codec.
    3. If the *valueType* provides a ``encodeTo`` method, use that.
    4. If the user has allowed the use of `pickle`, pickle the value.
    5. Otherwise raise a `SerializationError`.

    Thus, you need only extend the serialization mechanism if your `Distribution` cannot
    be made deterministic (by adding appropriate dependencies with simpler valueTypes)
    and it has an unusual **valueType**. In that case, it's best to have your **valueType**
    implement ``encodeTo`` and ``decodeFrom`` methods: see `Vector` for example. If for
    some reason you can't add those methods to the class in question, you can use
    `Serializer.addCodec` to register encoder/decoder functions. Finally, if you're only
    using serialization internally and aren't concerned about security issues or making
    the encoding as compact as possible, you can turn on the **allowPickle** option: this
    will use `pickle` to encode any objects for which no specialized encoder is known.
    """

    codecs = {}

    def __init__(self, data=b"", allowPickle=False, detectEnd=False):
        self.allowPickle = allowPickle
        self.stream = data if isinstance(data, io.BufferedIOBase) else io.BytesIO(data)
        if detectEnd:
            self.stream = io.BufferedReader(self.stream)
        self.seenObjs = set()

    def getBytes(self):
        return self.stream.getvalue()

    def atEnd(self):
        return not self.stream.peek(1)

    @classmethod
    def sceneFormatVersion(cls):
        """Current version of the `Scene` serialization format.

        Must be incremented if the `writeScene` method or any of its helper
        methods (e.g. `writeValue`) change, or if a new codec is added.
        """
        return 3

    @classmethod
    def replayFormatVersion(cls):
        """Current version of the `Simulation` replay serialization format.

        Must be incremented if the `writeReplayHeader` or `writeValue` methods
        change, or if a new codec is added.
        """
        return 2

    def writeScene(self, scenario, scene):
        """Serialize a `Scene`."""
        version = struct.pack("<H", self.sceneFormatVersion())
        self.stream.write(version)
        assert len(scenario.astHash) == 4
        self.stream.write(scenario.astHash)
        optionsHash = scenario.compileOptions.hash
        assert len(optionsHash) == 4
        self.stream.write(optionsHash)
        self.writeSample(scenario.dependencies, scene.sample)

    def readScene(self, scenario, verify=True):
        versionField = self.stream.read(2)
        if len(versionField) != 2:
            raise SerializationError("serialized Scene is corrupted")
        version = struct.unpack("<H", versionField)[0]
        if version != self.sceneFormatVersion():
            raise SerializationError(
                "cannot read serialized Scene from " "a different Scenic version"
            )
        astHash = self.stream.read(4)
        if verify and astHash != scenario.astHash:
            raise SerializationError(
                "serialized Scene does not correspond to this Scenario"
            )
        optionsHash = self.stream.read(4)
        if verify and optionsHash != scenario.compileOptions.hash:
            raise SerializationError(
                "serialized Scene used different compile options " "than this Scenario"
            )
        sample = self.readSample(scenario.dependencies)
        scene = scenario._makeSceneFromSample(sample)
        return scene

    def writeSample(self, objects, values):
        for obj in objects:
            self.writeSamplable(obj, values)

    def readSample(self, objects):
        values = DefaultIdentityDict()
        for obj in objects:
            self.readSamplable(obj, values)
        return values

    def writeSamplable(self, obj, values):
        if not needsSampling(obj):
            return  # value is not random, so no need to encode
        i = id(obj)
        if i not in self.seenObjs:
            self.seenObjs.add(i)
            obj.serializeValue(values, self)

    def readSamplable(self, obj, values):
        if not needsSampling(obj):
            return
        if obj not in values:
            values[obj] = obj.deserializeValue(self, values)

    def writeReplayHeader(self, flags):
        """Begin the encoding of a `Simulation` replay."""
        version = struct.pack("<H", self.replayFormatVersion())
        self.stream.write(version)
        self.stream.write(struct.pack("<I", flags))

    def readReplayHeader(self):
        versionField = self.stream.read(2)
        if len(versionField) != 2:
            raise SerializationError("replay is corrupted")
        version = struct.unpack("<H", versionField)[0]
        if version != self.replayFormatVersion():
            raise SerializationError("cannot read replay from a different Scenic version")
        flagsField = self.stream.read(4)
        if len(flagsField) != 4:
            raise SerializationError("replay is corrupted")
        flags = struct.unpack("<I", flagsField)[0]
        return flags

    @classmethod
    def addCodec(cls, ty, encoder, decoder):
        """Register encoder and decoder functions for the given type.

        The encoder function should have signature :samp:`encoder({value}, {stream})`
        with *stream* a :term:`binary file-like object <binary file>`. The decoder
        function should have signature :samp:`decoder({stream})` and return the decoded
        value.
        """
        if ty in cls.codecs:
            raise ValueError(f"Serializer already has a codec for type {ty}")
        cls.codecs[ty] = (encoder, decoder)

    def writeValue(self, value, ty):
        """Serialize a value of the given type."""
        try:
            if ty in self.codecs:
                encoder, decoder = self.codecs[ty]
                encoder(value, self.stream)
                return
            elif hasattr(ty, "encodeTo"):
                ty.encodeTo(value, self.stream)
                return
            elif self.allowPickle:
                pickle.dump(value, self.stream)
                return
        except Exception as e:
            raise SerializationError(
                f"failed to serialize object of type {ty.__name__}"
            ) from e

        # No known method of serialization
        raise SerializationError(f"{ty.__name__} type does not implement serialization")

    def readValue(self, ty):
        try:
            if ty in self.codecs:
                encoder, decoder = self.codecs[ty]
                return decoder(self.stream)
            elif hasattr(ty, "encodeTo"):
                return ty.decodeFrom(self.stream)
            elif self.allowPickle:
                return pickle.load(self.stream)
        except Exception as e:
            raise SerializationError(
                f"failed to deserialize object of type {ty.__name__}"
            ) from e

        # No known method of deserialization
        raise SerializationError(f"{ty.__name__} type does not implement serialization")


# Encoder/decoder functions for various types


def _writeNone(value, stream):
    pass


def _readNone(stream):
    return None


Serializer.addCodec(type(None), _writeNone, _readNone)


def writeFloat(value, stream):
    stream.write(struct.pack("<d", value))


def readFloat(stream):
    return struct.unpack("<d", stream.read(8))[0]


Serializer.addCodec(float, writeFloat, readFloat)


def writeInt(value, stream):
    # Optimize for small nonnegative integers, which commonly arise from Options
    if 0 <= value <= 252:
        stream.write(bytes([value]))
    elif -32768 <= value <= 32767:
        stream.write(bytes([253]))
        stream.write(value.to_bytes(length=2, byteorder="little", signed=True))
    elif -2147483648 <= value <= 2147483647:
        stream.write(bytes([254]))
        stream.write(value.to_bytes(length=4, byteorder="little", signed=True))
    else:
        stream.write(bytes([255]))
        length = max(1, math.ceil((value.bit_length() + 1) / 8))  # +1 for sign
        if length >= 256:
            raise SerializationError(
                "cannot serialize integers with >600 digits"
                " (what is this, cryptography?)"
            )
        stream.write(bytes([length]))
        stream.write(value.to_bytes(length=length, byteorder="little", signed=True))


def readInt(stream):
    first = stream.read(1)[0]
    if first <= 252:
        return first
    elif first == 253:
        return int.from_bytes(stream.read(2), byteorder="little", signed=True)
    elif first == 254:
        return int.from_bytes(stream.read(4), byteorder="little", signed=True)
    else:
        length = stream.read(1)[0]
        return int.from_bytes(stream.read(length), byteorder="little", signed=True)


Serializer.addCodec(int, writeInt, readInt)


def writeBool(value, stream):
    writeInt(value, stream)


def readBool(stream):
    return bool(readInt(stream))


Serializer.addCodec(bool, writeBool, readBool)


def writeBytes(value, stream):
    writeInt(len(value), stream)
    stream.write(value)


def readBytes(stream):
    length = readInt(stream)
    return stream.read(length)


Serializer.addCodec(bytes, writeBytes, readBytes)


def writeStr(value, stream):
    encoded = value.encode()
    writeBytes(encoded, stream)


def readStr(stream):
    encoded = readBytes(stream)
    return encoded.decode()


Serializer.addCodec(str, writeStr, readStr)
