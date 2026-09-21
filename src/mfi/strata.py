"""Land-type stratification. Every score in this project is reported per
land type, so every pixel — flooded or dry — needs a land type. Land type and
flood label are kept as two separate arrays; the joint (label, land_type) is
what metrics are computed over.

Land types (int8), from ESA WorldCover codes:
    0  OPEN_WATER   permanent water (80)
    1  CROPLAND     cropland (40)                                   <- the hypothesis lives here
    2  VEGETATION   tree / shrub / grass / wetland / mangrove (10, 20, 30, 90, 95)
    3  BUILT        built-up (50)
    4  OTHER        bare / snow / moss (60, 70, 100)
    5  UNKNOWN      WorldCover nodata (0)

Caveat recorded in the evaluation plan: WorldCover "cropland" is not "rice".
In Banteay Meanchey it is overwhelmingly paddy; elsewhere in Sen1Floods11 it is
not, so per-event numbers for CROPLAND mean "cropland", nothing more.
"""
from __future__ import annotations

import numpy as np

OPEN_WATER, CROPLAND, VEGETATION, BUILT, OTHER, UNKNOWN = range(6)

LAND_NAMES = {
    OPEN_WATER: "open_water",
    CROPLAND: "cropland",
    VEGETATION: "vegetation",
    BUILT: "built",
    OTHER: "other",
    UNKNOWN: "unknown",
}

# ESA WorldCover v100/v200 class codes
WC_TREE, WC_SHRUB, WC_GRASS, WC_CROP, WC_BUILT, WC_BARE, WC_SNOW, WC_WATER, WC_WETLAND, WC_MANGROVE, WC_MOSS = (
    10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100,
)

_WC_TO_LAND = {
    WC_WATER: OPEN_WATER,
    WC_CROP: CROPLAND,
    WC_TREE: VEGETATION,
    WC_SHRUB: VEGETATION,
    WC_GRASS: VEGETATION,
    WC_WETLAND: VEGETATION,
    WC_MANGROVE: VEGETATION,
    WC_BUILT: BUILT,
    WC_BARE: OTHER,
    WC_SNOW: OTHER,
    WC_MOSS: OTHER,
}


def land_type(worldcover: np.ndarray) -> np.ndarray:
    """Per-pixel land type (int8) from a WorldCover code raster. Every pixel gets one."""
    out = np.full(worldcover.shape, UNKNOWN, dtype=np.int8)
    for code, lt in _WC_TO_LAND.items():
        out[worldcover == code] = lt
    return out


def counts(label: np.ndarray, land: np.ndarray) -> dict[str, int]:
    """Pixel counts of the joint (label, land type), for inventories.

    Keys: 'flood_<land>', 'dry_<land>', and 'ignore' (label == -1).
    """
    out = {"ignore": int((label == -1).sum())}
    for lt, name in LAND_NAMES.items():
        m = land == lt
        out[f"flood_{name}"] = int((m & (label == 1)).sum())
        out[f"dry_{name}"] = int((m & (label == 0)).sum())
    return out


COUNT_KEYS = ["ignore"] + [f"{k}_{n}" for n in LAND_NAMES.values() for k in ("flood", "dry")]
