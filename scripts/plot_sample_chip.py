"""Render the Level 0 figure: VV, VH, hand label and land type for one chip,
plus per-class backscatter medians printed to stdout.

Default chip is the Mekong chip with the most flooded cropland according to
docs/level0_inventory.csv (run scripts/level0_inventory.py first).

Usage:
    python scripts/plot_sample_chip.py                 # -> docs/figures/level0_mekong_chip.png
    python scripts/plot_sample_chip.py Mekong_1111068  # any chip id
"""
import csv
import pathlib
import sys

import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io, strata  # noqa: E402

FIG_DIR = catalog.ROOT / "docs" / "figures"
WC_DIR = catalog.DATA / "interim" / "worldcover_chips"


def richest_mekong_chip() -> str:
    with open(catalog.ROOT / "docs" / "level0_inventory.csv") as f:
        rows = [r for r in csv.DictReader(f) if r["event"] == "Mekong"]
    return max(rows, key=lambda r: int(r["flood_cropland"]))["chip"]


def main(chip: str | None):
    chip = chip or richest_mekong_chip()
    s1, lab, grid = io.read_s1f11_chip(chip)
    with rasterio.open(WC_DIR / f"{chip}_WorldCover2020.tif") as src:
        wc = src.read(1)
    land = strata.land_type(wc)
    n_crop = int(((lab == 1) & (land == strata.CROPLAND)).sum())

    fig, ax = plt.subplots(1, 4, figsize=(18, 5))
    for a, arr, title, vmin, vmax in [
        (ax[0], s1[0], "Sentinel-1 VV (dB)", -25, 5),
        (ax[1], s1[1], "Sentinel-1 VH (dB)", -30, -5),
    ]:
        im = a.imshow(arr, cmap="gray", vmin=vmin, vmax=vmax)
        a.set_title(title)
        fig.colorbar(im, ax=a, fraction=0.046)
    ax[2].imshow(lab + 1, cmap=ListedColormap(["#888888", "#f4f1e8", "#1f5fa8"]), vmin=0, vmax=2)
    ax[2].set_title("Hand label (blue = water, grey = no data)")
    # land type shown only where flooded, so the eye reads "what kind of flood"
    shown = np.where(lab == 1, land + 1, np.where(lab == 0, 0, 7)).astype(np.int8)
    cmap = ListedColormap(["#f4f1e8", "#1f5fa8", "#d9a441", "#3a9d5d", "#c0392b", "#7f8c8d", "#bbbbbb", "#888888"])
    ax[3].imshow(shown, cmap=cmap, vmin=0, vmax=7)
    ax[3].set_title("Flood by land type (yellow = cropland,\ngreen = vegetation, blue = open water)")
    for a in ax:
        a.set_xticks([])
        a.set_yticks([])
    fig.suptitle(f"Sen1Floods11 {chip} — flooded cropland {n_crop:,} px", y=1.0)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / ("level0_mekong_chip.png" if chip.startswith("Mekong") else f"level0_{chip}.png")
    fig.savefig(out, dpi=110, bbox_inches="tight")
    print("wrote", out)

    print(f"\n{chip}: median backscatter per class")
    for name, m in [
        ("flooded cropland", (lab == 1) & (land == strata.CROPLAND)),
        ("dry cropland", (lab == 0) & (land == strata.CROPLAND)),
        ("flooded open water", (lab == 1) & (land == strata.OPEN_WATER)),
        ("flooded vegetation", (lab == 1) & (land == strata.VEGETATION)),
        ("dry vegetation", (lab == 0) & (land == strata.VEGETATION)),
    ]:
        if m.sum():
            print(f"  {name:20s} n={m.sum():7d}  VV {np.median(s1[0][m]):6.1f} dB  VH {np.median(s1[1][m]):6.1f} dB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
