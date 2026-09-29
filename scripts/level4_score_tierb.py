"""Score the three Level 4 methods against the Tier B hand labels.

This is the measurement the project was built for: the models judged on
Cambodian ground, at rice-ripening stage, against labels a human confirmed.

Two comparisons, because the maps answer two different questions:
    TOTAL WATER   <method>_<date>.tif        vs labels of class 1, 2 or 3
    NEW FLOOD     flood_<method>_<date>.tif  vs labels of class 1 or 2 only
                                             (class 3 is permanent water, which
                                              the flood map removes by design)
Scoring the flood map against labels that include permanent water would count
every reservoir as a miss.

Scoring rules, from the protocol:
  - only inside the labelling tiles that were reviewed
  - a pixel is WATER if it falls in a qualifying polygon with confidence >= 2
  - a pixel is IGNORED if it falls in a class -1 polygon (cloud, or the labeller
    was unsure), or in a candidate the labeller never reached
  - every other pixel in a reviewed tile is DRY

What these labels can and cannot test: they were seeded from an optical water
index, so they cannot contain water that optical could not see -- which is
precisely the flooded-vegetation case this project is about. Recall on flooded
vegetation is therefore NOT a fair test here; precision and open water are.

Outputs: results/level4/tierb_scores.{csv,json}
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, metrics  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import CACHE, MAPS, METHODS, SUFFIX, aoi_grid  # noqa: E402
from level5_change_detection import PEAK  # noqa: E402

GPKG = catalog.DATA / "labels" / "tierB_bmc_oct2020.gpkg"
MIN_CONFIDENCE = 2
GROUPS = ("all", "cropland", "vegetation", "open_water", "built")


def main():
    grid, inside = aoi_grid()
    labels = gpd.read_file(GPKG, layer="flood").to_crs(grid.crs)
    tiles = gpd.read_file(GPKG, layer="tiles").to_crs(grid.crs)
    land = np.load(CACHE / f"ancillary{SUFFIX}.npz")["land"]

    confirmed = labels[labels["confidence"] >= MIN_CONFIDENCE]
    ignore = labels[(labels["class"] == -1) | (labels["confidence"] < MIN_CONFIDENCE)]
    reviewed = sorted(set(confirmed["tile_id"]) | set(ignore["tile_id"]))
    print(f"{len(confirmed)} confirmed polygons, {len(ignore)} ignored areas, {len(reviewed)} tiles reviewed")

    shape = (grid.height, grid.width)
    px_km2 = (abs(grid.transform.a) ** 2) / 1e6
    in_tiles = rasterize(((g, 1) for g in tiles[tiles["tile_id"].isin(reviewed)].geometry),
                         out_shape=shape, transform=grid.transform, dtype="uint8").astype(bool)
    ign = (rasterize(((g, 1) for g in ignore.geometry), out_shape=shape, transform=grid.transform,
                     dtype="uint8").astype(bool) if len(ignore) else np.zeros(shape, bool))

    def label_for(classes):
        sel = confirmed[confirmed["class"].isin(classes)]
        lab = (rasterize(((g, 1) for g in sel.geometry), out_shape=shape, transform=grid.transform,
                         dtype="uint8").astype(np.int8) if len(sel) else np.zeros(shape, np.int8))
        return np.where(in_tiles & ~ign, lab, -1).astype(np.int8)

    comparisons = {
        "total_water": (label_for([1, 2, 3]), lambda m: MAPS / f"{m}_{PEAK}{SUFFIX}.tif"),
        "new_flood": (label_for([1, 2]), lambda m: MAPS / f"flood_{m}_{PEAK}{SUFFIX}.tif"),
    }

    rows, out = [], {"min_confidence": MIN_CONFIDENCE, "tiles_reviewed": reviewed, "comparisons": {}}
    for cname, (label, path_of) in comparisons.items():
        n_pos, n_neg = int((label == 1).sum()), int((label == 0).sum())
        out["comparisons"][cname] = {"water_px": n_pos, "dry_px": n_neg,
                                     "water_km2": round(n_pos * px_km2, 2), "methods": {}}
        print(f"\n{cname}: {n_pos:,} water px ({n_pos * px_km2:.2f} km2), {n_neg:,} dry px, "
              f"{int((in_tiles & ign).sum()):,} ignored")
        for method in METHODS:
            with rasterio.open(path_of(method)) as src:
                pred = src.read(1) == 1
            m = metrics.Confusion().add(pred, label, land).metrics()
            out["comparisons"][cname]["methods"][method] = {
                g: {k: m[g][k] for k in ("iou", "recall", "precision", "tp", "fp", "fn", "n_pos")} for g in GROUPS}
            for g in GROUPS:
                rows.append({"comparison": cname, "method": method, "group": g,
                             **{k: m[g][k] for k in ("iou", "recall", "precision", "tp", "fp", "fn", "n_pos")}})
            experiments.log_row("level4", f"tierb_{cname}_{method}", "tierb", method,
                                {"labels": "Tier B confirmed", "comparison": cname,
                                 "min_confidence": MIN_CONFIDENCE, "date": PEAK},
                                len(reviewed), m, note=f"Tier B hand labels, {cname}")

    d = experiments.RESULTS / "level4"
    with open(d / f"tierb_scores{SUFFIX}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(d / f"tierb_scores{SUFFIX}.json", "w") as f:
        json.dump(out, f, indent=2)

    for cname in comparisons:
        print(f"\n== {cname}")
        print(f"{'method':17s} {'IoU':>6s} {'recall':>7s} {'prec':>6s} | "
              f"{'crop IoU':>8s} {'crop rec':>8s} {'crop prec':>9s}")
        for method in METHODS:
            mm = out["comparisons"][cname]["methods"][method]
            a, c = mm["all"], mm["cropland"]
            print(f"{method:17s} {a['iou']:6.3f} {a['recall']:7.3f} {a['precision']:6.3f} | "
                  f"{c['iou']:8.3f} {c['recall']:8.3f} {c['precision']:9.3f}")
    print("\nCAVEAT: the labels were seeded from an optical water index, so they cannot contain"
          "\nwater that optical could not see. Recall on flooded vegetation is not a fair test"
          "\nhere; precision and open water are.")


if __name__ == "__main__":
    main()
