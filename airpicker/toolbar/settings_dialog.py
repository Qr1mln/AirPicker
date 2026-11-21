# -*- coding: utf-8 -*-
"""悬浮工具栏设置：横 / 竖排列、资源目录与代码回写表达式。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ToolbarSettingsDialog(QDialog):
    """悬浮工具栏设置弹窗。"""

    def __init__(
        self,
        horizontal: bool,
        resource_dir: Path | str = "",
        coord_expr: str = "({x}, {y})",
        tpl_expr: str = 'Template(r"{name}", record_pos=({rx}, {ry}), resolution=({rw}, {rh}))',
        swipe_expr: str = "swipe(({x1}, {y1}), ({x2}, {y2}))",
        lock_ratio: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.combo = QComboBox()
        self.combo.addItem("竖向", False)
        self.combo.addItem("横向", True)
        self.combo.setCurrentIndex(1 if horizontal else 0)
        form.addRow("工具栏排列", self.combo)

        self.aspect_check = QCheckBox("窗口缩放时保持画面宽高比")
        self.aspect_check.setChecked(bool(lock_ratio))
        form.addRow("", self.aspect_check)

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

        root.addLayout(form)

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

    def _browse_dir(self) -> None:
        start = self.dir_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择资源目录", start)
        if chosen:
            self.dir_edit.setText(chosen)

    def resource_dir(self) -> str:
        return self.dir_edit.text().strip()

    def coord_expr(self) -> str:
        return self.expr_edit.text().strip()

    def tpl_expr(self) -> str:
        return self.tpl_edit.text().strip()

    def swipe_expr(self) -> str:
        return self.swipe_edit.text().strip()

    def lock_ratio(self) -> bool:
        return self.aspect_check.isChecked()
