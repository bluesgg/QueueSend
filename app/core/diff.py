"""Diff calculation and threshold calibration.

Implements the change detection algorithm and noise-based threshold
calibration as specified in Executable Spec Sections 7 and 8.
"""

import time
from typing import Optional

import numpy as np

from .capture import capture_roi_gray, to_grayscale
from .constants import (
    CALIB_FRAMES_DEFAULT,
    CALIB_INTERVAL_MS,
    TH_HOLD_MAX,
    TH_HOLD_MIN,
)
from .model import ROI, CalibrationStats, Circle, ROIShape

# Get logger for debug info
def _get_diff_logger():
    """Get logger instance, lazy init to avoid circular imports."""
    try:
        from .logging import get_logger
        return get_logger()
    except:
        return None


def create_circle_mask(height: int, width: int, circle: Circle) -> np.ndarray:
    """Create a boolean mask for circular ROI.

    The mask is True for pixels inside the circle, False outside.
    Uses the formula: (x - cx)^2 + (y - cy)^2 <= r^2

    Args:
        height: Image height in pixels
        width: Image width in pixels
        circle: Circle parameters (in local ROI coordinates)

    Returns:
        Boolean mask array of shape (height, width)
    """
    # Create coordinate grids
    # Note: In array coordinates, rows are y and columns are x
    y_coords, x_coords = np.ogrid[:height, :width]

    # Calculate local circle center (relative to ROI top-left)
    # The circle.cx and circle.cy are in virtual desktop coordinates
    # For the mask, we need local coordinates within the ROI
    # Since the ROI rect starts at (rect.x, rect.y), the local center is:
    # cx_local = circle.cx - rect.x = (rect.x + w/2) - rect.x = w/2
    # cy_local = circle.cy - rect.y = (rect.y + h/2) - rect.y = h/2
    cx_local = width / 2
    cy_local = height / 2
    r = min(width, height) / 2

    # Calculate squared distance from center
    dist_sq = (x_coords - cx_local) ** 2 + (y_coords - cy_local) ** 2

    # Create mask: True where inside circle
    return dist_sq <= r ** 2


def calculate_diff(
    frame_t: np.ndarray,
    frame_t0: np.ndarray,
    roi: Optional[ROI] = None,
) -> float:
    """Calculate the difference between two frames.

    Implements the diff algorithm from Executable Spec Section 7.1:
    1. Frames should already be grayscale
    2. absdiff = abs(frame_t - frame_t0)
    3. For circle ROI: only count pixels inside the circle mask
    4. d = mean(absdiff) / 255.0

    Args:
        frame_t: Current frame (grayscale uint8)
        frame_t0: Reference frame (grayscale uint8)
        roi: Optional ROI for circle mask (if shape is CIRCLE)

    Returns:
        Diff value in range [0.0, 1.0]

    Raises:
        ValueError: If frames have different shapes
    """
    logger = _get_diff_logger()
    
    if frame_t.shape != frame_t0.shape:
        error_msg = f"Frame shapes must match: {frame_t.shape} vs {frame_t0.shape}"
        if logger:
            logger.error(error_msg, frame_t_shape=str(frame_t.shape), frame_t0_shape=str(frame_t0.shape))
        raise ValueError(error_msg)

    # Ensure grayscale (2D array)
    if frame_t.ndim == 3:
        frame_t = to_grayscale(frame_t)
    if frame_t0.ndim == 3:
        frame_t0 = to_grayscale(frame_t0)

    # Calculate absolute difference
    # Use int16 to avoid overflow issues with subtraction
    try:
        absdiff = np.abs(
            frame_t.astype(np.int16) - frame_t0.astype(np.int16)
        ).astype(np.uint8)
    except Exception as e:
        if logger:
            logger.exception("计算absdiff失败", e, frame_t_dtype=str(frame_t.dtype), frame_t0_dtype=str(frame_t0.dtype))
        raise

    # Apply circle mask if needed (Spec 4.2, 7.1)
    if roi is not None and roi.shape == ROIShape.CIRCLE:
        height, width = absdiff.shape
        mask = create_circle_mask(height, width, roi.circle)  # type: ignore
        # Only count pixels inside the circle
        masked_pixels = absdiff[mask]
        if len(masked_pixels) == 0:
            if logger:
                logger.warning("圆形蒙版内没有像素", height=height, width=width)
            return 0.0
        mean_diff = float(np.mean(masked_pixels))
        if logger:
            logger.debug(f"使用圆形蒙版", masked_pixel_count=len(masked_pixels), mean_diff=f"{mean_diff:.2f}")
    else:
        mean_diff = float(np.mean(absdiff))

    # Normalize to [0, 1]
    d = mean_diff / 255.0

    return d


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to the given range."""
    return max(min_val, min(max_val, value))


def calibrate_threshold(
    roi: ROI,
    k_frames: int = CALIB_FRAMES_DEFAULT,
    interval_ms: int = CALIB_INTERVAL_MS,
) -> CalibrationStats:
    """Calibrate the change detection threshold based on static noise.

    Implements the calibration algorithm from Executable Spec Section 8.3:
    1. Capture K frames (default 8, range 5-10)
    2. Take first frame as reference
    3. Calculate di = diff(frame_i, ref) for each subsequent frame
    4. Calculate mu = mean(di), sigma = std(di)
    5. TH_rec = clamp(mu + 3*sigma, 0.005, 0.2)

    The 3*sigma covers 99.7% of normal noise (assuming normal distribution).

    Args:
        roi: Region of interest to calibrate
        k_frames: Number of frames to capture (5-10, default 8)
        interval_ms: Interval between captures in milliseconds (100-200)

    Returns:
        CalibrationStats with mu, sigma, recommended threshold, and warning if any
    """
    # Validate k_frames
    k_frames = max(5, min(10, k_frames))

    # Capture frames
    frames: list[np.ndarray] = []
    for i in range(k_frames):
        frame = capture_roi_gray(roi)
        frames.append(frame)
        if i < k_frames - 1:
            time.sleep(interval_ms / 1000.0)

    # Use first frame as reference
    ref = frames[0]

    # Calculate diff for each subsequent frame
    di_values: list[float] = []
    for i in range(1, len(frames)):
        d = calculate_diff(frames[i], ref, roi)
        di_values.append(d)

    # Calculate statistics
    if len(di_values) == 0:
        # Edge case: only one frame captured
        mu = 0.0
        sigma = 0.0
    else:
        mu = float(np.mean(di_values))
        sigma = float(np.std(di_values))

    # Calculate recommended threshold (Spec 8.3)
    raw_th = mu + 3 * sigma

    # Check for warning condition
    warning: Optional[str] = None
    if raw_th > TH_HOLD_MAX:
        warning = "噪声异常,建议重新选择ROI"

    # Clamp to valid range
    th_rec = clamp(raw_th, TH_HOLD_MIN, TH_HOLD_MAX)

    return CalibrationStats(
        mu=mu,
        sigma=sigma,
        th_rec=th_rec,
        di_values=di_values,
        warning=warning,
    )


class HoldHitsTracker:
    """Tracks consecutive diff hits for change detection.

    Implements the "hold 2 seconds" logic from Spec Section 7.2:
    - At 1 FPS sampling, require 2 consecutive hits
    - Reset counter to 0 when diff < threshold
    """

    def __init__(self, required_hits: int = 2) -> None:
        """Initialize the tracker.

        Args:
            required_hits: Number of consecutive hits required (default 2)
        """
        self._required_hits = required_hits
        self._hold_hits = 0

    @property
    def hold_hits(self) -> int:
        """Current consecutive hit count."""
        return self._hold_hits

    @property
    def required_hits(self) -> int:
        """Number of hits required to pass."""
        return self._required_hits

    def update(self, diff: float, threshold: float) -> bool:
        """Update tracker with new diff value.

        Args:
            diff: Current diff value
            threshold: Detection threshold (TH_HOLD)

        Returns:
            True if consecutive hits requirement is met, False otherwise
        """
        if diff >= threshold:
            self._hold_hits += 1
        else:
            # Reset on miss (Spec 7.2)
            self._hold_hits = 0

        return self._hold_hits >= self._required_hits

    def reset(self) -> None:
        """Reset the hit counter."""
        self._hold_hits = 0


class DiffCalculator:
    """High-level diff calculation interface.

    Provides a stateful interface for the automation engine to
    calculate diffs and track hold hits.
    """

    def __init__(self, roi: ROI, threshold: float) -> None:
        """Initialize the diff calculator.

        Args:
            roi: Region of interest for change detection
            threshold: Initial detection threshold (TH_HOLD)
        """
        self._roi = roi
        self._threshold = threshold
        self._frame_t0: Optional[np.ndarray] = None
        self._tracker = HoldHitsTracker()

    @property
    def roi(self) -> ROI:
        """Get the current ROI."""
        return self._roi

    @property
    def threshold(self) -> float:
        """Get the current threshold."""
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        """Set a new threshold."""
        self._threshold = value

    @property
    def hold_hits(self) -> int:
        """Get current consecutive hit count."""
        return self._tracker.hold_hits

    @property
    def frame_t0(self) -> Optional[np.ndarray]:
        """Get the reference frame."""
        return self._frame_t0

    def capture_reference(self) -> np.ndarray:
        """Capture and set the reference frame (frame_t0).

        Returns:
            The captured reference frame
        """
        self._frame_t0 = capture_roi_gray(self._roi)
        self._tracker.reset()
        return self._frame_t0

    def set_reference(self, frame: np.ndarray) -> None:
        """Set reference frame directly (for testing or restore).

        Args:
            frame: Reference frame to use
        """
        self._frame_t0 = frame
        self._tracker.reset()

    def sample(self) -> tuple[float, bool]:
        """Capture current frame and calculate diff.

        Returns:
            Tuple of (diff_value, passed).
            passed is True if hold hits requirement is met.

        Raises:
            ValueError: If reference frame not set
        """
        if self._frame_t0 is None:
            raise ValueError("Reference frame not set. Call capture_reference() first.")

        frame_t = capture_roi_gray(self._roi)
        diff = calculate_diff(frame_t, self._frame_t0, self._roi)
        passed = self._tracker.update(diff, self._threshold)

        return diff, passed

    def reset(self) -> None:
        """Reset the calculator state."""
        self._frame_t0 = None
        self._tracker.reset()

    def calibrate(
        self,
        k_frames: int = CALIB_FRAMES_DEFAULT,
        interval_ms: int = CALIB_INTERVAL_MS,
    ) -> CalibrationStats:
        """Run threshold calibration.

        Args:
            k_frames: Number of frames to capture
            interval_ms: Interval between captures

        Returns:
            CalibrationStats with recommended threshold
        """
        return calibrate_threshold(self._roi, k_frames, interval_ms)

    def freeze_state(self) -> dict:
        """Freeze current state for pause/resume.

        Returns:
            Dictionary with frame_t0 and hold_hits for later restore
        """
        return {
            "frame_t0": self._frame_t0.copy() if self._frame_t0 is not None else None,
            "hold_hits": self._tracker.hold_hits,
        }

    def restore_state(self, state: dict) -> None:
        """Restore state from freeze_state().

        Args:
            state: State dictionary from freeze_state()
        """
        self._frame_t0 = state.get("frame_t0")
        self._tracker._hold_hits = state.get("hold_hits", 0)


