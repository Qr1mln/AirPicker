# -*- coding: utf-8 -*-
"""Android 设备连接与屏幕信息。"""
from __future__ import annotations

import subprocess
import time

from . import settings as app_settings
from .config import MINICAP_QUALITY
from .connection import build_uri as build_android_uri


def build_uri() -> str:
    """按 config/settings.json 中的 Android 连接配置构造 Airtest URI。"""
    return build_android_uri(app_settings.get_connection(app_settings.load_settings()))


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


ADB_RESTART_COOLDOWN = 30.0
_last_adb_restart = 0.0


def _force_restart_adb(adb_path: str = "") -> bool:
    """强制重启 adb server；带冷却时间，避免反复点击时反复杀掉 adb.exe。"""
    global _last_adb_restart
    now = time.monotonic()
    if now - _last_adb_restart < ADB_RESTART_COOLDOWN:
        print("[信息] ADB 重启处于冷却期，跳过（避免反复结束 adb.exe）")
        return False
    _last_adb_restart = now

    from airtest.core.android.adb import ADB

    # 找不到 adb.exe 时 taskkill 返回非零，属正常情况，忽略
    _run_quietly(["taskkill", "/F", "/IM", "adb.exe"])
    time.sleep(0.5)
    _run_quietly([adb_path or ADB.get_adb_path(), "start-server"])
    return True


def diagnose_failure(detail: str, connection: dict | None = None) -> list[str]:
    """根据失败原因给出针对性排查提示，避免一律误导到 MINICAP。"""
    text = str(detail).lower()
    cfg = connection or {}
    tips: list[str] = []

    port = cfg.get("adb_port")
    if port not in (None, 5037):
        tips.append(
            f"ADB server 端口当前为 {port}，通常是 5037；"
            "若目标是网络模拟器，请先把地址填在设备序列号（如 127.0.0.1:5555）"
        )

    if any(key in text for key in (
        "devices not found", "device not ready", "offline", "unauthorized", "adb",
    )):
        tips.append("运行 adb devices 确认设备状态为 device（不是 offline / unauthorized）")
        tips.append("确认模拟器已启动完成，或手机 USB 调试已授权")

    if any(key in text for key in ("minicap", "cap_method", "install", "push", "screen")):
        tips.append("MINICAP 不可用时，在设置「设备连接」页把截图方式改为 JAVACAP")

    if not tips:
        tips.append("可在设置「设备连接」页调整参数后重试")
    return tips


def connect():
    """连接设备并配置 MINICAP 画质；失败时强制重启 adb 后重试一次。"""
    from airtest.core.api import connect_device
    from airtest.core.android.cap_methods.minicap import Minicap

    quality_flag = f"-Q {MINICAP_QUALITY}"
    if quality_flag not in Minicap.CMD:
        Minicap.CMD = f"{Minicap.CMD} {quality_flag}"

    connection = app_settings.get_connection(app_settings.load_settings())
    uri = build_uri()
    print(f"[信息] 连接 URI：{uri}")
    if connection.get("adb_port") != 5037:
        print(
            f"[警告] ADB server 端口为 {connection.get('adb_port')}，默认应为 5037；"
            "5555 通常是模拟器调试端口，应填在设备序列号中"
        )
    try:
        return connect_device(uri)
    except Exception as first_exc:
        print(f"[警告] 首次连接失败：{first_exc}")
        if "device not ready" in str(first_exc).lower():
            print("[信息] 设备尚未就绪，重启 ADB 无效，请确认模拟器/设备已启动完成")
            raise
        print("[信息] 正在强制结束 adb.exe 并重新连接...")
        try:
            restarted = _force_restart_adb(connection.get("adb_path", ""))
        except Exception as restart_exc:
            print(f"[警告] 重启 adb 失败：{restart_exc}")
            raise first_exc
        if not restarted:
            raise
        try:
            device = connect_device(uri)
        except Exception:
            print("[错误] 重启 adb 后仍连接失败")
            raise
        print("[信息] 强制重启 adb 后连接成功")
        return device


def disconnect(device) -> None:
    """释放 airtest 的推流/触控资源，并从全局设备列表移除。"""
    if device is None:
        return
    try:
        device.disconnect()
    except Exception as exc:
        print(f"[警告] 释放设备资源失败：{exc}")
    try:
        from airtest.core.helper import G

        G.DEVICE_LIST[:] = [item for item in G.DEVICE_LIST if item is not device]
        # 直接读底层属性，避免空列表时 G.DEVICE 的 getter 抛 NoDeviceError
        if G.__dict__.get("_DEVICE") is device:
            G.DEVICE = G.DEVICE_LIST[-1] if G.DEVICE_LIST else None
    except Exception as exc:
        print(f"[警告] 清理设备列表失败：{exc}")
