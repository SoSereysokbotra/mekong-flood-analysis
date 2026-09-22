"""Level 3: score the held-out Mekong split. Runs only after a selection has
been recorded in the experiment log (evaluation_plan.md section 5), and only
for (a) the selected run and (b) the fixed controls of section 6. Sweeps are
never scored on test.

Usage:
    python scripts/level3_test.py --select        # choose best run on valid, record it, commit reminder
    python scripts/level3_test.py --run <run_id>  # score one run on test (selected run or a listed control)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from mfi import data, experiments, metrics, models  # noqa: E402

LEVEL = "level3"
CONTROLS = {"pixel_logreg", "pixel_mlp", "unet_vv_ce"}  # section 6.2 and 6.3
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from level3_train import NORM_PATH, evaluate, fmt, selection_score  # noqa: E402


def candidates() -> list[str]:
    """Every level3 run with a valid metrics file, excluding controls."""
    out = []
    for d in (experiments.RESULTS / LEVEL).iterdir():
        if d.is_dir() and not d.name.startswith("_") and (d / "metrics_valid.json").exists() and d.name not in CONTROLS:
            out.append(d.name)
    return sorted(out)


def valid_metrics(run_id: str) -> dict:
    with open(experiments.run_dir(LEVEL, run_id) / "metrics_valid.json") as f:
        return json.load(f)


def select():
    rows = [(selection_score(valid_metrics(r)), r) for r in candidates()]
    rows.sort(reverse=True)
    print("valid selection score (min bright recall | crop IoU tie-break):")
    for (sc, tb), r in rows:
        print(f"  {r:20s} score {sc:.3f}  tie {tb:.3f}")
    best = rows[0][1]
    experiments.record_selection(LEVEL, best, "evaluation_plan v1.0 section 5: min(cropland_bright, vegetation_bright) recall on valid, "
                                              "subject to valid cropland precision >= 0.48; tie-break cropland IoU")
    print(f"\nrecorded selection: {best}\nNow commit results/experiment_log.csv, then run --run {best} and the controls.")


def score_test(run_id: str):
    log = experiments.read_log()
    sel = [r for r in log if r["level"] == LEVEL and r["split"] == "selection"]
    if not sel:
        sys.exit("refusing: no level3 selection recorded; run --select first")
    selected = sel[-1]["run_id"]
    if run_id != selected and run_id not in CONTROLS:
        sys.exit(f"refusing: {run_id} is neither the selected run ({selected}) nor a section-6 control")
    sp = data.splits()
    run_dir = experiments.run_dir(LEVEL, run_id)
    if run_id.startswith("pixel_"):
        from joblib import load
        from level3_pixel_control import evaluate as px_eval
        obj = load(run_dir / "model.joblib")
        conf, rows = px_eval(obj["clf"], obj["scaler"], sp["test"], save_dir=run_dir / "pred_test")
        m = experiments.save_split_results(LEVEL, run_id, "test", conf, rows)
        params = {"features": obj["feats"], "plan": "v1.0"}
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ck = torch.load(run_dir / "best.pt", map_location=device)
        model = models.build_model(ck["cfg"]["model"], len(ck["channels"]), False).to(device)
        model.load_state_dict(ck["model"])
        norm = data.load_norm(NORM_PATH)
        cm, rows = evaluate(model, sp["test"], ck["channels"], norm, device, save_pred_dir=run_dir / "pred_test")
        conf = metrics.Confusion()
        conf.tp, conf.fp, conf.fn, conf.tn = ({g: cm[g][k] for g in metrics.GROUPS} for k in ("tp", "fp", "fn", "tn"))
        m = experiments.save_split_results(LEVEL, run_id, "test", conf, rows)
        params = {k: ck["cfg"][k] for k in ck["cfg"] if k != "seed"} | {"best_epoch": ck["epoch"], "plan": "v1.0"}
    role = "selected" if run_id == selected else "control"
    experiments.log_row(LEVEL, run_id, "test", run_id, params, len(sp["test"]), m, note=f"held-out Mekong, {role}")
    per_chip_bright = [r["cropland_bright_recall"] for r in rows if r["cropland_bright_n_pos"] > 500]
    print(f"{run_id} ({role}) TEST: {fmt(m)}")
    print(f"  per-chip cropland_bright recall (chips with >500 bright px, n={len(per_chip_bright)}): "
          f"median {np.nanmedian(per_chip_bright):.3f}, min {np.nanmin(per_chip_bright):.3f}, max {np.nanmax(per_chip_bright):.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--run")
    a = ap.parse_args()
    if a.select:
        select()
    elif a.run:
        score_test(a.run)
    else:
        ap.print_help()
