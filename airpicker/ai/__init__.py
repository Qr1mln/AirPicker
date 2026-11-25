# -*- coding: utf-8 -*-
"""AI 独立模块：通过 AIAddon 挂载到主窗口，不侵入原有代码。"""
from .addon import AIAddon
from .log_settings_tab import AILogSettingsTab
from .settings_tab import AISettingsTab

__all__ = ["AIAddon", "AISettingsTab", "AILogSettingsTab"]
