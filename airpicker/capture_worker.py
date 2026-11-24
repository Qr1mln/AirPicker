# -*- coding: utf-8 -*-
"""后台抓帧线程：把阻塞的 device.snapshot() 移出 UI 线程。"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from . import image_utils
from .config import CAPTURE_MAX_FAILURES, CAPTURE_RETRY_MS, FRAME_INTERVAL_MS


class CaptureWorker(QThread):
    """持续抓帧并做 CPU 侧图像处理，结果以 ndarray 发给 UI 线程渲染。

    snapshot() 阻塞（如 minicap 重启）时只卡本线程，界面保持响应。
    """

    frame_ready = Signal(object, object, float)  # bgr, display, dpr
    capture_failed = Signal(str)
    device_waiting = Signal()
    device_recovered = Signal()

    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        self._paused = False
        self._view_w = 1
        self._view_h = 1
        self._dpr = 1.0
        self._keep_ratio = True
        self._failures = 0
        self._waiting = False

    def set_view_params(self, view_w: int, view_h: int, dpr: float, keep_ratio: bool) -> None:
        """UI 线程调用：同步显示区域尺寸，供 worker 侧缩放帧。"""
        self._view_w = max(1, view_w)
        self._view_h = max(1, view_h)
        self._dpr = dpr or 1.0
        self._keep_ratio = bool(keep_ratio)

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)

    def run(self) -> None:
        while not self.isInterruptionRequested():
            if self._paused:
                self.msleep(50)
                continue
            interval = CAPTURE_RETRY_MS if self._waiting else FRAME_INTERVAL_MS
            try:
                raw = self.device.snapshot()
            except Exception as exc:
                self._on_failure(exc)
                self.msleep(interval)
                continue
            if self.isInterruptionRequested():
                return
            arr = image_utils.to_bgr(raw)
            if arr is None:
                self.msleep(interval)
                continue
            if self._waiting:
                self._waiting = False
                self._failures = 0
                self.device_recovered.emit()
            display = image_utils.fit_frame(
                arr, self._view_w, self._view_h, self._dpr, self._keep_ratio
            )
            self.frame_ready.emit(arr, display, self._dpr)
            self.msleep(interval)

    def _on_failure(self, exc: Exception) -> None:
        self._failures += 1
        if self._failures == 1:
            detail = str(exc).strip() or type(exc).__name__
            self.capture_failed.emit(detail)
        if self._failures >= CAPTURE_MAX_FAILURES and not self._waiting:
            self._waiting = True
            self.device_waiting.emit()
