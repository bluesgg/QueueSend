"""Tests for diff calculation algorithm.

Verifies that the diff function:
- Returns values in the range [0, 1]
- Correctly converts to grayscale using ITU-R BT.601 weights
- Handles identical and completely different frames correctly

See Executable Spec Section 7.1 for requirements.
"""

import numpy as np
import pytest

from app.core.diff import calculate_diff
from app.core.capture import to_grayscale
from app.core.model import ROI, Rect, ROIShape


class TestDiffCalculation:
    """Test suite for calculate_diff function."""

    def test_identical_frames_return_zero_diff(self) -> None:
        """Identical frames should produce diff = 0."""
        frame = np.full((100, 100), 128, dtype=np.uint8)
        diff = calculate_diff(frame, frame)
        assert diff == 0.0

    def test_maximum_difference_returns_one(self) -> None:
        """Black vs white frames should produce diff = 1.0."""
        frame_black = np.zeros((100, 100), dtype=np.uint8)
        frame_white = np.full((100, 100), 255, dtype=np.uint8)
        diff = calculate_diff(frame_white, frame_black)
        assert diff == pytest.approx(1.0, abs=0.001)

    def test_diff_in_valid_range(self) -> None:
        """Diff should always be in [0, 1]."""
        # Test with random frames
        np.random.seed(42)
        for _ in range(10):
            frame_t0 = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
            frame_t = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
            diff = calculate_diff(frame_t, frame_t0)
            assert 0.0 <= diff <= 1.0, f"Diff {diff} out of range [0, 1]"

    def test_partial_difference(self) -> None:
        """Partial difference should produce value between 0 and 1."""
        frame_t0 = np.full((100, 100), 100, dtype=np.uint8)
        frame_t = np.full((100, 100), 150, dtype=np.uint8)
        diff = calculate_diff(frame_t, frame_t0)
        # Expected: 50 / 255 ≈ 0.196
        expected = 50.0 / 255.0
        assert diff == pytest.approx(expected, abs=0.001)

    def test_shape_mismatch_raises_error(self) -> None:
        """Frames with different shapes should raise ValueError."""
        frame_t0 = np.zeros((100, 100), dtype=np.uint8)
        frame_t = np.zeros((50, 50), dtype=np.uint8)
        with pytest.raises(ValueError, match="Frame shapes must match"):
            calculate_diff(frame_t, frame_t0)

    def test_handles_color_input_by_converting_to_gray(self) -> None:
        """Color frames (3D arrays) should be converted to grayscale."""
        # Create BGRA frames (like mss output)
        frame_t0 = np.zeros((100, 100, 4), dtype=np.uint8)
        frame_t = np.full((100, 100, 4), 255, dtype=np.uint8)
        # Should not raise and should return valid diff
        diff = calculate_diff(frame_t, frame_t0)
        assert 0.0 <= diff <= 1.0

    def test_symmetric_difference(self) -> None:
        """diff(a, b) should equal diff(b, a)."""
        np.random.seed(123)
        frame_a = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
        frame_b = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
        diff_ab = calculate_diff(frame_a, frame_b)
        diff_ba = calculate_diff(frame_b, frame_a)
        assert diff_ab == pytest.approx(diff_ba, abs=0.0001)


class TestGrayscaleConversion:
    """Test suite for grayscale conversion."""

    def test_grayscale_weights_bt601(self) -> None:
        """Verify ITU-R BT.601 grayscale weights: Y = 0.299*R + 0.587*G + 0.114*B."""
        # Create a single pixel BGRA image
        # B=100, G=150, R=200 -> Y = 0.299*200 + 0.587*150 + 0.114*100 = 159.25
        bgra = np.array([[[100, 150, 200, 255]]], dtype=np.uint8)
        gray = to_grayscale(bgra)
        expected = 0.299 * 200 + 0.587 * 150 + 0.114 * 100
        assert gray[0, 0] == pytest.approx(expected, abs=1.0)

    def test_grayscale_pure_red(self) -> None:
        """Pure red (BGR: 0, 0, 255) should produce Y = 0.299 * 255 ≈ 76."""
        bgra = np.array([[[0, 0, 255, 255]]], dtype=np.uint8)
        gray = to_grayscale(bgra)
        expected = 0.299 * 255
        assert gray[0, 0] == pytest.approx(expected, abs=1.0)

    def test_grayscale_pure_green(self) -> None:
        """Pure green (BGR: 0, 255, 0) should produce Y = 0.587 * 255 ≈ 150."""
        bgra = np.array([[[0, 255, 0, 255]]], dtype=np.uint8)
        gray = to_grayscale(bgra)
        expected = 0.587 * 255
        assert gray[0, 0] == pytest.approx(expected, abs=1.0)

    def test_grayscale_pure_blue(self) -> None:
        """Pure blue (BGR: 255, 0, 0) should produce Y = 0.114 * 255 ≈ 29."""
        bgra = np.array([[[255, 0, 0, 255]]], dtype=np.uint8)
        gray = to_grayscale(bgra)
        expected = 0.114 * 255
        assert gray[0, 0] == pytest.approx(expected, abs=1.0)

    def test_grayscale_already_gray_passthrough(self) -> None:
        """Already grayscale (2D) array should pass through unchanged."""
        gray_input = np.array([[100, 150], [200, 50]], dtype=np.uint8)
        gray_output = to_grayscale(gray_input)
        np.testing.assert_array_equal(gray_output, gray_input)

    def test_grayscale_output_is_uint8(self) -> None:
        """Grayscale output should be uint8."""
        bgra = np.random.randint(0, 256, (10, 10, 4), dtype=np.uint8)
        gray = to_grayscale(bgra)
        assert gray.dtype == np.uint8


class TestDiffWithROI:
    """Test diff calculation with ROI parameter."""

    def test_diff_with_rect_roi_same_as_no_roi(self) -> None:
        """Rectangle ROI should not apply mask (same result as no ROI)."""
        frame_t0 = np.full((100, 100), 100, dtype=np.uint8)
        frame_t = np.full((100, 100), 150, dtype=np.uint8)

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=100, h=100),
        )

        diff_with_roi = calculate_diff(frame_t, frame_t0, roi)
        diff_no_roi = calculate_diff(frame_t, frame_t0, None)

        assert diff_with_roi == pytest.approx(diff_no_roi, abs=0.0001)

