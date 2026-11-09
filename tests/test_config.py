"""Fast tests for configuration loading and validation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
import yaml

from mfi.aoi import METHODS, RES_M
from mfi.check import MIN_COVERAGE, SEL, VERDICT_MIN_KM2, VERDICT_RATIO
from mfi.config import ConfigError, load_check_config


def test_check_config_loads_exact_literal_values():
    """Verify that configs/check.yaml loads and matches the exact pre-registered values."""
    cfg = load_check_config()

    # Resolution: 20 m (2x native 10 m Sentinel-1 resolution)
    assert cfg.resolution_m == 20.0
    assert cfg.res_m == 20.0

    # Temporal comparison window: 18 days gap, 3 years baseline
    assert cfg.default_gap_days == 18
    assert cfg.gap == 18
    assert cfg.default_comparison_years == 3
    assert cfg.years == 3

    # Verdict rule: 2.0x baseline median and > 50.0 km2
    assert cfg.verdict_ratio == 2.0
    assert cfg.verdict_min_km2 == 50.0

    # Coverage threshold: 95%
    assert cfg.min_coverage == 0.95

    # Study track for Banteay Meanchey: 164 descending
    assert cfg.study_track.rel_orbit == 164
    assert cfg.study_track.orbit_state == "descending"
    assert tuple(cfg.study_track) == (164, "descending")

    # Models: three methods, selected model is unet_vvvh_cropw
    assert cfg.methods == ("otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw")
    assert cfg.selected_method == "unet_vvvh_cropw"
    assert cfg.sel == "unet_vvvh_cropw"


def test_module_aliases_match_config():
    """Module-level aliases in mfi.aoi and mfi.check must match the loaded config."""
    cfg = load_check_config()
    assert RES_M == cfg.resolution_m
    assert METHODS == list(cfg.methods)
    assert SEL == cfg.selected_method
    assert VERDICT_RATIO == cfg.verdict_ratio
    assert VERDICT_MIN_KM2 == cfg.verdict_min_km2
    assert MIN_COVERAGE == cfg.min_coverage


def test_check_config_is_frozen():
    """CheckConfig and StudyTrackConfig instances must be immutable."""
    cfg = load_check_config()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        cfg.resolution_m = 10.0  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        cfg.study_track.rel_orbit = 99  # type: ignore[misc]


def test_missing_keys_raise_clear_error(tmp_path):
    """Omitting any required top-level key must raise ConfigError naming the key."""
    base_data = {
        "resolution_m": 20.0,
        "default_gap_days": 18,
        "default_comparison_years": 3,
        "verdict_ratio": 2.0,
        "verdict_min_km2": 50.0,
        "min_coverage": 0.95,
        "study_track": {"rel_orbit": 164, "orbit_state": "descending"},
        "methods": ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"],
        "selected_method": "unet_vvvh_cropw",
    }

    for key in list(base_data.keys()):
        incomplete = {k: v for k, v in base_data.items() if k != key}
        cfg_file = tmp_path / f"missing_{key}.yaml"
        cfg_file.write_text(yaml.safe_dump(incomplete), encoding="utf-8")
        with pytest.raises(ConfigError) as exc:
            load_check_config(cfg_file)
        assert "Missing required key(s)" in str(exc.value)
        assert key in str(exc.value)


def test_misspelled_top_level_key_raises_clear_error(tmp_path):
    """A misspelled key (e.g. min_coverge) must be rejected with a clear error."""
    bad_data = {
        "resolution_m": 20.0,
        "default_gap_days": 18,
        "default_comparison_years": 3,
        "verdict_ratio": 2.0,
        "verdict_min_km2": 50.0,
        "min_coverge": 0.95,  # typo
        "study_track": {"rel_orbit": 164, "orbit_state": "descending"},
        "methods": ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"],
        "selected_method": "unet_vvvh_cropw",
    }
    cfg_file = tmp_path / "misspelled.yaml"
    cfg_file.write_text(yaml.safe_dump(bad_data), encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_check_config(cfg_file)
    assert "min_coverge" in str(exc.value)


def test_misspelled_track_key_raises_clear_error(tmp_path):
    """A misspelled key in study_track must be rejected with a clear error."""
    bad_data = {
        "resolution_m": 20.0,
        "default_gap_days": 18,
        "default_comparison_years": 3,
        "verdict_ratio": 2.0,
        "verdict_min_km2": 50.0,
        "min_coverage": 0.95,
        "study_track": {"relative_orbit": 164, "orbit_state": "descending"},  # typo
        "methods": ["otsu_vh_global", "unet_vv_ce", "unet_vvvh_cropw"],
        "selected_method": "unet_vvvh_cropw",
    }
    cfg_file = tmp_path / "bad_track.yaml"
    cfg_file.write_text(yaml.safe_dump(bad_data), encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_check_config(cfg_file)
    assert "relative_orbit" in str(exc.value) or "rel_orbit" in str(exc.value)


def test_invalid_selected_method_raises_clear_error(tmp_path):
    """selected_method must be present in methods."""
    bad_data = {
        "resolution_m": 20.0,
        "default_gap_days": 18,
        "default_comparison_years": 3,
        "verdict_ratio": 2.0,
        "verdict_min_km2": 50.0,
        "min_coverage": 0.95,
        "study_track": {"rel_orbit": 164, "orbit_state": "descending"},
        "methods": ["otsu_vh_global", "unet_vv_ce"],
        "selected_method": "unet_vvvh_cropw",  # not in methods
    }
    cfg_file = tmp_path / "bad_sel.yaml"
    cfg_file.write_text(yaml.safe_dump(bad_data), encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_check_config(cfg_file)
    assert "selected_method" in str(exc.value)


def test_nonexistent_config_raises_file_not_found(tmp_path):
    """Loading from a non-existent path must raise FileNotFoundError."""
    missing = tmp_path / "nonexistent.yaml"
    with pytest.raises(FileNotFoundError):
        load_check_config(missing)
