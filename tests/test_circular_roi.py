"""Tests for circular ROI inscribed circle calculation.

Verifies that:
- Circle is correctly derived from bounding rectangle
- cx = x + w/2
- cy = y + h/2  
- r = min(w, h) / 2

See Executable Spec Section 4.2 for requirements.
"""

import pytest

from app.core.model import Circle, Rect, ROI, ROIShape


class TestCircleFromRect:
    """Test Circle.from_rect() calculation."""

    def test_square_rect_produces_centered_circle(self) -> None:
        """Square rectangle should produce perfectly centered inscribed circle."""
        rect = Rect(x=0, y=0, w=100, h=100)
        circle = Circle.from_rect(rect)

        assert circle.cx == 50.0   # 0 + 100/2
        assert circle.cy == 50.0   # 0 + 100/2
        assert circle.r == 50.0    # min(100, 100)/2

    def test_wide_rect_uses_height_for_radius(self) -> None:
        """Wide rectangle should use height/2 as radius."""
        rect = Rect(x=0, y=0, w=200, h=100)
        circle = Circle.from_rect(rect)

        assert circle.cx == 100.0  # 0 + 200/2
        assert circle.cy == 50.0   # 0 + 100/2
        assert circle.r == 50.0    # min(200, 100)/2 = 100/2

    def test_tall_rect_uses_width_for_radius(self) -> None:
        """Tall rectangle should use width/2 as radius."""
        rect = Rect(x=0, y=0, w=100, h=200)
        circle = Circle.from_rect(rect)

        assert circle.cx == 50.0   # 0 + 100/2
        assert circle.cy == 100.0  # 0 + 200/2
        assert circle.r == 50.0    # min(100, 200)/2 = 100/2

    def test_offset_rect_shifts_center(self) -> None:
        """Rectangle with offset origin should shift circle center."""
        rect = Rect(x=100, y=200, w=50, h=50)
        circle = Circle.from_rect(rect)

        assert circle.cx == 125.0  # 100 + 50/2
        assert circle.cy == 225.0  # 200 + 50/2
        assert circle.r == 25.0    # min(50, 50)/2

    def test_negative_coordinates(self) -> None:
        """Negative coordinates (multi-monitor) should work correctly."""
        rect = Rect(x=-1920, y=0, w=100, h=100)
        circle = Circle.from_rect(rect)

        assert circle.cx == -1870.0  # -1920 + 100/2
        assert circle.cy == 50.0     # 0 + 100/2
        assert circle.r == 50.0

    def test_small_dimensions(self) -> None:
        """Small dimensions should work correctly."""
        rect = Rect(x=0, y=0, w=10, h=10)
        circle = Circle.from_rect(rect)

        assert circle.cx == 5.0
        assert circle.cy == 5.0
        assert circle.r == 5.0

    def test_large_dimensions(self) -> None:
        """Large dimensions should work correctly."""
        rect = Rect(x=0, y=0, w=4000, h=2000)
        circle = Circle.from_rect(rect)

        assert circle.cx == 2000.0  # 0 + 4000/2
        assert circle.cy == 1000.0  # 0 + 2000/2
        assert circle.r == 1000.0   # min(4000, 2000)/2

    def test_odd_dimensions(self) -> None:
        """Odd dimensions should produce float center coordinates."""
        rect = Rect(x=0, y=0, w=101, h=101)
        circle = Circle.from_rect(rect)

        assert circle.cx == 50.5   # 0 + 101/2
        assert circle.cy == 50.5   # 0 + 101/2
        assert circle.r == 50.5    # min(101, 101)/2


class TestROICircleAutoGeneration:
    """Test that ROI auto-generates circle when shape is CIRCLE."""

    def test_circle_roi_auto_generates_circle(self) -> None:
        """CIRCLE shape ROI should auto-generate circle from rect."""
        roi = ROI(
            shape=ROIShape.CIRCLE,
            rect=Rect(x=10, y=20, w=100, h=80),
        )

        assert roi.circle is not None
        assert roi.circle.cx == 60.0   # 10 + 100/2
        assert roi.circle.cy == 60.0   # 20 + 80/2
        assert roi.circle.r == 40.0    # min(100, 80)/2

    def test_rect_roi_has_no_circle(self) -> None:
        """RECT shape ROI should not have circle (or have None)."""
        roi = ROI(
            shape=ROIShape.RECT,
            rect=Rect(x=0, y=0, w=100, h=100),
        )

        # For RECT shape, circle should remain None
        assert roi.circle is None

    def test_circle_roi_uses_provided_circle(self) -> None:
        """If circle is explicitly provided, it should be used."""
        custom_circle = Circle(cx=50.0, cy=50.0, r=30.0)
        roi = ROI(
            shape=ROIShape.CIRCLE,
            rect=Rect(x=0, y=0, w=100, h=100),
            circle=custom_circle,
        )

        # Should use the provided circle, not auto-generate
        assert roi.circle.r == 30.0


class TestCircleContainsPoint:
    """Test Circle.contains_point() method."""

    def test_center_is_inside(self) -> None:
        """Center point should be inside the circle."""
        circle = Circle(cx=50.0, cy=50.0, r=30.0)
        assert circle.contains_point(50.0, 50.0) is True

    def test_point_on_boundary_is_inside(self) -> None:
        """Points on boundary should be inside (<=, not <)."""
        circle = Circle(cx=50.0, cy=50.0, r=30.0)
        # Point at distance exactly r from center
        assert circle.contains_point(80.0, 50.0) is True  # Right edge
        assert circle.contains_point(50.0, 80.0) is True  # Bottom edge
        assert circle.contains_point(20.0, 50.0) is True  # Left edge
        assert circle.contains_point(50.0, 20.0) is True  # Top edge

    def test_point_inside_is_inside(self) -> None:
        """Points inside circle should return True."""
        circle = Circle(cx=50.0, cy=50.0, r=30.0)
        assert circle.contains_point(60.0, 50.0) is True
        assert circle.contains_point(50.0, 60.0) is True
        assert circle.contains_point(40.0, 40.0) is True

    def test_point_outside_is_outside(self) -> None:
        """Points outside circle should return False."""
        circle = Circle(cx=50.0, cy=50.0, r=30.0)
        assert circle.contains_point(0.0, 0.0) is False
        assert circle.contains_point(100.0, 100.0) is False
        assert circle.contains_point(81.0, 50.0) is False  # Just outside right edge


class TestInscribedCircleFormula:
    """Verify the inscribed circle formula from the spec."""

    def test_formula_cx_equals_x_plus_w_over_2(self) -> None:
        """Verify cx = x + w/2."""
        test_cases = [
            (Rect(x=0, y=0, w=100, h=100), 50.0),
            (Rect(x=50, y=0, w=100, h=100), 100.0),
            (Rect(x=-100, y=0, w=200, h=100), 0.0),
            (Rect(x=10, y=0, w=30, h=50), 25.0),
        ]

        for rect, expected_cx in test_cases:
            circle = Circle.from_rect(rect)
            assert circle.cx == expected_cx, \
                f"For rect({rect.x}, {rect.y}, {rect.w}, {rect.h}): expected cx={expected_cx}, got {circle.cx}"

    def test_formula_cy_equals_y_plus_h_over_2(self) -> None:
        """Verify cy = y + h/2."""
        test_cases = [
            (Rect(x=0, y=0, w=100, h=100), 50.0),
            (Rect(x=0, y=50, w=100, h=100), 100.0),
            (Rect(x=0, y=-100, w=100, h=200), 0.0),
            (Rect(x=0, y=10, w=50, h=30), 25.0),
        ]

        for rect, expected_cy in test_cases:
            circle = Circle.from_rect(rect)
            assert circle.cy == expected_cy, \
                f"For rect({rect.x}, {rect.y}, {rect.w}, {rect.h}): expected cy={expected_cy}, got {circle.cy}"

    def test_formula_r_equals_min_w_h_over_2(self) -> None:
        """Verify r = min(w, h) / 2."""
        test_cases = [
            (Rect(x=0, y=0, w=100, h=100), 50.0),   # Square
            (Rect(x=0, y=0, w=200, h=100), 50.0),   # Wide: use h
            (Rect(x=0, y=0, w=100, h=200), 50.0),   # Tall: use w
            (Rect(x=0, y=0, w=60, h=40), 20.0),     # Wide: use h
            (Rect(x=0, y=0, w=40, h=60), 20.0),     # Tall: use w
        ]

        for rect, expected_r in test_cases:
            circle = Circle.from_rect(rect)
            assert circle.r == expected_r, \
                f"For rect({rect.x}, {rect.y}, {rect.w}, {rect.h}): expected r={expected_r}, got {circle.r}"


class TestCircleROIEdgeCases:
    """Edge cases for circular ROI."""

    def test_very_thin_rect_produces_tiny_circle(self) -> None:
        """Very thin rectangle should produce very small radius."""
        rect = Rect(x=0, y=0, w=1000, h=2)
        circle = Circle.from_rect(rect)

        assert circle.cx == 500.0
        assert circle.cy == 1.0
        assert circle.r == 1.0  # min(1000, 2)/2

    def test_unit_rect_produces_half_unit_circle(self) -> None:
        """1x1 rectangle should produce r=0.5 circle."""
        rect = Rect(x=0, y=0, w=1, h=1)
        circle = Circle.from_rect(rect)

        assert circle.cx == 0.5
        assert circle.cy == 0.5
        assert circle.r == 0.5

    def test_circle_touches_rect_edges(self) -> None:
        """Inscribed circle should touch the shorter dimension's edges."""
        # Wide rect: circle touches top and bottom
        rect = Rect(x=0, y=0, w=200, h=100)
        circle = Circle.from_rect(rect)

        # Top touch point: (cx, 0)
        assert circle.contains_point(circle.cx, 0.0)
        # Bottom touch point: (cx, h)
        assert circle.contains_point(circle.cx, 100.0)

        # Tall rect: circle touches left and right
        rect = Rect(x=0, y=0, w=100, h=200)
        circle = Circle.from_rect(rect)

        # Left touch point: (0, cy)
        assert circle.contains_point(0.0, circle.cy)
        # Right touch point: (w, cy)
        assert circle.contains_point(100.0, circle.cy)


