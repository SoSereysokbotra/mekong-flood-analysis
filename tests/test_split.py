"""Project rule: split by event; every Cambodia ("Mekong") chip is held out for test."""
import pytest

from mfi import catalog


def test_split_rule_on_a_fake_chip_list(monkeypatch):
    chips = ["Mekong_1", "Mekong_2", "Spain_1", "Nigeria_1", "Bolivia_1", "India_1", "India_2"]
    monkeypatch.setattr(catalog, "s1f11_hand_chips", lambda: chips)
    s = catalog.s1f11_split()
    assert s["test"] == ["Mekong_1", "Mekong_2"]
    assert sorted(s["valid"]) == ["Nigeria_1", "Spain_1"]
    assert sorted(s["train"]) == ["Bolivia_1", "India_1", "India_2"]


def test_held_out_and_valid_events_are_the_documented_ones():
    assert catalog.HELD_OUT_EVENTS == ("Mekong",)
    assert set(catalog.VALID_EVENTS) == {"Spain", "Nigeria"}
    assert not set(catalog.HELD_OUT_EVENTS) & set(catalog.VALID_EVENTS)


def real_split():
    try:
        s = catalog.s1f11_split()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Sen1Floods11 not on disk ({e})")
    if not any(s.values()):
        pytest.skip("Sen1Floods11 not on disk")
    return s


def test_real_split_has_no_overlap_and_no_mekong_outside_test():
    s = real_split()
    sets = {k: set(v) for k, v in s.items()}
    assert not sets["train"] & sets["valid"] and not sets["train"] & sets["test"] and not sets["valid"] & sets["test"]
    assert all(catalog.s1f11_event(c) == "Mekong" for c in s["test"])
    assert not any(catalog.s1f11_event(c) == "Mekong" for c in s["train"] + s["valid"])


def test_real_split_sizes_match_level0():
    s = real_split()                       # skips first where the data (and torch) are missing
    from mfi import data

    # v1.0 (sigma0): 368 train chips (docs/level0_inventory.md). v1.1 (RTC, the default) drops Paraguay's
    # 67 chips, which have no RTC radar (catalog.NO_RTC_EVENTS). Valid and test are the same in both.
    train = 301 if data.PIPELINE == "rtc" else 368
    assert (len(s["train"]), len(s["valid"]), len(s["test"])) == (train, 48, 30)


def test_weak_labels_never_include_cambodia():
    try:
        weak = catalog.s1f11_weak_chips()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"weak labels not on disk ({e})")
    assert not any(catalog.s1f11_event(c) == "Mekong" for c in weak)
