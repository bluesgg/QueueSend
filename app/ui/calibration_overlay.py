"""Calibration overlay for ROI and point selection.

Provides a semi-transparent fullscreen overlay for:
- ROI rectangle/circle selection via drag
- Input point selection via click
- Send point selection via click

See Executable Spec Section 4 for requirements.
"""

from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from app.core.model import Circle, Point, Rect, ROI, ROIShape


class CalibrationMode(Enum):
    """Current calibration mode."""

    NONE = auto()
    ROI = auto()
    INPUT_POINT = auto()
    SEND_POINT = auto()


class CalibrationOverlay(QWidget):
    """Fullscreen overlay for calibration.

    Features:
    - Semi-transparent dark overlay
    - ROI selection via drag (rect or circle)
    - Point selection via click
    - ESC to cancel, Enter to confirm
    """

    # Signals
    roi_selected = Signal(ROI)
    input_point_selected = Signal(Point)
    send_point_selected = Signal(Point)
    cancelled = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Frameless fullscreen window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # State
        self._mode = CalibrationMode.NONE
        self._roi_shape = ROIShape.RECT
        self._is_dragging = False
        self._drag_start: Optional[QPoint] = None
        self._drag_current: Optional[QPoint] = None
        self._current_roi: Optional[ROI] = None
        self._input_point: Optional[Point] = None
        self._send_point: Optional[Point] = None

        # Instructions text
        self._instructions = ""

    def start_roi_selection(self, shape: ROIShape = ROIShape.RECT) -> None:
        """Start ROI selection mode.

        Args:
            shape: ROI shape (RECT or CIRCLE)
        """
        self._mode = CalibrationMode.ROI
        self._roi_shape = shape
        self._is_dragging = False
        self._drag_start = None
        self._drag_current = None

        if shape == ROIShape.RECT:
            self._instructions = "拖拽选择矩形ROI区域 | ESC取消 | Enter确认"
        else:
            self._instructions = "拖拽选择圆形ROI区域(内切圆) | ESC取消 | Enter确认"

        self._show_fullscreen()

    def start_input_point_selection(self) -> None:
        """Start input point selection mode."""
        self._mode = CalibrationMode.INPUT_POINT
        self._instructions = "点击选择输入点(用于抢焦点) | ESC取消"
        self._show_fullscreen()

    def start_send_point_selection(self) -> None:
        """Start send point selection mode."""
        self._mode = CalibrationMode.SEND_POINT
        self._instructions = "点击选择发送按钮位置 | ESC取消"
        self._show_fullscreen()

    def _show_fullscreen(self) -> None:
        """Show overlay covering all screens."""
        # Get virtual desktop geometry
        desktop = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(desktop)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event) -> None:
        """Paint the overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Semi-transparent dark background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

        # Draw current selection
        if self._mode == CalibrationMode.ROI and self._drag_start and self._drag_current:
            self._draw_roi_selection(painter)
        elif self._mode in (CalibrationMode.INPUT_POINT, CalibrationMode.SEND_POINT):
            self._draw_crosshair(painter)

        # Draw instructions
        self._draw_instructions(painter)

        # Draw existing points
        if self._input_point:
            self._draw_point_marker(painter, self._input_point, "输入点", QColor(0, 255, 0))
        if self._send_point:
            self._draw_point_marker(painter, self._send_point, "发送点", QColor(255, 0, 0))

    def _draw_roi_selection(self, painter: QPainter) -> None:
        """Draw the ROI selection rectangle/circle."""
        if not self._drag_start or not self._drag_current:
            return

        rect = self._get_selection_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Clear the ROI area (make it transparent)
        painter.save()

        # Create a path for the overlay with hole
        overlay_path = QPainterPath()
        overlay_path.addRect(self.rect())

        hole_path = QPainterPath()
        if self._roi_shape == ROIShape.CIRCLE:
            # Draw inscribed circle
            cx = rect.x() + rect.width() / 2
            cy = rect.y() + rect.height() / 2
            r = min(rect.width(), rect.height()) / 2
            hole_path.addEllipse(cx - r, cy - r, r * 2, r * 2)
        else:
            hole_path.addRect(rect)

        # Draw selection border
        pen = QPen(QColor(0, 255, 255), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._roi_shape == ROIShape.CIRCLE:
            cx = rect.x() + rect.width() / 2
            cy = rect.y() + rect.height() / 2
            r = min(rect.width(), rect.height()) / 2
            painter.drawEllipse(QPoint(int(cx), int(cy)), int(r), int(r))
            # Also draw bounding rect for reference
            painter.setPen(QPen(QColor(128, 128, 128), 1, Qt.PenStyle.DotLine))
            painter.drawRect(rect)
        else:
            painter.drawRect(rect)

        # Draw dimensions
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        size_text = f"{rect.width()} × {rect.height()}"
        painter.drawText(rect.bottomLeft() + QPoint(4, 20), size_text)

        painter.restore()

    def _draw_crosshair(self, painter: QPainter) -> None:
        """Draw crosshair at cursor position."""
        cursor_pos = self.mapFromGlobal(self.cursor().pos())

        painter.save()
        pen = QPen(QColor(255, 255, 0), 1)
        painter.setPen(pen)

        # Horizontal line
        painter.drawLine(0, cursor_pos.y(), self.width(), cursor_pos.y())
        # Vertical line
        painter.drawLine(cursor_pos.x(), 0, cursor_pos.x(), self.height())

        # Coordinates
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)

        # Get global position for display
        global_pos = self.cursor().pos()
        coord_text = f"({global_pos.x()}, {global_pos.y()})"
        painter.drawText(cursor_pos + QPoint(10, -10), coord_text)

        painter.restore()

    def _draw_instructions(self, painter: QPainter) -> None:
        """Draw instructions at top of screen."""
        painter.save()

        # Background bar
        bar_rect = QRect(0, 0, self.width(), 50)
        painter.fillRect(bar_rect, QColor(0, 0, 0, 200))

        # Text
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, self._instructions)

        painter.restore()

    def _draw_point_marker(
        self,
        painter: QPainter,
        point: Point,
        label: str,
        color: QColor,
    ) -> None:
        """Draw a marker for a selected point."""
        # Convert to local coordinates
        local_x = point.x - self.geometry().x()
        local_y = point.y - self.geometry().y()

        painter.save()

        # Draw crosshair
        pen = QPen(color, 2)
        painter.setPen(pen)
        size = 15
        painter.drawLine(local_x - size, local_y, local_x + size, local_y)
        painter.drawLine(local_x, local_y - size, local_x, local_y + size)

        # Draw circle
        painter.drawEllipse(QPoint(local_x, local_y), 5, 5)

        # Draw label
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(local_x + 10, local_y - 10, label)

        painter.restore()

    def _get_selection_rect(self) -> QRect:
        """Get the current selection rectangle."""
        if not self._drag_start or not self._drag_current:
            return QRect()

        x1, y1 = self._drag_start.x(), self._drag_start.y()
        x2, y2 = self._drag_current.x(), self._drag_current.y()

        # Normalize to ensure positive width/height
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)

        return QRect(left, top, width, height)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == CalibrationMode.ROI:
                self._is_dragging = True
                self._drag_start = event.pos()
                self._drag_current = event.pos()
            elif self._mode == CalibrationMode.INPUT_POINT:
                global_pos = event.globalPos()
                self._input_point = Point(global_pos.x(), global_pos.y())
                self.input_point_selected.emit(self._input_point)
                self.hide()
            elif self._mode == CalibrationMode.SEND_POINT:
                global_pos = event.globalPos()
                self._send_point = Point(global_pos.x(), global_pos.y())
                self.send_point_selected.emit(self._send_point)
                self.hide()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move."""
        if self._is_dragging:
            self._drag_current = event.pos()
            self.update()
        elif self._mode in (CalibrationMode.INPUT_POINT, CalibrationMode.SEND_POINT):
            self.update()  # Update crosshair

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._drag_current = event.pos()
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press."""
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._confirm()

    def _cancel(self) -> None:
        """Cancel calibration."""
        self._mode = CalibrationMode.NONE
        self._is_dragging = False
        self._drag_start = None
        self._drag_current = None
        self.hide()
        self.cancelled.emit()

    def _confirm(self) -> None:
        """Confirm current selection."""
        if self._mode == CalibrationMode.ROI:
            rect = self._get_selection_rect()
            if rect.width() > 0 and rect.height() > 0:
                # Convert to global coordinates
                global_pos = self.geometry().topLeft()
                global_rect = Rect(
                    x=rect.x() + global_pos.x(),
                    y=rect.y() + global_pos.y(),
                    w=rect.width(),
                    h=rect.height(),
                )
                roi = ROI(shape=self._roi_shape, rect=global_rect)
                self._current_roi = roi
                self.roi_selected.emit(roi)
                self.hide()

    def set_existing_points(
        self,
        input_point: Optional[Point] = None,
        send_point: Optional[Point] = None,
    ) -> None:
        """Set existing points to display during calibration.

        Args:
            input_point: Previously selected input point
            send_point: Previously selected send point
        """
        self._input_point = input_point
        self._send_point = send_point

    @property
    def current_roi(self) -> Optional[ROI]:
        """Get the currently selected ROI."""
        return self._current_roi

    @property
    def input_point(self) -> Optional[Point]:
        """Get the selected input point."""
        return self._input_point

    @property
    def send_point(self) -> Optional[Point]:
        """Get the selected send point."""
        return self._send_point

