# -*- coding: utf-8 -*-
"""OpenAI 兼容 VLM 调用：画面描述与智能取码坐标定位。"""
from __future__ import annotations

import base64
import json
import re
import time
from collections import Counter
import urllib.error
import urllib.request
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

DEFAULT_QUESTION = "请描述当前画面内容，列出可见的文字和按钮。"
ANALYZE_QUESTION = (
    "请描述当前画面内容，逐条列出可见的文字和按钮，"
    "包括数字、时间、阶段名称和分区标题；按画面顺序列出，不要输出 JSON 或额外解释。"
)
MAX_TOKENS = 800
IMAGE_WIDTH = 720
RETRY_IMAGE_WIDTH = 540


def _is_degenerate(text: str) -> bool:
    """识别模型卡住后大量重复同一字符的输出。"""
    if len(text) < 200:
        return False
    _char, count = Counter(text).most_common(1)[0]
    return count / len(text) > 0.5


def _compact_error(raw: str) -> str:
    """从 API 错误响应中提取简短信息，避免整段 JSON 灌进日志。"""
    text = " ".join(raw.split())
    try:
        data = json.loads(text)
        err = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(err, dict):
            message = err.get("message") or err.get("code") or ""
            code = err.get("code", "")
            text = " ".join(str(message).split())
            for marker in (" Learn more at:", " Learn more:"):
                if marker in text:
                    text = text.split(marker, 1)[0]
            if code and code not in text:
                text = f"{text} [{code}]"
        elif isinstance(err, str):
            text = err
    except (ValueError, TypeError):
        pass
    return text[:300] + ("…" if len(text) > 300 else "")


def _encode_png(frame: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", frame)
    if not ok:
        raise ValueError("截图编码 PNG 失败")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def _chat(
    prompt: str,
    frame: np.ndarray | None,
    api_url: str,
    model: str,
    timeout: float,
    token: str,
    temperature: float = 0.2,
    retry_temperature: float = 0.6,
) -> str:
    attempts: list[tuple[int | None, float]] = (
        [(None, temperature)]
        if frame is None
        else [(IMAGE_WIDTH, temperature), (RETRY_IMAGE_WIDTH, retry_temperature)]
    )
    last_error: RuntimeError | None = None
    for index, (width, temperature) in enumerate(attempts):
        current = frame
        if current is not None and width is not None and current.shape[1] > width:
            scale = width / current.shape[1]
            current = cv2.resize(
                current, (width, max(1, int(current.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
        parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if current is not None:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_encode_png(current)}"},
                }
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": parts}],
            "temperature": temperature,
            "max_tokens": MAX_TOKENS,
            "cache_prompt": False,
            "repeat_penalty": 1.1,
        }
        if index:
            payload["seed"] = int(time.time())
        headers = {"Content-Type": "application/json"}
        if token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        request = urllib.request.Request(
            api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = _compact_error(exc.read().decode("utf-8", errors="replace"))
            raise RuntimeError(f"API HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"API 连接失败：{exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise RuntimeError(f"API 请求超时或失败：{exc}") from exc

        if raw.get("error"):
            raise RuntimeError(
                f"API 返回错误：{_compact_error(json.dumps(raw['error'], ensure_ascii=False))}"
            )
        try:
            answer = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"API 响应格式异常：{json.dumps(raw, ensure_ascii=False)[:300]}"
            ) from exc

        if isinstance(answer, str):
            text = answer.strip()
        elif isinstance(answer, list):
            fragments = [
                str(item.get("text", ""))
                for item in answer
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            text = "\n".join(part for part in fragments if part).strip()
        else:
            text = str(answer).strip()
        if not _is_degenerate(text):
            return text
        last_error = RuntimeError("模型输出异常（大量重复字符），请重试")
    raise last_error or RuntimeError("模型输出异常，请重试")


def build_analyze_prompt(question: str) -> str:
    return (
        f"这是一张手机屏幕截图。{question.strip() or DEFAULT_QUESTION}\n"
        "请直接用中文回答，不要输出 JSON 或额外解释。"
    )


def ask(
    frame: np.ndarray,
    question: str,
    api_url: str,
    model: str,
    timeout: float = 30,
    token: str = "",
    temperature: float = 0.2,
    retry_temperature: float = 0.6,
) -> str:
    """把单帧截图和问题发给 VLM，返回模型文本。失败时抛异常。"""
    return _chat(
        build_analyze_prompt(question), frame, api_url, model, timeout, token,
        temperature, retry_temperature,
    )


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
        prompt, frame, api_url, model, timeout, token, temperature, retry_temperature
    )
    return parse_point(answer, (w, h))


def _scene_local_score(analysis: str, desc: str) -> int:
    """统计场景描述中的文字片段在界面分析结果里明确出现了多少。"""
    text = re.sub(r"\s+", "", analysis)
    score = 0
    for part in re.split(r"[\n\r，,。；;、/|]+", desc):
        fragment = re.sub(r"\s+", "", part.strip())
        if len(fragment) >= 2 and fragment in text:
            score += len(fragment)
    return score


def build_match_prompt(
    analysis: str,
    scenes: list[dict[str, str]],
    hint: str = "",
) -> str:
    lines = "\n".join(
        f"- {item['name']}：{item['desc']}" for item in scenes if item.get("name")
    )
    return (
        "上一步的界面识别结果：\n"
        f"{analysis.strip()}\n\n"
        f"用户补充线索：{hint.strip() or '无'}\n\n"
        f"候选场景（名称：描述）：\n{lines}\n\n"
        "规则：只有当候选场景描述中的关键文字在识别结果里明确出现时才能选择，"
        "不要仅凭语义猜测。名称必须原样从候选里选；都不符合输出 none。只输出场景名，不要解释。"
    )


def match_scene(
    analysis: str,
    scenes: list[dict[str, str]],
    api_url: str,
    model: str,
    timeout: float = 30,
    token: str = "",
    hint: str = "",
    temperature: float = 0.2,
) -> str:
    """第二步：根据界面分析结果与场景配置匹配，返回场景名（不匹配返回空串）。"""
    answer = _chat(
        build_match_prompt(analysis, scenes, hint), None, api_url, model, timeout, token,
        temperature,
    )
    cleaned = answer.strip().strip("`\"'。 ")

    scores = {
        item["name"]: _scene_local_score(analysis, item.get("desc", ""))
        for item in scenes if item.get("name")
    }
    picked = ""
    for name in scores:
        if cleaned.lower() == name.lower():
            picked = name
            break
    if not picked:
        for name in scores:
            if name.lower() in cleaned.lower():
                picked = name
                break
    if picked and scores.get(picked, 0) > 0:
        return picked
    best_name, best_score = max(scores.items(), key=lambda kv: kv[1], default=("", 0))
    return best_name if best_score > 0 else ""


class RecognitionWorker(QThread):
    """后台执行画面描述请求，避免阻塞 30 FPS 抓帧循环。"""

    result_ready = Signal(str, float)
    prompt_ready = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        frame: np.ndarray,
        question: str,
        api_url: str,
        model: str,
        timeout: float,
        token: str = "",
        temperature: float = 0.2,
        retry_temperature: float = 0.6,
        parent=None,
    ):
        super().__init__(parent)
        self._frame = frame
        self._question = question
        self._api_url = api_url
        self._model = model
        self._timeout = timeout
        self._token = token
        self._temperature = temperature
        self._retry_temperature = retry_temperature

    def run(self) -> None:
        started = time.perf_counter()
        self.prompt_ready.emit(build_analyze_prompt(self._question))
        try:
            answer = ask(
                self._frame, self._question, self._api_url, self._model,
                self._timeout, self._token, self._temperature, self._retry_temperature,
            )
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        self.result_ready.emit(answer, time.perf_counter() - started)


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
        self._temperature = temperature
        self._retry_temperature = retry_temperature

    def run(self) -> None:
        started = time.perf_counter()
        try:
            x, y = locate(
                self._frame, self._target, self._api_url, self._model,
                self._timeout, self._token, self._temperature, self._retry_temperature,
            )
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        self.located.emit(x, y, time.perf_counter() - started)


class MatchWorker(QThread):
    """第二步：用界面识别结果 + 场景配置匹配场景。"""

    matched = Signal(str, float)
    prompt_ready = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        analysis: str,
        scenes: list[dict[str, str]],
        api_url: str,
        model: str,
        timeout: float,
        token: str = "",
        temperature: float = 0.2,
        parent=None,
    ):
        super().__init__(parent)
        self._analysis = analysis
        self._scenes = scenes
        self._api_url = api_url
        self._model = model
        self._timeout = timeout
        self._token = token
        self._temperature = temperature

    def run(self) -> None:
        started = time.perf_counter()
        self.prompt_ready.emit(build_match_prompt(self._analysis, self._scenes))
        try:
            scene = match_scene(
                self._analysis, self._scenes, self._api_url, self._model,
                self._timeout, self._token, temperature=self._temperature,
            )
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        self.matched.emit(scene, time.perf_counter() - started)
