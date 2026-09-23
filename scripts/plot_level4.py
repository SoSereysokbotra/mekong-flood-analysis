"""Level 4 figures, from the saved maps and area files only.

    docs/figures/level4_flood_map.png    the deliverable: flood extent at the
                                         peak (14 Oct 2020) for each method,
                                         with the pre-event water and the
                                         labelling tiles drawn on top
    docs/figures/level4_timeseries.png   water and flood area by date and method
"""
import json
import pathlib
import sys

import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import MAPS, METHODS, SUFFIX, aoi_grid  # noqa: E402
from level5_change_detection import PEAK, POST, PRE  # noqa: E402

FIG = catalog.ROOT / "docs" / "figures"
NAMES = {"otsu_vh_global": "VH threshold (Level 1)", "unet_vv_ce": "U-Net VV only",
         "unet_vvvh_cropw": "U-Net VV+VH cropland-weighted (selected)"}


def read(path):
    with rasterio.open(path) as src:
        return src.read(1), src.transform


def flood_map():
    grid, inside = aoi_grid()
    with open(experiments.RESULTS / "level4" / f"change_detection{SUFFIX}.json") as f:
        cd = json.load(f)
    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        tiles = json.load(f)["features"]
    from rasterio.warp import transform_geom

    fig, axes = plt.subplots(1, 3, figsize=(19, 7.2))
    cmap = ListedColormap(["#e9e6dd", "#9fc5e8", "#1f5fa8"])  # dry, pre-existing water, new flood
    for ax, method in zip(axes, METHODS):
        pre, _ = read(MAPS / f"{method}_{PRE}{SUFFIX}.tif")
        flood, _ = read(MAPS / f"flood_{method}_{PEAK}{SUFFIX}.tif")
        img = np.zeros(flood.shape, np.uint8)
        img[(pre == 1)] = 1
        img[flood == 1] = 2
        img = np.where(inside, img, 255)
        ax.imshow(np.ma.masked_equal(img, 255), cmap=cmap, vmin=0, vmax=2, interpolation="nearest")
        for t in tiles:
            g = transform_geom("EPSG:4326", grid.crs.to_string(), t["geometry"])
            xs = [p[0] for p in g["coordinates"][0]]
            ys = [p[1] for p in g["coordinates"][0]]
            c0 = (min(xs) - grid.transform.c) / grid.transform.a
            r0 = (max(ys) - grid.transform.f) / grid.transform.e
            w = (max(xs) - min(xs)) / grid.transform.a
            ax.add_patch(Rectangle((c0, r0), w, w, fill=False, ec="#c0392b", lw=0.9))
        s = cd["methods"][method]
        ax.set_title(f"{NAMES[method]}\nflood at peak {s['flood_peak_km2']:,.0f} km² "
                     f"(cropland {s['flood_peak_cropland_km2']:,.0f} km²)", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    handles = [plt.Rectangle((0, 0), 1, 1, fc="#1f5fa8"), plt.Rectangle((0, 0), 1, 1, fc="#9fc5e8"),
               plt.Rectangle((0, 0), 1, 1, fc="#e9e6dd"), plt.Rectangle((0, 0), 1, 1, fc="none", ec="#c0392b")]
    axes[0].legend(handles, ["new flood (14 Oct, not water on 26 Sep)", "water already there on 26 Sep",
                             "dry", "Tier B labelling tiles"], loc="lower left", fontsize=8)
    fig.suptitle("Banteay Meanchey, 14 October 2020 — Sentinel-1 RTC track 164, evaluation plan v1.1 models. "
                 "No hand labels yet: these maps are unscored.", y=0.98)
    fig.tight_layout()
    fig.savefig(FIG / "level4_flood_map.png", dpi=110, bbox_inches="tight")


def timeseries():
    with open(experiments.RESULTS / "level4" / f"areas{SUFFIX}.json") as f:
        areas = json.load(f)
    with open(experiments.RESULTS / "level4" / f"change_detection{SUFFIX}.json") as f:
        cd = json.load(f)
    ref = json.load(open(catalog.DATA / "reference" / "tier_e_reference.json"))
    rice_km2 = next(x for x in ref["figures"] if x["quantity"] == "rice fields inundated" and "Banteay" in x["scope"])["value_km2"]

    dates = [PRE, PEAK, POST]
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6))
    for method in METHODS:
        axes[0].plot(range(3), [areas["methods"][method][d]["water_km2"] for d in dates], "o-", label=NAMES[method])
    axes[0].set_xticks(range(3))
    axes[0].set_xticklabels([f"{d}\n{r}" for d, r in zip(dates, ("pre", "peak", "post"))])
    axes[0].set_ylabel("detected water, km²")
    axes[0].set_title("Total detected water over the province")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    x = np.arange(len(METHODS))
    peak = [cd["methods"][m]["flood_peak_cropland_km2"] for m in METHODS]
    post = [cd["methods"][m]["flood_post_cropland_km2"] for m in METHODS]
    axes[1].bar(x - 0.2, peak, 0.4, color="#1f5fa8", label="14 Oct (peak)")
    axes[1].bar(x + 0.2, post, 0.4, color="#9fc5e8", label="1 Nov (post)")
    axes[1].axhline(rice_km2, color="#c0392b", ls="--", lw=1.2)
    axes[1].text(len(METHODS) - 0.5, rice_km2 * 1.06, f"Tier E report: {rice_km2:.0f} km² rice inundated",
                 ha="right", color="#c0392b", fontsize=8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([NAMES[m].replace(" (", "\n(") for m in METHODS], fontsize=8)
    axes[1].set_ylabel("flood on cropland, km²")
    axes[1].set_title("Flood on cropland vs the reported figure")
    axes[1].grid(axis="y", alpha=0.3)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "level4_timeseries.png", dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    flood_map()
    timeseries()
    print("wrote level4_flood_map.png and level4_timeseries.png")
