# -*- coding: utf-8 -*-
"""全屏截图：按设备原图分辨率保存到独立目录，并触发画面高亮反馈。"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .. import image_utils, screenshot_names, settings


class ScreenshotMixin:
    def capture_screenshot(self) -> None:
        frame = self._screenshot_frame()
        if frame is None:
            print("[警告] 暂无画面，截图失败")
            return
        cur = settings.load_settings()
        out_dir = settings.get_screenshot_dir(cur)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            name, next_number = self._screenshot_name(cur, out_dir)
            path = out_dir / name
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(path)
            if next_number is not None:
                settings.save_screenshot_seq_next(next_number)
        except Exception as exc:
            print(f"[警告] 截图保存失败：{exc}")
            return
        self.screen.flash_screenshot()
        print(f"[截图] 全屏截图已保存：{path.as_posix()}")

    @staticmethod
    def _screenshot_name(cur: dict, out_dir: Path) -> tuple[str, int | None]:
        """返回文件名与下一个序号计数；随机模式不返回计数。"""
        is_sequence = (
            settings.get_screenshot_name_mode(cur) == screenshot_names.SCREENSHOT_NAME_SEQUENCE
        )
        if is_sequence:
            expr = settings.get_screenshot_seq_expr(cur)
            number = screenshot_names.resolve_sequence_number(
                out_dir, expr, settings.get_screenshot_seq_next(cur)
            )
            return screenshot_names.render_name(expr, number), number + 1

        expr = settings.get_screenshot_random_expr(cur)
        name = screenshot_names.render_name(expr)
        suffix = 0
        while (out_dir / name).exists():
            suffix += 1
            stem, ext = (name[:-4], ".png") if name.lower().endswith(".png") else (name, ".png")
            name = f"{stem}_{suffix}{ext}"
        return name, None

    def _screenshot_frame(self) -> np.ndarray | None:
        """优先实时抓取完整画面，失败时回退到最近一帧。"""
        try:
            frame = image_utils.to_bgr(self.device.snapshot())
            if frame is not None:
                return frame
        except Exception as exc:
            print(f"[警告] 实时抓帧失败，改用最近一帧：{exc}")
        return self.latest_bgr
