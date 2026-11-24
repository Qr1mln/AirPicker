# -*- coding: utf-8 -*-
"""AI 模块接入层：四个可停靠面板的显隐、状态保存与两步场景识别。"""
from __future__ import annotations

import base64

from PySide6.QtCore import QByteArray, QEvent, QObject, QPoint, QThread, QTimer, Qt
from PySide6.QtWidgets import QDockWidget

from . import config
from .api import ANALYZE_QUESTION, MatchWorker, RecognitionWorker
from .panel import AIPanel


class AIAddon(QObject):
    """AI 面板拆成识别 / 场景配置 / 场景匹配 / 状态日志四个停靠面板。"""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._worker: QThread | None = None
        self._last_analysis = ""
        self._visible_pref = bool(config.load()["panel_visible"])
        self._setting_visibility = False
        self._restoring_state = False
        self._state_timer = QTimer(self)
        self._state_timer.setSingleShot(True)
        self._state_timer.timeout.connect(self._save_state)

        self.panel = AIPanel(window)
        self.docks: list[QDockWidget] = self.panel.docks
        self.panel.recognize_button.clicked.connect(self.start_recognition)
        self.panel.match_requested.connect(self.start_matching)
        for dock in self.docks:
            dock.visibilityChanged.connect(self._on_dock_visibility)
            dock.topLevelChanged.connect(self._on_dock_changed)
            dock.dockLocationChanged.connect(self._on_dock_changed)

        window.toolbar.ai_clicked = self.toggle
        window.toolbar.set_ai_active(self._visible_pref)
        self.panel.set_visible_all(self._visible_pref)
        window.installEventFilter(self)
        QTimer.singleShot(0, self._restore_state)

    def _save_state(self) -> None:
        if self._restoring_state:
            return
        state = bytes(self.window.saveState())
        config.save(window_state=base64.b64encode(state).decode("ascii"))

    def _restore_state(self) -> None:
        self._restoring_state = True
        try:
            raw = config.load().get("window_state", "")
            if raw:
                self.window.restoreState(QByteArray.fromBase64(raw.encode("ascii")))
            else:
                self.panel.set_visible_all(self._visible_pref)
                self.window.resizeDocks(self.docks, [280, 380, 240], Qt.Horizontal)
                self.window.resizeDocks(self.docks, [150, 390, 220], Qt.Vertical)
            if not self._visible_pref:
                self.panel.set_visible_all(False)
        finally:
            self._restoring_state = False
        self._sync_dock_width()
        self._place_toolbar()

    def _sync_dock_width(self) -> None:
        width = 0
        for dock in self.docks:
            if (
                not dock.isHidden()
                and not dock.isFloating()
                and self.window.dockWidgetArea(dock) == Qt.RightDockWidgetArea
            ):
                width += dock.width()
        self.window._right_dock_width = width

    def _place_toolbar(self) -> None:
        anchor = getattr(self.window, "screen", None) or self.window.centralWidget()
        if anchor is None:
            return
        origin = anchor.mapToGlobal(QPoint(0, 0))
        toolbar = self.window.toolbar
        target = self.window.mapFromGlobal(
            QPoint(origin.x() + 20, origin.y() + 60)
        )
        toolbar.move(target)
        toolbar.constrain_to_window()

    def _on_dock_visibility(self, _visible: bool) -> None:
        if self._setting_visibility or self._restoring_state:
            return
        self._visible_pref = self.panel.any_visible()
        self.window.toolbar.set_ai_active(self._visible_pref)
        config.save(panel_visible=self._visible_pref)
        self._sync_dock_width()
        self._state_timer.start(400)

    def _on_dock_changed(self, *_args) -> None:
        if self._restoring_state:
            return
        self._sync_dock_width()
        self._state_timer.start(400)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.window:
            kind = event.type()
            if kind == QEvent.Close:
                self._save_state()
                config.save(panel_visible=self._visible_pref)
                if self._worker is not None and self._worker.isRunning():
                    self._worker.requestInterruption()
                    self._worker.wait(2000)
            elif kind in (QEvent.Move, QEvent.Resize):
                self._sync_dock_width()
                self._state_timer.start(400)
        return super().eventFilter(obj, event)

    def toggle(self) -> None:
        self._set_visible(not self.panel.any_visible())

    def collapse(self) -> None:
        self._set_visible(False)

    def _set_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self.panel.any_visible():
            return
        self._visible_pref = visible
        self._setting_visibility = True
        try:
            self.panel.set_visible_all(visible)
        finally:
            self._setting_visibility = False
        self.window.toolbar.set_ai_active(visible)
        config.save(panel_visible=visible)
        self._sync_dock_width()
        self._state_timer.start(100)

    # -------- 第一步：识别界面 --------
    def start_recognition(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        frame = self.window._screenshot_frame()
        if frame is None:
            self.panel.append_log("[识别失败] 暂无画面，无法识别界面")
            return
        cfg = config.load()
        worker = RecognitionWorker(
            frame.copy(), ANALYZE_QUESTION,
            cfg["api_url"], cfg["model"], cfg["timeout"], cfg["api_token"],
            cfg["temperature"], cfg["retry_temperature"], self,
        )
        worker.prompt_ready.connect(lambda text: self._log_prompt("界面识别", text))
        worker.result_ready.connect(self._on_analyzed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        self.panel.recognize_button.setEnabled(False)
        self.panel.recognize_button.setText("识别中…")
        self.panel.append_log("已截取当前帧，正在识别界面元素…")
        worker.start()

    def _on_analyzed(self, analysis: str, elapsed: float) -> None:
        self._last_analysis = analysis.strip()
        self.panel.append_log(
            f"界面元素信息（耗时 {elapsed:.1f}s）：\n{analysis}\n{'-' * 28}"
        )

    # -------- 第二步：场景配置匹配 --------
    def _scenes_from_table(self) -> list[dict[str, str]]:
        return self.panel.scenes()

    def start_matching(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._last_analysis:
            self.panel.append_log("[提示] 请先点击「识别界面」获取界面元素信息")
            return
        scenes = self._scenes_from_table()
        if not scenes:
            self.panel.append_log("[提示] 场景配置为空，请填写场景名称和描述")
            return
        cfg = config.load()
        worker = MatchWorker(
            self._last_analysis, scenes,
            cfg["api_url"], cfg["model"], cfg["timeout"], cfg["api_token"],
            cfg["temperature"], self,
        )
        worker.prompt_ready.connect(lambda text: self._log_prompt("场景匹配", text))
        worker.matched.connect(self._on_matched)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        self.panel.match_button.setEnabled(False)
        self.panel.match_button.setText("匹配中…")
        self.panel.append_log("正在用场景配置和界面识别结果匹配场景…")
        worker.start()

    def _on_matched(self, scene: str, elapsed: float) -> None:
        self.panel.append_log(
            f"匹配场景：{scene or '无'} · 耗时 {elapsed:.1f}s\n{'-' * 28}"
        )

    def _log_prompt(self, title: str, prompt: str) -> None:
        self.panel.append_log(f"[{title}提示词]\n{prompt}\n{'-' * 28}")

    def _on_failed(self, message: str) -> None:
        self.panel.append_log(f"[识别失败] {message}")

    def _on_finished(self) -> None:
        self.panel.recognize_button.setText("识别界面")
        self.panel.recognize_button.setEnabled(True)
        self.panel.match_button.setText("匹配场景")
        self.panel.match_button.setEnabled(True)
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
