# -*- coding: utf-8 -*-
"""设备连接的异步执行与主窗口连接状态管理。"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .. import settings as app_settings
from ..device import (
    connect,
    disconnect as release_device,
    device_screen_wh,
    diagnose_failure,
)


class DeviceConnectWorker(QThread):
    """后台连接设备，避免 ADB 自愈等待阻塞界面。"""

    connected = Signal(object, object)  # device, screen_wh
    failed = Signal(str)

    def run(self) -> None:
        try:
            device = connect()
            screen_wh = device_screen_wh(device)
        except Exception as exc:
            self.failed.emit(str(exc).strip() or type(exc).__name__)
            return
        if self.isInterruptionRequested():
            return
        self.connected.emit(device, screen_wh)


class DeviceConnectionMixin:
    @property
    def connection_status(self) -> str:
        if self._connecting:
            return "正在连接..."
        if self.device is None:
            return "未连接"
        method = getattr(getattr(self.device, "screen_proxy", None), "method_name", "MINICAP")
        return f"已连接（{method}）"

    @property
    def can_connect(self) -> bool:
        return not self._connecting and self.device is None

    @property
    def can_disconnect(self) -> bool:
        return not self._connecting and self.device is not None

    def toggle_connection(self) -> None:
        """工具栏单一按钮：未连接则连接，已连接则断开。"""
        if self._connecting:
            print("[信息] 正在连接设备，请稍候")
            return
        if self.device is None:
            self.connect_device()
        else:
            self.disconnect_device()

    def _on_connection_state_for_toolbar(self, status: str, can_connect: bool, can_disconnect: bool) -> None:
        """连接状态变化时，工具栏按钮图标切到对应动作。"""
        self.toolbar.set_connected(self.device is not None)

    def disconnect_device(self) -> None:
        """断开当前设备：停止预览、释放 airtest 资源并清空画面。"""
        if self._connecting:
            print("[信息] 正在连接设备，请稍候")
            return
        if self.device is None:
            print("[信息] 当前未连接设备")
            return
        device = self.device
        self.device = None
        self.timer.stop()
        self._device_retry_timer.stop()
        self.latest_bgr = None
        self.frozen_bgr = None
        self._capture_failures = 0
        self._waiting_device = False
        self.screen.setText("未连接设备\n请在设置中点击「连接设备」")
        self.setWindowTitle("AirPicker · 未连接设备")
        release_device(device)
        print("[信息] 设备已断开")
        self._emit_connection_state()

    def connect_device(self) -> None:
        """发起一次异步连接；连接中或已连接时忽略重复点击。"""
        if not self.can_connect:
            return
        self._connecting = True
        self.screen.setText("正在连接设备...")
        self._emit_connection_state()
        print("[信息] 正在连接设备：...")
        worker = DeviceConnectWorker(self)
        worker.connected.connect(self._on_device_connected)
        worker.failed.connect(self._on_device_connect_failed)
        worker.finished.connect(self._on_connect_finished)
        self._connect_worker = worker
        worker.start()

    def _emit_connection_state(self) -> None:
        self.connectionStateChanged.emit(
            self.connection_status, self.can_connect, self.can_disconnect
        )

    def _on_device_connected(self, device, screen_wh) -> None:
        if self._closing:
            return
        self.device = device
        self.setWindowTitle("AirPicker")
        if screen_wh:
            self._screen_wh = tuple(screen_wh)
        method = getattr(getattr(device, "screen_proxy", None), "method_name", "MINICAP")
        print(f"[信息] 设备连接成功（{method}）")
        if screen_wh:
            print(f"[信息] 设备屏幕：{screen_wh[0]} x {screen_wh[1]}")
        print("[信息] 默认模式：单击=点击设备，拖拽=滑动设备；工具栏可切换框选 / 取点")
        self._connecting = False
        self._emit_connection_state()
        self._maybe_start_preview()

    def _on_device_connect_failed(self, detail: str) -> None:
        if self._closing:
            return
        self._connecting = False
        self.screen.setText("设备连接失败\n可在设置中重试")
        self._emit_connection_state()
        print(f"[错误] 设备连接失败：{detail}")
        cfg = app_settings.get_connection(app_settings.load_settings())
        for tip in diagnose_failure(detail, cfg):
            print(f"[提示] {tip}")

    def _on_connect_finished(self) -> None:
        worker = self._connect_worker
        self._connect_worker = None
        if worker is not None:
            worker.deleteLater()

    def _require_device(self) -> bool:
        if self.device is None:
            print("[警告] 尚未连接设备，请在设置中点击「连接设备」")
            return False
        return True
