# -*- coding: utf-8 -*-
"""场景编辑对话框：图片选择 / 识别截图 / 关键词与权重表格录入。"""
from __future__ import annotations

import cv2
import json
import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QSizePolicy,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import config
from .recognition import RecognitionWorker, recognize_screen


class _ImagePreview(QLabel):
    """撑满左列的自适应图片预览：控件尺寸变化时按原图等比缩放显示。"""

    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: QPixmap | None = None
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(220, 160)
        self.setStyleSheet(
            "QLabel { background: #242424; border: 1px dashed #555555; "
            "border-radius: 4px; color: #666666; }"
        )

    def set_source(self, pixmap: QPixmap | None) -> None:
        self._source = pixmap
        self._rescale()

    def _rescale(self) -> None:
        if self._source is None or self._source.isNull():
            self.setText("未设置图片")
            return
        self.setPixmap(
            self._source.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def mouseDoubleClickEvent(self, event) -> None:
        if self._source is not None and not self._source.isNull():
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)




class SceneEditorMixin:
    """场景编辑对话框能力，由 AIPanel 混入。要求宿主提供 window / recognition_frame / append_log。"""

    def _scene_editor(self, scene: dict[str, str] | None = None) -> dict[str, str] | None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("编辑场景" if scene else "新增场景")
        dialog.setStyleSheet(
            "QDialog, QLineEdit { background: #2b2b2b; color: #dddddd; }"
            "QDialog::title { background: #2b2b2b; color: #dddddd; }"
            "QLabel { color: #dddddd; }"
            "QPushButton { background: #3a3a3a; color: #dddddd; padding: 4px 10px; }"
            "QTableWidget { background: #242424; color: #dddddd; border: 1px solid #3a3a3a; "
            "border-radius: 4px; gridline-color: #3a3a3a; }"
            "QHeaderView::section { background: #2b2b2b; color: #aaaaaa; border: none; padding: 4px; }"
            "QDoubleSpinBox { background: #2b2b2b; color: #dddddd; border: 1px solid #3a3a3a; "
            "border-radius: 3px; padding: 2px; }"
            "QToolButton { color: #aaaaaa; border: none; }"
            "QToolButton:hover { color: #ffffff; }"
        )
        root = QHBoxLayout(dialog)
        image_column = QVBoxLayout()
        image_column.setContentsMargins(0, 0, 8, 0)
        root.addLayout(image_column, 0)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setLabelAlignment(Qt.AlignRight)
        root.addLayout(form, 1)

        name_edit = QLineEdit(scene.get("name", "") if scene else "")
        form.addRow("场景名", name_edit)

        desc_tabs = QTabWidget()
        desc_tabs.setStyleSheet(
            "QTabWidget::pane { background: #242424; border: 1px solid #3a3a3a; border-radius: 4px; }"
            "QTabBar::tab { background: #2b2b2b; color: #aaaaaa; padding: 5px 16px; "
            "border: 1px solid #3a3a3a; border-bottom: none; }"
            "QTabBar::tab:selected { background: #3a3a3a; color: #ffffff; }"
        )
        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(4, 4, 4, 4)

        desc_table = QTableWidget(0, 0)
        desc_table.verticalHeader().setVisible(False)
        table_layout.addWidget(desc_table, 1)
        desc_fields: list[str] = []
        weight_label = QLabel("权重合计：0%")
        weight_label.setStyleSheet("color: #888888; font-size: 11px;")
        table_layout.addWidget(weight_label)
        desc_tabs.addTab(table_page, "表格")

        json_page = QWidget()
        json_layout = QVBoxLayout(json_page)
        json_layout.setContentsMargins(4, 4, 4, 4)
        json_edit = QPlainTextEdit()
        json_edit.setPlaceholderText('[{"text":"立即领取","weight":8}, ...]')
        json_edit.setStyleSheet(
            "QPlainTextEdit { background: #242424; color: #dddddd; border: 1px solid #3a3a3a; "
            "border-radius: 4px; font-family: Consolas, monospace; }"
        )
        initial_feature = scene.get("feature", []) if scene else []
        json_edit.setPlainText(json.dumps(initial_feature, ensure_ascii=False, indent=2))
        json_layout.addWidget(json_edit)
        desc_tabs.addTab(json_page, "JSON")
        form.addRow("描述", desc_tabs)

        def remove_desc_row(button: QToolButton) -> None:
            for row in range(desc_table.rowCount()):
                if desc_table.cellWidget(row, desc_table.columnCount() - 1) is button:
                    desc_table.removeRow(row)
                    refresh_weight_label()
                    break

        def add_desc_row(obj: dict | None = None) -> None:
            updating_table["flag"] = True
            row = desc_table.rowCount()
            desc_table.insertRow(row)
            for col, field in enumerate(desc_fields):
                value = obj.get(field, "") if obj else ""
                if field == "weight":
                    try:
                        num = float(value) if value not in ("", None) else 0.0
                    except (ValueError, TypeError):
                        num = 0.0
                    desc_table.setItem(row, col, QTableWidgetItem(f"{num:g}%"))
                else:
                    desc_table.setItem(row, col, QTableWidgetItem(str(value)))
            delete_button = QToolButton()
            delete_button.setText("×")
            delete_button.setToolTip("删除该行")
            delete_button.clicked.connect(
                lambda _checked=False, b=delete_button: remove_desc_row(b)
            )
            desc_table.setCellWidget(row, len(desc_fields), delete_button)
            updating_table["flag"] = False
            refresh_weight_label()

        updating_table = {"flag": False}

        def weight_total() -> float:
            if "weight" not in desc_fields:
                return 0.0
            col = desc_fields.index("weight")
            total = 0.0
            for row in range(desc_table.rowCount()):
                item = desc_table.item(row, col)
                if item is None:
                    continue
                try:
                    total += float(item.text().rstrip("%").strip())
                except ValueError:
                    pass
            return total

        def refresh_weight_label() -> None:
            total = weight_total()
            ok = abs(total - 100.0) < 0.01
            weight_label.setText(f"权重合计：{total:g}%" + ("" if ok else "（需等于 100%）"))
            weight_label.setStyleSheet(
                f"color: {'#4caf50' if ok else '#f44336'}; font-size: 11px;"
            )

        def on_item_changed(_item) -> None:
            if not updating_table["flag"]:
                refresh_weight_label()

        desc_table.itemChanged.connect(on_item_changed)

        add_row_button = QPushButton("+ 添加一行")
        add_row_button.clicked.connect(lambda: add_desc_row())
        desc_actions = QHBoxLayout()
        desc_actions.addWidget(add_row_button)
        desc_actions.addStretch(1)
        hint = QLabel("表格列随 JSON 字段生成，权重列按百分比显示（总和建议 100）；两页双向同步")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        desc_actions.addWidget(hint)
        table_layout.addLayout(desc_actions)

        image_row = QHBoxLayout()
        recognize_button = QPushButton("识别界面")
        recognize_button.setToolTip("截取当前画面识别：截图作为图片，返回结果填入描述表")
        pick_button = QPushButton("选择图片…")
        snap_button = QPushButton("插入识别图片")
        clear_button = QPushButton("清除图片")
        for button in (recognize_button, pick_button, snap_button, clear_button):
            image_row.addWidget(button)
        image_row.addStretch(1)
        form.addRow("图片操作", image_row)

        current_image = scene.get("image", "") if scene else ""
        picked_data = {"value": ""}
        cleared = {"flag": False}

        def _read_json_data() -> list | None:
            raw = json_edit.toPlainText().strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                return None
            return data if isinstance(data, list) else None

        def sync_from_json() -> None:
            """按 JSON 字段重建表格列与行，字段完全跟随 JSON。"""
            data = _read_json_data() or []
            fields: list[str] = []
            for obj in data:
                if isinstance(obj, dict):
                    for key in obj:
                        if key not in fields:
                            fields.append(key)
            has_weight = any(isinstance(obj, dict) and "weight" in obj for obj in data)
            if "weight" not in fields:
                fields.append("weight")
            desc_fields[:] = fields
            if not has_weight and data:
                share = round(100 / len(data), 2)
                for index, obj in enumerate(data):
                    if isinstance(obj, dict):
                        obj["weight"] = share if index < len(data) - 1 else round(100 - share * (len(data) - 1), 2)
            desc_table.clear()
            desc_table.setRowCount(0)
            desc_table.setColumnCount(len(fields) + 1)
            desc_table.setHorizontalHeaderLabels(
                ["权重%" if f == "weight" else f for f in fields] + [""]
            )
            header = desc_table.horizontalHeader()
            for col in range(len(fields)):
                header.setSectionResizeMode(col, QHeaderView.Stretch)
            header.setSectionResizeMode(len(fields), QHeaderView.Fixed)
            desc_table.setColumnWidth(len(fields), 36)
            for obj in data:
                add_desc_row(obj if isinstance(obj, dict) else None)

        def sync_table_to_json() -> None:
            """把表格按当前字段重建为 JSON 数组，切回 JSON 页时同步。"""
            original = _read_json_data() or []
            data: list[dict] = []
            for row in range(desc_table.rowCount()):
                obj: dict = {}
                for col, field in enumerate(desc_fields):
                    item = desc_table.item(row, col)
                    text = item.text().strip() if item else ""
                    source = original[row].get(field) if row < len(original) and isinstance(original[row], dict) else ""
                    if field == "weight":
                        cleaned = text.rstrip("%").strip()
                        try:
                            obj[field] = float(cleaned) if "." in cleaned else int(cleaned)
                        except ValueError:
                            obj[field] = 0
                    elif isinstance(source, (int, float)) and not isinstance(source, bool):
                        try:
                            obj[field] = float(text) if "." in text else int(text)
                        except ValueError:
                            obj[field] = text
                    else:
                        obj[field] = text
                data.append(obj)
            json_edit.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))

        def on_desc_tab_changed(index: int) -> None:
            if index == desc_tabs.indexOf(table_page):
                sync_from_json()
            elif index == desc_tabs.indexOf(json_page):
                sync_table_to_json()

        desc_tabs.currentChanged.connect(on_desc_tab_changed)
        sync_from_json()

        image_label = QLabel("图片")
        image_label.setStyleSheet("color: #dddddd;")
        image_label.setAlignment(Qt.AlignCenter)
        image_column.addWidget(image_label)

        image_preview = _ImagePreview()
        image_preview.setToolTip("双击查看大图")
        image_column.addWidget(image_preview, 1)

        def show_full_image() -> None:
            source = image_preview._source
            if source is None or source.isNull():
                return
            viewer = QDialog(dialog)
            viewer.setWindowTitle("图片预览")
            viewer.setStyleSheet("QDialog { background: #1e1e1e; }")
            layout = QVBoxLayout(viewer)
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            screen = viewer.screen().availableGeometry() if viewer.screen() else None
            max_size = screen.size() if screen else source.size()
            label.setPixmap(
                source.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            layout.addWidget(label)
            viewer.resize(label.sizeHint())
            viewer.exec()

        image_preview.double_clicked.connect(show_full_image)

        def refresh_preview() -> None:
            pix: QPixmap | None = None
            if picked_data["value"]:
                pix = self._load_scene_pixmap(picked_data["value"])
            elif not cleared["flag"]:
                pix = self._load_scene_pixmap(current_image)
            image_preview.set_source(pix)
            clear_button.setEnabled(
                bool(picked_data["value"] or (not cleared["flag"] and current_image))
            )

        def pick_image() -> None:
            file_path, _ = QFileDialog.getOpenFileName(
                dialog, "选择场景图片", "",
                "图片 (*.png *.jpg *.jpeg *.bmp *.webp)",
            )
            if file_path:
                try:
                    mime = "image/" + (Path(file_path).suffix.lower().lstrip(".") or "png")
                    picked_data["value"] = config.image_to_data_url(file_path, mime)
                except Exception as exc:
                    QMessageBox.warning(dialog, "提示", f"读取图片失败：{exc}")
                    return
                cleared["flag"] = False
                refresh_preview()

        def save_frame(frame) -> None:
            ok, buf = cv2.imencode(".png", frame)
            if not ok:
                QMessageBox.warning(dialog, "提示", "画面编码失败")
                return
            import base64
            picked_data["value"] = (
                "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
            )
            cleared["flag"] = False
            self.recognition_frame = frame
            refresh_preview()

        def snap_image() -> None:
            """插入最近一次界面识别使用的画面帧（识别时已保存），不是现截。"""
            frame = self.recognition_frame
            if frame is None:
                QMessageBox.warning(dialog, "提示", "尚未进行界面识别，请先点击「识别界面」")
                return
            save_frame(frame)

        def clear_image() -> None:
            picked_data["value"] = ""
            cleared["flag"] = True
            refresh_preview()

        pick_button.clicked.connect(pick_image)
        snap_button.clicked.connect(snap_image)
        clear_button.clicked.connect(clear_image)
        refresh_preview()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        def on_accept() -> None:
            if desc_tabs.currentWidget() is json_page:
                sync_from_json()
            total = weight_total()
            if abs(total - 100.0) >= 0.01:
                QMessageBox.warning(
                    dialog, "提示", f"权重合计必须等于 100%（当前 {total:g}%）"
                )
                return
            dialog.accept()

        buttons.accepted.connect(on_accept)

        worker_box: dict[str, RecognitionWorker | None] = {"worker": None}
        closed = {"flag": False}

        def set_busy(busy: bool) -> None:
            recognize_button.setText("识别中…" if busy else "识别界面")
            for control in (recognize_button, pick_button, snap_button, clear_button, add_row_button):
                control.setEnabled(not busy)

        def collect_desc() -> str:
            return json_edit.toPlainText().strip()

        def on_recognized(answer: str, elapsed: float) -> None:
            if closed["flag"]:
                return
            rows = config.parse_desc(answer)
            count = len(rows)
            share = round(100 / count, 2) if count else 0
            for index, row in enumerate(rows):
                row["weight"] = share if index < count - 1 else round(100 - share * (count - 1), 2)
            json_edit.setPlainText(config.format_desc(rows))
            sync_from_json()
            self.append_log(
                f"[场景编辑识别]（耗时 {elapsed:.1f}s）：\n{answer}\n{'-' * 28}"
            )

        def on_recognize_failed(message: str) -> None:
            if closed["flag"]:
                return
            QMessageBox.warning(dialog, "识别失败", message)

        def on_worker_finished() -> None:
            worker_box["worker"] = None
            if not closed["flag"]:
                set_busy(False)

        def recognize_scene() -> None:
            if worker_box["worker"] is not None:
                return
            worker = recognize_screen(
                self.window,
                parent=self,
                on_frame=save_frame,
                on_ready=on_recognized,
                on_failed=on_recognize_failed,
                on_finished=on_worker_finished,
            )
            if worker is None:
                QMessageBox.warning(dialog, "提示", "暂无画面，无法识别界面")
                return
            worker.finished.connect(worker.deleteLater)
            worker_box["worker"] = worker
            set_busy(True)

        def on_dialog_finished(_result: int) -> None:
            closed["flag"] = True
            worker = worker_box["worker"]
            if worker is not None:
                for signal, slot in (
                    (worker.result_ready, on_recognized),
                    (worker.failed, on_recognize_failed),
                    (worker.finished, on_worker_finished),
                ):
                    try:
                        signal.disconnect(slot)
                    except (RuntimeError, TypeError):
                        pass

        recognize_button.clicked.connect(recognize_scene)
        dialog.finished.connect(on_dialog_finished)
        dialog.resize(760, 400)
        accepted = dialog.exec() == QDialog.Accepted
        if not accepted:
            return None
        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(dialog, "提示", "场景名不能为空")
            return None
        image = current_image if not cleared["flag"] else ""
        if picked_data["value"]:
            image = picked_data["value"]
        try:
            feature_data = json.loads(collect_desc())
            if not isinstance(feature_data, list):
                feature_data = []
        except (ValueError, TypeError):
            feature_data = []
        return {"name": name, "feature": feature_data, "image": image}
