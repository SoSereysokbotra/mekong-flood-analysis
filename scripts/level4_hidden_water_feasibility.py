"""Can the Tier B tiles be labelled for water hidden under the rice canopy?

The Tier B labels were seeded from an optical water index, so they cannot
contain water under a closed canopy -- the case the project is about. Before
asking a labeller to add such polygons, this measures whether any free,
non-radar evidence could support them. Two candidate routes:

  TERRAIN   Low ground next to confirmed water is plausibly flooded. Needs the
            DEM to resolve height differences larger than its own noise
            (Copernicus GLO-30: ~1-2 m in flat terrain).
            Measured: elevation spread per tile, and height of green
            (canopy-covered) land within 300 m of confirmed water relative to
            that water (height of the nearest confirmed-water pixel).

  POST-EVENT OPTICAL  A field that is green canopy on the event date but open
            water on the post-event scene (9-19 Nov) was probably flooded under
            the canopy, if the water receded monotonically in between.
            Measured: area with NDWI > 0 after the event and NDWI <= 0 on the
            event date, outside cloud.

No radar and no model output is read here.

Outputs: results/level4/hidden_water_feasibility.json
         data/labels/imagery/<tile>/dem.tif  (cached, git-ignored)
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
from scipy import ndimage

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_tier_b_imagery import OUT, tile_grid  # noqa: E402
from make_label_candidates import SCL_BAD, scl_on_tile  # noqa: E402

GPKG = catalog.DATA / "labels" / "tierB_bmc_oct2020.gpkg"
GREEN_NDWI = -0.3        # event-date NDWI below this = closed green canopy
NEAR_M = 300.0           # "next to" confirmed water
LOW_M = 0.5              # "low ground": within this height of the nearby water


def tile_dem(tid, grid) -> np.ndarray:
    p = OUT / tid / "dem.tif"
    if not p.exists():
        dem = io.dem_on_grid(grid)
        with rasterio.open(p, "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
                           dtype="float32", crs=grid.crs, transform=grid.transform) as dst:
            dst.write(dem, 1)
    with rasterio.open(p) as s:
        return s.read(1)


def first(d: pathlib.Path, pattern: str):
    return next(iter(sorted(d.glob(pattern))), None)


def pct(a, q):
    return [round(float(x), 2) for x in np.nanpercentile(a, q)] if a.size else None


def main():
    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        feats = {x["properties"]["tile_id"]: x for x in json.load(f)["features"]}
    with open(catalog.DATA / "labels" / "optical_availability.csv") as f:
        avail = {r["tile_id"]: r for r in csv.DictReader(f)}
    labels = gpd.read_file(GPKG, layer="flood")

    out = {"params": {"green_ndwi": GREEN_NDWI, "near_m": NEAR_M, "low_m": LOW_M}, "tiles": {}}
    for tid in sorted(avail, key=lambda t: int(avail[t]["label_order"])):
        grid = tile_grid(feats[tid])
        shape = (grid.height, grid.width)
        L = labels[labels["tile_id"] == tid].to_crs(grid.crs)
        conf = L[(L["confidence"] >= 2) & (L["class"] >= 1)]
        cloud = L[L["class"] == -1]
        burn = lambda gs: (rasterize(((g, 1) for g in gs.geometry), out_shape=shape,  # noqa: E731
                                     transform=grid.transform).astype(bool) if len(gs) else np.zeros(shape, bool))
        water, cl = burn(conf), burn(cloud)
        d = OUT / tid / "optical"
        ev, po = first(d, "ndwi_event_*.tif"), first(d, "ndwi_post_*.tif")
        rec = {"stratum": avail[tid]["stratum"], "confirmed_water_km2": round(water.sum() * 1e-4, 3)}

        dem = tile_dem(tid, grid)
        rec["dem_p5_p50_p95_m"] = pct(dem, [5, 50, 95])
        rec["dem_spread_p5_p95_m"] = round(rec["dem_p5_p50_p95_m"][2] - rec["dem_p5_p50_p95_m"][0], 2)

        if ev is None:
            rec["note"] = "no event-date optical"
            out["tiles"][tid] = rec
            continue
        with rasterio.open(ev) as s:
            e = s.read(1)
        green = (e < GREEN_NDWI) & ~cl & ~water
        rec["green_clear_km2"] = round(green.sum() * 1e-4, 3)
        if water.any():
            dist, (iy, ix) = ndimage.distance_transform_edt(~water, return_indices=True)
            height = dem - dem[iy, ix]
            near = green & (dist * abs(grid.transform.a) < NEAR_M)
            rec["green_near_water_km2"] = round(near.sum() * 1e-4, 3)
            rec["green_near_water_height_p10_p50_p90_m"] = pct(height[near], [10, 50, 90])
            rec["green_near_water_frac_low"] = round(float(np.mean(height[near] <= LOW_M)), 3) if near.any() else None
        if po is not None:
            with rasterio.open(po) as s:
                p = s.read(1)
            rec["post_date"] = avail[tid]["post_date"]
            # the class -1 polygons are event-date cloud; the post scene needs its own mask
            xs = [q[0] for q in feats[tid]["geometry"]["coordinates"][0]]
            ys = [q[1] for q in feats[tid]["geometry"]["coordinates"][0]]
            scl_post = scl_on_tile(tid, grid, rec["post_date"], [min(xs), min(ys), max(xs), max(ys)], role="post")
            cl_post = np.isin(scl_post, list(SCL_BAD)) if scl_post is not None else np.zeros(shape, bool)
            both = ~cl & ~cl_post
            rec["post_cloud_frac"] = round(float(cl_post.mean()), 3)
            rec["post_water_km2"] = round(((p > 0) & ~cl_post).sum() * 1e-4, 3)
            rec["event_water_km2"] = round(((e > 0) & ~cl).sum() * 1e-4, 3)
            rec["post_water_event_not_km2"] = round(((p > 0) & (e <= 0) & both).sum() * 1e-4, 3)
        out["tiles"][tid] = rec

    t = out["tiles"].values()
    crop = [r for r in t if r["stratum"] == "cropland"]
    out["summary"] = {
        "tiles_measured_optical": sum("post_water_km2" in r for r in t),
        "cropland_tiles": len(crop),
        "cropland_dem_spread_median_m": round(float(np.median([r["dem_spread_p5_p95_m"] for r in crop])), 2),
        "cropland_tiles_with_confirmed_water": int(sum(r["confirmed_water_km2"] > 0 for r in crop)),
        "post_water_event_not_km2_total": round(sum(r.get("post_water_event_not_km2", 0) for r in t), 3),
        "post_water_event_not_km2_cropland": round(sum(r.get("post_water_event_not_km2", 0) for r in crop), 3),
    }
    p = experiments.RESULTS / "level4" / "hidden_water_feasibility.json"
    with open(p, "w") as f:
        json.dump(out, f, indent=2)

    print(f"{'tile':12s} {'DEM p5-p95':>10s} {'water km2':>9s} {'green<300m':>10s} {'frac low':>8s} {'post-not-event':>14s}")
    for tid, r in out["tiles"].items():
        print(f"{tid:12s} {r['dem_spread_p5_p95_m']:10.2f} {r['confirmed_water_km2']:9.3f} "
              f"{r.get('green_near_water_km2', 0):10.3f} {str(r.get('green_near_water_frac_low', '-')):>8s} "
              f"{r.get('post_water_event_not_km2', 0):14.3f}")
    print("\n", json.dumps(out["summary"], indent=1))
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
