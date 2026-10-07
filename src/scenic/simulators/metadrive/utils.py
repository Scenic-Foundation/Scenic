# NOTE: MetaDrive uses a coordinate system where (0, 0) is centered near the
# middle of the SUMO map.
# Some OpenDRIVE maps include a dataset-level <header><offset ...>, and
# SUMO/netconvert may apply an additional translation recorded as
# <location netOffset="..."> in the .net.xml.
# To align Scenic with MetaDrive, we account for both translations (when
# present) and then recenter using the convBoundary midpoint.

import math
import xml.etree.ElementTree as ET

from metadrive.envs import BaseEnv
from metadrive.manager.sumo_map_manager import SumoMapManager
from metadrive.obs.observation_base import DummyObservation

from scenic.core.vectors import Vector


def calculateFilmSize(
    sumo_map_boundary,
    scaling=5,
    margin_factor=1.1,
    min_extent=200.0,
):
    """Compute film_size (width, height) in pixels for MetaDrive's top-down renderer.

    The SUMO convBoundary gives the map extent (xmin, ymin, xmax, ymax) in meters.
    If one dimension is zero (e.g. a single straight road), clamp it to min_extent
    to avoid a zero-width/height film size.
    """
    xmin, ymin, xmax, ymax = sumo_map_boundary
    width = xmax - xmin
    height = ymax - ymin

    # Clamp zero-width/height maps (e.g. straight roads) to a reasonable minimum.
    width = max(width, min_extent)
    height = max(height, min_extent)

    adjusted_width = width * margin_factor
    adjusted_height = height * margin_factor

    film_w = int(adjusted_width * scaling)
    film_h = int(adjusted_height * scaling)
    return film_w, film_h


def extractNetOffsetAndBoundary(sumo_map_path):
    """Extracts the net offset and boundary from the given SUMO map file."""
    tree = ET.parse(sumo_map_path)
    root = tree.getroot()
    location_tag = root.find("location")
    net_offset = tuple(map(float, location_tag.attrib["netOffset"].split(",")))
    sumo_map_boundary = tuple(map(float, location_tag.attrib["convBoundary"].split(",")))
    return net_offset, sumo_map_boundary


def extractXODROffset(xodr_map_path):
    """Return the (x, y) translation from the OpenDRIVE <header><offset> element.

    If the file has no <header> or no <offset>, returns (0.0, 0.0).
    """
    tree = ET.parse(xodr_map_path)
    root = tree.getroot()
    header = root.find("header")
    if header is None:
        return 0.0, 0.0
    offset = header.find("offset")
    if offset is None:
        return 0.0, 0.0
    return float(offset.get("x", "0")), float(offset.get("y", "0"))


def getMapParameters(sumo_map_path, xodr_map_path):
    """Retrieve the map parameters."""
    net_offset, sumo_map_boundary = extractNetOffsetAndBoundary(sumo_map_path)
    xmin, ymin, xmax, ymax = sumo_map_boundary
    center_x = (xmin + xmax) / 2
    center_y = (ymin + ymax) / 2

    xodr_offset = extractXODROffset(xodr_map_path)
    combined_offset_x = net_offset[0] + xodr_offset[0]
    combined_offset_y = net_offset[1] + xodr_offset[1]

    scenic_offset = (center_x - combined_offset_x, center_y - combined_offset_y)
    return scenic_offset, sumo_map_boundary


def metadriveToScenicPosition(loc, scenic_offset):
    """Converts MetaDrive position to Scenic position using map parameters."""
    x_scenic = loc[0] + scenic_offset[0]
    y_scenic = loc[1] + scenic_offset[1]
    return Vector(x_scenic, y_scenic, 0)


def scenicToMetaDrivePosition(vec, scenic_offset):
    """Converts Scenic position to MetaDrive position using map parameters."""
    adjusted_x = vec[0] - scenic_offset[0]
    adjusted_y = vec[1] - scenic_offset[1]
    return adjusted_x, adjusted_y


class DriveEnv(BaseEnv):
    def reward_function(self, agent):
        """Dummy reward function."""
        return 0, {}

    def cost_function(self, agent):
        """Dummy cost function."""
        return 0, {}

    def done_function(self, agent):
        """Dummy done function."""
        return False, {}

    def get_single_observation(self):
        """Dummy observation function."""
        return DummyObservation()

    def setup_engine(self):
        """Setup the engine for MetaDrive."""
        super().setup_engine()
        self.engine.register_manager(
            "map_manager", SumoMapManager(self.config["sumo_map"])
        )
