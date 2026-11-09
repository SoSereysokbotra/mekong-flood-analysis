"""Fast unit tests for flood check logic (no data, no torch, no network)."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from mfi.check import (
    CheckError,
    Region,
    check_flood,
    compute_flood,
    compute_verdicts,
    key,
    parse_date,
    pass_nearest,
    pass_on_or_before,
)


def test_compute_flood_rule():
    # 5 test pixels:
    # 0: new flood (water now, dry before, valid) -> flood
    # 1: permanent/pre-existing water (water now, water before, valid) -> not flood
    # 2: dry (dry now, dry before, valid) -> not flood
    # 3: receding water (dry now, water before, valid) -> not flood
    # 4: new water but invalid/outside AOI (water now, dry before, invalid) -> not flood
    water_now = np.array([True, True, False, False, True])
    water_pre = np.array([False, True, False, True, False])
    ok = np.array([True, True, True, True, False])

    flood = compute_flood(water_now, water_pre, ok)
    expected = np.array([True, False, False, False, False])
    np.testing.assert_array_equal(flood, expected)


def test_compute_flood_2d_grid():
    water_now = np.array([[True, True], [False, False]])
    water_pre = np.array([[False, True], [False, True]])
    ok = np.array([[True, True], [True, True]])

    flood = compute_flood(water_now, water_pre, ok)
    expected = np.array([[True, False], [False, False]])
    np.testing.assert_array_equal(flood, expected)


def test_parse_date_accepts_standard_and_unpadded_dates():
    assert parse_date("2026-09-29") == dt.date(2026, 9, 29)
    assert parse_date("2026-9-29") == dt.date(2026, 9, 29)
    assert parse_date("2026-10-4") == dt.date(2026, 10, 4)
    assert parse_date(" 2026-09-26 ") == dt.date(2026, 9, 26)


def test_parse_date_none_returns_today():
    assert parse_date(None) == dt.date.today()


def test_parse_date_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Cannot read the date"):
        parse_date("not-a-date")
    with pytest.raises(ValueError, match="Cannot read the date"):
        parse_date("2026/09/29")
    with pytest.raises(ValueError, match="Cannot read the date"):
        parse_date("29-09-2026")


def test_key_normalization():
    assert key("Banteay Meanchey") == "banteaymeanchey"
    assert key("Banteay Meanchey Province") == "banteaymeanchey"
    assert key("Battambang") == "battambang"
    assert key("Siem Reap Province") == "siemreap"


def test_pass_nearest_tie_goes_to_earlier_pass(monkeypatch):
    import mfi.check

    # Fake passes returning two equidistant passes (2 days before, 2 days after)
    monkeypatch.setattr(
        mfi.check,
        "passes",
        lambda region, start, end: {"2026-10-02": "sentinel-1a", "2026-10-06": "sentinel-1a"},
    )
    # Day Oct 4 is exactly 2 days from Oct 2 and 2 days from Oct 6.
    # Ties go to the earlier pass deterministically.
    res = pass_nearest(None, dt.date(2026, 10, 4))
    assert res == ("2026-10-02", "sentinel-1a")


def test_pass_nearest_selects_closest_pass(monkeypatch):
    import mfi.check

    monkeypatch.setattr(
        mfi.check,
        "passes",
        lambda region, start, end: {"2026-10-02": "sentinel-1a", "2026-10-06": "sentinel-1b"},
    )
    # Day Oct 5 is 3 days from Oct 2 and 1 day from Oct 6 -> Oct 6 chosen
    assert pass_nearest(None, dt.date(2026, 10, 5)) == ("2026-10-06", "sentinel-1b")


def test_pass_nearest_and_on_or_before_empty(monkeypatch):
    import mfi.check

    monkeypatch.setattr(mfi.check, "passes", lambda region, start, end: {})
    assert pass_nearest(None, dt.date(2026, 10, 4)) is None
    assert pass_on_or_before(None, dt.date(2026, 10, 4)) is None


def test_compute_verdicts():
    # Model "unet_vvvh_cropw": baseline median = 100 km2
    base = {
        "2025": {"methods": {"unet_vvvh_cropw": {"flood_cropland_km2": 90.0},
                             "otsu_vh_global": {"flood_cropland_km2": 50.0},
                             "unet_vv_ce": {"flood_cropland_km2": 80.0}}},
        "2024": {"methods": {"unet_vvvh_cropw": {"flood_cropland_km2": 100.0},
                             "otsu_vh_global": {"flood_cropland_km2": 60.0},
                             "unet_vv_ce": {"flood_cropland_km2": 90.0}}},
        "2023": {"methods": {"unet_vvvh_cropw": {"flood_cropland_km2": 110.0},
                             "otsu_vh_global": {"flood_cropland_km2": 70.0},
                             "unet_vv_ce": {"flood_cropland_km2": 100.0}}},
    }

    # Case 1: Unusual flooding (> 2.0x median and > 50 km2)
    now_unusual = {
        "methods": {
            "unet_vvvh_cropw": {"flood_cropland_km2": 250.0},
            "otsu_vh_global": {"flood_cropland_km2": 40.0},
            "unet_vv_ce": {"flood_cropland_km2": 150.0},
        }
    }
    v = compute_verdicts(now_unusual, base)
    assert v["unet_vvvh_cropw"]["verdict"] == "UNUSUAL FLOODING"
    assert v["unet_vvvh_cropw"]["ratio"] == 2.5
    # otsu is 40 km2 (below 50 km2 threshold)
    assert v["otsu_vh_global"]["verdict"] == "NORMAL FOR THE SEASON"
    # unet_vv_ce is 150 km2 vs median 90 km2 (1.67x, below 2.0x ratio)
    assert v["unet_vv_ce"]["verdict"] == "NORMAL FOR THE SEASON"

    # Case 2: No baseline years -> verdict is None
    v_nobase = compute_verdicts(now_unusual, {})
    assert v_nobase["unet_vvvh_cropw"]["verdict"] is None
    assert v_nobase["unet_vvvh_cropw"]["baseline_median_km2"] is None


def test_check_flood_future_date_raises_check_error(monkeypatch):
    import mfi.check

    # Mock pass_on_or_before so no remote network/STAC call occurs
    monkeypatch.setattr(mfi.check, "pass_on_or_before", lambda region, day, window=13: ("2026-10-02", "sentinel-1a"))
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    with pytest.raises(CheckError, match="is in the future"):
        check_flood(date=future)


def test_check_flood_invalid_date_raises_check_error():
    with pytest.raises(CheckError, match="Cannot read the date"):
        check_flood(date="2026-99-99")


def test_region_unknown_province_raises_check_error():
    with pytest.raises(CheckError, match="Unknown province"):
        Region("Atlantis")
