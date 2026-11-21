# -*- coding: utf-8 -*-
"""AirPicker P0：从 Android 实时屏幕框选模板，并生成 Airtest 代码。

运行：
    uv run python tools/template_capture_minicap.py
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMainWindow,
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
        if event.button() == Qt.LeftButton:
            self.app.begin_selection(event.position().toPoint())
        elif event.button() == Qt.RightButton:
            self.app.cancel_selection()

    def mouseMoveEvent(self, event) -> None:
        self.app.update_selection(event.position().toPoint())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.app.finish_selection(event.position().toPoint())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.app.dragging and self.app.drag_start and self.app.drag_end:
            rect = QRect(self.app.drag_start, self.app.drag_end).normalized()
            painter = QPainter(self)
            painter.setPen(QPen(SELECT_COLOR, 2))
            painter.setBrush(Qt.transparent)
            painter.drawRect(rect)
            painter.end()


class IconButton(QWidget):
    """自绘线性图标按钮（仅展示，暂无点击逻辑）。"""

    def __init__(self, kind: str, parent: QWidget):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(40, 44)
        self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(95, 95, 95), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        k = self.kind

        if k == "phone":
            p.drawRoundedRect(int(cx - 9), int(cy - 13), 18, 26, 3, 3)
            p.drawLine(int(cx - 6), int(cy - 9), int(cx + 6), int(cy - 9))
            p.drawEllipse(int(cx - 2), int(cy + 9), 4, 4)
        elif k == "person":
            p.drawEllipse(int(cx - 6), int(cy - 12), 12, 12)
            p.drawArc(int(cx - 13), int(cy - 2), 26, 24, 180 * 16, 180 * 16)
        elif k == "tools":
            p.setWidth(3)
            p.drawLine(int(cx - 10), int(cy + 10), int(cx + 8), int(cy - 8))
            p.drawArc(int(cx), int(cy - 13), 14, 14, 270 * 16, 180 * 16)
        elif k == "headset":
            p.drawArc(int(cx - 12), int(cy - 13), 24, 24, 180 * 16, 180 * 16)
            p.drawRoundedRect(int(cx - 14), int(cy - 2), 6, 14, 2, 2)
            p.drawRoundedRect(int(cx + 8), int(cy - 2), 6, 14, 2, 2)
        elif k == "cart":
            p.drawLine(int(cx - 13), int(cy - 10), int(cx - 9), int(cy - 10))
            p.drawLine(int(cx - 9), int(cy - 10), int(cx - 5), int(cy + 4))
            p.drawLine(int(cx - 5), int(cy + 4), int(cx + 11), int(cy + 4))
            p.drawLine(int(cx + 11), int(cy + 4), int(cx + 13), int(cy - 5))
            p.drawLine(int(cx + 13), int(cy - 5), int(cx - 3), int(cy - 5))
            p.setBrush(QColor(95, 95, 95))
            p.drawEllipse(int(cx - 6), int(cy + 5), 4, 4)
            p.drawEllipse(int(cx + 7), int(cy + 5), 4, 4)
        elif k == "upload":
            p.drawLine(int(cx), int(cy + 10), int(cx), int(cy - 10))
            p.drawLine(int(cx - 6), int(cy - 4), int(cx), int(cy - 10))
            p.drawLine(int(cx), int(cy - 10), int(cx + 6), int(cy - 4))
            p.drawLine(int(cx - 9), int(cy + 12), int(cx + 9), int(cy + 12))
        p.end()


class FloatingToolbar(QFrame):
    """独立顶层悬浮窗口：无边框、置顶、可鼠标拖拽。"""

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(56)
        self._drag_pos: QPoint | None = None
        self.drag_state_changed = None
        self.setStyleSheet("FloatingToolbar { background: #f5f5f5; border: 1px solid #d8d8d8; }")

        inner = QFrame(self)
        inner.setObjectName("toolbarPanel")
        inner.setStyleSheet(
            "#toolbarPanel { background: #ffffff; border: 1px solid #d8d8d8; }"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(inner)

        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 4, 0, 4)
        inner_layout.setSpacing(0)
        for kind in ("phone", "person", "tools", "headset", "cart", "upload"):
            inner_layout.addWidget(IconButton(kind, inner))

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
        self._aspect_resizing = False

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

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_frame)
        self._move_resume_timer = QTimer(self)
        self._move_resume_timer.setSingleShot(True)
        self._move_resume_timer.timeout.connect(self._on_move_resume)

        method = getattr(getattr(device, "screen_proxy", None), "method_name", "MINICAP")
        print(f"[信息] 设备连接成功（{method}）")

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._aspect_resizing or not self._screen_wh or self.isMaximized():
            return
        src_w, src_h = self._screen_wh
        old_size, new_size = event.oldSize(), event.size()
        if not old_size.isValid():
            return
        dw = abs(new_size.width() - old_size.width()) / max(1, old_size.width())
        dh = abs(new_size.height() - old_size.height()) / max(1, old_size.height())
        self._aspect_resizing = True
        if dh > dw:
            target_w = max(1, int(round(new_size.height() * src_w / src_h)))
            if target_w != new_size.width():
                self.resize(target_w, new_size.height())
        else:
            target_h = max(1, int(round(new_size.width() * src_h / src_w)))
            if target_h != new_size.height():
                self.resize(new_size.width(), target_h)
        self._aspect_resizing = False

    def _aspect_size(self, w: int, h: int) -> tuple[int, int]:
        scale = min(MAX_W / w, MAX_H / h)
        return max(1, int(round(w * scale))), max(1, int(round(h * scale)))

    def _sync_window_aspect(self, w: int, h: int) -> None:
        if self._screen_wh == (w, h):
            return
        self._screen_wh = (w, h)
        target_w, target_h = self._aspect_size(w, h)
        if self.width() == target_w and self.height() == target_h:
            return
        self._aspect_resizing = True
        self.resize(target_w, target_h)
        self.toolbar.move(self.x() + target_w - 76, self.y() + 60)
        self._aspect_resizing = False

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
        if pm is None or self.frozen_bgr is None:
            return 0, 0
        h, w = self.frozen_bgr.shape[:2]
        dpr = pm.devicePixelRatioF() or 1.0
        iw, ih = pm.width() / dpr, pm.height() / dpr
        ox = (self.screen.width() - iw) / 2
        oy = (self.screen.height() - ih) / 2
        sx = int(round((pos.x() - ox) / iw * w))
        sy = int(round((pos.y() - oy) / ih * h))
        return max(0, min(w - 1, sx)), max(0, min(h - 1, sy))

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
