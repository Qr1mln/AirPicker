# -*- coding: utf-8 -*-
"""AI 日志设置页：按字段选择状态日志中显示的内容。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from . import config
from .log_fields import notifier


class AILogSettingsTab(QWidget):
    """日志字段显示配置，勾选后立即保存并刷新已显示的日志。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        group = QGroupBox("状态日志字段")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        fields = config.load()["log_fields"]
        self._checks: dict[str, QCheckBox] = {}
        for key, label, hint in config.LOG_FIELDS:
            check = QCheckBox(label)
            check.setChecked(bool(fields.get(key, True)))
            check.setToolTip(hint)
            check.toggled.connect(lambda checked, k=key: self._on_toggled(k, checked))
            self._checks[key] = check
            tip = QLabel(hint)
            tip.setStyleSheet("color: #888; font-size: 11px;")
            tip.setWordWrap(True)
            form.addRow(check, tip)

        root.addWidget(group)

        hint = QLabel(
            "取消勾选后，对应内容不再写入状态日志；已显示的日志会立即按新配置重新筛选。"
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

    def _on_toggled(self, key: str, checked: bool) -> None:
        fields = dict(config.load()["log_fields"])
        fields[key] = bool(checked)
        config.save(log_fields=fields)
        notifier.changed.emit()
