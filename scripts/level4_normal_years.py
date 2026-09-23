"""Is the October 2020 extent a flood, or is that just what a wet-season paddy
looks like in October?

Runs the identical pipeline on the same track (164 descending), the same
models, the same processing and the same ~2.5-week gap, for the years around
the event. Every pass listed below covers 100 % of the province.

    year   pre        mid-October    note
    2018   09-25      10-13
    2019   09-26      10-14          same day of year as the event
    2020   09-26      10-14          THE EVENT
    2021   09-27      10-15
    2022   09-28      10-10          12-day gap: S1B failed in Dec 2021

For each year: water on the October date, and "flood" = October water that was
not water on the September date. If the non-event years show a similar extent,
most of what Level 4 maps is ordinary ponded paddy and only the excess is the
disaster. If they are much smaller, the 2020 extent is genuinely anomalous.

Nothing here is tuned or selected; it is the same code applied to more dates.

Outputs: results/level4/normal_years.{csv,json}
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import experiments, infer, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import METHODS, SUFFIX, ancillary, aoi_grid, s1_on_aoi  # noqa: E402

YEARS = {
    2018: ("2018-09-25", "2018-10-13"),
    2019: ("2019-09-26", "2019-10-14"),
    2020: ("2020-09-26", "2020-10-14"),
    2021: ("2021-09-27", "2021-10-15"),
    2022: ("2022-09-28", "2022-10-10"),
}
EVENT_YEAR = 2020


def main():
    grid, inside = aoi_grid()
    px_km2 = (abs(grid.transform.a) ** 2) / 1e6
    land, jrc, slope = ancillary(grid)
    unets = {m: infer.load_unet(m) for m in METHODS if m.startswith("unet")}

    rows, summary = [], {"track": "164 descending", "res_m": abs(grid.transform.a),
                         "aoi_km2": float(inside.sum() * px_km2), "years": {}}
    for year, (pre_date, oct_date) in YEARS.items():
        print(f"\n=== {year}  pre {pre_date}  october {oct_date}", flush=True)
        pre_s1 = s1_on_aoi(pre_date, grid)
        oct_s1 = s1_on_aoi(oct_date, grid)
        ok = np.isfinite(pre_s1).all(axis=0) & np.isfinite(oct_s1).all(axis=0) & inside
        summary["years"][str(year)] = {"pre_date": pre_date, "october_date": oct_date,
                                  "gap_days": int((np.datetime64(oct_date) - np.datetime64(pre_date)).astype(int)),
                                  "coverage_frac": float(ok.sum() / inside.sum()), "methods": {}}
        for method in METHODS:
            def predict(s1):
                ch = {"vv": s1[0], "vh": s1[1], "ratio": s1[0] - s1[1], "slope": slope}
                if method == "otsu_vh_global":
                    return infer.predict_threshold(ch, "vh") == 1
                model, channels, norm, device = unets[method]
                return infer.predict_unet(model, channels, norm, device, ch) == 1

            w_pre, w_oct = predict(pre_s1) & ok, predict(oct_s1) & ok
            flood = w_oct & ~w_pre
            s = {"water_pre_km2": float(w_pre.sum() * px_km2),
                 "water_october_km2": float(w_oct.sum() * px_km2),
                 "flood_km2": float(flood.sum() * px_km2),
                 "flood_cropland_km2": float((flood & (land == strata.CROPLAND)).sum() * px_km2),
                 "flood_vegetation_km2": float((flood & (land == strata.VEGETATION)).sum() * px_km2)}
            summary["years"][str(year)]["methods"][method] = s
            rows.append({"year": int(year), "method": method, "pre_date": pre_date, "october_date": oct_date, **s})
            print(f"  {method:16s} water pre {s['water_pre_km2']:6,.0f} | october {s['water_october_km2']:6,.0f} "
                  f"| flood {s['flood_km2']:6,.0f} km2 (cropland {s['flood_cropland_km2']:6,.0f})", flush=True)

    # the comparison this script exists for
    print(f"\n{'method':16s} " + " ".join(f"{y:>8d}" for y in YEARS) + "   excess 2020 vs median of other years")
    for method in METHODS:
        vals = {y: summary["years"][str(y)]["methods"][method]["flood_cropland_km2"] for y in YEARS}
        others = [v for y, v in vals.items() if y != EVENT_YEAR]
        med = float(np.median(others))
        excess = vals[EVENT_YEAR] - med
        summary.setdefault("excess_2020_cropland_km2", {})[method] = {
            "event": vals[EVENT_YEAR], "median_other_years": med, "excess_km2": excess,
            "ratio": vals[EVENT_YEAR] / med if med else float("inf")}
        tail = f"   {excess:+,.0f} km2 ({vals[EVENT_YEAR] / med:.1f}x median {med:,.0f})" if med else "   (no baseline)"
        print(f"{method:16s} " + " ".join(f"{vals[y]:8,.0f}" for y in YEARS) + tail)

    out = experiments.RESULTS / "level4"
    with open(out / f"normal_years{SUFFIX}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out / f"normal_years{SUFFIX}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {out / f'normal_years{SUFFIX}.csv'} and .json")


if __name__ == "__main__":
    main()
