"""Fast unit tests for Level 7 report pure logic (no data, no torch)."""
from __future__ import annotations

from mfi.report import build_report_data, day, km, render_report_markdown, rng


def test_day_formatting():
    assert day("2020-10-14") == "14 Oct 2020"
    assert day("2020-09-01") == "1 Sep 2020"
    assert day("2026-11-05") == "5 Nov 2026"


def test_km_formatting():
    assert km(1218) == "1,218"
    assert km(1218.4) == "1,218"
    assert km(882.0) == "882"
    assert km(0) == "0"


def test_rng_formatting():
    assert rng([882, 1131, 1218]) == "882–1,218"
    assert rng([500]) == "500–500"
    assert rng([1000, 200, 500]) == "200–1,000"


def test_build_report_data():
    cd = {
        "peak": "2020-10-14",
        "pre": "2020-09-26",
        "post": "2020-11-01",
        "methods": {
            "otsu_vh_global": {
                "flood_peak_km2": 882.1,
                "flood_peak_cropland_km2": 700.1,
                "flood_peak_vegetation_km2": 150.0,
                "water_pre_km2": 100.0,
                "water_peak_km2": 982.1,
                "flood_post_cropland_km2": 300.0,
                "drained_by_post_km2": 500.0,
                "flood_post_km2": 350.0,
            },
            "unet_vv_ce": {
                "flood_peak_km2": 1131.2,
                "flood_peak_cropland_km2": 950.2,
                "flood_peak_vegetation_km2": 160.0,
                "water_pre_km2": 110.0,
                "water_peak_km2": 1241.2,
                "flood_post_cropland_km2": 400.0,
                "drained_by_post_km2": 600.0,
                "flood_post_km2": 450.0,
            },
            "unet_vvvh_cropw": {
                "flood_peak_km2": 1218.3,
                "flood_peak_cropland_km2": 1050.3,
                "flood_peak_vegetation_km2": 140.0,
                "water_pre_km2": 120.0,
                "water_peak_km2": 1338.3,
                "flood_post_cropland_km2": 500.0,
                "drained_by_post_km2": 700.0,
                "flood_post_km2": 600.0,
            },
        },
    }
    nyf = {
        "excess_2020_cropland_km2": {
            "otsu_vh_global": {"ratio": 4.1, "excess_km2": 500.0, "event": 700.1},
            "unet_vv_ce": {"ratio": 5.0, "excess_km2": 750.0, "event": 950.2},
            "unet_vvvh_cropw": {"ratio": 6.0, "excess_km2": 850.0, "event": 1050.3},
        },
        "years": {
            "2018": {
                "methods": {
                    "otsu_vh_global": {"flood_cropland_km2": 600.0},  # >= 0.8 * 700.1 -> exception!
                    "unet_vv_ce": {"flood_cropland_km2": 200.0},
                    "unet_vvvh_cropw": {"flood_cropland_km2": 250.0},
                }
            }
        },
    }
    tb = {
        "otsu_vh_global": {"cropland": {"recall": 0.553, "precision": 0.85}, "vegetation": {"precision": 0.4}},
        "unet_vv_ce": {"cropland": {"recall": 0.75, "precision": 0.84}, "vegetation": {"precision": 0.45}},
        "unet_vvvh_cropw": {"cropland": {"recall": 0.801, "precision": 0.89}, "vegetation": {"precision": 0.5}},
    }
    hw = {"cropland_dem_spread_median_m": 1.5}
    dist = {
        "totals": {"cropland_km2": 2500.0, "flood_cropland_unet_vvvh_cropw": 1000.0},
        "unassigned_km2": 12.34,
        "districts": [
            {"district": "DistA", "cropland_km2": 1000.0, "flood_cropland_unet_vvvh_cropw": 500.0,
             "flood_cropland_otsu_vh_global": 400.0, "flood_cropland_unet_vv_ce": 450.0,
             "flood_cropland_post_unet_vvvh_cropw": 200.0},
            {"district": "DistB", "cropland_km2": 800.0, "flood_cropland_unet_vvvh_cropw": 300.0,
             "flood_cropland_otsu_vh_global": 200.0, "flood_cropland_unet_vv_ce": 250.0,
             "flood_cropland_post_unet_vvvh_cropw": 100.0},
            {"district": "DistC", "cropland_km2": 500.0, "flood_cropland_unet_vvvh_cropw": 150.0,
             "flood_cropland_otsu_vh_global": 100.0, "flood_cropland_unet_vv_ce": 120.0,
             "flood_cropland_post_unet_vvvh_cropw": 50.0},
            {"district": "DistD", "cropland_km2": 200.0, "flood_cropland_unet_vvvh_cropw": 50.0,
             "flood_cropland_otsu_vh_global": 30.0, "flood_cropland_unet_vv_ce": 40.0,
             "flood_cropland_post_unet_vvvh_cropw": 20.0},
        ],
    }

    rep = build_report_data(cd, nyf, tb, hw, dist, te_val=150.0)

    assert rep["method_best"] == "unet_vvvh_cropw"
    assert rep["flood_km2"]["unet_vvvh_cropw"] == 1218.3
    # peak persisting = peak (1218.3) - drained (700.0) = 518.3
    assert rep["peak_flood_persisting_km2"] == 518.3
    # new after peak = post (600.0) - persisting (518.3) = 81.7
    assert rep["flood_new_after_peak_km2"] == 81.7
    # top 3 sum = 500 + 300 + 150 = 950; total = 1000 -> 0.95
    assert rep["top3_share"] == 0.95
    # 2018 otsu was 600 >= 0.8 * 700.1 (560.08) -> caught in normal_year_exceptions
    assert len(rep["normal_year_exceptions"]) == 1
    assert rep["normal_year_exceptions"][0]["method"] == "otsu_vh_global"
    assert rep["normal_year_exceptions"][0]["year"] == "2018"


def test_render_report_markdown():
    cd = {"peak": "2020-10-14", "pre": "2020-09-26", "post": "2020-11-01"}
    rep = {
        "flood_cropland_km2": {"unet_vvvh_cropw": 1050.0, "otsu_vh_global": 700.0, "unet_vv_ce": 950.0},
        "flood_km2": {"unet_vvvh_cropw": 1218.0, "otsu_vh_global": 882.0, "unet_vv_ce": 1131.0},
        "flood_vegetation_km2": {"unet_vvvh_cropw": 140.0},
        "water_pre_km2": {"unet_vvvh_cropw": 120.0},
        "water_peak_km2": {"unet_vvvh_cropw": 1338.0},
        "flood_cropland_post_km2": {"unet_vvvh_cropw": 500.0},
        "normal_year_ratio": {"unet_vvvh_cropw": 6.0, "otsu_vh_global": 4.1, "unet_vv_ce": 5.0},
        "normal_year_excess_km2": {"unet_vvvh_cropw": 850.0},
        "reported_rice_inundated_km2": 150.0,
        "tierb_cropland": {
            "unet_vvvh_cropw": {"recall": 0.801, "precision": 0.89},
            "otsu_vh_global": {"recall": 0.553, "precision": 0.85},
            "unet_vv_ce": {"recall": 0.75, "precision": 0.84},
        },
        "tierb_vegetation_precision": {"unet_vvvh_cropw": 0.5},
        "hidden_water": {"cropland_dem_spread_median_m": 1.5},
        "unassigned_km2": 12.0,
        "peak_flood_persisting_km2": 518.0,
        "flood_new_after_peak_km2": 82.0,
        "normal_year_exceptions": [],
        "top3_share": 0.84,
    }
    rows = [
        {"district": "Mongkol Borei", "cropland_km2": 800.0, "flood_cropland_unet_vvvh_cropw": 500.0,
         "flood_cropland_otsu_vh_global": 400.0, "flood_cropland_unet_vv_ce": 450.0,
         "flood_cropland_post_unet_vvvh_cropw": 600.0},  # 600 > 500 * 1.1 -> rising!
        {"district": "Preah Netr Preah", "cropland_km2": 700.0, "flood_cropland_unet_vvvh_cropw": 300.0,
         "flood_cropland_otsu_vh_global": 200.0, "flood_cropland_unet_vv_ce": 250.0,
         "flood_cropland_post_unet_vvvh_cropw": 100.0},
        {"district": "Serei Saophoan", "cropland_km2": 500.0, "flood_cropland_unet_vvvh_cropw": 100.0,
         "flood_cropland_otsu_vh_global": 80.0, "flood_cropland_unet_vv_ce": 90.0,
         "flood_cropland_post_unet_vvvh_cropw": 50.0},
    ]

    md = render_report_markdown(rep, rows, crop_total=2500.0, cd=cd)
    assert "# Flood report: Banteay Meanchey, October 2020" in md
    assert "Mongkol Borei" in md
    # Rising district check: Mongkol Borei was rising
    assert "In **Mongkol Borei** the flooded cropland was *larger* than at the peak" in md
    assert "Three districts hold 84 % of the flooded cropland" in md
