"""Main window for QueueSend application.

Combines all UI components into the main application window:
- Message editor
- Calibration controls
- Run panel integration

See TDD Section 9 for UI requirements.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.logging import LogBuffer, Logger, get_logger
from app.core.model import CalibrationConfig, Point, ROI, ROIShape, State

from .calibration_overlay import CalibrationOverlay
from .message_editor import MessageEditor
from .run_panel import RunPanel
from .widgets import WarningBanner


class MainWindow(QMainWindow):
    """Main application window.

    Contains:
    - Message editor (left panel)
    - Run panel with status and controls (right panel)
    - Calibration overlay (shown during calibration)
    """

    # Signals for engine communication
    start_automation = Signal(list, CalibrationConfig)  # messages, config
    pause_automation = Signal()
    resume_automation = Signal()
    stop_automation = Signal()
    calibrate_threshold = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("QueueSend - ROI自动化工具")
        self.setMinimumSize(800, 600)

        # State
        self._current_roi: Optional[ROI] = None
        self._input_point: Optional[Point] = None
        self._send_point: Optional[Point] = None
        self._threshold: float = 0.02
        self._logger = get_logger()
        self._dpi_warning: Optional[str] = None

        self._setup_ui()
        self._setup_calibration_overlay()
        self._connect_signals()
        self._update_calibration_status()

    def _setup_ui(self) -> None:
        """Setup the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # DPI warning banner (shown if needed)
        self._dpi_banner = WarningBanner("", dismissible=True)
        self._dpi_banner.hide()
        main_layout.addWidget(self._dpi_banner)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Message editor
        self._message_editor = MessageEditor()
        splitter.addWidget(self._message_editor)

        # Right: Run panel
        self._run_panel = RunPanel()
        splitter.addWidget(self._run_panel)

        # Set initial sizes (60% editor, 40% panel)
        splitter.setSizes([480, 320])

        main_layout.addWidget(splitter)

    def _setup_calibration_overlay(self) -> None:
        """Setup the calibration overlay."""
        self._calibration_overlay = CalibrationOverlay()

        # Connect overlay signals
        self._calibration_overlay.roi_selected.connect(self._on_roi_selected)
        self._calibration_overlay.input_point_selected.connect(
            self._on_input_point_selected
        )
        self._calibration_overlay.send_point_selected.connect(
            self._on_send_point_selected
        )

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        # Run panel signals
        self._run_panel.start_requested.connect(self._on_start_requested)
        self._run_panel.pause_requested.connect(self.pause_automation.emit)
        self._run_panel.resume_requested.connect(self._on_resume_requested)
        self._run_panel.stop_requested.connect(self.stop_automation.emit)

        # Calibration signals
        self._run_panel.calibrate_roi_requested.connect(self._start_roi_calibration)
        self._run_panel.calibrate_input_requested.connect(
            self._start_input_point_calibration
        )
        self._run_panel.calibrate_send_requested.connect(
            self._start_send_point_calibration
        )
        
        # Set initial calibration status
        self._update_calibration_status()

        # Threshold signals
        self._run_panel.threshold_calibrate_requested.connect(
            self.calibrate_threshold.emit
        )
        self._run_panel.threshold_changed.connect(self._on_threshold_changed)

        # Set log buffer
        self._run_panel.set_log_buffer(self._logger.buffer)

    # Calibration handlers

    @Slot(ROIShape)
    def _start_roi_calibration(self, shape: ROIShape) -> None:
        """Start ROI calibration.

        Args:
            shape: ROI shape to use (RECT or CIRCLE)
        """
        self._calibration_overlay.set_existing_points(
            self._input_point, self._send_point
        )
        self._calibration_overlay.start_roi_selection(shape)

    def _start_input_point_calibration(self) -> None:
        """Start input point calibration."""
        self._calibration_overlay.set_existing_points(
            self._input_point, self._send_point
        )
        self._calibration_overlay.start_input_point_selection()

    def _start_send_point_calibration(self) -> None:
        """Start send point calibration."""
        self._calibration_overlay.set_existing_points(
            self._input_point, self._send_point
        )
        self._calibration_overlay.start_send_point_selection()

    @Slot(ROI)
    def _on_roi_selected(self, roi: ROI) -> None:
        """Handle ROI selection."""
        self._current_roi = roi
        self._update_calibration_status()
        self._logger.info(
            f"ROI已设置: ({roi.rect.x}, {roi.rect.y}) "
            f"{roi.rect.w}x{roi.rect.h} [{roi.shape.value}]"
        )

    @Slot(Point)
    def _on_input_point_selected(self, point: Point) -> None:
        """Handle input point selection."""
        self._input_point = point
        self._update_calibration_status()
        self._logger.info(f"输入点已设置: ({point.x}, {point.y})")

    @Slot(Point)
    def _on_send_point_selected(self, point: Point) -> None:
        """Handle send point selection."""
        self._send_point = point
        self._run_panel.set_send_point(point)
        self._update_calibration_status()
        self._logger.info(f"发送点已设置: ({point.x}, {point.y})")

    def _update_calibration_status(self) -> None:
        """Update calibration status in run panel."""
        self._run_panel.set_calibration_status(
            roi_set=self._current_roi is not None,
            input_set=self._input_point is not None,
            send_set=self._send_point is not None,
        )

    # Control handlers

    def _on_start_requested(self) -> None:
        """Handle start button click."""
        # Validate calibration
        if not self._is_calibration_complete():
            QMessageBox.warning(
                self,
                "无法开始",
                "请先完成标定(ROI、输入点、发送点)",
            )
            return

        # Get messages
        messages = self._message_editor.get_messages()
        if not messages:
            QMessageBox.warning(
                self,
                "无法开始",
                "消息列表为空,请添加至少一条消息",
            )
            return

        # Create config
        config = CalibrationConfig(
            roi=self._current_roi,  # type: ignore
            input_point=self._input_point,  # type: ignore
            send_point=self._send_point,  # type: ignore
            th_hold=self._threshold,
        )

        # Snap panel to corner
        self._run_panel.snap_to_screen_corner()

        # Emit start signal
        self.start_automation.emit(messages, config)

    def _on_resume_requested(self) -> None:
        """Handle resume button click."""
        # Check for message changes (will be done by engine)
        self.resume_automation.emit()

    @Slot(float)
    def _on_threshold_changed(self, value: float) -> None:
        """Handle threshold change."""
        self._threshold = value

    def _is_calibration_complete(self) -> bool:
        """Check if all calibration is complete."""
        return (
            self._current_roi is not None and
            self._input_point is not None and
            self._send_point is not None
        )

    # State updates from engine

    @Slot(State)
    def update_state(self, state: State) -> None:
        """Update UI for new automation state.

        Args:
            state: New automation state
        """
        self._run_panel.set_state(state)

        # Disable message editing during run (except paused)
        is_running = state not in (State.Idle, State.Paused)
        self._message_editor.set_editable(not is_running)

    @Slot(int, int)
    def update_progress(self, current: int, total: int) -> None:
        """Update progress display.

        Args:
            current: Current message index (1-based)
            total: Total messages
        """
        self._run_panel.set_progress(current, total)

    @Slot(float)
    def update_countdown(self, seconds: float) -> None:
        """Update countdown display.

        Args:
            seconds: Remaining seconds
        """
        self._run_panel.set_countdown(seconds)

    @Slot(float)
    def set_recommended_threshold(self, th_rec: float) -> None:
        """Set recommended threshold from calibration.

        Args:
            th_rec: Recommended threshold value
        """
        self._threshold = th_rec
        self._run_panel.set_threshold(th_rec)

    @Slot(bool)
    def highlight_calibrate(self, highlight: bool) -> None:
        """Highlight calibration button.

        Args:
            highlight: Whether to highlight
        """
        self._run_panel.highlight_calibrate_button(highlight)

    # DPI warning

    def set_dpi_warning(self, warning: str) -> None:
        """Show DPI warning banner.

        Args:
            warning: Warning message to display
        """
        if warning:
            self._dpi_warning = warning
            self._dpi_banner.set_message(warning)
            self._dpi_banner.show()

    # Message snapshot for pause/resume

    def get_message_snapshot(self) -> list[str]:
        """Get current message list for snapshot."""
        return self._message_editor.get_snapshot()

    def check_messages_changed(self, snapshot: list[str]) -> bool:
        """Check if messages changed since snapshot."""
        return self._message_editor.has_changed(snapshot)

    # Dialogs

    def show_message_changed_dialog(self) -> None:
        """Show dialog when messages changed during pause."""
        QMessageBox.warning(
            self,
            "消息已修改",
            "检测到消息列表已修改,自动化已停止。\n若需继续,请重新Start。",
        )

    def show_error_dialog(self, title: str, message: str) -> None:
        """Show error dialog.

        Args:
            title: Dialog title
            message: Error message
        """
        QMessageBox.critical(self, title, message)

    def show_capture_error_dialog(self) -> tuple[str, None]:
        """Show capture error dialog with options.

        Returns:
            Tuple of (action, None) where action is 'retry', 'log', or 'close'
        """
        result = QMessageBox.critical(
            self,
            "无法获取屏幕截图",
            "已重试3次失败\n\n"
            "可能原因:\n"
            "- macOS权限被撤销\n"
            "- Windows DPI设置异常\n"
            "- 显示器配置变化\n\n"
            "建议操作:\n"
            "- 检查权限设置\n"
            "- 重启应用\n"
            "- 重新标定",
            QMessageBox.StandardButton.Retry |
            QMessageBox.StandardButton.Close,
            QMessageBox.StandardButton.Close,
        )

        if result == QMessageBox.StandardButton.Retry:
            return ("retry", None)
        return ("close", None)

