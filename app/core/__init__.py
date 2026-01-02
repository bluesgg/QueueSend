"""Core automation engine and utilities.

This package provides the core functionality for QueueSend:
- Data models (Point, Rect, ROI, State, etc.)
- Screen capture and ROI cropping
- Diff calculation and threshold calibration
- Automation engine with state machine
- Logging with circular buffer
- Platform-specific adapters
"""

from .constants import (
    CALIB_FRAMES_DEFAULT,
    CAPTURE_RETRY_INTERVAL_MS,
    CAPTURE_RETRY_N,
    HOLD_HITS_REQUIRED,
    LOG_BUFFER_SIZE,
    PANEL_MARGIN_PX,
    SAMPLE_HZ,
    T_COOL_SEC,
    T_COUNTDOWN_SEC,
    TH_HOLD_DEFAULT,
    TH_HOLD_MAX,
    TH_HOLD_MIN,
)
from .model import (
    CalibrationConfig,
    CalibrationStats,
    Circle,
    Event,
    Point,
    Rect,
    ROI,
    ROIShape,
    State,
    VirtualDesktopInfo,
)

__all__ = [
    # Constants
    "T_COUNTDOWN_SEC",
    "T_COOL_SEC",
    "SAMPLE_HZ",
    "HOLD_HITS_REQUIRED",
    "TH_HOLD_DEFAULT",
    "TH_HOLD_MIN",
    "TH_HOLD_MAX",
    "CALIB_FRAMES_DEFAULT",
    "CAPTURE_RETRY_N",
    "CAPTURE_RETRY_INTERVAL_MS",
    "LOG_BUFFER_SIZE",
    "PANEL_MARGIN_PX",
    # Models
    "State",
    "Event",
    "ROIShape",
    "Point",
    "Rect",
    "Circle",
    "ROI",
    "CalibrationConfig",
    "CalibrationStats",
    "VirtualDesktopInfo",
]
