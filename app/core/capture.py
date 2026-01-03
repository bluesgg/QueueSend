"""Screen capture module using mss.

Captures the entire virtual desktop and crops ROI regions.
See TDD Section 5 and Executable Spec Section 2.2 for requirements.
"""

import time
import json
from dataclasses import dataclass
from typing import Optional

import mss
import numpy as np

from .constants import (
    CAPTURE_RETRY_INTERVAL_MS,
    CAPTURE_RETRY_N,
    GRAY_WEIGHT_B,
    GRAY_WEIGHT_G,
    GRAY_WEIGHT_R,
)
from .model import ROI, Rect, VirtualDesktopInfo

# #region agent log
import os as _os
_DEBUG_LOG_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), ".cursor", "debug.log")
_capture_count = 0
def _log_debug(location: str, message: str, data: dict, hypothesis_id: str):
    entry = {"location": location, "message": message, "data": data, "timestamp": int(time.time()*1000), "sessionId": "debug-session", "hypothesisId": hypothesis_id}
    try:
        _os.makedirs(_os.path.dirname(_DEBUG_LOG_PATH), exist_ok=True)
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except: pass
# #endregion

# Thread-local mss instance to avoid GDI resource exhaustion and thread-safety issues
# mss uses thread-local storage for Windows GDI handles, so each thread needs its own instance
import threading
_thread_local = threading.local()

def _get_mss() -> "mss.mss":
    """Get or create a thread-local mss instance.
    
    mss uses thread-local storage for Windows GDI handles (srcdc, memdc, etc.).
    If an mss instance is created on one thread and used on another, it will fail
    with "'_thread._local' object has no attribute 'srcdc'".
    
    This function ensures each thread has its own mss instance.
    """
    if not hasattr(_thread_local, 'mss_instance') or _thread_local.mss_instance is None:
        _thread_local.mss_instance = mss.mss()
        # #region agent log
        _log_debug("capture.py:_get_mss", "Created new thread-local mss instance", {"monitors_count": len(_thread_local.mss_instance.monitors), "thread": threading.current_thread().name}, "B")
        # #endregion
    return _thread_local.mss_instance

def _reset_mss() -> None:
    """Reset the thread-local mss instance (call on error recovery)."""
    if hasattr(_thread_local, 'mss_instance') and _thread_local.mss_instance is not None:
        try:
            _thread_local.mss_instance.close()
        except Exception:
            pass
        _thread_local.mss_instance = None


class CaptureError(Exception):
    """Exception raised when screen capture fails after retries."""

    pass


@dataclass
class CaptureResult:
    """Result of a screen capture operation.

    Attributes:
        image: Captured image as numpy array (BGRA format from mss)
        desktop_info: Virtual desktop bounds info
    """

    image: np.ndarray
    desktop_info: VirtualDesktopInfo


def get_virtual_desktop_info_from_mss() -> VirtualDesktopInfo:
    """Get virtual desktop info using mss.

    Returns:
        VirtualDesktopInfo with bounds of the entire virtual desktop.
    """
    sct = _get_mss()
    # Monitor 0 is the "all monitors" virtual screen
    all_monitors = sct.monitors[0]
    return VirtualDesktopInfo(
        left=all_monitors["left"],
        top=all_monitors["top"],
        width=all_monitors["width"],
        height=all_monitors["height"],
    )


def capture_full_desktop(
    retry_count: int = CAPTURE_RETRY_N,
    retry_interval_ms: int = CAPTURE_RETRY_INTERVAL_MS,
) -> CaptureResult:
    """Capture the entire virtual desktop.

    Uses mss monitor=0 to capture all monitors combined.
    Includes retry logic per Spec Section 11.2.

    Args:
        retry_count: Number of retry attempts on failure
        retry_interval_ms: Milliseconds between retry attempts

    Returns:
        CaptureResult with image and desktop info

    Raises:
        CaptureError: If capture fails after all retries
    """
    global _capture_count
    _capture_count += 1
    last_error: Optional[Exception] = None

    for attempt in range(retry_count):
        try:
            # #region agent log
            if _capture_count <= 5:
                _log_debug("capture.py:capture_full_desktop:before_grab", "About to grab", {"count": _capture_count, "attempt": attempt}, "B")
            # #endregion

            # Use global mss instance to avoid GDI resource exhaustion
            sct = _get_mss()

            # Monitor 0 is the entire virtual desktop
            monitor = sct.monitors[0]

            screenshot = sct.grab(monitor)

            # #region agent log
            if _capture_count <= 5:
                _log_debug("capture.py:capture_full_desktop:after_grab", "sct.grab completed", {"count": _capture_count}, "B")
            # #endregion

            # Convert to numpy array (BGRA format)
            # Shape: (height, width, 4)
            image = np.array(screenshot)

            # #region agent log
            if _capture_count <= 5:
                _log_debug("capture.py:capture_full_desktop:converted", "Converted to numpy", {"count": _capture_count, "shape": list(image.shape)}, "B")
            # #endregion

            desktop_info = VirtualDesktopInfo(
                left=monitor["left"],
                top=monitor["top"],
                width=monitor["width"],
                height=monitor["height"],
            )

            return CaptureResult(image=image, desktop_info=desktop_info)

        except Exception as e:
            # #region agent log
            _log_debug("capture.py:capture_full_desktop:exception", "Capture failed with exception", {"count": _capture_count, "error": str(e), "type": type(e).__name__, "attempt": attempt}, "B")
            # #endregion
            last_error = e
            # Reset mss instance on error - it may be in a bad state
            _reset_mss()
            if attempt < retry_count - 1:
                time.sleep(retry_interval_ms / 1000.0)

    raise CaptureError(
        f"截图失败,已重试{retry_count}次。最后错误: {last_error}"
    )


def crop_roi(
    full_image: np.ndarray,
    roi: ROI,
    desktop_info: VirtualDesktopInfo,
) -> np.ndarray:
    """Crop the ROI region from a full desktop capture.

    Maps virtual desktop coordinates to array indices.

    Args:
        full_image: Full desktop image from capture_full_desktop()
        roi: Region of interest to crop
        desktop_info: Virtual desktop bounds used during capture

    Returns:
        Cropped image as numpy array (same format as input)

    Raises:
        ValueError: If ROI is outside the captured region
    """
    rect = roi.rect

    # Map virtual desktop coordinates to array indices
    # Virtual desktop may have negative coordinates (e.g., -1920, 0)
    # Array indices are always 0-based
    x0 = rect.x - desktop_info.left
    y0 = rect.y - desktop_info.top
    x1 = x0 + rect.w
    y1 = y0 + rect.h

    # #region agent log
    if _capture_count <= 3:
        _log_debug("capture.py:crop_roi", "Cropping ROI", {
            "roi_rect": {"x": rect.x, "y": rect.y, "w": rect.w, "h": rect.h},
            "desktop": {"left": desktop_info.left, "top": desktop_info.top, "width": desktop_info.width, "height": desktop_info.height},
            "array_indices": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
            "image_shape": list(full_image.shape),
        }, "C,D")
    # #endregion

    # Validate bounds
    if x0 < 0 or y0 < 0 or x1 > full_image.shape[1] or y1 > full_image.shape[0]:
        # #region agent log
        _log_debug("capture.py:crop_roi:bounds_error", "ROI out of bounds", {
            "roi_rect": {"x": rect.x, "y": rect.y, "w": rect.w, "h": rect.h},
            "desktop": {"left": desktop_info.left, "top": desktop_info.top, "width": desktop_info.width, "height": desktop_info.height},
            "array_indices": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
            "image_shape": list(full_image.shape),
        }, "C,D")
        # #endregion
        raise ValueError(
            f"ROI ({rect.x}, {rect.y}, {rect.w}x{rect.h}) 超出截图范围 "
            f"({desktop_info.left}, {desktop_info.top}, "
            f"{desktop_info.width}x{desktop_info.height})"
        )

    # Crop: numpy uses [y, x] indexing (row, column)
    return full_image[y0:y1, x0:x1].copy()


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert BGRA/BGR image to grayscale.

    Uses ITU-R BT.601 weights: Y = 0.299*R + 0.587*G + 0.114*B

    Args:
        image: Input image in BGR or BGRA format (from mss)

    Returns:
        Grayscale image as uint8 numpy array
    """
    # mss returns BGRA format
    # Extract B, G, R channels (ignore alpha if present)
    if image.ndim == 2:
        # Already grayscale
        return image.astype(np.uint8)

    b = image[:, :, 0].astype(np.float32)
    g = image[:, :, 1].astype(np.float32)
    r = image[:, :, 2].astype(np.float32)

    # Apply grayscale weights
    gray = GRAY_WEIGHT_R * r + GRAY_WEIGHT_G * g + GRAY_WEIGHT_B * b

    return gray.astype(np.uint8)


def capture_roi_gray(
    roi: ROI,
    retry_count: int = CAPTURE_RETRY_N,
    retry_interval_ms: int = CAPTURE_RETRY_INTERVAL_MS,
) -> np.ndarray:
    """Capture and crop ROI, returning grayscale image.

    Convenience function that combines full desktop capture,
    ROI cropping, and grayscale conversion.

    Args:
        roi: Region of interest to capture
        retry_count: Number of retry attempts on failure
        retry_interval_ms: Milliseconds between retry attempts

    Returns:
        Grayscale ROI image as uint8 numpy array

    Raises:
        CaptureError: If capture fails after all retries
    """
    result = capture_full_desktop(retry_count, retry_interval_ms)
    cropped = crop_roi(result.image, roi, result.desktop_info)
    return to_grayscale(cropped)


def save_roi_preview(
    roi: ROI,
    filepath: str,
) -> bool:
    """Capture ROI and save as PNG for debugging.

    This is a debug utility per TDD Section 11.2 requirements.

    Args:
        roi: Region of interest to capture
        filepath: Output file path (should end in .png)

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        from PIL import Image

        result = capture_full_desktop()
        cropped = crop_roi(result.image, roi, result.desktop_info)

        # Convert BGRA to RGBA for PIL
        if cropped.shape[2] == 4:
            rgba = cropped.copy()
            rgba[:, :, 0] = cropped[:, :, 2]  # R <- B
            rgba[:, :, 2] = cropped[:, :, 0]  # B <- R
            img = Image.fromarray(rgba, mode="RGBA")
        else:
            # BGR to RGB
            rgb = cropped[:, :, ::-1]
            img = Image.fromarray(rgb, mode="RGB")

        img.save(filepath)
        return True

    except ImportError:
        # PIL not available, try with mss built-in
        try:
            import mss.tools

            result = capture_full_desktop()
            cropped = crop_roi(result.image, roi, result.desktop_info)
            # mss.tools.to_png expects specific format
            mss.tools.to_png(cropped.tobytes(), (roi.rect.w, roi.rect.h), output=filepath)
            return True
        except Exception:
            return False

    except Exception:
        return False


class ScreenCapture:
    """High-level screen capture interface.

    Provides a stateful interface for the automation engine to
    capture ROI frames with caching of desktop info.
    """

    def __init__(self) -> None:
        """Initialize the screen capture interface."""
        self._desktop_info: Optional[VirtualDesktopInfo] = None
        self._last_full_capture: Optional[np.ndarray] = None

    def refresh_desktop_info(self) -> VirtualDesktopInfo:
        """Refresh and return virtual desktop info."""
        self._desktop_info = get_virtual_desktop_info_from_mss()
        return self._desktop_info

    @property
    def desktop_info(self) -> VirtualDesktopInfo:
        """Get cached or fresh virtual desktop info."""
        if self._desktop_info is None:
            self.refresh_desktop_info()
        return self._desktop_info  # type: ignore

    def capture_roi(self, roi: ROI) -> np.ndarray:
        """Capture ROI region as grayscale.

        Args:
            roi: Region of interest to capture

        Returns:
            Grayscale image as uint8 numpy array
        """
        return capture_roi_gray(roi)

    def capture_full(self) -> CaptureResult:
        """Capture full desktop.

        Returns:
            CaptureResult with image and desktop info
        """
        result = capture_full_desktop()
        self._desktop_info = result.desktop_info
        self._last_full_capture = result.image
        return result

    def crop_from_last(self, roi: ROI) -> np.ndarray:
        """Crop ROI from the last full capture.

        Useful when you need to crop multiple ROIs from the same
        capture without re-capturing.

        Args:
            roi: Region of interest to crop

        Returns:
            Cropped image as numpy array

        Raises:
            ValueError: If no previous capture exists
        """
        if self._last_full_capture is None or self._desktop_info is None:
            raise ValueError("No previous capture available. Call capture_full() first.")

        return crop_roi(self._last_full_capture, roi, self._desktop_info)


