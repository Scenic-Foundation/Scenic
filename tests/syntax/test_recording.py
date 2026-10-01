"""Tests for advanced usages of the `record` statement."""

import numpy as np

from tests.utils import compileScenic, sampleResult

## Utilities


def checkRecordTo(tmp_path, period=None, delay=None, maxSteps=5):
    """Helper for testing the `record ... to ...` statement.

    Returns the timesteps at which a value was recorded.
    """

    # Clear out the folder in case the helper is used multiple times in a test
    for f in tmp_path.iterdir():
        f.unlink()

    every = f"every {period}" if period else ""
    after = f"after {delay}" if delay else ""
    scenario = compileScenic(
        f"""
        record -simulation().currentTime {every} {after} to "value_{{step}}.npy"
        record -simulation().currentTime {every} {after} to "series.npz"
        """,
        params=dict(recordFolder=tmp_path),
    )
    result = sampleResult(scenario, maxSteps=maxSteps)
    assert result is not None

    recordedTimes = []
    for t in range(maxSteps + 1):
        path = tmp_path / f"value_{t}.npy"
        if path.exists():
            value = np.load(path)
            assert float(value) == -t
            recordedTimes.append(t)

    series = np.load(tmp_path / "series.npz")
    assert np.array_equal(series["timesteps"], recordedTimes)
    assert np.array_equal(series["values"], [-t for t in recordedTimes])

    return recordedTimes


## Recording to files


def test_record_to(tmp_path):
    times = checkRecordTo(tmp_path)
    assert times == [0, 1, 2, 3, 4, 5]


def test_record_to_after(tmp_path):
    times = checkRecordTo(tmp_path, delay="2 steps")
    assert times == [2, 3, 4, 5]

    times = checkRecordTo(tmp_path, delay="3.5 seconds")
    assert times == [3, 4, 5]

    times = checkRecordTo(tmp_path, delay="10 steps")
    assert times == []


def test_record_to_every(tmp_path):
    times = checkRecordTo(tmp_path, period="2 steps")
    assert times == [0, 2, 4]

    times = checkRecordTo(tmp_path, period="3.5 seconds")
    assert times == [0, 3]

    times = checkRecordTo(tmp_path, period="10 steps")
    assert times == [0]


def test_record_to_in_subscenario(tmp_path):
    scenario = compileScenic(
        """
        scenario Main():
            compose:
                wait for 2 steps
                do Sub(1)
                wait for 2 steps
                do Sub(2)
                wait
        scenario Sub(i):
            record simulation().currentTime to "value_{step}.npy"
            record simulation().currentTime to f"series{i}.npz"
            terminate after 2 steps
        """,
        params=dict(recordFolder=tmp_path),
    )
    result = sampleResult(scenario, maxSteps=10)
    assert result is not None

    for t in range(11):
        path = tmp_path / f"value_{t}.npy"
        if 2 <= t <= 4 or 6 <= t <= 8:
            value = np.load(path)
            assert float(value) == t
        else:
            assert not path.exists(), t

    series1 = np.load(tmp_path / "series1.npz")
    assert np.array_equal(series1["timesteps"], [2, 3, 4])
    assert np.array_equal(series1["values"], [2, 3, 4])
    series2 = np.load(tmp_path / "series2.npz")
    assert np.array_equal(series2["timesteps"], [6, 7, 8])
    assert np.array_equal(series2["values"], [6, 7, 8])
