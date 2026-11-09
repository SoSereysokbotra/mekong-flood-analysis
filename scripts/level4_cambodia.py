"""Level 4: apply the Level 1 threshold and the two Level 3 v1.1 models to
Banteay Meanchey, October 2020, on the pipeline they were trained on.

Scenes: Sentinel-1 RTC, track 164 descending (the only track with full province
coverage that also passes on the flood peak):
    2020-09-26  pre-event reference
    2020-10-14  peak
    2020-11-01  post-event

For each date and method this writes a flood map on a 20 m grid over the
province, and per-date areas split by land type and by JRC permanent water
(Tier D): total water, permanent water, and *new* water = detected water that
is not permanent. Areas are computed in EPSG:32648 (metres), not in degrees.

Outputs:
    data/interim/level4/s1_<date>.npz          VV/VH dB on the AOI grid (cached)
    results/level4/maps/<method>_<date>.tif    int8 flood map (1 water, 0 dry, -1 no data)
    results/level4/areas.csv                   one row per (method, date, land type)
    results/level4/areas.json                  summary incl. Tier D split

No hand labels exist yet, so nothing here is scored; this is the map and its
areas. Scoring happens once Tier B labels are drawn.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import experiments, infer, strata  # noqa: E402
from mfi.aoi import (  # noqa: F401
    AOI_EPSG,
    CACHE,
    METHODS,
    RES_M,
    SUFFIX,
    ancillary,
    aoi_grid,
    s1_on_aoi,
    write_map,
)

DATES = {"2020-09-26": "pre", "2020-10-14": "peak", "2020-11-01": "post"}
MAPS = experiments.RESULTS / "level4" / "maps"
JRC_PERMANENT = 80    # JRC occurrence >= 80% of observations -> permanent water


def main():
    grid, inside = aoi_grid()
    px_km2 = (RES_M ** 2) / 1e6
    print(f"AOI grid {grid.height} x {grid.width} at {RES_M:.0f} m; province {inside.sum() * px_km2:,.0f} km2")
    land, jrc, slope = ancillary(grid)
    permanent = jrc >= JRC_PERMANENT
    print(f"JRC permanent water in province: {(permanent & inside).sum() * px_km2:,.0f} km2")

    unets = {m: infer.load_unet(m) for m in METHODS if m.startswith("unet")}
    rows, summary = [], {"res_m": RES_M, "aoi_km2": float(inside.sum() * px_km2),
                         "jrc_permanent_km2": float((permanent & inside).sum() * px_km2),
                         "jrc_threshold_pct": JRC_PERMANENT, "dates": {}, "methods": {}}

    for date, role in DATES.items():
        s1 = s1_on_aoi(date, grid)
        ch = {"vv": s1[0], "vh": s1[1], "ratio": s1[0] - s1[1], "slope": slope}
        valid = np.isfinite(s1).all(axis=0) & inside
        summary["dates"][date] = {"role": role, "coverage_frac_of_province": float(valid.sum() / inside.sum())}
        print(f"\n{date} ({role}): radar covers {100 * valid.sum() / inside.sum():.1f}% of the province")
        for method in METHODS:
            if method == "otsu_vh_global":
                pred = infer.predict_threshold(ch, "vh")
            else:
                model, channels, norm, device = unets[method]
                pred = infer.predict_unet(model, channels, norm, device, ch)
            pred[~inside] = infer.NODATA
            write_map(MAPS / f"{method}_{date}{SUFFIX}.tif", pred, grid)
            water = pred == 1
            new_water = water & ~permanent
            summary["methods"].setdefault(method, {})[date] = {
                "water_km2": float(water.sum() * px_km2),
                "new_water_km2": float(new_water.sum() * px_km2),
                "permanent_detected_km2": float((water & permanent).sum() * px_km2),
                "new_water_cropland_km2": float((new_water & (land == strata.CROPLAND)).sum() * px_km2),
                "new_water_vegetation_km2": float((new_water & (land == strata.VEGETATION)).sum() * px_km2),
                "new_water_built_km2": float((new_water & (land == strata.BUILT)).sum() * px_km2),
            }
            for lt, name in strata.LAND_NAMES.items():
                m = new_water & (land == lt)
                rows.append({"method": method, "date": date, "role": role, "land_type": name,
                             "new_water_km2": float(m.sum() * px_km2),
                             "land_type_km2": float(((land == lt) & valid).sum() * px_km2)})
            s = summary["methods"][method][date]
            print(f"  {method:16s} water {s['water_km2']:7,.0f} km2 | new {s['new_water_km2']:7,.0f} "
                  f"(cropland {s['new_water_cropland_km2']:6,.0f}, vegetation {s['new_water_vegetation_km2']:5,.0f}, built {s['new_water_built_km2']:4,.0f})")

    out = experiments.RESULTS / "level4"
    with open(out / f"areas{SUFFIX}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out / f"areas{SUFFIX}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {out / 'areas.csv'} and areas.json; maps in {MAPS}")


if __name__ == "__main__":
    main()
