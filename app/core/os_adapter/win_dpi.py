"""Windows DPI awareness setup.

MUST be called BEFORE Qt/QApplication initialization to prevent
coordinate scaling issues on high-DPI displays.

See Executable Spec Section 2.3 for requirements.
"""

import ctypes
import json
from typing import Final

# Windows API constants
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2: Final[int] = -4
ERROR_ACCESS_DENIED: Final[int] = 5

# #region agent log
_DEBUG_LOG_PATH = r"e:\projects\QueueSend\.cursor\debug.log"
def _log_debug(location: str, message: str, data: dict):
    import time
    entry = {"location": location, "message": message, "data": data, "timestamp": int(time.time()*1000)}
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except: pass
# #endregion


def setup_dpi_awareness() -> tuple[bool, str]:
    """Set Per-Monitor DPI awareness for the current process.

    This function MUST be called before QApplication is created.

    Returns:
        Tuple of (success, warning_message).
        - (True, "") if setup succeeded or was already set
        - (False, warning_message) if setup truly failed

    The warning message (if any) should be displayed in the UI as
    a dismissible yellow banner per Spec Section 2.3.
    """
    # #region agent log
    _log_debug("win_dpi.py:setup_dpi_awareness:entry", "Function entry", {})
    # #endregion
    try:
        # Try the modern API first (Windows 10 1703+)
        user32 = ctypes.windll.user32

        # DPI_AWARENESS_CONTEXT is a HANDLE type (pointer-sized integer)
        # We must use c_void_p to pass the correct type to the API
        DPI_AWARENESS_CONTEXT = ctypes.c_void_p
        
        # Set up proper argument types for the API call
        user32.SetProcessDpiAwarenessContext.argtypes = [DPI_AWARENESS_CONTEXT]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool

        # SetProcessDpiAwarenessContext returns BOOL
        result = user32.SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )

        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:api_result", "API call completed", {"result": result})
        # #endregion

        if result:
            # Success
            return True, ""

        # Check why it failed
        error_code = ctypes.windll.kernel32.GetLastError()

        if error_code == ERROR_ACCESS_DENIED:
            # Already set - this is fine
            # This happens when manifest sets DPI awareness or
            # when called multiple times
            return True, ""

        # Actual failure
        return False, (
            "⚠️ DPI感知设置失败,坐标可能偏移。"
            "建议在100%缩放下运行或重启应用"
        )

    except AttributeError as e:
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:attr_error", "AttributeError - API not available", {"error": str(e)})
        # #endregion
        # API not available (older Windows or non-Windows)
        try:
            # Fallback to older API (Windows 8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            return True, ""
        except Exception:
            return False, (
                "⚠️ DPI感知设置失败,坐标可能偏移。"
                "建议在100%缩放下运行或重启应用"
            )

    except Exception as e:
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:exception", "Unexpected exception", {"error": str(e), "type": type(e).__name__})
        # #endregion
        return False, f"⚠️ DPI设置异常: {e}"


def get_dpi_scale_factor() -> float:
    """Get the DPI scale factor for the primary monitor.

    Returns:
        Scale factor (1.0 = 100%, 1.25 = 125%, 1.5 = 150%, etc.)
    """
    try:
        user32 = ctypes.windll.user32
        # Get DPI for primary monitor
        dpi = user32.GetDpiForSystem()
        return dpi / 96.0  # 96 DPI = 100%
    except Exception:
        return 1.0


