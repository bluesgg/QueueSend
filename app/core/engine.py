"""Automation engine with state machine.

Implements the core automation logic including:
- State machine (Idle/Countdown/Sending/Cooling/WaitingHold/Paused)
- Message processing loop
- Pause/Resume/Stop controls

See Executable Spec Sections 6, 9, 10 for requirements.
"""

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .capture import CaptureError, capture_roi_gray
from .constants import (
    HOLD_HITS_REQUIRED,
    SAMPLE_HZ,
    T_COOL_SEC,
    T_COUNTDOWN_SEC,
    TH_HOLD_DEFAULT,
)
from .diff import calculate_diff, calibrate_threshold
from .logging import Logger, get_logger
from .model import CalibrationConfig, CalibrationStats, Point, ROI, State
from .os_adapter.input_inject import click_point, paste_text


class AutomationWorker(QObject):
    """Worker that runs the automation loop in a separate thread.

    Implements the message processing loop from Spec Section 6.1.
    """

    # Signals for state updates
    state_changed = Signal(State)
    progress_updated = Signal(int, int)  # current (1-based), total
    countdown_tick = Signal(float)  # remaining seconds
    sampling_update = Signal(float, int)  # diff, hold_hits
    message_started = Signal(int, str)  # index (1-based), content
    automation_finished = Signal()
    error_occurred = Signal(str)  # error message
    capture_failed = Signal()  # trigger capture error dialog

    def __init__(
        self,
        messages: list[str],
        config: CalibrationConfig,
        logger: Optional[Logger] = None,
    ) -> None:
        """Initialize the worker.

        Args:
            messages: List of messages to send (already filtered)
            config: Calibration configuration
            logger: Logger instance (uses global if None)
        """
        super().__init__()

        self._messages = messages
        self._config = config
        self._logger = logger or get_logger()

        # State
        self._state = State.Idle
        self._current_idx = 0
        self._frame_t0: Optional[bytes] = None  # Stored as bytes for thread safety
        self._hold_hits = 0
        self._th_hold = config.th_hold

        # Control events
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()

        # For pause/resume
        self._paused_state: Optional[State] = None
        self._messages_snapshot: Optional[list[str]] = None

        # Callback for message change detection (set by controller)
        self._check_messages_changed: Optional[Callable[[], bool]] = None

    @property
    def state(self) -> State:
        """Current state."""
        return self._state

    @property
    def messages(self) -> list[str]:
        """Message list."""
        return self._messages

    def set_message_change_checker(
        self,
        checker: Callable[[], bool],
    ) -> None:
        """Set callback to check if messages changed during pause.

        Args:
            checker: Function that returns True if messages changed
        """
        self._check_messages_changed = checker

    def _set_state(self, new_state: State) -> None:
        """Update state and emit signal."""
        old_state = self._state
        self._state = new_state
        self._logger.state_change(old_state.name, new_state.name)
        self.state_changed.emit(new_state)

    def request_pause(self) -> None:
        """Request pause (thread-safe)."""
        self._pause_event.set()

    def request_resume(self) -> None:
        """Request resume (thread-safe)."""
        self._pause_event.clear()
        self._resume_event.set()

    def request_stop(self) -> None:
        """Request stop (thread-safe)."""
        self._stop_event.set()
        self._pause_event.clear()
        self._resume_event.set()  # Unblock if paused

    def run(self) -> None:
        """Run the automation loop.

        This is called in the worker thread.
        """
        try:
            self._run_automation()
        except CaptureError as e:
            self._logger.error(f"截图失败: {e}")
            self.capture_failed.emit()
        except Exception as e:
            self._logger.error(f"自动化错误: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self._set_state(State.Idle)
            self.automation_finished.emit()

    def _run_automation(self) -> None:
        """Main automation loop implementation."""
        messages = self._messages
        n = len(messages)
        roi = self._config.roi
        input_point = self._config.input_point
        send_point = self._config.send_point

        self._logger.info(f"开始自动化: {n}条消息")

        # Countdown phase (Spec 3.1)
        self._set_state(State.Countdown)
        start_time = datetime.now()
        self._logger.info(f"Start时间: {start_time.strftime('%H:%M:%S.%f')[:-3]}")

        if not self._countdown(T_COUNTDOWN_SEC):
            return  # Stopped during countdown

        # Process each message
        for idx in range(n):
            if self._stop_event.is_set():
                self._logger.info("用户停止")
                break

            # Update progress (1-based display)
            self._current_idx = idx
            self._logger.set_progress(idx + 1, n)
            self.progress_updated.emit(idx + 1, n)

            # Log message content
            self._logger.message_content(idx + 1, messages[idx])
            self.message_started.emit(idx + 1, messages[idx])

            # === Sending phase (Spec 6.1) ===
            self._set_state(State.Sending)

            # Check for pause/stop
            if self._handle_pause_stop():
                return

            # 1. Click input point
            first_click_time = datetime.now()
            if idx == 0:
                self._logger.info(
                    f"第一次点击输入点时间: {first_click_time.strftime('%H:%M:%S.%f')[:-3]}"
                )
                delta = (first_click_time - start_time).total_seconds()
                self._logger.info(f"T1-T0 = {delta:.3f}秒")

            click_point(input_point)
            self._logger.debug(f"点击输入点: ({input_point.x}, {input_point.y})")
            time.sleep(0.1)  # Small delay after click

            # 2. Paste message
            if not paste_text(messages[idx]):
                self._logger.warning("粘贴可能失败,继续执行")
            self._logger.debug("粘贴消息完成")
            time.sleep(0.1)  # Small delay after paste

            # 3. Click send button
            click_point(send_point)
            self._logger.debug(f"点击发送点: ({send_point.x}, {send_point.y})")

            # === Cooling phase (Spec 6.1 step 4) ===
            self._set_state(State.Cooling)

            if self._handle_pause_stop():
                return

            time.sleep(T_COOL_SEC)

            # === Capture reference frame (Spec 6.1 step 5) ===
            frame_t0 = capture_roi_gray(roi)
            self._hold_hits = 0
            self._logger.info("采集frame_t0")

            # === WaitingHold phase (Spec 6.1 steps 6-8) ===
            self._set_state(State.WaitingHold)

            while True:
                if self._stop_event.is_set():
                    self._logger.info("用户停止")
                    return

                # Handle pause
                if self._pause_event.is_set():
                    # Save state for resume
                    self._paused_state = State.WaitingHold
                    if not self._handle_pause(frame_t0):
                        return  # Messages changed or stopped

                # Sample at SAMPLE_HZ (Spec 6.1 step 6)
                frame_t = capture_roi_gray(roi)
                diff = calculate_diff(frame_t, frame_t0, roi)

                # Hold hits logic (Spec 7.2)
                if diff >= self._th_hold:
                    self._hold_hits += 1
                else:
                    self._hold_hits = 0  # Reset on miss

                # Log and emit (Spec 12)
                self._logger.sampling(diff, self._hold_hits)
                self.sampling_update.emit(diff, self._hold_hits)

                # Check if passed (Spec 6.1 step 7)
                if self._hold_hits >= HOLD_HITS_REQUIRED:
                    self._logger.info(
                        f"连续{HOLD_HITS_REQUIRED}次命中,进入下一条"
                    )
                    break

                # Wait for next sample (Spec 6.1 step 8 - infinite wait)
                time.sleep(1.0 / SAMPLE_HZ)

        # All messages processed
        self._logger.info("自动化完成")

    def _countdown(self, seconds: float) -> bool:
        """Run countdown timer.

        Args:
            seconds: Total countdown seconds

        Returns:
            True if countdown completed, False if stopped
        """
        interval = 0.1  # Update every 100ms
        remaining = seconds

        while remaining > 0:
            if self._stop_event.is_set():
                return False

            self.countdown_tick.emit(remaining)
            time.sleep(interval)
            remaining -= interval

        self.countdown_tick.emit(0.0)
        return True

    def _handle_pause_stop(self) -> bool:
        """Check for pause/stop and handle.

        Returns:
            True if should exit (stopped), False to continue
        """
        if self._stop_event.is_set():
            return True

        if self._pause_event.is_set():
            if not self._handle_pause(None):
                return True

        return False

    def _handle_pause(
        self,
        frame_t0: Optional[bytes],
    ) -> bool:
        """Handle pause state.

        Args:
            frame_t0: Current reference frame (preserved during pause)

        Returns:
            True to continue, False if should stop (messages changed or stopped)
        """
        self._paused_state = self._state
        saved_hold_hits = self._hold_hits
        self._set_state(State.Paused)

        self._logger.info("暂停")

        # Wait for resume or stop
        while self._pause_event.is_set():
            if self._stop_event.is_set():
                self._logger.info("暂停期间停止")
                return False

            self._resume_event.wait(timeout=0.1)

        self._resume_event.clear()

        # Check if stopped while waiting
        if self._stop_event.is_set():
            return False

        # Check for message changes (Spec 10.2)
        if self._check_messages_changed and self._check_messages_changed():
            self._logger.warning("检测到消息列表已修改")
            return False

        # Resume - restore state
        self._hold_hits = saved_hold_hits
        self._logger.info(f"继续 (恢复到 {self._paused_state.name})")
        self._set_state(self._paused_state)

        return True

    def get_frozen_state(self) -> dict:
        """Get current state for pause freeze (Spec 10.1).

        Returns:
            Dictionary with frozen state variables
        """
        return {
            "state": self._state,
            "current_idx": self._current_idx,
            "hold_hits": self._hold_hits,
        }


class AutomationEngine(QObject):
    """Main automation engine controller.

    Manages the worker thread and provides the interface for UI.
    """

    # Signals (forwarded from worker)
    state_changed = Signal(State)
    progress_updated = Signal(int, int)
    countdown_tick = Signal(float)
    sampling_update = Signal(float, int)
    automation_finished = Signal()
    error_occurred = Signal(str)
    capture_failed = Signal()
    message_changed_during_pause = Signal()

    # Calibration signals
    calibration_completed = Signal(CalibrationStats)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Initialize the engine."""
        super().__init__(parent)

        self._worker: Optional[AutomationWorker] = None
        self._thread: Optional[QThread] = None
        self._logger = get_logger()
        self._config: Optional[CalibrationConfig] = None
        self._messages: list[str] = []
        self._messages_snapshot: Optional[list[str]] = None

        # Callback for message change detection
        self._get_current_messages: Optional[Callable[[], list[str]]] = None

    @property
    def is_running(self) -> bool:
        """Check if automation is currently running."""
        return self._thread is not None and self._thread.isRunning()

    @property
    def state(self) -> State:
        """Get current state."""
        if self._worker:
            return self._worker.state
        return State.Idle

    def set_message_getter(
        self,
        getter: Callable[[], list[str]],
    ) -> None:
        """Set callback to get current messages from UI.

        Args:
            getter: Function that returns current message list
        """
        self._get_current_messages = getter

    def start(
        self,
        messages: list[str],
        config: CalibrationConfig,
    ) -> bool:
        """Start automation.

        Args:
            messages: List of messages to send
            config: Calibration configuration

        Returns:
            True if started, False if already running or invalid
        """
        if self.is_running:
            self._logger.warning("自动化已在运行中")
            return False

        if not messages:
            self._logger.error("消息列表为空")
            return False

        self._messages = messages
        self._config = config
        self._messages_snapshot = messages.copy()

        # Create worker
        self._worker = AutomationWorker(messages, config, self._logger)
        self._worker.set_message_change_checker(self._check_messages_changed)

        # Connect signals
        self._worker.state_changed.connect(self.state_changed.emit)
        self._worker.progress_updated.connect(self.progress_updated.emit)
        self._worker.countdown_tick.connect(self.countdown_tick.emit)
        self._worker.sampling_update.connect(self.sampling_update.emit)
        self._worker.automation_finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.capture_failed.connect(self.capture_failed.emit)

        # Create thread
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._cleanup_thread)

        # Start
        self._thread.start()
        return True

    def pause(self) -> None:
        """Pause automation."""
        if self._worker:
            # Save snapshot for change detection
            if self._get_current_messages:
                self._messages_snapshot = self._get_current_messages()
            self._worker.request_pause()

    def resume(self) -> None:
        """Resume automation."""
        if self._worker:
            # Check for message changes before resuming
            if self._check_messages_changed():
                self._logger.warning("消息列表已修改,自动化停止")
                self.message_changed_during_pause.emit()
                self.stop()
                return
            self._worker.request_resume()

    def stop(self) -> None:
        """Stop automation."""
        if self._worker:
            self._worker.request_stop()

    def _check_messages_changed(self) -> bool:
        """Check if messages changed since pause."""
        if not self._get_current_messages or not self._messages_snapshot:
            return False
        current = self._get_current_messages()
        return current != self._messages_snapshot

    def _on_finished(self) -> None:
        """Handle worker finished."""
        self.automation_finished.emit()

    def _cleanup_thread(self) -> None:
        """Clean up thread resources."""
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None

    def calibrate_threshold(self, roi: ROI) -> CalibrationStats:
        """Run threshold calibration.

        Args:
            roi: ROI to calibrate

        Returns:
            CalibrationStats with results
        """
        self._logger.info("开始阈值校准")
        stats = calibrate_threshold(roi)
        self._logger.calibration_result(
            stats.mu, stats.sigma, stats.th_rec, stats.warning
        )
        self.calibration_completed.emit(stats)
        return stats

