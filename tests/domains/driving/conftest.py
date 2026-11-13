import glob
import os
from pathlib import Path
import shutil

import pytest

from scenic.domains.driving.roads import Network

mapFolder = Path("assets") / "maps"
maps = glob.glob(str(mapFolder / "**" / "*.xodr"))

badmaps = []  # currently all maps are working!
# Maps with targeted parser tests but not yet supported for full scenario load.
scenario_test_exclusions = {
    str(mapFolder / "misc" / "bs-schwarzer-berg.xodr"),
}
map_params = []
for path in maps:
    if path in scenario_test_exclusions:
        continue
    if path in badmaps:
        param = pytest.param(
            badmap,
            marks=pytest.mark.xfail(
                reason="unsolved bug in geometry calculations", strict=True
            ),
        )
    else:
        param = path
    map_params.append(param)


@pytest.fixture(scope="session")
def cached_maps(tmpdir_factory):
    folder = tmpdir_factory.mktemp("maps")
    paths = {}
    for localMap in maps:
        newPath = folder.join(localMap)
        os.makedirs(newPath.dirname, exist_ok=True)
        shutil.copyfile(localMap, newPath)
        paths[localMap] = newPath
    return paths


@pytest.fixture(scope="session")
def network(cached_maps, pytestconfig):
    if pytestconfig.getoption("--fast", False):
        path = mapFolder / "CARLA" / "Town01.xodr"
    else:
        path = mapFolder / "CARLA" / "Town03.xodr"
    path = cached_maps[str(path)]
    return Network.fromFile(path)
