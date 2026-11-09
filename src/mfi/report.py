"""Level 7 report and district area calculations.

Moved from scripts/level7_district_areas.py and scripts/level7_report.py into the library.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib

import geopandas as gpd
import matplotlib
import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from rasterio.features import rasterize

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from mfi import catalog, experiments, strata
from mfi.aoi import CACHE, DISTRICTS, METHODS, SUFFIX, aoi_grid

NAMES = {
    "otsu_vh_global": "the VH threshold",
    "unet_vv_ce": "the VV-only U-Net",
    "unet_vvvh_cropw": "the selected U-Net",
}

SEL = "unet_vvvh_cropw"      # selected at Level 3 by the frozen rule; best on Tier B cropland
L4 = experiments.RESULTS / "level4"
OUT = experiments.RESULTS / "level7"
DOC = catalog.ROOT / "docs" / "level7_report.md"
FIG = catalog.ROOT / "docs" / "figures" / "level7_districts.png"
MAPS = experiments.RESULTS / "level4" / "maps"

PRE = "2020-09-26"
PEAK = "2020-10-14"
POST = "2020-11-01"

INK, MUTED, GRID, BLUE = "#1f2328", "#6b7280", "#e5e7eb", "#2a78d6"


def read_raster_mask(path: pathlib.Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1) == 1


def compute_district_areas(
    cache_dir: pathlib.Path = CACHE,
    maps_dir: pathlib.Path = MAPS,
    districts_path: pathlib.Path = DISTRICTS,
    suffix: str = SUFFIX,
) -> tuple[dict, list[dict], dict]:
    """Compute per-district flood and cropland flood areas from saved Level 4 maps."""
    grid, inside = aoi_grid()
    px_km2 = abs(grid.transform.a) ** 2 / 1e6
    land = np.load(cache_dir / f"ancillary{suffix}.npz")["land"]
    crop = land == strata.CROPLAND
    d = gpd.read_file(districts_path).to_crs(grid.crs).sort_values("shapeName").reset_index(drop=True)
    dist = rasterize(((g, i + 1) for i, g in enumerate(d.geometry)), out_shape=inside.shape,
                     transform=grid.transform, dtype="uint8")
    dist = np.where(inside, dist, 0)
    unassigned = inside & (dist == 0)

    maps = {m: {"peak": read_raster_mask(maps_dir / f"flood_{m}_{PEAK}{suffix}.tif"),
                "post": read_raster_mask(maps_dir / f"flood_{m}_{POST}{suffix}.tif")} for m in METHODS}

    rows = []
    for i, name in enumerate(d["shapeName"]):
        z = dist == i + 1
        r = {"district": name, "area_km2": round(float(z.sum() * px_km2), 1),
             "cropland_km2": round(float((z & crop).sum() * px_km2), 1)}
        for m in METHODS:
            r[f"flood_{m}"] = round(float((z & maps[m]["peak"]).sum() * px_km2), 1)
            r[f"flood_cropland_{m}"] = round(float((z & crop & maps[m]["peak"]).sum() * px_km2), 1)
            r[f"flood_cropland_post_{m}"] = round(float((z & crop & maps[m]["post"]).sum() * px_km2), 1)
        rows.append(r)

    totals = {k: round(sum(r[k] for r in rows), 1) for k in rows[0] if k != "district"}
    summary = {
        "peak": PEAK,
        "post": POST,
        "res_m": abs(grid.transform.a),
        "districts_source": "geoBoundaries KHM ADM2 (Open Development Cambodia 2014, CC BY 4.0)",
        "unassigned_km2": round(float(unassigned.sum() * px_km2), 2),
        "totals": totals,
        "districts": rows,
    }
    return summary, rows, totals


def write_district_areas(summary: dict, rows: list[dict], out_dir: pathlib.Path = OUT):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "districts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out_dir / "districts.json", "w") as f:
        json.dump(summary, f, indent=2)


def run_district_areas(
    cache_dir: pathlib.Path = CACHE,
    maps_dir: pathlib.Path = MAPS,
    districts_path: pathlib.Path = DISTRICTS,
    out_dir: pathlib.Path = OUT,
    suffix: str = SUFFIX,
):
    summary, rows, totals = compute_district_areas(
        cache_dir=cache_dir,
        maps_dir=maps_dir,
        districts_path=districts_path,
        suffix=suffix,
    )
    write_district_areas(summary, rows, out_dir=out_dir)

    sel = "unet_vvvh_cropw"
    print(f"{'district':18s} {'crop km2':>8s} {'flooded crop (thr / vv / sel)':>30s} {'% crop':>7s} {'1 Nov':>6s}")
    for r in sorted(rows, key=lambda r: -r[f"flood_cropland_{sel}"]):
        print(f"{r['district']:18s} {r['cropland_km2']:8.0f} "
              f"{r['flood_cropland_otsu_vh_global']:9.0f} / {r['flood_cropland_unet_vv_ce']:6.0f} / "
              f"{r[f'flood_cropland_{sel}']:6.0f} {100 * r[f'flood_cropland_{sel}'] / r['cropland_km2']:6.1f}% "
              f"{r[f'flood_cropland_post_{sel}']:6.0f}")
    unassigned_km2 = summary["unassigned_km2"]
    print(f"\ntotals: {totals}\nunassigned (province edge vs district edge): {unassigned_km2:.2f} km2")


def load_json(p: pathlib.Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def day(iso: str) -> str:
    """2020-10-14 -> 14 Oct 2020"""
    return dt.date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")


def km(x: float | int) -> str:
    return f"{x:,.0f}"


def rng(vals) -> str:
    return f"{km(min(vals))}–{km(max(vals))}"


def generate_district_figure(
    rows: list[dict],
    districts_path: pathlib.Path = DISTRICTS,
    fig_path: pathlib.Path = FIG,
):
    d = gpd.read_file(districts_path).to_crs("EPSG:32648")
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

    rows_sorted = sorted(rows, key=lambda r: r[f"flood_cropland_{SEL}"])
    y = np.arange(len(rows_sorted))
    best = [r[f"flood_cropland_{SEL}"] for r in rows_sorted]
    lo = [min(r[f"flood_cropland_{m}"] for m in METHODS) for r in rows_sorted]
    hi = [max(r[f"flood_cropland_{m}"] for m in METHODS) for r in rows_sorted]
    ax2.barh(y, best, height=0.62, color=BLUE, zorder=2)
    ax2.hlines(y, lo, hi, color=INK, linewidth=2, zorder=3)
    for yi, b, h in zip(y, best, hi):
        ax2.text(max(b, h) + 8, yi, km(b), va="center", fontsize=9, color=INK)
    ax2.set_yticks(y, [r["district"] for r in rows_sorted], color=INK)
    ax2.set_xlabel("flooded cropland, km²  (bar: best estimate · black line: range of three methods)", color=MUTED)
    ax2.set_title("Flooded cropland by district, 14 Oct 2020", loc="left", fontsize=12, color=INK)
    ax2.grid(axis="x", color=GRID, zorder=0)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.spines["bottom"].set_color(GRID)
    ax2.tick_params(colors=MUTED, length=0)
    ax2.set_xlim(0, max(hi) * 1.15)
    fig.tight_layout()
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=130, facecolor="white")
    plt.close(fig)


def build_report_data(
    cd: dict,
    nyf: dict,
    tb: dict,
    hw: dict,
    dist: dict,
    te_val: float,
) -> dict:
    m = cd["methods"]
    ny = nyf["excess_2020_cropland_km2"]
    crop_total = dist["totals"]["cropland_km2"]
    rows = dist["districts"]

    rep = {
        "event": "Banteay Meanchey, October 2020", "peak": cd["peak"], "pre": cd["pre"], "post": cd["post"],
        "method_best": SEL,
        "flood_km2": {k: round(v["flood_peak_km2"], 3) for k, v in m.items()},
        "flood_cropland_km2": {k: round(v["flood_peak_cropland_km2"], 3) for k, v in m.items()},
        "flood_vegetation_km2": {k: round(v["flood_peak_vegetation_km2"], 3) for k, v in m.items()},
        "water_pre_km2": {k: round(v["water_pre_km2"], 3) for k, v in m.items()},
        "water_peak_km2": {k: round(v["water_peak_km2"], 3) for k, v in m.items()},
        "flood_cropland_post_km2": {k: round(v["flood_post_cropland_km2"], 3) for k, v in m.items()},
        "province_cropland_km2": crop_total,
        "normal_year_ratio": {k: round(v["ratio"], 1) for k, v in ny.items()},
        "normal_year_excess_km2": {k: round(v["excess_km2"], 3) for k, v in ny.items()},
        "reported_rice_inundated_km2": te_val,
        "tierb_cropland": {k: {x: round(v["cropland"][x], 3) for x in ("recall", "precision")} for k, v in tb.items()},
        "tierb_vegetation_precision": {k: round(v["vegetation"]["precision"], 3) for k, v in tb.items()},
        "hidden_water": hw,
        "unassigned_km2": dist["unassigned_km2"],
        # of the peak flood, how much was still water on the post date, and how much is new since the peak
        "peak_flood_persisting_km2": round(m[SEL]["flood_peak_km2"] - m[SEL]["drained_by_post_km2"], 3),
        "flood_new_after_peak_km2": round(m[SEL]["flood_post_km2"] - (m[SEL]["flood_peak_km2"]
                                                                     - m[SEL]["drained_by_post_km2"]), 3),
    }
    # any normal year that one method finds nearly as flooded as 2020 must be named, not averaged away
    rep["normal_year_exceptions"] = [
        {"method": k, "year": y, "flood_cropland_km2": round(v["methods"][k]["flood_cropland_km2"], 1),
         "event_km2": round(ny[k]["event"], 1)}
        for y, v in nyf["years"].items() if y != "2020" for k in METHODS
        if v["methods"][k]["flood_cropland_km2"] >= 0.8 * ny[k]["event"]]
    top = sorted(rows, key=lambda r: -r[f"flood_cropland_{SEL}"])
    top3 = top[:3]
    rep["top3_share"] = round(sum(r[f"flood_cropland_{SEL}"] for r in top3) / dist["totals"][f"flood_cropland_{SEL}"], 3)
    return rep


def render_report_markdown(rep: dict, rows: list[dict], crop_total: float, cd: dict) -> str:
    top = sorted(rows, key=lambda r: -r[f"flood_cropland_{SEL}"])
    top3 = top[:3]
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
        f"Compared with normal:      {rep['normal_year_ratio'][SEL]}× the median of four other Octobers"
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
        f"The last column is all water on {day(cd['post'])} that was not there before the flood. "
        f"It is not the same water as at the peak: across the province, {km(rep['peak_flood_persisting_km2'])} km² "
        f"of the peak flood was still under water, and {km(rep['flood_new_after_peak_km2'])} km² had flooded *after* "
        "the peak. "
        + (f"In **{' and '.join(rising)}** the flooded cropland was *larger* than at the peak, so the flood there "
           "was still spreading. " if rising else "")
        + "The northern and western districts (Thma Puok, Svay Chek, Paoy Paet) show almost no flooding.",
        "",
        "## How far to trust these numbers",
        "",
        "| Question | Answer | Evidence |",
        "| --- | --- | --- |",
        f"| Is this a real flood, not normal wet-season paddy water? | **Yes.** Flooded cropland is "
        f"{min(rep['normal_year_ratio'].values())}–{max(rep['normal_year_ratio'].values())}× the median of the "
        "same dates in 2018, 2019, 2021 and 2022"
        + ("" if not rep["normal_year_exceptions"] else
           ". **One exception:** " + "; ".join(
               f"{NAMES[e['method']]} finds {e['year']} about as large ({km(e['flood_cropland_km2'])} km² vs "
               f"{km(e['event_km2'])} km² in 2020)" for e in rep["normal_year_exceptions"])
           + ", so treat the size of the anomaly as uncertain")
        + ". | [level4_cambodia.md §3b](level4_cambodia.md) |",
        f"| Is the cropland number accurate? | **Mostly.** Checked against 17 hand-labelled sites: it finds "
        f"{100 * rec:.0f} % of the new flood water on cropland that people could see; {100 * prec:.0f} % of its "
        "cropland flood is real. "
        f"A simple threshold finds only {100 * rep['tierb_cropland']['otsu_vh_global']['recall']:.0f} %. "
        "| [level4_tierb_scores.md](level4_tierb_scores.md) |",
        f"| Is the forest and grassland number accurate? | **No, do not use it.** "
        f"{km(rep['flood_vegetation_km2'][SEL])} km² is mapped there, but on the hand-labelled sites only "
        f"about {100 * rep['tierb_vegetation_precision'][SEL]:.0f} % of it could be confirmed. "
        "| [level4_tierb_scores.md](level4_tierb_scores.md) |",
        "| Does it find water hidden under tall rice? | **Unknown.** Photos cannot see under the canopy, and "
        "free terrain data is too coarse to tell (the cropland is flat to within about "
        f"{rep['hidden_water']['cropland_dem_spread_median_m']:.1f} m). | [level4_tierb_scores.md §5](level4_tierb_scores.md) |",
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
        "- **Use it to rank districts**, and the last column to see where flooding was still present two weeks "
        "later. "
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
        f"(Open Development Cambodia, 2014, CC BY 4.0); {rep['unassigned_km2']:.0f} km² along the province edge falls "
        "outside them and is in the province totals but not in any district. Cropland: ESA WorldCover 2020, which does not separate "
        "rice from other crops.",
        "",
    ]
    return "\n".join(lines)


def build_report(
    l4_dir: pathlib.Path = L4,
    out_dir: pathlib.Path = OUT,
    doc_path: pathlib.Path = DOC,
    fig_path: pathlib.Path = FIG,
    ref_path: pathlib.Path | None = None,
) -> tuple[dict, str]:
    if ref_path is None:
        ref_path = catalog.DATA / "reference" / "tier_e_reference.json"
    cd = load_json(l4_dir / "change_detection.json")
    nyf = load_json(l4_dir / "normal_years.json")
    tb = load_json(l4_dir / "tierb_scores.json")["comparisons"]["new_flood"]["methods"]
    hw = load_json(l4_dir / "hidden_water_feasibility.json")["summary"]
    dist = load_json(out_dir / "districts.json")
    te = next(f for f in load_json(ref_path)["figures"]
              if f["quantity"] == "rice fields inundated")
    rows = dist["districts"]
    crop_total = dist["totals"]["cropland_km2"]

    rep = build_report_data(cd, nyf, tb, hw, dist, te["value_km2"])

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)

    generate_district_figure(rows, fig_path=fig_path)

    text = render_report_markdown(rep, rows, crop_total, cd)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(text, encoding="utf-8")
    print(f"wrote {doc_path}\nwrote {fig_path}\nwrote {out_dir / 'report.json'}")
    return rep, text
