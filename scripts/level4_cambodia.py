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
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, infer, io, rtc, strata  # noqa: E402

DATES = {"2020-09-26": "pre", "2020-10-14": "peak", "2020-11-01": "post"}
METHODS = ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"]
RES_M = 20.0          # 20 m grid: 2x the native 10 m, keeps the province in ~7k x 6k px
AOI_EPSG = 32648
CACHE = catalog.DATA / "interim" / "level4"
MAPS = experiments.RESULTS / "level4" / "maps"
JRC_PERMANENT = 80    # JRC occurrence >= 80% of observations -> permanent water


def aoi_grid() -> tuple[io.Grid, np.ndarray]:
    """Province grid in UTM 48N at RES_M, and a boolean mask of the province."""
    geom = catalog.aoi_geometry()
    utm = transform_geom("EPSG:4326", f"EPSG:{AOI_EPSG}", geom)

    def walk(c):
        if isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c:
                yield from walk(x)

    pts = list(walk(utm["coordinates"]))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    l, b = np.floor(min(xs) / RES_M) * RES_M, np.floor(min(ys) / RES_M) * RES_M
    r, t = np.ceil(max(xs) / RES_M) * RES_M, np.ceil(max(ys) / RES_M) * RES_M
    w, h = int((r - l) / RES_M), int((t - b) / RES_M)
    transform = rasterio.transform.from_origin(l, t, RES_M, RES_M)
    grid = io.Grid(rasterio.crs.CRS.from_epsg(AOI_EPSG), transform, h, w)
    inside = ~geometry_mask([utm], (h, w), transform, invert=False)
    return grid, inside


def s1_on_aoi(date: str, grid: io.Grid) -> np.ndarray:
    """(2, H, W) dB VV/VH for one date, cached."""
    p = CACHE / f"s1_{date}.npz"
    if p.exists():
        return np.load(p)["s1_db"]
    items = rtc.rtc_items(catalog.aoi_bbox(), date, date,
                          rel_orbit=catalog.ANCHOR_REL_ORBIT, orbit_state=catalog.ANCHOR_ORBIT_STATE)
    if not items:
        sys.exit(f"no RTC items for {date} on track {catalog.ANCHOR_REL_ORBIT}")
    print(f"  {date}: {len(items)} RTC slice(s)", flush=True)
    s1 = rtc.rtc_db_on_grid(items, grid)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(p, s1_db=s1.astype(np.float32), items=np.array([i.id for i in items]))
    return s1


def ancillary(grid: io.Grid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(land type, JRC occurrence %, slope deg) on the AOI grid, cached."""
    p = CACHE / "ancillary.npz"
    if p.exists():
        z = np.load(p)
        return z["land"], z["jrc"], z["slope"]
    land = strata.land_type(io.worldcover_on_grid(grid, year=2020))
    jrc = io.jrc_occurrence_on_grid(grid)
    slope = np.nan_to_num(io.slope_deg(io.dem_on_grid(grid), grid), nan=0.0)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(p, land=land, jrc=jrc, slope=slope)
    return land, jrc, slope


def write_map(path: pathlib.Path, arr: np.ndarray, grid: io.Grid):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
                       dtype="int8", crs=grid.crs, transform=grid.transform, compress="deflate", nodata=-1) as dst:
        dst.write(arr.astype(np.int8), 1)


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
            write_map(MAPS / f"{method}_{date}.tif", pred, grid)
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
    with open(out / "areas.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out / "areas.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {out / 'areas.csv'} and areas.json; maps in {MAPS}")


if __name__ == "__main__":
    main()
