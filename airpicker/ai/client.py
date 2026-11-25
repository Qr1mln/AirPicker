# -*- coding: utf-8 -*-
"""VLM 调用底层：图片编码、请求发送、重试与错误压缩。"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

import cv2
import numpy as np

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
    max_tokens: int,
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
            "max_tokens": max_tokens,
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
