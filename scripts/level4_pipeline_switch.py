"""Level 4 step 2 (plan rule 9): measure the pre-processing switch.

Level 3 was trained and tested on Sen1Floods11 chips: sigma-nought, dB, from
Google Earth Engine. Level 4 will run on Planetary Computer RTC: gamma-nought,
linear, from Microsoft. Same satellite, different processing. Before any
Cambodia conclusion, this script asks: if the *same 30 Mekong chips* are
rebuilt from the RTC product for the *same date* (5 Aug 2018, S1B, orbit 26)
and scored against the *same hand labels*, how much do the Level 1 baseline
and the Level 3 models change?

Outputs:
    data/interim/chip_cache_gamma0/<chip>.npz      RTC gamma0 dB chips on the chip grids
    results/level4/pipeline_switch.json            per-band offsets + scores sigma0 vs gamma0 per method
    results/level4/pipeline_switch_per_chip.csv
    experiment_log rows: level4, split "test_gamma0", one per method

This re-scores the held-out chips, but with different *inputs*; no model or
threshold is chosen from it. It quantifies a known nuisance, as the plan requires.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, data, experiments, infer, io, metrics, rtc, strata  # noqa: E402

LEVEL = "level4"
G0_CACHE = catalog.DATA / "interim" / "chip_cache_gamma0"
METHODS = ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"]


def gamma0_chip(chip: str, items) -> np.ndarray:
    p = G0_CACHE / f"{chip}.npz"
    if p.exists():
        return np.load(p)["s1_db"]
    with rasterio.open(catalog.s1f11_paths(chip)["s1"]) as src:
        grid = io.Grid.of(src)
    s1 = rtc.rtc_db_on_grid(items, grid)
    G0_CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(p, s1_db=s1.astype(np.float32))
    return s1


def main():
    chips = catalog.s1f11_split()["test"]
    # one STAC search for the union footprint, exact date, exact track
    l = b = 1e9
    r = t = -1e9
    for c in chips:
        with rasterio.open(catalog.s1f11_paths(c)["s1"]) as src:
            cl, cb, cr, ct = src.bounds
        l, b, r, t = min(l, cl), min(b, cb), max(r, cr), max(t, ct)
    items = rtc.rtc_items([l, b, r, t], "2018-08-05", "2018-08-05", rel_orbit=26, orbit_state="ascending")
    print(f"RTC items: {[i.id[:40] for i in items]}")

    unets = {m: infer.load_unet(m) for m in METHODS if m.startswith("unet")}
    conf = {m: {"sigma0": metrics.Confusion(), "gamma0": metrics.Confusion()} for m in METHODS}
    offsets, rows = {"vv": [], "vh": []}, []
    for chip in tqdm(chips, desc="chips"):
        ch_s, label, land, _ = data.raw_channels(chip)            # sigma0 (as trained)
        g = gamma0_chip(chip, items)                                # gamma0 (as Level 4 will use)
        ch_g = {"vv": g[0], "vh": g[1], "ratio": g[0] - g[1], "slope": ch_s["slope"]}
        ok = (label >= 0) & np.isfinite(g[0]) & np.isfinite(g[1])
        for band in ("vv", "vh"):
            d = ch_g[band][ok] - ch_s[band][ok]
            offsets[band].append((float(np.median(d)), float(np.mean(d)), float(np.std(d)), float(np.corrcoef(ch_g[band][ok], ch_s[band][ok])[0, 1])))
        lab = label.copy()
        lab[~ok] = -1  # score both versions on exactly the same pixels
        row = {"chip": chip, "n_valid": int(ok.sum()),
               "vv_offset_median": offsets["vv"][-1][0], "vh_offset_median": offsets["vh"][-1][0],
               "vv_corr": offsets["vv"][-1][3], "vh_corr": offsets["vh"][-1][3]}
        for m in METHODS:
            for ver, ch in (("sigma0", ch_s), ("gamma0", ch_g)):
                if m == "otsu_vh_global":
                    pred = infer.predict_threshold(ch, "vh") == 1
                else:
                    model, channels, norm, device = unets[m]
                    pred = infer.predict_unet(model, channels, norm, device, ch) == 1
                c = metrics.Confusion().add(pred, lab, land, vh=ch_s["vh"])  # sub-strata defined on the sigma0 VH, as at Level 3
                conf[m][ver].merge(c)
                cm = c.metrics()
                row[f"{m}_{ver}_bright_rec"] = cm["cropland_bright"]["recall"]
                row[f"{m}_{ver}_crop_prec"] = cm["cropland"]["precision"]
        rows.append(row)

    out = experiments.RESULTS / LEVEL
    out.mkdir(parents=True, exist_ok=True)
    summary = {"rtc_items": [i.id for i in items], "n_chips": len(chips),
               "offset_gamma0_minus_sigma0_db": {b: {"median_of_chip_medians": float(np.median([o[0] for o in offsets[b]])),
                                                     "mean": float(np.mean([o[1] for o in offsets[b]])),
                                                     "within_chip_std": float(np.mean([o[2] for o in offsets[b]])),
                                                     "corr": float(np.mean([o[3] for o in offsets[b]]))} for b in ("vv", "vh")},
               "scores": {}}
    for m in METHODS:
        summary["scores"][m] = {}
        for ver in ("sigma0", "gamma0"):
            mm = conf[m][ver].metrics()
            summary["scores"][m][ver] = {g: {k: mm[g][k] for k in ("iou", "recall", "precision")} for g in ("all", "cropland", "cropland_bright", "vegetation_bright", "cropland_dark", "open_water")}
            experiments.log_row(LEVEL, f"switch_{m}", f"test_{ver}", m, {"input": ver, "date": "2018-08-05", "track": "26A"}, len(chips), mm,
                                note="pipeline-switch measurement (plan rule 9); same chips, same labels, different processing")
    with open(out / "pipeline_switch.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(out / "pipeline_switch_per_chip.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    o = summary["offset_gamma0_minus_sigma0_db"]
    print(f"\ngamma0 - sigma0 offset: VV {o['vv']['median_of_chip_medians']:+.2f} dB (corr {o['vv']['corr']:.3f}), "
          f"VH {o['vh']['median_of_chip_medians']:+.2f} dB (corr {o['vh']['corr']:.3f}); within-chip std VV {o['vv']['within_chip_std']:.2f}, VH {o['vh']['within_chip_std']:.2f}")
    print(f"\n{'method':18s} {'input':7s} {'allIoU':>6s} {'cropIoU':>7s} {'prec':>6s} {'rec':>6s} {'bright-crop':>11s} {'bright-veg':>10s} {'dark':>6s} {'water':>6s}")
    for m in METHODS:
        for ver in ("sigma0", "gamma0"):
            s = summary["scores"][m][ver]
            print(f"{m:18s} {ver:7s} {s['all']['iou']:6.3f} {s['cropland']['iou']:7.3f} {s['cropland']['precision']:6.3f} {s['cropland']['recall']:6.3f} "
                  f"{s['cropland_bright']['recall']:11.3f} {s['vegetation_bright']['recall']:10.3f} {s['cropland_dark']['recall']:6.3f} {s['open_water']['recall']:6.3f}")


if __name__ == "__main__":
    main()
