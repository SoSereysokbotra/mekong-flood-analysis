"""Tier B for the September 2026 flood: hand labels to score the flood check.

The 2020 Tier B scripts have the 2020 dates built in and are left untouched, so
the published 2020 scores stay reproducible. This runs the same procedure on
the same 20 tiles (fixed in 2020, chosen without any model output) for 2026,
under protocol v1.3 section 9 (data/labels/LABELLING_PROTOCOL.md).

    python scripts/tierb2026.py status
        per tile: clear fraction of every Sentinel-2 scene since the flood began.
        Prints the date the protocol selects, if one exists yet.
    python scripts/tierb2026.py prepare
        for the selected date: false colour + NDWI + cloud band per tile, a
        pre-flood scene, NDWI candidate polygons, and the review page
    (labeller)  open data/labels/2026/review.html, click, Download decisions
    python scripts/tierb2026.py apply  [--csv path]
        writes the decisions into data/labels/tierB_bmc_sep2026.gpkg
    python scripts/tierb2026.py score
        scores the flood check at the radar pass nearest the optical date

Outputs: data/labels/2026/, data/labels/tierB_bmc_sep2026.gpkg,
         results/check/<radar date>/tierb_scores.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io, metrics, rtc, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_tier_b_imagery import clear_fraction, tile_grid, write  # noqa: E402

DIR = catalog.DATA / "labels" / "2026"
IMG = DIR / "imagery"
GPKG = catalog.DATA / "labels" / "tierB_bmc_sep2026.gpkg"
PAGE = DIR / "review.html"
FLOOD_START = "2026-09-24"       # heavy rain began (news reports)
DEADLINE = "2026-10-31"          # protocol v1.3 s9.1
PRE_WINDOW = ("2026-09-01", "2026-09-20")
MIN_TILES, MIN_CLEAR, MAX_RADAR_GAP = 10, 0.5, 3   # protocol v1.3 s9.1
CSV_NAME = "tierb_decisions_2026.csv"
MIN_CONFIDENCE = 2
GROUPS = ("all", "cropland", "vegetation", "open_water", "built")


def tiles():
    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        return sorted(json.load(f)["features"], key=lambda x: x["properties"]["label_order"])


def bbox(feat):
    xs = [p[0] for p in feat["geometry"]["coordinates"][0]]
    ys = [p[1] for p in feat["geometry"]["coordinates"][0]]
    return [min(xs), min(ys), max(xs), max(ys)]


def radar_passes(start: str, end: str) -> list[str]:
    items = rtc.rtc_items(catalog.aoi_bbox(), start, end, rel_orbit=catalog.ANCHOR_REL_ORBIT,
                          orbit_state=catalog.ANCHOR_ORBIT_STATE)
    return sorted({i.datetime.date().isoformat() for i in items})


def nearest_pass(day: str, passes: list[str]) -> tuple[str, int] | None:
    if not passes:
        return None
    d0 = dt.date.fromisoformat(day)
    # ties go to the earlier pass (protocol v1.3 s9.2): sorted list + strict min keeps the first
    best = min(passes, key=lambda p: abs((dt.date.fromisoformat(p) - d0).days))
    return best, abs((dt.date.fromisoformat(best) - d0).days)


# ---------------------------------------------------------------- status

def status(end: str):
    cl = catalog._client()
    rows, dates = [], set()
    for feat in tiles():
        tid = feat["properties"]["tile_id"]
        grid = tile_grid(feat)
        items = list(cl.search(collections=["sentinel-2-l2a"], bbox=bbox(feat),
                               datetime=f"{FLOOD_START}/{end}").items())
        best = {}
        for it in items:
            if it.properties["eo:cloud_cover"] > 99.5:      # nothing to see, skip the read
                continue
            d = it.properties["datetime"][:10]
            best[d] = max(best.get(d, 0.0), clear_fraction(it, grid))
        dates |= set(best)
        rows.append({"tile_id": tid, "stratum": feat["properties"]["stratum"], **best})
        print(f"{tid:12s} " + "  ".join(f"{d[5:]} {100 * v:3.0f}%" for d, v in sorted(best.items())), flush=True)

    dates = sorted(dates)
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / "optical_status.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["tile_id", "stratum", *dates])
        w.writeheader()
        w.writerows(rows)

    passes = radar_passes(FLOOD_START, (dt.date.fromisoformat(end) + dt.timedelta(days=MAX_RADAR_GAP)).isoformat())
    print(f"\nradar passes since {FLOOD_START}: {', '.join(passes) or 'none'}")
    print("Tiles at least half clear, per date:")
    selected = None
    for d in dates:
        n = sum(r.get(d, 0) >= MIN_CLEAR for r in rows)
        near = nearest_pass(d, passes)
        ok = n >= MIN_TILES and near is not None and near[1] <= MAX_RADAR_GAP
        print(f"  {d}: {n:2d} of {len(rows)}"
              + (f"   radar {near[0]} ({near[1]} d)" if near else "") + ("   <- SELECTED" if ok and not selected else ""))
        if ok and not selected:
            selected = (d, near[0])
    if selected:
        with open(DIR / "selected.json", "w") as f:
            json.dump({"optical_date": selected[0], "radar_date": selected[1],
                       "rule": f">= {MIN_TILES} tiles >= {MIN_CLEAR:.0%} clear, radar within {MAX_RADAR_GAP} d"}, f, indent=2)
        print(f"\nSELECTED by protocol v1.3: optical {selected[0]}, radar {selected[1]}. "
              f"Next: python scripts/tierb2026.py prepare")
    elif end >= DEADLINE:
        print(f"\nDeadline {DEADLINE} reached with no usable date: record 'no usable optical' (protocol v1.3 s9.1).")
    else:
        print(f"\nNo date qualifies yet ({MIN_TILES} tiles needed). Check again in 2-3 days; deadline {DEADLINE}.")
    print(f"wrote {DIR / 'optical_status.csv'}")


# ---------------------------------------------------------------- prepare

def selected():
    p = DIR / "selected.json"
    if not p.exists():
        sys.exit("No date selected yet. Run: python scripts/tierb2026.py status")
    with open(p) as f:
        return json.load(f)


def scene_layers(item, grid, d: pathlib.Path, role: str, date: str):
    """False colour (SWIR/NIR/Red), NDWI and the cloud band for one scene on one tile."""
    b03, b04, b08, b11 = (io._read_on_grid(item.assets[b].href, grid, Resampling.bilinear)[0].astype(np.float32)
                          for b in ("B03", "B04", "B08", "B11"))
    fc = np.stack([np.clip(b11 / 3000, 0, 1), np.clip(b08 / 4000, 0, 1), np.clip(b04 / 3000, 0, 1)]) * 255
    write(d / f"falsecolour_{role}_{date}.tif", fc, grid, "uint8")
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = (b03 - b08) / (b03 + b08)
    write(d / f"ndwi_{role}_{date}.tif", np.nan_to_num(ndwi, nan=-1).astype(np.float32), grid, "float32", nodata=-999)
    scl, _ = io._read_on_grid(item.assets["SCL"].href, grid, Resampling.nearest)
    write(d / f"scl_{role}_{date}.tif", scl.astype("uint8"), grid, "uint8")


def prepare():
    import pandas as pd

    from make_label_candidates import MIN_PIXELS, NDWI_WATER, SCL_BAD, clean, polygonise

    sel = selected()
    date = sel["optical_date"]
    cl = catalog._client()
    rows, avail = [], []
    for feat in tqdm(tiles(), desc="tiles"):
        tid = feat["properties"]["tile_id"]
        grid = tile_grid(feat)
        d = IMG / tid
        ev = [i for i in cl.search(collections=["sentinel-2-l2a"], bbox=bbox(feat), datetime=f"{date}/{date}").items()]
        scored = sorted(((clear_fraction(i, grid), i) for i in ev), key=lambda x: -x[0])
        rec = {"tile_id": tid, "label_order": feat["properties"]["label_order"], "event_date": date,
               "event_clear_frac": round(scored[0][0], 3) if scored else 0.0}
        if not scored or scored[0][0] <= 0.05:
            avail.append(rec)
            continue
        scene_layers(scored[0][1], grid, d, "event", date)
        pre = list(cl.search(collections=["sentinel-2-l2a"], bbox=bbox(feat),
                             datetime=f"{PRE_WINDOW[0]}/{PRE_WINDOW[1]}").items())
        pre = sorted(pre, key=lambda i: i.properties["eo:cloud_cover"])[:6]
        pscored = sorted(((clear_fraction(i, grid), i) for i in pre), key=lambda x: -x[0])
        if pscored and pscored[0][0] > 0.05:
            pdate = pscored[0][1].properties["datetime"][:10]
            scene_layers(pscored[0][1], grid, d, "pre", pdate)
            rec.update(pre_date=pdate, pre_clear_frac=round(pscored[0][0], 3))
        avail.append(rec)

        # candidates: identical to make_label_candidates.py (protocol s5b), on the 2026 scene
        with rasterio.open(d / f"ndwi_event_{date}.tif") as s:
            ndwi = s.read(1)
        with rasterio.open(d / f"scl_event_{date}.tif") as s:
            bad = np.isin(s.read(1), list(SCL_BAD))
        land = strata.land_type(io.worldcover_on_grid(grid, year=2020))
        water = clean((ndwi > NDWI_WATER) & ~bad)
        for g in polygonise(water, grid):
            m = rasterio.features.geometry_mask([g], water.shape, grid.transform, invert=True)
            lt = np.bincount(land[m].astype(int), minlength=6).argmax() if m.any() else strata.OTHER
            cls = 2 if lt in (strata.CROPLAND, strata.VEGETATION) else (3 if lt == strata.OPEN_WATER else 1)
            rows.append({"geometry": g, "class": cls, "confidence": 1, "tile_id": tid,
                         "evidence": f"CANDIDATE from NDWI>{NDWI_WATER} on S2 {date} - REVIEW",
                         "labeller": "", "date_labelled": "", "note": "candidate: confirm, fix or delete"})
        from scipy import ndimage as nd

        badm = nd.binary_closing(bad, np.ones((5, 5)))
        lab, n = nd.label(badm)
        if n:
            sizes = nd.sum(badm, lab, range(1, n + 1))
            badm = np.isin(lab, 1 + np.flatnonzero(sizes >= 60))
        for g in polygonise(badm, grid):
            rows.append({"geometry": g, "class": -1, "confidence": 1, "tile_id": tid,
                         "evidence": f"cloud or shadow in S2 {date} - optical unusable here",
                         "labeller": "", "date_labelled": "", "note": "uncertain: no usable optical"})

    with open(DIR / "optical_availability.csv", "w", newline="") as f:
        keys = ["tile_id", "label_order", "event_date", "event_clear_frac", "pre_date", "pre_clear_frac"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(avail)
    epsg = tiles()[0]["properties"]["utm_epsg"]
    gdf = gpd.GeoDataFrame(rows, crs=f"EPSG:{epsg}") if rows else gpd.GeoDataFrame(
        columns=["geometry", "class", "confidence", "tile_id", "evidence", "labeller", "date_labelled", "note"],
        geometry="geometry", crs=f"EPSG:{epsg}")
    if GPKG.exists():
        sys.exit(f"{GPKG} already exists: refusing to overwrite reviewed labels. Move it away to re-prepare.")
    gdf.to_file(GPKG, layer="flood", driver="GPKG")
    n_w = int((gdf["class"] >= 1).sum()) if len(gdf) else 0
    print(f"\n{n_w} water candidates, {len(gdf) - n_w} cloud areas -> {GPKG}")
    review_page(date)


def review_page(date: str):
    from make_review_page import PAGE_TEMPLATE, crop

    g = gpd.read_file(GPKG, layer="flood")
    water = g[g["evidence"].fillna("").str.contains("CANDIDATE")].copy().sort_values("tile_id").reset_index()
    cards = []
    for _, row in tqdm(water.iterrows(), total=len(water), desc="thumbnails"):
        d = IMG / row["tile_id"]
        ev = next(iter(sorted(d.glob("falsecolour_event_*.tif"))), None)
        pre = next(iter(sorted(d.glob("falsecolour_pre_*.tif"))), None)
        nd = next(iter(sorted(d.glob("ndwi_event_*.tif"))), None)
        b = row.geometry.bounds
        cards.append({"fid": int(row["index"]), "tile": row["tile_id"], "class": int(row["class"]),
                      "area_ha": round(row.geometry.area / 1e4, 2), "event": crop(ev, b, row.geometry) if ev else None,
                      "pre": crop(pre, b, row.geometry) if pre else None, "ndwi": crop(nd, b, row.geometry) if nd else None})
    html = (PAGE_TEMPLATE.replace("__CARDS__", json.dumps(cards))
            .replace('"tierb_review_v1"', '"tierb_review_2026"')          # 2020 decisions must not leak in
            .replace("tierb_decisions.csv", CSV_NAME)
            .replace("Tier B review —", f"Tier B 2026 review ({date}) —"))
    assert '"tierb_review_2026"' in html and CSV_NAME in html, "review page template changed; storage key not replaced"
    PAGE.write_text(html, encoding="utf-8")
    print(f"wrote {PAGE} ({len(cards)} candidates). Open it by double-clicking.")


# ---------------------------------------------------------------- apply

def apply(csv_path: str | None, labeller: str):
    home = pathlib.Path.home()
    looks = [pathlib.Path(csv_path)] if csv_path else [home / "Downloads" / CSV_NAME,
                                                       home / "OneDrive" / "Pictures" / "Downloads" / CSV_NAME,
                                                       catalog.ROOT / CSV_NAME, DIR / CSV_NAME]
    path = next((p for p in looks if p.exists()), None)
    if path is None:
        sys.exit(f"{CSV_NAME} not found. Looked in:\n  " + "\n  ".join(map(str, looks)))
    with open(path) as f:
        dec = {int(r["fid"]): r["decision"] for r in csv.DictReader(f)}
    g = gpd.read_file(GPKG, layer="flood")
    today = dt.date.today().isoformat()
    keep, summary = [], {}
    for i, row in g.iterrows():
        d = dec.get(i)
        s = summary.setdefault(row["tile_id"] or "?", {"water": 0, "not": 0, "unsure": 0, "untouched": 0})
        if d is None:
            s["untouched"] += 1
            keep.append(i)
            continue
        s[d] += 1
        if d == "not":
            continue
        if d == "water":
            g.loc[i, ["confidence", "labeller", "date_labelled", "note"]] = [3, labeller, today, "confirmed in browser review"]
        else:
            g.loc[i, ["class", "labeller", "date_labelled", "note"]] = [-1, labeller, today,
                                                                         "labeller unsure; excluded from the primary score"]
        keep.append(i)
    g.loc[keep].to_file(GPKG, layer="flood", driver="GPKG")
    totals = {k: sum(v[k] for v in summary.values()) for k in ("water", "not", "unsure", "untouched")}
    with open(DIR / "review_summary.json", "w") as f:
        json.dump({"labeller": labeller, "date": today, "source_csv": str(path), "totals": totals,
                   "per_tile": summary}, f, indent=2)
    print(f"confirmed water {totals['water']}, rejected {totals['not']}, unsure {totals['unsure']}, "
          f"not reviewed {totals['untouched']}")
    if totals["water"] and not totals["not"]:
        print("Note: nothing was rejected; protocol s5b flags that as possible anchoring.")


# ---------------------------------------------------------------- score

def score():
    from check_flood import Predictor, s1_retry
    from level4_cambodia import METHODS, ancillary, aoi_grid

    sel = selected()
    radar = sel["radar_date"]
    mapdir = experiments.RESULTS / "check" / radar
    if not all((mapdir / f"flood_{m}.tif").exists() for m in METHODS):
        sys.exit(f"No flood check for {radar} yet. Run: python scripts/check_flood.py --date {radar}")
    with open(mapdir / "summary.json") as f:
        if json.load(f)["date"] != radar:
            sys.exit(f"{mapdir} is not the check for {radar}")

    grid, inside = aoi_grid()
    land, _, slope = ancillary(grid)
    shape = (grid.height, grid.width)
    labels = gpd.read_file(GPKG, layer="flood").to_crs(grid.crs)
    tl = gpd.GeoDataFrame.from_features(tiles(), crs="EPSG:4326").to_crs(grid.crs)
    confirmed = labels[labels["confidence"] >= MIN_CONFIDENCE]
    ignore = labels[(labels["class"] == -1) | (labels["confidence"] < MIN_CONFIDENCE)]
    reviewed = sorted(set(confirmed["tile_id"]) | set(ignore["tile_id"]))
    burn = lambda gs: (rasterize(((g, 1) for g in gs.geometry), out_shape=shape, transform=grid.transform,  # noqa: E731
                                 dtype="uint8").astype(bool) if len(gs) else np.zeros(shape, bool))
    in_tiles, ign = burn(tl[tl["tile_id"].isin(reviewed)]), burn(ignore)

    def label_for(classes):
        lab = burn(confirmed[confirmed["class"].isin(classes)]).astype(np.int8)
        return np.where(in_tiles & ~ign, lab, -1).astype(np.int8)

    pred = Predictor(slope)
    s1 = s1_retry(radar, grid)
    preds = {"total_water": {m: pred.water(s1, m) == 1 for m in METHODS}, "new_flood": {}}
    for m in METHODS:
        with rasterio.open(mapdir / f"flood_{m}.tif") as src:
            preds["new_flood"][m] = src.read(1) == 1
    labs = {"total_water": label_for([1, 2, 3]), "new_flood": label_for([1, 2])}

    px = abs(grid.transform.a) ** 2 / 1e6
    out = {"optical_date": sel["optical_date"], "radar_date": radar, "min_confidence": MIN_CONFIDENCE,
           "tiles_reviewed": reviewed, "comparisons": {}}
    for c, lab in labs.items():
        out["comparisons"][c] = {"water_px": int((lab == 1).sum()), "dry_px": int((lab == 0).sum()),
                                 "water_km2": round(float((lab == 1).sum() * px), 2), "methods": {}}
        for m in METHODS:
            r = metrics.Confusion().add(preds[c][m], lab, land).metrics()
            out["comparisons"][c]["methods"][m] = {g: {k: r[g][k] for k in ("iou", "recall", "precision", "tp", "fp",
                                                                             "fn", "n_pos")} for g in GROUPS}
            experiments.log_row("check2026", f"tierb2026_{c}_{m}", "tierb2026", m,
                                {"labels": "Tier B 2026 confirmed", "comparison": c, "radar": radar,
                                 "optical": sel["optical_date"]}, len(reviewed), r, note=f"Tier B 2026, {c}")
    with open(mapdir / "tierb_scores.json", "w") as f:
        json.dump(out, f, indent=2)
    for c in labs:
        print(f"\n== {c}  ({out['comparisons'][c]['water_km2']} km2 labelled water)")
        print(f"{'method':17s} {'crop IoU':>8s} {'crop rec':>8s} {'crop prec':>9s} {'n crop':>7s}")
        for m in METHODS:
            k = out["comparisons"][c]["methods"][m]["cropland"]
            print(f"{m:17s} {k['iou']:8.3f} {k['recall']:8.3f} {k['precision']:9.3f} {k['n_pos']:7d}")
    print(f"\nwrote {mapdir / 'tierb_scores.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["status", "prepare", "review", "apply", "score"])
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--csv")
    ap.add_argument("--labeller", default="Sobotra")
    a = ap.parse_args()
    if a.step == "status":
        status(a.end)
    elif a.step == "prepare":
        prepare()
    elif a.step == "review":
        review_page(selected()["optical_date"])
    elif a.step == "apply":
        apply(a.csv, a.labeller)
    else:
        score()


if __name__ == "__main__":
    main()
