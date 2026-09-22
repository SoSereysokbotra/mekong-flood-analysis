"""Sensitivity check: does the v1.1 outcome depend on how "bright" is defined?

evaluation_plan v1.1 says the bright sub-strata stay pinned to the sigma0 VH
threshold (-19.65 dB) so v1.0 and v1.1 cover the same pixels. The code instead
takes the VH of whichever pipeline the run uses, and gamma0 sits ~1.8 dB higher,
so the v1.1 bright class is larger (131k vs 50k cropland pixels on test).

This re-scores the *saved test predictions* (no model runs, no selection) of the
selected model and the controls under both definitions:
    rtc_vh    bright = RTC VH >= -19.65 dB        (what the v1.1 runs reported)
    sigma0_vh bright = Sen1Floods11 VH >= -19.65  (what the plan text says)

Writes results/level4/bright_definition_check.json. Reported, not used to choose
anything.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, data, experiments, metrics, strata  # noqa: E402

RUNS = ["unet_vvvh_cropw", "unet_vv_ce", "pixel_logreg", "pixel_mlp"]


def sigma0_vh(chip: str) -> np.ndarray:
    z = np.load(data.CACHE_SIGMA0 / f"{chip}.npz")
    return z["x"][1].astype(np.float32)


def main():
    chips = catalog.s1f11_split()["test"]
    out = {}
    for run in RUNS:
        pred_dir = experiments.run_dir(experiments.level3_dir(), run) / "pred_test"
        conf = {"rtc_vh": metrics.Confusion(), "sigma0_vh": metrics.Confusion()}
        for chip in tqdm(chips, desc=run, leave=False):
            ch, label, land, _ = data.raw_channels(chip)     # RTC channels + label + land
            with rasterio.open(pred_dir / f"{chip}.tif") as src:
                pred = src.read(1).astype(bool)
            lab = np.where(np.isfinite(ch["vv"]) & np.isfinite(ch["vh"]), label, -1).astype(np.int8)
            conf["rtc_vh"].add(pred, lab, land, vh=ch["vh"])
            conf["sigma0_vh"].add(pred, lab, land, vh=sigma0_vh(chip))
        out[run] = {}
        for k, c in conf.items():
            m = c.metrics()
            out[run][k] = {g: {kk: m[g][kk] for kk in ("recall", "precision", "iou", "n_pos")}
                           for g in ("cropland_bright", "vegetation_bright", "cropland_dark", "cropland", "all")}
    p = experiments.RESULTS / "level4" / "bright_definition_check.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {p}\n")
    print(f"{'run':18s} {'definition':10s} {'B':>6s} {'n_B':>9s} {'V':>6s} {'n_V':>9s} {'D':>6s}")
    for run in RUNS:
        for k in ("rtc_vh", "sigma0_vh"):
            d = out[run][k]
            print(f"{run:18s} {k:10s} {d['cropland_bright']['recall']:6.3f} {d['cropland_bright']['n_pos']:9,d} "
                  f"{d['vegetation_bright']['recall']:6.3f} {d['vegetation_bright']['n_pos']:9,d} {d['cropland_dark']['recall']:6.3f}")


if __name__ == "__main__":
    main()
