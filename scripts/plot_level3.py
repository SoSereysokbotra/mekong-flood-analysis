"""Level 3 figures, generated only from saved artefacts:
    results/level3/<run>/metrics_valid.json, metrics_test.json, per_chip_test.csv, history.json

Outputs:
    docs/figures/level3_test.png       selected model vs controls vs Level 1 thresholds on the held-out Mekong split
    docs/figures/level3_valid.png      every run's valid selection score with its last-10-epoch spread
    docs/figures/level3_per_chip.png   per-chip bright-cropland recall on test, selected model vs VV-only control
"""
import csv
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
R3 = experiments.RESULTS / "level3"
R1 = experiments.RESULTS / "level1"
SELECTED = "unet_vvvh_cropw"


def load(level_dir, run, split):
    with open(level_dir / run / f"metrics_{split}.json") as f:
        return json.load(f)


def test_bars():
    runs = [("otsu_vh_global", R1, "Level 1 baseline\n(VH threshold)"), ("otsu_vv_global", R1, "VV threshold"),
            ("pixel_logreg", R3, "per-pixel\nlogreg"), ("pixel_mlp", R3, "per-pixel\nMLP"),
            ("unet_vv_ce", R3, "U-Net\nVV only"), (SELECTED, R3, "U-Net VV+VH\ncropland-weighted\n(selected)")]
    groups = [("cropland_bright", "recall", "bright cropland recall (B)"), ("vegetation_bright", "recall", "bright vegetation recall (V)"),
              ("cropland", "precision", "cropland precision (P)"), ("all", "iou", "all IoU (I)"), ("cropland_dark", "recall", "dark cropland recall (D)")]
    thresholds = {"cropland_bright": 0.50, "vegetation_bright": 0.50, "cropland": 0.75, "all": 0.765, "cropland_dark": 0.95}
    fig, axes = plt.subplots(1, len(groups), figsize=(22, 5), sharey=True)
    x = np.arange(len(runs))
    for ax, (g, k, title) in zip(axes, groups):
        vals = [load(d, r, "test")[g][k] for r, d, _ in runs]
        cols = ["#7f8c8d", "#7f8c8d", "#c0392b", "#c0392b", "#d9a441", "#1f5fa8"]
        ax.bar(x, vals, color=cols)
        ax.axhline(thresholds[g], color="k", ls="--", lw=1)
        ax.text(len(runs) - 0.5, thresholds[g] + 0.01, f"frozen bar {thresholds[g]}", ha="right", fontsize=8)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.01, f"{v:.2f}", ha="center", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels([n for _, _, n in runs], fontsize=7, rotation=20)
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Held-out Mekong test (30 chips, scored once): selected model vs controls vs thresholds — evaluation_plan v1.0 §7")
    fig.tight_layout()
    fig.savefig(FIG / "level3_test.png", dpi=110, bbox_inches="tight")


def valid_scores():
    runs = sorted([d.name for d in R3.iterdir() if d.is_dir() and not d.name.startswith("_") and (d / "metrics_valid.json").exists()],
                  key=lambda r: -min(load(R3, r, "valid")["cropland_bright"]["recall"], load(R3, r, "valid")["vegetation_bright"]["recall"]))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for i, r in enumerate(runs):
        m = load(R3, r, "valid")
        sc = min(m["cropland_bright"]["recall"], m["vegetation_bright"]["recall"])
        ok = m["cropland"]["precision"] >= 0.48
        ax.bar(i, sc, color="#1f5fa8" if r == SELECTED else ("#d9a441" if ok else "#c0392b"))
        hp = R3 / r / "history.json"
        if hp.exists():
            with open(hp) as f:
                h = json.load(f)
            s = [e["valid_score"] for e in h[-10:]]
            ax.plot([i, i], [min(s), max(s)], color="k", lw=2)
        ax.text(i, sc + 0.01, f"{sc:.2f}\nP {m['cropland']['precision']:.2f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(runs)))
    ax.set_xticklabels(runs, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("valid selection score = min(bright cropland, bright vegetation) recall")
    ax.set_title("Selection on valid (Spain + Nigeria). Black bar = spread of the score over the last 10 epochs; blue = selected")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "level3_valid.png", dpi=110, bbox_inches="tight")


def per_chip():
    def rows(run):
        with open(R3 / run / "per_chip_test.csv") as f:
            return {r["chip"]: r for r in csv.DictReader(f)}
    a, b = rows(SELECTED), rows("unet_vv_ce")
    chips = [c for c in a if float(a[c]["cropland_bright_n_pos"]) > 500]
    chips.sort(key=lambda c: -float(a[c]["cropland_bright_n_pos"]))
    fig, ax = plt.subplots(figsize=(11, 4.2))
    x = np.arange(len(chips))
    ax.bar(x - 0.2, [float(a[c]["cropland_bright_recall"]) for c in chips], 0.4, color="#1f5fa8", label="U-Net VV+VH cropland-weighted (selected)")
    ax.bar(x + 0.2, [float(b[c]["cropland_bright_recall"]) for c in chips], 0.4, color="#d9a441", label="U-Net VV only (control)")
    ax.axhline(0.5, color="k", ls="--", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c.split('_')[1]}\n{int(float(a[c]['cropland_bright_n_pos'])):,}" for c in chips], fontsize=7)
    ax.set_xlabel("Mekong chip id and number of bright flooded-cropland pixels")
    ax.set_ylabel("bright cropland recall")
    ax.set_title("Per-chip bright-cropland recall on test (chips with > 500 bright px)")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "level3_per_chip.png", dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    test_bars()
    valid_scores()
    per_chip()
    print("wrote level3_test.png, level3_valid.png, level3_per_chip.png")
