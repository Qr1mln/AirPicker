# -*- coding: utf-8 -*-
"""Android 设备连接与屏幕信息。"""
from __future__ import annotations

import subprocess
import time

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


def _run_quietly(cmd: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    """静默执行命令，避免 GUI 程序弹出控制台窗口。"""
    return subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=timeout,
        check=False,
    )


def _force_restart_adb() -> None:
    """强制结束所有 adb.exe 并重启 adb server，清除卡死的 daemon。"""
    from airtest.core.android.adb import ADB

    # 找不到 adb.exe 时 taskkill 返回非零，属正常情况，忽略
    _run_quietly(["taskkill", "/F", "/IM", "adb.exe"])
    time.sleep(0.5)
    _run_quietly([ADB.get_adb_path(), "start-server"])


def connect():
    """连接设备并配置 MINICAP 画质；失败时强制重启 adb 后重试一次。"""
    from airtest.core.api import connect_device
    from airtest.core.android.cap_methods.minicap import Minicap

    quality_flag = f"-Q {MINICAP_QUALITY}"
    if quality_flag not in Minicap.CMD:
        Minicap.CMD = f"{Minicap.CMD} {quality_flag}"

    uri = build_uri()
    try:
        return connect_device(uri)
    except Exception as first_exc:
        print(f"[警告] 首次连接失败：{first_exc}")
        print("[信息] 正在强制结束 adb.exe 并重新连接...")
        try:
            _force_restart_adb()
        except Exception as restart_exc:
            print(f"[警告] 重启 adb 失败：{restart_exc}")
            raise first_exc
        try:
            device = connect_device(uri)
        except Exception:
            print("[错误] 重启 adb 后仍连接失败")
            raise
        print("[信息] 强制重启 adb 后连接成功")
        return device
