# -*- coding: utf-8 -*-
"""框选模板：冻结画面、绘制选区、裁剪保存并生成代码。"""
from __future__ import annotations

from PySide6.QtCore import QPoint

from .. import image_utils, settings, template_store
from ..config import MIN_SELECT


class SelectionMixin:
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
        project_dir = settings.get_project_dir(cur)
        tpl_expr = settings.get_tpl_expr(cur)
        template_store.save_template(
            self.frozen_bgr[y1:y2, x1:x2], resource_dir, tpl_expr, meta, project_dir
        )
        self.frozen_bgr = None
