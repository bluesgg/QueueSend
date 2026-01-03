"""Global constants as defined in the Executable Specification Section 1."""

from typing import Final

# Timing constants
T_COUNTDOWN_SEC: Final[float] = 2.0
"""Start后倒计时秒数"""

T_COOL_SEC: Final[float] = 1.0
"""每条消息发送后冷却秒数"""

SAMPLE_HZ: Final[float] = 1.0
"""ROI采样频率 (1 FPS)"""

# Detection thresholds
HOLD_HITS_REQUIRED: Final[int] = 2
"""连续命中次数要求"""

TH_HOLD_DEFAULT: Final[float] = 0.02
"""未校准前阈值兜底值"""

TH_HOLD_MIN: Final[float] = 0.005
"""校准阈值最小值"""

TH_HOLD_MAX: Final[float] = 0.2
"""校准阈值最大值"""

# Calibration settings
CALIB_FRAMES_MIN: Final[int] = 5
"""阈值校准帧数区间下限"""

CALIB_FRAMES_MAX: Final[int] = 10
"""阈值校准帧数区间上限"""

CALIB_FRAMES_DEFAULT: Final[int] = 8
"""阈值校准帧数默认值"""

CALIB_INTERVAL_MS: Final[int] = 150
"""校准采样间隔毫秒 (100-200ms recommended)"""

# Error handling
CAPTURE_RETRY_N: Final[int] = 3
"""截图失败重试次数"""

CAPTURE_RETRY_INTERVAL_MS: Final[int] = 500
"""截图重试间隔毫秒"""

# UI constants
LOG_BUFFER_SIZE: Final[int] = 200
"""日志环形缓冲最大条数"""

PANEL_MARGIN_PX: Final[int] = 12
"""运行面板边距 (逻辑像素)"""

PANEL_MARGIN_TOLERANCE_PX: Final[int] = 2
"""运行面板边距容差 (±2px)"""

# Grayscale conversion weights (ITU-R BT.601)
GRAY_WEIGHT_R: Final[float] = 0.299
GRAY_WEIGHT_G: Final[float] = 0.587
GRAY_WEIGHT_B: Final[float] = 0.114


