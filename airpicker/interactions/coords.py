# -*- coding: utf-8 -*-
"""取点模式：单击画面复制设备原图坐标。"""
from __future__ import annotations

from PySide6.QtCore import QPoint

from .. import settings, template_store
from ..config import MODE_PICK_COORD


class CoordPickMixin:
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
