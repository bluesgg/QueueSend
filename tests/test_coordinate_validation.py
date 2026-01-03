"""Tests for coordinate validation.

Verifies that:
- Points outside virtual desktop bounds are blocked
- ROI outside virtual desktop bounds is blocked
- Start is prevented when validation fails

See Executable Spec Section 4.4 for requirements.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.core.model import (
    CalibrationConfig,
    Point,
    Rect,
    ROI,
    ROIShape,
    VirtualDesktopInfo,
)
from app.core.os_adapter.validation import (
    ValidationResult,
    validate_point_in_bounds,
    validate_rect_in_bounds,
    validate_roi,
    validate_calibration_config,
)


# Test fixtures
@pytest.fixture
def standard_desktop() -> VirtualDesktopInfo:
    """Standard single monitor virtual desktop."""
    return VirtualDesktopInfo(left=0, top=0, width=1920, height=1080)


@pytest.fixture
def multi_monitor_desktop() -> VirtualDesktopInfo:
    """Multi-monitor setup with negative coordinates."""
    # Primary: 0,0 to 1920,1080
    # Secondary to the left: -1920,0 to 0,1080
    return VirtualDesktopInfo(left=-1920, top=0, width=3840, height=1080)


@pytest.fixture
def valid_config(standard_desktop: VirtualDesktopInfo) -> CalibrationConfig:
    """Valid calibration config within standard desktop."""
    return CalibrationConfig(
        roi=ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=200)),
        input_point=Point(x=500, y=500),
        send_point=Point(x=600, y=600),
        th_hold=0.02,
    )


class TestValidationResult:
    """Test ValidationResult helper class."""

    def test_success_is_valid(self) -> None:
        """Success result should be valid with no errors."""
        result = ValidationResult.success()
        assert result.valid is True
        assert result.errors == []
        assert bool(result) is True

    def test_failure_is_invalid(self) -> None:
        """Failure result should be invalid with errors."""
        result = ValidationResult.failure("Error message")
        assert result.valid is False
        assert "Error message" in result.errors
        assert bool(result) is False

    def test_multiple_errors(self) -> None:
        """Failure can have multiple error messages."""
        result = ValidationResult.failure("Error 1", "Error 2", "Error 3")
        assert len(result.errors) == 3


class TestPointValidation:
    """Test point coordinate validation."""

    def test_point_inside_bounds_valid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Point inside virtual desktop should be valid."""
        point = Point(x=500, y=500)
        result = validate_point_in_bounds(point, "测试点", standard_desktop)
        assert result.valid is True

    def test_point_at_origin_valid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Point at origin (0, 0) should be valid."""
        point = Point(x=0, y=0)
        result = validate_point_in_bounds(point, "测试点", standard_desktop)
        assert result.valid is True

    def test_point_at_boundary_valid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Point at boundary edge should be valid (< not <=)."""
        # Point at (1919, 1079) is the last valid point
        point = Point(x=1919, y=1079)
        result = validate_point_in_bounds(point, "测试点", standard_desktop)
        assert result.valid is True

    def test_point_outside_right_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Point outside right edge should be invalid."""
        point = Point(x=1920, y=500)  # x == width, out of bounds
        result = validate_point_in_bounds(point, "测试点", standard_desktop)
        assert result.valid is False
        assert len(result.errors) == 1

    def test_point_outside_bottom_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Point outside bottom edge should be invalid."""
        point = Point(x=500, y=1080)  # y == height, out of bounds
        result = validate_point_in_bounds(point, "测试点", standard_desktop)
        assert result.valid is False

    def test_point_negative_on_single_monitor_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Negative coordinates on single monitor should be invalid."""
        point = Point(x=-100, y=500)
        result = validate_point_in_bounds(point, "测试点", standard_desktop)
        assert result.valid is False

    def test_point_negative_on_multi_monitor_valid(
        self, multi_monitor_desktop: VirtualDesktopInfo
    ) -> None:
        """Negative coordinates on multi-monitor setup can be valid."""
        # Point on left monitor
        point = Point(x=-500, y=500)
        result = validate_point_in_bounds(point, "测试点", multi_monitor_desktop)
        assert result.valid is True

    def test_point_far_negative_on_multi_monitor_invalid(
        self, multi_monitor_desktop: VirtualDesktopInfo
    ) -> None:
        """Point too far left on multi-monitor should be invalid."""
        point = Point(x=-2000, y=500)  # Beyond left edge at -1920
        result = validate_point_in_bounds(point, "测试点", multi_monitor_desktop)
        assert result.valid is False


class TestRectValidation:
    """Test rectangle coordinate validation."""

    def test_rect_inside_bounds_valid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Rectangle fully inside should be valid."""
        rect = Rect(x=100, y=100, w=200, h=200)
        result = validate_rect_in_bounds(rect, "ROI", standard_desktop)
        assert result.valid is True

    def test_rect_touching_edges_valid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Rectangle touching edges but inside should be valid."""
        rect = Rect(x=0, y=0, w=1920, h=1080)  # Full screen
        result = validate_rect_in_bounds(rect, "ROI", standard_desktop)
        assert result.valid is True

    def test_rect_extending_past_right_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Rectangle extending past right edge should be invalid."""
        rect = Rect(x=1800, y=100, w=200, h=100)  # Extends to 2000
        result = validate_rect_in_bounds(rect, "ROI", standard_desktop)
        assert result.valid is False

    def test_rect_extending_past_bottom_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Rectangle extending past bottom edge should be invalid."""
        rect = Rect(x=100, y=1000, w=100, h=200)  # Extends to 1200
        result = validate_rect_in_bounds(rect, "ROI", standard_desktop)
        assert result.valid is False

    def test_rect_negative_origin_on_single_monitor_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Negative origin on single monitor should be invalid."""
        rect = Rect(x=-50, y=100, w=100, h=100)
        result = validate_rect_in_bounds(rect, "ROI", standard_desktop)
        assert result.valid is False


class TestROIValidation:
    """Test ROI-specific validation."""

    def test_valid_roi_passes(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Valid ROI should pass validation."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=200))
        result = validate_roi(roi, standard_desktop)
        assert result.valid is True

    def test_zero_width_roi_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """ROI with zero width should be invalid (Spec 4.4: w > 0)."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=0, h=200))
        result = validate_roi(roi, standard_desktop)
        assert result.valid is False
        assert any("宽度" in err for err in result.errors)

    def test_zero_height_roi_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """ROI with zero height should be invalid (Spec 4.4: h > 0)."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=0))
        result = validate_roi(roi, standard_desktop)
        assert result.valid is False
        assert any("高度" in err for err in result.errors)

    def test_negative_dimensions_roi_invalid(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """ROI with negative dimensions should be invalid."""
        roi = ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=-50, h=200))
        result = validate_roi(roi, standard_desktop)
        assert result.valid is False

    def test_circle_roi_validates_bounding_rect(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Circle ROI should validate its bounding rectangle."""
        roi = ROI(shape=ROIShape.CIRCLE, rect=Rect(x=100, y=100, w=200, h=200))
        result = validate_roi(roi, standard_desktop)
        assert result.valid is True


class TestCalibrationConfigValidation:
    """Test complete calibration config validation."""

    def test_valid_config_passes(
        self,
        valid_config: CalibrationConfig,
        standard_desktop: VirtualDesktopInfo,
    ) -> None:
        """Valid config should pass all validations."""
        result = validate_calibration_config(valid_config, standard_desktop)
        assert result.valid is True

    def test_invalid_input_point_fails(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Config with invalid input point should fail."""
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=200)),
            input_point=Point(x=5000, y=500),  # Out of bounds
            send_point=Point(x=600, y=600),
            th_hold=0.02,
        )
        result = validate_calibration_config(config, standard_desktop)
        assert result.valid is False
        assert any("输入点" in err for err in result.errors)

    def test_invalid_send_point_fails(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Config with invalid send point should fail."""
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=200)),
            input_point=Point(x=500, y=500),
            send_point=Point(x=600, y=5000),  # Out of bounds
            th_hold=0.02,
        )
        result = validate_calibration_config(config, standard_desktop)
        assert result.valid is False
        assert any("发送点" in err for err in result.errors)

    def test_invalid_roi_fails(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Config with invalid ROI should fail."""
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=1800, y=100, w=200, h=200)),  # Extends past edge
            input_point=Point(x=500, y=500),
            send_point=Point(x=600, y=600),
            th_hold=0.02,
        )
        result = validate_calibration_config(config, standard_desktop)
        assert result.valid is False

    def test_multiple_validation_errors_collected(
        self, standard_desktop: VirtualDesktopInfo
    ) -> None:
        """Multiple validation errors should all be collected."""
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=0, h=0)),  # Invalid dims
            input_point=Point(x=5000, y=500),  # Out of bounds
            send_point=Point(x=600, y=5000),  # Out of bounds
            th_hold=0.02,
        )
        result = validate_calibration_config(config, standard_desktop)
        assert result.valid is False
        # Should have multiple errors
        assert len(result.errors) >= 2


class TestStartPrevention:
    """Test that Start is blocked when validation fails."""

    def test_start_blocked_on_validation_failure(self) -> None:
        """Start should be blocked when coordinates are out of bounds."""
        # This is a behavioral test - the actual blocking happens in controller
        # Here we verify the validation returns failure
        desktop = VirtualDesktopInfo(left=0, top=0, width=1920, height=1080)
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=200)),
            input_point=Point(x=5000, y=500),  # Invalid
            send_point=Point(x=600, y=600),
            th_hold=0.02,
        )

        result = validate_calibration_config(config, desktop)

        # Validation should fail, which blocks Start
        assert not result.valid
        assert not result  # Boolean conversion

    def test_start_allowed_on_validation_success(self) -> None:
        """Start should be allowed when all coordinates are valid."""
        desktop = VirtualDesktopInfo(left=0, top=0, width=1920, height=1080)
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=100, y=100, w=200, h=200)),
            input_point=Point(x=500, y=500),
            send_point=Point(x=600, y=600),
            th_hold=0.02,
        )

        result = validate_calibration_config(config, desktop)

        # Validation should pass, allowing Start
        assert result.valid
        assert result  # Boolean conversion


class TestMultiMonitorScenarios:
    """Test validation with multi-monitor configurations."""

    def test_negative_coordinates_valid_on_left_monitor(self) -> None:
        """Points on left monitor with negative coordinates should be valid."""
        # Setup: left monitor at -1920 to 0, right monitor at 0 to 1920
        desktop = VirtualDesktopInfo(left=-1920, top=0, width=3840, height=1080)

        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=-1800, y=100, w=200, h=200)),
            input_point=Point(x=-1500, y=500),
            send_point=Point(x=-1400, y=600),
            th_hold=0.02,
        )

        result = validate_calibration_config(config, desktop)
        assert result.valid is True

    def test_roi_spanning_monitors_valid(self) -> None:
        """ROI spanning monitor boundary should be valid if within desktop."""
        desktop = VirtualDesktopInfo(left=-1920, top=0, width=3840, height=1080)

        # ROI from -100 to 100 spans the monitor boundary
        config = CalibrationConfig(
            roi=ROI(shape=ROIShape.RECT, rect=Rect(x=-100, y=100, w=200, h=200)),
            input_point=Point(x=0, y=500),
            send_point=Point(x=100, y=600),
            th_hold=0.02,
        )

        result = validate_calibration_config(config, desktop)
        assert result.valid is True


