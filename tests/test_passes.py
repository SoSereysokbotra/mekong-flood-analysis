"""Radar pass choice for Tier B 2026: nearest pass, ties to the earlier one (protocol v1.3 s9.2)."""
import tierb2026


def test_nearest_pass_is_chosen():
    assert tierb2026.nearest_pass("2026-10-04", ["2026-09-26", "2026-10-02", "2026-10-14"]) == ("2026-10-02", 2)


def test_tie_goes_to_the_earlier_pass():
    assert tierb2026.nearest_pass("2026-10-04", ["2026-10-02", "2026-10-06"]) == ("2026-10-02", 2)


def test_no_passes():
    assert tierb2026.nearest_pass("2026-10-04", []) is None
