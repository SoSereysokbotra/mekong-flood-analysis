"""Run a trained Level 3 model (or the Level 1 threshold) on arbitrary arrays.

Works on numpy channel dicts {"vv": dB, "vh": dB, "slope": deg, ...} of any
size: large rasters are processed in overlapping tiles so the U-Net sees full
context at tile edges. NaN inputs (no coverage) give a "no data" (-1) output.
"""
from __future__ import annotations

import json

import numpy as np
import torch

from . import data, experiments, models

NODATA = -1


def load_unet(run_id: str, device: torch.device | None = None):
    """(model, channels, norm, device) for a level3 run's best checkpoint."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(experiments.run_dir("level3", run_id) / "best.pt", map_location=device)
    model = models.build_model(ck["cfg"]["model"], len(ck["channels"]), False).to(device).eval()
    model.load_state_dict(ck["model"])
    with open(experiments.RESULTS / "level3" / "_norm_stats.json") as f:
        norm = json.load(f)
    return model, ck["channels"], norm, device


@torch.no_grad()
def predict_unet(model, channels: list[str], norm: dict, device, ch: dict[str, np.ndarray],
                 tile: int = 1024, overlap: int = 64) -> np.ndarray:
    """int8 map: 1 water, 0 dry, -1 no data. Tiled with overlap; centre of each tile is kept."""
    H, W = ch[channels[0]].shape
    valid = np.all([np.isfinite(ch[c]) for c in channels], axis=0)
    x = np.stack([(np.nan_to_num(np.clip(ch[c], *data.DB_CLIP) if c in ("vv", "vh", "ratio") else ch[c]) - norm[c][0]) / norm[c][1]
                  for c in channels]).astype(np.float32)
    out = np.full((H, W), NODATA, np.int8)
    step = tile - 2 * overlap
    for r0 in range(0, H, step):
        for c0 in range(0, W, step):
            rs, cs = max(0, r0 - overlap), max(0, c0 - overlap)
            re, ce = min(H, r0 + step + overlap), min(W, c0 + step + overlap)
            # pad to a multiple of 8 for the U-Net's three poolings
            xt = x[:, rs:re, cs:ce]
            ph, pw = (-xt.shape[1]) % 8, (-xt.shape[2]) % 8
            xt = np.pad(xt, ((0, 0), (0, ph), (0, pw)), mode="reflect") if (ph or pw) else xt
            t = torch.from_numpy(xt).unsqueeze(0).to(device)
            with torch.autocast("cuda", dtype=torch.float16, enabled=device.type == "cuda"):
                pred = (model(t).argmax(1)[0] == 1).cpu().numpy()[: re - rs, : ce - cs]
            # keep the centre (drop the overlap margin except at raster edges)
            kr0, kc0 = r0 - rs, c0 - cs
            kr1, kc1 = min(re, r0 + step) - rs, min(ce, c0 + step) - cs
            out[r0:r0 + (kr1 - kr0), c0:c0 + (kc1 - kc0)] = pred[kr0:kr1, kc0:kc1]
    out[~valid] = NODATA
    return out


def predict_threshold(ch: dict[str, np.ndarray], band: str = "vh", t: float | None = None) -> np.ndarray:
    """Level 1 global threshold as an int8 map with -1 where no data."""
    if t is None:
        with open(experiments.run_dir("level1", "_global_thresholds") / "config.json") as f:
            t = float(json.load(f)[band])
    x = ch[band]
    out = np.where(x < t, 1, 0).astype(np.int8)
    out[~np.isfinite(x)] = NODATA
    return out


def gamma0_channels(s1_db: np.ndarray, slope: np.ndarray | None = None) -> dict[str, np.ndarray]:
    ch = {"vv": s1_db[0], "vh": s1_db[1], "ratio": s1_db[0] - s1_db[1]}
    if slope is not None:
        ch["slope"] = slope
    return ch
