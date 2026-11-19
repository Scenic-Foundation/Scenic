import math

import pytest

from scenic.simulators.utils.coordinates import rep103ToScenicHeading, scenicToRep103Heading


## rep103ToScenicHeading: REP-103 yaw (CCW from East) -> Scenic heading (CCW from North)


def test_rep103_north():
    # REP-103 yaw = π/2 (pointing North) -> Scenic heading = 0
    assert rep103ToScenicHeading(math.pi / 2) == pytest.approx(0.0)


def test_rep103_east():
    # REP-103 yaw = 0 (pointing East) -> Scenic heading = -π/2
    assert rep103ToScenicHeading(0.0) == pytest.approx(-math.pi / 2)


def test_rep103_west():
    # REP-103 yaw = π (pointing West) -> Scenic heading = π/2
    assert rep103ToScenicHeading(math.pi) == pytest.approx(-math.pi / 2 + math.pi)


def test_rep103_south():
    # REP-103 yaw = -π/2 (pointing South) -> Scenic heading = -π (or equivalently π)
    result = rep103ToScenicHeading(-math.pi / 2)
    assert abs(abs(result) - math.pi) < 1e-10


def test_rep103_output_normalized():
    # Output is always in [-π, π)
    for yaw in [0, math.pi / 3, math.pi, -math.pi, 3 * math.pi, -3 * math.pi / 2]:
        h = rep103ToScenicHeading(yaw)
        assert -math.pi <= h < math.pi, f"yaw={yaw}: heading {h} out of range"


## scenicToRep103Heading: Scenic heading (CCW from North) -> REP-103 yaw (CCW from East)


def test_scenic_north():
    # Scenic heading = 0 (pointing North) -> REP-103 yaw = π/2
    assert scenicToRep103Heading(0.0) == pytest.approx(math.pi / 2)


def test_scenic_east():
    # Scenic heading = -π/2 (pointing East) -> REP-103 yaw = 0
    assert scenicToRep103Heading(-math.pi / 2) == pytest.approx(0.0)


def test_scenic_west():
    # Scenic heading = π/2 (pointing West) -> REP-103 yaw = π (or -π)
    result = scenicToRep103Heading(math.pi / 2)
    assert abs(abs(result) - math.pi) < 1e-10


def test_scenic_output_normalized():
    for h in [0, math.pi / 3, math.pi / 2, -math.pi / 2, 3 * math.pi, -3 * math.pi]:
        y = scenicToRep103Heading(h)
        assert -math.pi <= y < math.pi, f"heading={h}: yaw {y} out of range"


## Round-trip


@pytest.mark.parametrize("heading", [
    0, math.pi / 6, math.pi / 4, math.pi / 2,
    -math.pi / 3, -math.pi / 2, math.pi * 0.9,
])
def test_round_trip(heading):
    assert rep103ToScenicHeading(scenicToRep103Heading(heading)) == pytest.approx(heading)
