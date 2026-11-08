"""Experiment log: the 'select on valid before test' guard (Mistake_avoidance.md rule 3)."""
import pytest

from mfi import experiments, metrics


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    """Point the experiment log at a temporary file so tests never touch results/."""
    monkeypatch.setattr(experiments, "RESULTS", tmp_path)
    monkeypatch.setattr(experiments, "LOG", tmp_path / "experiment_log.csv")
    monkeypatch.setattr(experiments, "git_commit", lambda: "test")
    return tmp_path / "experiment_log.csv"


def row(level, split):
    m = metrics.Confusion().metrics()
    experiments.log_row(level, "run", split, "m", {}, 1, m)


def test_selection_before_test_is_allowed(tmp_log):
    row("level3", "valid")
    experiments.record_selection("level3", "run", "cropland IoU on valid")
    rows = experiments.read_log()
    assert [r["split"] for r in rows] == ["valid", "selection"]


def test_selection_after_test_is_refused(tmp_log):
    row("level3", "valid")
    row("level3", "test")
    with pytest.raises(RuntimeError, match="selection must be recorded first"):
        experiments.record_selection("level3", "run", "anything")
    assert [r["split"] for r in experiments.read_log()] == ["valid", "test"]     # nothing written


def test_test_rows_of_another_level_do_not_block(tmp_log):
    row("level1", "test")
    experiments.record_selection("level3", "run", "x")
    assert experiments.read_log()[-1]["split"] == "selection"
