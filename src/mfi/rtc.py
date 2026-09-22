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
    """
    out = []
    for band in ("vv", "vh"):
        lin = io._mosaic_on_grid(items, band, grid, Resampling.average, fill=np.nan).astype(np.float32)
        lin[lin <= 0] = np.nan  # RTC uses 0 / negative as nodata in some products
        out.append(io.to_db(lin))
    return np.stack(out)
