# -*- coding: utf-8 -*-
"""主窗口：编排抓帧渲染、手势、框选、取点与悬浮工具栏。"""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QDialog, QMainWindow

from . import image_utils, settings, template_store
from .config import (
    FRAME_INTERVAL_MS,
    MAX_H,
    MAX_W,
    MIN_SELECT,
    MODE_GESTURE,
    MODE_PICK_COORD,
    MODE_SELECT,
    SWIPE_DURATION,
    TAP_SLOP,
)
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

        self.toolbar = FloatingToolbar()
        self.toolbar.main_window = self
        self.toolbar.set_horizontal(settings.get_toolbar_horizontal(cur_settings))
        self.toolbar.drag_state_changed = self.set_toolbar_dragging
        self.toolbar.settings_clicked = self.open_toolbar_settings
        self.toolbar.select_clicked = self.start_select_mode
        self.toolbar.coord_clicked = self.start_pick_coord
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

    @property
    def picking_coord(self) -> bool:
        return self.interaction_mode == MODE_PICK_COORD

    # -------- 交互模式 --------
    def set_interaction_mode(self, mode: str) -> None:
        """切换模式，并清理上一模式的残留状态。"""
        self.cancel_selection()
        self.cancel_gesture()
        self.interaction_mode = mode
        if mode == MODE_PICK_COORD:
            self.screen.setCursor(Qt.CrossCursor)
            self.setWindowTitle("AirPicker · 取点模式：单击画面获取坐标，右键取消")
        elif mode == MODE_SELECT:
            self.screen.setCursor(Qt.CrossCursor)
            self.setWindowTitle("AirPicker · 框选模式：拖拽框选模板，右键取消")
        else:
            self.screen.unsetCursor()
            self._last_title = ""
            self._update_title()

    def reset_interaction_mode(self) -> None:
        self.set_interaction_mode(MODE_GESTURE)

    def start_select_mode(self) -> None:
        if self.latest_bgr is None:
            print("[提示] 画面尚未就绪，暂时无法框选")
            return
        self.set_interaction_mode(MODE_SELECT)

    # -------- 鼠标模拟触控 / 滑动 --------
    def begin_gesture(self, pos: QPoint) -> None:
        self.gesture_start = pos
        self.gesture_end = pos
        self.gesturing = True
        self.screen.update()

    def update_gesture(self, pos: QPoint) -> None:
        if not self.gesturing:
            return
        self.gesture_end = pos
        self.screen.update()

    def finish_gesture(self, pos: QPoint) -> None:
        if not self.gesturing or self.gesture_start is None:
            self.cancel_gesture()
            return
        start = self.gesture_start
        self.cancel_gesture()
        if (pos - start).manhattanLength() < TAP_SLOP:
            self._tap_device(self.to_source(start))
        else:
            self._swipe_device(self.to_source(start), self.to_source(pos))

    def cancel_gesture(self) -> None:
        self.gesturing = False
        self.gesture_start = self.gesture_end = None
        self.screen.update()

    def _tap_device(self, pos: tuple[int, int]) -> None:
        try:
            self.device.touch(pos)
            print(f"[手势] 点击设备 {pos}")
        except Exception as exc:
            print(f"[警告] 模拟点击失败：{exc}")

    def _swipe_device(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        try:
            self.device.swipe(start, end, duration=SWIPE_DURATION)
            print(f"[手势] 滑动设备 {start} -> {end}")
        except Exception as exc:
            print(f"[警告] 模拟滑动失败：{exc}")

    # -------- 设备按键 --------
    def device_back(self) -> None:
        self._send_key("BACK", "返回")

    def device_home(self) -> None:
        self._send_key("HOME", "主页")

    def _send_key(self, key: str, label: str) -> None:
        try:
            self.device.keyevent(key)
            print(f"[按键] {label}")
        except Exception as exc:
            print(f"[警告] {label}失败：{exc}")

    def open_toolbar_settings(self) -> None:
        cur = settings.load_settings()
        dialog = ToolbarSettingsDialog(
            self.toolbar.is_horizontal(),
            settings.get_resource_dir(cur),
            settings.get_coord_expr(cur),
            settings.get_tpl_expr(cur),
            settings.get_lock_ratio(cur),
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            horizontal = dialog.is_horizontal()
            self.toolbar.set_horizontal(horizontal)
            settings.save_toolbar_horizontal(horizontal)
            settings.save_resource_dir(dialog.resource_dir())
            settings.save_coord_expr(dialog.coord_expr())
            settings.save_tpl_expr(dialog.tpl_expr())
            settings.save_lock_ratio(dialog.lock_ratio())
            self._lock_ratio = dialog.lock_ratio()
            if horizontal:
                self.toolbar.move(
                    self.x() + self.width() - self.toolbar.width() - 20,
                    self.y() + 60,
                )
            self.toolbar.constrain_to_window()

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
        if hasattr(self, "toolbar"):
            self.toolbar.follow_window()

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
        self.reset_interaction_mode()

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
        src_h, src_w = self.frozen_bgr.shape[:2]
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        rx = round(cx / src_w - 0.5, 3) if src_w else 0.0
        ry = round(cy / src_h - 0.5, 3) if src_h else 0.0
        meta = {"rx": rx, "ry": ry, "rw": src_w, "rh": src_h}

        cur = settings.load_settings()
        resource_dir = settings.get_resource_dir(cur)
        tpl_expr = settings.get_tpl_expr(cur)
        template_store.save_template(
            self.frozen_bgr[y1:y2, x1:x2], resource_dir, tpl_expr, meta
        )
        self.frozen_bgr = None

    # -------- 坐标获取 --------
    def start_pick_coord(self) -> None:
        if self.latest_bgr is None:
            print("[提示] 画面尚未就绪，暂时无法取点")
            return
        self.set_interaction_mode(MODE_PICK_COORD)

    def cancel_pick_coord(self) -> None:
        self.reset_interaction_mode()

    def pick_coord(self, pos: QPoint) -> None:
        x, y = self.to_source(pos)
        expr = settings.get_coord_expr(settings.load_settings())
        text = expr.replace("{x}", str(x)).replace("{y}", str(y))
        print(f"[坐标] {text}")
        template_store.copy_text(text, "坐标已复制到剪贴板")
        self.cancel_pick_coord()

    def closeEvent(self, event) -> None:
        self._preview_started = False
        self.timer.stop()
        self._move_resume_timer.stop()
        self._aspect_timer.stop()
        settings.save_window_size(max(1, self.width()), max(1, self.height()))
        self.toolbar.close()
        super().closeEvent(event)
