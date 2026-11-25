# -*- coding: utf-8 -*-
"""日志字段：字段判定与显示配置变更通知。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from . import config


class LogFieldsNotifier(QObject):
    """日志字段显示配置变化时通知面板重新渲染。"""

    changed = Signal()


notifier = LogFieldsNotifier()


def is_visible(field: str) -> bool:
    """按当前配置判断某字段是否显示；未知字段默认显示。"""
    return bool(config.load()["log_fields"].get(field, True))


def classify(text: str) -> str:
    """根据日志文本前缀推断字段分类，供未显式标注字段的调用使用。"""
    head = text.strip()
    if head.startswith("["):
        head = head[1:].split("]", 1)[0]
    if head in ("下发设备", "设备已响应", "执行动作", "执行完成", "执行失败"):
        return "action"
    if "提示词" in head:
        return "prompt"
    if head == "场景编辑识别" or text.startswith("界面元素信息"):
        return "analysis"
    if head == "匹配场景":
        return "match"
    return "system"
