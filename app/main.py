"""QueueSend application entry point.

This module initializes the application with proper DPI awareness
(on Windows) and permission checks (on macOS) before creating the UI.

IMPORTANT: DPI awareness must be set BEFORE QApplication is created.
"""

import sys
import faulthandler
from typing import Optional

# Enable faulthandler to catch segmentation faults and other low-level crashes
faulthandler.enable()
print(f"[INIT] faulthandler enabled - will catch segfaults", file=sys.stderr)

from app.core.os_adapter import IS_MACOS, IS_WINDOWS


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
    import traceback
    import threading
    
    # Install global exception hooks to catch ALL exceptions
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """Catch all uncaught exceptions in main thread."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow Ctrl+C to work normally
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        print(f"\n{'='*60}\nUNCAUGHT EXCEPTION 未捕获的异常 (主线程)\n{'='*60}", file=sys.stderr)
        print(f"Exception Type: {exc_type.__name__}", file=sys.stderr)
        print(f"Exception Value: {exc_value}", file=sys.stderr)
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
    
    def thread_exception_handler(args):
        """Catch all uncaught exceptions in other threads."""
        print(f"\n{'='*60}\nUNCAUGHT EXCEPTION 未捕获的异常 (线程: {args.thread.name})\n{'='*60}", file=sys.stderr)
        print(f"Exception Type: {args.exc_type.__name__}", file=sys.stderr)
        print(f"Exception Value: {args.exc_value}", file=sys.stderr)
        if args.exc_traceback:
            traceback.print_tb(args.exc_traceback, file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
    
    # Install the hooks
    sys.excepthook = global_exception_handler
    threading.excepthook = thread_exception_handler
    
    try:
        # Platform setup MUST happen before QApplication
        dpi_success, dpi_warning = setup_platform()

        # Now we can import Qt
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication(sys.argv)
        app.setApplicationName("QueueSend")
        app.setApplicationVersion("1.1.0")
        app.setOrganizationName("QueueSend")

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
        from app.core.logging import enable_console_logging, LogLevel

        # Enable console logging for all levels (DEBUG and above)
        enable_console_logging(LogLevel.DEBUG)

        window = MainWindow()
        controller = ApplicationController(window)

        # Show DPI warning if needed
        if dpi_warning:
            window.set_dpi_warning(dpi_warning)

        # Show window
        window.show()

        # Run event loop
        return app.exec()
    except Exception as e:
        print(f"\n{'='*60}\nFATAL ERROR 致命错误\n{'='*60}", file=sys.stderr)
        traceback.print_exc()
        print(f"{'='*60}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
