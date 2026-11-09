"""Configuration loader for Mekong Flood Intelligence (MFI).

Loads frozen dataclass configurations from YAML files in configs/.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DEFAULT_CHECK_CONFIG_PATH = CONFIGS / "check.yaml"

EXPECTED_CHECK_KEYS = {
    "resolution_m",
    "default_gap_days",
    "default_comparison_years",
    "verdict_ratio",
    "verdict_min_km2",
    "min_coverage",
    "study_track",
    "methods",
    "selected_method",
}

EXPECTED_STUDY_TRACK_KEYS = {"rel_orbit", "orbit_state"}


class ConfigError(ValueError):
    """Raised when configuration values, keys, or structure are invalid."""


@dataclass(frozen=True)
class StudyTrackConfig:
    """Radar track specification for the study province."""

    rel_orbit: int
    orbit_state: str

    def __iter__(self):
        yield self.rel_orbit
        yield self.orbit_state

    def __getitem__(self, index: int) -> Any:
        return (self.rel_orbit, self.orbit_state)[index]

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, (tuple, list)):
            return (self.rel_orbit, self.orbit_state) == tuple(other)
        if isinstance(other, StudyTrackConfig):
            return (self.rel_orbit, self.orbit_state) == (other.rel_orbit, other.orbit_state)
        return False


@dataclass(frozen=True)
class CheckConfig:
    """Frozen configuration settings for flood check and multi-year comparisons."""

    resolution_m: float
    default_gap_days: int
    default_comparison_years: int
    verdict_ratio: float
    verdict_min_km2: float
    min_coverage: float
    study_track: StudyTrackConfig
    methods: tuple[str, ...]
    selected_method: str

    @property
    def res_m(self) -> float:
        return self.resolution_m

    @property
    def sel(self) -> str:
        return self.selected_method

    @property
    def gap(self) -> int:
        return self.default_gap_days

    @property
    def years(self) -> int:
        return self.default_comparison_years


def load_check_config(path: str | pathlib.Path | None = None) -> CheckConfig:
    """Load and validate flood check configuration from a YAML file.

    Parameters
    ----------
    path : str | pathlib.Path | None
        Path to YAML file. If None, defaults to configs/check.yaml.

    Returns
    -------
    CheckConfig
        Validated, frozen dataclass of check settings.
    """
    cfg_path = pathlib.Path(path) if path is not None else DEFAULT_CHECK_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    with open(cfg_path, encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing YAML in {cfg_path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Config in {cfg_path} must be a mapping, got {type(raw).__name__}")

    missing = EXPECTED_CHECK_KEYS - raw.keys()
    extra = raw.keys() - EXPECTED_CHECK_KEYS
    if missing and extra:
        raise ConfigError(
            f"Missing required key(s) in {cfg_path}: {', '.join(sorted(missing))}. "
            f"Unexpected or misspelled key(s): {', '.join(sorted(extra))}"
        )
    if missing:
        raise ConfigError(f"Missing required key(s) in {cfg_path}: {', '.join(sorted(missing))}")
    if extra:
        raise ConfigError(f"Unexpected or misspelled key(s) in {cfg_path}: {', '.join(sorted(extra))}")

    track_raw = raw["study_track"]
    if not isinstance(track_raw, dict):
        raise ConfigError(f"study_track in {cfg_path} must be a mapping with 'rel_orbit' and 'orbit_state'")

    missing_track = EXPECTED_STUDY_TRACK_KEYS - track_raw.keys()
    extra_track = track_raw.keys() - EXPECTED_STUDY_TRACK_KEYS
    if missing_track and extra_track:
        raise ConfigError(
            f"Missing required key(s) in study_track in {cfg_path}: {', '.join(sorted(missing_track))}. "
            f"Unexpected or misspelled key(s): {', '.join(sorted(extra_track))}"
        )
    if missing_track:
        raise ConfigError(f"Missing required key(s) in study_track in {cfg_path}: {', '.join(sorted(missing_track))}")
    if extra_track:
        raise ConfigError(f"Unexpected or misspelled key(s) in study_track in {cfg_path}: {', '.join(sorted(extra_track))}")

    orbit_state = str(track_raw["orbit_state"]).strip()
    if orbit_state not in ("ascending", "descending"):
        raise ConfigError(f"study_track.orbit_state in {cfg_path} must be 'ascending' or 'descending', got '{orbit_state}'")

    methods_raw = raw["methods"]
    if not isinstance(methods_raw, (list, tuple)) or not methods_raw:
        raise ConfigError(f"methods in {cfg_path} must be a non-empty sequence of method names")
    methods = tuple(str(m) for m in methods_raw)

    sel = str(raw["selected_method"])
    if sel not in methods:
        raise ConfigError(f"selected_method '{sel}' in {cfg_path} is not in methods: {methods}")

    return CheckConfig(
        resolution_m=float(raw["resolution_m"]),
        default_gap_days=int(raw["default_gap_days"]),
        default_comparison_years=int(raw["default_comparison_years"]),
        verdict_ratio=float(raw["verdict_ratio"]),
        verdict_min_km2=float(raw["verdict_min_km2"]),
        min_coverage=float(raw["min_coverage"]),
        study_track=StudyTrackConfig(
            rel_orbit=int(track_raw["rel_orbit"]),
            orbit_state=orbit_state,
        ),
        methods=methods,
        selected_method=sel,
    )
