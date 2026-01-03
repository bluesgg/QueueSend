"""Coordinate and configuration validation utilities.

Provides validation functions to check if points and ROIs are within
the virtual desktop bounds before starting automation.

See Executable Spec Section 4.4 for requirements.
"""

from dataclasses import dataclass
from typing import Optional

from ..model import CalibrationConfig, Point, Rect, ROI, VirtualDesktopInfo
from . import get_virtual_desktop_info


@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        valid: True if validation passed
        errors: List of error messages if validation failed
    """

    valid: bool
    errors: list[str]

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(valid=True, errors=[])

    @classmethod
    def failure(cls, *errors: str) -> "ValidationResult":
        """Create a failed validation result with error messages."""
        return cls(valid=False, errors=list(errors))

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.valid


def validate_point_in_bounds(
    point: Point,
    name: str,
    desktop: Optional[VirtualDesktopInfo] = None,
) -> ValidationResult:
    """Validate that a point is within virtual desktop bounds.

    Args:
        point: The point to validate
        name: Human-readable name for error messages (e.g., "输入点", "发送点")
        desktop: Virtual desktop info (fetched automatically if None)

    Returns:
        ValidationResult indicating success or failure with error message
    """
    if desktop is None:
        desktop = get_virtual_desktop_info()

    if not desktop.contains_point(point):
        return ValidationResult.failure(
            f"{name}坐标 ({point.x}, {point.y}) 超出虚拟桌面范围 "
            f"[{desktop.left}, {desktop.top}] - [{desktop.right}, {desktop.bottom}]"
        )

    return ValidationResult.success()


def validate_rect_in_bounds(
    rect: Rect,
    name: str,
    desktop: Optional[VirtualDesktopInfo] = None,
) -> ValidationResult:
    """Validate that a rectangle is entirely within virtual desktop bounds.

    Args:
        rect: The rectangle to validate
        name: Human-readable name for error messages
        desktop: Virtual desktop info (fetched automatically if None)

    Returns:
        ValidationResult indicating success or failure
    """
    if desktop is None:
        desktop = get_virtual_desktop_info()

    if not desktop.contains_rect(rect):
        return ValidationResult.failure(
            f"{name}区域 ({rect.x}, {rect.y}, {rect.w}x{rect.h}) 超出虚拟桌面范围"
        )

    return ValidationResult.success()


def validate_roi(
    roi: ROI,
    desktop: Optional[VirtualDesktopInfo] = None,
) -> ValidationResult:
    """Validate ROI dimensions and bounds.

    Checks:
    - ROI width > 0
    - ROI height > 0
    - ROI is within virtual desktop bounds

    Args:
        roi: The ROI to validate
        desktop: Virtual desktop info (fetched automatically if None)

    Returns:
        ValidationResult indicating success or failure
    """
    errors: list[str] = []

    # Check dimensions (Spec 4.4)
    if roi.rect.w <= 0:
        errors.append("ROI宽度必须大于0")
    if roi.rect.h <= 0:
        errors.append("ROI高度必须大于0")

    if errors:
        return ValidationResult.failure(*errors)

    # Check bounds
    return validate_rect_in_bounds(roi.rect, "ROI", desktop)


def validate_calibration_config(
    config: CalibrationConfig,
    desktop: Optional[VirtualDesktopInfo] = None,
) -> ValidationResult:
    """Validate complete calibration configuration before Start.

    Checks all requirements from Spec Section 4.4:
    - ROI width and height > 0
    - Input point within virtual desktop
    - Send point within virtual desktop
    - ROI within virtual desktop

    Args:
        config: The calibration configuration to validate
        desktop: Virtual desktop info (fetched automatically if None)

    Returns:
        ValidationResult with all validation errors
    """
    if desktop is None:
        desktop = get_virtual_desktop_info()

    all_errors: list[str] = []

    # Validate ROI
    roi_result = validate_roi(config.roi, desktop)
    if not roi_result.valid:
        all_errors.extend(roi_result.errors)

    # Validate input point
    input_result = validate_point_in_bounds(
        config.input_point, "输入点", desktop
    )
    if not input_result.valid:
        all_errors.extend(input_result.errors)

    # Validate send point
    send_result = validate_point_in_bounds(
        config.send_point, "发送点", desktop
    )
    if not send_result.valid:
        all_errors.extend(send_result.errors)

    if all_errors:
        return ValidationResult.failure(*all_errors)

    return ValidationResult.success()


def check_macos_display_limit() -> ValidationResult:
    """Check macOS single display requirement.

    Per Spec Section 2.3, macOS only supports single display.

    Returns:
        ValidationResult indicating if display configuration is valid
    """
    from . import IS_MACOS, get_screen_count

    if not IS_MACOS:
        return ValidationResult.success()

    screen_count = get_screen_count()
    if screen_count > 1:
        return ValidationResult.failure(
            f"macOS版本仅支持单显示器环境,当前检测到{screen_count}个显示器"
        )

    return ValidationResult.success()


