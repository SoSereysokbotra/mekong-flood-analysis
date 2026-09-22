"""The single experiment log. Every run of every level appends one row here,
by code, never by hand. Documents and figures cite run ids from this file and
are generated from the per-run artefacts, so numbers cannot drift between
documents.

Layout:
    results/experiment_log.csv                 one row per (run, split)
    results/<level>/<run_id>/config.json       what was run
    results/<level>/<run_id>/metrics_<split>.json
    results/<level>/<run_id>/per_chip_<split>.csv
    results/<level>/<run_id>/pred/             predictions (git-ignored)

Test-set rows are written only by an explicit `--test` invocation, and the log
records which run was selected on valid *before* any test row exists, so the
choice can be audited (mistake #3 in Mistake_avoidance.md).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import subprocess

from . import catalog, metrics

RESULTS = catalog.ROOT / "results"
LOG = RESULTS / "experiment_log.csv"

LOG_FIELDS = [
    "timestamp", "level", "run_id", "split", "method", "params", "git_commit", "n_chips",
    *[f"{g}_{k}" for g in metrics.GROUPS for k in ("iou", "recall", "precision")],
    "note",
]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=catalog.ROOT, text=True).strip()
    except Exception:
        return ""


def run_dir(level: str, run_id: str) -> pathlib.Path:
    d = RESULTS / level / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_config(level: str, run_id: str, config: dict) -> None:
    with open(run_dir(level, run_id) / "config.json", "w") as f:
        json.dump(config, f, indent=2, default=str)


def save_split_results(level: str, run_id: str, split: str, conf: metrics.Confusion, per_chip: list[dict]) -> dict:
    d = run_dir(level, run_id)
    m = conf.metrics()
    with open(d / f"metrics_{split}.json", "w") as f:
        json.dump(m, f, indent=2)
    if per_chip:
        with open(d / f"per_chip_{split}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(per_chip[0].keys()))
            w.writeheader()
            w.writerows(per_chip)
    return m


def _migrate_header() -> None:
    """If GROUPS grew since the log was created, rewrite it with the new columns (old rows get '')."""
    if not LOG.exists():
        return
    rows = read_log()
    if rows and list(rows[0].keys()) == LOG_FIELDS:
        return
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in LOG_FIELDS})


def log_row(level: str, run_id: str, split: str, method: str, params: dict, n_chips: int,
            m: dict, note: str = "") -> None:
    RESULTS.mkdir(exist_ok=True)
    _migrate_header()
    new = not LOG.exists()
    row = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "level": level, "run_id": run_id, "split": split, "method": method,
        "params": json.dumps(params, sort_keys=True, default=str), "git_commit": git_commit(),
        "n_chips": n_chips, **metrics.flat(m), "note": note,
    }
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def read_log() -> list[dict]:
    if not LOG.exists():
        return []
    with open(LOG, newline="") as f:
        return list(csv.DictReader(f))


def record_selection(level: str, run_id: str, criterion: str) -> None:
    """Append a 'selected' marker row: this run was chosen on valid by `criterion`.

    Must be called before any test row for that level is written.
    """
    if any(r["level"] == level and r["split"] == "test" for r in read_log()):
        raise RuntimeError(f"test rows already exist for {level}; selection must be recorded first")
    log_row(level, run_id, "selection", "", {"criterion": criterion}, 0,
            {g: {"iou": float("nan"), "recall": float("nan"), "precision": float("nan")} for g in metrics.GROUPS},
            note=f"selected on valid by {criterion}")
