"""Level 7, step 1: flood and flooded cropland per district, from the saved maps.

A province total tells nobody where to send help. This splits the Level 4
flood maps (peak 14 Oct 2020, and still flooded on 1 Nov) by district, for all
three methods, so the report can give each district a best estimate and a
range.

Districts: geoBoundaries KHM ADM2 (source Open Development Cambodia, 2014,
CC BY 4.0), the 9 districts of Banteay Meanchey, saved as
data/aoi/banteay_meanchey_adm2.geojson.

Outputs: results/level7/districts.{csv,json}
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
from mfi import catalog, experiments, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import CACHE, MAPS, METHODS, SUFFIX, aoi_grid  # noqa: E402
from level5_change_detection import PEAK, POST  # noqa: E402

DISTRICTS = catalog.DATA / "aoi" / "banteay_meanchey_adm2.geojson"
OUT = experiments.RESULTS / "level7"


def read(path):
    with rasterio.open(path) as src:
        return src.read(1) == 1


def main():
    grid, inside = aoi_grid()
    px_km2 = abs(grid.transform.a) ** 2 / 1e6
    land = np.load(CACHE / f"ancillary{SUFFIX}.npz")["land"]
    crop = land == strata.CROPLAND
    d = gpd.read_file(DISTRICTS).to_crs(grid.crs).sort_values("shapeName").reset_index(drop=True)
    dist = rasterize(((g, i + 1) for i, g in enumerate(d.geometry)), out_shape=inside.shape,
                     transform=grid.transform, dtype="uint8")
    dist = np.where(inside, dist, 0)
    unassigned = inside & (dist == 0)

    maps = {m: {"peak": read(MAPS / f"flood_{m}_{PEAK}{SUFFIX}.tif"),
                "post": read(MAPS / f"flood_{m}_{POST}{SUFFIX}.tif")} for m in METHODS}

    rows = []
    for i, name in enumerate(d["shapeName"]):
        z = dist == i + 1
        r = {"district": name, "area_km2": round(z.sum() * px_km2, 1),
             "cropland_km2": round((z & crop).sum() * px_km2, 1)}
        for m in METHODS:
            r[f"flood_{m}"] = round((z & maps[m]["peak"]).sum() * px_km2, 1)
            r[f"flood_cropland_{m}"] = round((z & crop & maps[m]["peak"]).sum() * px_km2, 1)
            r[f"flood_cropland_post_{m}"] = round((z & crop & maps[m]["post"]).sum() * px_km2, 1)
        rows.append(r)

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "districts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    totals = {k: round(sum(r[k] for r in rows), 1) for k in rows[0] if k != "district"}
    with open(OUT / "districts.json", "w") as f:
        json.dump({"peak": PEAK, "post": POST, "res_m": abs(grid.transform.a),
                   "districts_source": "geoBoundaries KHM ADM2 (Open Development Cambodia 2014, CC BY 4.0)",
                   "unassigned_km2": round(unassigned.sum() * px_km2, 2),
                   "totals": totals, "districts": rows}, f, indent=2)

    sel = "unet_vvvh_cropw"
    print(f"{'district':18s} {'crop km2':>8s} {'flooded crop (thr / vv / sel)':>30s} {'% crop':>7s} {'1 Nov':>6s}")
    for r in sorted(rows, key=lambda r: -r[f"flood_cropland_{sel}"]):
        print(f"{r['district']:18s} {r['cropland_km2']:8.0f} "
              f"{r['flood_cropland_otsu_vh_global']:9.0f} / {r['flood_cropland_unet_vv_ce']:6.0f} / "
              f"{r[f'flood_cropland_{sel}']:6.0f} {100 * r[f'flood_cropland_{sel}'] / r['cropland_km2']:6.1f}% "
              f"{r[f'flood_cropland_post_{sel}']:6.0f}")
    print(f"\ntotals: {totals}\nunassigned (province edge vs district edge): {unassigned.sum() * px_km2:.2f} km2")


if __name__ == "__main__":
    main()
