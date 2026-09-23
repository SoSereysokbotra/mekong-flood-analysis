"""Fix the Tier B hand-labelling grid before any polygon is drawn
(data/labels/LABELLING_PROTOCOL.md section 2).

Candidate tiles are 2 x 2 km squares in EPSG:32648 that lie inside Banteay
Meanchey and have radar coverage on all three dates. Tiles are stratified by
the land type that dominates them, and within each stratum chosen by a fixed,
written rule -- not by how any model scored, which would make the labels
depend on the thing they are meant to test:

    cropland     >= 60% of tiles, picked by highest cropland fraction, spread
                 across the province by a minimum separation
    vegetation   tiles dominated by tree/grass/wetland
    built        tiles containing the most built-up land (Sisophon and towns)
    water        tiles containing permanent water (JRC), as negative controls

Ordering within the output is a fixed shuffle (seed 0) so the labeller does
not work through all of one stratum first.

Writes data/labels/tiles.geojson (tracked in git) and prints a summary.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_bounds, transform_geom

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, strata  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level4_cambodia import CACHE, DATES, MAPS, SUFFIX, aoi_grid  # noqa: E402

TILE_M = 2000.0
N_TILES = {"cropland": 12, "vegetation": 3, "built": 3, "water": 2}
MIN_SEP_M = 8000.0          # keep tiles of one stratum from clustering
OUT = catalog.DATA / "labels" / "tiles.geojson"


def main():
    grid, inside = aoi_grid()
    z = np.load(CACHE / "ancillary.npz")
    land, jrc = z["land"], z["jrc"]
    # Coverage comes from the flood maps: a pixel is -1 exactly where the radar
    # was missing or the pixel is outside the province, so >= 0 on all three
    # dates means usable everywhere. Avoids needing the multi-GB scene caches.
    import rasterio

    cov = np.ones(inside.shape, bool)
    for date in DATES:
        f = MAPS / f"otsu_vh_global_{date}{SUFFIX}.tif"
        if not f.exists():
            sys.exit(f"missing {f} - run scripts/level4_cambodia.py (or unzip level4_maps.zip) first")
        with rasterio.open(f) as src:
            cov &= src.read(1) >= 0

    step = int(TILE_M / (grid.transform.a))
    H, W = grid.height, grid.width
    cands = []
    for r0 in range(0, H - step + 1, step):
        for c0 in range(0, W - step + 1, step):
            sl = (slice(r0, r0 + step), slice(c0, c0 + step))
            ins, cv = inside[sl], cov[sl]
            if ins.mean() < 0.98 or cv.mean() < 0.99:
                continue
            lt = land[sl]
            frac = {name: float((lt == code).mean()) for code, name in strata.LAND_NAMES.items()}
            x = grid.transform.c + (c0 + step / 2) * grid.transform.a
            y = grid.transform.f + (r0 + step / 2) * grid.transform.e
            cands.append({"r0": r0, "c0": c0, "x": x, "y": y, "frac": frac,
                          "jrc_permanent_frac": float((jrc[sl] >= 80).mean())})
    print(f"{len(cands)} candidate 2x2 km tiles fully inside the province with radar on all three dates")

    def pick(key, n, score):
        chosen = []
        for cand in sorted(cands, key=score, reverse=True):
            if any(np.hypot(cand["x"] - c["x"], cand["y"] - c["y"]) < MIN_SEP_M for c in chosen):
                continue
            if cand.get("_taken"):
                continue
            cand["_taken"] = True
            cand["stratum"] = key
            chosen.append(cand)
            if len(chosen) == n:
                break
        return chosen

    tiles = []
    tiles += pick("cropland", N_TILES["cropland"], lambda c: c["frac"]["cropland"])
    tiles += pick("vegetation", N_TILES["vegetation"], lambda c: c["frac"]["vegetation"])
    tiles += pick("built", N_TILES["built"], lambda c: c["frac"]["built"])
    tiles += pick("water", N_TILES["water"], lambda c: c["jrc_permanent_frac"])

    rng = np.random.default_rng(0)
    order = rng.permutation(len(tiles))
    feats = []
    for rank, i in enumerate(order, 1):
        t = tiles[i]
        x0 = grid.transform.c + t["c0"] * grid.transform.a
        y0 = grid.transform.f + t["r0"] * grid.transform.e
        ring_utm = [[x0, y0], [x0 + TILE_M, y0], [x0 + TILE_M, y0 - TILE_M], [x0, y0 - TILE_M], [x0, y0]]
        geom_utm = {"type": "Polygon", "coordinates": [ring_utm]}
        geom_ll = transform_geom(f"EPSG:{grid.crs.to_epsg()}", "EPSG:4326", geom_utm)
        feats.append({"type": "Feature", "geometry": geom_ll, "properties": {
            "tile_id": f"BMC_{t['stratum'][:4].upper()}_{rank:02d}", "label_order": rank, "stratum": t["stratum"],
            "utm_epsg": grid.crs.to_epsg(), "size_m": TILE_M,
            **{f"frac_{k}": round(v, 3) for k, v in t["frac"].items() if v > 0},
            "jrc_permanent_frac": round(t["jrc_permanent_frac"], 3),
            "centre_lon": round(transform_bounds(grid.crs, "EPSG:4326", t["x"], t["y"], t["x"], t["y"])[0], 5),
            "centre_lat": round(transform_bounds(grid.crs, "EPSG:4326", t["x"], t["y"], t["x"], t["y"])[1], 5),
            "labeller": "", "date_labelled": "", "status": "todo"}})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection",
                   "properties": {"protocol": "data/labels/LABELLING_PROTOCOL.md",
                                  "selection_rule": "stratified by dominant land type; within stratum by land-type fraction "
                                                    "(water: JRC permanent fraction), min separation 8 km; order shuffled with seed 0; "
                                                    "no model output used"},
                   "features": feats}, f, indent=1)
    print(f"wrote {OUT}: {len(feats)} tiles ({TILE_M / 1000:.0f} x {TILE_M / 1000:.0f} km, "
          f"{len(feats) * (TILE_M / 1000) ** 2:.0f} km2 total)")
    key = {"cropland": "frac_cropland", "vegetation": "frac_vegetation",
           "built": "frac_built", "water": "frac_open_water"}
    for s in N_TILES:
        sel = [f for f in feats if f["properties"]["stratum"] == s]
        print(f"  {s:11s} {len(sel):2d} tiles, mean {key[s].removeprefix('frac_')} fraction "
              f"{np.mean([f['properties'].get(key[s], 0) for f in sel]):.2f}"
              + (f", mean JRC permanent {np.mean([f['properties']['jrc_permanent_frac'] for f in sel]):.2f}" if s == "water" else ""))
    print("\nlabel order:", ", ".join(f["properties"]["tile_id"] for f in feats))


if __name__ == "__main__":
    main()
