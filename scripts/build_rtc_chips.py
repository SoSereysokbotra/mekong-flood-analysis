"""Rebuild every Sen1Floods11 hand-labelled chip from Planetary Computer RTC
(gamma-nought, linear -> dB) on the chip's own grid, so training and the
Cambodia stage use one pre-processing pipeline (plan rule 9, evaluation_plan
v1.1). Labels, land type and slope are unchanged; only the radar changes.

One STAC search per event (the API rate-limits per-chip searches), exact date
and track from Sen1Floods11_Metadata.geojson. Paraguay has no RTC for its
2018-10-31 orbit-68 acquisition and is skipped; it is dropped from the split.

Writes data/interim/chip_cache_rtc/<chip>.npz with the same keys as the sigma0
cache (x = [vv, vh, ratio, slope] float16, label int8, land int8) plus
coverage stats, and results/level4/rtc_chip_build.json.
"""
from __future__ import annotations

import collections
import concurrent.futures as cf
import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, data, experiments, io, rtc  # noqa: E402

CACHE = catalog.DATA / "interim" / "chip_cache_rtc"
NO_RTC_EVENTS = ("Paraguay",)


def event_meta() -> dict[str, dict]:
    with open(catalog.S1F11 / "Sen1Floods11_Metadata.geojson", encoding="utf-8") as f:
        feats = json.load(f)["features"]
    m = {x["properties"]["location"]: x["properties"] for x in feats}
    m["Mekong"] = m.pop("Cambodia")  # chips are named Mekong_*
    return m


def union_bounds(chips):
    l = b = 1e9
    r = t = -1e9
    for c in chips:
        with rasterio.open(catalog.s1f11_paths(c)["s1"]) as src:
            cl, cb, cr, ct = src.bounds
        l, b, r, t = min(l, cl), min(b, cb), max(r, cr), max(t, ct)
    return [l, b, r, t]


def main():
    meta = event_meta()
    by_event = collections.defaultdict(list)
    for c in catalog.s1f11_hand_chips():
        by_event[catalog.s1f11_event(c)].append(c)

    CACHE.mkdir(parents=True, exist_ok=True)
    report = {"events": {}, "skipped_events": list(NO_RTC_EVENTS)}
    for event, chips in sorted(by_event.items()):
        if event in NO_RTC_EVENTS:
            print(f"{event:10s} skipped (no RTC for its acquisition)")
            continue
        p = meta[event]
        date = p["s1_date"].replace("/", "-")
        items = rtc.rtc_items(union_bounds(chips), date, date,
                              rel_orbit=int(p["rel_orbit_num"]), orbit_state=p["orbit"].lower())
        if not items:
            print(f"{event:10s} NO RTC ITEMS for {date} orbit {p['rel_orbit_num']} - skipping")
            report["events"][event] = {"date": date, "items": 0, "chips_written": 0}
            continue
        print(f"{event:10s} {date} orbit {int(p['rel_orbit_num']):3d}: {len(items)} RTC slices, {len(chips)} chips", flush=True)
        def build(chip, items=items):
            """Returns coverage, or None if already cached. Network-bound -> threaded."""
            out = CACHE / f"{chip}.npz"
            if out.exists():
                return None
            for attempt in range(4):
                try:
                    ch_s, label, land, _ = data.raw_channels(chip)  # sigma0 cache: label, land, slope
                    with rasterio.open(catalog.s1f11_paths(chip)["s1"]) as src:
                        grid = io.Grid.of(src)
                    s1 = rtc.rtc_db_on_grid(items, grid)
                    break
                except Exception:  # noqa: BLE001 - transient COG/TLS errors under parallel load
                    if attempt == 3:
                        raise
                    time.sleep(3 * (attempt + 1))
            cov = float(np.isfinite(s1).all(axis=0).mean())
            x = np.stack([s1[0], s1[1], s1[0] - s1[1], ch_s["slope"]]).astype(np.float16)
            np.savez(out, x=x, label=label.astype(np.int8), land=land.astype(np.int8), coverage=np.float32(cov))
            return cov

        written, coverage = 0, []
        with cf.ThreadPoolExecutor(8) as ex:
            for cov in tqdm(ex.map(build, chips), total=len(chips), desc=event, leave=False):
                written += 1
                if cov is not None:
                    coverage.append(cov)
        report["events"][event] = {"date": date, "track": f"{int(p['rel_orbit_num'])}{p['orbit'][0]}",
                                   "items": [i.id for i in items], "chips_written": written,
                                   "mean_coverage": float(np.mean(coverage)) if coverage else None,
                                   "min_coverage": float(np.min(coverage)) if coverage else None}
        time.sleep(1)

    out_dir = experiments.RESULTS / "level4"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "rtc_chip_build.json", "w") as f:
        json.dump(report, f, indent=2)
    n = len(list(CACHE.glob("*.npz")))
    print(f"\nRTC chips on disk: {n}")
    for e, r in report["events"].items():
        if r.get("mean_coverage") is not None:
            print(f"  {e:10s} {r['chips_written']:3d} chips, coverage mean {r['mean_coverage']:.3f} min {r['min_coverage']:.3f}")


if __name__ == "__main__":
    main()
