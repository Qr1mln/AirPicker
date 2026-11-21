# -*- coding: utf-8 -*-
"""悬浮工具栏：自绘图标按钮、横竖切换、设置弹窗。"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    Qt,
    Property as QtProperty,
)
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
    """自绘白色线性图标按钮：悬停渐亮、按下缩放，刷新按钮点击后转圈。"""

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
        self._press_pos: QPoint | None = None
        self._anims: dict[str, QPropertyAnimation] = {}

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

        if self._hover > 0.01:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(10 + 30 * self._hover)))
            p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 6, 6)

        p.save()
        scale = 1.0 - 0.08 * self._press
        p.translate(cx, cy)
        p.scale(scale, scale)
        if self.kind == "refresh" and self._rotation:
            p.rotate(self._rotation)
        p.translate(-cx, -cy)

        shade = int(235 + 20 * max(self._hover, self._press))
        pen = QPen(QColor(shade, shade, shade), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        k = self.kind

        if k == "refresh":
            r = 10.0
            box = (int(cx - r), int(cy - r), int(2 * r), int(2 * r))
            p.drawArc(*box, -60 * 16, 255 * 16)
            p.drawArc(*box, 120 * 16, 255 * 16)
            for angle in (-60, 120):
                a = math.radians(angle)
                tip = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
                p.drawLine(tip, QPointF(tip.x() - 4, tip.y() - 1))
                p.drawLine(tip, QPointF(tip.x() + 1, tip.y() - 4))
        elif k == "back":
            p.drawLine(int(cx - 10), int(cy), int(cx + 10), int(cy))
            p.drawLine(int(cx - 10), int(cy), int(cx - 3), int(cy - 7))
            p.drawLine(int(cx - 10), int(cy), int(cx - 3), int(cy + 7))
        elif k == "home":
            p.drawLine(int(cx - 11), int(cy - 1), int(cx), int(cy - 11))
            p.drawLine(int(cx), int(cy - 11), int(cx + 11), int(cy - 1))
            p.drawLine(int(cx - 9), int(cy - 3), int(cx - 9), int(cy + 10))
            p.drawLine(int(cx + 9), int(cy - 3), int(cx + 9), int(cy + 10))
            p.drawLine(int(cx - 9), int(cy + 10), int(cx + 9), int(cy + 10))
            p.drawRect(int(cx - 3), int(cy + 2), 6, 8)
        elif k == "coord":
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            p.drawEllipse(QPointF(cx, cy), 2, 2)
            p.drawLine(int(cx - 13), int(cy), int(cx - 4), int(cy))
            p.drawLine(int(cx + 4), int(cy), int(cx + 13), int(cy))
            p.drawLine(int(cx), int(cy - 13), int(cx), int(cy - 4))
            p.drawLine(int(cx), int(cy + 4), int(cx), int(cy + 13))
        elif k == "select":
            x1, y1, x2, y2 = int(cx - 10), int(cy - 9), int(cx + 10), int(cy + 9)
            for ax, ay, sx, sy in (
                (x1, y1, 1, 1), (x2, y1, -1, 1),
                (x1, y2, 1, -1), (x2, y2, -1, -1),
            ):
                p.drawLine(ax, ay, ax + 5 * sx, ay)
                p.drawLine(ax, ay, ax, ay + 5 * sy)
        elif k == "swipe":
            sx, sy, ex, ey = int(cx - 10), int(cy + 8), int(cx + 10), int(cy - 8)
            p.drawLine(sx, sy, ex, ey)
            p.drawEllipse(QPointF(sx, sy), 2.5, 2.5)
            p.drawLine(ex, ey, ex - 7, ey + 1)
            p.drawLine(ex, ey, ex - 1, ey + 7)
        elif k == "settings":
            teeth = 8
            step = 2 * math.pi / teeth
            outer, inner = 11.0, 8.0
            points = []
            for i in range(teeth):
                base = i * step
                for offset, radius in (
                    (-0.28, outer), (-0.14, outer),
                    (-0.07, inner), (0.07, inner),
                    (0.14, outer), (0.28, outer),
                ):
                    a = base + offset * step / 0.5
                    points.append(QPointF(cx + radius * math.cos(a), cy + radius * math.sin(a)))
            p.drawPolygon(QPolygonF(points))
            p.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
        p.restore()
        p.end()


class FloatingToolbar(QFrame):
    """独立顶层悬浮窗口：无边框，作为主窗口的 owned window 浮于其上方，可鼠标拖拽。"""

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)
        self._drag_pos: QPoint | None = None
        self.drag_state_changed = None
        self.settings_clicked = None
        self.coord_clicked = None
        self.select_clicked = None
        self.swipe_clicked = None
        self.back_clicked = None
        self.home_clicked = None
        self.main_window: QWidget | None = None
        self._window_offset: QPoint | None = None
        self._horizontal = False
        self.setStyleSheet(
            "FloatingToolbar { background: #1e1e1e; border: 1px solid #3a3a3a; }"
        )

        self._inner = QFrame(self)
        self._inner.setObjectName("toolbarPanel")
        self._inner.setStyleSheet("#toolbarPanel { background: transparent; border: none; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._inner)

        self._inner_layout = QBoxLayout(QBoxLayout.TopToBottom, self._inner)
        self._inner_layout.setContentsMargins(0, 4, 0, 4)
        self._inner_layout.setSpacing(0)
        for kind in ("refresh", "back", "home", "settings"):
            btn = IconButton(kind, self._inner)
            btn.setObjectName("toolbarIcon")
            if kind == "back":
                btn.clicked = self._go_back
            elif kind == "home":
                btn.clicked = self._go_home
            elif kind == "settings":
                btn.clicked = self._open_settings
            self._inner_layout.addWidget(btn)
        self._separator = ToolbarSeparator(False, self._inner)
        self._inner_layout.addWidget(self._separator)
        for kind, callback in (
            ("coord", self._pick_coord),
            ("select", self._select_template),
            ("swipe", self._start_swipe),
        ):
            btn = IconButton(kind, self._inner)
            btn.setObjectName("toolbarIcon")
            btn.clicked = callback
            self._inner_layout.addWidget(btn)
        self._apply_orientation()

    def _go_back(self) -> None:
        if self.back_clicked:
            self.back_clicked()

    def _go_home(self) -> None:
        if self.home_clicked:
            self.home_clicked()

    def _open_settings(self) -> None:
        if self.settings_clicked:
            self.settings_clicked()

    def _select_template(self) -> None:
        if self.select_clicked:
            self.select_clicked()

    def _pick_coord(self) -> None:
        if self.coord_clicked:
            self.coord_clicked()

    def _start_swipe(self) -> None:
        if self.swipe_clicked:
            self.swipe_clicked()

    def is_horizontal(self) -> bool:
        return self._horizontal

    def set_horizontal(self, horizontal: bool) -> None:
        if self._horizontal == horizontal:
            return
        self._horizontal = horizontal
        self._apply_orientation()

    def _apply_orientation(self) -> None:
        self._separator.set_horizontal(self._horizontal)
        if self._horizontal:
            self._inner_layout.setDirection(QBoxLayout.LeftToRight)
            self.setFixedSize(324, 60)
        else:
            self._inner_layout.setDirection(QBoxLayout.TopToBottom)
            self.setFixedSize(56, 344)

    def _clamp_pos(self, pos: QPoint) -> QPoint:
        window = self.main_window
        if window is None:
            return pos
        bounds = window.geometry()
        if bounds.width() < 1 or bounds.height() < 1:
            return pos
        x = max(bounds.left(), min(pos.x(), bounds.right() - self.width() + 1))
        y = max(bounds.top(), min(pos.y(), bounds.bottom() - self.height() + 1))
        return QPoint(x, y)

    def constrain_to_window(self) -> None:
        target = self._clamp_pos(self.pos())
        if target != self.pos():
            self.move(target)
        self.sync_offset()

    def sync_offset(self) -> None:
        """记录工具栏相对主窗口左上角的偏移。"""
        if self.main_window is not None:
            self._window_offset = self.pos() - self.main_window.pos()

    def follow_window(self) -> None:
        """主窗口移动时按记录的偏移跟随。"""
        if self.main_window is None or self._window_offset is None:
            self.constrain_to_window()
            return
        self.move(self._clamp_pos(self.main_window.pos() + self._window_offset))

    def raise_above_main(self) -> None:
        """把工具栏 Z 序抬到主窗口之上（非全局置顶，不遮挡其他程序）。"""
        if self.main_window is None:
            return
        try:
            import win32con
            import win32gui

            toolbar_hwnd = int(self.winId())
            main_hwnd = int(self.main_window.winId())
            win32gui.SetWindowPos(
                toolbar_hwnd, main_hwnd, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
        except Exception as exc:
            print(f"[警告] 抬升工具栏失败：{exc}")
            self.raise_()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)
            if self.drag_state_changed:
                self.drag_state_changed(True)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None:
            self.move(self._clamp_pos(event.globalPosition().toPoint() - self._drag_pos))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            self.sync_offset()
            self.unsetCursor()
            if self.drag_state_changed:
                self.drag_state_changed(False)


class ToolbarSettingsDialog(QDialog):
    """悬浮工具栏设置：横 / 竖排列、模板资源目录。"""

    def __init__(
        self,
        horizontal: bool,
        resource_dir: Path | str = "",
        coord_expr: str = "({x}, {y})",
        tpl_expr: str = 'Template(r"{name}", record_pos=({rx}, {ry}), resolution=({rw}, {rh}))',
        swipe_expr: str = "swipe(({x1}, {y1}), ({x2}, {y2}))",
        lock_ratio: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.combo = QComboBox()
        self.combo.addItem("竖向", False)
        self.combo.addItem("横向", True)
        self.combo.setCurrentIndex(1 if horizontal else 0)
        form.addRow("工具栏排列", self.combo)

        self.aspect_check = QCheckBox("窗口缩放时保持画面宽高比")
        self.aspect_check.setChecked(bool(lock_ratio))
        form.addRow("", self.aspect_check)

        dir_widget = QWidget()
        dir_row = QHBoxLayout(dir_widget)
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.setSpacing(6)
        self.dir_edit = QLineEdit(str(resource_dir))
        self.dir_edit.setPlaceholderText("留空则使用项目 pics 目录")
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse)
        form.addRow("资源目录", dir_widget)

        self.expr_edit = QLineEdit(coord_expr)
        form.addRow("坐标回写", self.expr_edit)
        coord_hint = QLabel("变量：{x}=X坐标，{y}=Y坐标（可任意组合，如 ({x}, {y})）")
        coord_hint.setStyleSheet("color: #888; font-size: 11px;")
        coord_hint.setWordWrap(True)
        form.addRow("", coord_hint)

        self.tpl_edit = QLineEdit(tpl_expr)
        form.addRow("模板回写", self.tpl_edit)
        tpl_hint = QLabel(
            "变量：{name}=文件名，{path}=相对路径，\n"
            "{rx}/{ry}=模板中心偏移(-0.5~0.5)，{rw}/{rh}=屏幕宽高（可任意组合）"
        )
        tpl_hint.setStyleSheet("color: #888; font-size: 11px;")
        tpl_hint.setWordWrap(True)
        form.addRow("", tpl_hint)

        self.swipe_edit = QLineEdit(swipe_expr)
        form.addRow("滑动回写", self.swipe_edit)
        swipe_hint = QLabel("变量：{x1}/{y1}=起点，{x2}/{y2}=终点（可任意组合）")
        swipe_hint.setStyleSheet("color: #888; font-size: 11px;")
        swipe_hint.setWordWrap(True)
        form.addRow("", swipe_hint)

        root.addLayout(form)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.setFixedWidth(84)
        cancel.setFixedWidth(84)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

    def is_horizontal(self) -> bool:
        return bool(self.combo.currentData())

    def _browse_dir(self) -> None:
        start = self.dir_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择资源目录", start)
        if chosen:
            self.dir_edit.setText(chosen)

    def resource_dir(self) -> str:
        return self.dir_edit.text().strip()

    def coord_expr(self) -> str:
        return self.expr_edit.text().strip()

    def tpl_expr(self) -> str:
        return self.tpl_edit.text().strip()

    def swipe_expr(self) -> str:
        return self.swipe_edit.text().strip()

    def lock_ratio(self) -> bool:
        return self.aspect_check.isChecked()
