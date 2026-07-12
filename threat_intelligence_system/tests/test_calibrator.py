"""
Tests for the confidence calibrator (src/scoring/calibrator.py).

Covers:
- All four calibration methods (platt, isotonic, temperature, identity).
- fit/calibrate/calibrate_batch workflow.
- Output range is always [0, 1].
- Save/load round-trip.
- Invalid method raises ValueError.
- calibration_info() returns correct keys.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.scoring.calibrator import ConfidenceCalibrator, CALIBRATION_METHODS


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    """Return y_true and y_prob for calibration tests."""
    rng = np.random.default_rng(42)
    y_true = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1, 0])
    # Slightly miscalibrated probs
    y_prob = np.array([0.8, 0.3, 0.9, 0.7, 0.4, 0.2, 0.85, 0.35, 0.75, 0.25])
    return y_true, y_prob


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestCalibrator:
    def test_invalid_method_raises(self):
        with pytest.raises(ValueError, match="Unknown calibration method"):
            ConfidenceCalibrator(method="magic")

    def test_valid_methods(self):
        for method in CALIBRATION_METHODS:
            cal = ConfidenceCalibrator(method=method)
            assert cal.method == method

    def test_initially_not_fitted(self):
        cal = ConfidenceCalibrator()
        assert not cal.is_fitted

    def test_identity_no_fit_needed(self):
        cal = ConfidenceCalibrator(method="identity")
        # calibrate without fitting should return original value
        assert cal.calibrate(0.8) == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Fit + calibrate (all methods)
# ---------------------------------------------------------------------------

class TestFitCalibrate:
    @pytest.mark.parametrize("method", CALIBRATION_METHODS)
    def test_fit_marks_fitted(self, method, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method=method)
        cal.fit(y_true, y_prob)
        assert cal.is_fitted

    @pytest.mark.parametrize("method", CALIBRATION_METHODS)
    def test_calibrate_in_range(self, method, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method=method)
        cal.fit(y_true, y_prob)
        for raw in [0.0, 0.1, 0.5, 0.9, 1.0]:
            cal_val = cal.calibrate(raw)
            assert 0.0 <= cal_val <= 1.0, f"Out of range for method={method}, raw={raw}"

    @pytest.mark.parametrize("method", CALIBRATION_METHODS)
    def test_calibrate_batch_length(self, method, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method=method)
        cal.fit(y_true, y_prob)
        batch = [0.1, 0.5, 0.9]
        out = cal.calibrate_batch(batch)
        assert len(out) == 3

    def test_fit_returns_self(self, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method="platt")
        result = cal.fit(y_true, y_prob)
        assert result is cal

    def test_empty_data_raises(self):
        cal = ConfidenceCalibrator(method="platt")
        with pytest.raises(ValueError, match="non-empty"):
            cal.fit(np.array([]), np.array([]))

    def test_length_mismatch_raises(self):
        cal = ConfidenceCalibrator(method="platt")
        with pytest.raises(ValueError, match="same length"):
            cal.fit(np.array([1, 0]), np.array([0.8]))

    def test_clamps_confidence_above_1(self, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method="identity")
        cal.fit(y_true, y_prob)
        assert cal.calibrate(1.5) == pytest.approx(1.0)

    def test_clamps_confidence_below_0(self, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method="identity")
        cal.fit(y_true, y_prob)
        assert cal.calibrate(-0.5) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    @pytest.mark.parametrize("method", CALIBRATION_METHODS)
    def test_save_load_roundtrip(self, method, sample_data, tmp_path):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method=method)
        cal.fit(y_true, y_prob)

        path = tmp_path / f"calibrator_{method}.json"
        cal.save(path)
        assert path.exists()

        loaded = ConfidenceCalibrator.load(path)
        assert loaded.method == method
        assert loaded.is_fitted

        # Calibrated values should match original
        for raw in [0.2, 0.5, 0.8]:
            orig_val = cal.calibrate(raw)
            load_val = loaded.calibrate(raw)
            assert orig_val == pytest.approx(load_val, abs=1e-5)


# ---------------------------------------------------------------------------
# calibration_info
# ---------------------------------------------------------------------------

class TestCalibrationInfo:
    def test_platt_info_keys(self, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method="platt")
        cal.fit(y_true, y_prob)
        info = cal.calibration_info()
        assert "platt_A" in info
        assert "platt_B" in info

    def test_temperature_info_keys(self, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method="temperature")
        cal.fit(y_true, y_prob)
        info = cal.calibration_info()
        assert "temperature" in info

    def test_isotonic_info_keys(self, sample_data):
        y_true, y_prob = sample_data
        cal = ConfidenceCalibrator(method="isotonic")
        cal.fit(y_true, y_prob)
        info = cal.calibration_info()
        assert "n_calibration_points" in info
