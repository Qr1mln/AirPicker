# -*- coding: utf-8 -*-
"""帧处理、BGR→QPixmap 转换与显示坐标换算。"""
from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPixmap

from .config import DISPLAY_SHARPEN


def to_bgr(raw) -> np.ndarray | None:
    """把设备截图转成连续的 BGR ndarray。"""
    if raw is None or np.asarray(raw).size == 0:
        return None
    arr = np.asarray(raw)
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    elif arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
    if not arr.flags.c_contiguous:
        arr = np.ascontiguousarray(arr)
    return arr


def fit_frame(arr: np.ndarray, view_w: int, view_h: int, dpr: float) -> np.ndarray:
    """按显示区域等比缩放并可选锐化。"""
    h, w = arr.shape[:2]
    scale = min((view_w * dpr) / w, (view_h * dpr) / h)
    if scale < 1.0:
        dw, dh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        display = cv2.resize(arr, (dw, dh), interpolation=cv2.INTER_AREA)
    else:
        display = arr
    if DISPLAY_SHARPEN:
        blurred = cv2.GaussianBlur(display, (0, 0), 1.0)
        display = cv2.addWeighted(display, 1.25, blurred, -0.25, 0)
    return display


def to_pixmap(display: np.ndarray, dpr: float) -> QPixmap:
    h, w = display.shape[:2]
    image = QImage(display.data, w, h, 3 * w, QImage.Format_BGR888).copy()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def view_to_source(
    pos: QPoint, frame: np.ndarray | None, pixmap: QPixmap | None,
    view_w: int, view_h: int,
) -> tuple[int, int]:
    """把画面上的显示坐标换算成设备原始坐标。"""
    if pixmap is None or frame is None:
        return 0, 0
    h, w = frame.shape[:2]
    dpr = pixmap.devicePixelRatioF() or 1.0
    iw, ih = pixmap.width() / dpr, pixmap.height() / dpr
    ox = (view_w - iw) / 2
    oy = (view_h - ih) / 2
    sx = int(round((pos.x() - ox) / iw * w))
    sy = int(round((pos.y() - oy) / ih * h))
    return max(0, min(w - 1, sx)), max(0, min(h - 1, sy))
