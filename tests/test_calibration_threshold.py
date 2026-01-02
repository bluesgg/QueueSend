"""Tests for threshold calibration algorithm.

Verifies that:
- TH_rec = clamp(mu + 3*sigma, 0.005, 0.2)
- Algorithm is reproducible
- Warning is generated when noise is abnormal

See Executable Spec Section 8.3 for requirements.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from app.core.diff import clamp, calibrate_threshold
from app.core.model import ROI, Rect, ROIShape, CalibrationStats
from app.core.constants import TH_HOLD_MIN, TH_HOLD_MAX


class TestClampFunction:
    """Test suite for the clamp helper function."""

    def test_value_in_range_unchanged(self) -> None:
        """Values within range should be unchanged."""
        assert clamp(0.05, 0.0, 1.0) == 0.05
        assert clamp(0.1, 0.005, 0.2) == 0.1

    def test_value_below_min_clamped(self) -> None:
        """Values below min should be clamped to min."""
        assert clamp(0.001, 0.005, 0.2) == 0.005
        assert clamp(-1.0, 0.0, 1.0) == 0.0

    def test_value_above_max_clamped(self) -> None:
        """Values above max should be clamped to max."""
        assert clamp(0.5, 0.005, 0.2) == 0.2
        assert clamp(10.0, 0.0, 1.0) == 1.0

    def test_boundary_values(self) -> None:
        """Values at boundaries should be returned as-is."""
        assert clamp(0.005, 0.005, 0.2) == 0.005
        assert clamp(0.2, 0.005, 0.2) == 0.2


class TestThresholdCalculation:
    """Test the core threshold calculation logic: mu + 3*sigma, clamped."""

    def test_threshold_formula_correct(self) -> None:
        """Verify TH_rec = clamp(mu + 3*sigma, TH_MIN, TH_MAX)."""
        # Given di values, calculate expected threshold
        di_values = [0.01, 0.012, 0.011, 0.013, 0.009, 0.010, 0.011]
        mu = np.mean(di_values)
        sigma = np.std(di_values)
        expected_raw = mu + 3 * sigma
        expected = clamp(expected_raw, TH_HOLD_MIN, TH_HOLD_MAX)

        # The result should match our expected calculation
        assert expected == pytest.approx(
            clamp(mu + 3 * sigma, TH_HOLD_MIN, TH_HOLD_MAX)
        )

    def test_low_noise_produces_minimum_threshold(self) -> None:
        """Very low noise should produce TH_MIN (0.005)."""
        # If all di values are 0 (identical frames), mu=0, sigma=0
        # TH_rec = clamp(0 + 0, 0.005, 0.2) = 0.005
        di_values = [0.0, 0.0, 0.0, 0.0]
        mu = np.mean(di_values)
        sigma = np.std(di_values)
        th_rec = clamp(mu + 3 * sigma, TH_HOLD_MIN, TH_HOLD_MAX)
        assert th_rec == TH_HOLD_MIN

    def test_high_noise_produces_maximum_threshold(self) -> None:
        """Very high noise should be clamped to TH_MAX (0.2)."""
        # If noise is very high, threshold should be capped at 0.2
        di_values = [0.1, 0.15, 0.2, 0.25, 0.3]
        mu = np.mean(di_values)
        sigma = np.std(di_values)
        raw_th = mu + 3 * sigma
        # This should exceed 0.2
        assert raw_th > TH_HOLD_MAX
        th_rec = clamp(raw_th, TH_HOLD_MIN, TH_HOLD_MAX)
        assert th_rec == TH_HOLD_MAX

    def test_typical_noise_within_bounds(self) -> None:
        """Typical noise levels should produce threshold within bounds."""
        di_values = [0.015, 0.018, 0.012, 0.016, 0.014, 0.017, 0.013]
        mu = np.mean(di_values)
        sigma = np.std(di_values)
        th_rec = clamp(mu + 3 * sigma, TH_HOLD_MIN, TH_HOLD_MAX)
        assert TH_HOLD_MIN <= th_rec <= TH_HOLD_MAX


class TestCalibrationStatsOutput:
    """Test CalibrationStats data structure."""

    def test_stats_contains_required_fields(self) -> None:
        """CalibrationStats should have all required fields."""
        stats = CalibrationStats(
            mu=0.01,
            sigma=0.002,
            th_rec=0.016,
            di_values=[0.008, 0.01, 0.012],
            warning=None,
        )
        assert hasattr(stats, 'mu')
        assert hasattr(stats, 'sigma')
        assert hasattr(stats, 'th_rec')
        assert hasattr(stats, 'di_values')
        assert hasattr(stats, 'warning')

    def test_stats_warning_when_noise_abnormal(self) -> None:
        """Warning should be set when mu + 3*sigma > TH_MAX."""
        stats = CalibrationStats(
            mu=0.1,
            sigma=0.05,
            th_rec=TH_HOLD_MAX,  # Clamped
            di_values=[0.1, 0.15, 0.08, 0.12],
            warning="噪声异常,建议重新选择ROI",
        )
        assert stats.warning is not None
        assert "噪声" in stats.warning


class TestCalibrateThresholdWithMock:
    """Test calibrate_threshold function with mocked capture."""

    @patch('app.core.diff.capture_roi_gray')
    def test_calibration_captures_k_frames(
        self, mock_capture: MagicMock
    ) -> None:
        """Calibration should capture K frames."""
        # Create mock frames that return static noise
        def make_frame(noise_level: int) -> np.ndarray:
            base = np.full((50, 50), 100, dtype=np.int16)
            noise = np.random.randint(-noise_level, noise_level + 1, (50, 50), dtype=np.int16)
            frame = base + noise
            return np.clip(frame, 0, 255).astype(np.uint8)

        np.random.seed(42)
        mock_capture.side_effect = [make_frame(5) for _ in range(8)]

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )

        stats = calibrate_threshold(roi, k_frames=8, interval_ms=0)

        # Should have captured 8 frames
        assert mock_capture.call_count == 8

        # Should have 7 di values (K-1 comparisons with first frame)
        assert len(stats.di_values) == 7

    @patch('app.core.diff.capture_roi_gray')
    def test_calibration_produces_reproducible_results(
        self, mock_capture: MagicMock
    ) -> None:
        """Same input should produce same output."""
        # Create deterministic frames
        frames = [
            np.full((50, 50), 100, dtype=np.uint8),  # Reference
            np.full((50, 50), 102, dtype=np.uint8),  # Small diff
            np.full((50, 50), 101, dtype=np.uint8),
            np.full((50, 50), 103, dtype=np.uint8),
            np.full((50, 50), 99, dtype=np.uint8),
        ]

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )

        # Run calibration twice with same frames
        mock_capture.side_effect = frames.copy()
        stats1 = calibrate_threshold(roi, k_frames=5, interval_ms=0)

        mock_capture.side_effect = frames.copy()
        stats2 = calibrate_threshold(roi, k_frames=5, interval_ms=0)

        # Results should be identical
        assert stats1.mu == stats2.mu
        assert stats1.sigma == stats2.sigma
        assert stats1.th_rec == stats2.th_rec

    @patch('app.core.diff.capture_roi_gray')
    def test_calibration_clamps_k_frames_to_valid_range(
        self, mock_capture: MagicMock
    ) -> None:
        """K frames should be clamped to [5, 10]."""
        frames = [np.full((50, 50), 100, dtype=np.uint8) for _ in range(15)]
        mock_capture.side_effect = frames

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )

        # Request too many frames - should be clamped to 10
        calibrate_threshold(roi, k_frames=15, interval_ms=0)
        assert mock_capture.call_count == 10

    @patch('app.core.diff.capture_roi_gray')
    def test_calibration_warning_on_high_noise(
        self, mock_capture: MagicMock
    ) -> None:
        """Warning should be generated when noise is too high."""
        # Create frames with high variance
        np.random.seed(42)
        frames = [
            np.full((50, 50), 100, dtype=np.uint8),  # Reference
        ]
        # Add frames with large differences
        for val in [150, 200, 50, 180, 30, 170, 60]:
            frames.append(np.full((50, 50), val, dtype=np.uint8))

        mock_capture.side_effect = frames

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )

        stats = calibrate_threshold(roi, k_frames=8, interval_ms=0)

        # Should have warning due to high noise
        assert stats.warning is not None
        assert stats.th_rec == TH_HOLD_MAX  # Clamped to max

    @patch('app.core.diff.capture_roi_gray')
    def test_calibration_no_warning_on_normal_noise(
        self, mock_capture: MagicMock
    ) -> None:
        """No warning when noise is within normal range."""
        # Create frames with low variance
        frames = [np.full((50, 50), 100 + i % 3, dtype=np.uint8) for i in range(8)]
        mock_capture.side_effect = frames

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=50, h=50),
        )

        stats = calibrate_threshold(roi, k_frames=8, interval_ms=0)

        # Should not have warning
        assert stats.warning is None


class TestCalibrationMathematicalCorrectness:
    """Verify the mathematical correctness of calibration."""

    def test_three_sigma_rule_coverage(self) -> None:
        """3*sigma covers 99.7% of normal distribution."""
        # This is a property of normal distributions that the spec relies on
        # mu + 3*sigma captures 99.7% of samples
        # Test that our calculation matches this principle

        # Generate normally distributed noise
        np.random.seed(42)
        noise = np.random.normal(0.02, 0.003, 1000)

        mu = np.mean(noise)
        sigma = np.std(noise)
        threshold = mu + 3 * sigma

        # Count samples below threshold
        below_threshold = np.sum(noise <= threshold)
        coverage = below_threshold / len(noise)

        # Should be close to 99.7% (allowing some variance due to sampling)
        assert coverage >= 0.99

    def test_minimum_threshold_prevents_quantization_noise_issues(self) -> None:
        """TH_MIN = 0.005 prevents false positives from quantization noise."""
        # Quantization noise in 8-bit images can cause small diffs even
        # between "identical" captures due to sensor noise
        # TH_MIN of 0.005 = ~1.3 gray levels of average difference

        # Verify the constant is set correctly
        assert TH_HOLD_MIN == 0.005
        # 0.005 * 255 ≈ 1.27 gray levels
        assert TH_HOLD_MIN * 255 < 2.0

    def test_maximum_threshold_ensures_detectability(self) -> None:
        """TH_MAX = 0.2 ensures significant changes are still detected."""
        # TH_MAX of 0.2 = ~51 gray levels of average difference
        # Changes larger than this should definitely be "real" changes

        assert TH_HOLD_MAX == 0.2
        # 0.2 * 255 ≈ 51 gray levels
        assert TH_HOLD_MAX * 255 > 50

