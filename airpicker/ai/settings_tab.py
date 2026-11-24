# -*- coding: utf-8 -*-
"""AI 设置页：由主设置弹窗挂载，读写 ai_settings.json。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import config


class AISettingsTab(QWidget):
    """VLM 服务配置页，输入即保存到独立配置文件。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        cfg = config.load()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        group = QGroupBox("单次截图分析（VLM）")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.api_url_edit = QLineEdit(cfg["api_url"])
        self.api_url_edit.setPlaceholderText("http://192.168.1.1:1234/v1/chat/completions")
        form.addRow("API 地址", self.api_url_edit)

        self.token_edit = QLineEdit(cfg["api_token"])
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("留空表示不需要认证；填写后以 Bearer 方式发送")
        form.addRow("API Token", self.token_edit)

        self.model_edit = QLineEdit(cfg["model"])
        self.model_edit.setPlaceholderText("模型名称")
        form.addRow("模型名", self.model_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 600)
        self.timeout_spin.setValue(int(cfg["timeout"]))
        self.timeout_spin.setSuffix(" 秒")
        form.addRow("超时", self.timeout_spin)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setValue(float(cfg["temperature"]))
        form.addRow("温度", self.temperature_spin)

        self.retry_temperature_spin = QDoubleSpinBox()
        self.retry_temperature_spin.setRange(0.0, 2.0)
        self.retry_temperature_spin.setDecimals(2)
        self.retry_temperature_spin.setSingleStep(0.05)
        self.retry_temperature_spin.setValue(float(cfg["retry_temperature"]))
        form.addRow("重试温度", self.retry_temperature_spin)

        hint = QLabel("配置保存在 ai_settings.json；识别时截图当前帧并交给模型分析，结果写入状态日志。")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow("", hint)

        root.addWidget(group)
        root.addStretch(1)

        self.api_url_edit.textChanged.connect(self._save)
        self.token_edit.textChanged.connect(self._save)
        self.model_edit.textChanged.connect(self._save)
        self.timeout_spin.valueChanged.connect(self._save)
        self.temperature_spin.valueChanged.connect(self._save)
        self.retry_temperature_spin.valueChanged.connect(self._save)

    def _save(self) -> None:
        config.save(
            api_url=self.api_url_edit.text().strip(),
            api_token=self.token_edit.text().strip(),
            model=self.model_edit.text().strip(),
            timeout=self.timeout_spin.value(),
            temperature=self.temperature_spin.value(),
            retry_temperature=self.retry_temperature_spin.value(),
        )
