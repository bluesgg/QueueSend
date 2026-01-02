"""Run panel for QueueSend automation control.

The main control panel that shows during automation:
- Always on top
- Snaps to bottom-right of screen containing send point
- Shows progress, status, controls, and log

See Executable Spec Section 3 for requirements.
"""

from typing import Optional

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import PANEL_MARGIN_PX
from app.core.logging import LogBuffer, LogEntry
from app.core.model import Point, ROIShape, State

from .widgets import (
    ControlButtons,
    CountdownDisplay,
    FixedWarningBanner,
    ProgressDisplay,
    StatusIndicator,
    ThresholdInput,
)


class LogView(QPlainTextEdit):
    """Log viewer with circular buffer display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(200)  # Circular buffer
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setStyleSheet(
            "font-family: Consolas, Monaco, monospace; font-size: 11px;"
        )

    def add_entry(self, entry: LogEntry) -> None:
        """Add a log entry."""
        self.appendPlainText(entry.format())

    def set_entries(self, entries: list[LogEntry]) -> None:
        """Set all log entries."""
        self.clear()
        for entry in entries:
            self.appendPlainText(entry.format())


class RunPanel(QWidget):
    """Main control panel for automation.

    Features (per Spec Section 3):
    - Always on top (WindowStaysOnTopHint)
    - Snaps to bottom-right of screen containing send_point
    - Shows progress (i/N, 1-based), status, controls, log
    - Fixed warning banner during run
    """

    # Signals for control actions
    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    calibrate_roi_requested = Signal(ROIShape)  # Emits selected shape
    calibrate_input_requested = Signal()
    calibrate_send_requested = Signal()
    threshold_calibrate_requested = Signal()
    threshold_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Window flags: always on top, tool window
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("QueueSend")
        self.setMinimumWidth(350)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._connect_signals()

        # State tracking
        self._is_running = False
        self._send_point: Optional[Point] = None

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Warning banner (hidden by default)
        self._warning_banner = FixedWarningBanner()
        self._warning_banner.hide()
        layout.addWidget(self._warning_banner)

        # Countdown display (hidden by default)
        self._countdown = CountdownDisplay()
        self._countdown.hide()
        layout.addWidget(self._countdown)

        # Status section
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)

        self._status = StatusIndicator()
        status_layout.addWidget(self._status)

        status_layout.addStretch()

        self._progress = ProgressDisplay()
        status_layout.addWidget(self._progress)

        layout.addWidget(status_frame)

        # Calibration section
        calib_frame = QFrame()
        calib_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        calib_layout = QVBoxLayout(calib_frame)

        calib_label = QLabel("标定")
        calib_label.setStyleSheet("font-weight: bold;")
        calib_layout.addWidget(calib_label)

        # ROI shape selection (Spec 4.2)
        shape_layout = QHBoxLayout()
        shape_layout.addWidget(QLabel("ROI形状:"))

        self._shape_group = QButtonGroup(self)
        self._rect_radio = QRadioButton("矩形")
        self._rect_radio.setChecked(True)
        self._circle_radio = QRadioButton("圆形")
        self._shape_group.addButton(self._rect_radio, 0)
        self._shape_group.addButton(self._circle_radio, 1)
        shape_layout.addWidget(self._rect_radio)
        shape_layout.addWidget(self._circle_radio)
        shape_layout.addStretch()

        calib_layout.addLayout(shape_layout)

        # Calibration buttons
        calib_btns = QHBoxLayout()

        self._roi_btn = QPushButton("ROI区域")
        self._roi_btn.clicked.connect(self._on_roi_calibrate_clicked)
        calib_btns.addWidget(self._roi_btn)

        self._input_btn = QPushButton("输入点")
        self._input_btn.clicked.connect(self.calibrate_input_requested.emit)
        calib_btns.addWidget(self._input_btn)

        self._send_btn = QPushButton("发送点")
        self._send_btn.clicked.connect(self.calibrate_send_requested.emit)
        calib_btns.addWidget(self._send_btn)

        calib_layout.addLayout(calib_btns)

        # Calibration status
        self._calib_status = QLabel("未完成标定")
        self._calib_status.setStyleSheet("color: #dc3545;")
        calib_layout.addWidget(self._calib_status)

        layout.addWidget(calib_frame)

        # Threshold section
        self._threshold_input = ThresholdInput()
        self._threshold_input.calibrate_clicked.connect(
            self.threshold_calibrate_requested.emit
        )
        self._threshold_input.value_changed.connect(self.threshold_changed.emit)
        layout.addWidget(self._threshold_input)

        # Control buttons
        control_layout = QHBoxLayout()

        self._start_btn = QPushButton("开始 (Start)")
        self._start_btn.setStyleSheet(
            "background-color: #28a745; color: white; font-weight: bold;"
        )
        self._start_btn.clicked.connect(self.start_requested.emit)
        control_layout.addWidget(self._start_btn)

        self._controls = ControlButtons()
        self._controls.pause_clicked.connect(self.pause_requested.emit)
        self._controls.resume_clicked.connect(self.resume_requested.emit)
        self._controls.stop_clicked.connect(self.stop_requested.emit)
        self._controls.hide()
        control_layout.addWidget(self._controls)

        layout.addLayout(control_layout)

        # Log section
        log_label = QLabel("日志")
        log_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(log_label)

        self._log_view = LogView()
        layout.addWidget(self._log_view, 1)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        pass

    def _on_roi_calibrate_clicked(self) -> None:
        """Handle ROI calibrate button click."""
        shape = ROIShape.CIRCLE if self._circle_radio.isChecked() else ROIShape.RECT
        self.calibrate_roi_requested.emit(shape)

    def get_selected_roi_shape(self) -> ROIShape:
        """Get the currently selected ROI shape."""
        return ROIShape.CIRCLE if self._circle_radio.isChecked() else ROIShape.RECT

    # State updates

    def set_state(self, state: State) -> None:
        """Update displayed state.

        Args:
            state: Current automation state
        """
        self._status.set_state(state.name)

        # Update UI based on state
        is_running = state != State.Idle
        is_paused = state == State.Paused
        is_countdown = state == State.Countdown

        self._is_running = is_running

        # Show/hide elements
        self._warning_banner.setVisible(is_running)
        self._countdown.setVisible(is_countdown)
        self._start_btn.setVisible(not is_running)
        self._controls.setVisible(is_running)
        self._controls.set_paused(is_paused)

        # Enable/disable calibration buttons
        self._set_calibration_enabled(not is_running)

        # Threshold input enabled only when idle or paused (but spec says disabled when paused)
        self._threshold_input.set_enabled(not is_running)

    def set_progress(self, current: int, total: int) -> None:
        """Update progress display.

        Args:
            current: Current message index (1-based)
            total: Total message count
        """
        self._progress.set_progress(current, total)

    def set_countdown(self, seconds: float) -> None:
        """Update countdown display.

        Args:
            seconds: Remaining seconds
        """
        self._countdown.set_value(seconds)

    def set_calibration_status(
        self,
        roi_set: bool,
        input_set: bool,
        send_set: bool,
    ) -> None:
        """Update calibration status display.

        Args:
            roi_set: Whether ROI is calibrated
            input_set: Whether input point is set
            send_set: Whether send point is set
        """
        all_set = roi_set and input_set and send_set

        if all_set:
            self._calib_status.setText("✓ 标定完成")
            self._calib_status.setStyleSheet("color: #28a745;")
            self._start_btn.setEnabled(True)
        else:
            missing = []
            if not roi_set:
                missing.append("ROI")
            if not input_set:
                missing.append("输入点")
            if not send_set:
                missing.append("发送点")
            self._calib_status.setText(f"未设置: {', '.join(missing)}")
            self._calib_status.setStyleSheet("color: #dc3545;")
            self._start_btn.setEnabled(False)

        # Update button styles
        self._roi_btn.setStyleSheet(
            "background-color: #d4edda;" if roi_set else ""
        )
        self._input_btn.setStyleSheet(
            "background-color: #d4edda;" if input_set else ""
        )
        self._send_btn.setStyleSheet(
            "background-color: #d4edda;" if send_set else ""
        )

    def _set_calibration_enabled(self, enabled: bool) -> None:
        """Enable or disable calibration buttons and shape selection."""
        self._roi_btn.setEnabled(enabled)
        self._input_btn.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._rect_radio.setEnabled(enabled)
        self._circle_radio.setEnabled(enabled)

    def set_threshold(self, value: float) -> None:
        """Set threshold value.

        Args:
            value: Threshold value
        """
        self._threshold_input.set_value(value)

    def highlight_calibrate_button(self, highlight: bool) -> None:
        """Highlight threshold calibration button.

        Args:
            highlight: Whether to highlight
        """
        self._threshold_input.highlight_calibrate(highlight)

    # Positioning

    def set_send_point(self, point: Point) -> None:
        """Store send point for positioning.

        Args:
            point: Send button location
        """
        self._send_point = point

    def snap_to_screen_corner(self) -> None:
        """Snap panel to bottom-right of screen containing send point.

        Implements Spec Section 3.1 positioning logic.
        """
        if self._send_point is None:
            return

        # Find screen containing send point
        target_screen = None
        for screen in QApplication.screens():
            geom = screen.geometry()
            if geom.contains(self._send_point.x, self._send_point.y):
                target_screen = screen
                break

        if target_screen is None:
            target_screen = QApplication.primaryScreen()

        # Calculate position
        available = target_screen.availableGeometry()
        new_x = available.right() - self.width() - PANEL_MARGIN_PX
        new_y = available.bottom() - self.height() - PANEL_MARGIN_PX

        self.move(new_x, new_y)

    # Logging

    def add_log_entry(self, entry: LogEntry) -> None:
        """Add a log entry to the log view.

        Args:
            entry: Log entry to add
        """
        self._log_view.add_entry(entry)

    def set_log_buffer(self, buffer: LogBuffer) -> None:
        """Set log buffer and display existing entries.

        Args:
            buffer: Log buffer to use
        """
        # Display existing entries
        self._log_view.set_entries(buffer.get_all())

        # Add listener for new entries
        buffer.add_listener(self.add_log_entry)

    def clear_log(self) -> None:
        """Clear the log view."""
        self._log_view.clear()

    # Window behavior

    def closeEvent(self, event) -> None:
        """Handle close event - request stop if running."""
        if self._is_running:
            self.stop_requested.emit()
        event.accept()

