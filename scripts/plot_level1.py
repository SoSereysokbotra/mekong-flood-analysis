"""Level 1 figures, generated only from saved artefacts (never recomputed here):
    results/level1/<method>/metrics_<split>.json
    results/level1/label_brightness_hist.npz + label_brightness.json

Outputs:
    docs/figures/level1_scores.png       per-method IoU / recall by land type, valid vs test
    docs/figures/level1_brightness.png   VH histograms: flooded vs dry cropland, train vs test
"""
import json
import pathlib
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402

FIG = catalog.ROOT / "docs" / "figures"
METHODS = ["otsu_vh_perchip", "otsu_vv_perchip", "otsu_vh_global", "otsu_vv_global", "authors_otsu"]
SELECTED = "otsu_vh_global"
LANDS = ["open_water", "cropland", "vegetation"]
COL = {"open_water": "#1f5fa8", "cropland": "#d9a441", "vegetation": "#3a9d5d"}


def load_metrics(method, split):
    with open(experiments.run_dir("level1", method) / f"metrics_{split}.json") as f:
        return json.load(f)


def scores():
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), sharey="row")
    x = np.arange(len(METHODS))
    w = 0.26
    for col, split in enumerate(("valid", "test")):
        for row, metric in enumerate(("iou", "recall")):
            ax = axes[row, col]
            for i, land in enumerate(LANDS):
                vals = [load_metrics(m, split)[land][metric] for m in METHODS]
                ax.bar(x + (i - 1) * w, vals, w, color=COL[land], label=land.replace("_", " "))
            ax.set_xticks(x)
            ax.set_xticklabels([m.replace("otsu_", "").replace("_", "\n") for m in METHODS], fontsize=9)
            ax.set_ylim(0, 1)
            ax.set_ylabel(metric.upper() if metric == "iou" else metric)
            ax.set_title(f"{split} — {'Spain + Nigeria' if split == 'valid' else 'Mekong (held out)'}")
            ax.axvspan(METHODS.index(SELECTED) - 0.45, METHODS.index(SELECTED) + 0.45, color="#000", alpha=0.06)
            ax.axvspan(METHODS.index("authors_otsu") - 0.45, METHODS.index("authors_otsu") + 0.45, color="#c0392b", alpha=0.06)
            ax.grid(axis="y", alpha=0.3)
    axes[0, 0].legend(loc="upper left", fontsize=9)
    fig.suptitle("Level 1 thresholding, scored per land type (grey = selected on valid; red = dataset cross-check, not a candidate)")
    fig.tight_layout()
    fig.savefig(FIG / "level1_scores.png", dpi=110, bbox_inches="tight")


def brightness():
    z = np.load(experiments.RESULTS / "level1" / "label_brightness_hist.npz")
    with open(experiments.RESULTS / "level1" / "label_brightness.json") as f:
        summ = json.load(f)
    bins = z["bins"]
    centers = (bins[:-1] + bins[1:]) / 2
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.2), sharey=True)
    for ax, split in zip(axes, ("train", "valid", "test")):
        for cls, colr, lab in (("flood", "#1f5fa8", "flooded cropland"), ("dry", "#d9a441", "dry cropland")):
            h = z[f"{split}/cropland/{cls}/vh"].astype(float)
            ax.plot(centers, h / h.sum(), color=colr, lw=2, label=lab)
        r = summ[split]["cropland"]["vh"]
        ax.axvline(r["global_threshold"], color="k", ls="--", lw=1, label=f"global VH threshold {r['global_threshold']:.1f} dB")
        ax.axvline(r["dry_median"], color="#d9a441", ls=":", lw=1)
        ax.set_title(f"{split}: {r['frac_flood_above_threshold']:.1%} of flooded cropland above threshold,\n"
                     f"{r['frac_flood_at_or_above_dry_median']:.1%} at/above dry-cropland median")
        ax.set_xlim(-40, 0)
        ax.set_xlabel("Sentinel-1 VH (dB)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("fraction of pixels (0.5 dB bins)")
    axes[0].legend(fontsize=9)
    fig.suptitle("Is bright (double-bounce) flooded cropland present in the hand labels?")
    fig.tight_layout()
    fig.savefig(FIG / "level1_brightness.png", dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    scores()
    brightness()
    print("wrote", FIG / "level1_scores.png", "and", FIG / "level1_brightness.png")
