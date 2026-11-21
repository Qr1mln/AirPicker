# -*- coding: utf-8 -*-
"""模板图片落盘、Airtest 代码生成与剪贴板写入。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .config import COPY_MODE, PICS_DIR, SCRIPTS_DIR

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


def save_template(crop_bgr: np.ndarray) -> Path:
    PICS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"tpl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.png"
    path = PICS_DIR / name
    Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)).save(path)

    rel = os.path.relpath(path, SCRIPTS_DIR).replace("\\", "/")
    template_code = f'Template(r"{rel}")'
    full_code = f"touch({template_code})"
    mode = COPY_MODE if COPY_MODE in ("touch", "template") else "touch"
    code = full_code if mode == "touch" else template_code

    print(f"模板已保存：{path.as_posix()}")
    print(f"Template：{template_code}")
    print(f"完整命令：{full_code}")
    copy_text(code, "已复制到剪贴板")
    return path
