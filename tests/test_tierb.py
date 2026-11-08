"""Tier B: which tiles are scored, and the SCL sensitivity mask."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from mfi import io, tierb

CRS = rasterio.crs.CRS.from_epsg(32648)


def write_scl(path, arr, x0=300000.0, y0=1500000.0, res=10.0):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="uint8", crs=CRS, transform=from_origin(x0, y0, res, res)) as d:
        d.write(arr.astype(np.uint8), 1)
    return path


def test_clear_tile_is_scored_even_with_no_polygons(tmp_path):
    # the 2026 bug: a clear tile with no candidate used to be dropped
    p = write_scl(tmp_path / "a.tif", np.full((20, 20), 4))
    assert tierb.tiles_to_score({"A": p}) == (["A"], {})


def test_missing_scene_is_skipped_with_a_reason(tmp_path):
    scored, skipped = tierb.tiles_to_score({"A": None, "B": tmp_path / "nope.tif"})
    assert scored == [] and skipped == {"A": "no event scene", "B": "no event scene"}


def test_almost_empty_scene_is_skipped(tmp_path):
    # the 2020 BMC_CROP_18 case: 98 % no data
    a = np.zeros((50, 50))
    a[:1, :] = 4
    p = write_scl(tmp_path / "a.tif", a)
    scored, skipped = tierb.tiles_to_score({"A": p})
    assert scored == [] and "98% no data" in skipped["A"]


def test_partly_empty_scene_stops_the_run(tmp_path):
    a = np.full((20, 20), 4)
    a[0, 0] = 0                                     # one no-data pixel would count as dry
    with pytest.raises(ValueError, match="no data"):
        tierb.tiles_to_score({"A": write_scl(tmp_path / "a.tif", a)})


def test_cloudy_tile_is_still_scored(tmp_path):
    # cloud is handled by the cloud polygons, not by dropping the tile
    a = np.full((20, 20), 9)
    a[:5] = 4
    assert tierb.tiles_to_score({"A": write_scl(tmp_path / "a.tif", a)})[0] == ["A"]


def test_scl_mask_lands_on_the_right_pixels(tmp_path):
    a = np.full((20, 20), 4)
    a[:10, :10] = 2                                  # top-left quarter is "dark area"
    p = write_scl(tmp_path / "a.tif", a)
    grid = io.Grid(CRS, from_origin(300000.0, 1500000.0, 20.0, 20.0), 10, 10)   # 20 m grid, same corner
    m = tierb.scl_mask({"A": p}, ["A"], grid, (1, 2))
    assert m[:5, :5].all() and not m[5:, :].any() and not m[:, 5:].any()
