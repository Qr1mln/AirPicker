# -*- coding: utf-8 -*-
"""AirPicker P0：从 Android 实时屏幕框选模板，并生成 Airtest 代码。

运行：
    uv run python tools/template_capture_minicap.py
"""
from __future__ import annotations

import math
import os
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    Property as QtProperty,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    import pyperclip
except ImportError:  # 剪贴板不可用时仍可在控制台手动复制
    pyperclip = None

# ============================== 配置区 ==============================
SERIAL = ""  # 多设备时填设备序列号，例如 "emulator-5554"
DEVICE_URI = "Android:///?cap_method=MINICAP&touch_method=MINITOUCH"
MAX_W = 1280
MAX_H = 1200
MINICAP_QUALITY = 100
DISPLAY_SHARPEN = True
FPS = 30
COPY_MODE = "touch"  # "touch" -> touch(Template(...))；"template" -> Template(...)
# ==================================================================

ROOT = Path(__file__).resolve().parent.parent
PICS_DIR = ROOT / "pics"
SCRIPTS_DIR = ROOT / "scripts"

SELECT_COLOR = QColor(40, 167, 69)
MIN_SELECT = 4
FRAME_INTERVAL_MS = max(1, int(1000 / max(1, FPS)))


def _build_uri() -> str:
    if SERIAL:
        return (
            f"Android://127.0.0.1:5037/{SERIAL}"
            f"?cap_method=MINICAP&touch_method=MINITOUCH"
        )
    return DEVICE_URI


def _device_screen_wh(device) -> tuple[int, int] | None:
    try:
        info = device.adb.get_display_info()
        w, h = int(info["width"]), int(info["height"])
        if int(info.get("rotation", 0)) % 180:
            w, h = h, w
        return w, h
    except Exception:
        return None


class ScreenWidget(QLabel):
    """实时画面显示，左键拖拽框选、右键取消。"""

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.app = parent
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 300)

    def mousePressEvent(self, event) -> None:
        if self.app.picking_coord:
            if event.button() == Qt.LeftButton:
                self.app.pick_coord(event.position().toPoint())
            elif event.button() == Qt.RightButton:
                self.app.cancel_pick_coord()
            return
        if event.button() == Qt.LeftButton:
            self.app.begin_selection(event.position().toPoint())
        elif event.button() == Qt.RightButton:
            self.app.cancel_selection()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        self.app.cursor_pos = pos
        self.update()
        if self.app.picking_coord:
            return
        self.app.update_selection(pos)

    def leaveEvent(self, event) -> None:
        self.app.cursor_pos = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.app.picking_coord:
            return
        if event.button() == Qt.LeftButton:
            self.app.finish_selection(event.position().toPoint())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.app.dragging and self.app.drag_start and self.app.drag_end:
            rect = QRect(self.app.drag_start, self.app.drag_end).normalized()
            painter.setPen(QPen(SELECT_COLOR, 2))
            painter.setBrush(Qt.transparent)
            painter.drawRect(rect)
        pos = self.app.cursor_pos
        if pos is not None and self.app.latest_bgr is not None:
            x, y = self.app._to_source(pos)
            text = f"{x}, {y}"
            fm = painter.fontMetrics()
            tw, th = fm.horizontalAdvance(text), fm.height()
            bx, by = pos.x() + 14, pos.y() + 14
            if bx + tw + 12 > self.width():
                bx = pos.x() - tw - 20
            if by + th + 10 > self.height():
                by = pos.y() - th - 16
            bx, by = max(0, bx), max(0, by)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 20, 210))
            painter.drawRoundedRect(bx, by, tw + 12, th + 8, 4, 4)
            painter.setPen(QColor(240, 240, 240))
            painter.drawText(bx + 6, by + 4 + fm.ascent(), text)
        painter.end()


class IconButton(QWidget):
    """自绘白色线性图标按钮：悬停渐亮、按下缩放，刷新按钮点击后转圈。"""

    def __init__(self, kind: str, parent: QWidget):
        super().__init__(parent)
        self.kind = kind
        self.clicked = None
        self.setFixedSize(40, 44)
        self.setCursor(Qt.ArrowCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._hover = 0.0
        self._press = 0.0
        self._rotation = 0.0
        self._press_pos: QPoint | None = None
        self._anims: dict[str, QPropertyAnimation] = {}

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    def _get_press(self) -> float:
        return self._press

    def _set_press(self, value: float) -> None:
        self._press = value
        self.update()

    def _get_rotation(self) -> float:
        return self._rotation

    def _set_rotation(self, value: float) -> None:
        self._rotation = value
        self.update()

    hover = QtProperty(float, _get_hover, _set_hover)
    press = QtProperty(float, _get_press, _set_press)
    rotation = QtProperty(float, _get_rotation, _set_rotation)

    def _animate(self, name: str, end: float, duration: int, curve=QEasingCurve.OutQuad) -> None:
        anim = QPropertyAnimation(self, name.encode(), self)
        anim.setDuration(duration)
        anim.setStartValue(getattr(self, "_" + name))
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        anim.start()
        self._anims[name] = anim

    def enterEvent(self, event) -> None:
        self._animate("hover", 1.0, 140)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate("hover", 0.0, 180)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
            self._animate("press", 1.0, 90)
        event.ignore()  # 继续交给悬浮工具栏处理拖拽

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._animate("press", 0.0, 160)
            if self._press_pos is not None:
                moved = (event.position().toPoint() - self._press_pos).manhattanLength()
                if moved < 6:
                    if self.kind == "refresh":
                        self._animate(
                            "rotation", self._rotation + 360.0, 700,
                            QEasingCurve.InOutQuad,
                        )
                    if self.clicked:
                        self.clicked()
            self._press_pos = None
        event.ignore()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2

        if self._hover > 0.01:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(10 + 30 * self._hover)))
            p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 6, 6)

        p.save()
        scale = 1.0 - 0.08 * self._press
        p.translate(cx, cy)
        p.scale(scale, scale)
        if self.kind == "refresh" and self._rotation:
            p.rotate(self._rotation)
        p.translate(-cx, -cy)

        shade = int(235 + 20 * max(self._hover, self._press))
        pen = QPen(QColor(shade, shade, shade), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        k = self.kind

        if k == "refresh":
            r = 10.0
            box = (int(cx - r), int(cy - r), int(2 * r), int(2 * r))
            p.drawArc(*box, -60 * 16, 255 * 16)
            p.drawArc(*box, 120 * 16, 255 * 16)
            for angle in (-60, 120):
                a = math.radians(angle)
                tip = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
                p.drawLine(tip, QPointF(tip.x() - 4, tip.y() - 1))
                p.drawLine(tip, QPointF(tip.x() + 1, tip.y() - 4))
        elif k == "back":
            p.drawLine(int(cx - 10), int(cy), int(cx + 10), int(cy))
            p.drawLine(int(cx - 10), int(cy), int(cx - 3), int(cy - 7))
            p.drawLine(int(cx - 10), int(cy), int(cx - 3), int(cy + 7))
        elif k == "home":
            p.drawLine(int(cx - 11), int(cy - 1), int(cx), int(cy - 11))
            p.drawLine(int(cx), int(cy - 11), int(cx + 11), int(cy - 1))
            p.drawLine(int(cx - 9), int(cy - 3), int(cx - 9), int(cy + 10))
            p.drawLine(int(cx + 9), int(cy - 3), int(cx + 9), int(cy + 10))
            p.drawLine(int(cx - 9), int(cy + 10), int(cx + 9), int(cy + 10))
            p.drawRect(int(cx - 3), int(cy + 2), 6, 8)
        elif k == "coord":
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            p.drawEllipse(QPointF(cx, cy), 2, 2)
            p.drawLine(int(cx - 13), int(cy), int(cx - 4), int(cy))
            p.drawLine(int(cx + 4), int(cy), int(cx + 13), int(cy))
            p.drawLine(int(cx), int(cy - 13), int(cx), int(cy - 4))
            p.drawLine(int(cx), int(cy + 4), int(cx), int(cy + 13))
        elif k == "settings":
            teeth = 8
            step = 2 * math.pi / teeth
            outer, inner = 11.0, 8.0
            points = []
            for i in range(teeth):
                base = i * step
                for offset, radius in (
                    (-0.28, outer), (-0.14, outer),
                    (-0.07, inner), (0.07, inner),
                    (0.14, outer), (0.28, outer),
                ):
                    a = base + offset * step / 0.5
                    points.append(QPointF(cx + radius * math.cos(a), cy + radius * math.sin(a)))
            p.drawPolygon(QPolygonF(points))
            p.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
        p.restore()
        p.end()


class FloatingToolbar(QFrame):
    """独立顶层悬浮窗口：无边框、置顶、可鼠标拖拽。"""

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._drag_pos: QPoint | None = None
        self.drag_state_changed = None
        self.settings_clicked = None
        self.coord_clicked = None
        self._horizontal = False
        self.setStyleSheet(
            "FloatingToolbar { background: #1e1e1e; border: 1px solid #3a3a3a; }"
        )

        self._inner = QFrame(self)
        self._inner.setObjectName("toolbarPanel")
        self._inner.setStyleSheet("#toolbarPanel { background: transparent; border: none; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._inner)

        self._inner_layout = QBoxLayout(QBoxLayout.TopToBottom, self._inner)
        self._inner_layout.setContentsMargins(0, 4, 0, 4)
        self._inner_layout.setSpacing(0)
        for kind in ("refresh", "back", "home", "coord", "settings"):
            btn = IconButton(kind, self._inner)
            btn.setObjectName("toolbarIcon")
            if kind == "settings":
                btn.clicked = self._open_settings
            elif kind == "coord":
                btn.clicked = self._pick_coord
            self._inner_layout.addWidget(btn)
        self._apply_orientation()

    def _open_settings(self) -> None:
        if self.settings_clicked:
            self.settings_clicked()

    def _pick_coord(self) -> None:
        if self.coord_clicked:
            self.coord_clicked()

    def is_horizontal(self) -> bool:
        return self._horizontal

    def set_horizontal(self, horizontal: bool) -> None:
        if self._horizontal == horizontal:
            return
        self._horizontal = horizontal
        self._apply_orientation()

    def _apply_orientation(self) -> None:
        if self._horizontal:
            self._inner_layout.setDirection(QBoxLayout.LeftToRight)
            self.setFixedSize(232, 60)
        else:
            self._inner_layout.setDirection(QBoxLayout.TopToBottom)
            self.setFixedSize(56, 244)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)
            if self.drag_state_changed:
                self.drag_state_changed(True)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            self.unsetCursor()
            if self.drag_state_changed:
                self.drag_state_changed(False)


class ToolbarSettingsDialog(QDialog):
    """悬浮工具栏设置：横 / 竖排列。"""

    def __init__(self, horizontal: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("浮动工具栏样式"))
        self.combo = QComboBox()
        self.combo.addItem("竖向", False)
        self.combo.addItem("横向", True)
        self.combo.setCurrentIndex(1 if horizontal else 0)
        row.addWidget(self.combo)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def is_horizontal(self) -> bool:
        return bool(self.combo.currentData())


class MainWindow(QMainWindow):
    def __init__(self, device, screen_wh: tuple[int, int] | None = None):
        super().__init__()
        self.device = device
        self.latest_bgr: np.ndarray | None = None
        self.frozen_bgr: np.ndarray | None = None
        self.drag_start: QPoint | None = None
        self.drag_end: QPoint | None = None
        self.dragging = False
        self.frame_times: list[float] = []
        self._last_title = ""
        self._preview_started = False
        self._preview_paused = False
        self._toolbar_dragging = False
        self._window_moving = False
        self._screen_wh = tuple(screen_wh) if screen_wh else None
        self.picking_coord = False
        self.cursor_pos: QPoint | None = None

        self.setWindowTitle("AirPicker")
        self.screen = ScreenWidget(self)
        self.setCentralWidget(self.screen)
        if self._screen_wh:
            init_w, init_h = self._aspect_size(*self._screen_wh)
            self.resize(init_w, init_h)
        else:
            self.resize(MAX_W, MAX_H)

        self.toolbar = FloatingToolbar()
        self.toolbar.drag_state_changed = self.set_toolbar_dragging
        self.toolbar.settings_clicked = self.open_toolbar_settings
        self.toolbar.coord_clicked = self.start_pick_coord

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_frame)
        self._move_resume_timer = QTimer(self)
        self._move_resume_timer.setSingleShot(True)
        self._move_resume_timer.timeout.connect(self._on_move_resume)

        method = getattr(getattr(device, "screen_proxy", None), "method_name", "MINICAP")
        print(f"[信息] 设备连接成功（{method}）")

    def open_toolbar_settings(self) -> None:
        dialog = ToolbarSettingsDialog(self.toolbar.is_horizontal(), self)
        if dialog.exec() == QDialog.Accepted:
            self.toolbar.set_horizontal(dialog.is_horizontal())
            if self.toolbar.is_horizontal():
                self.toolbar.move(
                    self.x() + self.width() - self.toolbar.width() - 20,
                    self.y() + 60,
                )

    def start(self) -> None:
        self._preview_started = True
        if not self._preview_paused:
            self.timer.start(FRAME_INTERVAL_MS)

    def set_preview_paused(self, paused: bool) -> None:
        self._preview_paused = paused
        if paused:
            if self.timer.isActive():
                self.timer.stop()
        elif self._preview_started and not self.timer.isActive():
            self.timer.start(FRAME_INTERVAL_MS)

    def set_toolbar_dragging(self, dragging: bool) -> None:
        self._toolbar_dragging = dragging
        if dragging:
            self.set_preview_paused(True)
        else:
            self._maybe_resume_preview()

    def _maybe_resume_preview(self) -> None:
        if not self._toolbar_dragging and not self._window_moving:
            self.set_preview_paused(False)

    def moveEvent(self, event) -> None:
        if self._preview_started:
            self._window_moving = True
            self.set_preview_paused(True)
            self._move_resume_timer.start(200)
        super().moveEvent(event)

    def _aspect_size(self, w: int, h: int) -> tuple[int, int]:
        scale = min(MAX_W / w, MAX_H / h)
        return max(1, int(round(w * scale))), max(1, int(round(h * scale)))

    def _sync_window_aspect(self, w: int, h: int) -> None:
        if self._screen_wh == (w, h):
            return
        self._screen_wh = (w, h)

    def _on_move_resume(self) -> None:
        self._window_moving = False
        self._maybe_resume_preview()

    # -------- 抓帧与渲染（主线程，与已验证的 OpenCV 版同构）--------
    def on_frame(self) -> None:
        if self.dragging or self._preview_paused:
            return
        try:
            raw = self.device.snapshot()
        except Exception as exc:
            print(f"[警告] 截图异常：{exc}")
            return
        if raw is None or np.asarray(raw).size == 0:
            return

        arr = np.asarray(raw)
        if arr.ndim == 2:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        elif arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        if not arr.flags.c_contiguous:
            arr = np.ascontiguousarray(arr)
        self.latest_bgr = arr

        h, w = arr.shape[:2]
        dpr = self.screen.devicePixelRatioF() or 1.0
        view_w, view_h = max(1, self.screen.width()), max(1, self.screen.height())
        scale = min((view_w * dpr) / w, (view_h * dpr) / h)
        if scale < 1.0:
            dw, dh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
            display = cv2.resize(arr, (dw, dh), interpolation=cv2.INTER_AREA)
        else:
            display = arr
        if DISPLAY_SHARPEN:
            blurred = cv2.GaussianBlur(display, (0, 0), 1.0)
            display = cv2.addWeighted(display, 1.25, blurred, -0.25, 0)

        dh, dw = display.shape[:2]
        image = QImage(display.data, dw, dh, 3 * dw, QImage.Format_BGR888).copy()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(dpr)
        self.screen.setPixmap(pixmap)
        self._sync_window_aspect(w, h)

        self.frame_times.append(time.perf_counter())
        self.frame_times = self.frame_times[-20:]
        self._update_title()

    def _fps(self) -> int:
        if len(self.frame_times) < 2:
            return 0
        span = self.frame_times[-1] - self.frame_times[0]
        return int((len(self.frame_times) - 1) / span) if span > 0 else 0

    def _update_title(self) -> None:
        if self.latest_bgr is None:
            return
        h, w = self.latest_bgr.shape[:2]
        pm = self.screen.pixmap()
        if pm:
            dpr = pm.devicePixelRatioF() or 1.0
            dw, dh = pm.width() / dpr, pm.height() / dpr
        else:
            dw, dh = w, h
        title = (
            f"AirPicker · 原图 {w} x {h} · "
            f"显示 {int(round(dw))} x {int(round(dh))} · {self._fps()} FPS"
        )
        if title != self._last_title:
            self.setWindowTitle(title)
            self._last_title = title

    # -------- 框选与保存 --------
    def begin_selection(self, pos: QPoint) -> None:
        if self.latest_bgr is None:
            return
        self.frozen_bgr = self.latest_bgr.copy()
        self.drag_start = pos
        self.drag_end = pos
        self.dragging = True
        self.screen.update()

    def update_selection(self, pos: QPoint) -> None:
        if not self.dragging:
            return
        self.drag_end = pos
        self.screen.update()

    def finish_selection(self, pos: QPoint) -> None:
        if not self.dragging:
            return
        self.drag_end = pos
        self.dragging = False
        self.screen.update()
        self.save_template()

    def cancel_selection(self) -> None:
        self.dragging = False
        self.frozen_bgr = None
        self.drag_start = self.drag_end = None
        self.screen.update()

    def _to_source(self, pos: QPoint) -> tuple[int, int]:
        pm = self.screen.pixmap()
        frame = self.frozen_bgr if self.frozen_bgr is not None else self.latest_bgr
        if pm is None or frame is None:
            return 0, 0
        h, w = frame.shape[:2]
        dpr = pm.devicePixelRatioF() or 1.0
        iw, ih = pm.width() / dpr, pm.height() / dpr
        ox = (self.screen.width() - iw) / 2
        oy = (self.screen.height() - ih) / 2
        sx = int(round((pos.x() - ox) / iw * w))
        sy = int(round((pos.y() - oy) / ih * h))
        return max(0, min(w - 1, sx)), max(0, min(h - 1, sy))

    # -------- 坐标获取 --------
    def start_pick_coord(self) -> None:
        if self.latest_bgr is None:
            print("[提示] 画面尚未就绪，暂时无法取点")
            return
        self.picking_coord = True
        self.screen.setCursor(Qt.CrossCursor)
        self.setWindowTitle("AirPicker · 取点模式：单击画面获取坐标，右键取消")

    def cancel_pick_coord(self) -> None:
        self.picking_coord = False
        self.screen.unsetCursor()
        self._last_title = ""
        self._update_title()

    def pick_coord(self, pos: QPoint) -> None:
        x, y = self._to_source(pos)
        text = f"{x}, {y}"
        print(f"[坐标] {text}")
        try:
            if pyperclip is None:
                raise RuntimeError("pyperclip 未安装")
            pyperclip.copy(text)
            print("坐标已复制到剪贴板")
        except Exception as exc:
            print(f"剪贴板不可用（{exc}），请手动复制：{text}")
        self.cancel_pick_coord()

    def save_template(self) -> None:
        if self.frozen_bgr is None or self.drag_start is None or self.drag_end is None:
            return
        p1 = self._to_source(self.drag_start)
        p2 = self._to_source(self.drag_end)
        x1, x2 = sorted((p1[0], p2[0]))
        y1, y2 = sorted((p1[1], p2[1]))
        if x2 - x1 < MIN_SELECT or y2 - y1 < MIN_SELECT:
            return

        crop_bgr = self.frozen_bgr[y1:y2, x1:x2]
        PICS_DIR.mkdir(parents=True, exist_ok=True)
        name = f"tpl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.png"
        path = PICS_DIR / name
        Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)).save(path)

        rel = os.path.relpath(path, SCRIPTS_DIR).replace("\\", "/")
        template_code = f'Template(r"{rel}")'
        full_code = f"touch({template_code})"
        mode = COPY_MODE if COPY_MODE in ("touch", "template") else "touch"
        code = full_code if mode == "touch" else template_code

        print(f"模板已保存：{path.as_posix()}")
        print(f"Template：{template_code}")
        print(f"完整命令：{full_code}")
        try:
            if pyperclip is None:
                raise RuntimeError("pyperclip 未安装")
            pyperclip.copy(code)
            print("已复制到剪贴板")
        except Exception as exc:
            print(f"剪贴板不可用（{exc}），请手动复制上面的代码")
        self.frozen_bgr = None

    def closeEvent(self, event) -> None:
        self._preview_started = False
        self.timer.stop()
        self._move_resume_timer.stop()
        self.toolbar.close()
        super().closeEvent(event)


def main() -> None:
    from airtest.core.api import connect_device
    from airtest.core.android.cap_methods.minicap import Minicap

    quality_flag = f"-Q {MINICAP_QUALITY}"
    if quality_flag not in Minicap.CMD:
        Minicap.CMD = f"{Minicap.CMD} {quality_flag}"

    uri = _build_uri()
    print(f"[信息] 正在连接设备：{uri}")
    try:
        device = connect_device(uri)
    except Exception as exc:
        print(f"[错误] 设备连接失败：{exc}")
        print("[提示] MINICAP 不可用时可改用：")
        print("       Android:///?cap_method=JAVACAP&touch_method=MINITOUCH")
        raise SystemExit(1) from exc

    screen_wh = _device_screen_wh(device)
    if screen_wh:
        print(f"[信息] 设备屏幕：{screen_wh[0]} x {screen_wh[1]}")

    app = QApplication([])
    window = MainWindow(device, screen_wh)
    window.show()
    window.toolbar.move(window.x() + window.width() - 76, window.y() + 60)
    window.toolbar.show()
    QTimer.singleShot(0, window.start)
    app.exec()


if __name__ == "__main__":
    main()
