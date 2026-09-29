"""Is Banteay Meanchey flooded on a given date? One command, any date with radar.

    python scripts/check_flood.py --date 2026-09-26
    python scripts/check_flood.py                    # the latest radar pass

What it does, in the same way as Level 4:
  1. finds the Sentinel-1 track-164 pass on (or just before) --date, and the
     pass --gap days earlier as "before" (default 18, as in the 2020 study);
  2. runs the three methods on both, 20 m over the whole province;
     flood = water on the date that was not water before;
  3. compares with the same dates in the --years previous years, because in
     the wet season a lot of new water is ordinary paddy ponding, not a flood;
  4. writes a map, a per-district table and a short plain-language report.

The verdict is a stated rule, not a measured accuracy:
    UNUSUAL FLOODING   flooded cropland (selected model) is more than
                       VERDICT_RATIO x the median of the previous years
                       and more than VERDICT_MIN_KM2
    NORMAL FOR THE SEASON otherwise
The rule was not tuned on any event. The 2020 event is 6.0x its baseline.

Downloads ~350 MB per radar pass (2 per year compared): run it on Colab
(notebooks/colab_check_flood.ipynb), not on a slow home connection.

Outputs: results/check/<date>/{report.md, summary.json, districts.csv,
         map.png, flood_<method>.tif}
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

import geopandas as gpd
import matplotlib
import numpy as np
from rasterio.features import rasterize

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, infer, rtc, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import METHODS, ancillary, aoi_grid, s1_on_aoi, write_map  # noqa: E402
from level7_district_areas import DISTRICTS  # noqa: E402

SEL = "unet_vvvh_cropw"
VERDICT_RATIO = 2.0
VERDICT_MIN_KM2 = 50.0
MIN_COVERAGE = 0.95        # below this the province is not fully seen; say so
OUT = experiments.RESULTS / "check"
NAMES = {"otsu_vh_global": "VH threshold", "unet_vv_ce": "U-Net VV only", "unet_vvvh_cropw": "U-Net VV+VH (selected)"}


def passes(start: dt.date, end: dt.date) -> dict[str, str]:
    """{date: platform} of track-164 descending passes between start and end."""
    items = rtc.rtc_items(catalog.aoi_bbox(), start.isoformat(), end.isoformat(),
                          rel_orbit=catalog.ANCHOR_REL_ORBIT, orbit_state=catalog.ANCHOR_ORBIT_STATE)
    return {i.datetime.date().isoformat(): i.properties.get("platform", "?").lower() for i in items}


def pass_on_or_before(day: dt.date, window: int = 13) -> tuple[str, str] | None:
    got = passes(day - dt.timedelta(days=window), day)
    if not got:
        return None
    d = max(got)
    return d, got[d]


def pass_nearest(day: dt.date, window: int = 7) -> tuple[str, str] | None:
    got = passes(day - dt.timedelta(days=window), day + dt.timedelta(days=window))
    if not got:
        return None
    d = min(got, key=lambda x: abs((dt.date.fromisoformat(x) - day).days))
    return d, got[d]


class Predictor:
    def __init__(self, slope):
        self.slope = slope
        self.unets = {m: infer.load_unet(m) for m in METHODS if m.startswith("unet")}

    def water(self, s1, method) -> np.ndarray:
        ch = {"vv": s1[0], "vh": s1[1], "ratio": s1[0] - s1[1], "slope": self.slope}
        if method == "otsu_vh_global":
            return infer.predict_threshold(ch, "vh")
        model, channels, norm, device = self.unets[method]
        return infer.predict_unet(model, channels, norm, device, ch)


def flood_pair(pred, grid, inside, land, pre_date, date):
    """Per method: flood map and areas for one (before, date) pair."""
    px = abs(grid.transform.a) ** 2 / 1e6
    pre_s1, s1 = s1_on_aoi(pre_date, grid), s1_on_aoi(date, grid)
    ok = np.isfinite(pre_s1).all(axis=0) & np.isfinite(s1).all(axis=0) & inside
    out = {"coverage": float(ok.sum() / inside.sum()), "methods": {}, "maps": {}}
    for m in METHODS:
        w_pre, w = pred.water(pre_s1, m) == 1, pred.water(s1, m) == 1
        flood = w & ~w_pre & ok
        out["maps"][m] = (flood, w_pre & ok)
        out["methods"][m] = {"water_before_km2": round(float((w_pre & ok).sum() * px), 1),
                             "water_km2": round(float((w & ok).sum() * px), 1),
                             "flood_km2": round(float(flood.sum() * px), 1),
                             "flood_cropland_km2": round(float((flood & (land == strata.CROPLAND)).sum() * px), 1)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", help="YYYY-MM-DD; default: the latest radar pass")
    ap.add_argument("--gap", type=int, default=18, help="days between 'before' and the date (default 18)")
    ap.add_argument("--years", type=int, default=3, help="previous years to compare with (default 3; 0 = none)")
    a = ap.parse_args()

    today = dt.date.today()
    want = dt.date.fromisoformat(a.date) if a.date else today
    hit = pass_on_or_before(want)
    if hit is None:
        sys.exit(f"No track-164 radar pass in the 13 days up to {want}. The archive may not have it yet "
                 "(it usually lags 1-3 days).")
    date, platform = hit
    before = pass_nearest(dt.date.fromisoformat(date) - dt.timedelta(days=a.gap))
    if before is None:
        sys.exit(f"No 'before' pass near {a.gap} days before {date}.")
    pre_date, pre_platform = before
    print(f"date   {date} ({platform})\nbefore {pre_date} ({pre_platform})", flush=True)

    grid, inside = aoi_grid()
    land, _, slope = ancillary(grid)
    pred = Predictor(slope)
    now = flood_pair(pred, grid, inside, land, pre_date, date)

    base = {}
    d0, p0 = dt.date.fromisoformat(date), dt.date.fromisoformat(pre_date)
    for k in range(1, a.years + 1):
        shift = dt.timedelta(days=round(365.25 * k))    # not .replace(year=): 29 Feb
        dd, pp = pass_nearest(d0 - shift), pass_nearest(p0 - shift)
        if dd is None or pp is None:
            print(f"  {d0.year - k}: no pass near these dates, skipped")
            continue
        print(f"  baseline {d0.year - k}: before {pp[0]}, date {dd[0]}", flush=True)
        r = flood_pair(pred, grid, inside, land, pp[0], dd[0])
        base[str(d0.year - k)] = {"before": pp[0], "date": dd[0], "coverage": r["coverage"],
                                  "methods": r["methods"]}

    # verdict from the selected model; the other two are reported for agreement
    verdicts = {}
    for m in METHODS:
        now_c = now["methods"][m]["flood_cropland_km2"]
        vals = [b["methods"][m]["flood_cropland_km2"] for b in base.values()]
        med = float(np.median(vals)) if vals else None
        unusual = med is not None and now_c > VERDICT_RATIO * max(med, 1.0) and now_c > VERDICT_MIN_KM2
        verdicts[m] = {"flood_cropland_km2": now_c, "baseline_median_km2": med,
                       "ratio": round(now_c / med, 1) if med else None,
                       "verdict": None if med is None else ("UNUSUAL FLOODING" if unusual else "NORMAL FOR THE SEASON")}

    # districts, selected model
    px = abs(grid.transform.a) ** 2 / 1e6
    dg = gpd.read_file(DISTRICTS).to_crs(grid.crs).sort_values("shapeName").reset_index(drop=True)
    dist = rasterize(((g, i + 1) for i, g in enumerate(dg.geometry)), out_shape=inside.shape,
                     transform=grid.transform, dtype="uint8")
    flood_sel = now["maps"][SEL][0]
    crop = land == strata.CROPLAND
    rows = []
    for i, name in enumerate(dg["shapeName"]):
        z = (dist == i + 1) & inside
        rows.append({"district": name, "cropland_km2": round(float((z & crop).sum() * px), 1),
                     **{f"flood_cropland_{m}": round(float((z & crop & now["maps"][m][0]).sum() * px), 1)
                        for m in METHODS}})
    rows.sort(key=lambda r: -r[f"flood_cropland_{SEL}"])

    out = OUT / date
    out.mkdir(parents=True, exist_ok=True)
    for m in METHODS:
        f, w_pre = now["maps"][m]
        write_map(out / f"flood_{m}.tif", np.where(inside, f.astype(np.int8), -1), grid)
    with open(out / "districts.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    platforms = {platform, pre_platform}
    summary = {"date": date, "platform": platform, "before": pre_date, "before_platform": pre_platform,
               "gap_days": (d0 - p0).days, "coverage": round(now["coverage"], 3), "methods": now["methods"],
               "baseline": base, "verdicts": verdicts, "verdict_rule": {"ratio": VERDICT_RATIO,
                                                                       "min_km2": VERDICT_MIN_KM2},
               "untested_platforms": sorted(p for p in platforms if p not in ("sentinel-1a", "sentinel-1b"))}
    with open(out / "summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)

    # map
    fig, ax = plt.subplots(figsize=(9, 9))
    img = np.zeros(inside.shape, np.uint8)
    img[now["maps"][SEL][1]] = 1
    img[flood_sel] = 2
    img = np.ma.masked_where(~inside, img)
    ax.imshow(img, cmap=ListedColormap(["#e9e6dd", "#9fc5e8", "#1f5fa8"]), vmin=0, vmax=2,
              interpolation="nearest", extent=(grid.transform.c, grid.transform.c + grid.width * grid.transform.a,
                                               grid.transform.f + grid.height * grid.transform.e, grid.transform.f))
    dg.boundary.plot(ax=ax, color="#555", linewidth=0.8)
    for _, r in dg.iterrows():
        p = r.geometry.representative_point()
        ax.annotate(r["shapeName"], (p.x, p.y), ha="center", fontsize=8, color="#222")
    v = verdicts[SEL]["verdict"] or "no comparison"
    ax.set_title(f"Banteay Meanchey, {date}: {v}\n"
                 f"dark blue = new water since {pre_date} · light blue = water already there", loc="left", fontsize=11)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out / "map.png", dpi=110, facecolor="white")
    plt.close(fig)

    # report
    s, vs = now["methods"][SEL], verdicts[SEL]
    agree = [NAMES[m] for m in METHODS if verdicts[m]["verdict"] == vs["verdict"]]
    L = [f"# Flood check: Banteay Meanchey, {date}", "",
         f"## {vs['verdict'] or 'No comparison with previous years'}", ""]
    if vs["verdict"]:
        L.append(f"Flooded cropland: **{s['flood_cropland_km2']:,.0f} km²**. The same dates in the previous "
                 f"{len(base)} years had a median of **{vs['baseline_median_km2']:,.0f} km²** "
                 f"({vs['ratio']}×). Rule: 'unusual' means more than {VERDICT_RATIO:.0f}× the usual amount "
                 f"and more than {VERDICT_MIN_KM2:.0f} km². {len(agree)} of 3 methods give this verdict.")
    else:
        L.append(f"Flooded cropland: **{s['flood_cropland_km2']:,.0f} km²**. Without previous years there is no "
                 "way to tell a flood from normal wet-season paddy water.")
    L += ["", "![map](map.png)", "",
          f"| | {date} | " + " | ".join(base) + " |",
          "| --- | --- | " + " | ".join("---" for _ in base) + " |"]
    for m in METHODS:
        L.append(f"| {NAMES[m]}: flooded cropland, km² | {now['methods'][m]['flood_cropland_km2']:,.0f} | "
                 + " | ".join(f"{b['methods'][m]['flood_cropland_km2']:,.0f}" for b in base.values()) + " |")
    L += ["", "**Flooded cropland by district** (selected model):", "",
          "| District | km² | share of district's cropland |", "| --- | --- | --- |"]
    for r in rows:
        sh = 100 * r[f"flood_cropland_{SEL}"] / r["cropland_km2"] if r["cropland_km2"] else 0
        L.append(f"| {r['district']} | {r[f'flood_cropland_{SEL}']:,.0f} | {'< 1' if sh < 1 else f'{sh:.0f}'} % |")
    L += ["", "## Read before using", "",
          f"- Radar passes: {pre_date} (before) and {date}, track 164. "
          f"The radar saw {100 * now['coverage']:.0f} % of the province"
          + ("." if now["coverage"] >= MIN_COVERAGE else " — **part of the province is missing; totals are too low.**"),
          "- 'Flood' = water on the date that was not water on the 'before' date. Water that was already there "
          "before is not counted, so a flood that started before the 'before' date is under-counted.",
          "- Accuracy was measured once, on the October 2020 flood: on cropland the selected model found 74 % of "
          "the flood water people could see in photos, and 89 % of what it called flood was flood. Forest and "
          "grassland numbers are not reliable. Water hidden under tall rice was not checked. See "
          "`docs/level7_report.md`."]
    if summary["untested_platforms"]:
        L.append(f"- These passes include {', '.join(summary['untested_platforms'])}. The models were trained and "
                 "tested on Sentinel-1A/1B only. The newer satellites carry the same radar design, but this project "
                 "has not measured them, so treat the numbers with extra caution.")
    L.append("")
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")
    print("\n" + "\n".join(L[:6]))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
