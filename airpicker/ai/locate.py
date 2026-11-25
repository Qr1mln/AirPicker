# -*- coding: utf-8 -*-
"""智能取码：解析模型返回的坐标，后台定位目标像素位置。"""
from __future__ import annotations

import json
import re
import time

import numpy as np
from PySide6.QtCore import QThread, Signal

from .client import _chat


def parse_point(text: str, size: tuple[int, int]) -> tuple[int, int]:
    """从模型输出解析 {"x":…,"y":…}，失败时报错，成功时裁剪到原图范围。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    x = y = None
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            x, y = data.get("x"), data.get("y")
        elif isinstance(data, (list, tuple)) and len(data) >= 2:
            x, y = data[0], data[1]
    except (ValueError, TypeError):
        pass
    if x is None or y is None:
        match = re.search(
            r'"x"\s*:\s*(-?\d+(?:\.\d+)?).*?"y"\s*:\s*(-?\d+(?:\.\d+)?)',
            cleaned, re.S,
        )
        if match:
            x, y = match.group(1), match.group(2)
        else:
            numbers = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
            if len(numbers) >= 2:
                x, y = numbers[0], numbers[1]
    if x is None or y is None:
        raise ValueError(f"无法解析坐标：{cleaned[:120]}")
    w, h = size
    px = max(0, min(w - 1, int(round(float(x)))))
    py = max(0, min(h - 1, int(round(float(y)))))
    return px, py


def locate(
    frame: np.ndarray,
    target: str,
    api_url: str,
    model: str,
    timeout: float = 30,
    token: str = "",
    max_tokens: int = 800,
    temperature: float = 0.2,
    retry_temperature: float = 0.6,
) -> tuple[int, int]:
    """让 VLM 返回目标中心的设备原图坐标。失败时抛异常。"""
    h, w = frame.shape[:2]
    prompt = (
        f"这是一张手机屏幕截图，原图尺寸为 {w}×{h}。\n"
        f"请定位目标：{target.strip()}\n"
        "返回目标中心的设备原图像素坐标，只输出 JSON：{\"x\":整数,\"y\":整数}，不要其他文字。"
    )
    answer = _chat(
        prompt, frame, api_url, model, timeout, token, max_tokens,
        temperature, retry_temperature,
    )
    return parse_point(answer, (w, h))


class LocateWorker(QThread):
    """后台执行智能取码请求，返回目标像素坐标。"""

    located = Signal(int, int, float)
    failed = Signal(str)

    def __init__(
        self,
        frame: np.ndarray,
        target: str,
        api_url: str,
        model: str,
        timeout: float,
        token: str = "",
        max_tokens: int = 800,
        temperature: float = 0.2,
        retry_temperature: float = 0.6,
        parent=None,
    ):
        super().__init__(parent)
        self._frame = frame
        self._target = target
        self._api_url = api_url
        self._model = model
        self._timeout = timeout
        self._token = token
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._retry_temperature = retry_temperature

    def run(self) -> None:
        started = time.perf_counter()
        try:
            x, y = locate(
                self._frame, self._target, self._api_url, self._model,
                self._timeout, self._token, self._max_tokens,
                self._temperature, self._retry_temperature,
            )
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        self.located.emit(x, y, time.perf_counter() - started)
