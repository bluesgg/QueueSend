"""Thread-safe logging system with circular buffer.

Provides a logging interface for the automation engine that:
- Uses a circular buffer (max 200 entries) to prevent memory growth
- Is thread-safe for worker thread -> UI thread communication
- Formats log entries with timestamps and context
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from threading import Lock
from typing import Any, Callable, Optional, Union

from .constants import LOG_BUFFER_SIZE


class LogLevel(Enum):
    """Log entry severity levels."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class LogEntry:
    """A single log entry.

    Attributes:
        timestamp: When the entry was created
        level: Severity level
        message: Log message content
        state: Current automation state (if applicable)
        progress: Current progress as (i, N) tuple (if applicable)
        diff: Current diff value (if applicable)
        hold_hits: Current hold hits count (if applicable)
    """

    timestamp: datetime
    level: LogLevel
    message: str
    state: Optional[str] = None
    progress: Optional[tuple[int, int]] = None
    diff: Optional[float] = None
    hold_hits: Optional[int] = None

    def format(self) -> str:
        """Format the log entry as a string."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        parts = [f"[{time_str}]"]

        if self.state:
            parts.append(f"[{self.state}]")

        if self.progress:
            i, n = self.progress
            parts.append(f"[{i}/{n}]")

        parts.append(self.message)

        if self.diff is not None:
            parts.append(f"diff={self.diff:.4f}")

        if self.hold_hits is not None:
            parts.append(f"hold_hits={self.hold_hits}")

        return " ".join(parts)


@dataclass
class LogBuffer:
    """Thread-safe circular buffer for log entries.

    Uses a deque with maxlen to automatically discard old entries.
    Thread-safe for multiple writers and readers.
    """

    max_size: int = LOG_BUFFER_SIZE
    _buffer: deque[LogEntry] = field(default_factory=lambda: deque(maxlen=LOG_BUFFER_SIZE))
    _lock: Lock = field(default_factory=Lock)
    _listeners: list[Callable[[LogEntry], None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reinitialize buffer with correct maxlen if max_size differs."""
        if self._buffer.maxlen != self.max_size:
            self._buffer = deque(maxlen=self.max_size)

    def add(self, entry: LogEntry) -> None:
        """Add a log entry to the buffer (thread-safe)."""
        with self._lock:
            self._buffer.append(entry)

        # Notify listeners (outside lock to prevent deadlock)
        for listener in self._listeners:
            try:
                listener(entry)
            except Exception:
                pass  # Don't let listener errors affect logging

    def get_all(self) -> list[LogEntry]:
        """Get all entries in the buffer (thread-safe)."""
        with self._lock:
            return list(self._buffer)

    def get_recent(self, count: int) -> list[LogEntry]:
        """Get the most recent N entries (thread-safe)."""
        with self._lock:
            if count >= len(self._buffer):
                return list(self._buffer)
            return list(self._buffer)[-count:]

    def clear(self) -> None:
        """Clear all entries (thread-safe)."""
        with self._lock:
            self._buffer.clear()

    def add_listener(self, callback: Callable[[LogEntry], None]) -> None:
        """Add a listener to be notified of new entries."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def __len__(self) -> int:
        """Return current buffer size."""
        with self._lock:
            return len(self._buffer)


class Logger:
    """Main logging interface for the automation engine.

    Provides convenience methods for logging at different levels
    with optional context (state, progress, diff, hold_hits).
    """

    def __init__(self, buffer: Optional[LogBuffer] = None) -> None:
        """Initialize logger with optional existing buffer."""
        self._buffer = buffer or LogBuffer()
        self._current_state: Optional[str] = None
        self._current_progress: Optional[tuple[int, int]] = None

    @property
    def buffer(self) -> LogBuffer:
        """Access the underlying log buffer."""
        return self._buffer

    def set_state(self, state: str) -> None:
        """Set the current state for subsequent log entries."""
        self._current_state = state

    def set_progress(self, current: int, total: int) -> None:
        """Set the current progress for subsequent log entries.

        Args:
            current: Current message index (1-based for display)
            total: Total message count
        """
        self._current_progress = (current, total)

    def clear_context(self) -> None:
        """Clear current state and progress context."""
        self._current_state = None
        self._current_progress = None

    def _log(
        self,
        level: LogLevel,
        message: str,
        diff: Optional[float] = None,
        hold_hits: Optional[int] = None,
    ) -> LogEntry:
        """Internal logging method."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            state=self._current_state,
            progress=self._current_progress,
            diff=diff,
            hold_hits=hold_hits,
        )
        self._buffer.add(entry)
        return entry

    def debug(self, message: str, **kwargs: Any) -> LogEntry:
        """Log a debug message."""
        return self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> LogEntry:
        """Log an info message."""
        return self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> LogEntry:
        """Log a warning message."""
        return self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> LogEntry:
        """Log an error message."""
        return self._log(LogLevel.ERROR, message, **kwargs)

    def state_change(self, old_state: str, new_state: str) -> LogEntry:
        """Log a state transition."""
        self.set_state(new_state)
        return self.info(f"状态变化: {old_state} → {new_state}")

    def sampling(self, diff: float, hold_hits: int) -> LogEntry:
        """Log a sampling result during WaitingHold."""
        return self.info("采样", diff=diff, hold_hits=hold_hits)

    def message_content(self, index: int, content: str) -> LogEntry:
        """Log message content for debugging."""
        # Truncate very long messages for display
        display_content = content if len(content) <= 100 else content[:97] + "..."
        return self.debug(f"消息内容[{index}]: {display_content}")

    def calibration_result(
        self,
        mu: float,
        sigma: float,
        th_rec: float,
        warning: Optional[str] = None,
    ) -> LogEntry:
        """Log calibration results."""
        msg = f"校准完成: μ={mu:.4f}, σ={sigma:.4f}, 推荐阈值={th_rec:.4f}"
        if warning:
            msg += f" (警告: {warning})"
        return self.info(msg)


# Global logger instance for convenience
_global_logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Get the global logger instance, creating one if needed."""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger()
    return _global_logger


def set_logger(logger: Logger) -> None:
    """Set the global logger instance."""
    global _global_logger
    _global_logger = logger

