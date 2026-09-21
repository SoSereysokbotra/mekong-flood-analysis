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
GROUPS = ["all"] + LANDS


@dataclass
class Confusion:
    """TP/FP/FN/TN per land type plus 'all'. Only label in {0,1} pixels count."""

    tp: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})
    fp: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})
    fn: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})
    tn: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GROUPS})

    def add(self, pred: np.ndarray, label: np.ndarray, land: np.ndarray) -> "Confusion":
        """Accumulate one chip. pred is bool, label int8 {-1,0,1}, land int8."""
        valid = label >= 0
        p, y = pred.astype(bool) & valid, label == 1
        masks = {"all": valid} | {name: valid & (land == code) for code, name in strata.LAND_NAMES.items()}
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
