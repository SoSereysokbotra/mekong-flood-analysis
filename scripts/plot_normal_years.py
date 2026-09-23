"""Figure for the seasonal baseline: is October 2020 anomalous, and in what?

Left  : water detected on each year's mid-October pass (the state).
Right : October water minus that year's late-September water (the change) -
        what Level 4 calls "flood", with the Tier E report for scale.

Built only from results/level4/normal_years.json.
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
NAMES = {"otsu_vh_global": "VH threshold", "unet_vv_ce": "U-Net VV only",
         "unet_vvvh_cropw": "U-Net VV+VH cropw (selected)"}
COL = {"otsu_vh_global": "#7f8c8d", "unet_vv_ce": "#d9a441", "unet_vvvh_cropw": "#1f5fa8"}


def main():
    with open(experiments.RESULTS / "level4" / "normal_years.json") as f:
        d = json.load(f)
    ref = json.load(open(catalog.DATA / "reference" / "tier_e_reference.json"))
    rice = next(x for x in ref["figures"] if x["quantity"] == "rice fields inundated" and "Banteay" in x["scope"])["value_km2"]
    years = sorted(d["years"])
    x = np.arange(len(years))

    fig, axes = plt.subplots(1, 3, figsize=(17, 4.6))
    for m in NAMES:
        axes[0].plot(x, [d["years"][y]["methods"][m]["water_october_km2"] for y in years], "o-", color=COL[m], label=NAMES[m])
        axes[1].plot(x, [d["years"][y]["methods"][m]["water_pre_km2"] for y in years], "o-", color=COL[m])
        axes[2].bar(x + (list(NAMES).index(m) - 1) * 0.27,
                    [d["years"][y]["methods"][m]["flood_cropland_km2"] for y in years], 0.27, color=COL[m])
    for ax, title, ylab in (
        (axes[0], "Water on the mid-October pass\n(the state: 2020 is not the wettest October)", "detected water, km²"),
        (axes[1], "Water on the late-September pass\n(the baseline each year is measured against)", "detected water, km²"),
        (axes[2], "Flood on cropland = October minus September\n(the change: this is where 2020 stands out)", "flood on cropland, km²"),
    ):
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylab)
        ax.grid(axis="y", alpha=0.3)
        ax.axvline(years.index("2020"), color="#c0392b", lw=1, alpha=0.4)
    axes[2].axhline(rice, color="#c0392b", ls="--", lw=1.2)
    axes[2].text(len(years) - 0.4, rice * 1.05, f"Tier E report {rice:.0f} km²", ha="right", color="#c0392b", fontsize=8)
    axes[0].legend(fontsize=8)
    fig.suptitle("Banteay Meanchey, same track (164 descending), same models, same processing, 2018–2022", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG / "level4_normal_years.png", dpi=110, bbox_inches="tight")
    print("wrote", FIG / "level4_normal_years.png")


if __name__ == "__main__":
    main()
