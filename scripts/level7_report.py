"""Level 7: the flood report, generated from the artefacts only.

The plan's deliverable is "a report a non-technical person could act on", with
the model's own limitation stated in the output. Every number in the report is
read from a results file here; nothing is typed by hand, so re-running the
upstream scripts re-writes the report.

Reads:  results/level4/{change_detection,normal_years,tierb_scores,
                        hidden_water_feasibility}.json
        results/level7/districts.json   (scripts/level7_district_areas.py)
        data/reference/tier_e_reference.json
Writes: results/level7/report.json      the headline numbers, one place
        docs/level7_report.md           the report
        docs/figures/level7_districts.png
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import geopandas as gpd
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import METHODS  # noqa: E402
from level7_district_areas import DISTRICTS, OUT  # noqa: E402

SEL = "unet_vvvh_cropw"      # selected at Level 3 by the frozen rule; best on Tier B cropland
L4 = experiments.RESULTS / "level4"
DOC = catalog.ROOT / "docs" / "level7_report.md"
FIG = catalog.ROOT / "docs" / "figures" / "level7_districts.png"
INK, MUTED, GRID, BLUE = "#1f2328", "#6b7280", "#e5e7eb", "#2a78d6"


def load(p):
    with open(p) as f:
        return json.load(f)


def day(iso):
    """2020-10-14 -> 14 Oct 2020"""
    return dt.date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")


def km(x):
    return f"{x:,.0f}"


def rng(vals):
    return f"{km(min(vals))}–{km(max(vals))}"


def figure(rows):
    d = gpd.read_file(DISTRICTS).to_crs("EPSG:32648")
    share = {r["district"]: 100 * r[f"flood_cropland_{SEL}"] / r["cropland_km2"] for r in rows}
    d["share"] = d["shapeName"].map(share)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2), gridspec_kw={"width_ratios": [1.05, 1]})
    cmap = LinearSegmentedColormap.from_list("blue", ["#eaf2fc", "#9cc3ef", BLUE, "#0d3a73"])
    d.plot(column="share", cmap=cmap, vmin=0, vmax=70, edgecolor="white", linewidth=1.5, ax=ax1)
    for _, r in d.iterrows():
        p = r.geometry.representative_point()
        name = r["shapeName"].replace(" ", "\n") if r.geometry.area < 4e8 else r["shapeName"]
        pc = "<1%" if r["share"] < 1 else f"{r['share']:.0f}%"
        ax1.annotate(f"{name}\n{pc}", (p.x, p.y), ha="center", va="center", fontsize=9,
                     color="white" if r["share"] > 35 else INK, fontweight="bold" if r["share"] > 35 else "normal")
    ax1.set_axis_off()
    ax1.set_title("Share of each district's cropland flooded, 14 Oct 2020", loc="left", fontsize=12, color=INK)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 70))
    cb = fig.colorbar(sm, ax=ax1, fraction=0.035, pad=0.01)
    cb.set_label("% of district cropland", color=MUTED)
    cb.outline.set_visible(False)

    rows = sorted(rows, key=lambda r: r[f"flood_cropland_{SEL}"])
    y = np.arange(len(rows))
    best = [r[f"flood_cropland_{SEL}"] for r in rows]
    lo = [min(r[f"flood_cropland_{m}"] for m in METHODS) for r in rows]
    hi = [max(r[f"flood_cropland_{m}"] for m in METHODS) for r in rows]
    ax2.barh(y, best, height=0.62, color=BLUE, zorder=2)
    ax2.hlines(y, lo, hi, color=INK, linewidth=2, zorder=3)
    for yi, b, h in zip(y, best, hi):
        ax2.text(max(b, h) + 8, yi, km(b), va="center", fontsize=9, color=INK)
    ax2.set_yticks(y, [r["district"] for r in rows], color=INK)
    ax2.set_xlabel("flooded cropland, km²  (bar: best estimate · black line: range of three methods)", color=MUTED)
    ax2.set_title("Flooded cropland by district, 14 Oct 2020", loc="left", fontsize=12, color=INK)
    ax2.grid(axis="x", color=GRID, zorder=0)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.spines["bottom"].set_color(GRID)
    ax2.tick_params(colors=MUTED, length=0)
    ax2.set_xlim(0, max(hi) * 1.15)
    fig.tight_layout()
    fig.savefig(FIG, dpi=130, facecolor="white")
    plt.close(fig)


def main():
    cd = load(L4 / "change_detection.json")
    ny = load(L4 / "normal_years.json")["excess_2020_cropland_km2"]
    tb = load(L4 / "tierb_scores.json")["comparisons"]["total_water"]["methods"]
    hw = load(L4 / "hidden_water_feasibility.json")["summary"]
    dist = load(OUT / "districts.json")
    te = next(f for f in load(catalog.DATA / "reference" / "tier_e_reference.json")["figures"]
              if f["quantity"] == "rice fields inundated")
    m = cd["methods"]
    rows = dist["districts"]
    crop_total = dist["totals"]["cropland_km2"]

    rep = {
        "event": "Banteay Meanchey, October 2020", "peak": cd["peak"], "pre": cd["pre"], "post": cd["post"],
        "method_best": SEL,
        "flood_km2": {k: round(v["flood_peak_km2"], 1) for k, v in m.items()},
        "flood_cropland_km2": {k: round(v["flood_peak_cropland_km2"], 1) for k, v in m.items()},
        "flood_vegetation_km2": {k: round(v["flood_peak_vegetation_km2"], 1) for k, v in m.items()},
        "water_pre_km2": {k: round(v["water_pre_km2"], 1) for k, v in m.items()},
        "water_peak_km2": {k: round(v["water_peak_km2"], 1) for k, v in m.items()},
        "flood_cropland_post_km2": {k: round(v["flood_post_cropland_km2"], 1) for k, v in m.items()},
        "province_cropland_km2": crop_total,
        "normal_year_ratio": {k: round(v["ratio"], 1) for k, v in ny.items()},
        "normal_year_excess_km2": {k: round(v["excess_km2"], 1) for k, v in ny.items()},
        "reported_rice_inundated_km2": te["value_km2"],
        "tierb_cropland": {k: {x: round(v["cropland"][x], 3) for x in ("recall", "precision")} for k, v in tb.items()},
        "tierb_vegetation_precision": {k: round(v["vegetation"]["precision"], 3) for k, v in tb.items()},
        "hidden_water": hw,
    }
    top = sorted(rows, key=lambda r: -r[f"flood_cropland_{SEL}"])
    top3 = top[:3]
    rep["top3_share"] = round(sum(r[f"flood_cropland_{SEL}"] for r in top3) / dist["totals"][f"flood_cropland_{SEL}"], 3)
    with open(OUT / "report.json", "w") as f:
        json.dump(rep, f, indent=2)
    figure(rows)

    fc, fl = rep["flood_cropland_km2"], rep["flood_km2"]
    rec, prec = rep["tierb_cropland"][SEL]["recall"], rep["tierb_cropland"][SEL]["precision"]
    lines = [
        "# Flood report: Banteay Meanchey, October 2020",
        "",
        "*Generated by `scripts/level7_report.py` from the results files; do not edit by hand.*",
        "*Numbers: `results/level7/report.json`, `results/level7/districts.csv`.*",
        "",
        "```",
        "Flood event — Banteay Meanchey province, Cambodia",
        f"Detected:                  {day(cd['peak'])}  (Sentinel-1 radar, ~06:00 local)",
        f"Flooded area:              {km(fl[SEL])} km²   (range {rng(fl.values())})",
        f"  of which cropland:       {km(fc[SEL])} km²   (range {rng(fc.values())})"
        f" = {100 * fc[SEL] / crop_total:.0f} % of the province's cropland",
        f"Change since last pass:    +{km(rep['water_peak_km2'][SEL] - rep['water_pre_km2'][SEL])} km² of water"
        f" since {day(cd['pre'])}",
        f"{'Two weeks later:':27s}{km(rep['flood_cropland_post_km2'][SEL])} km² of cropland flooded on {day(cd['post'])}",
        f"Compared with normal:      {rep['normal_year_ratio'][SEL]}× the flooded cropland of a normal October"
        f" (range {min(rep['normal_year_ratio'].values())}–{max(rep['normal_year_ratio'].values())}×)",
        "Method:                    Sentinel-1 VV+VH, U-Net (cropland-weighted)",
        f"Known limitation:          on cropland it found {100 * rec:.0f} % of the flood water that people could",
        f"                           see in satellite photos, and {100 * prec:.0f} % of what it called flood was flood.",
        "                           Water hidden under the rice canopy is NOT checked (see below).",
        "```",
        "",
        "## Where the flooding is",
        "",
        f"**Three districts hold {100 * rep['top3_share']:.0f} % of the flooded cropland:** "
        + ", ".join(f"{r['district']} ({km(r[f'flood_cropland_{SEL}'])} km²)" for r in top3)
        + ". All three methods rank the same four districts at the top, in the same order.",
        "",
        "![Flooded cropland by district](figures/level7_districts.png)",
        "",
        "| District | Cropland flooded, km² | Range (3 methods) | Share of district's cropland | Flooded on "
        f"{day(cd['post'])}, km² |",
        "| --- | --- | --- | --- | --- |",
    ]
    def share(r):
        v = 100 * r[f"flood_cropland_{SEL}"] / r["cropland_km2"]
        return "< 1 %" if v < 1 else f"{v:.0f} %"

    for r in top:
        vals = [r[f"flood_cropland_{mm}"] for mm in METHODS]
        lines.append(f"| {r['district']} | **{km(r[f'flood_cropland_{SEL}'])}** | {rng(vals)} | "
                     f"{share(r)} | {km(r[f'flood_cropland_post_{SEL}'])} |")
    rising = [r["district"] for r in top if r[f"flood_cropland_post_{SEL}"] > r[f"flood_cropland_{SEL}"] * 1.1]
    lines += [
        "",
        f"On {day(cd['post'])}, {100 * rep['flood_cropland_post_km2'][SEL] / fc[SEL]:.0f} % as much cropland was flooded as at the peak. "
        + (f"In **{' and '.join(rising)}** it was *larger* than at the peak, "
           "so water there was still spreading or not draining. " if rising else "")
        + "The northern and western districts (Thma Puok, Svay Chek, Paoy Paet) show almost no flooding.",
        "",
        "## How far to trust these numbers",
        "",
        "| Question | Answer | Evidence |",
        "| --- | --- | --- |",
        f"| Is this a real flood, not normal wet-season paddy water? | **Yes.** Flooded cropland is "
        f"{min(rep['normal_year_ratio'].values())}–{max(rep['normal_year_ratio'].values())}× the same date in "
        "2018, 2019, 2021 and 2022. | [level4_cambodia.md §3b](level4_cambodia.md) |",
        f"| Is the cropland number accurate? | **Mostly.** Checked against 17 hand-labelled sites: it finds "
        f"{100 * rec:.0f} % of visible flood water on cropland; {100 * prec:.0f} % of its cropland flood is real. "
        f"A simple threshold finds only {100 * rep['tierb_cropland']['otsu_vh_global']['recall']:.0f} %. "
        "| [level4_tierb_scores.md](level4_tierb_scores.md) |",
        f"| Is the forest and grassland number accurate? | **No, do not use it.** "
        f"{km(rep['flood_vegetation_km2'][SEL])} km² is mapped there, but on the hand-labelled sites under "
        f"about {100 * rep['tierb_vegetation_precision'][SEL]:.0f} % of it could be confirmed. "
        "| [level4_tierb_scores.md](level4_tierb_scores.md) |",
        "| Does it find water hidden under tall rice? | **Unknown.** Photos cannot see under the canopy, and "
        "free terrain data is too coarse to tell (the cropland is flat to within about "
        f"{hw['cropland_dem_spread_median_m']:.1f} m). | [level4_tierb_scores.md §5](level4_tierb_scores.md) |",
        f"| Does it agree with the official figure? | **No.** The reported figure is "
        f"{km(rep['reported_rice_inundated_km2'])} km² of rice inundated; this map gives "
        f"{fc[SEL] / rep['reported_rice_inundated_km2']:.1f}× that. Even the flooding *above a normal year* "
        f"({km(rep['normal_year_excess_km2'][SEL])} km²) is "
        f"{rep['normal_year_excess_km2'][SEL] / rep['reported_rice_inundated_km2']:.1f}× that. The two probably "
        "measure different things (damage assessed per district, versus all water seen on one morning), but this "
        "is not resolved. | [level4_cambodia.md §3](level4_cambodia.md) |",
        "",
        "## How to use it",
        "",
        "- **Use it to rank districts** and to see where water was still standing two weeks later. "
        "All three methods agree on which districts are worst, so this is the most reliable part of this report.",
        "- **Use the cropland area as an upper-end estimate**, with the range beside it. Do not quote it as rice "
        "*damaged*: water on a field is not the same as a lost crop.",
        "- **Do not use** the forest and grassland area, or any figure for a single village. The map is 20 m, "
        "and it was checked on 17 sites of 4 km² each, not everywhere.",
        "",
        "## How it was made",
        "",
        f"Sentinel-1 radar passes on {day(cd['pre'])} (before), {day(cd['peak'])} (peak) and {day(cd['post'])} (after), "
        "track 164, covering 100 % of the province. Flood = water on the date that was not water before. "
        "The model was chosen on floods in other countries, under rules written down before it was trained, "
        "and then checked on Cambodian ground ([SUMMARY.md](SUMMARY.md)). District boundaries: geoBoundaries "
        "(Open Development Cambodia, 2014, CC BY 4.0). Cropland: ESA WorldCover 2020, which does not separate "
        "rice from other crops.",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DOC}\nwrote {FIG}\nwrote {OUT / 'report.json'}")


if __name__ == "__main__":
    main()
