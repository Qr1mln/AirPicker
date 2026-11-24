# -*- coding: utf-8 -*-
"""AI 工具：识别 / 场景配置 / 场景匹配 / 状态日志四个可停靠面板。"""
from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import config

_DOCK_STYLE = (
    "QDockWidget { background: #1e1e1e; color: #dddddd; border: 1px solid #3a3a3a; }"
    "QDockWidget::title { background: #2b2b2b; color: #dddddd; padding: 4px 8px; "
    "border-bottom: 1px solid #3a3a3a; }"
)

_PANE_STYLE = (
    "QWidget { background: #1e1e1e; color: #dddddd; }"
    "QGroupBox { color: #dddddd; border: 1px solid #3a3a3a; border-radius: 6px; "
    "margin-top: 10px; padding-top: 10px; }"
    "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
    "QRadioButton, QLabel { color: #dddddd; }"
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


class AIPanel(QObject):
    """构建四个独立停靠面板，并对外暴露按钮、场景列表和日志接口。"""

    collapse_requested = Signal()
    match_requested = Signal()

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
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

        mode = QGroupBox("工作模式")
        mode_layout = QVBoxLayout(mode)
        mode_layout.setContentsMargins(10, 6, 10, 8)
        mode_layout.setSpacing(4)
        manual = QRadioButton("手动操作")
        manual.setChecked(True)
        mode_layout.addWidget(manual)
        layout.addWidget(mode)

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

        cruise_button = QPushButton("自动巡航（预留）")
        cruise_button.setObjectName("sceneActionButton")
        cruise_button.setEnabled(False)
        cruise_button.setToolTip("P2 阶段接入")
        layout.addWidget(cruise_button)

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
            {"name": s.get("name", ""), "desc": s.get("desc", "")}
            for s in config.load()["scenes"]
            if s.get("name") and s.get("desc")
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

    # -------- 场景卡片列表 --------
    def _refresh_scene_list(self) -> None:
        self.scene_list.clear()
        for index, scene in enumerate(config.load()["scenes"]):
            item = QListWidgetItem()
            item.setSizeHint(QSize(10, 72))
            self.scene_list.addItem(item)
            self.scene_list.setItemWidget(item, self._make_scene_card(index, scene))

    def _make_scene_card(self, index: int, scene: dict[str, str]) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #292929; border: 1px solid #3a3a3a; border-radius: 6px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)

        top = QHBoxLayout()
        name = QLabel(scene.get("name") or "(未命名)")
        name.setStyleSheet("color: #ffffff; font-weight: bold;")
        top.addWidget(name, 1)
        for text, tip, callback in (
            ("↑", "上移", lambda: self._move_scene(index, -1)),
            ("↓", "下移", lambda: self._move_scene(index, 1)),
            ("×", "删除", lambda: self._delete_scene(index)),
        ):
            button = QToolButton()
            button.setObjectName("sceneCardButton")
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda _checked=False, cb=callback: cb())
            top.addWidget(button)
        card_layout.addLayout(top)

        summary = " ".join(scene.get("desc", "").split())[:100] or "（无描述）"
        desc = QLabel(summary)
        desc.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        return card

    def _scene_editor(self, scene: dict[str, str] | None = None) -> dict[str, str] | None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("编辑场景" if scene else "新增场景")
        dialog.setStyleSheet(
            "QDialog, QLineEdit, QPlainTextEdit { background: #2b2b2b; color: #dddddd; }"
            "QLabel { color: #dddddd; }"
            "QPushButton { background: #3a3a3a; color: #dddddd; padding: 4px 10px; }"
        )
        form = QFormLayout(dialog)
        name_edit = QLineEdit(scene.get("name", "") if scene else "")
        desc_edit = QPlainTextEdit()
        desc_edit.setPlainText(scene.get("desc", "") if scene else "")
        form.addRow("场景名", name_edit)
        form.addRow("描述", desc_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        dialog.resize(560, 360)
        if dialog.exec() != QDialog.Accepted:
            return None
        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(dialog, "提示", "场景名不能为空")
            return None
        return {"name": name, "desc": desc_edit.toPlainText().strip()}

    def _add_scene(self) -> None:
        data = self._scene_editor()
        if data is not None:
            scenes = config.load()["scenes"]
            scenes.append(data)
            config.save(scenes=scenes)
            self._refresh_scene_list()

    def _edit_scene_item(self, item) -> None:
        self._edit_scene_at(self.scene_list.row(item))

    def _edit_selected_scene(self) -> None:
        self._edit_scene_at(self.scene_list.currentRow())

    def _edit_scene_at(self, index: int) -> None:
        scenes = config.load()["scenes"]
        if not 0 <= index < len(scenes):
            return
        data = self._scene_editor(scenes[index])
        if data is not None:
            scenes[index] = data
            config.save(scenes=scenes)
            self._refresh_scene_list()

    def _delete_scene(self, index: int) -> None:
        scenes = config.load()["scenes"]
        if 0 <= index < len(scenes):
            scenes.pop(index)
            config.save(scenes=scenes)
            self._refresh_scene_list()

    def _move_scene(self, index: int, delta: int) -> None:
        scenes = config.load()["scenes"]
        target = index + delta
        if 0 <= index < len(scenes) and 0 <= target < len(scenes):
            scenes[index], scenes[target] = scenes[target], scenes[index]
            config.save(scenes=scenes)
            self._refresh_scene_list()

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
