"""UI components for QueueSend.

This package provides PySide6-based UI components:
- MainWindow: Main application window
- RunPanel: Control panel with progress and status
- MessageEditor: List-based message editor
- CalibrationOverlay: Fullscreen calibration overlay
- Common widgets: Banners, indicators, buttons
"""

from .calibration_overlay import CalibrationMode, CalibrationOverlay
from .main_window import MainWindow
from .message_editor import MessageEditor, MessageListItem, MessageTextEdit
from .run_panel import LogView, RunPanel
from .widgets import (
    ControlButtons,
    CountdownDisplay,
    FixedWarningBanner,
    ProgressDisplay,
    StatusIndicator,
    ThresholdInput,
    WarningBanner,
)

__all__ = [
    # Main window
    "MainWindow",
    # Run panel
    "RunPanel",
    "LogView",
    # Message editor
    "MessageEditor",
    "MessageListItem",
    "MessageTextEdit",
    # Calibration
    "CalibrationOverlay",
    "CalibrationMode",
    # Widgets
    "WarningBanner",
    "FixedWarningBanner",
    "StatusIndicator",
    "ProgressDisplay",
    "CountdownDisplay",
    "ControlButtons",
    "ThresholdInput",
]
