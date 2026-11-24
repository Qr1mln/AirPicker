# -*- coding: utf-8 -*-
"""工具栏设置弹窗的打开与设置持久化。"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog

from .. import settings
from ..toolbar import ToolbarSettingsDialog


class PreferencesMixin:
    def open_toolbar_settings(self) -> None:
        cur = settings.load_settings()
        dialog = ToolbarSettingsDialog(
            self.toolbar.is_horizontal(),
            settings.get_resource_dir(cur),
            settings.get_screenshot_dir(cur),
            settings.get_screenshot_name_mode(cur),
            settings.get_screenshot_random_expr(cur),
            settings.get_screenshot_seq_expr(cur),
            settings.get_screenshot_seq_next(cur),
            settings.get_project_dir(cur),
            settings.get_coord_expr(cur),
            settings.get_tpl_expr(cur),
            settings.get_swipe_expr(cur),
            settings.get_lock_ratio(cur),
            self.connection_status,
            self.can_connect,
            self.can_disconnect,
            settings.get_auto_connect(cur),
            settings.get_connection(cur),
            self,
        )
        dialog.connect_requested.connect(self.connect_device)
        dialog.disconnect_requested.connect(self.disconnect_device)
        self.connectionStateChanged.connect(dialog.set_connection_status)
        try:
            accepted = dialog.exec() == QDialog.Accepted
        finally:
            self.connectionStateChanged.disconnect(dialog.set_connection_status)
        if accepted:
            horizontal = dialog.is_horizontal()
            self.toolbar.set_horizontal(horizontal)
            settings.save_toolbar_horizontal(horizontal)
            settings.save_auto_connect(dialog.auto_connect())
            settings.save_connection(dialog.connection())
            settings.save_resource_dir(dialog.resource_dir())
            settings.save_screenshot_dir(dialog.screenshot_dir())
            settings.save_screenshot_name_mode(dialog.screenshot_name_mode())
            settings.save_screenshot_random_expr(dialog.screenshot_random_expr())
            settings.save_screenshot_seq_expr(dialog.screenshot_seq_expr())
            settings.save_screenshot_seq_next(dialog.screenshot_seq_next())
            settings.save_project_dir(dialog.project_dir())
            settings.save_coord_expr(dialog.coord_expr())
            settings.save_tpl_expr(dialog.tpl_expr())
            settings.save_swipe_expr(dialog.swipe_expr())
            settings.save_lock_ratio(dialog.lock_ratio())
            self._lock_ratio = dialog.lock_ratio()
            if horizontal:
                self.toolbar.move(
                    self.width() - self.toolbar.width() - 20,
                    60,
                )
            self.toolbar.constrain_to_window()
