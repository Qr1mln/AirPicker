# -*- coding: utf-8 -*-
"""AI 模块独立配置：读写 config/ai_settings.json，不依赖主程序 settings。"""
from __future__ import annotations

import base64
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "ai_settings.json"
SCENE_IMAGE_DIR = CONFIG_DIR / "scenes"

DEFAULT_SCENES: list[dict] = [
    {"name": "reward_dialog", "feature": [{"text": "立即领取", "weight": 1}, {"text": "恭喜获得", "weight": 1}]},
    {"name": "taobao_app", "feature": [{"text": "首页", "weight": 1}, {"text": "购物车", "weight": 1}, {"text": "我的淘宝", "weight": 1}]},
    {"name": "main_screen", "feature": [{"text": "主界面", "weight": 1}]},
]


def parse_desc(desc: str) -> list[dict[str, float | str]]:
    """把场景描述解析成 [{text, weight}]；兼容旧「词*权重」文本格式。"""
    if not isinstance(desc, str) or not desc.strip():
        return []
    cleaned = desc.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, list):
        rows: list[dict[str, float | str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            weight = item.get("weight", 1)
            if isinstance(weight, (int, float)) and not isinstance(weight, bool) and weight > 0:
                rows.append({"text": text.strip(), "weight": float(weight)})
            else:
                rows.append({"text": text.strip(), "weight": 1.0})
        if rows:
            return rows
    rows = []
    for line in cleaned.splitlines():
        part = line.strip()
        if not part:
            continue
        weight = 1.0
        match = re.search(r"\*(\d+(?:\.\d+)?)\s*$", part)
        if match:
            weight = float(match.group(1))
            part = part[: match.start()].rstrip()
        if part:
            rows.append({"text": part, "weight": weight})
    return rows


def format_desc(rows: list[dict[str, float | str]]) -> str:
    """把 [{text, weight}] 序列化成 JSON 数组文本。"""
    data = [
        {"text": str(row.get("text", "")).strip(), "weight": float(row.get("weight", 1.0))}
        for row in rows
        if str(row.get("text", "")).strip()
    ]
    return json.dumps(data, ensure_ascii=False)


def image_to_data_url(path: str | Path, mime: str = "image/png") -> str:
    """把图片文件读成 data URL 文本，直接存进场景 JSON。"""
    raw = Path(path).read_bytes()
    prefix = mime.split("/")[-1].lower() or "png"
    return f"data:image/{prefix};base64,{base64.b64encode(raw).decode('ascii')}"


def decode_image(value: str) -> bytes | None:
    """从 data URL 或裸 base64 解出图片字节；非图片值返回 None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.startswith("data:image/"):
        head, _, payload = text.partition(",")
        if not payload:
            return None
        text = payload
    try:
        return base64.b64decode(text, validate=True)
    except Exception:
        return None

DEFAULT_ANALYZE_PROMPT = (
    "这是一张手机屏幕截图。请识别画面中实际可见的元素（文字、按钮、图标），"
    "按画面从左到右、从上到下的顺序输出 JSON 数组，"
    "每项格式：{\"id\":顺序号,\"text\":\"元素文字\",\"type\":\"文字|按钮|图标\"}。\n"
    "严格规则：\n"
    "1. 只输出画面中真实存在的内容，禁止复述本指令里的任何文字（如「手机屏幕截图」"
    "「从左到右」「元素列表」等）。\n"
    "2. 若画面为空白、纯色或无可见元素，只输出："
    "[{\"id\":0,\"text\":\"空白屏幕\",\"type\":\"状态\"}]。\n"
    "只输出 JSON 数组，不要输出任何解释。"
)
LEGACY_ANALYZE_PROMPT_V1 = (
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
    "max_tokens": 800,
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
    max_tokens = raw.get("max_tokens")
    if isinstance(max_tokens, int) and not isinstance(max_tokens, bool) and max_tokens > 0:
        config["max_tokens"] = max_tokens
    for key in ("temperature", "retry_temperature"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 2:
            config[key] = float(value)
    for key, default in (("analyze_prompt", DEFAULT_ANALYZE_PROMPT), ("match_prompt", DEFAULT_MATCH_PROMPT)):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            text = value.replace("{question}", LEGACY_QUESTION).strip()
            if key == "analyze_prompt" and text == LEGACY_ANALYZE_PROMPT_V1:
                text = DEFAULT_ANALYZE_PROMPT
            config[key] = text
        else:
            config[key] = default
    config["scenes"] = load_scenes()
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


def list_scene_files() -> list[Path]:
    """按文件名排序列出 config/scenes 下的场景 JSON 文件。"""
    if not SCENE_IMAGE_DIR.exists():
        return []
    return sorted(
        p for p in SCENE_IMAGE_DIR.glob("*.json") if p.is_file()
    )


def load_scenes() -> list[dict]:
    """从每个场景 JSON 文件读取场景配置，列表顺序 = 文件名顺序。

    feature 为标准 JSON 数组；旧文件里字符串化的 feature/desc 自动解析兼容。
    """
    scenes: list[dict] = []
    for path in list_scene_files():
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        feature = item.get("feature", item.get("desc", []))
        image = item.get("image", "")
        if isinstance(feature, str):
            feature = parse_desc(feature)
        if not isinstance(feature, list):
            feature = []
        if isinstance(name, str):
            scenes.append({
                "name": name,
                "feature": feature,
                "image": image if isinstance(image, str) else "",
                "_file": path.name,
            })
    return scenes


def save_scenes(scenes: list[dict]) -> None:
    """把场景列表按 001.json... 编号写入目录，删除多余旧文件。"""
    SCENE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    old_files = set(p.name for p in list_scene_files())
    new_files: set[str] = set()
    for index, scene in enumerate(scenes, 1):
        filename = f"{index:03d}.json"
        new_files.add(filename)
        feature = scene.get("feature", [])
        if isinstance(feature, str):
            feature = parse_desc(feature)
        payload = {
            "name": scene.get("name", ""),
            "feature": feature if isinstance(feature, list) else [],
            "image": scene.get("image", ""),
        }
        (SCENE_IMAGE_DIR / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    for filename in old_files - new_files:
        (SCENE_IMAGE_DIR / filename).unlink(missing_ok=True)


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
