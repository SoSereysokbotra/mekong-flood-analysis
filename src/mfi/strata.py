"""Land-type stratification. Turns a flood label + a land-cover map into the
per-pixel stratum every score in this project is reported against.

Strata (int8):
    0  NON_FLOOD          label == 0, any land cover
    1  FLOOD_OPEN_WATER   label == 1, WorldCover permanent water (80)
    2  FLOOD_CROPLAND     label == 1, WorldCover cropland (40)      <- the hypothesis lives here
    3  FLOOD_VEGETATION   label == 1, tree / shrub / grass / wetland / mangrove (10, 20, 30, 90, 95)
    4  FLOOD_BUILT        label == 1, built-up (50)
    5  FLOOD_OTHER        label == 1, bare / snow / moss (60, 70, 100)
   -1  IGNORE             label == -1

Caveat recorded in the evaluation plan: WorldCover "cropland" is not "rice".
In Banteay Meanchey it is overwhelmingly paddy; elsewhere in Sen1Floods11 it is
not, so per-event numbers for stratum 2 mean "flooded cropland", nothing more.
"""
from __future__ import annotations

import numpy as np

NON_FLOOD, FLOOD_OPEN_WATER, FLOOD_CROPLAND, FLOOD_VEGETATION, FLOOD_BUILT, FLOOD_OTHER = range(6)
IGNORE = -1

NAMES = {
    NON_FLOOD: "non_flood",
    FLOOD_OPEN_WATER: "flood_open_water",
    FLOOD_CROPLAND: "flood_cropland",
    FLOOD_VEGETATION: "flood_vegetation",
    FLOOD_BUILT: "flood_built",
    FLOOD_OTHER: "flood_other",
    IGNORE: "ignore",
}

# ESA WorldCover v100/v200 class codes
WC_TREE, WC_SHRUB, WC_GRASS, WC_CROP, WC_BUILT, WC_BARE, WC_SNOW, WC_WATER, WC_WETLAND, WC_MANGROVE, WC_MOSS = (
    10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100,
)

_WC_TO_FLOOD_STRATUM = {
    WC_WATER: FLOOD_OPEN_WATER,
    WC_CROP: FLOOD_CROPLAND,
    WC_TREE: FLOOD_VEGETATION,
    WC_SHRUB: FLOOD_VEGETATION,
    WC_GRASS: FLOOD_VEGETATION,
    WC_WETLAND: FLOOD_VEGETATION,
    WC_MANGROVE: FLOOD_VEGETATION,
    WC_BUILT: FLOOD_BUILT,
    WC_BARE: FLOOD_OTHER,
    WC_SNOW: FLOOD_OTHER,
    WC_MOSS: FLOOD_OTHER,
}


def stratify(label: np.ndarray, worldcover: np.ndarray) -> np.ndarray:
    """Per-pixel stratum from a {-1,0,1} label and a WorldCover code raster."""
    out = np.full(label.shape, IGNORE, dtype=np.int8)
    out[label == 0] = NON_FLOOD
    flood = label == 1
    out[flood] = FLOOD_OTHER  # WorldCover nodata (0) under a flood pixel -> other
    for code, stratum in _WC_TO_FLOOD_STRATUM.items():
        out[flood & (worldcover == code)] = stratum
    return out


def counts(strata: np.ndarray) -> dict[str, int]:
    """Pixel count per stratum name, for inventories."""
    vals, n = np.unique(strata, return_counts=True)
    return {NAMES[int(v)]: int(c) for v, c in zip(vals, n)}
