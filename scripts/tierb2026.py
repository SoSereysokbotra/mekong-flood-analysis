"""Tier B for the September 2026 flood: hand labels to score the flood check.

The 2020 Tier B scripts have the 2020 dates built in and are left untouched, so
the published 2020 scores stay reproducible. This runs the same procedure on
the same 20 tiles (fixed in 2020, chosen without any model output) for 2026.

    python scripts/tierb2026.py status
        per tile: clear fraction of every Sentinel-2 scene since the flood
        began, from the scene classification band (not scene-level cloud)

Further steps (prepare, review, score) are added once a usable scene exists.

Output: data/labels/2026/optical_status.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_tier_b_imagery import clear_fraction, tile_grid  # noqa: E402

DIR = catalog.DATA / "labels" / "2026"
FLOOD_START = "2026-09-24"      # heavy rain began (news reports); radar pass 26 Sep shows the flood


def tiles():
    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        return sorted(json.load(f)["features"], key=lambda x: x["properties"]["label_order"])


def bbox(feat):
    xs = [p[0] for p in feat["geometry"]["coordinates"][0]]
    ys = [p[1] for p in feat["geometry"]["coordinates"][0]]
    return [min(xs), min(ys), max(xs), max(ys)]


def status(end: str):
    cl = catalog._client()
    feats = tiles()
    rows, dates = [], set()
    for feat in feats:
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
    print("\nTiles at least half clear, per date:")
    for d in dates:
        n = sum(r.get(d, 0) >= 0.5 for r in rows)
        print(f"  {d}: {n:2d} of {len(rows)}")
    print(f"\nwrote {DIR / 'optical_status.csv'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["status"])
    ap.add_argument("--end", default=dt.date.today().isoformat())
    a = ap.parse_args()
    if a.step == "status":
        status(a.end)


if __name__ == "__main__":
    main()
