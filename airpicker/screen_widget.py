# -*- coding: utf-8 -*-
"""实时投屏画面显示：模式化鼠标交互、框选、取点与实时坐标标签。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel

from .config import MODE_GESTURE, MODE_PICK_COORD, MODE_SELECT, MODE_SWIPE

if TYPE_CHECKING:
    from .main_window import MainWindow


class ScreenWidget(QLabel):
    """实时画面显示，按当前交互模式分发鼠标事件。

    - 默认：单击模拟设备点击，拖拽模拟设备滑动；
    - 框选模式：左键拖拽框选模板，右键取消；
    - 取点模式：单击获取设备坐标，右键取消（触控 / 滑动失效）。
    """

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.app = parent
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 300)

    def mousePressEvent(self, event) -> None:
        mode = self.app.interaction_mode
        if mode == MODE_PICK_COORD:
            if event.button() == Qt.LeftButton:
                self.app.pick_coord(event.position().toPoint())
            elif event.button() == Qt.RightButton:
                self.app.cancel_pick_coord()
            return
        if mode == MODE_SELECT:
            if event.button() == Qt.LeftButton:
                self.app.begin_selection(event.position().toPoint())
            elif event.button() == Qt.RightButton:
                self.app.cancel_selection()
            return
        if mode == MODE_SWIPE:
            if event.button() == Qt.LeftButton:
                self.app.begin_swipe(event.position().toPoint())
            elif event.button() == Qt.RightButton:
                self.app.cancel_swipe()
            return
        if event.button() == Qt.LeftButton:
            self.app.begin_gesture(event.position().toPoint())

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        self.app.cursor_pos = pos
        self.update()
        mode = self.app.interaction_mode
        if mode == MODE_PICK_COORD:
            return
        if mode == MODE_SELECT:
            self.app.update_selection(pos)
        elif mode == MODE_SWIPE:
            self.app.update_swipe(pos)
        else:
            self.app.update_gesture(pos)

    def leaveEvent(self, event) -> None:
        self.app.cursor_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        mode = self.app.interaction_mode
        if mode == MODE_PICK_COORD:
            return
        if mode == MODE_SELECT:
            self.app.finish_selection(pos)
        elif mode == MODE_SWIPE:
            self.app.finish_swipe(pos)
        else:
            self.app.finish_gesture(pos)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if (
            self.app.interaction_mode in (MODE_GESTURE, MODE_SWIPE)
            and self.app.gesturing
            and self.app.gesture_start is not None
            and self.app.gesture_end is not None
            and self.app.gesture_start != self.app.gesture_end
        ):
            color = (
                QColor(80, 170, 255, 210)
                if self.app.interaction_mode == MODE_SWIPE
                else QColor(255, 200, 60, 190)
            )
            painter.setPen(QPen(color, 2))
            painter.drawLine(self.app.gesture_start, self.app.gesture_end)
            for pt in (self.app.gesture_start, self.app.gesture_end):
                painter.setBrush(color)
                painter.drawEllipse(pt, 3, 3)
                painter.setBrush(Qt.NoBrush)
        if self.app.dragging and self.app.drag_start and self.app.drag_end:
            rect = QRect(self.app.drag_start, self.app.drag_end).normalized()
            pen = QPen(QColor(40, 167, 69), 4)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.transparent)
            painter.drawRect(rect)
        pos = self.app.cursor_pos
        if pos is not None and self.app.latest_bgr is not None:
            x, y = self.app.to_source(pos)
            mode = self.app.interaction_mode
            coord_text = f"{x}, {y}"
            hint_text = ""
            if mode == MODE_PICK_COORD:
                hint_text = "坐标：单击取点"
            elif mode == MODE_SELECT:
                hint_text = "框选模板：拖拽框选"
            elif mode == MODE_SWIPE:
                hint_text = "滑动：拖拽起点→终点生成代码"

            fm = painter.fontMetrics()
            line_h = fm.height()
            lines = 1 if not hint_text else 2
            tw = max(fm.horizontalAdvance(coord_text), fm.horizontalAdvance(hint_text))
            pad_x, pad_y = 8, 6
            box_w, box_h = tw + pad_x * 2, line_h * lines + pad_y * 2
            bx, by = pos.x() + 14, pos.y() + 14
            if bx + box_w > self.width():
                bx = pos.x() - box_w - 14
            if by + box_h > self.height():
                by = pos.y() - box_h - 14
            bx, by = max(0, bx), max(0, by)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 20, 215))
            painter.drawRoundedRect(bx, by, box_w, box_h, 5, 5)
            painter.setPen(QColor(240, 240, 240))
            painter.drawText(bx + pad_x, by + pad_y + fm.ascent(), coord_text)
            if hint_text:
                painter.setPen(QColor(255, 200, 60))
                painter.drawText(bx + pad_x, by + pad_y + line_h + fm.ascent(), hint_text)
        painter.end()
