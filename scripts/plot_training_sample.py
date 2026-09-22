"""Render an illustrated 6-panel overview of a real training chip.

Shows exactly what data was collected, what channels the AI sees,
and what ground truth labels it was trained against.
"""
import csv
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io, strata

def main():
    # Find a training chip from India or Pakistan with substantial flooded cropland
    with open("docs/level0_inventory.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == "train" and r["event"] in ("India", "Pakistan") and int(r["flood_cropland"]) > 5000]

    rich_chip = sorted(rows, key=lambda r: int(r["flood_cropland"]), reverse=True)[0]["chip"]
    print("Selected training chip:", rich_chip)

    s1, lab, grid = io.read_s1f11_chip(rich_chip)
    s2 = io.read_s1f11_s2(rich_chip)  # Bands 4 (Red), 3 (Green), 2 (Blue)
    wc = io.worldcover_chip(rich_chip, grid)
    land = strata.land_type(wc)
    slope = io.slope_deg(io.dem_chip(rich_chip, grid), grid)

    # Normalize S2 RGB (Bands 4, 3, 2)
    rgb = np.stack([s2[3], s2[2], s2[1]], axis=-1).astype(np.float32)
    rgb = np.clip(rgb / 3000.0, 0, 1)

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    # 1. Optical RGB
    axes[0, 0].imshow(rgb)
    axes[0, 0].set_title("1. Sentinel-2 Optical (True Color RGB)\nWhat human eyes/cameras see", fontsize=11, fontweight="bold")

    # 2. S1 VV
    im_vv = axes[0, 1].imshow(s1[0], cmap="gray", vmin=-22, vmax=0)
    axes[0, 1].set_title("2. Sentinel-1 VV Radar (dB)\nVertical co-pol (sensitive to stalks)", fontsize=11, fontweight="bold")
    fig.colorbar(im_vv, ax=axes[0, 1], fraction=0.046)

    # 3. S1 VH
    im_vh = axes[0, 2].imshow(s1[1], cmap="gray", vmin=-28, vmax=-8)
    axes[0, 2].set_title("3. Sentinel-1 VH Radar (dB)\nCross-pol (sensitive to plant canopies)", fontsize=11, fontweight="bold")
    fig.colorbar(im_vh, ax=axes[0, 2], fraction=0.046)

    # 4. Land Cover (WorldCover)
    land_cmap = ListedColormap(["#1f5fa8", "#e5c07b", "#2ecc71", "#e74c3c", "#95a5a6", "#555555"])
    axes[1, 0].imshow(land, cmap=land_cmap, vmin=0, vmax=5)
    axes[1, 0].set_title("4. ESA WorldCover Land-Type\nYellow=Cropland, Green=Veg, Blue=Water", fontsize=11, fontweight="bold")

    # 5. DEM Slope
    im_sl = axes[1, 1].imshow(slope, cmap="terrain", vmin=0, vmax=15)
    axes[1, 1].set_title("5. Copernicus DEM Terrain Slope (degrees)\nHills vs Flat Lowlands", fontsize=11, fontweight="bold")
    fig.colorbar(im_sl, ax=axes[1, 1], fraction=0.046)

    # 6. Hand Label
    lab_cmap = ListedColormap(["#888888", "#ffffff", "#0984e3"])
    axes[1, 2].imshow(lab + 1, cmap=lab_cmap, vmin=0, vmax=2)
    axes[1, 2].set_title("6. Human Ground Truth Label\nBlue=Flooded, White=Dry, Grey=No Data", fontsize=11, fontweight="bold")

    for ax in axes.ravel():
        ax.set_xticks([])
        ax.set_yticks([])

    fig.suptitle(f"Inside the Training Data: Chip \"{rich_chip}\" (512 x 512 px @ 10m resolution)", fontsize=14, y=0.98, fontweight="bold")
    plt.tight_layout()
    out_path = pathlib.Path("docs/figures/training_sample_illustrated.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print("Saved figure to:", out_path)

if __name__ == "__main__":
    main()
