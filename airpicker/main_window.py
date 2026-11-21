# -*- coding: utf-8 -*-
"""主窗口：编排抓帧渲染、框选、取点与悬浮工具栏。"""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QDialog, QMainWindow

from . import image_utils, template_store
from .config import FRAME_INTERVAL_MS, MAX_H, MAX_W, MIN_SELECT
from .screen_widget import ScreenWidget
from .toolbar import FloatingToolbar, ToolbarSettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, device, screen_wh: tuple[int, int] | None = None):
        super().__init__()
        self.device = device
        self.latest_bgr: np.ndarray | None = None
        self.frozen_bgr: np.ndarray | None = None
        self.drag_start: QPoint | None = None
        self.drag_end: QPoint | None = None
        self.dragging = False
        self.frame_times: list[float] = []
        self._last_title = ""
        self._preview_started = False
        self._preview_paused = False
        self._toolbar_dragging = False
        self._window_moving = False
        self._screen_wh = tuple(screen_wh) if screen_wh else None
        self.picking_coord = False
        self.cursor_pos: QPoint | None = None

        self.setWindowTitle("AirPicker")
        self.screen = ScreenWidget(self)
        self.setCentralWidget(self.screen)
        if self._screen_wh:
            init_w, init_h = self._aspect_size(*self._screen_wh)
            self.resize(init_w, init_h)
        else:
            self.resize(MAX_W, MAX_H)

        self.toolbar = FloatingToolbar()
        self.toolbar.drag_state_changed = self.set_toolbar_dragging
        self.toolbar.settings_clicked = self.open_toolbar_settings
        self.toolbar.coord_clicked = self.start_pick_coord

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_frame)
        self._move_resume_timer = QTimer(self)
        self._move_resume_timer.setSingleShot(True)
        self._move_resume_timer.timeout.connect(self._on_move_resume)

        method = getattr(getattr(device, "screen_proxy", None), "method_name", "MINICAP")
        print(f"[信息] 设备连接成功（{method}）")

    def open_toolbar_settings(self) -> None:
        dialog = ToolbarSettingsDialog(self.toolbar.is_horizontal(), self)
        if dialog.exec() == QDialog.Accepted:
            self.toolbar.set_horizontal(dialog.is_horizontal())
            if self.toolbar.is_horizontal():
                self.toolbar.move(
                    self.x() + self.width() - self.toolbar.width() - 20,
                    self.y() + 60,
                )

    def start(self) -> None:
        self._preview_started = True
        if not self._preview_paused:
            self.timer.start(FRAME_INTERVAL_MS)

    def set_preview_paused(self, paused: bool) -> None:
        self._preview_paused = paused
        if paused:
            if self.timer.isActive():
                self.timer.stop()
        elif self._preview_started and not self.timer.isActive():
            self.timer.start(FRAME_INTERVAL_MS)

    def set_toolbar_dragging(self, dragging: bool) -> None:
        self._toolbar_dragging = dragging
        if dragging:
            self.set_preview_paused(True)
        else:
            self._maybe_resume_preview()

    def _maybe_resume_preview(self) -> None:
        if not self._toolbar_dragging and not self._window_moving:
            self.set_preview_paused(False)

    def moveEvent(self, event) -> None:
        if self._preview_started:
            self._window_moving = True
            self.set_preview_paused(True)
            self._move_resume_timer.start(200)
        super().moveEvent(event)

    def _aspect_size(self, w: int, h: int) -> tuple[int, int]:
        scale = min(MAX_W / w, MAX_H / h)
        return max(1, int(round(w * scale))), max(1, int(round(h * scale)))

    def _sync_window_aspect(self, w: int, h: int) -> None:
        if self._screen_wh == (w, h):
            return
        self._screen_wh = (w, h)

    def _on_move_resume(self) -> None:
        self._window_moving = False
        self._maybe_resume_preview()

    # -------- 抓帧与渲染 --------
    def on_frame(self) -> None:
        if self.dragging or self._preview_paused:
            return
        try:
            raw = self.device.snapshot()
        except Exception as exc:
            print(f"[警告] 截图异常：{exc}")
            return
        arr = image_utils.to_bgr(raw)
        if arr is None:
            return
        self.latest_bgr = arr

        dpr = self.screen.devicePixelRatioF() or 1.0
        display = image_utils.fit_frame(
            arr, max(1, self.screen.width()), max(1, self.screen.height()), dpr
        )
        self.screen.setPixmap(image_utils.to_pixmap(display, dpr))
        h, w = arr.shape[:2]
        self._sync_window_aspect(w, h)

        self.frame_times.append(time.perf_counter())
        self.frame_times = self.frame_times[-20:]
        self._update_title()

    def _fps(self) -> int:
        if len(self.frame_times) < 2:
            return 0
        span = self.frame_times[-1] - self.frame_times[0]
        return int((len(self.frame_times) - 1) / span) if span > 0 else 0

    def _update_title(self) -> None:
        if self.latest_bgr is None:
            return
        h, w = self.latest_bgr.shape[:2]
        pm = self.screen.pixmap()
        if pm:
            dpr = pm.devicePixelRatioF() or 1.0
            dw, dh = pm.width() / dpr, pm.height() / dpr
        else:
            dw, dh = w, h
        title = (
            f"AirPicker · 原图 {w} x {h} · "
            f"显示 {int(round(dw))} x {int(round(dh))} · {self._fps()} FPS"
        )
        if title != self._last_title:
            self.setWindowTitle(title)
            self._last_title = title

    # -------- 框选与保存 --------
    def begin_selection(self, pos: QPoint) -> None:
        if self.latest_bgr is None:
            return
        self.frozen_bgr = self.latest_bgr.copy()
        self.drag_start = pos
        self.drag_end = pos
        self.dragging = True
        self.screen.update()

    def update_selection(self, pos: QPoint) -> None:
        if not self.dragging:
            return
        self.drag_end = pos
        self.screen.update()

    def finish_selection(self, pos: QPoint) -> None:
        if not self.dragging:
            return
        self.drag_end = pos
        self.dragging = False
        self.screen.update()
        self.save_template()

    def cancel_selection(self) -> None:
        self.dragging = False
        self.frozen_bgr = None
        self.drag_start = self.drag_end = None
        self.screen.update()

    def to_source(self, pos: QPoint) -> tuple[int, int]:
        frame = self.frozen_bgr if self.frozen_bgr is not None else self.latest_bgr
        return image_utils.view_to_source(
            pos, frame, self.screen.pixmap(), self.screen.width(), self.screen.height()
        )

    def save_template(self) -> None:
        if self.frozen_bgr is None or self.drag_start is None or self.drag_end is None:
            return
        p1 = self.to_source(self.drag_start)
        p2 = self.to_source(self.drag_end)
        x1, x2 = sorted((p1[0], p2[0]))
        y1, y2 = sorted((p1[1], p2[1]))
        if x2 - x1 < MIN_SELECT or y2 - y1 < MIN_SELECT:
            return
        template_store.save_template(self.frozen_bgr[y1:y2, x1:x2])
        self.frozen_bgr = None

    # -------- 坐标获取 --------
    def start_pick_coord(self) -> None:
        if self.latest_bgr is None:
            print("[提示] 画面尚未就绪，暂时无法取点")
            return
        self.picking_coord = True
        self.screen.setCursor(Qt.CrossCursor)
        self.setWindowTitle("AirPicker · 取点模式：单击画面获取坐标，右键取消")

    def cancel_pick_coord(self) -> None:
        self.picking_coord = False
        self.screen.unsetCursor()
        self._last_title = ""
        self._update_title()

    def pick_coord(self, pos: QPoint) -> None:
        x, y = self.to_source(pos)
        text = f"{x}, {y}"
        print(f"[坐标] {text}")
        template_store.copy_text(text, "坐标已复制到剪贴板")
        self.cancel_pick_coord()

    def closeEvent(self, event) -> None:
        self._preview_started = False
        self.timer.stop()
        self._move_resume_timer.stop()
        self.toolbar.close()
        super().closeEvent(event)
