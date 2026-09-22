"""Cache Copernicus DEM GLO-30 on every Sen1Floods11 hand-labelled chip grid.

One STAC search per *event* (chips of an event are clustered), then chip reads
straight from blob storage. Idempotent; sequential with a short pause so the
STAC API is not rate-limited. Retries transient errors.
"""
import collections
import pathlib
import sys
import time

import rasterio
from rasterio.warp import transform_bounds
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, io  # noqa: E402


def event_items(chips):
    """DEM items covering the union bbox of these chips (single STAC search, with retries)."""
    l = b = float("inf")
    r = t = float("-inf")
    for c in chips:
        with rasterio.open(catalog.s1f11_paths(c)["s1"]) as src:
            cl, cb, cr, ct = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        l, b, r, t = min(l, cl), min(b, cb), max(r, cr), max(t, ct)
    for i in range(6):
        try:
            return list(catalog._client().search(collections=["cop-dem-glo-30"], bbox=[l, b, r, t]).items())
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"STAC search kept failing: {err!r}")


by_event = collections.defaultdict(list)
for c in catalog.s1f11_hand_chips():
    if not (catalog.DATA / "interim" / "dem_chips" / f"{c}_CopDEM30.tif").exists():
        by_event[catalog.s1f11_event(c)].append(c)
print({e: len(v) for e, v in by_event.items()})

failed = []
for event, chips in by_event.items():
    items = event_items(chips)
    print(f"{event}: {len(items)} DEM tiles for {len(chips)} chips")
    for c in tqdm(chips, desc=event, leave=False):
        for i in range(4):
            try:
                io.dem_chip(c, items=items)
                break
            except Exception as e:  # noqa: BLE001
                err = e
                time.sleep(5 * (i + 1))
        else:
            failed.append((c, repr(err)[:120]))
print(f"done, {len(failed)} failed")
for f in failed:
    print("  ", *f)
