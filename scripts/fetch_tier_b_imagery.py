"""Fetch the imagery the Tier B labeller needs, clipped to the 20 tiles, and
report honestly which tiles actually have usable optical on the event date.

The plan (Section 5) warns that Tier C optical may not exist near the event.
Over this province in 2020 the least cloudy Sentinel-2 scenes are:
    pre    25 Sep, 12 % cloud   -- good: land cover and pre-event state
    event  20-23 Oct, 50-58 %   -- poor at scene level
    post    9 Nov,  5 %         -- excellent, but the flood is receding
Scene-level cloud is not per-tile cloud, so this script measures the real
clear fraction over each 2 x 2 km tile from the Sentinel-2 scene classification
band and keeps the clearest event-window scenes for that tile.

Per tile (10 m grid, the tile's UTM CRS):
    optical/pre_<date>_cloud<pct>.tif      true colour
    optical/event_<date>_cloud<pct>.tif    true colour, clearest over THIS tile
    optical/post_<date>_cloud<pct>.tif     true colour
    radar_use_last/s1_<date>_vv_vh_db.tif  VV/VH dB, three dates

Also writes data/labels/optical_availability.csv: per tile, the clear fraction
of the best event-window scene. A tile with a low value cannot be labelled from
event-date optical and must rely on the pre/post pair plus terrain — record that
in the polygon's `evidence` field.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io, rtc  # noqa: E402

OUT = catalog.DATA / "labels" / "imagery"
TILE_RES_M = 10.0
S1_DATES = ["2020-09-26", "2020-10-14", "2020-11-01"]
WINDOWS = {"pre": ("2020-09-01", "2020-09-30"),
           "event": ("2020-10-05", "2020-10-25"),
           "post": ("2020-11-01", "2020-11-20")}
# Sentinel-2 scene classification values that are usable ground
SCL_CLEAR = {4, 5, 6, 7}   # vegetation, bare, water, unclassified-but-not-cloud


def tile_grid(feat) -> io.Grid:
    from rasterio.warp import transform_geom

    epsg = feat["properties"]["utm_epsg"]
    g = transform_geom("EPSG:4326", f"EPSG:{epsg}", feat["geometry"])
    xs = [p[0] for p in g["coordinates"][0]]
    ys = [p[1] for p in g["coordinates"][0]]
    n = int(round((max(xs) - min(xs)) / TILE_RES_M))
    return io.Grid(rasterio.crs.CRS.from_epsg(epsg), from_origin(min(xs), max(ys), TILE_RES_M, TILE_RES_M), n, n)


def write(path: pathlib.Path, arr: np.ndarray, grid: io.Grid, dtype: str, nodata=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr.ndim == 2:
        arr = arr[None]
    with rasterio.open(path, "w", driver="GTiff", height=grid.height, width=grid.width,
                       count=arr.shape[0], dtype=dtype, crs=grid.crs, transform=grid.transform,
                       compress="deflate", nodata=nodata) as dst:
        dst.write(arr.astype(dtype))


def clear_fraction(item, grid) -> float:
    """Fraction of the tile that is clear ground in this scene, from the SCL band."""
    try:
        scl, _ = io._read_on_grid(item.assets["SCL"].href, grid, Resampling.nearest)
    except Exception:  # noqa: BLE001
        return 0.0
    return float(np.isin(scl, list(SCL_CLEAR)).mean())


def rgb_clip(item, grid) -> np.ndarray:
    bands = [io._read_on_grid(item.assets[b].href, grid, Resampling.bilinear)[0] for b in ("B04", "B03", "B02")]
    rgb = np.stack(bands).astype(np.float32)
    return np.clip(rgb / 3000.0, 0, 1) * 255   # 0-3000 reflectance covers land and water


def main():
    with open(catalog.DATA / "labels" / "tiles.geojson", encoding="utf-8") as f:
        feats = sorted(json.load(f)["features"], key=lambda x: x["properties"]["label_order"])
    cl = catalog._client()
    rows = []

    for feat in tqdm(feats, desc="tiles"):
        tid = feat["properties"]["tile_id"]
        grid = tile_grid(feat)
        d = OUT / tid
        xs = [p[0] for p in feat["geometry"]["coordinates"][0]]
        ys = [p[1] for p in feat["geometry"]["coordinates"][0]]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        row = {"tile_id": tid, "stratum": feat["properties"]["stratum"], "label_order": feat["properties"]["label_order"]}

        for role, (a, b) in WINDOWS.items():
            items = list(cl.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{a}/{b}").items())
            # scene cloud is a weak guide at 2 km scale: rank the plausible ones by
            # the actual clear fraction over this tile
            items = sorted(items, key=lambda i: i.properties["eo:cloud_cover"])[:6]
            scored = sorted(((clear_fraction(i, grid), i) for i in items), key=lambda x: -x[0])
            if not scored:
                row[f"{role}_clear_frac"] = 0.0
                continue
            best_frac, best = scored[0]
            row[f"{role}_clear_frac"] = round(best_frac, 3)
            row[f"{role}_date"] = best.properties["datetime"][:10]
            p = d / "optical" / f"{role}_{best.properties['datetime'][:10]}_clear{best_frac * 100:.0f}pct.tif"
            if not p.exists() and best_frac > 0.05:
                try:
                    write(p, rgb_clip(best, grid), grid, "uint8")
                except Exception as e:  # noqa: BLE001
                    tqdm.write(f"{tid} {role}: {e.__class__.__name__}")
            # for the event window also keep the runner-up: clouds move
            if role == "event" and len(scored) > 1 and scored[1][0] > 0.3:
                f2, i2 = scored[1]
                p2 = d / "optical" / f"event_alt_{i2.properties['datetime'][:10]}_clear{f2 * 100:.0f}pct.tif"
                if not p2.exists():
                    try:
                        write(p2, rgb_clip(i2, grid), grid, "uint8")
                    except Exception:  # noqa: BLE001
                        pass

        for date in S1_DATES:
            p = d / "radar_use_last" / f"s1_{date}_vv_vh_db.tif"
            if p.exists():
                continue
            items = rtc.rtc_items(bbox, date, date, rel_orbit=catalog.ANCHOR_REL_ORBIT,
                                  orbit_state=catalog.ANCHOR_ORBIT_STATE)
            if items:
                write(p, rtc.rtc_db_on_grid(items, grid), grid, "float32", nodata=float("nan"))
        rows.append(row)

    csv_path = catalog.DATA / "labels" / "optical_availability.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}, key=lambda k: (k != "label_order", k)))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["label_order"]))

    n = sum(1 for _ in OUT.rglob("*.tif"))
    good = [r for r in rows if r.get("event_clear_frac", 0) >= 0.7]
    part = [r for r in rows if 0.3 <= r.get("event_clear_frac", 0) < 0.7]
    print(f"\n{n} rasters under {OUT}")
    print(f"event-date optical: {len(good)}/{len(rows)} tiles >= 70 % clear, {len(part)} between 30 and 70 %, "
          f"{len(rows) - len(good) - len(part)} below 30 %")
    print(f"per-tile detail in {csv_path}")


if __name__ == "__main__":
    main()
