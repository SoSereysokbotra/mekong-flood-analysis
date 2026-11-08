"""Land types: every score is reported per land type, so the mapping must be exact."""
import numpy as np

from mfi import strata


def test_worldcover_codes_map_to_the_documented_land_types():
    wc = np.array([80, 40, 10, 20, 30, 90, 95, 50, 60, 70, 100, 0], np.uint8)
    want = [strata.OPEN_WATER, strata.CROPLAND] + [strata.VEGETATION] * 5 + [strata.BUILT] + [strata.OTHER] * 3 \
        + [strata.UNKNOWN]
    assert strata.land_type(wc).tolist() == want


def test_unexpected_code_is_unknown_never_a_real_class():
    assert strata.land_type(np.array([255, 41, 1])).tolist() == [strata.UNKNOWN] * 3


def test_every_pixel_gets_a_land_type():
    wc = np.random.default_rng(0).choice([0, 10, 40, 50, 80, 255], size=(50, 50))
    lt = strata.land_type(wc)
    assert lt.dtype == np.int8 and lt.shape == wc.shape
    assert set(np.unique(lt)) <= set(strata.LAND_NAMES)


def test_counts_split_flood_dry_and_ignore():
    label = np.array([1, 0, -1, 1, 0])
    land = np.array([strata.CROPLAND, strata.CROPLAND, strata.CROPLAND, strata.BUILT, strata.BUILT])
    c = strata.counts(label, land)
    assert c["ignore"] == 1
    assert (c["flood_cropland"], c["dry_cropland"], c["flood_built"], c["dry_built"]) == (1, 1, 1, 1)
    assert set(c) == set(strata.COUNT_KEYS)
    assert sum(c.values()) == label.size
