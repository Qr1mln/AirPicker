# -*- coding: utf-8 -*-
"""界面识别：构建识别提示词、调用 VLM、后台识别线程。"""
from __future__ import annotations

import time
from typing import Callable

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from . import config
from .client import _chat


BLANK_SCREEN_MARKER = "空白屏幕"


def normalize_analysis(answer: str) -> str:
    """识别返回空数组时补上「空白屏幕」标记，让空白屏也能参与场景匹配。"""
    text = answer.strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        import json
        data = json.loads(text)
        if isinstance(data, list) and not data:
            return json.dumps(
                [{"id": 0, "text": BLANK_SCREEN_MARKER, "type": "状态"}],
                ensure_ascii=False,
            )
    except (ValueError, TypeError):
        pass
    return answer


def build_analyze_prompt() -> str:
    """识别提示词即完整文本，截图作为图片附件随提示词发送。"""
    return config.load()["analyze_prompt"]


def ask(
    frame: np.ndarray,
    api_url: str,
    model: str,
    timeout: float = 30,
    token: str = "",
    max_tokens: int = 800,
    temperature: float = 0.2,
    retry_temperature: float = 0.6,
) -> str:
    """把单帧截图和识别提示词发给 VLM，返回模型文本。失败时抛异常。"""
    return _chat(
        build_analyze_prompt(), frame, api_url, model, timeout, token, max_tokens,
        temperature, retry_temperature,
    )


def recognize_screen(
    window,
    *,
    parent: QObject | None = None,
    on_frame=None,
    on_prompt: Callable[[str], None] | None = None,
    on_ready: Callable[[str, float], None] | None = None,
    on_failed: Callable[[str], None] | None = None,
    on_finished: Callable[[], None] | None = None,
) -> RecognitionWorker | None:
    """截取当前画面并发起一次界面识别。

    返回 worker 供调用方管理引用与 UI；无画面返回 None。
    on_frame 在截图成功后立即收到画面快照（用于保存帧或预览）；
    on_ready / on_failed / on_finished / on_prompt 连接到 worker 对应信号。
    worker 的 deleteLater 由调用方按需连接。
    """
    frame = window._screenshot_frame()
    if frame is None:
        return None
    snapshot = frame.copy()
    if on_frame is not None:
        on_frame(snapshot)
    cfg = config.load()
    worker = RecognitionWorker(
        snapshot,
        cfg["api_url"], cfg["model"], cfg["timeout"], cfg["api_token"],
        cfg["max_tokens"], cfg["temperature"], cfg["retry_temperature"], parent,
    )
    if on_prompt is not None:
        worker.prompt_ready.connect(on_prompt)
    if on_ready is not None:
        worker.result_ready.connect(on_ready)
    if on_failed is not None:
        worker.failed.connect(on_failed)
    if on_finished is not None:
        worker.finished.connect(on_finished)
    worker.start()
    return worker


class RecognitionWorker(QThread):
    """后台执行画面描述请求，避免阻塞 30 FPS 抓帧循环。"""

    result_ready = Signal(str, float)
    prompt_ready = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        frame: np.ndarray,
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
        self._api_url = api_url
        self._model = model
        self._timeout = timeout
        self._token = token
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._retry_temperature = retry_temperature

    def run(self) -> None:
        started = time.perf_counter()
        self.prompt_ready.emit(build_analyze_prompt())
        try:
            answer = ask(
                self._frame, self._api_url, self._model,
                self._timeout, self._token, self._max_tokens,
                self._temperature, self._retry_temperature,
            )
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        self.result_ready.emit(normalize_analysis(answer), time.perf_counter() - started)
