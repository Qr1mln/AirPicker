# -*- coding: utf-8 -*-
"""AI 工具：识别 / 场景配置 / 状态日志可停靠面板的构建与对外接口。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QHBoxLayout,
    QListWidget,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import config
from .scene_cards import SceneCardsMixin
from .scene_editor import SceneEditorMixin

_DOCK_STYLE = (
    "QDockWidget { background: #1e1e1e; color: #dddddd; border: 1px solid #3a3a3a; }"
    "QDockWidget::title { background: #2b2b2b; color: #dddddd; padding: 4px 8px; "
    "border-bottom: 1px solid #3a3a3a; }"
)

_PANE_STYLE = (
    "QWidget { background: #1e1e1e; color: #dddddd; }"
    "QLabel { color: #dddddd; }"
    "QLineEdit, QTextEdit, QPlainTextEdit, QListWidget { background: #2b2b2b; color: #dddddd; "
    "border: 1px solid #3a3a3a; border-radius: 4px; }"
    "QPushButton { background: #2b2b2b; color: #dddddd; border: 1px solid #3a3a3a; "
    "border-radius: 4px; padding: 4px 10px; }"
    "QPushButton:hover:!disabled { background: #3a3a3a; }"
    "QPushButton:disabled { color: #666666; }"
    "QPushButton#sceneActionButton { background: #242424; color: #ffffff; "
    "border: 1px solid #3a3a3a; border-radius: 6px; padding: 6px 12px; }"
    "QPushButton#sceneActionButton:hover:!disabled { background: #363636; border-color: #555555; }"
    "QPushButton#sceneActionButton:pressed { background: #1e1e1e; }"
    "QToolButton { background: transparent; color: #aaaaaa; border: none; padding: 2px 5px; }"
    "QToolButton:hover { color: #ffffff; background: #3a3a3a; border-radius: 3px; }"
    "QToolButton#sceneCardButton { background: #242424; color: #dddddd; "
    "border: 1px solid #3a3a3a; border-radius: 4px; padding: 2px 6px; }"
    "QToolButton#sceneCardButton:hover { background: #3a3a3a; color: #ffffff; }"
    "QFrame { background: #292929; border: 1px solid #3a3a3a; border-radius: 6px; }"
)


class AIPanel(SceneCardsMixin, SceneEditorMixin, QObject):
    """构建可停靠面板，并对外暴露按钮、场景列表和日志接口。"""

    collapse_requested = Signal()
    match_requested = Signal()

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self.recognition_frame = None  # 最近一次界面识别使用的画面帧，由 AIAddon 写入
        self._docks: list[QDockWidget] = []
        self._create_docks()
        extra = (
            "QMainWindow::separator, QSplitter::handle { background: #3a3a3a; }"
        )
        self.window.setStyleSheet((self.window.styleSheet() or "") + "\n" + extra)

    # -------- 面板构建 --------
    def _create_docks(self) -> None:
        self.recognize_dock = self._make_dock("aiRecognizeDock", "识别界面")
        self.scene_dock = self._make_dock("aiSceneDock", "场景配置")
        self.log_dock = self._make_dock("aiLogDock", "状态日志")
        self._docks = [self.recognize_dock, self.scene_dock, self.log_dock]
        self._build_recognize_pane()
        self._build_scene_pane()
        self._build_log_pane()

    def _make_dock(self, object_name: str, title: str) -> QDockWidget:
        dock = QDockWidget(title, self.window)
        dock.setObjectName(object_name)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        dock.setStyleSheet(_DOCK_STYLE)
        self.window.addDockWidget(Qt.RightDockWidgetArea, dock)
        return dock

    @staticmethod
    def _pane(dock: QDockWidget, margins: tuple[int, int, int, int] = (10, 8, 10, 8)) -> QWidget:
        pane = QWidget()
        pane.setStyleSheet(_PANE_STYLE)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(*margins)
        layout.setSpacing(8)
        dock.setWidget(pane)
        return pane

    def _build_recognize_pane(self) -> None:
        pane = self._pane(self.recognize_dock)
        layout = pane.layout()

        self.recognize_button = QPushButton("识别界面")
        self.recognize_button.setToolTip("分析当前画面，返回可见的界面元素信息")
        layout.addWidget(self.recognize_button)

        actions = QHBoxLayout()
        start = QPushButton("▶ 开始")
        stop = QPushButton("■ 停止")
        for button in (start, stop):
            button.setEnabled(False)
            button.setToolTip("P2 阶段接入")
        actions.addStretch(1)
        actions.addWidget(start)
        actions.addWidget(stop)
        layout.addLayout(actions)
        layout.addStretch(1)

    def _build_scene_pane(self) -> None:
        pane = self._pane(self.scene_dock)
        layout = pane.layout()

        self.scene_list = QListWidget()
        self.scene_list.setObjectName("sceneList")
        self.scene_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.scene_list.itemDoubleClicked.connect(self._edit_scene_item)
        layout.addWidget(self.scene_list)

        row = QHBoxLayout()
        add_button = QPushButton("+ 添加场景")
        add_button.setObjectName("sceneActionButton")
        add_button.clicked.connect(self._add_scene)
        edit_button = QPushButton("编辑选中")
        edit_button.setObjectName("sceneActionButton")
        edit_button.clicked.connect(self._edit_selected_scene)
        self.match_button = QPushButton("匹配场景")
        self.match_button.setObjectName("sceneActionButton")
        self.match_button.setToolTip("用场景配置和上次界面识别结果匹配场景")
        self.match_button.clicked.connect(self.match_requested.emit)
        for button in (add_button, edit_button, self.match_button):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        self._refresh_scene_list()

    def _build_log_pane(self) -> None:
        pane = self._pane(self.log_dock, (10, 6, 10, 8))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("识别结果、耗时等信息将显示在这里")
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._show_log_menu)
        pane.layout().addWidget(self.log_view)

    # -------- 对外接口 --------
    @property
    def docks(self) -> list[QDockWidget]:
        return list(self._docks)

    def any_visible(self) -> bool:
        return any(not dock.isHidden() for dock in self._docks)

    def set_visible_all(self, visible: bool) -> None:
        for dock in self._docks:
            dock.setVisible(bool(visible))

    def scenes(self) -> list[dict[str, str]]:
        """供场景匹配使用的场景配置（名称和描述都非空）。"""
        return [
            {"name": s.get("name", ""), "feature": s.get("feature", "")}
            for s in config.load()["scenes"]
            if s.get("name") and s.get("feature")
        ]

    def append_log(self, text: str) -> None:
        """纯文本追加日志，避免把模型输出当 HTML 解析；自动滚到底部。"""
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.insertPlainText(text + "\n")
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)

    # -------- 日志右键菜单 --------
    def _show_log_menu(self, pos) -> None:
        menu = QMenu(self.log_view)
        copy_action = menu.addAction("复制")
        copy_action.setEnabled(self.log_view.textCursor().hasSelection())
        clear_action = menu.addAction("清除日志")
        action = menu.exec(self.log_view.mapToGlobal(pos))
        if action == copy_action:
            self.log_view.copy()
        elif action == clear_action:
            self.log_view.clear()
