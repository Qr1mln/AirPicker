# -*- coding: utf-8 -*-
"""应用设置持久化：项目根目录 settings.json。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import ROOT

SETTINGS_PATH = ROOT / "settings.json"

DEFAULTS: dict[str, Any] = {
    "toolbar": {
        "horizontal": False,
    },
}


def load_settings() -> dict[str, Any]:
    """读取设置；文件缺失、损坏或字段缺失时回退默认值。"""
    settings = deepcopy(DEFAULTS)
    if not SETTINGS_PATH.exists():
        return settings
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[警告] 读取设置失败，使用默认值：{exc}")
        return settings
    if not isinstance(raw, dict):
        return settings
    saved = raw.get("toolbar")
    if isinstance(saved, dict) and isinstance(saved.get("horizontal"), bool):
        settings["toolbar"]["horizontal"] = saved["horizontal"]
    return settings


def get_toolbar_horizontal(settings: dict[str, Any]) -> bool:
    return bool(settings.get("toolbar", {}).get("horizontal", False))


def save_toolbar_horizontal(horizontal: bool) -> None:
    settings = load_settings()
    settings.setdefault("toolbar", {})["horizontal"] = bool(horizontal)
    try:
        SETTINGS_PATH.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[警告] 保存设置失败：{exc}")
