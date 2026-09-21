"""Level 1: no-AI water detection by histogram thresholding. "Dark = water."

Two flavours:
- per-chip Otsu: threshold fitted on each chip's own histogram (what the
  Sen1Floods11 authors did on VH; their output is the S1OtsuLabelHand layer).
- global threshold: one value fitted once on the training split and applied
  everywhere. Closer to how an operational system behaves.

All thresholds operate on dB values clipped to CLIP so a handful of extreme
pixels (Level 0 caveat 6) cannot move the histogram.
"""
from __future__ import annotations

import numpy as np
from skimage.filters import threshold_otsu

CLIP = (-50.0, 10.0)
BAND = {"vv": 0, "vh": 1}


def _clipped(s1_db: np.ndarray, band: str, valid: np.ndarray) -> np.ndarray:
    x = s1_db[BAND[band]][valid]
    return np.clip(x, *CLIP)


def otsu_per_chip(s1_db: np.ndarray, band: str, valid: np.ndarray) -> tuple[np.ndarray, float]:
    """Water mask (bool) and the threshold used, fitted on this chip only.

    A chip with no bimodality (all dry, all water) still gets an Otsu value;
    it will just be a poor one. That is a real weakness of per-chip Otsu and
    is reported, not hidden.
    """
    x = _clipped(s1_db, band, valid)
    if x.size < 2 or np.ptp(x) == 0:
        return np.zeros(s1_db.shape[1:], bool), float("nan")
    t = float(threshold_otsu(x))
    return (s1_db[BAND[band]] < t) & valid, t


def fit_global(chips: list[tuple[np.ndarray, np.ndarray]], band: str, max_pixels: int = 5_000_000, seed: int = 0) -> float:
    """One Otsu threshold from a random pixel sample pooled over many chips.

    chips: list of (s1_db, valid) pairs. Sampling keeps memory flat and makes
    the result independent of chip order.
    """
    rng = np.random.default_rng(seed)
    per_chip = max(1, max_pixels // max(1, len(chips)))
    pool = []
    for s1_db, valid in chips:
        x = _clipped(s1_db, band, valid)
        if x.size > per_chip:
            x = rng.choice(x, per_chip, replace=False)
        pool.append(x)
    return float(threshold_otsu(np.concatenate(pool)))


def apply_global(s1_db: np.ndarray, band: str, valid: np.ndarray, t: float) -> np.ndarray:
    return (s1_db[BAND[band]] < t) & valid
