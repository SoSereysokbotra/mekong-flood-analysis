"""The operational threshold map: 1 water, 0 dry, -1 no data."""
import numpy as np
import pytest

infer = pytest.importorskip("mfi.infer")        # imports torch at module level


def test_threshold_map_values_and_nodata():
    vh = np.array([[-25.0, -10.0], [np.nan, -19.0]])
    out = infer.predict_threshold({"vh": vh}, "vh", t=-19.65)
    assert out.dtype == np.int8
    assert out.tolist() == [[1, 0], [-1, 0]]


def test_value_exactly_at_threshold_is_dry():
    assert infer.predict_threshold({"vh": np.array([-19.65])}, "vh", t=-19.65).tolist() == [0]
