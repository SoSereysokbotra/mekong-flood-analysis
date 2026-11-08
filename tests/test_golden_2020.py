"""Golden test: the 14 Oct 2020 Banteay Meanchey flood areas must not change.

Re-runs the three methods on the cached radar (26 Sep and 14 Oct 2020, track 164)
and compares with results/level4/change_detection.json: 882 / 1,131 / 1,218 km2.
Needs the local radar cache and model checkpoints, so it is marked `slow` and
skips itself where they are missing (e.g. on GitHub Actions).
"""
import json

import pytest

from mfi import experiments

pytestmark = pytest.mark.slow
TOL_KM2 = 0.1     # check_flood rounds to 0.1 km2


@pytest.fixture(scope="module")
def result():
    pytest.importorskip("torch")
    import check_flood
    from level4_cambodia import CACHE, METHODS, aoi_grid
    from level5_change_detection import PEAK, PRE

    need = [CACHE / f"s1_{PRE}.npz", CACHE / f"s1_{PEAK}.npz", CACHE / "ancillary.npz"]
    need += [experiments.run_dir(experiments.level3_dir(), m) / "best.pt" for m in METHODS if m.startswith("unet")]
    missing = [str(p) for p in need if not p.exists()]
    if missing:
        pytest.skip(f"local cache or checkpoints missing: {missing}")
    check_flood.REGION = None                        # the study province, original grid and cache
    grid, inside = aoi_grid()
    from level4_cambodia import ancillary
    land, _, slope = ancillary(grid)
    return check_flood.flood_pair(check_flood.Predictor(slope), grid, inside, land, PRE, PEAK)["methods"]


@pytest.mark.parametrize("method,km2", [("otsu_vh_global", 882), ("unet_vv_ce", 1131), ("unet_vvvh_cropw", 1218)])
def test_flood_area_matches_the_published_level4_numbers(result, method, km2):
    with open(experiments.RESULTS / "level4" / "change_detection.json") as f:
        ref = json.load(f)["methods"][method]
    assert round(ref["flood_peak_km2"]) == km2                     # the file still says what the docs say
    assert result[method]["flood_km2"] == pytest.approx(ref["flood_peak_km2"], abs=TOL_KM2)
    assert result[method]["flood_cropland_km2"] == pytest.approx(ref["flood_peak_cropland_km2"], abs=TOL_KM2)
