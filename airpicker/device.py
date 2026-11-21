# -*- coding: utf-8 -*-
"""Android 设备连接与屏幕信息。"""
from __future__ import annotations

from .config import DEVICE_URI, MINICAP_QUALITY, SERIAL


def build_uri() -> str:
    if SERIAL:
        return (
            f"Android://127.0.0.1:5037/{SERIAL}"
            f"?cap_method=MINICAP&touch_method=MINITOUCH"
        )
    return DEVICE_URI


def device_screen_wh(device) -> tuple[int, int] | None:
    try:
        info = device.adb.get_display_info()
        w, h = int(info["width"]), int(info["height"])
        if int(info.get("rotation", 0)) % 180:
            w, h = h, w
        return w, h
    except Exception:
        return None


def connect():
    """连接设备并配置 MINICAP 画质，失败时抛出原始异常。"""
    from airtest.core.api import connect_device
    from airtest.core.android.cap_methods.minicap import Minicap

    quality_flag = f"-Q {MINICAP_QUALITY}"
    if quality_flag not in Minicap.CMD:
        Minicap.CMD = f"{Minicap.CMD} {quality_flag}"
    return connect_device(build_uri())
