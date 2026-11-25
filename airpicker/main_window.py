# -*- coding: utf-8 -*-
"""主窗口：编排抓帧渲染、窗口事件，交互能力由 interactions 中的 Mixin 提供。"""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QPoint, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow

from . import image_utils, settings
from .ai import AIAddon
from .capture_worker import CaptureWorker
from .config import APP_ICON, MAX_H, MAX_W, MODE_GESTURE
from .interactions import (
    CoordPickMixin,
    DeviceConnectionMixin,
    DeviceKeyMixin,
    GestureMixin,
    InteractionModeMixin,
    PreferencesMixin,
    ScreenshotMixin,
    SelectionMixin,
)
from .screen_widget import ScreenWidget
from .toolbar import FloatingToolbar


class MainWindow(
    InteractionModeMixin,
    GestureMixin,
    SelectionMixin,
    CoordPickMixin,
    DeviceConnectionMixin,
    DeviceKeyMixin,
    PreferencesMixin,
    ScreenshotMixin,
    QMainWindow,
):
    connectionStateChanged = Signal(str, bool, bool)  # 状态文本、可连接、可断开

    def __init__(self, device=None, screen_wh: tuple[int, int] | None = None):
        super().__init__()
        self.device = device
        self._connecting = False
        self._connect_worker = None
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
        self._closing = False
        self._capture_worker: CaptureWorker | None = None
        self._toolbar_dragging = False
        self._window_moving = False
        self._screen_wh = tuple(screen_wh) if screen_wh else None
        self._resizing_aspect = False
        self.interaction_mode = MODE_GESTURE
        self.cursor_pos: QPoint | None = None

        cur_settings = settings.load_settings()
        self._lock_ratio = settings.get_lock_ratio(cur_settings)

        self.setWindowTitle("AirPicker · 未连接设备" if device is None else "AirPicker")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.screen = ScreenWidget(self)
        self.setCentralWidget(self.screen)
        if device is None:
            self.screen.setText("未连接设备\n请在设置中点击「连接设备」")
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
        self.toolbar.connection_toggled = self.toggle_connection
        self.connectionStateChanged.connect(self._on_connection_state_for_toolbar)
        self.toolbar.screenshot_clicked = self.capture_screenshot
        self.toolbar.select_clicked = self.start_select_mode
        self.toolbar.coord_clicked = self.start_pick_coord
        self.toolbar.swipe_clicked = self.start_swipe_mode
        self.toolbar.back_clicked = self.device_back
        self.toolbar.home_clicked = self.device_home

        self.ai_addon = AIAddon(self)

        self._move_resume_timer = QTimer(self)
        self._move_resume_timer.setSingleShot(True)
        self._move_resume_timer.timeout.connect(self._on_move_resume)
        self._aspect_timer = QTimer(self)
        self._aspect_timer.setSingleShot(True)
        self._aspect_timer.timeout.connect(self._apply_aspect_ratio)

        if device is not None:
            method = getattr(getattr(device, "screen_proxy", None), "method_name", "MINICAP")
            print(f"[信息] 设备连接成功（{method}）")
            print("[信息] 默认模式：单击=点击设备，拖拽=滑动设备；工具栏可切换框选 / 取点")
        else:
            print("[信息] 未连接设备，可在设置中连接或开启自动连接")

    # -------- 预览与窗口事件 --------
    def start(self) -> None:
        """界面加载完成后调用：按需启动预览并尝试自动连接。"""
        self._preview_started = True
        self._maybe_start_preview()
        if settings.get_auto_connect(settings.load_settings()):
            QTimer.singleShot(0, self.connect_device)

    def _sync_view_params(self) -> None:
        if self._capture_worker is not None:
            self._capture_worker.set_view_params(
                self.screen.width(), self.screen.height(),
                self.screen.devicePixelRatioF() or 1.0, self._lock_ratio,
            )

    def _maybe_start_preview(self) -> None:
        if (
            self._preview_started
            and self.device is not None
            and not self._preview_paused
            and not self._closing
            and self._capture_worker is None
        ):
            worker = CaptureWorker(self.device, self)
            worker.frame_ready.connect(self._on_frame_ready)
            worker.capture_failed.connect(self._on_capture_failed)
            worker.device_waiting.connect(self._on_device_waiting)
            worker.device_recovered.connect(self._on_device_recovered)
            self._capture_worker = worker
            self._sync_view_params()
            worker.start()

    def _stop_capture(self) -> None:
        worker = self._capture_worker
        self._capture_worker = None
        if worker is not None:
            worker.requestInterruption()
            # snapshot 可能正阻塞在 minicap recv，超时后由 worker 自行退出
            worker.wait(3000)

    def set_preview_paused(self, paused: bool) -> None:
        if not paused and self._closing:
            return
        self._preview_paused = paused
        if self._capture_worker is not None:
            self._capture_worker.set_paused(paused)

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
        self._sync_view_params()
        if self._resizing_aspect:
            return
        self._aspect_timer.start(120)

    def _apply_aspect_ratio(self) -> None:
        """保存用户手动调整后的窗口尺寸；停靠面板模式下不再强制校正比例。"""
        cw, ch = self.width(), self.height()
        if cw <= 0 or ch <= 0:
            return
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
    def _on_frame_ready(self, bgr, display, dpr: float) -> None:
        """worker 已完成 snapshot 与缩放，UI 线程只做 QPixmap 渲染。"""
        if self._closing or self._preview_paused:
            return
        self.latest_bgr = bgr
        self.screen.setPixmap(image_utils.to_pixmap(display, dpr))
        h, w = bgr.shape[:2]
        self._sync_window_aspect(w, h)

        self.frame_times.append(time.perf_counter())
        self.frame_times = self.frame_times[-20:]
        self._update_title()

    def _on_capture_failed(self, detail: str) -> None:
        print(f"[警告] 截图异常：{detail}")

    def _on_device_waiting(self) -> None:
        print("[信息] 连续截图失败，已降频等待设备恢复")

    def _on_device_recovered(self) -> None:
        print("[信息] 设备画面已恢复，继续预览")

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
        self._closing = True
        self._preview_started = False
        self._move_resume_timer.stop()
        self._aspect_timer.stop()
        self._stop_capture()
        if self._connect_worker is not None:
            self._connect_worker.requestInterruption()
        settings.save_window_size(max(1, self.width()), max(1, self.height()))
        super().closeEvent(event)
