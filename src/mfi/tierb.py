"""Tier B scoring rules shared by the 2020 and 2026 scorers.

Moved here from scripts/level4_score_tierb.py (8 Nov 2026) so it can be tested
without the model stack. Behaviour unchanged.
"""
from __future__ import annotations

import pathlib

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

MIN_VALID = 0.05            # under this fraction of data, a tile has no usable optical
MAX_PARTIAL_NODATA = 0.0    # any no-data pixel in a scored tile stops the run (Gemini review, 8 Nov 2026)
SCL_NODATA = 0
# Sensitivity only (the protocol's mask is cloud + shadow, SCL 3/8/9/10/11): also ignore pixels Sen2Cor
# did not classify confidently. 1 saturated/defective, 2 dark area, 7 unclassified.
SCL_SENSITIVITY = {"ignore_scl_1_2": (1, 2), "ignore_scl_1_2_7": (1, 2, 7)}


def tiles_to_score(scl_paths: dict[str, pathlib.Path | None]) -> tuple[list[str], dict[str, str]]:
    """Which tiles are scored, from the event scene's scene-classification band (SCL) per tile.

    Rule (6 Nov 2026, replaces "tiles that have any polygon", which dropped clear tiles with no
    candidate and would drop a tile whose candidates were all rejected):
      - no event SCL, or under 5 % of it has data  -> not scored ("no usable optical")
      - otherwise scored; every clear pixel outside a confirmed polygon is DRY, cloud is ignored
      - a scored tile with any no-data pixel raises ValueError: those pixels would be counted
        as dry, so the case must be handled explicitly rather than silently.
    Returns (scored tile ids, {skipped tile id: reason}).
    """
    scored, skipped = [], {}
    for tid, p in sorted(scl_paths.items()):
        if p is None or not pathlib.Path(p).exists():
            skipped[tid] = "no event scene"
            continue
        with rasterio.open(p) as s:
            nodata = float((s.read(1) == SCL_NODATA).mean())
        if 1 - nodata < MIN_VALID:
            skipped[tid] = f"event scene {100 * nodata:.0f}% no data"
        elif nodata > MAX_PARTIAL_NODATA:
            raise ValueError(f"{tid}: event scene is {100 * nodata:.1f}% no data; these pixels would score "
                             "as dry. Mask them before scoring.")
        else:
            scored.append(tid)
    return scored, skipped


def scl_mask(scl_paths: dict, tile_ids: list[str], grid, classes) -> np.ndarray:
    """True on the scoring grid where a tile's event SCL is in `classes` (nearest resampling)."""
    out = np.zeros((grid.height, grid.width), bool)
    for tid in tile_ids:
        with rasterio.open(scl_paths[tid]) as s:
            dst = np.full(out.shape, 255, np.uint8)
            reproject(s.read(1), dst, src_transform=s.transform, src_crs=s.crs, dst_transform=grid.transform,
                      dst_crs=grid.crs, resampling=Resampling.nearest, dst_nodata=255)
        out |= np.isin(dst, classes)
    return out
