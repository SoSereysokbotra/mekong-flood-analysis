"""Banteay Meanchey AOI grid, ancillary layers, and Level 4 constants.

Moved from scripts/level4_cambodia.py so the library does not depend on scripts.
"""
from __future__ import annotations

import os
import pathlib

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

from mfi import catalog, io, rtc, strata

AOI_EPSG = 32648
# Grid resolution in metres. 20 m (2x the native 10 m) is the product; a
# coarser value is a cheap preview when the link to the data is slow.
RES_M = float(os.environ.get("MFI_LEVEL4_RES_M", "20"))
CACHE = catalog.DATA / "interim" / "level4"
METHODS = ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"]
SUFFIX = "" if RES_M == 20 else f"_{int(RES_M)}m"
DISTRICTS = catalog.DATA / "aoi" / "banteay_meanchey_adm2.geojson"


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
    p = CACHE / f"s1_{date}{SUFFIX}.npz"
    if p.exists():
        return np.load(p)["s1_db"]
    items = rtc.rtc_items(catalog.aoi_bbox(), date, date,
                          rel_orbit=catalog.ANCHOR_REL_ORBIT, orbit_state=catalog.ANCHOR_ORBIT_STATE)
    if not items:
        from mfi.check import CheckError

        raise CheckError(f"no RTC items for {date} on track {catalog.ANCHOR_REL_ORBIT}")
    print(f"  {date}: {len(items)} RTC slice(s)", flush=True)
    s1 = rtc.rtc_db_on_grid(items, grid)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(p, s1_db=s1.astype(np.float32), items=np.array([i.id for i in items]))
    return s1


def ancillary(grid: io.Grid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(land type, JRC occurrence %, slope deg) on the AOI grid, cached."""
    p = CACHE / f"ancillary{SUFFIX}.npz"
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
