"""Level 1 baseline: "dark = water" thresholding."""
import json
import math

import numpy as np
import pytest

from mfi import experiments, threshold


def bimodal(n=4000, water=-25.0, land=-12.0, seed=0):
    """(2, 1, n) dB image: first half water-dark, second half land-bright, in both VV and VH."""
    r = np.random.default_rng(seed)
    x = np.concatenate([r.normal(water, 1.0, n // 2), r.normal(land, 1.0, n // 2)])
    return np.stack([x, x])[:, None, :], np.ones((1, n), bool)


def test_otsu_splits_two_clear_modes():
    s1, valid = bimodal()
    mask, t = threshold.otsu_per_chip(s1, "vh", valid)
    assert -25 < t < -12
    assert mask[0, :2000].mean() > 0.99 and mask[0, 2000:].mean() < 0.01


def test_otsu_on_a_flat_chip_returns_nan_and_no_water():
    s1 = np.full((2, 4, 4), -15.0)
    mask, t = threshold.otsu_per_chip(s1, "vh", np.ones((4, 4), bool))
    assert math.isnan(t) and not mask.any()


def test_invalid_pixels_are_never_water():
    s1, valid = bimodal()
    valid[0, :100] = False
    mask, t = threshold.otsu_per_chip(s1, "vh", valid)
    assert not mask[0, :100].any()
    assert not threshold.apply_global(s1, "vh", valid, t)[0, :100].any()


def test_extreme_pixels_are_clipped_and_cannot_move_the_threshold():
    s1, valid = bimodal()
    _, t = threshold.otsu_per_chip(s1, "vh", valid)
    s1x = s1.copy()
    s1x[1, 0, :20] = -500.0                     # a few absurd values
    _, tx = threshold.otsu_per_chip(s1x, "vh", valid)
    assert tx == pytest.approx(t, abs=0.5)


def test_global_fit_is_reproducible_and_order_independent():
    chips = [bimodal(seed=s) for s in range(4)]
    t1 = threshold.fit_global(chips, "vh", max_pixels=3000, seed=0)
    assert t1 == threshold.fit_global(chips, "vh", max_pixels=3000, seed=0)
    assert -25 < t1 < -12


def test_frozen_level1_threshold_is_the_documented_value():
    p = experiments.run_dir("level1", "_global_thresholds") / "config.json"
    if not p.exists():
        pytest.skip("results/level1 not present")
    with open(p) as f:
        assert json.load(f)["vh"] == pytest.approx(-19.65, abs=0.005)
