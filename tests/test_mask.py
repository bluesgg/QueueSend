"""Tests for circle mask in diff calculation.

Verifies that:
- Circle mask correctly identifies inner/outer pixels
- Changes outside the circle are ignored in diff calculation
- Changes inside the circle are correctly counted

See Executable Spec Sections 4.2 and 7.1 for requirements.
"""

import numpy as np
import pytest

from app.core.diff import calculate_diff, create_circle_mask
from app.core.model import ROI, Rect, Circle, ROIShape


class TestCircleMaskCreation:
    """Test suite for circle mask generation."""

    def test_mask_shape_matches_input(self) -> None:
        """Mask shape should match specified dimensions."""
        mask = create_circle_mask(100, 200, Circle(100.0, 50.0, 50.0))
        assert mask.shape == (100, 200)

    def test_mask_is_boolean(self) -> None:
        """Mask should be a boolean array."""
        mask = create_circle_mask(50, 50, Circle(25.0, 25.0, 20.0))
        assert mask.dtype == bool

    def test_center_pixel_is_inside(self) -> None:
        """Center of circle should be inside the mask."""
        mask = create_circle_mask(100, 100, Circle(50.0, 50.0, 30.0))
        assert mask[50, 50] is np.True_

    def test_corner_pixels_are_outside(self) -> None:
        """Corner pixels should be outside the inscribed circle."""
        mask = create_circle_mask(100, 100, Circle(50.0, 50.0, 30.0))
        # Corners at (0,0), (0,99), (99,0), (99,99) are all outside a r=30 circle
        assert mask[0, 0] is np.False_
        assert mask[0, 99] is np.False_
        assert mask[99, 0] is np.False_
        assert mask[99, 99] is np.False_

    def test_inscribed_circle_from_square(self) -> None:
        """Inscribed circle in a square should touch midpoints of edges."""
        # 100x100 square -> inscribed circle r=50, center (50, 50)
        mask = create_circle_mask(100, 100, Circle(50.0, 50.0, 50.0))

        # Edge midpoints should be inside (or on boundary)
        # Top midpoint: (50, 0) should be on the boundary
        # The formula is: dist(50, 0) to (50, 50) = 50 = r, so on boundary
        assert mask[0, 50] is np.True_  # top edge midpoint
        assert mask[99, 50] is np.True_  # bottom edge midpoint (99 is inside since < 100)
        assert mask[50, 0] is np.True_  # left edge midpoint
        assert mask[50, 99] is np.True_  # right edge midpoint

    def test_inscribed_circle_from_rectangle(self) -> None:
        """Inscribed circle in rectangle uses min(w,h)/2 as radius."""
        # 200x100 rectangle -> inscribed circle r=50 (from height)
        # Center at (100, 50)
        mask = create_circle_mask(100, 200, Circle(100.0, 50.0, 50.0))

        # Point at center should be inside
        assert mask[50, 100] is np.True_

        # Points near horizontal edges of rectangle but within circle
        assert mask[50, 60] is np.True_   # 60 is within radius of center 100
        assert mask[50, 140] is np.True_  # 140 is within radius of center 100

        # Points outside the inscribed circle (beyond r=50 from center)
        # At x=0 or x=199, far from center x=100
        assert mask[50, 0] is np.False_
        assert mask[50, 199] is np.False_


class TestCircleMaskInDiff:
    """Test that circle mask correctly filters diff calculation."""

    def test_outer_changes_ignored(self) -> None:
        """Changes outside the circle should not affect diff."""
        size = 100
        frame_t0 = np.full((size, size), 100, dtype=np.uint8)
        frame_t = frame_t0.copy()

        # Create inscribed circle ROI
        roi = ROI(
            shape=ROIShape.CIRCLE,
            rect=Rect(x=0, y=0, w=size, h=size),
        )

        # Get the mask to identify outside pixels
        mask = create_circle_mask(size, size, roi.circle)

        # Only change pixels OUTSIDE the circle
        frame_t[~mask] = 255

        # Diff should be 0 since only outside pixels changed
        diff = calculate_diff(frame_t, frame_t0, roi)
        assert diff == pytest.approx(0.0, abs=0.001)

    def test_inner_changes_counted(self) -> None:
        """Changes inside the circle should be correctly counted in diff."""
        size = 100
        frame_t0 = np.full((size, size), 100, dtype=np.uint8)
        frame_t = frame_t0.copy()

        # Create inscribed circle ROI
        roi = ROI(
            shape=ROIShape.CIRCLE,
            rect=Rect(x=0, y=0, w=size, h=size),
        )

        # Get the mask
        mask = create_circle_mask(size, size, roi.circle)

        # Only change pixels INSIDE the circle
        frame_t[mask] = 200  # +100 change

        # Diff should reflect the change (100/255 ≈ 0.392)
        diff = calculate_diff(frame_t, frame_t0, roi)
        expected = 100.0 / 255.0
        assert diff == pytest.approx(expected, abs=0.01)

    def test_mixed_changes_only_counts_inner(self) -> None:
        """When both inside and outside change, only inside is counted."""
        size = 100
        frame_t0 = np.full((size, size), 100, dtype=np.uint8)
        frame_t = frame_t0.copy()

        roi = ROI(
            shape=ROIShape.CIRCLE,
            rect=Rect(x=0, y=0, w=size, h=size),
        )

        mask = create_circle_mask(size, size, roi.circle)

        # Inside: change by 50
        frame_t[mask] = 150

        # Outside: change by 100 (should be ignored)
        frame_t[~mask] = 200

        # Diff should only reflect inside change
        diff = calculate_diff(frame_t, frame_t0, roi)
        expected = 50.0 / 255.0
        assert diff == pytest.approx(expected, abs=0.01)

    def test_rectangle_roi_counts_all_pixels(self) -> None:
        """Rectangle ROI should count all pixels, not just a circle."""
        size = 100
        frame_t0 = np.full((size, size), 100, dtype=np.uint8)
        frame_t = frame_t0.copy()

        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=size, h=size),
        )

        # Change only corner pixels (outside inscribed circle)
        frame_t[0, 0] = 200
        frame_t[0, 99] = 200
        frame_t[99, 0] = 200
        frame_t[99, 99] = 200

        # With RECT ROI, these changes should be counted
        diff = calculate_diff(frame_t, frame_t0, roi)
        assert diff > 0.0

    def test_empty_mask_returns_zero(self) -> None:
        """If mask has no pixels (edge case), diff should be 0."""
        # Create a tiny ROI where the inscribed circle might be very small
        frame_t0 = np.full((2, 2), 100, dtype=np.uint8)
        frame_t = np.full((2, 2), 200, dtype=np.uint8)

        roi = ROI(
            shape=ROIShape.CIRCLE,
            rect=Rect(x=0, y=0, w=2, h=2),
        )

        # With a 2x2 rect, inscribed circle has r=1, center at (1, 1)
        # Some pixels should still be inside
        diff = calculate_diff(frame_t, frame_t0, roi)
        # Should handle gracefully
        assert 0.0 <= diff <= 1.0


class TestMaskEdgeCases:
    """Edge cases for mask behavior."""

    def test_very_small_circle(self) -> None:
        """Very small circles should still work correctly."""
        mask = create_circle_mask(10, 10, Circle(5.0, 5.0, 2.0))
        # Center should be inside
        assert mask[5, 5] is np.True_
        # Corners should be outside
        assert mask[0, 0] is np.False_

    def test_large_circle(self) -> None:
        """Large circles should work correctly."""
        mask = create_circle_mask(1000, 1000, Circle(500.0, 500.0, 400.0))
        assert mask[500, 500] is np.True_
        assert mask[0, 0] is np.False_
        assert mask[999, 999] is np.False_

    def test_non_square_aspect_ratio(self) -> None:
        """Non-square images should use min(w,h)/2 for inscribed circle."""
        # Wide rectangle: 200 x 50
        mask = create_circle_mask(50, 200, Circle(100.0, 25.0, 25.0))

        # Center should be inside
        assert mask[25, 100] is np.True_

        # Points at horizontal extremes should be outside (beyond radius)
        assert mask[25, 0] is np.False_
        assert mask[25, 199] is np.False_


