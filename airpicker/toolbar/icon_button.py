# -*- coding: utf-8 -*-
"""自绘图标按钮：悬停渐亮、按下缩放，刷新按钮点击后转圈。"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    Property as QtProperty,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .icons import ICON_DRAWERS


class ToolbarSeparator(QWidget):
    """工具栏分割线：竖向排列时画横线，横向排列时画竖线。"""

    def __init__(self, horizontal: bool, parent: QWidget):
        super().__init__(parent)
        self._horizontal = horizontal
        self.setObjectName("toolbarSeparator")
        self._apply_size()

    def set_horizontal(self, horizontal: bool) -> None:
        if self._horizontal == horizontal:
            return
        self._horizontal = horizontal
        self._apply_size()
        self.update()

    def _apply_size(self) -> None:
        if self._horizontal:
            self.setFixedSize(12, 44)
        else:
            self.setFixedSize(40, 12)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setPen(QPen(QColor(80, 80, 80), 1))
        if self._horizontal:
            p.drawLine(6, 4, 6, self.height() - 4)
        else:
            p.drawLine(4, 6, self.width() - 4, 6)
        p.end()


class IconButton(QWidget):
    """白色线性图标按钮，交互反馈全部为动画。"""

    def __init__(self, kind: str, parent: QWidget):
        super().__init__(parent)
        self.kind = kind
        self.clicked = None
        self.setFixedSize(40, 44)
        self.setCursor(Qt.ArrowCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._hover = 0.0
        self._press = 0.0
        self._rotation = 0.0
        self._active = False
        self._press_pos: QPoint | None = None
        self._anims: dict[str, QPropertyAnimation] = {}

    def set_kind(self, kind: str) -> None:
        if self.kind != kind:
            self.kind = kind
            self.update()

    def set_active(self, active: bool) -> None:
        """面板展开时保持高亮，收起时恢复普通亮度。"""
        active = bool(active)
        if self._active != active:
            self._active = active
            self.update()

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    def _get_press(self) -> float:
        return self._press

    def _set_press(self, value: float) -> None:
        self._press = value
        self.update()

    def _get_rotation(self) -> float:
        return self._rotation

    def _set_rotation(self, value: float) -> None:
        self._rotation = value
        self.update()

    hover = QtProperty(float, _get_hover, _set_hover)
    press = QtProperty(float, _get_press, _set_press)
    rotation = QtProperty(float, _get_rotation, _set_rotation)

    def _animate(self, name: str, end: float, duration: int, curve=QEasingCurve.OutQuad) -> None:
        anim = QPropertyAnimation(self, name.encode(), self)
        anim.setDuration(duration)
        anim.setStartValue(getattr(self, "_" + name))
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        anim.start()
        self._anims[name] = anim

    def enterEvent(self, event) -> None:
        self._animate("hover", 1.0, 140)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate("hover", 0.0, 180)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
            self._animate("press", 1.0, 90)
        event.ignore()  # 继续交给悬浮工具栏处理拖拽

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._animate("press", 0.0, 160)
            if self._press_pos is not None:
                moved = (event.position().toPoint() - self._press_pos).manhattanLength()
                if moved < 6:
                    if self.kind == "refresh":
                        self._animate(
                            "rotation", self._rotation + 360.0, 700,
                            QEasingCurve.InOutQuad,
                        )
                    if self.clicked:
                        self.clicked()
            self._press_pos = None
        event.ignore()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2

        if self._hover > 0.01 or self._active:
            p.setPen(Qt.NoPen)
            alpha = 10 + 30 * self._hover + (16 if self._active else 0)
            p.setBrush(QColor(255, 255, 255, int(alpha)))
            p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 6, 6)

        p.save()
        scale = 1.0 - 0.08 * self._press
        p.translate(cx, cy)
        p.scale(scale, scale)
        if self.kind == "refresh" and self._rotation:
            p.rotate(self._rotation)
        p.translate(-cx, -cy)

        shade = 255 if self._active else int(235 + 20 * max(self._hover, self._press))
        pen = QPen(QColor(shade, shade, shade), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        drawer = ICON_DRAWERS.get(self.kind)
        if drawer is not None:
            drawer(p, cx, cy)

        p.restore()
        p.end()
