"""Mistake_avoidance.md #8: measure the key assumption before investing.

Question: do the Sen1Floods11 hand labels contain *bright* flooded cropland at
all? Double-bounce flooded rice should sit above the dark-water threshold and
near, or above, dry-cropland brightness. If almost every labelled flooded
cropland pixel is dark, then (a) thresholding already finds it and (b) the
labels cannot be used to train or test a model for the bright case.

For each split and land type this writes the VV/VH distribution of flood
pixels and of dry pixels, and the fraction of flood pixels above the global
thresholds from results/level1/_global_thresholds/config.json.

Outputs (artefacts; the figure is generated from them by plot_level1.py):
    results/level1/label_brightness.json
    results/level1/label_brightness_hist.npz   (histograms, 0.5 dB bins)
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io, strata  # noqa: E402

BINS = np.arange(-50, 10.5, 0.5)
LANDS = ["open_water", "cropland", "vegetation", "built"]


def main():
    with open(experiments.run_dir("level1", "_global_thresholds") / "config.json") as f:
        gt = json.load(f)
    split = catalog.s1f11_split()
    hists = {}
    summary = {}
    for s, chips in split.items():
        # (split, land, class, band) -> histogram counts
        h = {(land, cls, band): np.zeros(len(BINS) - 1, np.int64)
             for land in LANDS for cls in ("flood", "dry") for band in ("vv", "vh")}
        for chip in tqdm(chips, desc=s, leave=False):
            s1, label, grid = io.read_s1f11_chip(chip)
            land = strata.land_type(io.worldcover_chip(chip, grid))
            for lname in LANDS:
                lcode = {v: k for k, v in strata.LAND_NAMES.items()}[lname]
                for cls, lv in (("flood", 1), ("dry", 0)):
                    m = (label == lv) & (land == lcode)
                    if not m.any():
                        continue
                    for bi, band in enumerate(("vv", "vh")):
                        h[(lname, cls, band)] += np.histogram(np.clip(s1[bi][m], -50, 10), BINS)[0]
        centers = (BINS[:-1] + BINS[1:]) / 2
        for (lname, cls, band), counts in h.items():
            hists[f"{s}/{lname}/{cls}/{band}"] = counts
        summary[s] = {}
        for lname in LANDS:
            row = {}
            for band in ("vv", "vh"):
                fl, dr = h[(lname, "flood", band)], h[(lname, "dry", band)]
                if fl.sum() == 0:
                    continue
                cdf = np.cumsum(fl) / fl.sum()
                q = lambda p: float(centers[np.searchsorted(cdf, p)])  # noqa: E731
                dry_median = float(centers[np.searchsorted(np.cumsum(dr) / max(dr.sum(), 1), 0.5)]) if dr.sum() else float("nan")
                above_t = float(fl[centers >= gt[band]].sum() / fl.sum())
                above_dry_median = float(fl[centers >= dry_median].sum() / fl.sum()) if dr.sum() else float("nan")
                row[band] = {
                    "n_flood": int(fl.sum()), "n_dry": int(dr.sum()),
                    "flood_p10": q(0.10), "flood_median": q(0.50), "flood_p90": q(0.90),
                    "dry_median": dry_median, "global_threshold": gt[band],
                    "frac_flood_above_threshold": above_t,
                    "frac_flood_at_or_above_dry_median": above_dry_median,
                }
            summary[s][lname] = row
    out = experiments.RESULTS / "level1"
    with open(out / "label_brightness.json", "w") as f:
        json.dump(summary, f, indent=2)
    np.savez_compressed(out / "label_brightness_hist.npz", bins=BINS, **hists)
    print("wrote", out / "label_brightness.json")

    print(f"\n{'split':6s} {'land':11s} {'band':4s} {'n_flood':>10s} {'flood med':>9s} {'dry med':>8s} {'thr':>7s} {'>thr':>6s} {'>=dry med':>9s}")
    for s in ("train", "valid", "test"):
        for lname in LANDS:
            for band in ("vv", "vh"):
                r = summary[s][lname].get(band)
                if r:
                    print(f"{s:6s} {lname:11s} {band:4s} {r['n_flood']:10,d} {r['flood_median']:9.1f} {r['dry_median']:8.1f} "
                          f"{r['global_threshold']:7.2f} {r['frac_flood_above_threshold']:6.1%} {r['frac_flood_at_or_above_dry_median']:9.1%}")


if __name__ == "__main__":
    main()
