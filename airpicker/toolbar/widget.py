# -*- coding: utf-8 -*-
"""主窗口的无边框子部件：天然浮于父窗口之上、随之移动/最小化，可鼠标拖拽。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QBoxLayout, QFrame, QVBoxLayout, QWidget

from .icon_button import IconButton, ToolbarSeparator


class FloatingToolbar(QFrame):
    """黑色面板 + 白色线性图标的可拖拽悬浮工具栏。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.FramelessWindowHint)
        self._drag_pos: QPoint | None = None
        self.drag_state_changed = None
        self.settings_clicked = None
        self.connection_toggled = None
        self.screenshot_clicked = None
        self.coord_clicked = None
        self.select_clicked = None
        self.swipe_clicked = None
        self.back_clicked = None
        self.home_clicked = None
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
        for kind in ("refresh", "connect", "back", "home", "screenshot", "settings"):
            btn = IconButton(kind, self._inner)
            btn.setObjectName("toolbarIcon")
            if kind == "connect":
                btn.clicked = self._toggle_connection
                self._connect_btn = btn
            elif kind == "back":
                btn.clicked = self._go_back
            elif kind == "home":
                btn.clicked = self._go_home
            elif kind == "screenshot":
                btn.clicked = self._capture_screenshot
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

    def _toggle_connection(self) -> None:
        if self.connection_toggled:
            self.connection_toggled()

    def set_connected(self, connected: bool) -> None:
        """根据连接状态切换按钮图标：已连接显示断开，未连接显示连接。"""
        self._connect_btn.set_kind("disconnect" if connected else "connect")

    def _go_back(self) -> None:
        if self.back_clicked:
            self.back_clicked()

    def _go_home(self) -> None:
        if self.home_clicked:
            self.home_clicked()

    def _capture_screenshot(self) -> None:
        if self.screenshot_clicked:
            self.screenshot_clicked()

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
            self.setFixedSize(392, 60)
        else:
            self._inner_layout.setDirection(QBoxLayout.TopToBottom)
            self.setFixedSize(56, 432)

    def _clamp_pos(self, pos: QPoint) -> QPoint:
        parent = self.parentWidget()
        if parent is None:
            return pos
        x = max(0, min(pos.x(), parent.width() - self.width()))
        y = max(0, min(pos.y(), parent.height() - self.height()))
        return QPoint(x, y)

    def constrain_to_window(self) -> None:
        target = self._clamp_pos(self.pos())
        if target != self.pos():
            self.move(target)

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
            self.unsetCursor()
            if self.drag_state_changed:
                self.drag_state_changed(False)
