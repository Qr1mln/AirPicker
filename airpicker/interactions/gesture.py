# -*- coding: utf-8 -*-
"""默认鼠标模拟触控，以及滑动取码模式。"""
from __future__ import annotations

from PySide6.QtCore import QPoint

from .. import settings, template_store
from ..config import SWIPE_DURATION, TAP_SLOP


class GestureMixin:
    # -------- 滑动命令 --------
    def begin_swipe(self, pos: QPoint) -> None:
        self.gesture_start = pos
        self.gesture_end = pos
        self.gesturing = True
        self.screen.update()

    def update_swipe(self, pos: QPoint) -> None:
        if not self.gesturing:
            return
        self.gesture_end = pos
        self.screen.update()

    def finish_swipe(self, pos: QPoint) -> None:
        if not self.gesturing or self.gesture_start is None:
            self.cancel_gesture()
            return
        start = self.gesture_start
        self.cancel_gesture()
        x1, y1 = self.to_source(start)
        x2, y2 = self.to_source(pos)
        expr = settings.get_swipe_expr(settings.load_settings())
        template_store.copy_swipe(x1, y1, x2, y2, expr)
        self.reset_interaction_mode()

    def cancel_swipe(self) -> None:
        self.cancel_gesture()
        self.reset_interaction_mode()

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
