# -*- coding: utf-8 -*-
"""悬浮工具栏设置：横 / 竖排列、资源 / 截图目录、截图命名与代码回写表达式。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import screenshot_names, settings
from ..ai import AILogSettingsTab, AISettingsTab
from ..config import ROOT, SCREENSHOT_DIR
from ..connection import (
    CAP_LABELS,
    IME_LABELS,
    ORI_LABELS,
    PRESETS,
    PRESET_LABELS,
    TOUCH_LABELS,
    URI_HINT,
    build_uri,
    match_preset,
    normalize as normalize_connection,
)


class ToolbarSettingsDialog(QDialog):
    """悬浮工具栏设置弹窗。"""

    connect_requested = Signal()
    disconnect_requested = Signal()

    def __init__(
        self,
        horizontal: bool,
        resource_dir: Path | str = "",
        screenshot_dir: Path | str = "",
        screenshot_name_mode: str = "random",
        screenshot_random_expr: str = "screen_{datetime}_{ms}",
        screenshot_seq_expr: str = "screen_{0000}",
        screenshot_seq_next: int | None = None,
        project_dir: Path | str = "",
        coord_expr: str = "({x}, {y})",
        tpl_expr: str = 'Template(r"{path}", record_pos=({rx}, {ry}), resolution=({rw}, {rh}))',
        swipe_expr: str = "swipe(({x1}, {y1}), ({x2}, {y2}))",
        lock_ratio: bool = True,
        connection_status: str = "未连接",
        can_connect: bool = True,
        can_disconnect: bool = False,
        auto_connect: bool = False,
        connection: dict | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(600)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(14)

        tabs = QTabWidget()
        conn_tab = QWidget()
        conn_outer = QVBoxLayout(conn_tab)
        conn_outer.setContentsMargins(0, 0, 0, 0)
        conn_outer.setSpacing(12)
        general_tab = QWidget()
        gen_layout = QVBoxLayout(general_tab)
        gen_layout.setContentsMargins(0, 0, 0, 0)
        tabs.addTab(conn_tab, "设备连接")
        tabs.addTab(general_tab, "通用设置")
        tabs.addTab(AISettingsTab(self), "AI 设置")
        tabs.addTab(AILogSettingsTab(self), "日志显示")

        conn_cfg = normalize_connection(connection)
        conn_group = QGroupBox("连接设置")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setContentsMargins(12, 10, 12, 10)
        conn_layout.setSpacing(8)
        conn_row = QHBoxLayout()
        conn_row.setSpacing(8)
        self.conn_status = QLabel(f"状态：{connection_status}")
        self.conn_button = QPushButton("连接设备")
        self.conn_button.setEnabled(bool(can_connect))
        self.conn_button.clicked.connect(self.connect_requested.emit)
        self.disconnect_button = QPushButton("断开")
        self.disconnect_button.setEnabled(bool(can_disconnect))
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        conn_row.addWidget(self.conn_status, 1)
        conn_row.addWidget(self.conn_button)
        conn_row.addWidget(self.disconnect_button)
        conn_layout.addLayout(conn_row)
        self.auto_connect_check = QCheckBox("启动界面加载完成后自动连接设备")
        self.auto_connect_check.setChecked(bool(auto_connect))
        self.auto_connect_check.stateChanged.connect(self._on_auto_connect_changed)
        conn_layout.addWidget(self.auto_connect_check)
        conn_outer.addWidget(conn_group)

        params_group = QGroupBox("Android 连接参数（Airtest URI）")
        params_form = QFormLayout(params_group)
        params_form.setLabelAlignment(Qt.AlignRight)
        params_form.setHorizontalSpacing(12)
        params_form.setVerticalSpacing(8)

        self.serial_edit = QLineEdit(conn_cfg["serial"])
        self.serial_edit.setPlaceholderText("留空 = 自动选择唯一设备；多设备填序列号")
        params_form.addRow("设备序列号", self.serial_edit)

        host_widget = QWidget()
        host_row = QHBoxLayout(host_widget)
        host_row.setContentsMargins(0, 0, 0, 0)
        host_row.setSpacing(6)
        self.host_edit = QLineEdit(conn_cfg["adb_host"])
        self.host_edit.setPlaceholderText("127.0.0.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(conn_cfg["adb_port"])
        host_row.addWidget(self.host_edit, 1)
        host_row.addWidget(QLabel(":"))
        host_row.addWidget(self.port_spin)
        params_form.addRow("ADB 地址 / 端口", host_widget)
        port_hint = QLabel(
            "ADB server 端口默认 5037；网络模拟器地址（如 127.0.0.1:5555）请填在「设备序列号」"
        )
        port_hint.setStyleSheet("color: #888; font-size: 11px;")
        port_hint.setWordWrap(True)
        params_form.addRow("", port_hint)

        self.preset_combo = QComboBox()
        for value, text in PRESET_LABELS:
            self.preset_combo.addItem(text, value)
        preset_index = self.preset_combo.findData(match_preset(conn_cfg))
        self.preset_combo.setCurrentIndex(max(0, preset_index))
        params_form.addRow("连接方式", self.preset_combo)

        methods_widget = QWidget()
        methods_form = QFormLayout(methods_widget)
        methods_form.setContentsMargins(0, 0, 0, 0)
        methods_form.setHorizontalSpacing(12)
        methods_form.setVerticalSpacing(8)

        def add_method_row(label: str, items, current: str) -> QComboBox:
            combo = QComboBox()
            for value, text in items:
                combo.addItem(text, value)
            combo.setCurrentIndex(max(0, combo.findData(current)))
            methods_form.addRow(label, combo)
            return combo

        self.cap_combo = add_method_row("截图方式", CAP_LABELS, conn_cfg["cap_method"])
        self.touch_combo = add_method_row("触控方式", TOUCH_LABELS, conn_cfg["touch_method"])
        self.ime_combo = add_method_row("输入方式", IME_LABELS, conn_cfg["ime_method"])
        self.ori_combo = add_method_row("屏幕方向", ORI_LABELS, conn_cfg["ori_method"])
        self.methods_widget = methods_widget
        params_form.addRow("", methods_widget)

        self.uri_preview = QLabel()
        self.uri_preview.setStyleSheet("color: #6ab04c; font-size: 11px;")
        self.uri_preview.setWordWrap(True)
        params_form.addRow("连接 URI", self.uri_preview)
        uri_hint = QLabel(URI_HINT)
        uri_hint.setStyleSheet("color: #888; font-size: 11px;")
        uri_hint.setWordWrap(True)
        params_form.addRow("", uri_hint)

        self.display_edit = QLineEdit(conn_cfg["display_id"])
        self.display_edit.setPlaceholderText("多屏时填写，如 1")
        params_form.addRow("display_id", self.display_edit)
        self.input_event_edit = QLineEdit(conn_cfg["input_event"])
        self.input_event_edit.setPlaceholderText("如 /dev/input/event3")
        params_form.addRow("input_event", self.input_event_edit)
        self.adb_path_edit = QLineEdit(conn_cfg["adb_path"])
        self.adb_path_edit.setPlaceholderText("留空使用 airtest 自带 adb")
        params_form.addRow("adb_path", self.adb_path_edit)

        conn_outer.addWidget(params_group)
        conn_outer.addStretch(1)

        for widget in (self.serial_edit, self.host_edit, self.display_edit,
                       self.input_event_edit, self.adb_path_edit):
            widget.textChanged.connect(self._on_connection_changed)
        self.port_spin.valueChanged.connect(self._on_connection_changed)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        for combo in (self.cap_combo, self.touch_combo, self.ime_combo, self.ori_combo):
            combo.currentIndexChanged.connect(self._on_method_changed)
        self._on_preset_changed()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.combo = QComboBox()
        self.combo.addItem("竖向", False)
        self.combo.addItem("横向", True)
        self.combo.setCurrentIndex(1 if horizontal else 0)
        form.addRow("工具栏排列", self.combo)

        self.aspect_check = QCheckBox("设备画面保持宽高比（取消则拉伸填满画面区）")
        self.aspect_check.setChecked(bool(lock_ratio))
        form.addRow("", self.aspect_check)

        project_widget = QWidget()
        project_row = QHBoxLayout(project_widget)
        project_row.setContentsMargins(0, 0, 0, 0)
        project_row.setSpacing(6)
        self.project_edit = QLineEdit(str(project_dir))
        self.project_edit.setPlaceholderText("留空则相对 airpicker/scripts 计算")
        project_browse = QPushButton("浏览...")
        project_browse.clicked.connect(self._browse_project_dir)
        project_row.addWidget(self.project_edit, 1)
        project_row.addWidget(project_browse)
        form.addRow("项目目录", project_widget)

        dir_widget = QWidget()
        dir_row = QHBoxLayout(dir_widget)
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.setSpacing(6)
        self.dir_edit = QLineEdit(str(resource_dir))
        self.dir_edit.setPlaceholderText("留空则使用项目 pics 目录")
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse)
        form.addRow("资源目录", dir_widget)

        shot_widget = QWidget()
        shot_row = QHBoxLayout(shot_widget)
        shot_row.setContentsMargins(0, 0, 0, 0)
        shot_row.setSpacing(6)
        self.shot_edit = QLineEdit(str(screenshot_dir))
        self.shot_edit.setPlaceholderText("留空则使用项目 screenshots 目录")
        shot_browse = QPushButton("浏览...")
        shot_browse.clicked.connect(self._browse_screenshot_dir)
        shot_row.addWidget(self.shot_edit, 1)
        shot_row.addWidget(shot_browse)
        form.addRow("截图目录", shot_widget)

        self.name_combo = QComboBox()
        self.name_combo.addItem("随机", "random")
        self.name_combo.addItem("序号", "sequence")
        index = self.name_combo.findData(screenshot_name_mode)
        self.name_combo.setCurrentIndex(max(0, index))
        form.addRow("截图命名", self.name_combo)

        self.expr_label = QLabel("随机表达式")
        self.name_stack = QStackedWidget()

        random_page = QWidget()
        random_layout = QVBoxLayout(random_page)
        random_layout.setContentsMargins(0, 0, 0, 0)
        random_layout.setSpacing(4)
        self.random_expr_edit = QLineEdit(screenshot_random_expr)
        self.random_preview = QLabel()
        self.random_preview.setStyleSheet("color: #6ab04c; font-size: 11px;")
        random_hint = QLabel(screenshot_names.NAME_HINT)
        random_hint.setStyleSheet("color: #888; font-size: 11px;")
        random_hint.setWordWrap(True)
        random_layout.addWidget(self.random_expr_edit)
        random_layout.addWidget(self.random_preview)
        random_layout.addWidget(random_hint)

        seq_page = QWidget()
        seq_layout = QVBoxLayout(seq_page)
        seq_layout.setContentsMargins(0, 0, 0, 0)
        seq_layout.setSpacing(4)
        self.seq_expr_edit = QLineEdit(screenshot_seq_expr)
        self.seq_preview = QLabel()
        self.seq_preview.setStyleSheet("color: #6ab04c; font-size: 11px;")
        seq_hint = QLabel(screenshot_names.SEQ_HINT)
        seq_hint.setStyleSheet("color: #888; font-size: 11px;")
        seq_hint.setWordWrap(True)

        counter_widget = QWidget()
        counter_row = QHBoxLayout(counter_widget)
        counter_row.setContentsMargins(0, 0, 0, 0)
        counter_row.setSpacing(6)
        self.seq_spin = QSpinBox()
        self.seq_spin.setRange(0, 999999)
        initial_next = (
            screenshot_seq_next if screenshot_seq_next is not None
            else screenshot_names.next_sequence_number(self._preview_dir(), screenshot_seq_expr)
        )
        self.seq_spin.setValue(max(0, int(initial_next)))
        reset_counter = QPushButton("重置计数")
        reset_counter.clicked.connect(self._reset_seq_counter)
        counter_row.addWidget(QLabel("当前计数"))
        counter_row.addWidget(self.seq_spin, 1)
        counter_row.addWidget(reset_counter)

        seq_layout.addWidget(self.seq_expr_edit)
        seq_layout.addWidget(self.seq_preview)
        seq_layout.addWidget(counter_widget)
        seq_layout.addWidget(seq_hint)

        self.name_stack.addWidget(random_page)
        self.name_stack.addWidget(seq_page)
        form.addRow(self.expr_label, self.name_stack)

        self.random_expr_edit.textChanged.connect(self._update_previews)
        self.seq_expr_edit.textChanged.connect(self._update_previews)
        self.seq_spin.valueChanged.connect(self._update_previews)
        self.shot_edit.textChanged.connect(self._update_previews)
        self.name_combo.currentIndexChanged.connect(self._on_name_mode_changed)
        self._on_name_mode_changed()
        self._update_previews()

        self.expr_edit = QLineEdit(coord_expr)
        form.addRow("坐标回写", self.expr_edit)
        coord_hint = QLabel("变量：{x}=X坐标，{y}=Y坐标（可任意组合，如 ({x}, {y})）")
        coord_hint.setStyleSheet("color: #888; font-size: 11px;")
        coord_hint.setWordWrap(True)
        form.addRow("", coord_hint)

        self.tpl_edit = QLineEdit(tpl_expr)
        form.addRow("模板回写", self.tpl_edit)
        tpl_hint = QLabel(
            "变量：{name}=文件名，{path}=相对路径，\n"
            "{rx}/{ry}=模板中心偏移(-0.5~0.5)，{rw}/{rh}=屏幕宽高（可任意组合）"
        )
        tpl_hint.setStyleSheet("color: #888; font-size: 11px;")
        tpl_hint.setWordWrap(True)
        form.addRow("", tpl_hint)

        self.swipe_edit = QLineEdit(swipe_expr)
        form.addRow("滑动回写", self.swipe_edit)
        swipe_hint = QLabel("变量：{x1}/{y1}=起点，{x2}/{y2}=终点（可任意组合）")
        swipe_hint.setStyleSheet("color: #888; font-size: 11px;")
        swipe_hint.setWordWrap(True)
        form.addRow("", swipe_hint)

        gen_layout.addLayout(form)
        root.addWidget(tabs)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.setFixedWidth(84)
        cancel.setFixedWidth(84)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

    def is_horizontal(self) -> bool:
        return bool(self.combo.currentData())

    def set_connection_status(
        self, status: str, can_connect: bool, can_disconnect: bool
    ) -> None:
        self.conn_status.setText(f"状态：{status}")
        self.conn_button.setEnabled(bool(can_connect))
        self.disconnect_button.setEnabled(bool(can_disconnect))

    def _on_auto_connect_changed(self, state: int) -> None:
        settings.save_auto_connect(bool(state))

    def auto_connect(self) -> bool:
        return self.auto_connect_check.isChecked()

    def connection(self) -> dict:
        return {
            "adb_host": self.host_edit.text().strip(),
            "adb_port": self.port_spin.value(),
            "serial": self.serial_edit.text().strip(),
            "cap_method": str(self.cap_combo.currentData() or ""),
            "touch_method": str(self.touch_combo.currentData() or ""),
            "ime_method": str(self.ime_combo.currentData() or ""),
            "ori_method": str(self.ori_combo.currentData() or ""),
            "display_id": self.display_edit.text().strip(),
            "input_event": self.input_event_edit.text().strip(),
            "adb_path": self.adb_path_edit.text().strip(),
        }

    def _on_preset_changed(self) -> None:
        key = str(self.preset_combo.currentData() or "custom")
        preset = PRESETS.get(key)
        if preset:
            method_combos = (self.cap_combo, self.touch_combo, self.ime_combo, self.ori_combo)
            for combo in method_combos:
                combo.blockSignals(True)
            try:
                self.cap_combo.setCurrentIndex(max(0, self.cap_combo.findData(preset["cap_method"])))
                self.touch_combo.setCurrentIndex(
                    max(0, self.touch_combo.findData(preset["touch_method"]))
                )
                self.ime_combo.setCurrentIndex(max(0, self.ime_combo.findData(preset["ime_method"])))
                self.ori_combo.setCurrentIndex(max(0, self.ori_combo.findData(preset["ori_method"])))
            finally:
                for combo in method_combos:
                    combo.blockSignals(False)
        self.methods_widget.setVisible(not preset)
        self._on_connection_changed()

    def _on_method_changed(self) -> None:
        key = match_preset(self.connection())
        index = self.preset_combo.findData(key)
        if index >= 0:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(index)
            self.preset_combo.blockSignals(False)
            self.methods_widget.setVisible(key == "custom")
        self._on_connection_changed()

    def _on_connection_changed(self) -> None:
        cfg = self.connection()
        self.uri_preview.setText(build_uri(cfg))
        settings.save_connection(cfg)

    def _browse_dir(self) -> None:
        start = self.dir_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择资源目录", start)
        if chosen:
            self.dir_edit.setText(chosen)

    def resource_dir(self) -> str:
        return self.dir_edit.text().strip()

    def _browse_screenshot_dir(self) -> None:
        start = self.shot_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择截图目录", start)
        if chosen:
            self.shot_edit.setText(chosen)

    def screenshot_dir(self) -> str:
        return self.shot_edit.text().strip()

    def _reset_seq_counter(self) -> None:
        self.seq_spin.setValue(0)

    def _on_name_mode_changed(self) -> None:
        is_sequence = self.name_combo.currentData() == screenshot_names.SCREENSHOT_NAME_SEQUENCE
        self.name_stack.setCurrentIndex(1 if is_sequence else 0)
        self.expr_label.setText("序号表达式" if is_sequence else "随机表达式")

    def _preview_dir(self) -> Path:
        raw = self.shot_edit.text().strip()
        if not raw:
            return SCREENSHOT_DIR
        path = Path(raw).expanduser()
        return path if path.is_absolute() else (ROOT / path)

    def _update_previews(self) -> None:
        out_dir = self._preview_dir()
        random_name = screenshot_names.preview_name(
            self.random_expr_edit.text(), screenshot_names.SCREENSHOT_NAME_RANDOM, out_dir
        )
        seq_name = screenshot_names.preview_name(
            self.seq_expr_edit.text(), screenshot_names.SCREENSHOT_NAME_SEQUENCE,
            out_dir, self.seq_spin.value(),
        )
        self.random_preview.setText(f"预览：{random_name}")
        self.seq_preview.setText(f"预览：{seq_name}")

    def screenshot_name_mode(self) -> str:
        return str(self.name_combo.currentData() or screenshot_names.SCREENSHOT_NAME_RANDOM)

    def screenshot_random_expr(self) -> str:
        return self.random_expr_edit.text().strip()

    def screenshot_seq_expr(self) -> str:
        return self.seq_expr_edit.text().strip()

    def screenshot_seq_next(self) -> int:
        return int(self.seq_spin.value())

    def _browse_project_dir(self) -> None:
        start = self.project_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择项目目录", start)
        if chosen:
            self.project_edit.setText(chosen)

    def project_dir(self) -> str:
        return self.project_edit.text().strip()

    def coord_expr(self) -> str:
        return self.expr_edit.text().strip()

    def tpl_expr(self) -> str:
        return self.tpl_edit.text().strip()

    def swipe_expr(self) -> str:
        return self.swipe_edit.text().strip()

    def lock_ratio(self) -> bool:
        return self.aspect_check.isChecked()
