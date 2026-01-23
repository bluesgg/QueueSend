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
    import sys
    import traceback
    
    try:
        print(f"[DEBUG] click_point: ({point.x}, {point.y})", file=sys.stderr)
        mouse = _get_mouse()
        print(f"[DEBUG] mouse controller obtained", file=sys.stderr)

        # Move to position
        print(f"[DEBUG] setting mouse position to ({point.x}, {point.y})", file=sys.stderr)
        mouse.position = (point.x, point.y)
        print(f"[DEBUG] mouse position set", file=sys.stderr)

        # Small delay to ensure position is set
        time.sleep(0.01)

        # Click
        print(f"[DEBUG] performing click", file=sys.stderr)
        mouse.click(button, 1)
        print(f"[DEBUG] click completed", file=sys.stderr)
    except Exception as e:
        print(f"\n{'='*60}\nCLICK_POINT ERROR 点击错误\n{'='*60}", file=sys.stderr)
        print(f"Point: ({point.x}, {point.y})", file=sys.stderr)
        print(f"Button: {button}", file=sys.stderr)
        traceback.print_exc()
        print(f"{'='*60}\n", file=sys.stderr)
        raise


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


import threading as _threading

# Thread-safe clipboard synchronization
_clipboard_lock = _threading.Lock()
_clipboard_result = False
_clipboard_event = _threading.Event()
_clipboard_helper_instance = None


def _get_clipboard_helper():
    """Get the clipboard helper singleton. Must call init_clipboard_helper() first from main thread."""
    global _clipboard_helper_instance
    return _clipboard_helper_instance


def init_clipboard_helper() -> None:
    """Initialize the clipboard helper on the main thread.
    
    MUST be called from the main thread before any worker thread uses set_clipboard_text().
    Typically called during application startup.
    """
    global _clipboard_helper_instance
    if _clipboard_helper_instance is not None:
        return  # Already initialized
    
    from PySide6.QtCore import QObject, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    
    class ClipboardHelper(QObject):
        """Helper QObject to receive clipboard requests on main thread."""
        set_text_signal = Signal(str)
        
        def __init__(self):
            super().__init__()
            self.set_text_signal.connect(self._on_set_text)
        
        @Slot(str)
        def _on_set_text(self, text: str) -> None:
            import sys
            global _clipboard_result
            try:
                print(f"[DEBUG] _on_set_text SLOT called, text length={len(text)}", file=sys.stderr)
                print(f"[DEBUG] getting clipboard from QGuiApplication", file=sys.stderr)
                clipboard = QGuiApplication.clipboard()
                print(f"[DEBUG] clipboard object: {clipboard}", file=sys.stderr)
                if clipboard is not None:
                    print(f"[DEBUG] SLOT: calling clipboard.setText()", file=sys.stderr)
                    sys.stderr.flush()  # Force flush before potential crash
                    clipboard.setText(text)
                    print(f"[DEBUG] SLOT: clipboard.setText() completed", file=sys.stderr)
                    _clipboard_result = True
                else:
                    print(f"[DEBUG] SLOT: clipboard is None!", file=sys.stderr)
                    _clipboard_result = False
            except Exception as e:
                print(f"[DEBUG] SLOT: Exception: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                _clipboard_result = False
            finally:
                print(f"[DEBUG] SLOT: setting event", file=sys.stderr)
                _clipboard_event.set()
                print(f"[DEBUG] SLOT: event set, exiting", file=sys.stderr)
    
    _clipboard_helper_instance = ClipboardHelper()


def init_input_controllers() -> None:
    """Initialize pynput input controllers on the main thread.
    
    MUST be called from the main thread before any worker thread uses input injection.
    On macOS, pynput's controllers access HIServices APIs during initialization,
    which must run on the main thread to avoid dispatch_assert_queue crashes.
    
    Typically called during application startup.
    """
    import sys
    try:
        print(f"[INIT] Initializing input controllers on main thread...", file=sys.stderr)
        # Force initialization of both controllers on main thread
        _ = _get_mouse()
        _ = _get_keyboard()
        print(f"[INIT] Input controllers initialized successfully", file=sys.stderr)
    except Exception as e:
        print(f"[INIT] Warning: Failed to initialize input controllers: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()


def set_clipboard_text(text: str) -> bool:
    """Set text to the system clipboard using Qt.

    Args:
        text: Text to copy to clipboard (supports multi-line)

    Returns:
        True if successful, False otherwise

    Note:
        This function safely marshals clipboard calls to the main thread
        to avoid COM initialization issues on Windows.
    """
    import sys
    global _clipboard_result

    try:
        print(f"[DEBUG] set_clipboard_text START", file=sys.stderr)
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import QThread

        print(f"[DEBUG] getting QGuiApplication instance", file=sys.stderr)
        app = QGuiApplication.instance()
        if app is None:
            print(f"[DEBUG] QGuiApplication instance is None!", file=sys.stderr)
            return False

        print(f"[DEBUG] checking thread", file=sys.stderr)
        main_thread = app.thread()
        current_thread = QThread.currentThread()
        is_main = main_thread == current_thread
        print(f"[DEBUG] is_main_thread={is_main}, current={current_thread.objectName()}", file=sys.stderr)

        if is_main:
            print(f"[DEBUG] on main thread, direct clipboard access", file=sys.stderr)
            # Already on main thread, set directly
            clipboard = QGuiApplication.clipboard()
            if clipboard is None:
                print(f"[DEBUG] clipboard is None!", file=sys.stderr)
                return False
            print(f"[DEBUG] calling clipboard.setText()", file=sys.stderr)
            clipboard.setText(text)
            print(f"[DEBUG] clipboard.setText() completed", file=sys.stderr)
            return True
        else:
            print(f"[DEBUG] on worker thread, marshaling to main thread", file=sys.stderr)
            # Worker thread: use signal to marshal to main thread
            with _clipboard_lock:
                print(f"[DEBUG] acquired clipboard lock", file=sys.stderr)
                _clipboard_event.clear()
                _clipboard_result = False

                helper = _get_clipboard_helper()
                print(f"[DEBUG] clipboard helper: {helper}", file=sys.stderr)
                if helper is None:
                    print(f"[DEBUG] helper is None, using fallback", file=sys.stderr)
                    # Fallback: try direct access (may cause COM error on Windows)
                    clipboard = QGuiApplication.clipboard()
                    if clipboard:
                        print(f"[DEBUG] FALLBACK: calling clipboard.setText()", file=sys.stderr)
                        clipboard.setText(text)
                        print(f"[DEBUG] FALLBACK: clipboard.setText() completed", file=sys.stderr)
                        return True
                    return False

                # Emit signal - Qt will queue it to main thread
                print(f"[DEBUG] emitting set_text_signal", file=sys.stderr)
                helper.set_text_signal.emit(text)
                print(f"[DEBUG] signal emitted, waiting for result", file=sys.stderr)

                # Wait for the slot to execute on main thread
                success = _clipboard_event.wait(timeout=2.0)
                print(f"[DEBUG] wait completed, success={success}, result={_clipboard_result}", file=sys.stderr)

                return _clipboard_result if success else False

    except Exception as e:
        print(f"[DEBUG] Exception in set_clipboard_text: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
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
    import sys
    import traceback
    
    try:
        print(f"[DEBUG] paste_text: length={len(text)}, text={text[:50]}...", file=sys.stderr)
        
        # Set clipboard
        print(f"[DEBUG] setting clipboard", file=sys.stderr)
        if not set_clipboard_text(text):
            print(f"[DEBUG] clipboard set FAILED", file=sys.stderr)
            return False
        print(f"[DEBUG] clipboard set OK", file=sys.stderr)

        # Small delay to ensure clipboard is ready
        time.sleep(0.02)

        # Send paste shortcut
        print(f"[DEBUG] sending paste command", file=sys.stderr)
        paste_from_clipboard()
        print(f"[DEBUG] paste command sent", file=sys.stderr)

        return True
    except Exception as e:
        print(f"\n{'='*60}\nPASTE_TEXT ERROR 粘贴错误\n{'='*60}", file=sys.stderr)
        print(f"Text length: {len(text)}", file=sys.stderr)
        print(f"Text preview: {text[:100]}", file=sys.stderr)
        traceback.print_exc()
        print(f"{'='*60}\n", file=sys.stderr)
        raise


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

