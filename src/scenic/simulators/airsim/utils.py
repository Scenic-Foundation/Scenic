import airsim
import scipy

from scenic.core.type_support import toVector
from scenic.core.vectors import Orientation, Vector

worldOffset = Vector(0, 0, 0)


def tupleToVector3r(tuple):
    return airsim.Vector3r(tuple[0], tuple[1], tuple[2])


def VectorToAirsimVec(vec):
    return airsim.Vector3r(vec.x, vec.y, vec.z)


def AirsimVecToVector(vec):
    return Vector(vec.x_val, vec.y_val, vec.z_val)


def scenicToAirsimVector(vector):
    """Convert a Scenic vector to AirSim axes without translating it."""
    vector = toVector(vector)
    return airsim.Vector3r(vector.x, -vector.y, -vector.z)


def airsimToScenicVector(vector):
    """Convert an AirSim vector to Scenic axes without translating it."""
    return Vector(vector.x_val, -vector.y_val, -vector.z_val)


def scenicToAirsimOrientation(orientation):
    rad90 = 1.5708
    yaw, pitch, roll = orientation.r.as_euler("ZXY", degrees=False)
    yaw = -yaw - rad90
    return airsim.to_quaternion(pitch=pitch, yaw=yaw, roll=roll)


def airsimToScenicOrientation(orientation):
    pitch, roll, yaw = airsim.to_eularian_angles(orientation)
    angles = (pitch, -yaw - 90, roll)
    r = scipy.spatial.transform.Rotation.from_euler(
        seq="ZXY", angles=angles, degrees=True
    )
    orientation = Orientation(r)
    return Orientation(r)


# forPose - if the output will be fed into airsim's airsim.Pose() function
def scenicToAirsimLocation(position, centerOffset=Vector(0, 0, 0), forPose=True):
    # turn position to a vector
    position = Vector(position.x, position.y, position.z)

    # convert to unreal
    position *= 100  # account for mesh scaling
    position = Vector(position.x, -position.y, position.z)  # left hand coords

    position -= centerOffset
    position -= worldOffset

    if forPose:
        # undo airsim's adjustments
        position /= 100  # divide by 100
        position = Vector(position.x, position.y, -position.z)  # negate z axis

    position = airsim.Vector3r(
        position.x, position.y, position.z
    )  # multiplies by 100 and negates z axis

    return position


# fromPose - if position was gained from simGetObjectPose
def airsimToScenicLocation(position, centerOffset=Vector(0, 0, 0), fromPose=True):
    position = Vector(
        position.x_val,
        position.y_val,
        position.z_val,
    )

    if fromPose:
        # undo airsim's adjustments
        position *= 100  # mult by 100
        position = Vector(position.x, position.y, -position.z)  # negate z axis

    position += centerOffset
    position += worldOffset

    # convert to scenic
    position /= 100  # account for mesh scaling by .01
    position = Vector(position.x, -position.y, position.z)  # left hand coords

    return position


def scenicToAirsimScale(size, dims):
    return airsim.Vector3r(size.x / dims.x, size.y / dims.y, size.z / dims.z)


_prexistingObjs = {}


def _addPrexistingObj(obj):
    _prexistingObjs[obj.name] = obj


def getPrexistingObj(objName):
    return _prexistingObjs[objName]
