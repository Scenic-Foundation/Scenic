import numpy as np

from scenic.core.sensors import CallbackSensor


class CarlaVisionSensor(CallbackSensor):
    def __init__(
        self,
        offset=(0, 0, 0),
        rotation=(0, 0, 0),
        width=None,
        height=None,
        attributes=None,
    ):
        super().__init__()
        self.offset = offset
        self.rotation = rotation

        if isinstance(attributes, str):
            raise NotImplementedError(
                "String parsing for attributes is not yet implemented. Feel free to do so."
            )
        elif isinstance(attributes, dict):
            self.attributes = attributes
        else:
            self.attributes = {}

        if width is not None:
            self.attributes["image_size_x"] = int(width)
        if height is not None:
            self.attributes["image_size_y"] = int(height)

        self.convert = None
        convert = self.attributes.get("convert")
        if convert is not None and not isinstance(convert, (str, int)):
            raise TypeError("'convert' has to be int or string.")
        self.convert = convert

        self.frame = 0

    blueprint = "sensor.camera.rgb"

    def onData(self, data):
        super().onData(data)
        self.frame = data.frame


class CarlaRGBSensor(CarlaVisionSensor):
    def process(self, data):
        array = np.frombuffer(data.raw_data, dtype=np.dtype("uint8"))
        array = np.reshape(array, (data.height, data.width, 4))  # BGRA format
        array = array[:, :, :3]  # Take only RGB
        array = array[:, :, ::-1]  # Revert order

        return array.copy()


class CarlaSSSensor(CarlaVisionSensor):
    blueprint = "sensor.camera.semantic_segmentation"

    def process(self, data):
        if self.convert is not None:
            data.convert(self.convert)

        array = np.frombuffer(data.raw_data, dtype=np.dtype("uint8"))
        array = np.reshape(array, (data.height, data.width, 4))  # BGRA format

        if self.convert is not None:
            array = array[:, :, :3]  # Take only RGB
            array = array[:, :, ::-1]  # Revert order
        else:
            array = array[:, :, 2]  # Take only R

        return array.copy()


class CarlaCollisionSensor(CallbackSensor):
    """Collision sensor that detects collisions with other actors/objects."""

    blueprint = "sensor.other.collision"

    def __init__(self):
        super().__init__()
        self.collision_history = []
        self.has_collision = False
        self.last_collision_intensity = 0.0
        self.last_collision_data = None
        self.frame = 0
        self._initialized = False
        self._is_event_based = True

        self.offset = (0, 0, 0)
        self.rotation = (0, 0, 0)
        self.attributes = {}
        self.convert = None
        self.carla_sensor = None

    def onData(self, event):
        self.frame = event.frame
        self._initialized = True

        impulse = event.normal_impulse
        intensity = np.sqrt(impulse.x**2 + impulse.y**2 + impulse.z**2)

        collision_info = {
            "frame": event.frame,
            "timestamp": event.timestamp,
            "intensity": intensity,
            "other_actor": event.other_actor.type_id if event.other_actor else None,
            "impulse": (impulse.x, impulse.y, impulse.z),
        }

        self.collision_history.append(collision_info)
        self.has_collision = True
        self.last_collision_intensity = intensity
        self.last_collision_data = collision_info

    def process(self, data):
        return self.last_collision_data

    def getObservation(self):
        return {
            "has_collision": self.has_collision,
            "last_collision_intensity": self.last_collision_intensity,
            "last_collision_data": self.last_collision_data,
            "collision_history": self.collision_history,
        }

    def updateFrame(self, frame):
        """Advance frame number for event-based sensors that didn't fire this tick."""
        if not self._initialized:
            self._initialized = True
        if self.frame < frame:
            self.frame = frame

    def reset(self):
        """Reset collision state between simulations."""
        self.collision_history = []
        self.has_collision = False
        self.last_collision_intensity = 0.0
        self.last_collision_data = None
        self.frame = 0
        self._initialized = False
