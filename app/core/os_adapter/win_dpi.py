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
def _log_debug(location: str, message: str, data: dict, hypothesis_id: str):
    import time
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
    try:
        # Try the modern API first (Windows 10 1703+)
        user32 = ctypes.windll.user32

        # #region agent log
        # Log DPI awareness BEFORE setting
        try:
            current_ctx = user32.GetThreadDpiAwarenessContext()
            current_awareness = user32.GetAwarenessFromDpiAwarenessContext(current_ctx)
            _log_debug("win_dpi.py:setup_dpi_awareness:before", "DPI awareness before SetProcessDpiAwarenessContext", {"current_awareness": current_awareness}, "A")
        except Exception as e:
            _log_debug("win_dpi.py:setup_dpi_awareness:before", "Failed to get current DPI awareness", {"error": str(e)}, "A")
        # #endregion

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
        error_code_after = ctypes.windll.kernel32.GetLastError()
        _log_debug("win_dpi.py:setup_dpi_awareness:api_call", "SetProcessDpiAwarenessContext result", {"result": result, "error_code": error_code_after, "requested_context": DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2}, "A")
        # #endregion

        if result:
            # #region agent log
            # Verify DPI awareness was actually set
            try:
                new_ctx = user32.GetThreadDpiAwarenessContext()
                new_awareness = user32.GetAwarenessFromDpiAwarenessContext(new_ctx)
                system_dpi = user32.GetDpiForSystem()
                _log_debug("win_dpi.py:setup_dpi_awareness:success", "DPI awareness after successful set", {"new_awareness": new_awareness, "system_dpi": system_dpi}, "A")
            except Exception as e:
                _log_debug("win_dpi.py:setup_dpi_awareness:success", "Failed to verify DPI awareness", {"error": str(e)}, "A")
            # #endregion
            # Success
            return True, ""

        # Check why it failed
        error_code = ctypes.windll.kernel32.GetLastError()

        if error_code == ERROR_ACCESS_DENIED:
            # Already set - this is fine
            # This happens when manifest sets DPI awareness or
            # when called multiple times
            # #region agent log
            try:
                existing_ctx = user32.GetThreadDpiAwarenessContext()
                existing_awareness = user32.GetAwarenessFromDpiAwarenessContext(existing_ctx)
                _log_debug("win_dpi.py:setup_dpi_awareness:already_set", "DPI already set (ACCESS_DENIED)", {"existing_awareness": existing_awareness}, "A")
            except Exception as e:
                _log_debug("win_dpi.py:setup_dpi_awareness:already_set", "Failed to get existing DPI awareness", {"error": str(e)}, "A")
            # #endregion
            return True, ""

        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:failed", "SetProcessDpiAwarenessContext failed", {"error_code": error_code}, "A")
        # #endregion

        # Actual failure
        return False, (
            "⚠️ DPI感知设置失败,坐标可能偏移。"
            "建议在100%缩放下运行或重启应用"
        )

    except AttributeError:
        # API not available (older Windows or non-Windows)
        # #region agent log
        _log_debug("win_dpi.py:setup_dpi_awareness:fallback", "Modern API not available, trying shcore", {}, "A")
        # #endregion
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
        _log_debug("win_dpi.py:setup_dpi_awareness:exception", "Exception during DPI setup", {"error": str(e)}, "A")
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


