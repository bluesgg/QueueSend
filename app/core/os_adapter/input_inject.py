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

# Get logger for debug info
def _get_input_logger():
    """Get logger instance, lazy init to avoid circular imports."""
    try:
        from ..logging import get_logger
        return get_logger()
    except:
        return None

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
    logger = _get_input_logger()
    if logger:
        logger.debug(f"准备点击坐标", x=point.x, y=point.y, button=str(button))
    
    mouse = _get_mouse()

    # Move to position
    try:
        mouse.position = (point.x, point.y)
        if logger:
            logger.debug(f"鼠标移动到位置", x=point.x, y=point.y)
    except Exception as e:
        if logger:
            logger.exception("鼠标移动失败", e, x=point.x, y=point.y)
        raise

    # Small delay to ensure position is set
    time.sleep(0.01)

    # Click
    try:
        mouse.click(button, 1)
        if logger:
            logger.debug(f"点击完成", x=point.x, y=point.y)
    except Exception as e:
        if logger:
            logger.exception("点击失败", e, x=point.x, y=point.y)
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
    logger = _get_input_logger()
    if logger:
        logger.debug(f"准备发送粘贴快捷键", is_macos=IS_MACOS)
    
    keyboard = _get_keyboard()

    try:
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
        
        if logger:
            logger.debug(f"粘贴快捷键发送完成")
    except Exception as e:
        if logger:
            logger.exception("发送粘贴快捷键失败", e)
        raise

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
            global _clipboard_result
            try:
                clipboard = QGuiApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(text)
                    _clipboard_result = True
                else:
                    _clipboard_result = False
            except Exception:
                _clipboard_result = False
            finally:
                _clipboard_event.set()
    
    _clipboard_helper_instance = ClipboardHelper()


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
    global _clipboard_result
    logger = _get_input_logger()

    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import QThread

        app = QGuiApplication.instance()
        if app is None:
            if logger:
                logger.error("无法获取QGuiApplication实例")
            return False

        main_thread = app.thread()
        current_thread = QThread.currentThread()
        is_main = main_thread == current_thread

        if logger:
            logger.debug(f"设置剪贴板", text_length=len(text), is_main_thread=is_main)

        if is_main:
            # Already on main thread, set directly
            clipboard = QGuiApplication.clipboard()
            if clipboard is None:
                if logger:
                    logger.error("无法获取剪贴板对象")
                return False
            clipboard.setText(text)
            if logger:
                logger.debug("剪贴板设置成功 (主线程)")
            return True
        else:
            # Worker thread: use signal to marshal to main thread
            with _clipboard_lock:
                _clipboard_event.clear()
                _clipboard_result = False

                helper = _get_clipboard_helper()
                if helper is None:
                    if logger:
                        logger.warning("剪贴板助手未初始化，尝试直接访问")
                    # Fallback: try direct access (may cause COM error on Windows)
                    clipboard = QGuiApplication.clipboard()
                    if clipboard:
                        clipboard.setText(text)
                        return True
                    return False

                # Emit signal - Qt will queue it to main thread
                helper.set_text_signal.emit(text)

                # Wait for the slot to execute on main thread
                success = _clipboard_event.wait(timeout=2.0)
                
                if not success:
                    if logger:
                        logger.error("设置剪贴板超时")
                elif _clipboard_result:
                    if logger:
                        logger.debug("剪贴板设置成功 (工作线程)")
                else:
                    if logger:
                        logger.error("设置剪贴板失败")

                return _clipboard_result if success else False

    except Exception as e:
        if logger:
            logger.exception("设置剪贴板异常", e)
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
    logger = _get_input_logger()
    if logger:
        logger.debug(f"准备粘贴文本", text_length=len(text), has_newlines='\n' in text)
    
    # Set clipboard
    if not set_clipboard_text(text):
        if logger:
            logger.error("设置剪贴板失败，粘贴终止")
        return False

    # Small delay to ensure clipboard is ready
    time.sleep(0.02)

    # Send paste shortcut
    try:
        paste_from_clipboard()
        if logger:
            logger.debug("粘贴操作完成")
        return True
    except Exception as e:
        if logger:
            logger.exception("粘贴操作失败", e)
        return False


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

