# -*- coding: utf-8 -*-
"""交互模式切换：统一清理上一模式状态并设置光标/标题提示。"""
from __future__ import annotations

from PySide6.QtCore import Qt

from ..config import MODE_GESTURE, MODE_PICK_COORD, MODE_SELECT, MODE_SWIPE


class InteractionModeMixin:
    @property
    def picking_coord(self) -> bool:
        return self.interaction_mode == MODE_PICK_COORD

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
        elif mode == MODE_SWIPE:
            self.screen.setCursor(Qt.CrossCursor)
            self.setWindowTitle("AirPicker · 滑动模式：拖拽起点到终点生成 swipe 代码，右键取消")
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

    def start_swipe_mode(self) -> None:
        if self.latest_bgr is None:
            print("[提示] 画面尚未就绪，暂时无法滑动取码")
            return
        self.set_interaction_mode(MODE_SWIPE)
