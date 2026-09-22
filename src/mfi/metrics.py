"""Scoring. Every score in this project is a function of the triple
(prediction, hand label, land type), so per-land-type precision, recall and
IoU are always available and a pooled number can never stand alone.

Confusion counts are accumulated as pixel totals across chips and metrics are
computed from the totals ("micro" averaging). Per-chip averaging would let a
few tiny-flood chips dominate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import strata

LANDS = list(strata.LAND_NAMES.values())  # open_water, cropland, vegetation, built, other, unknown

# The hypothesis sub-strata. "Bright" flooded cropland is the double-bounce
# case: labelled flood, on cropland, with VH at or above the Level 1 global
# threshold. By construction the Level 1 baseline has recall 0 here; a model
# that "solves" double bounce must show recall on this group without losing
# precision on dry cropland. The constant is the Level 1 train-fit threshold,
# frozen (results/level1/_global_thresholds/config.json), not recomputed.
BRIGHT_VH_DB = -19.65
SUBSTRATA = ["cropland_bright", "cropland_dark", "vegetation_bright"]
GROUPS = ["all"] + LANDS + SUBSTRATA


@dataclass
class Confusion:
    """TP/FP/FN/TN per land type plus 'all'. Only label in {0,1} pixels count."""

    tp: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})
    fp: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})
    fn: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})
    tn: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})

    def add(self, pred: np.ndarray, label: np.ndarray, land: np.ndarray, vh: np.ndarray | None = None) -> "Confusion":
        """Accumulate one chip. pred is bool, label int8 {-1,0,1}, land int8.

        `vh` (dB) enables the cropland_bright / cropland_dark sub-strata. They
        are defined on *labelled flood* pixels only, so for them FP is always 0
        and precision is meaningless: read their recall.
        """
        valid = label >= 0
        p, y = pred.astype(bool) & valid, label == 1
        masks = {"all": valid} | {name: valid & (land == code) for code, name in strata.LAND_NAMES.items()}
        crop_flood = valid & y & (land == strata.CROPLAND)
        veg_flood = valid & y & (land == strata.VEGETATION)
        if vh is not None:
            masks["cropland_bright"] = crop_flood & (vh >= BRIGHT_VH_DB)
            masks["cropland_dark"] = crop_flood & (vh < BRIGHT_VH_DB)
            masks["vegetation_bright"] = veg_flood & (vh >= BRIGHT_VH_DB)
        else:
            for g in SUBSTRATA:
                masks[g] = np.zeros(label.shape, bool)
        for g, m in masks.items():
            self.tp[g] += int((p & y & m).sum())
            self.fp[g] += int((p & ~y & m).sum())
            self.fn[g] += int((~p & y & m).sum())
            self.tn[g] += int((~p & ~y & m).sum())
        return self

    def merge(self, other: "Confusion") -> "Confusion":
        for g in GROUPS:
            self.tp[g] += other.tp[g]
            self.fp[g] += other.fp[g]
            self.fn[g] += other.fn[g]
            self.tn[g] += other.tn[g]
        return self

    def metrics(self) -> dict[str, dict[str, float | int]]:
        """{group: {precision, recall, iou, f1, tp, fp, fn, tn, n_pos}}. NaN where undefined."""
        out = {}
        for g in GROUPS:
            tp, fp, fn, tn = self.tp[g], self.fp[g], self.fn[g], self.tn[g]
            prec = tp / (tp + fp) if tp + fp else float("nan")
            rec = tp / (tp + fn) if tp + fn else float("nan")
            iou = tp / (tp + fp + fn) if tp + fp + fn else float("nan")
            f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else float("nan")
            out[g] = {"precision": prec, "recall": rec, "iou": iou, "f1": f1,
                      "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n_pos": tp + fn}
        return out


def flat(metrics: dict[str, dict[str, float | int]], keys=("iou", "recall", "precision")) -> dict[str, float]:
    """Flatten to {'cropland_iou': ..., 'all_recall': ...} for CSV rows."""
    return {f"{g}_{k}": metrics[g][k] for g in metrics for k in keys}
