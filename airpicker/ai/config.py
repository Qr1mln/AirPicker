# -*- coding: utf-8 -*-
"""AI 模块独立配置：读写 config/ai_settings.json，不依赖主程序 settings。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "ai_settings.json"

DEFAULT_SCENES: list[dict[str, str]] = [
    {"name": "reward_dialog", "desc": "有立即领取/恭喜获得字样的活动弹窗"},
    {"name": "taobao_app", "desc": "淘宝商品页，底部有首页/购物车/我的淘宝"},
    {"name": "main_screen", "desc": "游戏主界面，无弹窗"},
]

DEFAULT_ANALYZE_PROMPT = (
    "这是一张手机屏幕截图。请识别画面中的可见元素（文字、按钮、图标），"
    "按画面从左到右、从上到下的顺序输出 JSON 数组，"
    "每项格式：{\"index\":顺序号,\"text\":\"元素文字\",\"type\":\"文字|按钮|图标\"}。"
    "只输出 JSON 数组，不要输出任何解释。"
)
LEGACY_QUESTION = "请描述当前画面内容，列出可见的文字和按钮。"
DEFAULT_MATCH_PROMPT = (
    "上一步的界面识别结果：\n"
    "{analysis}\n\n"
    "用户补充线索：{hint}\n\n"
    "候选场景（名称：描述）：\n{scenes}\n\n"
    "规则：只有当候选场景描述中的关键文字在识别结果里明确出现时才能选择，"
    "不要仅凭语义猜测。若多个候选场景的关键文字都出现，选择命中文字最多、描述最具体的场景。"
    "名称必须原样从候选里选；都不符合输出 none。只输出场景名，不要解释。"
)

DEFAULTS: dict[str, Any] = {
    "panel_visible": False,
    "api_url": "http://192.168.162.1:1234/v1/chat/completions",
    "api_token": "",
    "model": "ui-box-scorer-qwen2.5-vl-7b",
    "timeout": 30,
    "temperature": 0.2,
    "retry_temperature": 0.6,
    "analyze_prompt": DEFAULT_ANALYZE_PROMPT,
    "match_prompt": DEFAULT_MATCH_PROMPT,
    "scenes": deepcopy(DEFAULT_SCENES),
    "scene_columns": [140, 420],
    "splitter_sizes": [420, 260],
    "window_geometry": None,
    "window_state": "",
}


def load() -> dict[str, Any]:
    config = deepcopy(DEFAULTS)
    if not CONFIG_PATH.exists():
        return config
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[警告] 读取 AI 配置失败，使用默认值：{exc}")
        return config
    if not isinstance(raw, dict):
        return config
    visible = raw.get("panel_visible")
    if isinstance(visible, bool):
        config["panel_visible"] = visible
    url = raw.get("api_url")
    if isinstance(url, str) and url.strip():
        config["api_url"] = url.strip()
    token = raw.get("api_token")
    if isinstance(token, str):
        config["api_token"] = token.strip()
    model = raw.get("model")
    if isinstance(model, str) and model.strip():
        config["model"] = model.strip()
    timeout = raw.get("timeout")
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0:
        config["timeout"] = float(timeout)
    for key in ("temperature", "retry_temperature"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 2:
            config[key] = float(value)
    for key, default in (("analyze_prompt", DEFAULT_ANALYZE_PROMPT), ("match_prompt", DEFAULT_MATCH_PROMPT)):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            config[key] = value.replace("{question}", LEGACY_QUESTION).strip()
        else:
            config[key] = default
    raw_scenes = raw.get("scenes")
    if isinstance(raw_scenes, list):
        scenes: list[dict[str, str]] = []
        for item in raw_scenes:
            if not isinstance(item, dict):
                continue
            name, desc = item.get("name"), item.get("desc")
            if isinstance(name, str) and isinstance(desc, str):
                scenes.append({"name": name.strip(), "desc": desc.strip()})
        config["scenes"] = scenes
    raw_columns = raw.get("scene_columns")
    if (
        isinstance(raw_columns, list) and len(raw_columns) >= 2
        and all(isinstance(v, int) and not isinstance(v, bool) and v >= 40 for v in raw_columns[:2])
    ):
        config["scene_columns"] = [int(raw_columns[0]), int(raw_columns[1])]
    raw_splitter = raw.get("splitter_sizes")
    if (
        isinstance(raw_splitter, list) and len(raw_splitter) >= 2
        and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in raw_splitter[:2])
    ):
        config["splitter_sizes"] = [int(raw_splitter[0]), int(raw_splitter[1])]
    raw_geometry = raw.get("window_geometry")
    if (
        isinstance(raw_geometry, list) and len(raw_geometry) == 4
        and all(isinstance(v, int) and not isinstance(v, bool) for v in raw_geometry)
    ):
        config["window_geometry"] = [int(v) for v in raw_geometry]
    state = raw.get("window_state")
    if isinstance(state, str):
        config["window_state"] = state.strip()
    return config


def save(**updates: Any) -> None:
    config = load()
    config.update(updates)
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[警告] 保存 AI 配置失败：{exc}")
