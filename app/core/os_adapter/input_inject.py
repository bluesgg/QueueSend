"""Cross-platform input injection for mouse clicks and keyboard paste.

Provides click and paste functionality using pynput for input simulation
and Qt clipboard for text transfer.

See TDD Section 8 for requirements.
"""

import time
from typing import Optional

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

from ..model import Point
from . import IS_MACOS, IS_WINDOWS

# Global controller instances (reused for efficiency)
_mouse: Optional[MouseController] = None
_keyboard: Optional[KeyboardController] = None


def _get_mouse() -> MouseController:
    """Get or create the mouse controller singleton."""
    global _mouse
    if _mouse is None:
        _mouse = MouseController()
    return _mouse


def _get_keyboard() -> KeyboardController:
    """Get or create the keyboard controller singleton."""
    global _keyboard
    if _keyboard is None:
        _keyboard = KeyboardController()
    return _keyboard


def click_point(point: Point, button: Button = Button.left) -> None:
    """Click at the specified virtual desktop coordinates.

    Args:
        point: Target point in virtual desktop coordinates
        button: Mouse button to click (default: left)

    Note:
        On macOS, this requires Accessibility permission.
        Coordinates are in virtual desktop space (may include negative values
        on multi-monitor Windows setups).
    """
    mouse = _get_mouse()

    # Move to position
    mouse.position = (point.x, point.y)

    # Small delay to ensure position is set
    time.sleep(0.01)

    # Click
    mouse.click(button, 1)


def double_click_point(point: Point) -> None:
    """Double-click at the specified coordinates.

    Args:
        point: Target point in virtual desktop coordinates
    """
    mouse = _get_mouse()
    mouse.position = (point.x, point.y)
    time.sleep(0.01)
    mouse.click(Button.left, 2)


def move_to(point: Point) -> None:
    """Move mouse to the specified coordinates without clicking.

    Args:
        point: Target point in virtual desktop coordinates
    """
    mouse = _get_mouse()
    mouse.position = (point.x, point.y)


def get_mouse_position() -> Point:
    """Get current mouse position.

    Returns:
        Current mouse position as Point
    """
    mouse = _get_mouse()
    x, y = mouse.position
    return Point(int(x), int(y))


def paste_from_clipboard() -> None:
    """Send the paste keyboard shortcut (Ctrl+V on Windows, Cmd+V on macOS).

    This simulates the system paste shortcut to paste clipboard contents
    into the focused application.

    Note:
        The clipboard should be set before calling this function.
        Use set_clipboard_text() to set clipboard content.
    """
    keyboard = _get_keyboard()

    if IS_MACOS:
        # macOS: Cmd+V
        with keyboard.pressed(Key.cmd):
            keyboard.press('v')
            keyboard.release('v')
    else:
        # Windows/Linux: Ctrl+V
        with keyboard.pressed(Key.ctrl):
            keyboard.press('v')
            keyboard.release('v')

    # Small delay to allow paste to complete
    time.sleep(0.05)


def set_clipboard_text(text: str) -> bool:
    """Set text to the system clipboard using Qt.

    Args:
        text: Text to copy to clipboard (supports multi-line)

    Returns:
        True if successful, False otherwise

    Note:
        This function must be called from the main thread or a thread
        with Qt event loop access.
    """
    try:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False

        clipboard.setText(text)
        return True
    except Exception:
        return False


def paste_text(text: str) -> bool:
    """Set clipboard text and send paste command.

    This is the main function for pasting text into target applications.
    It combines clipboard setting with keyboard shortcut simulation.

    Args:
        text: Text to paste (supports multi-line with preserved line breaks)

    Returns:
        True if clipboard was set successfully, False otherwise

    Note:
        Even if this returns True, paste may fail if the target application
        doesn't have focus or doesn't support paste. The automation relies
        on ROI change detection to verify success.
    """
    # Set clipboard
    if not set_clipboard_text(text):
        return False

    # Small delay to ensure clipboard is ready
    time.sleep(0.02)

    # Send paste shortcut
    paste_from_clipboard()

    return True


def type_text(text: str, interval: float = 0.02) -> None:
    """Type text character by character.

    This is an alternative to paste for applications that don't support
    clipboard paste well. Generally slower but more compatible.

    Args:
        text: Text to type
        interval: Delay between keystrokes in seconds

    Note:
        This does NOT preserve special characters well and is much slower
        than paste. Use paste_text() when possible.
    """
    keyboard = _get_keyboard()

    for char in text:
        if char == '\n':
            keyboard.press(Key.enter)
            keyboard.release(Key.enter)
        else:
            keyboard.type(char)

        if interval > 0:
            time.sleep(interval)


def send_key(key: Key) -> None:
    """Send a single key press.

    Args:
        key: The key to press (from pynput.keyboard.Key)
    """
    keyboard = _get_keyboard()
    keyboard.press(key)
    keyboard.release(key)


def send_enter() -> None:
    """Send the Enter key."""
    send_key(Key.enter)


def send_escape() -> None:
    """Send the Escape key."""
    send_key(Key.esc)


def select_all() -> None:
    """Send Select All shortcut (Ctrl+A on Windows, Cmd+A on macOS)."""
    keyboard = _get_keyboard()

    if IS_MACOS:
        with keyboard.pressed(Key.cmd):
            keyboard.press('a')
            keyboard.release('a')
    else:
        with keyboard.pressed(Key.ctrl):
            keyboard.press('a')
            keyboard.release('a')


class InputInjector:
    """High-level input injection interface.

    Provides a clean interface for the automation engine to perform
    input operations with logging support.
    """

    def __init__(self) -> None:
        """Initialize the input injector."""
        self._last_click_point: Optional[Point] = None
        self._last_paste_text: Optional[str] = None

    def click(self, point: Point) -> None:
        """Click at the specified point.

        Args:
            point: Virtual desktop coordinates to click
        """
        click_point(point)
        self._last_click_point = point

    def paste(self, text: str) -> bool:
        """Paste text via clipboard.

        Args:
            text: Text to paste

        Returns:
            True if clipboard was set successfully
        """
        result = paste_text(text)
        if result:
            self._last_paste_text = text
        return result

    @property
    def last_click_point(self) -> Optional[Point]:
        """Get the last clicked point."""
        return self._last_click_point

    @property
    def last_paste_text(self) -> Optional[str]:
        """Get the last pasted text."""
        return self._last_paste_text

    def reset(self) -> None:
        """Reset tracking state."""
        self._last_click_point = None
        self._last_paste_text = None

