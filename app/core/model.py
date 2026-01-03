"""Core data models for QueueSend.

Defines data structures for coordinates, ROI, calibration config,
and state machine enums as specified in the TDD and Executable Spec.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Literal, Optional

from .constants import TH_HOLD_DEFAULT


class State(Enum):
    """Automation state machine states (Spec Section 9.1)."""

    Idle = auto()
    """未运行"""

    Countdown = auto()
    """倒计时阶段,不执行自动化"""

    Sending = auto()
    """执行点击/粘贴/发送"""

    Cooling = auto()
    """冷却等待"""

    WaitingHold = auto()
    """等待ROI变化满足条件"""

    Paused = auto()
    """暂停"""


class Event(Enum):
    """State machine events (Spec Section 9.3)."""

    EV_START = auto()
    """用户点击Start"""

    EV_COUNTDOWN_DONE = auto()
    """倒计时结束"""

    EV_SENT_STEP_DONE = auto()
    """Sending三步完成"""

    EV_COOL_DONE = auto()
    """冷却完成"""

    EV_HOLD_PASS = auto()
    """连续命中达标"""

    EV_PAUSE = auto()
    """用户点击Pause"""

    EV_RESUME = auto()
    """用户点击Resume"""

    EV_STOP = auto()
    """用户点击Stop"""

    EV_ERROR_FATAL = auto()
    """不可恢复错误,如权限缺失、连续截图失败"""

    EV_MSG_LIST_CHANGED = auto()
    """Resume时检测到消息列表变化"""


class ROIShape(Enum):
    """ROI shape types."""

    RECT = "rect"
    CIRCLE = "circle"


@dataclass(frozen=True)
class Point:
    """A point in virtual desktop coordinates.

    Attributes:
        x: X coordinate (may be negative on multi-monitor setups)
        y: Y coordinate (may be negative on multi-monitor setups)
    """

    x: int
    y: int

    def as_tuple(self) -> tuple[int, int]:
        """Return as (x, y) tuple."""
        return (self.x, self.y)


@dataclass(frozen=True)
class Rect:
    """A rectangle in virtual desktop coordinates.

    Attributes:
        x: Left edge X coordinate
        y: Top edge Y coordinate
        w: Width (must be > 0)
        h: Height (must be > 0)
    """

    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        """Right edge X coordinate."""
        return self.x + self.w

    @property
    def bottom(self) -> int:
        """Bottom edge Y coordinate."""
        return self.y + self.h

    @property
    def center(self) -> tuple[float, float]:
        """Center point (cx, cy)."""
        return (self.x + self.w / 2, self.y + self.h / 2)

    def contains_point(self, point: Point) -> bool:
        """Check if this rect contains the given point."""
        return (self.x <= point.x < self.right and
                self.y <= point.y < self.bottom)

    def is_valid(self) -> bool:
        """Check if rect has positive dimensions."""
        return self.w > 0 and self.h > 0


@dataclass(frozen=True)
class Circle:
    """A circle derived from a bounding rectangle.

    Generated as inscribed circle: cx=x+w/2, cy=y+h/2, r=min(w,h)/2

    Attributes:
        cx: Center X coordinate
        cy: Center Y coordinate
        r: Radius
    """

    cx: float
    cy: float
    r: float

    @classmethod
    def from_rect(cls, rect: Rect) -> "Circle":
        """Create inscribed circle from bounding rectangle (Spec 4.2)."""
        cx = rect.x + rect.w / 2
        cy = rect.y + rect.h / 2
        r = min(rect.w, rect.h) / 2
        return cls(cx=cx, cy=cy, r=r)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if point (x, y) is inside the circle."""
        return (x - self.cx) ** 2 + (y - self.cy) ** 2 <= self.r ** 2


@dataclass
class ROI:
    """Region of Interest for change detection.

    Attributes:
        shape: 'rect' or 'circle'
        rect: Bounding rectangle (always required)
        circle: Circle parameters (only for circle shape, derived from rect)
    """

    shape: ROIShape
    rect: Rect
    circle: Optional[Circle] = field(default=None)

    def __post_init__(self) -> None:
        """Auto-generate circle if shape is CIRCLE."""
        if self.shape == ROIShape.CIRCLE and self.circle is None:
            # Use object.__setattr__ since we want to allow this initialization
            object.__setattr__(self, 'circle', Circle.from_rect(self.rect))

    def is_valid(self) -> bool:
        """Check if ROI has valid dimensions."""
        return self.rect.is_valid()


@dataclass
class CalibrationConfig:
    """Calibration configuration for a single run.

    Attributes:
        roi: Region of interest for change detection
        input_point: Click point to grab focus
        send_point: Click point for send button
        th_hold: Change detection threshold
    """

    roi: ROI
    input_point: Point
    send_point: Point
    th_hold: float = TH_HOLD_DEFAULT

    def is_complete(self) -> bool:
        """Check if all calibration items are set and valid."""
        return (
            self.roi is not None and
            self.roi.is_valid() and
            self.input_point is not None and
            self.send_point is not None
        )


@dataclass
class VirtualDesktopInfo:
    """Information about the virtual desktop (all monitors combined).

    Attributes:
        left: Leftmost X coordinate (may be negative)
        top: Topmost Y coordinate (may be negative)
        width: Total width
        height: Total height
    """

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Rightmost X coordinate."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Bottommost Y coordinate."""
        return self.top + self.height

    def contains_point(self, point: Point) -> bool:
        """Check if point is within virtual desktop bounds."""
        return (self.left <= point.x < self.right and
                self.top <= point.y < self.bottom)

    def contains_rect(self, rect: Rect) -> bool:
        """Check if rect is entirely within virtual desktop bounds."""
        return (self.left <= rect.x and
                self.top <= rect.y and
                rect.right <= self.right and
                rect.bottom <= self.bottom)


@dataclass
class CalibrationStats:
    """Statistics from threshold calibration.

    Attributes:
        mu: Mean noise level
        sigma: Standard deviation of noise
        th_rec: Recommended threshold (clamp(mu + 3*sigma, 0.005, 0.2))
        di_values: Individual diff values from calibration frames
        warning: Optional warning message if noise is abnormal
    """

    mu: float
    sigma: float
    th_rec: float
    di_values: list[float]
    warning: Optional[str] = None


