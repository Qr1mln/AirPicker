# -*- coding: utf-8 -*-
"""场景匹配：结果解析、文字权重打分、匹配提示词与后台匹配线程。"""
from __future__ import annotations

import json
import re
import time

from PySide6.QtCore import QThread, Signal

from . import config
from .client import _chat


def _parse_elements(analysis: str) -> list[str]:
    """识别结果为 JSON 元素列表时提取元素文字；解析失败则整段文本当作单个元素。"""
    cleaned = analysis.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    fallback = [re.sub(r"\s+", "", analysis)]
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        return fallback
    if not isinstance(data, list):
        return fallback
    texts = []
    for item in data:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(re.sub(r"\s+", "", text))
    return texts or fallback


def _scene_weight_score(elements: list[str], feature: list | str) -> float:
    """场景特征数组中的片段按权重命中打分；兼容旧字符串格式。"""
    rows = feature if isinstance(feature, list) else config.parse_desc(str(feature))
    score = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        compact = re.sub(r"\s+", "", str(row.get("text", "")))
        if len(compact) >= 2 and any(compact in text for text in elements):
            try:
                score += float(row.get("weight", 1))
            except (ValueError, TypeError):
                pass
    return score


def build_match_prompt(
    analysis: str,
    scenes: list[dict[str, str]],
    hint: str = "",
) -> str:
    lines = "\n".join(
        "- {name}：{feature}".format(
            name=item["name"],
            feature="、".join(
                f"{row['text']}(权重{float(row['weight']):g})"
                for row in item.get("feature", [])
                if isinstance(row, dict) and row.get("text")
            ),
        )
        for item in scenes if item.get("name")
    )
    template = config.load()["match_prompt"]
    return (
        template
        .replace("{analysis}", analysis.strip())
        .replace("{hint}", hint.strip() or "无")
        .replace("{scenes}", lines)
    )


def match_scene(
    analysis: str,
    scenes: list[dict[str, str]],
    api_url: str,
    model: str,
    timeout: float = 30,
    token: str = "",
    max_tokens: int = 800,
    hint: str = "",
    temperature: float = 0.2,
) -> str:
    """第二步：根据界面分析结果与场景配置匹配，返回场景名（不匹配返回空串）。"""
    answer = _chat(
        build_match_prompt(analysis, scenes, hint), None, api_url, model, timeout, token,
        max_tokens, temperature,
    )
    cleaned = answer.strip().strip("`\"'。 ")

    elements = _parse_elements(analysis)
    scores = {
        item["name"]: _scene_weight_score(elements, item.get("feature", ""))
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
    best_name, best_score = max(scores.items(), key=lambda kv: kv[1], default=("", 0))
    if picked and scores.get(picked, 0) > 0:
        if best_name != picked and best_score > scores.get(picked, 0):
            return best_name
        return picked
    return best_name if best_score > 0 else ""


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
        max_tokens: int = 800,
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
        self._max_tokens = max_tokens
        self._temperature = temperature

    def run(self) -> None:
        started = time.perf_counter()
        self.prompt_ready.emit(build_match_prompt(self._analysis, self._scenes))
        try:
            scene = match_scene(
                self._analysis, self._scenes, self._api_url, self._model,
                self._timeout, self._token, self._max_tokens,
                temperature=self._temperature,
            )
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        self.matched.emit(scene, time.perf_counter() - started)
