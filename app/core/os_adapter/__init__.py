"""Platform-specific adapters for Windows and macOS.

This module provides cross-platform abstractions for:
- DPI awareness (Windows)
- Permission checking (macOS)
- Input injection (click/paste)
- Virtual desktop information
"""

import sys
from typing import TYPE_CHECKING

# Platform detection
IS_WINDOWS: bool = sys.platform == "win32"
IS_MACOS: bool = sys.platform == "darwin"
IS_LINUX: bool = sys.platform.startswith("linux")

if TYPE_CHECKING:
    from ..model import VirtualDesktopInfo


def get_virtual_desktop_info() -> "VirtualDesktopInfo":
    """Get information about the virtual desktop (all monitors combined).

    Returns:
        VirtualDesktopInfo with bounds of the entire virtual desktop.

    Note:
        On Windows with multiple monitors, coordinates may include
        negative values if monitors are positioned to the left of
        or above the primary monitor.
    """
    from ..model import VirtualDesktopInfo

    try:
        import mss

        with mss.mss() as sct:
            # Monitor 0 is the "all monitors" virtual screen
            all_monitors = sct.monitors[0]
            return VirtualDesktopInfo(
                left=all_monitors["left"],
                top=all_monitors["top"],
                width=all_monitors["width"],
                height=all_monitors["height"],
            )
    except Exception:
        # Fallback to primary screen via Qt
        try:
            from PySide6.QtWidgets import QApplication

            if QApplication.instance():
                screen = QApplication.primaryScreen()
                if screen:
                    geom = screen.virtualGeometry()
                    return VirtualDesktopInfo(
                        left=geom.x(),
                        top=geom.y(),
                        width=geom.width(),
                        height=geom.height(),
                    )
        except Exception:
            pass

        # Ultimate fallback
        return VirtualDesktopInfo(left=0, top=0, width=1920, height=1080)


def check_platform_ready() -> tuple[bool, str]:
    """Check if the platform is ready for automation.

    This performs platform-specific checks:
    - Windows: DPI awareness should already be set (done at startup)
    - macOS: Screen recording and accessibility permissions

    Returns:
        Tuple of (ready, message).
        - (True, "") if ready
        - (False, guidance_message) if not ready
    """
    if IS_MACOS:
        from .mac_permissions import check_permissions

        status = check_permissions()
        if not status.all_granted:
            return False, status.guidance or "缺少必需的系统权限"
        return True, ""

    # Windows and other platforms: assume ready
    return True, ""


def get_screen_count() -> int:
    """Get the number of connected displays.

    Returns:
        Number of displays, or 1 if detection fails.
    """
    try:
        from PySide6.QtWidgets import QApplication

        if QApplication.instance():
            return len(QApplication.screens())
    except Exception:
        pass

    try:
        import mss

        with mss.mss() as sct:
            # monitors[0] is virtual desktop, rest are individual monitors
            return len(sct.monitors) - 1
    except Exception:
        pass

    return 1


def is_single_display() -> bool:
    """Check if only a single display is connected.

    This is important for macOS which only supports single display
    in this version of the tool.

    Returns:
        True if single display, False if multiple.
    """
    return get_screen_count() == 1


# Convenience re-exports
__all__ = [
    "IS_WINDOWS",
    "IS_MACOS",
    "IS_LINUX",
    "get_virtual_desktop_info",
    "check_platform_ready",
    "get_screen_count",
    "is_single_display",
]
