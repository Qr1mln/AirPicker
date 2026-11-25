# -*- coding: utf-8 -*-
"""场景卡片列表：图片加载、列表渲染与增删改排序。"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import config
from .actions import dispatch_command, execute_actions, parse_actions


class SceneCardsMixin:
    """场景卡片列表相关能力，由 AIPanel 混入。要求宿主提供 scene_list 与 _scene_editor。"""

    def _load_scene_pixmap(self, image: str) -> QPixmap | None:
        """从场景配置的图片值加载：优先 base64/data URL，兼容旧文件名。"""
        if not image:
            return None
        raw = config.decode_image(image)
        if raw is not None:
            pix = QPixmap()
            pix.loadFromData(QByteArray(raw))
            return None if pix.isNull() else pix
        pix = QPixmap(str(config.SCENE_IMAGE_DIR / image))
        return None if pix.isNull() else pix

    def _refresh_scene_list(self) -> None:
        self.scene_list.clear()
        for index, scene in enumerate(config.load()["scenes"]):
            item = QListWidgetItem()
            item.setSizeHint(QSize(10, 60))
            self.scene_list.addItem(item)
            self.scene_list.setItemWidget(item, self._make_scene_card(index, scene))

    def _make_scene_card(self, index: int, scene: dict[str, str]) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #292929; border: 1px solid #3a3a3a; border-radius: 6px; }"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        preview = QLabel()
        preview.setFixedSize(48, 48)
        pix = self._load_scene_pixmap(scene.get("image", ""))
        if pix is not None:
            preview.setPixmap(
                pix.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            preview.setAlignment(Qt.AlignCenter)
            preview.setText("无图")
            preview.setStyleSheet(
                "QLabel { background: #2b2b2b; border: 1px dashed #555555; "
                "border-radius: 4px; color: #666666; font-size: 11px; }"
            )
        row.addWidget(preview)

        body = QVBoxLayout()
        body.setSpacing(4)

        top = QHBoxLayout()
        name = QLabel(scene.get("name") or "(未命名)")
        name.setStyleSheet("color: #ffffff; font-weight: bold;")
        top.addWidget(name, 1)
        for text, tip, callback in (
            ("▶", "执行该场景动作", lambda: self._execute_scene(index)),
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
        body.addLayout(top)

        feature = scene.get("feature", [])
        summary = (
            "、".join(str(row.get("text", "")) for row in feature if isinstance(row, dict))
            if isinstance(feature, list) else str(feature)
        )[:100] or "（无特征）"
        desc = QLabel(summary)
        desc.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        desc.setWordWrap(True)
        body.addWidget(desc)

        actions, errors = parse_actions(scene.get("action", ""))
        action_text = (
            "；".join(a.summary() for a in actions)
            if not errors else f"动作格式错误：{errors[0]}"
        ) or "（无动作）"
        action_label = QLabel(f"动作: {action_text}")
        action_label.setStyleSheet(
            f"color: {'#f44336' if errors else '#6ab04c'}; font-size: 11px;"
        )
        action_label.setWordWrap(True)
        body.addWidget(action_label)
        row.addLayout(body, 1)
        return card

    @staticmethod
    def _plain_scenes() -> list[dict[str, str]]:
        return [
            {
                "name": s.get("name", ""),
                "feature": s.get("feature", ""),
                "image": s.get("image", ""),
                "action": s.get("action", ""),
            }
            for s in config.load_scenes()
        ]

    def run_scene_actions(self, scene: dict, *, notify: bool = True) -> bool:
        """解析并执行场景动作，返回是否成功执行。notify=False 时只写日志不弹窗。"""
        name = scene.get("name", "")
        actions, errors = parse_actions(scene.get("action", ""))
        if errors:
            message = "\n".join(errors)
            self.append_log(f"[执行失败] 场景「{name}」动作格式错误：{message}")
            if notify:
                QMessageBox.warning(self.window, "动作格式错误", message)
            return False
        if not actions:
            message = f"场景「{name}」尚未配置动作"
            self.append_log(f"[执行动作] {message}")
            if notify:
                QMessageBox.information(self.window, "提示", message)
            return False
        device = getattr(self.window, "device", None)
        if device is None:
            message = "尚未连接设备，请先连接设备"
            self.append_log(f"[执行失败] {message}")
            if notify:
                QMessageBox.warning(self.window, "提示", message)
            return False

        def on_dispatch(done: int, total: int, action) -> None:
            self.append_log(
                f"[下发设备] {dispatch_command(action)}（{done}/{total}）"
            )

        def on_step(done: int, total: int, action) -> None:
            self.append_log(
                f"[设备已响应] {name}：{action.summary()}（{done}/{total}）"
            )

        self.append_log(f"[执行动作] 场景「{name}」开始执行 {len(actions)} 条动作")
        try:
            count = execute_actions(
                actions, device, on_dispatch=on_dispatch, on_step=on_step
            )
        except Exception as exc:
            self.append_log(f"[执行失败] {exc}")
            if notify:
                QMessageBox.warning(self.window, "执行失败", str(exc))
            return False
        self.append_log(f"[执行完成] 共执行 {count} 条动作\n{'-' * 28}")
        return True

    def _execute_scene(self, index: int) -> None:
        """卡片按钮：解析并执行指定场景的动作，下发到已连接设备。"""
        scenes = self._plain_scenes()
        if 0 <= index < len(scenes):
            self.run_scene_actions(scenes[index])

    def _add_scene(self) -> None:
        data = self._scene_editor()
        if data is not None:
            scenes = self._plain_scenes()
            scenes.append(data)
            config.save_scenes(scenes)
            self._refresh_scene_list()

    def _edit_scene_item(self, item) -> None:
        self._edit_scene_at(self.scene_list.row(item))

    def _edit_selected_scene(self) -> None:
        self._edit_scene_at(self.scene_list.currentRow())

    def _edit_scene_at(self, index: int) -> None:
        scenes = self._plain_scenes()
        if not 0 <= index < len(scenes):
            return
        data = self._scene_editor(scenes[index])
        if data is not None:
            scenes[index] = data
            config.save_scenes(scenes)
            self._refresh_scene_list()

    def _delete_scene(self, index: int) -> None:
        scenes = self._plain_scenes()
        if not 0 <= index < len(scenes):
            return
        scenes.pop(index)
        config.save_scenes(scenes)
        self._refresh_scene_list()

    def _move_scene(self, index: int, delta: int) -> None:
        scenes = self._plain_scenes()
        target = index + delta
        if 0 <= index < len(scenes) and 0 <= target < len(scenes):
            scenes[index], scenes[target] = scenes[target], scenes[index]
            config.save_scenes(scenes)
            self._refresh_scene_list()
