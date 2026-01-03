"""QueueSend application entry point.

This module initializes the application with proper DPI awareness
(on Windows) and permission checks (on macOS) before creating the UI.

IMPORTANT: DPI awareness must be set BEFORE QApplication is created.
"""

import sys
import json
from typing import Optional

from app.core.os_adapter import IS_MACOS, IS_WINDOWS

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


def setup_platform() -> tuple[bool, str]:
    """Perform platform-specific setup before Qt initialization.

    Returns:
        Tuple of (success, warning_message).
        If success is False, warning_message contains details.
    """
    if IS_WINDOWS:
        from app.core.os_adapter.win_dpi import setup_dpi_awareness
        return setup_dpi_awareness()
    elif IS_MACOS:
        # macOS permissions are checked after UI is created
        # to show proper guidance dialogs
        return True, ""
    else:
        return True, ""


def check_macos_requirements() -> tuple[bool, Optional[str]]:
    """Check macOS-specific requirements after Qt is initialized.

    Returns:
        Tuple of (ready, error_message).
        - (True, None) if ready to run
        - (False, message) if requirements not met
    """
    if not IS_MACOS:
        return True, None

    from app.core.os_adapter.mac_permissions import check_permissions
    from app.core.os_adapter.validation import check_macos_display_limit

    # Check display limit
    display_result = check_macos_display_limit()
    if not display_result.valid:
        return False, display_result.errors[0]

    # Check permissions
    perm_status = check_permissions()
    if not perm_status.all_granted:
        return False, perm_status.guidance

    return True, None


def main() -> int:
    """Application entry point.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # #region agent log
    _log_debug("main.py:main:entry", "Application starting", {"is_windows": IS_WINDOWS, "is_macos": IS_MACOS})
    # #endregion

    # Platform setup MUST happen before QApplication
    dpi_success, dpi_warning = setup_platform()

    # #region agent log
    _log_debug("main.py:main:after_platform_setup", "Platform setup complete", {"dpi_success": dpi_success, "dpi_warning": dpi_warning})
    # #endregion

    # Now we can import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    # #region agent log
    _log_debug("main.py:main:creating_qapp", "Creating QApplication", {})
    # #endregion

    app = QApplication(sys.argv)
    app.setApplicationName("QueueSend")
    app.setApplicationVersion("1.1.0")
    app.setOrganizationName("QueueSend")

    # #region agent log
    _log_debug("main.py:main:qapp_created", "QApplication created successfully", {})
    # #endregion

    # Initialize clipboard helper on main thread (required for worker thread clipboard access)
    from app.core.os_adapter.input_inject import init_clipboard_helper
    init_clipboard_helper()

    # Check macOS requirements
    macos_ready, macos_error = check_macos_requirements()

    if macos_error:
        QMessageBox.critical(
            None,
            "无法启动",
            macos_error,
            QMessageBox.StandardButton.Ok,
        )
        return 1

    # Create main window with controller
    from app.controller import ApplicationController
    from app.ui import MainWindow

    # #region agent log
    _log_debug("main.py:main:creating_window", "Creating MainWindow", {})
    # #endregion

    window = MainWindow()
    controller = ApplicationController(window)

    # #region agent log
    _log_debug("main.py:main:window_created", "MainWindow and controller created", {})
    # #endregion

    # Show DPI warning if needed
    if dpi_warning:
        window.set_dpi_warning(dpi_warning)

    # Show window
    window.show()

    # #region agent log
    _log_debug("main.py:main:window_shown", "Window shown, entering event loop", {})
    # #endregion

    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
