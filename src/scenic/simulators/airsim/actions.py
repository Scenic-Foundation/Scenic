from scenic.core.simulators import Action
from scenic.core.type_support import toVector
from scenic.syntax.veneer import verbosePrint

from .utils import scenicToAirsimVector


class SetVelocity(Action):
    def __init__(self, velocity):
        self.requestedVelocity = toVector(velocity)
        self.newVelocity = scenicToAirsimVector(self.requestedVelocity)
        verbosePrint(
            f"AirSim velocity command: {self.requestedVelocity} -> "
            f"({self.newVelocity.x_val}, {self.newVelocity.y_val}, "
            f"{self.newVelocity.z_val})",
            level=3,
        )

    def applyTo(self, obj, sim):
        client = sim.client
        client.cancelLastTask(vehicle_name=obj.realObjName)
        client.moveByVelocityAsync(
            self.newVelocity.x_val,
            self.newVelocity.y_val,
            self.newVelocity.z_val,
            duration=5,
            vehicle_name=obj.realObjName,
        )
