"""Common UI widgets for QueueSend.

Provides reusable UI components used across the application.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WarningBanner(QFrame):
    """A dismissible warning banner with yellow background.

    Used for DPI warnings and runtime warnings per Spec Section 2.3.
    """

    dismissed = Signal()

    def __init__(
        self,
        message: str,
        dismissible: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the warning banner.

        Args:
            message: Warning message to display
            dismissible: Whether to show close button
            parent: Parent widget
        """
        super().__init__(parent)

        self.setAutoFillBackground(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        # Yellow background
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 243, 205))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(133, 100, 4))
        self.setPalette(palette)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # Warning icon and message
        self._label = QLabel(message)
        self._label.setWordWrap(True)
        layout.addWidget(self._label, 1)

        # Close button
        if dismissible:
            close_btn = QPushButton("×")
            close_btn.setFixedSize(24, 24)
            close_btn.setFlat(True)
            close_btn.clicked.connect(self._on_dismiss)
            layout.addWidget(close_btn)

    def _on_dismiss(self) -> None:
        """Handle dismiss button click."""
        self.hide()
        self.dismissed.emit()

    def set_message(self, message: str) -> None:
        """Update the warning message."""
        self._label.setText(message)


class FixedWarningBanner(QFrame):
    """A non-dismissible warning banner for runtime warnings.

    Shows "运行中请勿操作目标窗口" per Spec Section 3.2.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setAutoFillBackground(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        # Yellow background
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 243, 205))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(133, 100, 4))
        self.setPalette(palette)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        label = QLabel("⚠️ 运行中请勿操作目标窗口")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


class StatusIndicator(QWidget):
    """Status indicator showing current automation state."""

    # State to color mapping
    STATE_COLORS = {
        "Idle": QColor(128, 128, 128),       # Gray
        "Countdown": QColor(255, 193, 7),     # Yellow
        "Sending": QColor(0, 123, 255),       # Blue
        "Cooling": QColor(23, 162, 184),      # Cyan
        "WaitingHold": QColor(40, 167, 69),   # Green
        "Paused": QColor(255, 152, 0),        # Orange
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Status dot
        self._dot = QLabel("●")
        self._dot.setFixedWidth(20)
        layout.addWidget(self._dot)

        # Status text
        self._text = QLabel("Idle")
        layout.addWidget(self._text, 1)

        self.set_state("Idle")

    def set_state(self, state: str) -> None:
        """Update the displayed state.

        Args:
            state: State name (Idle, Countdown, Sending, etc.)
        """
        self._text.setText(state)
        color = self.STATE_COLORS.get(state, QColor(128, 128, 128))
        self._dot.setStyleSheet(f"color: {color.name()};")


class ProgressDisplay(QWidget):
    """Progress display showing i/N format."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("0/0")
        self._label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self._label)

    def set_progress(self, current: int, total: int) -> None:
        """Update progress display.

        Args:
            current: Current message index (1-based)
            total: Total message count
        """
        self._label.setText(f"{current}/{total}")


class CountdownDisplay(QWidget):
    """Countdown timer display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("0.0")
        self._label.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #ffc107;"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._hint = QLabel("即将开始...")
        self._hint.setStyleSheet("color: #666;")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint)

    def set_value(self, seconds: float) -> None:
        """Update countdown value.

        Args:
            seconds: Remaining seconds
        """
        self._label.setText(f"{seconds:.1f}")

    def show_countdown(self) -> None:
        """Show countdown UI."""
        self.show()

    def hide_countdown(self) -> None:
        """Hide countdown UI."""
        self.hide()


class ControlButtons(QWidget):
    """Control buttons for Pause/Resume/Stop."""

    pause_clicked = Signal()
    resume_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Pause button
        self._pause_btn = QPushButton("暂停")
        self._pause_btn.clicked.connect(self.pause_clicked.emit)
        layout.addWidget(self._pause_btn)

        # Resume button (hidden by default)
        self._resume_btn = QPushButton("继续")
        self._resume_btn.clicked.connect(self.resume_clicked.emit)
        self._resume_btn.hide()
        layout.addWidget(self._resume_btn)

        # Stop button
        self._stop_btn = QPushButton("停止")
        self._stop_btn.setStyleSheet("background-color: #dc3545; color: white;")
        self._stop_btn.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self._stop_btn)

    def set_paused(self, paused: bool) -> None:
        """Update button visibility based on paused state.

        Args:
            paused: Whether currently paused
        """
        self._pause_btn.setVisible(not paused)
        self._resume_btn.setVisible(paused)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all control buttons.

        Args:
            enabled: Whether buttons should be enabled
        """
        self._pause_btn.setEnabled(enabled)
        self._resume_btn.setEnabled(enabled)
        self._stop_btn.setEnabled(enabled)


class ThresholdInput(QWidget):
    """Threshold input with calibration button."""

    calibrate_clicked = Signal()
    value_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        from PySide6.QtWidgets import QDoubleSpinBox

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        layout.addWidget(QLabel("阈值:"))

        # Spin box
        self._spinbox = QDoubleSpinBox()
        self._spinbox.setRange(0.001, 0.5)
        self._spinbox.setDecimals(3)
        self._spinbox.setSingleStep(0.005)
        self._spinbox.setValue(0.02)
        self._spinbox.valueChanged.connect(self.value_changed.emit)
        layout.addWidget(self._spinbox)

        # Calibrate button
        self._calibrate_btn = QPushButton("校准")
        self._calibrate_btn.clicked.connect(self.calibrate_clicked.emit)
        layout.addWidget(self._calibrate_btn)

    def get_value(self) -> float:
        """Get current threshold value."""
        return self._spinbox.value()

    def set_value(self, value: float) -> None:
        """Set threshold value."""
        self._spinbox.setValue(value)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable input."""
        self._spinbox.setEnabled(enabled)
        self._calibrate_btn.setEnabled(enabled)

    def highlight_calibrate(self, highlight: bool) -> None:
        """Highlight calibrate button to suggest calibration."""
        if highlight:
            self._calibrate_btn.setStyleSheet(
                "background-color: #ffc107; font-weight: bold;"
            )
        else:
            self._calibrate_btn.setStyleSheet("")

