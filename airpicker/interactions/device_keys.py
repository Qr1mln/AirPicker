# -*- coding: utf-8 -*-
"""工具栏设备按键：向设备发送 BACK / HOME。"""
from __future__ import annotations


class DeviceKeyMixin:
    def device_back(self) -> None:
        self._send_key("BACK", "返回")

    def device_home(self) -> None:
        self._send_key("HOME", "主页")

    def _send_key(self, key: str, label: str) -> None:
        if not self._require_device():
            return
        try:
            self.device.keyevent(key)
            print(f"[按键] {label}")
        except Exception as exc:
            print(f"[警告] {label}失败：{exc}")
