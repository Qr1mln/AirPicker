# -*- coding: utf-8 -*-
"""Android 连接协议：Airtest URI 的选项、默认值、校验与构建。

格式：Android://[adbhost:adbport]/[serialno]?param=value&...
参数与 airtest.core.android.Android.__init__ 一致，界面只展示 Android。
"""
from __future__ import annotations

from typing import Any

CAP_METHODS = ("MINICAP", "JAVACAP", "ADBCAP")
TOUCH_METHODS = ("MINITOUCH", "MAXTOUCH", "ADBTOUCH")
IME_METHODS = ("YOSEMITEIME", "ADBIME")
ORI_METHODS = ("MINICAPORI", "ADBORI")

# 下拉框显示文案（值, 说明）
CAP_LABELS = (
    ("MINICAP", "MINICAP — 默认，速度快，需设备支持"),
    ("JAVACAP", "JAVACAP — 兼容性较好"),
    ("ADBCAP", "ADBCAP — 最慢，兜底方案"),
)
TOUCH_LABELS = (
    ("MINITOUCH", "MINITOUCH — 默认，Android 10+ 自动切 MAXTOUCH"),
    ("MAXTOUCH", "MAXTOUCH — Android 10+ 可用"),
    ("ADBTOUCH", "ADBTOUCH — 兼容性兜底"),
)
IME_LABELS = (
    ("YOSEMITEIME", "YOSEMITEIME — 默认，需 Yosemite 输入法"),
    ("ADBIME", "ADBIME — 使用 adb 输入"),
)
ORI_LABELS = (
    ("MINICAPORI", "MINICAPORI — 默认"),
    ("ADBORI", "ADBORI — 使用 adb 获取方向"),
)

PRESETS: dict[str, dict[str, str]] = {
    "recommended": {
        "cap_method": "MINICAP",
        "touch_method": "MINITOUCH",
        "ime_method": "YOSEMITEIME",
        "ori_method": "MINICAPORI",
    },
    "compatible": {
        "cap_method": "JAVACAP",
        "touch_method": "ADBTOUCH",
        "ime_method": "ADBIME",
        "ori_method": "ADBORI",
    },
    "javacap_touch": {
        "cap_method": "JAVACAP",
        "touch_method": "MINITOUCH",
        "ime_method": "YOSEMITEIME",
        "ori_method": "MINICAPORI",
    },
}

PRESET_LABELS = (
    ("recommended", "推荐 — MINICAP + MINITOUCH"),
    ("compatible", "兼容 — JAVACAP + ADBTOUCH + ADBIME"),
    ("javacap_touch", "截图兼容 — JAVACAP + MINITOUCH"),
    ("custom", "自定义"),
)

URI_HINT = "格式：Android://[adbhost:adbport]/[serialno]?cap_method=...&touch_method=..."

DEFAULT_CONNECTION: dict[str, Any] = {
    "adb_host": "127.0.0.1",
    "adb_port": 5037,
    "serial": "",
    "cap_method": "MINICAP",
    "touch_method": "MINITOUCH",
    "ime_method": "YOSEMITEIME",
    "ori_method": "MINICAPORI",
    "display_id": "",
    "input_event": "",
    "adb_path": "",
}

_ENUM_FIELDS = {
    "cap_method": CAP_METHODS,
    "touch_method": TOUCH_METHODS,
    "ime_method": IME_METHODS,
    "ori_method": ORI_METHODS,
}
_TEXT_FIELDS = ("display_id", "input_event", "adb_path")


def normalize(data: dict[str, Any] | None) -> dict[str, Any]:
    """把任意输入规整为合法的连接配置，非法字段回退默认值。"""
    result = dict(DEFAULT_CONNECTION)
    if not isinstance(data, dict):
        return result

    host = data.get("adb_host")
    if isinstance(host, str) and host.strip():
        result["adb_host"] = host.strip()

    try:
        port = int(data.get("adb_port"))
    except (TypeError, ValueError):
        port = 0
    if 1 <= port <= 65535:
        result["adb_port"] = port

    serial = data.get("serial")
    if isinstance(serial, str):
        result["serial"] = serial.strip()

    for key, allowed in _ENUM_FIELDS.items():
        value = data.get(key)
        if isinstance(value, str) and value.strip().upper() in allowed:
            result[key] = value.strip().upper()

    for key in _TEXT_FIELDS:
        value = data.get(key)
        if isinstance(value, str):
            result[key] = value.strip()
    return result


def match_preset(data: dict[str, Any] | None) -> str:
    """找出与当前 4 个方式参数完全一致的预设，否则返回 custom。"""
    cfg = normalize(data)
    for key, preset in PRESETS.items():
        if all(cfg[field] == value for field, value in preset.items()):
            return key
    return "custom"


def build_uri(data: dict[str, Any] | None) -> str:
    """按 Airtest Android URI 格式生成连接串。"""
    cfg = normalize(data)
    netloc = f"{cfg['adb_host']}:{cfg['adb_port']}" if cfg["adb_host"] else ""
    uri = f"Android://{netloc}/{cfg['serial']}"

    params: list[str] = []
    for key in ("cap_method", "touch_method", "ime_method", "ori_method", *_TEXT_FIELDS):
        value = cfg[key]
        if value:
            params.append(f"{key}={value}")
    return uri + ("?" + "&".join(params) if params else "")
