# -*- coding: utf-8 -*-
"""应用设置持久化：项目根目录 settings.json。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import PICS_DIR, ROOT

SETTINGS_PATH = ROOT / "settings.json"

DEFAULT_COORD_EXPR = "({x}, {y})"
DEFAULT_TPL_EXPR = 'Template(r"{name}", record_pos=({rx}, {ry}), resolution=({rw}, {rh}))'

DEFAULTS: dict[str, Any] = {
    "toolbar": {
        "horizontal": False,
    },
    "resource_dir": "",
    "coord_expr": DEFAULT_COORD_EXPR,
    "tpl_expr": DEFAULT_TPL_EXPR,
    "lock_ratio": True,
    "window_size": None,
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
    resource_dir = raw.get("resource_dir")
    if isinstance(resource_dir, str):
        settings["resource_dir"] = resource_dir.strip()
    coord_expr = raw.get("coord_expr")
    if isinstance(coord_expr, str):
        settings["coord_expr"] = coord_expr.strip()
    tpl_expr = raw.get("tpl_expr")
    if isinstance(tpl_expr, str):
        settings["tpl_expr"] = tpl_expr.strip()
    lock_ratio = raw.get("lock_ratio")
    if isinstance(lock_ratio, bool):
        settings["lock_ratio"] = lock_ratio
    window_size = raw.get("window_size")
    if (
        isinstance(window_size, list)
        and len(window_size) == 2
        and all(isinstance(v, int) and v > 0 for v in window_size)
    ):
        settings["window_size"] = window_size
    return settings


def get_toolbar_horizontal(settings: dict[str, Any]) -> bool:
    return bool(settings.get("toolbar", {}).get("horizontal", False))


def get_lock_ratio(settings: dict[str, Any]) -> bool:
    return bool(settings.get("lock_ratio", True))


def get_window_size(settings: dict[str, Any]) -> tuple[int, int] | None:
    size = settings.get("window_size")
    if isinstance(size, list) and len(size) == 2:
        return (int(size[0]), int(size[1]))
    return None


def get_resource_dir(settings: dict[str, Any]) -> Path:
    """模板图片的保存目录：未设置时用项目 pics，相对路径基于 ROOT 解析。"""
    raw = settings.get("resource_dir", "")
    if isinstance(raw, str) and raw.strip():
        path = Path(raw.strip()).expanduser()
        return path if path.is_absolute() else (ROOT / path)
    return PICS_DIR


def get_coord_expr(settings: dict[str, Any]) -> str:
    """坐标回写表达式：{x} {y} 为变量占位符，留空回退默认值。"""
    raw = settings.get("coord_expr", "")
    return raw if isinstance(raw, str) and raw.strip() else DEFAULT_COORD_EXPR


def get_tpl_expr(settings: dict[str, Any]) -> str:
    """模板回写表达式：{path} 相对路径、{name} 文件名，{rx}/{ry} record_pos，{rw}/{rh} 分辨率。"""
    raw = settings.get("tpl_expr", "")
    return raw if isinstance(raw, str) and raw.strip() else DEFAULT_TPL_EXPR


def _write_settings(settings: dict[str, Any]) -> None:
    try:
        SETTINGS_PATH.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[警告] 保存设置失败：{exc}")


def save_toolbar_horizontal(horizontal: bool) -> None:
    settings = load_settings()
    settings.setdefault("toolbar", {})["horizontal"] = bool(horizontal)
    _write_settings(settings)


def save_resource_dir(path: str) -> None:
    settings = load_settings()
    settings["resource_dir"] = (path or "").strip()
    _write_settings(settings)


def save_coord_expr(expr: str) -> None:
    settings = load_settings()
    settings["coord_expr"] = (expr or "").strip() or DEFAULT_COORD_EXPR
    _write_settings(settings)


def save_tpl_expr(expr: str) -> None:
    settings = load_settings()
    settings["tpl_expr"] = (expr or "").strip() or DEFAULT_TPL_EXPR
    _write_settings(settings)


def save_lock_ratio(keep: bool) -> None:
    settings = load_settings()
    settings["lock_ratio"] = bool(keep)
    _write_settings(settings)


def save_window_size(width: int, height: int) -> None:
    settings = load_settings()
    settings["window_size"] = [int(width), int(height)]
    _write_settings(settings)
