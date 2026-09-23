"""Sentinel-1 RTC (Planetary Computer, gamma-nought, linear power) onto any
target grid, as dB. This is the Level 4+ input pipeline.

The Sen1Floods11 chips are sigma-nought dB from Google Earth Engine; RTC is
gamma-nought linear from Microsoft. The plan (rule 9) requires the effect of
that switch to be measured, not assumed; see scripts/level4_pipeline_switch.py.
"""
from __future__ import annotations

import numpy as np
from rasterio.enums import Resampling

from . import catalog, io


def rtc_items(bbox_4326: list[float], start: str, end: str, rel_orbit: int | None = None, orbit_state: str | None = None):
    """STAC items of sentinel-1-rtc intersecting a lon/lat bbox in a date range."""
    query = {}
    if rel_orbit is not None:
        query["sat:relative_orbit"] = {"eq": rel_orbit}
    if orbit_state is not None:
        query["sat:orbit_state"] = {"eq": orbit_state}
    return list(catalog._client().search(collections=["sentinel-1-rtc"], bbox=bbox_4326,
                                         datetime=f"{start}/{end}", query=query or None).items())


def rtc_db_on_grid(items, grid: io.Grid) -> np.ndarray:
    """(2, H, W) float32 dB = (VV, VH), NaN where no RTC coverage.

    Slices of the same pass are mosaicked (first valid wins); linear power is
    averaged onto the target grid (Resampling.average is right for intensity
    when downsampling; at equal resolution it degenerates to nearest).

    When the target grid is coarser than the source, the COG's own overview
    pyramid is used: warping a full-resolution 28,000 x 21,000 slice over a
    province-sized grid pulls hundreds of MB through many small range requests
    and stalls, while warping the matching overview is seconds.
    """
    out = []
    for band in ("vv", "vh"):
        lin = _mosaic_via_overviews(items, band, grid).astype(np.float32)
        lin[lin <= 0] = np.nan  # RTC uses 0 / negative as nodata in some products
        out.append(io.to_db(lin))
    return np.stack(out)


def _overview_level(src, target_res_m: float) -> int | None:
    """Index into src.overviews(1) whose resolution is still finer than the target, or None."""
    src_res = abs(src.transform.a)
    best = None
    for i, factor in enumerate(src.overviews(1) or []):
        if src_res * factor <= target_res_m:
            best = i
        else:
            break
    return best


# Reading remote COGs through the default GDAL settings issues a directory
# listing per open and many small range requests; these make a province-sized
# read minutes instead of seconds.
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": 256 * 1024 * 1024,
    "GDAL_CACHEMAX": 1024,
}


def _mosaic_via_overviews(items, asset: str, grid: io.Grid) -> np.ndarray:
    """Like io._mosaic_on_grid, but for large grids over remote COGs.

    Two differences that matter at province scale:
    - each source is opened at the overview level matching the target
      resolution, so a 10 m slice is not warped from full resolution onto a
      20 m grid;
    - only the window the source actually covers is read, instead of the whole
      target grid per source (the latter makes GDAL fetch across the entire
      footprint for every slice).
    """
    import rasterio
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    out = np.full((grid.height, grid.width), np.nan, np.float32)
    filled = np.zeros(out.shape, bool)
    gl, gt = grid.transform.c, grid.transform.f
    gr, gb = gl + grid.width * grid.transform.a, gt + grid.height * grid.transform.e
    with rasterio.Env(**GDAL_ENV):
        for it in io._items_covering(items, grid):
            href = it.assets[asset].href
            with rasterio.open(href) as src:
                if src.crs != grid.crs:  # different projection -> full warp (slow but correct)
                    arr, valid, win = _warped_window(src, grid)
                else:
                    # Same CRS and an axis-aligned grid: a decimated window read
                    # uses the COG's overview pyramid directly. Orders of
                    # magnitude faster than WarpedVRT over a province-sized
                    # grid, which reads the source at full resolution.
                    # Windows are clipped on the source side first, then mapped
                    # back to the target: a boundless read would bypass the
                    # overviews and resample the full-resolution data locally.
                    src_win = from_bounds(max(gl, src.bounds.left), max(gb, src.bounds.bottom),
                                          min(gr, src.bounds.right), min(gt, src.bounds.top),
                                          src.transform).round_offsets().round_lengths()
                    src_win = src_win.intersection(Window(0, 0, src.width, src.height))
                    if src_win.width < 1 or src_win.height < 1:
                        continue
                    win = from_bounds(*rasterio.windows.bounds(src_win, src.transform),
                                      grid.transform).round_offsets().round_lengths()
                    win = win.intersection(Window(0, 0, grid.width, grid.height))
                    if win.width < 1 or win.height < 1:
                        continue
                    shape = (int(win.height), int(win.width))
                    arr = src.read(1, window=src_win, out_shape=shape,
                                    resampling=Resampling.average).astype(np.float32)
                    # Validity from the data, not read_masks: the mask read
                    # ignores the overviews and costs minutes at this size.
                    # RTC linear gamma0 is strictly positive where there is
                    # signal; 0 and the fill value mark no data.
                    valid = np.isfinite(arr) & (arr > 0)
                    if src.nodata is not None:
                        valid &= arr != src.nodata
            r0, c0 = int(win.row_off), int(win.col_off)
            sl = (slice(r0, r0 + arr.shape[0]), slice(c0, c0 + arr.shape[1]))
            take = valid & ~filled[sl]
            out[sl][take] = arr[take]
            filled[sl] |= take
    return out


def _warped_window(src, grid: io.Grid):
    """Fallback for a source in a different CRS: warp only its window of the grid."""
    import rasterio
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    l, b, r, t = transform_bounds(src.crs, grid.crs, *src.bounds)
    win = from_bounds(l, b, r, t, grid.transform).round_offsets().round_lengths()
    win = win.intersection(Window(0, 0, grid.width, grid.height))
    sub = rasterio.windows.transform(win, grid.transform)
    nodata = src.nodata
    if nodata is None and np.issubdtype(np.dtype(src.dtypes[0]), np.floating):
        nodata = float("nan")
    with WarpedVRT(src, crs=grid.crs, transform=sub, width=int(win.width), height=int(win.height),
                   resampling=Resampling.average, nodata=nodata) as vrt:
        return vrt.read(1).astype(np.float32), vrt.read_masks(1) > 0, win
