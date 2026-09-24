"""Pre-draw candidate polygons for the Tier B labeller to review and correct.

The labeller's job becomes checking and fixing shapes rather than digitising
from scratch. Every polygon is written with confidence = 1 (weak) and status
"candidate", so nothing counts as a label until a human has looked at it and
raised the confidence.

Where the candidates come from, and why it is allowed:
  - water candidates: NDWI > NDWI_WATER on the event-date Sentinel-2 scene,
    specks below MIN_PIXELS removed, then polygonised and simplified.
    NDWI is *optical*, which the protocol's evidence hierarchy puts first;
    radar is not used here at all, so the labels cannot inherit the radar
    bias the project exists to measure.
  - uncertain areas: the Sentinel-2 scene classification band (cloud, cloud
    shadow, snow, saturated). NDWI is unreliable there -- cloud shadow in
    particular mimics water -- so those areas become class -1 automatically.

Class is seeded from ESA WorldCover, not from any model:
    cropland or vegetation -> 2 (flood with vegetation, the target class)
    open water             -> 3 (permanent water)
    anything else          -> 1 (flood, open water)
The seed is a starting point. The labeller must confirm or change it.

Run: python scripts/make_label_candidates.py [--tile BMC_CROP_01] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from shapely.geometry import shape as to_shape
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_tier_b_imagery import OUT, tile_grid  # noqa: E402

GPKG = catalog.DATA / "labels" / "tierB_bmc_oct2020.gpkg"
NDWI_WATER = 0.0          # standard NDWI water threshold
MIN_PIXELS = 12           # 12 x 100 m2 = 0.12 ha: drop specks
SIMPLIFY_M = 15.0         # smooth the pixel staircase, keep the field shape
SCL_BAD = {3, 8, 9, 10, 11}   # cloud shadow, cloud medium/high, cirrus, snow


def scl_on_tile(tid, grid, date, bbox):
    """Scene classification band for the event scene, cached per tile."""
    p = OUT / tid / "optical" / f"scl_event_{date}.tif"
    if p.exists():
        with rasterio.open(p) as s:
            return s.read(1)
    items = list(catalog._client().search(collections=["sentinel-2-l2a"], bbox=bbox,
                                          datetime=f"{date}/{date}").items())
    if not items:
        return None
    it = min(items, key=lambda i: i.properties["eo:cloud_cover"])
    scl, _ = io._read_on_grid(it.assets["SCL"].href, grid, Resampling.nearest)
    with rasterio.open(p, "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
                       dtype="uint8", crs=grid.crs, transform=grid.transform, compress="deflate") as dst:
        dst.write(scl.astype("uint8"), 1)
    return scl


def clean(mask: np.ndarray) -> np.ndarray:
    """Remove specks and fill pinholes so the polygons are drawable shapes."""
    from scipy import ndimage

    lab, n = ndimage.label(mask)
    if n:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.flatnonzero(sizes >= MIN_PIXELS))
    else:
        keep = mask
    return ndimage.binary_closing(keep, np.ones((3, 3)))


def polygonise(mask: np.ndarray, grid: io.Grid):
    out = []
    for geom, val in shapes(mask.astype(np.uint8), mask=mask, transform=grid.transform):
        if val:
            g = to_shape(geom).simplify(SIMPLIFY_M)
            if g.is_valid and g.area > MIN_PIXELS * 100:
                out.append(g)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        feats = {x["properties"]["tile_id"]: x for x in json.load(f)["features"]}
    with open(catalog.DATA / "labels" / "optical_availability.csv") as f:
        avail = {r["tile_id"]: r for r in csv.DictReader(f)}

    tiles = [a.tile] if a.tile else [t for t in sorted(avail, key=lambda t: int(avail[t]["label_order"]))]
    rows, summary = [], []
    for tid in tqdm(tiles, desc="tiles"):
        r = avail[tid]
        date = r.get("event_date")
        d = OUT / tid / "optical"
        ndwi_p = d / f"ndwi_event_{date}.tif"
        if not date or not ndwi_p.exists():
            summary.append((tid, 0, 0, "no event optical"))
            continue
        grid = tile_grid(feats[tid])
        xs = [p[0] for p in feats[tid]["geometry"]["coordinates"][0]]
        ys = [p[1] for p in feats[tid]["geometry"]["coordinates"][0]]
        scl = scl_on_tile(tid, grid, date, [min(xs), min(ys), max(xs), max(ys)])
        with rasterio.open(ndwi_p) as s:
            ndwi = s.read(1)
        land = strata.land_type(io.worldcover_on_grid(grid, year=2020))

        bad = np.isin(scl, list(SCL_BAD)) if scl is not None else np.zeros(ndwi.shape, bool)
        water = clean((ndwi > NDWI_WATER) & ~bad)
        n_w = n_u = 0
        for g in polygonise(water, grid):
            # seed the class from land cover, never from a model
            m = rasterio.features.geometry_mask([g], water.shape, grid.transform, invert=True)
            lt = np.bincount(land[m].astype(int), minlength=6).argmax() if m.any() else strata.OTHER
            cls = 2 if lt in (strata.CROPLAND, strata.VEGETATION) else (3 if lt == strata.OPEN_WATER else 1)
            rows.append({"geometry": g, "class": cls, "confidence": 1, "tile_id": tid,
                         "evidence": f"CANDIDATE from NDWI>{NDWI_WATER} on S2 {date} - REVIEW",
                         "labeller": "", "date_labelled": "", "note": "candidate: confirm, fix or delete"})
            n_w += 1
        # close small gaps only: dilating cloud swallows the clear land between
        # clouds, and that land is exactly where the labeller can still work
        from scipy import ndimage as _nd

        bad_merged = _nd.binary_closing(bad, np.ones((5, 5)))
        lab, n = _nd.label(bad_merged)
        if n:
            sizes = _nd.sum(bad_merged, lab, range(1, n + 1))
            bad_merged = np.isin(lab, 1 + np.flatnonzero(sizes >= 60))   # 0.6 ha
        for g in polygonise(bad_merged, grid):
            rows.append({"geometry": g, "class": -1, "confidence": 1, "tile_id": tid,
                         "evidence": f"cloud or shadow in S2 {date} - optical unusable here",
                         "labeller": "", "date_labelled": "", "note": "uncertain: no usable optical"})
            n_u += 1
        summary.append((tid, n_w, n_u, f"{100 * water.mean():.1f}% water"))

    print(f"\n{'tile':14s} {'water':>6s} {'uncert':>7s}  note")
    for tid, w, u, note in summary:
        print(f"{tid:14s} {w:6d} {u:7d}  {note}")
    print(f"\ntotal: {sum(s[1] for s in summary)} water candidates, {sum(s[2] for s in summary)} uncertain areas")
    if a.dry_run:
        print("dry run: nothing written")
        return
    if not rows:
        return
    import pandas as pd

    gdf = gpd.GeoDataFrame(rows, crs=f"EPSG:{feats[tiles[0]]['properties']['utm_epsg']}")
    existing = gpd.read_file(GPKG, layer="flood")
    if len(existing):
        gdf = gpd.GeoDataFrame(pd.concat([existing, gdf.to_crs(existing.crs)], ignore_index=True), crs=existing.crs)
    gdf.to_file(GPKG, layer="flood", driver="GPKG")
    print(f"\nwrote {len(rows)} polygons into {GPKG} layer 'flood'")
    print("Open QGIS, select the flood layer, and review: confirm (confidence 2-3), fix the edges, or delete.")


if __name__ == "__main__":
    main()
