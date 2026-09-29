"""Write the browser review decisions back into the label GeoPackage.

Input: the CSV downloaded from data/labels/review.html (fid, tile_id, decision),
by default looked for in the Downloads folder and the repo root.

    water  -> confidence 3, labeller and date filled in: this is now a label
    not    -> the polygon is deleted
    unsure -> class becomes -1 (uncertain), confidence stays 1: excluded from
              the primary score by protocol section 5

Also writes data/labels/review_summary.json with how many candidates were
accepted, rejected and marked unsure per tile. Protocol v1.2 requires that
number to be published: a tile where nothing was rejected is a tile where the
labeller may simply have agreed with the NDWI threshold.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

import geopandas as gpd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog  # noqa: E402

GPKG = catalog.DATA / "labels" / "tierB_bmc_oct2020.gpkg"
CANDIDATES = [pathlib.Path.home() / "Downloads" / "tierb_decisions.csv",
              catalog.ROOT / "tierb_decisions.csv",
              catalog.DATA / "labels" / "tierb_decisions.csv"]


def find_csv(explicit: str | None) -> pathlib.Path:
    if explicit:
        p = pathlib.Path(explicit)
        if p.exists():
            return p
        sys.exit(f"not found: {p}")
    for p in CANDIDATES:
        if p.exists():
            return p
    sys.exit("tierb_decisions.csv not found. Looked in:\n  " + "\n  ".join(str(p) for p in CANDIDATES))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--labeller", default="Sobotra")
    a = ap.parse_args()
    path = find_csv(a.csv)
    with open(path) as f:
        dec = {int(r["fid"]): r["decision"] for r in csv.DictReader(f)}
    print(f"{path}: {len(dec)} decisions")

    g = gpd.read_file(GPKG, layer="flood")
    today = dt.date.today().isoformat()
    keep, summary = [], {}
    for i, row in g.iterrows():
        d = dec.get(i)
        tile = row["tile_id"] or "?"
        s = summary.setdefault(tile, {"water": 0, "not": 0, "unsure": 0, "untouched": 0})
        if d is None:
            s["untouched"] += 1
            keep.append(i)
            continue
        s[d] += 1
        if d == "not":
            continue                      # drop the polygon
        if d == "water":
            g.at[i, "confidence"] = 3
            g.at[i, "labeller"] = a.labeller
            g.at[i, "date_labelled"] = today
            g.at[i, "note"] = "confirmed in browser review"
        else:                              # unsure
            g.at[i, "class"] = -1
            g.at[i, "labeller"] = a.labeller
            g.at[i, "date_labelled"] = today
            g.at[i, "note"] = "labeller unsure; excluded from the primary score"
        keep.append(i)

    out = g.loc[keep]
    out.to_file(GPKG, layer="flood", driver="GPKG")
    p = catalog.DATA / "labels" / "review_summary.json"
    totals = {k: sum(v[k] for v in summary.values()) for k in ("water", "not", "unsure", "untouched")}
    with open(p, "w") as f:
        json.dump({"labeller": a.labeller, "date": today, "source_csv": str(path),
                   "totals": totals, "per_tile": summary}, f, indent=2)

    print(f"\nconfirmed as water: {totals['water']}   rejected: {totals['not']}   "
          f"unsure: {totals['unsure']}   not yet reviewed: {totals['untouched']}")
    print(f"{len(out)} polygons remain in {GPKG}")
    if totals["water"] and totals["not"] == 0:
        print("\nNote: nothing was rejected. Protocol v1.2 flags that as suspicious - "
              "it may mean the candidates were accepted rather than judged.")
    print(f"summary written to {p}")


if __name__ == "__main__":
    main()
