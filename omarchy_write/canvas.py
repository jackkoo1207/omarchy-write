"""Drawing canvas that captures pen/mouse/touchpad strokes."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class StrokeCanvas(QWidget):
    strokeFinished = Signal()
    strokeStarted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strokes: list[list] = []
        self._current: list | None = None
        self._ink = QColor(24, 24, 24)
        self._pen_width = 12
        self.setMinimumSize(220, 170)

    # -- public --
    def normalized_strokes(self):
        # Uniform scale (max dim) so the aspect ratio of the drawn strokes is
        # preserved — dividing x and y by different dims would distort shapes.
        s = max(self.width(), self.height(), 1)
        return [[(p.x() / s, p.y() / s) for p in stroke] for stroke in self._strokes]

    def has_strokes(self) -> bool:
        return bool(self._strokes)

    def clear(self):
        self._strokes = []
        self._current = None
        self.update()

    # -- events --
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.strokeStarted.emit()
            self._current = [e.position()]
            self.update()

    def mouseMoveEvent(self, e):
        if self._current is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            self._current.append(e.position())
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._current is not None:
            if len(self._current) >= 1:
                self._strokes.append(self._current)
            self._current = None
            self.update()
            self.strokeFinished.emit()

    # -- paint --
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # rounded white "paper" background
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        p.fillPath(path, QColor(255, 255, 255))
        pen = QPen(
            self._ink,
            self._pen_width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for s in self._strokes:
            self._draw_stroke(p, s)
        if self._current:
            self._draw_stroke(p, self._current)
        p.end()

    def _draw_stroke(self, p: QPainter, pts):
        if len(pts) == 1:
            p.drawPoint(pts[0])
        else:
            path = QPainterPath(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            p.drawPath(path)

    # -- remote (touchpad) stroke API: pixel coords, called from main thread --
    def remote_move(self, x: float, y: float):
        if self._current is None:
            self.strokeStarted.emit()
            self._current = [QPointF(x, y)]
        else:
            self._current.append(QPointF(x, y))
        self.update()

    def remote_end(self, commit: bool = True):
        if self._current is not None:
            if commit and self._current:
                self._strokes.append(self._current)
            self._current = None
            self.update()
            if commit:
                self.strokeFinished.emit()
