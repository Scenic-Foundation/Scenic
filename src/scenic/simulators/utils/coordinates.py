"""Coordinate-convention utilities shared across simulator adapters.

Scenic headings are measured CCW from North:
0 = North, π/2 = West, -π/2 = East.
ROS2 REP-103 yaw (ENU frame) is measured CCW from East:
0 = East, π/2 = North.

MetaDrive and GTA's internal grid both use the same East-zero convention as REP-103.

Conversion:  scenic_heading = rep103_yaw - π/2
             rep103_yaw     = scenic_heading + π/2
"""

import math

from scenic.core.geometry import normalizeAngle


def rep103ToScenicHeading(yaw: float) -> float:
    """ROS2 REP-103 yaw (CCW from East, radians) → Scenic heading (CCW from North, radians)."""
    return normalizeAngle(yaw - math.pi / 2)


def scenicToRep103Heading(heading: float) -> float:
    """Scenic heading (CCW from North, radians) → ROS2 REP-103 yaw (CCW from East, radians)."""
    return normalizeAngle(heading + math.pi / 2)
