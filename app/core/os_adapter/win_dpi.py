"""Windows DPI awareness setup.

MUST be called BEFORE Qt/QApplication initialization to prevent
coordinate scaling issues on high-DPI displays.

See Executable Spec Section 2.3 for requirements.
"""

import ctypes
import json
import time
from typing import Final

# Windows API constants
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2: Final[int] = -4
ERROR_ACCESS_DENIED: Final[int] = 5

# #region agent log
_DEBUG_LOG_PATH = r"e:\projects\QueueSend\.cursor\debug.log"
def _log_debug(location: str, message: str, data: dict, hypothesis_id: str):
    entry = {"location": location, "message": message, "data": data, "timestamp": int(time.time()*1000), "sessionId": "debug-session", "hypothesisId": hypothesis_id}
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
    _log_debug("win_dpi.py:setup_dpi_awareness:entry", "Function entry", {}, "A")
    # #endregion

    # NOTE: We use SetProcessDpiAwareness (shcore) instead of 
    # SetProcessDpiAwarenessContext (user32) because the latter causes
    # crashes in mss.grab() when using Per-Monitor Aware V2 mode.
    # The shcore API is compatible with mss and still provides proper
    # DPI awareness for coordinate handling.

    try:
        # Use shcore.SetProcessDpiAwareness (Windows 8.1+)
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        shcore = ctypes.windll.shcore
        
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:using_shcore", "Using SetProcessDpiAwareness API (compatible with mss)", {}, "A")
        # #endregion
        
        result = shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:shcore_result", "SetProcessDpiAwareness result", {"result": result}, "A")
        # #endregion
        
        # result is HRESULT: S_OK (0) = success, E_ACCESSDENIED = already set
        if result == 0:
            return True, ""
        elif result == -2147024891:  # E_ACCESSDENIED (0x80070005)
            # Already set - this is fine
            # #region agent log
            _log_debug("win_dpi.py:setup_dpi_awareness:already_set", "DPI already set (E_ACCESSDENIED)", {}, "A")
            # #endregion
            return True, ""
        else:
            # Check with GetLastError for more info
            error_code = ctypes.windll.kernel32.GetLastError()
            # #region agent log
            _log_debug("win_dpi.py:setup_dpi_awareness:shcore_error", "SetProcessDpiAwareness returned non-zero", {"result": result, "error_code": error_code}, "A")
            # #endregion
            
            if error_code == ERROR_ACCESS_DENIED:
                return True, ""
            
            return False, (
                "⚠️ DPI感知设置失败,坐标可能偏移。"
                "建议在100%缩放下运行或重启应用"
            )
            
    except AttributeError:
        # shcore.SetProcessDpiAwareness not available (Windows 7)
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:no_shcore", "shcore API not available, trying user32", {}, "A")
        # #endregion
        try:
            # Fallback to user32.SetProcessDPIAware (Windows Vista+)
            # This only sets system DPI awareness, not per-monitor
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return True, ""
        except Exception:
            return False, (
                "⚠️ DPI感知设置失败,坐标可能偏移。"
                "建议在100%缩放下运行或重启应用"
            )

    except Exception as e:
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:exception", "Unexpected exception", {"error": str(e), "type": type(e).__name__}, "A")
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


