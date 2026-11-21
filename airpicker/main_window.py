# -*- coding: utf-8 -*-
"""主窗口：编排抓帧渲染、窗口事件，交互能力由 interactions 中的 Mixin 提供。"""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QMainWindow

from . import image_utils, settings
from .config import FRAME_INTERVAL_MS, MAX_H, MAX_W, MODE_GESTURE
from .interactions import (
    CoordPickMixin,
    DeviceKeyMixin,
    GestureMixin,
    InteractionModeMixin,
    PreferencesMixin,
    SelectionMixin,
)
from .screen_widget import ScreenWidget
from .toolbar import FloatingToolbar


class MainWindow(
    InteractionModeMixin,
    GestureMixin,
    SelectionMixin,
    CoordPickMixin,
    DeviceKeyMixin,
    PreferencesMixin,
    QMainWindow,
):
    def __init__(self, device, screen_wh: tuple[int, int] | None = None):
        super().__init__()
        self.device = device
        self.latest_bgr: np.ndarray | None = None
        self.frozen_bgr: np.ndarray | None = None
        self.drag_start: QPoint | None = None
        self.drag_end: QPoint | None = None
        self.dragging = False
        self.gesture_start: QPoint | None = None
        self.gesture_end: QPoint | None = None
        self.gesturing = False
        self.frame_times: list[float] = []
        self._last_title = ""
        self._preview_started = False
        self._preview_paused = False
        self._toolbar_dragging = False
        self._window_moving = False
        self._screen_wh = tuple(screen_wh) if screen_wh else None
        self._resizing_aspect = False
        self.interaction_mode = MODE_GESTURE
        self.cursor_pos: QPoint | None = None

        cur_settings = settings.load_settings()
        self._lock_ratio = settings.get_lock_ratio(cur_settings)

        self.setWindowTitle("AirPicker")
        self.screen = ScreenWidget(self)
        self.setCentralWidget(self.screen)
        saved_size = settings.get_window_size(cur_settings)
        if saved_size:
            self.resize(*saved_size)
        elif self._screen_wh:
            init_w, init_h = self._aspect_size(*self._screen_wh)
            self.resize(init_w, init_h)
        else:
            self.resize(MAX_W, MAX_H)

        self.toolbar = FloatingToolbar(self)
        self.toolbar.set_horizontal(settings.get_toolbar_horizontal(cur_settings))
        self.toolbar.drag_state_changed = self.set_toolbar_dragging
        self.toolbar.settings_clicked = self.open_toolbar_settings
        self.toolbar.select_clicked = self.start_select_mode
        self.toolbar.coord_clicked = self.start_pick_coord
        self.toolbar.swipe_clicked = self.start_swipe_mode
        self.toolbar.back_clicked = self.device_back
        self.toolbar.home_clicked = self.device_home

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_frame)
        self._move_resume_timer = QTimer(self)
        self._move_resume_timer.setSingleShot(True)
        self._move_resume_timer.timeout.connect(self._on_move_resume)
        self._aspect_timer = QTimer(self)
        self._aspect_timer.setSingleShot(True)
        self._aspect_timer.timeout.connect(self._apply_aspect_ratio)

        method = getattr(getattr(device, "screen_proxy", None), "method_name", "MINICAP")
        print(f"[信息] 设备连接成功（{method}）")
        print("[信息] 默认模式：单击=点击设备，拖拽=滑动设备；工具栏可切换框选 / 取点")

    # -------- 预览与窗口事件 --------
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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toolbar"):
            self.toolbar.constrain_to_window()
        if self._resizing_aspect:
            return
        self._aspect_timer.start(120)

    def _apply_aspect_ratio(self) -> None:
        """拖拽停止后按比例校正一次并保存尺寸，避免在 resizeEvent 内同步 resize 造成抖动。"""
        cw, ch = self.width(), self.height()
        if cw <= 0 or ch <= 0:
            return

        if self._lock_ratio and self._screen_wh:
            src_w, src_h = self._screen_wh
            if src_w > 0 and src_h > 0:
                w_by_h = max(1, round(ch * src_w / src_h))
                h_by_w = max(1, round(cw * src_h / src_w))
                if abs(w_by_h - cw) <= abs(h_by_w - ch):
                    target = (w_by_h, ch)
                else:
                    target = (cw, h_by_w)
                if target != (cw, ch):
                    self._resizing_aspect = True
                    try:
                        self.resize(*target)
                    finally:
                        self._resizing_aspect = False
                    cw, ch = target

        settings.save_window_size(cw, ch)

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
        if self.latest_bgr is None or self.interaction_mode != MODE_GESTURE:
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

    def closeEvent(self, event) -> None:
        self._preview_started = False
        self.timer.stop()
        self._move_resume_timer.stop()
        self._aspect_timer.stop()
        settings.save_window_size(max(1, self.width()), max(1, self.height()))
        super().closeEvent(event)
