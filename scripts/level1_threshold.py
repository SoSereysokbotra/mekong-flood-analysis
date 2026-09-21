"""Level 1: the no-AI baseline. Dark pixels = water, by histogram thresholding.

Methods (each is one run in the experiment log):
    otsu_vh_perchip   Otsu on VH, fitted per chip (the Sen1Floods11 authors' method)
    otsu_vv_perchip   Otsu on VV, fitted per chip
    otsu_vh_global    one VH threshold fitted on the training split
    otsu_vv_global    one VV threshold fitted on the training split
    authors_otsu      the S1OtsuLabelHand layer shipped with the dataset (implementation cross-check)

Every run is scored per land type on train and valid. The best method is then
chosen on valid by cropland IoU (the hypothesis stratum) and that choice is
written to the log. Only `--test` scores the held-out Mekong chips, and it
refuses to run until a selection has been recorded (Mistake_avoidance.md #3).

Predictions are saved as GeoTIFFs under results/level1/<run>/pred/ so Level 2
can look at exactly the failures that were scored (Mistake_avoidance.md #1).

Usage:
    python scripts/level1_threshold.py          # train + valid, record selection
    python scripts/level1_threshold.py --test   # score Mekong for every run
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import rasterio
from tqdm import tqdm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import catalog, experiments, io, metrics, strata, threshold  # noqa: E402

LEVEL = "level1"
METHODS = ["otsu_vh_perchip", "otsu_vv_perchip", "otsu_vh_global", "otsu_vv_global", "authors_otsu"]
# Candidates for selection are the project's own methods. authors_otsu is a
# cross-check only: it is ~94% identical to a per-event VH threshold fitted on
# each whole scene, including the held-out Mekong scene (see docs/level1).
CANDIDATES = [m for m in METHODS if m != "authors_otsu"]
# Cropland IoU, not recall: recall alone rewards calling everything water.
# IoU is the single number that penalises both misses and false alarms; the
# recall-vs-precision trade-off itself is set at Level 2 when X and Y are fixed.
SELECTION_CRITERION = "valid cropland_iou among project methods (tie-break: valid all_iou)"


def load(chip: str):
    s1, label, grid = io.read_s1f11_chip(chip)
    land = strata.land_type(io.worldcover_chip(chip, grid))
    return s1, label, land, grid


def predict(method: str, chip: str, s1, label, global_t: dict) -> tuple[np.ndarray, float]:
    valid = label >= 0
    if method == "authors_otsu":
        otsu = io.read_s1f11_layer(chip, "otsu")
        return (otsu == 1) & valid, float("nan")
    band = "vh" if "_vh_" in method else "vv"
    if method.endswith("perchip"):
        return threshold.otsu_per_chip(s1, band, valid)
    t = global_t[band]
    return threshold.apply_global(s1, band, valid, t), t


def save_pred(run_dir: pathlib.Path, chip: str, pred: np.ndarray, grid: io.Grid) -> None:
    d = run_dir / "pred"
    d.mkdir(exist_ok=True)
    with rasterio.open(
        d / f"{chip}.tif", "w", driver="GTiff", height=grid.height, width=grid.width, count=1,
        dtype="uint8", crs=grid.crs, transform=grid.transform, compress="deflate",
    ) as dst:
        dst.write(pred.astype(np.uint8), 1)


def run_split(method: str, split: str, chips: list[str], global_t: dict) -> dict:
    conf = metrics.Confusion()
    per_chip = []
    run_dir = experiments.run_dir(LEVEL, method)
    for chip in tqdm(chips, desc=f"{method:16s} {split}", leave=False):
        s1, label, land, grid = load(chip)
        pred, t = predict(method, chip, s1, label, global_t)
        c = metrics.Confusion().add(pred, label, land)
        conf.merge(c)
        m = c.metrics()
        per_chip.append({
            "chip": chip, "event": catalog.s1f11_event(chip), "threshold_db": t,
            **{f"{g}_{k}": m[g][k] for g in ("all", "cropland", "open_water", "vegetation") for k in ("iou", "recall", "precision", "n_pos")},
        })
        save_pred(run_dir, chip, pred, grid)
    m = experiments.save_split_results(LEVEL, method, split, conf, per_chip)
    params = {"band": "vh" if "_vh_" in method else ("vv" if "_vv_" in method else "vh"),
              "fit": method.split("_")[-1], "clip_db": list(threshold.CLIP)}
    if method.endswith("global"):
        params["threshold_db"] = global_t[params["band"]]
    experiments.log_row(LEVEL, method, split, method, params, len(chips), m)
    return m


def fmt(m: dict) -> str:
    g = lambda grp, k: m[grp][k]  # noqa: E731
    return (f"all IoU {g('all','iou'):.3f} rec {g('all','recall'):.3f} | "
            f"cropland IoU {g('cropland','iou'):.3f} rec {g('cropland','recall'):.3f} prec {g('cropland','precision'):.3f} | "
            f"open_water rec {g('open_water','recall'):.3f} | vegetation rec {g('vegetation','recall'):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="score the held-out Mekong split (requires a recorded selection)")
    args = ap.parse_args()
    split = catalog.s1f11_split()

    if args.test:
        log = experiments.read_log()
        sel = [r for r in log if r["level"] == LEVEL and r["split"] == "selection"]
        if not sel:
            sys.exit("refusing: no selection recorded for level1; run without --test first")
        print(f"selection on record: {sel[-1]['run_id']} ({sel[-1]['note']})")
        global_t = {b: _global_t(b) for b in ("vv", "vh")}
        print(f"global thresholds (from train): VV {global_t['vv']:.2f} dB, VH {global_t['vh']:.2f} dB")
        print("\n== TEST (Mekong, held out) ==")
        for method in METHODS:
            m = run_split(method, "test", split["test"], global_t)
            print(f"{method:16s} {fmt(m)}")
        return

    # --- fit global thresholds on train only ---------------------------------
    train_pairs = []
    for chip in tqdm(split["train"], desc="loading train for global fit", leave=False):
        s1, label, _, _ = load(chip)
        train_pairs.append((s1, label >= 0))
    global_t = {b: threshold.fit_global(train_pairs, b) for b in ("vv", "vh")}
    del train_pairs
    print(f"global thresholds (fit on train): VV {global_t['vv']:.2f} dB, VH {global_t['vh']:.2f} dB")
    experiments.save_config(LEVEL, "_global_thresholds", {"fit_split": "train", **global_t,
                                                         "clip_db": list(threshold.CLIP)})

    results = {}
    for s in ("train", "valid"):
        print(f"\n== {s.upper()} ==")
        for method in METHODS:
            experiments.save_config(LEVEL, method, {"method": method, "global_thresholds": global_t})
            m = run_split(method, s, split[s], global_t)
            results[(method, s)] = m
            print(f"{method:16s} {fmt(m)}")

    # --- select on valid, record before any test row exists ------------------
    def key(method):
        m = results[(method, "valid")]
        return (np.nan_to_num(m["cropland"]["iou"], nan=-1), np.nan_to_num(m["all"]["iou"], nan=-1))

    best = max(CANDIDATES, key=key)
    experiments.record_selection(LEVEL, best, SELECTION_CRITERION)
    print(f"\nselected on valid: {best}  ({SELECTION_CRITERION})")
    print("run with --test to score the held-out Mekong chips")


def _global_t(band: str) -> float:
    import json
    with open(experiments.run_dir(LEVEL, "_global_thresholds") / "config.json") as f:
        return float(json.load(f)[band])


if __name__ == "__main__":
    main()
