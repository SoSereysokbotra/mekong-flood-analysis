"""Level 2 figures, generated only from saved artefacts:
    results/level2/failure_taxonomy.json, failure_per_chip.csv, joint_hist.npz, separability.json
    results/level1/otsu_vh_global/pred/<chip>.tif  (for the example panels)

Outputs:
    docs/figures/level2_taxonomy.png   FP / FN categories per split
    docs/figures/level2_joint.png      2-D (VV, VH) density of flooded vs dry cropland, train vs test
    docs/figures/level2_examples.png   one example chip per failure type: VH, label, prediction, error map
"""
import csv
import json
import pathlib
import sys

import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap, LogNorm  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io, strata  # noqa: E402

FIG = catalog.ROOT / "docs" / "figures"
R2 = experiments.RESULTS / "level2"


def taxonomy():
    with open(R2 / "failure_taxonomy.json") as f:
        t = json.load(f)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    for ax, kind, cats in ((axes[0], "fp", t["fp_categories"]), (axes[1], "fn", t["fn_categories"])):
        x = np.arange(len(cats))
        for i, s in enumerate(("train", "valid", "test")):
            tot = max(t["splits"][s][f"{kind}_total"], 1)
            vals = [100 * t["splits"][s][c] / tot for c in cats]
            ax.bar(x + (i - 1) * 0.27, vals, 0.27, label=f"{s} ({t['splits'][s][f'{kind}_total']:,} px)")
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace(f"{kind}_", "").replace("_", "\n") for c in cats], fontsize=8)
        ax.set_ylabel(f"% of {kind.upper()} pixels")
        ax.set_title("False positives: predicted water, labelled dry" if kind == "fp" else "False negatives: labelled water, predicted dry")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle(f"Where the baseline ({t['baseline']}, VH < {t['vh_threshold']} dB) fails — slope ≥ {t['slope_deg']}° = terrain")
    fig.tight_layout()
    fig.savefig(FIG / "level2_taxonomy.png", dpi=110, bbox_inches="tight")


def joint():
    z = np.load(R2 / "joint_hist.npz")
    with open(R2 / "separability.json") as f:
        sep = json.load(f)
    with open(experiments.run_dir("level1", "_global_thresholds") / "config.json") as f:
        gt = json.load(f)
    e = z["edges"]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), sharex=True, sharey=True)
    for col, s in enumerate(("train", "valid", "test")):
        for row, cls in enumerate(("flood", "dry")):
            ax = axes[row, col]
            H = z[f"{s}/{cls}"].astype(float)
            ax.pcolormesh(e, e, H.T, norm=LogNorm(vmin=1, vmax=max(H.max(), 2)), cmap="viridis")
            ax.axhline(gt["vh"], color="w", ls="--", lw=1)
            ax.axvline(gt["vv"], color="w", ls=":", lw=1)
            ax.set_title(f"{s}: {'flooded' if cls == 'flood' else 'dry'} cropland  (n={int(H.sum()):,})", fontsize=10)
            if row == 1:
                ax.set_xlabel("VV (dB)")
            if col == 0:
                ax.set_ylabel("VH (dB)")
        a = sep[s]
        axes[0, col].text(-39, 3, f"bright-flooded vs dry AUC:\nVV {a['auc_vv_darker']:.2f}  VH {a['auc_vh_darker']:.2f}  VV−VH {a['auc_vv_minus_vh_higher']:.2f}",
                          color="w", fontsize=8, va="top")
    fig.suptitle("Joint VV/VH density of cropland pixels (dashed = VH threshold, dotted = VV threshold)")
    fig.tight_layout()
    fig.savefig(FIG / "level2_joint.png", dpi=110, bbox_inches="tight")


def examples():
    with open(R2 / "failure_per_chip.csv") as f:
        rows = list(csv.DictReader(f))
    picks = [
        ("fp_terrain", "FP: terrain shadow"),
        ("fp_dry_cropland", "FP: dark dry cropland"),
        ("fn_bright_cropland", "FN: bright flooded cropland"),
        ("fn_rough_open_water", "FN: rough open water"),
    ]
    pred_dir = experiments.run_dir("level1", "otsu_vh_global") / "pred"
    fig, axes = plt.subplots(len(picks), 4, figsize=(16, 4 * len(picks)))
    err_cmap = ListedColormap(["#f4f1e8", "#1f5fa8", "#c0392b", "#d9a441"])  # TN, TP, FP, FN
    for r, (cat, title) in enumerate(picks):
        best = max((x for x in rows if x["split"] != "test"), key=lambda x: int(x[cat]))  # examples from train/valid only
        chip = best["chip"]
        s1, lab, grid = io.read_s1f11_chip(chip)
        with rasterio.open(pred_dir / f"{chip}.tif") as src:
            pred = src.read(1).astype(bool)
        valid = lab >= 0
        err = np.zeros(lab.shape, np.int8)
        err[pred & (lab == 1)] = 1
        err[pred & (lab == 0)] = 2
        err[~pred & (lab == 1)] = 3
        axes[r, 0].imshow(s1[1], cmap="gray", vmin=-30, vmax=-5)
        axes[r, 0].set_title(f"{chip} — VH")
        axes[r, 1].imshow(lab + 1, cmap=ListedColormap(["#888", "#f4f1e8", "#1f5fa8"]), vmin=0, vmax=2)
        axes[r, 1].set_title("hand label")
        if cat == "fp_terrain":
            axes[r, 2].imshow(io.slope_deg(io.dem_chip(chip, grid), grid), cmap="magma", vmin=0, vmax=25)
            axes[r, 2].set_title("slope (deg)")
        else:
            axes[r, 2].imshow(strata.land_type(io.worldcover_chip(chip, grid)), cmap="tab10", vmin=0, vmax=9)
            axes[r, 2].set_title("land type")
        axes[r, 3].imshow(np.where(valid, err, 0), cmap=err_cmap, vmin=0, vmax=3)
        axes[r, 3].set_title(f"{title}  ({int(best[cat]):,} px)   red = FP, yellow = FN, blue = TP")
        for a in axes[r]:
            a.set_xticks([])
            a.set_yticks([])
    fig.tight_layout()
    fig.savefig(FIG / "level2_examples.png", dpi=90, bbox_inches="tight")


if __name__ == "__main__":
    taxonomy()
    joint()
    examples()
    print("wrote level2_taxonomy.png, level2_joint.png, level2_examples.png")
