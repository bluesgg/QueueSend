"""Screen capture module using mss.

Captures the entire virtual desktop and crops ROI regions.
See TDD Section 5 and Executable Spec Section 2.2 for requirements.
"""

import time
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
    with mss.mss() as sct:
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
    last_error: Optional[Exception] = None

    for attempt in range(retry_count):
        try:
            with mss.mss() as sct:
                # Monitor 0 is the entire virtual desktop
                monitor = sct.monitors[0]
                screenshot = sct.grab(monitor)

                # Convert to numpy array (BGRA format)
                # Shape: (height, width, 4)
                image = np.array(screenshot)

                desktop_info = VirtualDesktopInfo(
                    left=monitor["left"],
                    top=monitor["top"],
                    width=monitor["width"],
                    height=monitor["height"],
                )

                return CaptureResult(image=image, desktop_info=desktop_info)

        except Exception as e:
            last_error = e
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

    # Validate bounds
    if x0 < 0 or y0 < 0 or x1 > full_image.shape[1] or y1 > full_image.shape[0]:
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


