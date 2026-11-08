"""Scoring: every number in the project goes through metrics.Confusion."""
import math

import numpy as np
import pytest

from mfi import metrics, strata

C, V = strata.CROPLAND, strata.VEGETATION


def score(pred, label, land, vh=None):
    return metrics.Confusion().add(np.array(pred, bool), np.array(label, np.int8), np.array(land, np.int8),
                                   None if vh is None else np.array(vh, float)).metrics()


def test_counts_and_ratios_by_hand():
    # pred:  1 1 0 0 1 ;  label: 1 0 1 0 1  -> tp 2, fp 1, fn 1, tn 1
    m = score([1, 1, 0, 0, 1], [1, 0, 1, 0, 1], [C] * 5)["cropland"]
    assert (m["tp"], m["fp"], m["fn"], m["tn"], m["n_pos"]) == (2, 1, 1, 1, 3)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["iou"] == pytest.approx(2 / 4)
    assert m["f1"] == pytest.approx(4 / 6)


def test_precision_and_recall_are_not_swapped():
    # FP != FN, so swapping the two formulas would fail (Gemini review: the case above has FP == FN)
    # pred: 1 1 1 0 0 ; label: 1 1 0 1 1 -> tp 2, fp 1, fn 2
    m = score([1, 1, 1, 0, 0], [1, 1, 0, 1, 1], [C] * 5)["cropland"]
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 4)
    assert m["iou"] == pytest.approx(2 / 5)


def test_ignored_pixels_never_count():
    # the two label -1 pixels are predicted water; they must not become false positives
    m = score([1, 1, 1, 0], [1, -1, -1, 0], [C] * 4)["all"]
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 0, 0, 1)


def test_land_types_are_separate_and_add_up_to_all():
    pred, label = [1, 0, 1, 1, 0, 1], [1, 1, 0, 1, 0, 0]
    land = [C, C, C, V, V, strata.BUILT]
    m = score(pred, label, land)
    for k in ("tp", "fp", "fn", "tn"):
        assert m["all"][k] == sum(m[name][k] for name in strata.LAND_NAMES.values())
    assert (m["cropland"]["tp"], m["cropland"]["fn"], m["cropland"]["fp"]) == (1, 1, 1)
    assert (m["vegetation"]["tp"], m["vegetation"]["tn"]) == (1, 1)


def test_undefined_ratios_are_nan_not_zero():
    m = score([0, 0], [0, 0], [C, C])["cropland"]          # no water anywhere
    assert math.isnan(m["precision"]) and math.isnan(m["recall"]) and math.isnan(m["iou"])
    assert math.isnan(score([0], [0], [C])["open_water"]["iou"])   # empty group


def test_bright_substrata_use_the_frozen_threshold():
    t = metrics.BRIGHT_VH_DB
    # four flooded cropland pixels: two bright (VH >= t), two dark; model finds one of each
    m = score([1, 0, 1, 0], [1, 1, 1, 1], [C] * 4, vh=[t, t + 5, t - 1, t - 5])
    assert m["cropland_bright"]["recall"] == pytest.approx(0.5)
    assert m["cropland_dark"]["recall"] == pytest.approx(0.5)
    assert m["cropland_bright"]["fp"] == 0                   # defined on flooded pixels only


def test_substrata_empty_without_vh():
    m = score([1], [1], [C])
    assert m["cropland_bright"]["n_pos"] == 0


def test_merge_equals_adding_both_chips():
    a = ([1, 0, 1], [1, 1, 0], [C, C, V])
    b = ([0, 1, 1], [0, 1, 1], [V, C, C])
    merged = metrics.Confusion().add(*map(np.array, a)).merge(metrics.Confusion().add(*map(np.array, b))).metrics()
    together = score(a[0] + b[0], a[1] + b[1], a[2] + b[2])
    counts = ("tp", "fp", "fn", "tn")                        # NaN != NaN, so compare counts
    assert {g: [merged[g][k] for k in counts] for g in merged} == {g: [together[g][k] for k in counts] for g in together}


def test_flat_keys():
    f = metrics.flat(score([1], [1], [C]))
    assert f["cropland_iou"] == 1.0 and "all_recall" in f and "vegetation_precision" in f
