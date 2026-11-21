# -*- coding: utf-8 -*-
"""实时投屏画面显示：框选、取点、鼠标实时坐标标签。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel

if TYPE_CHECKING:
    from .main_window import MainWindow


class ScreenWidget(QLabel):
    """实时画面显示，左键拖拽框选、右键取消。"""

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.app = parent
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 300)

    def mousePressEvent(self, event) -> None:
        if self.app.picking_coord:
            if event.button() == Qt.LeftButton:
                self.app.pick_coord(event.position().toPoint())
            elif event.button() == Qt.RightButton:
                self.app.cancel_pick_coord()
            return
        if event.button() == Qt.LeftButton:
            self.app.begin_selection(event.position().toPoint())
        elif event.button() == Qt.RightButton:
            self.app.cancel_selection()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        self.app.cursor_pos = pos
        self.update()
        if self.app.picking_coord:
            return
        self.app.update_selection(pos)

    def leaveEvent(self, event) -> None:
        self.app.cursor_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.app.picking_coord:
            return
        if event.button() == Qt.LeftButton:
            self.app.finish_selection(event.position().toPoint())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.app.dragging and self.app.drag_start and self.app.drag_end:
            rect = QRect(self.app.drag_start, self.app.drag_end).normalized()
            painter.setPen(QPen(QColor(40, 167, 69), 2))
            painter.setBrush(Qt.transparent)
            painter.drawRect(rect)
        pos = self.app.cursor_pos
        if pos is not None and self.app.latest_bgr is not None:
            x, y = self.app.to_source(pos)
            text = f"{x}, {y}"
            fm = painter.fontMetrics()
            tw, th = fm.horizontalAdvance(text), fm.height()
            bx, by = pos.x() + 14, pos.y() + 14
            if bx + tw + 12 > self.width():
                bx = pos.x() - tw - 20
            if by + th + 10 > self.height():
                by = pos.y() - th - 16
            bx, by = max(0, bx), max(0, by)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 20, 210))
            painter.drawRoundedRect(bx, by, tw + 12, th + 8, 4, 4)
            painter.setPen(QColor(240, 240, 240))
            painter.drawText(bx + 6, by + 4 + fm.ascent(), text)
        painter.end()
