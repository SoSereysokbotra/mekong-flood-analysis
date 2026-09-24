"""Add the layers that make water unambiguous to the human eye.

True colour cannot separate standing water from dark wet vegetation: both look
near-black. Infrared can, because water absorbs almost all near-infrared and
shortwave-infrared light while vegetation reflects NIR strongly.

For every Sentinel-2 scene already chosen per tile (recorded in
data/labels/optical_availability.csv) this writes, on the tile's 10 m grid:

    falsecolour_<role>_<date>.tif   SWIR(B11) / NIR(B08) / Red(B04) as RGB
                                    water = black or deep blue
                                    healthy vegetation = bright green
                                    bare soil = pink / magenta
    ndwi_<role>_<date>.tif          (Green - NIR) / (Green + NIR), float
                                    > 0 is water; styled 0-1 in QGIS

Both go in the tile's optical/ folder next to the true-colour clips.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_tier_b_imagery import OUT, tile_grid, write  # noqa: E402

ROLES = ("pre", "event", "post")


def main():
    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        feats = {x["properties"]["tile_id"]: x for x in json.load(f)["features"]}
    with open(catalog.DATA / "labels" / "optical_availability.csv") as f:
        avail = {r["tile_id"]: r for r in csv.DictReader(f)}
    cl = catalog._client()

    for tid, row in tqdm(sorted(avail.items(), key=lambda kv: int(kv[1]["label_order"])), desc="tiles"):
        grid = tile_grid(feats[tid])
        d = OUT / tid / "optical"
        for role in ROLES:
            date = row.get(f"{role}_date")
            if not date or float(row.get(f"{role}_clear_frac") or 0) <= 0.05:
                continue
            fc_path = d / f"falsecolour_{role}_{date}.tif"
            ndwi_path = d / f"ndwi_{role}_{date}.tif"
            if fc_path.exists() and ndwi_path.exists():
                continue
            xs = [p[0] for p in feats[tid]["geometry"]["coordinates"][0]]
            ys = [p[1] for p in feats[tid]["geometry"]["coordinates"][0]]
            items = [i for i in cl.search(collections=["sentinel-2-l2a"],
                                          bbox=[min(xs), min(ys), max(xs), max(ys)],
                                          datetime=f"{date}/{date}").items()]
            if not items:
                continue
            it = min(items, key=lambda i: i.properties["eo:cloud_cover"])
            try:
                b03, b04, b08, b11 = (io._read_on_grid(it.assets[b].href, grid, Resampling.bilinear)[0].astype(np.float32)
                                      for b in ("B03", "B04", "B08", "B11"))
            except Exception as e:  # noqa: BLE001
                tqdm.write(f"{tid} {role}: {e.__class__.__name__}")
                continue
            fc = np.stack([np.clip(b11 / 3000, 0, 1), np.clip(b08 / 4000, 0, 1), np.clip(b04 / 3000, 0, 1)]) * 255
            write(fc_path, fc, grid, "uint8")
            with np.errstate(divide="ignore", invalid="ignore"):
                ndwi = (b03 - b08) / (b03 + b08)
            write(ndwi_path, np.nan_to_num(ndwi, nan=-1).astype(np.float32), grid, "float32", nodata=-999)

    n = sum(1 for _ in OUT.rglob("falsecolour_*.tif"))
    print(f"\nwrote {n} false-colour and matching NDWI rasters")
    print("In QGIS: add falsecolour_event_* (water is black/deep blue) and ndwi_event_* "
          "(style: singleband pseudocolour, min 0 max 0.5 -> anything coloured is water).")


if __name__ == "__main__":
    main()
