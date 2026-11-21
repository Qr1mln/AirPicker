# -*- coding: utf-8 -*-
"""模板图片落盘、Airtest 代码生成与剪贴板写入。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .config import PICS_DIR, SCRIPTS_DIR

try:
    import pyperclip
except ImportError:  # 剪贴板不可用时仍可在控制台手动复制
    pyperclip = None


def copy_text(text: str, tip: str) -> None:
    try:
        if pyperclip is None:
            raise RuntimeError("pyperclip 未安装")
        pyperclip.copy(text)
        print(tip)
    except Exception as exc:
        print(f"剪贴板不可用（{exc}），请手动复制：{text}")

def save_template(
    crop_bgr: np.ndarray,
    resource_dir: Path | None = None,
    tpl_expr: str | None = None,
    meta: dict | None = None,
) -> Path:
    out_dir = resource_dir if resource_dir is not None else PICS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"tpl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.png"
    path = out_dir / file_name
    Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)).save(path)

    rel = os.path.relpath(path, SCRIPTS_DIR).replace("\\", "/")
    template_code = f'Template(r"{rel}")'
    full_code = f"touch({template_code})"
    expr = tpl_expr if tpl_expr is not None else template_code
    m = meta or {}
    code = (
        expr.replace("{path}", rel)
        .replace("{name}", file_name)
        .replace("{rx}", str(m.get("rx", 0.0)))
        .replace("{ry}", str(m.get("ry", 0.0)))
        .replace("{rw}", str(m.get("rw", 0)))
        .replace("{rh}", str(m.get("rh", 0)))
    )

    print(f"模板已保存：{path.as_posix()}")
    print(f"Template：{template_code}")
    print(f"完整命令：{full_code}")
    print(f"回写表达式：{expr}")
    copy_text(code, "已复制到剪贴板")
    return path


def copy_swipe(x1: int, y1: int, x2: int, y2: int, expr: str) -> str:
    """按滑动回写表达式生成并复制 swipe 代码。"""
    code = (
        expr.replace("{x1}", str(x1))
        .replace("{y1}", str(y1))
        .replace("{x2}", str(x2))
        .replace("{y2}", str(y2))
    )
    print(f"[滑动] {x1}, {y1} -> {x2}, {y2}")
    print(f"回写：{code}")
    copy_text(code, "swipe 代码已复制到剪贴板")
    return code
