"""Level 3 dataset: Sen1Floods11 chips -> normalised input tensors + labels.

Inputs are built from named channels so every experiment is a config, not a
code branch:  "vv", "vh", "ratio" (VV-VH), "slope" (deg, from the cached DEM).
Normalisation stats are fitted on the train split once and saved with the run.

Labels: int64 with 0 = dry, 1 = water, IGNORE (255) = no data. Loss and metrics
skip IGNORE. Training samples random square crops; evaluation uses full chips.
Reads from disk per item (memory stays flat); Windows -> num_workers=0.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import torch
from torch.utils.data import Dataset

from . import catalog, io, strata

IGNORE = 255
DB_CLIP = (-50.0, 10.0)
CHANNELS = ("vv", "vh", "ratio", "slope")


# Which pre-processing the chips come from. evaluation_plan v1.0 used the
# Sen1Floods11 chips as shipped (sigma0, GEE); v1.1 uses Planetary Computer RTC
# (gamma0) for every split so training and Cambodia share one pipeline.
# MFI_PIPELINE=sigma0 reproduces v1.0 results.
import os

PIPELINE = os.environ.get("MFI_PIPELINE", "rtc")
CACHE_SIGMA0 = catalog.DATA / "interim" / "chip_cache"
CACHE_RTC = catalog.DATA / "interim" / "chip_cache_rtc"
CACHE = CACHE_RTC if PIPELINE == "rtc" else CACHE_SIGMA0


def _build_cache(chip: str) -> pathlib.Path:
    """One .npz per chip: float16 channels + int8 label + int8 land. Built once
    from the GeoTIFFs; afterwards a training sample is a single ~2 MB read
    instead of four compressed rasters plus a slope computation."""
    s1, label, grid = io.read_s1f11_chip(chip)
    vv, vh = np.clip(s1[0], *DB_CLIP), np.clip(s1[1], *DB_CLIP)
    slope = np.nan_to_num(io.slope_deg(io.dem_chip(chip, grid), grid), nan=0.0)
    land = strata.land_type(io.worldcover_chip(chip, grid))
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{chip}.npz"
    np.savez(p, x=np.stack([vv, vh, vv - vh, slope]).astype(np.float16), label=label.astype(np.int8), land=land.astype(np.int8))
    return p


def raw_channels(chip: str) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, io.Grid | None]:
    """All possible channels (unnormalised, float32), label {-1,0,1}, land type.

    Served from the per-chip cache (built on first use). The grid is not
    needed by training and is returned as None; use io.read_s1f11_chip for it.
    """
    p = CACHE / f"{chip}.npz"
    if not p.exists():
        if PIPELINE == "rtc":
            raise FileNotFoundError(f"{p} missing - run scripts/build_rtc_chips.py (plan v1.1 input pipeline)")
        _build_cache(chip)
    z = np.load(p)
    x = z["x"].astype(np.float32)
    ch = {"vv": x[0], "vh": x[1], "ratio": x[2], "slope": x[3]}
    return ch, z["label"], z["land"], None


def fit_norm_stats(chips: list[str], sample_per_chip: int = 20_000, seed: int = 0) -> dict[str, list[float]]:
    """Per-channel mean/std over labelled pixels of the given (train) chips."""
    rng = np.random.default_rng(seed)
    acc = {c: [] for c in CHANNELS}
    for chip in chips:
        ch, label, _, _ = raw_channels(chip)
        finite = np.all([np.isfinite(ch[c]) for c in CHANNELS], axis=0)
        idx = np.flatnonzero((label >= 0) & finite)
        if idx.size == 0:
            continue
        if idx.size > sample_per_chip:
            idx = rng.choice(idx, sample_per_chip, replace=False)
        for c in CHANNELS:
            acc[c].append(ch[c].ravel()[idx])
    return {c: [float(np.mean(v := np.concatenate(acc[c]))), float(np.std(v) + 1e-6)] for c in CHANNELS}


class ChipDataset(Dataset):
    def __init__(self, chips: list[str], channels: list[str], norm: dict[str, list[float]],
                 crop: int | None = 256, augment: bool = False, crops_per_chip: int = 1, seed: int = 0):
        self.chips, self.channels, self.norm = chips, channels, norm
        self.crop, self.augment, self.crops_per_chip = crop, augment, crops_per_chip
        self.rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.chips) * self.crops_per_chip

    def __getitem__(self, i):
        chip = self.chips[i % len(self.chips)]
        ch, label, land, _ = raw_channels(chip)
        x = np.stack([(ch[c] - self.norm[c][0]) / self.norm[c][1] for c in self.channels]).astype(np.float32)
        # cast before np.where: under NumPy 2 promotion an int8 label array would
        # keep IGNORE=255 as int8 and wrap it to -1 (invalid class index on GPU)
        y = np.where(label < 0, IGNORE, label.astype(np.int64))
        # RTC chips are NaN outside the slice footprint: those pixels carry no
        # radar, so they are not trainable and not scorable.
        nodata = ~np.isfinite(x).all(axis=0)
        if nodata.any():
            x = np.nan_to_num(x, nan=0.0)
            y = np.where(nodata, IGNORE, y)
        vh = ch["vh"].astype(np.float32)  # raw VH kept for the bright sub-strata
        if self.crop:
            H, W = y.shape
            r, c = self.rng.integers(0, H - self.crop + 1), self.rng.integers(0, W - self.crop + 1)
            sl = (slice(r, r + self.crop), slice(c, c + self.crop))
            x, y, land, vh = x[:, sl[0], sl[1]], y[sl], land[sl], vh[sl]
        if self.augment:
            # flips + 90-degree rotations. Physically questionable for side-looking
            # radar (shadow/layover direction is tied to look direction); tested
            # on/off as the plan asks, never assumed.
            k = self.rng.integers(0, 4)
            x, y, land, vh = (np.rot90(a, k, axes=(-2, -1)) for a in (x, y, land, vh))
            if self.rng.random() < 0.5:
                x, y, land, vh = (np.flip(a, axis=-1) for a in (x, y, land, vh))
        return {
            "x": torch.from_numpy(np.ascontiguousarray(x)),
            "y": torch.from_numpy(np.ascontiguousarray(y)),
            "land": torch.from_numpy(np.ascontiguousarray(land)),
            "vh": torch.from_numpy(np.ascontiguousarray(vh)),
            "chip": chip,
        }


def splits() -> dict[str, list[str]]:
    return catalog.s1f11_split()


def load_norm(path: pathlib.Path) -> dict[str, list[float]]:
    with open(path) as f:
        return json.load(f)
