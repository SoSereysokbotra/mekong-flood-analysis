"""Level 5 (and the honest version of the Level 4 area): separate the flood
from water that was already there.

"New water" in level4_cambodia.py means "detected water that JRC does not call
permanent". In Banteay Meanchey JRC permanent water is only 10 km2, so that
subtraction removes almost nothing -- and in October a wet-season rice paddy is
deliberately under water. Reported flood extent must therefore be:

    flood = water(peak) AND NOT water(pre-event)

with the pre-event pass on the same track and the same processing, so the two
maps are directly comparable. Recession is the same subtraction on the post
date, and the difference between them is how much water drained.

Inputs:  results/level4/maps/<method>_<date>.tif (from level4_cambodia.py,
         locally or unzipped from data/colab/level4_maps.zip)
Outputs: results/level4/maps/flood_<method>_<date>.tif   1 = new flood, 0 = not,
                                                          -1 = no data either date
         results/level4/change_detection.csv / .json
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import zipfile

import numpy as np
import rasterio

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import CACHE, JRC_PERMANENT, MAPS, METHODS, SUFFIX, aoi_grid  # noqa: E402

PRE, PEAK, POST = "2020-09-26", "2020-10-14", "2020-11-01"
MAPS_ZIP = catalog.DATA / "colab" / "level4_maps.zip"


def ensure_maps():
    if any(MAPS.glob(f"*_{PEAK}{SUFFIX}.tif")):
        return
    if not MAPS_ZIP.exists():
        sys.exit(f"no maps in {MAPS} and no {MAPS_ZIP}.\n"
                 "Download level4_maps.zip from Google Drive (MyDrive/mfi/) into data/colab/.")
    with zipfile.ZipFile(MAPS_ZIP) as z:
        z.extractall(experiments.RESULTS / "level4")
    print(f"unzipped {MAPS_ZIP.name}")


def read_map(method: str, date: str) -> np.ndarray:
    with rasterio.open(MAPS / f"{method}_{date}{SUFFIX}.tif") as src:
        return src.read(1)


def main():
    ensure_maps()
    grid, inside = aoi_grid()
    px_km2 = (abs(grid.transform.a) ** 2) / 1e6
    z = np.load(CACHE / f"ancillary{SUFFIX}.npz")
    land, jrc = z["land"], z["jrc"]
    permanent = jrc >= JRC_PERMANENT

    rows, summary = [], {"pre": PRE, "peak": PEAK, "post": POST, "res_m": abs(grid.transform.a),
                         "aoi_km2": float(inside.sum() * px_km2), "methods": {}}
    for method in METHODS:
        pre, peak, post = (read_map(method, d) for d in (PRE, PEAK, POST))
        ok = (pre >= 0) & (peak >= 0) & (post >= 0) & inside
        w_pre, w_peak, w_post = pre == 1, peak == 1, post == 1
        flood_peak = w_peak & ~w_pre & ok        # new since the pre-event pass
        flood_post = w_post & ~w_pre & ok
        drained = flood_peak & ~flood_post

        for tag, m in (("peak", flood_peak), ("post", flood_post)):
            with rasterio.open(MAPS / f"{method}_{PEAK if tag == 'peak' else POST}{SUFFIX}.tif") as src:
                prof = src.profile
            out = np.where(ok, m.astype(np.int8), np.int8(-1))
            with rasterio.open(MAPS / f"flood_{method}_{PEAK if tag == 'peak' else POST}{SUFFIX}.tif", "w", **prof) as dst:
                dst.write(out, 1)

        s = {
            "water_pre_km2": float((w_pre & ok).sum() * px_km2),
            "water_peak_km2": float((w_peak & ok).sum() * px_km2),
            "flood_peak_km2": float(flood_peak.sum() * px_km2),
            "flood_peak_cropland_km2": float((flood_peak & (land == strata.CROPLAND)).sum() * px_km2),
            "flood_peak_vegetation_km2": float((flood_peak & (land == strata.VEGETATION)).sum() * px_km2),
            "flood_peak_built_km2": float((flood_peak & (land == strata.BUILT)).sum() * px_km2),
            "flood_post_km2": float(flood_post.sum() * px_km2),
            "flood_post_cropland_km2": float((flood_post & (land == strata.CROPLAND)).sum() * px_km2),
            "drained_by_post_km2": float(drained.sum() * px_km2),
            "pre_water_on_cropland_km2": float((w_pre & ok & (land == strata.CROPLAND)).sum() * px_km2),
            "permanent_km2": float((permanent & ok).sum() * px_km2),
        }
        summary["methods"][method] = s
        for lt, name in strata.LAND_NAMES.items():
            rows.append({"method": method, "land_type": name,
                         "flood_peak_km2": float((flood_peak & (land == lt)).sum() * px_km2),
                         "flood_post_km2": float((flood_post & (land == lt)).sum() * px_km2),
                         "water_pre_km2": float((w_pre & ok & (land == lt)).sum() * px_km2)})
        print(f"{method:16s} pre-water {s['water_pre_km2']:6,.0f} | flood at peak {s['flood_peak_km2']:6,.0f} km2 "
              f"(cropland {s['flood_peak_cropland_km2']:6,.0f}, vegetation {s['flood_peak_vegetation_km2']:5,.0f}) | "
              f"still flooded 1 Nov {s['flood_post_km2']:6,.0f} | drained {s['drained_by_post_km2']:6,.0f}")

    out_dir = experiments.RESULTS / "level4"
    with open(out_dir / f"change_detection{SUFFIX}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out_dir / f"change_detection{SUFFIX}.json", "w") as f:
        json.dump(summary, f, indent=2)

    ref = json.load(open(catalog.DATA / "reference" / "tier_e_reference.json"))
    rice = next(x for x in ref["figures"] if x["quantity"] == "rice fields inundated" and "Banteay" in x["scope"])
    print(f"\nTier E: {rice['value_ha']:,} ha rice inundated = {rice['value_km2']:.0f} km2 (province, cumulative report)")
    for m, s in summary["methods"].items():
        print(f"  {m:16s} flood on cropland at peak {s['flood_peak_cropland_km2']:6,.0f} km2  "
              f"= {s['flood_peak_cropland_km2'] / rice['value_km2']:.1f}x the reported figure")


if __name__ == "__main__":
    main()
