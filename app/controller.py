"""Application controller that wires UI to automation engine.

Handles all signal connections between MainWindow and AutomationEngine,
plus error handling and validation.
"""

from typing import Optional

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication

from app.core.engine import AutomationEngine
from app.core.logging import get_logger
from app.core.model import CalibrationConfig, CalibrationStats, State
from app.core.os_adapter.validation import validate_calibration_config
from app.ui.main_window import MainWindow


class ApplicationController(QObject):
    """Controller that connects UI to automation engine.

    Responsibilities:
    - Wire signals between MainWindow and AutomationEngine
    - Handle validation before starting
    - Manage error dialogs and recovery
    - Coordinate message change detection
    """

    def __init__(
        self,
        window: MainWindow,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialize the controller.

        Args:
            window: Main application window
            parent: Parent QObject
        """
        super().__init__(parent)

        self._window = window
        self._engine = AutomationEngine(self)
        self._logger = get_logger()

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect all signals between window and engine."""
        # Window -> Controller -> Engine
        self._window.start_automation.connect(self._on_start_requested)
        self._window.pause_automation.connect(self._on_pause_requested)
        self._window.resume_automation.connect(self._on_resume_requested)
        self._window.stop_automation.connect(self._on_stop_requested)
        self._window.calibrate_threshold.connect(self._on_calibrate_threshold)

        # Engine -> Controller -> Window
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.progress_updated.connect(self._on_progress_updated)
        self._engine.countdown_tick.connect(self._on_countdown_tick)
        self._engine.sampling_update.connect(self._on_sampling_update)
        self._engine.automation_finished.connect(self._on_automation_finished)
        self._engine.error_occurred.connect(self._on_error_occurred)
        self._engine.capture_failed.connect(self._on_capture_failed)
        self._engine.message_changed_during_pause.connect(
            self._on_message_changed_during_pause
        )
        self._engine.calibration_completed.connect(self._on_calibration_completed)

        # Set message getter for engine
        self._engine.set_message_getter(self._window.get_message_snapshot)

    # Start/Stop handlers

    @Slot(list, CalibrationConfig)
    def _on_start_requested(
        self,
        messages: list[str],
        config: CalibrationConfig,
    ) -> None:
        """Handle start request from UI.

        Args:
            messages: List of messages to send
            config: Calibration configuration
        """
        # Validate configuration (Spec 4.4)
        validation = validate_calibration_config(config)
        if not validation.valid:
            error_msg = "\n".join(validation.errors)
            self._window.show_error_dialog(
                "标定无效",
                f"请重新标定:\n{error_msg}",
            )
            self._logger.error(f"标定验证失败: {error_msg}")
            return

        # Start engine
        if self._engine.start(messages, config):
            self._logger.info("自动化已启动")
        else:
            self._window.show_error_dialog(
                "启动失败",
                "无法启动自动化,请检查日志",
            )

    @Slot()
    def _on_pause_requested(self) -> None:
        """Handle pause request."""
        self._engine.pause()

    @Slot()
    def _on_resume_requested(self) -> None:
        """Handle resume request."""
        self._engine.resume()

    @Slot()
    def _on_stop_requested(self) -> None:
        """Handle stop request."""
        self._engine.stop()

    @Slot()
    def _on_calibrate_threshold(self) -> None:
        """Handle threshold calibration request."""
        # Need ROI to calibrate
        if self._window._current_roi is None:
            self._window.show_error_dialog(
                "无法校准",
                "请先设置ROI区域",
            )
            return

        # Run calibration (blocking, but quick)
        try:
            self._engine.calibrate_threshold(self._window._current_roi)
        except Exception as e:
            self._window.show_error_dialog(
                "校准失败",
                f"阈值校准失败: {e}",
            )

    # Engine state handlers

    @Slot(State)
    def _on_state_changed(self, state: State) -> None:
        """Handle state change from engine."""
        self._window.update_state(state)

        # Highlight calibrate button after first cooling (Spec 8.1)
        if state == State.WaitingHold:
            self._window.highlight_calibrate(True)

    @Slot(int, int)
    def _on_progress_updated(self, current: int, total: int) -> None:
        """Handle progress update."""
        self._window.update_progress(current, total)

    @Slot(float)
    def _on_countdown_tick(self, remaining: float) -> None:
        """Handle countdown tick."""
        self._window.update_countdown(remaining)

    @Slot(float, int)
    def _on_sampling_update(self, diff: float, hold_hits: int) -> None:
        """Handle sampling update during WaitingHold."""
        # Could add more UI feedback here if needed
        pass

    @Slot()
    def _on_automation_finished(self) -> None:
        """Handle automation completion."""
        self._logger.info("自动化流程结束")
        self._window.highlight_calibrate(False)

    @Slot(str)
    def _on_error_occurred(self, error_msg: str) -> None:
        """Handle error from engine."""
        self._window.show_error_dialog("自动化错误", error_msg)

    @Slot()
    def _on_capture_failed(self) -> None:
        """Handle capture failure (Spec 11.2)."""
        action, _ = self._window.show_capture_error_dialog()

        if action == "retry":
            # Retry by restarting (user needs to click Start again)
            self._logger.info("用户选择重试")
        else:
            # Close - already stopped
            self._logger.info("用户选择关闭")

    @Slot()
    def _on_message_changed_during_pause(self) -> None:
        """Handle message change detection during pause (Spec 10.2)."""
        self._window.show_message_changed_dialog()

    @Slot(CalibrationStats)
    def _on_calibration_completed(self, stats: CalibrationStats) -> None:
        """Handle calibration completion."""
        self._window.set_recommended_threshold(stats.th_rec)

        if stats.warning:
            self._window.show_error_dialog(
                "校准警告",
                f"推荐阈值: {stats.th_rec:.4f}\n\n警告: {stats.warning}",
            )


def create_application() -> tuple[QApplication, MainWindow, ApplicationController]:
    """Create and wire up the complete application.

    Returns:
        Tuple of (QApplication, MainWindow, ApplicationController)
    """
    import sys

    from app.core.os_adapter import IS_WINDOWS

    # DPI setup must happen before QApplication
    dpi_warning = ""
    if IS_WINDOWS:
        from app.core.os_adapter.win_dpi import setup_dpi_awareness
        success, dpi_warning = setup_dpi_awareness()

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("QueueSend")
    app.setApplicationVersion("1.1.0")
    app.setOrganizationName("QueueSend")

    # Create window and controller
    window = MainWindow()
    controller = ApplicationController(window)

    # Show DPI warning if needed
    if dpi_warning:
        window.set_dpi_warning(dpi_warning)

    return app, window, controller

