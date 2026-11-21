# -*- coding: utf-8 -*-
"""Windows 原生悬浮工具栏：无边框分层窗口，可拖拽，带阴影。

不依赖额外 GUI 框架，复用 pywin32（airtest 已带入）。
仅作 UI 展示，图标暂无点击逻辑。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import struct
import threading
import time

import win32api
import win32con
import win32gui


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", _BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 3)]


_gdi32 = ctypes.windll.gdi32
_user32 = ctypes.windll.user32
from PIL import Image, ImageDraw, ImageFilter

_CLASS_NAME = "AirPickerFloatingToolbar"
_INSTANCES: dict[int, "FloatingToolbar"] = {}

_PANEL_W = 56
_ITEM_H = 48
_TOP_PAD = 8
_BOTTOM_PAD = 8
_SHADOW = 12
_RADIUS = 12
_ICON_COLOR = (95, 95, 95, 255)
_BORDER = (215, 215, 215, 255)


def _icon_phone(d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    d.rounded_rectangle([cx - 9, cy - 13, cx + 9, cy + 13], radius=3, outline=_ICON_COLOR, width=2)
    d.line([(cx - 6, cy - 9), (cx + 6, cy - 9)], fill=_ICON_COLOR, width=1)
    d.ellipse([cx - 2, cy + 9, cx + 2, cy + 13], outline=_ICON_COLOR, width=1)


def _icon_person(d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    d.ellipse([cx - 6, cy - 12, cx + 6, cy], outline=_ICON_COLOR, width=2)
    d.arc([cx - 13, cy - 2, cx + 13, cy + 22], start=180, end=360, fill=_ICON_COLOR, width=2)


def _icon_tools(d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    d.line([(cx - 10, cy + 10), (cx + 8, cy - 8)], fill=_ICON_COLOR, width=3)
    d.arc([cx + 1, cy - 13, cx + 13, cy - 1], start=270, end=90, fill=_ICON_COLOR, width=3)
    d.line([(cx - 11, cy - 10), (cx - 3, cy - 2)], fill=_ICON_COLOR, width=2)


def _icon_headset(d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    d.arc([cx - 12, cy - 13, cx + 12, cy + 11], start=180, end=360, fill=_ICON_COLOR, width=2)
    d.rounded_rectangle([cx - 14, cy - 2, cx - 8, cy + 12], radius=2, outline=_ICON_COLOR, width=2)
    d.rounded_rectangle([cx + 8, cy - 2, cx + 14, cy + 12], radius=2, outline=_ICON_COLOR, width=2)


def _icon_cart(d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    d.line([(cx - 13, cy - 10), (cx - 9, cy - 10), (cx - 5, cy + 4), (cx + 11, cy + 4)], fill=_ICON_COLOR, width=2)
    d.line([(cx - 5, cy + 4), (cx + 11, cy + 4), (cx + 13, cy - 5), (cx - 3, cy - 5)], fill=_ICON_COLOR, width=2)
    d.ellipse([cx - 6, cy + 5, cx - 2, cy + 9], fill=_ICON_COLOR)
    d.ellipse([cx + 7, cy + 5, cx + 11, cy + 9], fill=_ICON_COLOR)


def _icon_upload(d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    d.line([(cx, cy + 10), (cx, cy - 10)], fill=_ICON_COLOR, width=2)
    d.line([(cx - 6, cy - 4), (cx, cy - 10), (cx + 6, cy - 4)], fill=_ICON_COLOR, width=2)
    d.line([(cx - 9, cy + 12), (cx + 9, cy + 12)], fill=_ICON_COLOR, width=2)


_ICONS = (_icon_phone, _icon_person, _icon_tools, _icon_headset, _icon_cart, _icon_upload)


def _build_image() -> tuple[Image.Image, int]:
    panel_h = _TOP_PAD + _ITEM_H * len(_ICONS) + _BOTTOM_PAD
    pad = _SHADOW * 3
    width, height = _PANEL_W + pad * 2, panel_h + pad * 2

    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [pad + 1, pad + 3, pad + _PANEL_W - 1, pad + panel_h + 3],
        radius=_RADIUS,
        fill=(0, 0, 0, 135),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(_SHADOW))

    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle(
        [pad, pad, pad + _PANEL_W, pad + panel_h],
        radius=_RADIUS,
        fill=(255, 255, 255, 240),
        outline=_BORDER,
        width=1,
    )
    for i, draw_icon in enumerate(_ICONS):
        cx = pad + _PANEL_W // 2
        cy = pad + _TOP_PAD + _ITEM_H * i + _ITEM_H // 2
        draw_icon(pd, cx, cy)

    return Image.alpha_composite(shadow, panel), pad


def _wnd_proc(hwnd, msg, wparam, lparam):
    inst = _INSTANCES.get(hwnd)
    if inst is None:
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    if msg == win32con.WM_LBUTTONDOWN:
        inst._drag_start()
        return 0
    if msg == win32con.WM_MOUSEMOVE:
        inst._drag_move()
        return 0
    if msg == win32con.WM_LBUTTONUP:
        inst._drag_end()
        return 0
    if msg == win32con.WM_CAPTURECHANGED:
        inst._drag_end()
        return 0
    if msg == win32con.WM_RBUTTONUP:
        inst.stop()
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


class FloatingToolbar:
    def __init__(self, x: int, y: int):
        self._x, self._y = x, y
        self._image, _ = _build_image()
        self._w, self._h = self._image.size
        self.hwnd = 0
        self._thread: threading.Thread | None = None
        self._running = False
        self._dragging = False
        self._offset = (0, 0)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self.hwnd and win32gui.IsWindow(self.hwnd):
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def _drag_start(self) -> None:
        mx, my = win32api.GetCursorPos()
        wx, wy = win32gui.GetWindowRect(self.hwnd)[:2]
        self._offset = (mx - wx, my - wy)
        self._dragging = True
        win32gui.SetCapture(self.hwnd)

    def _drag_move(self) -> None:
        if not self._dragging:
            return
        mx, my = win32api.GetCursorPos()
        x = mx - self._offset[0]
        y = my - self._offset[1]
        win32gui.SetWindowPos(
            self.hwnd, 0, x, y, 0, 0,
            win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
        )

    def _drag_end(self) -> None:
        self._dragging = False
        if self.hwnd and win32gui.GetCapture() == self.hwnd:
            win32gui.ReleaseCapture()

    def _run(self) -> None:
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = _wnd_proc
        wc.lpszClassName = _CLASS_NAME
        wc.hbrBackground = 0
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error:
            pass

        hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE,
            _CLASS_NAME,
            "",
            win32con.WS_POPUP,
            self._x, self._y, self._w, self._h,
            0, 0, 0, None,
        )
        self.hwnd = hwnd
        _INSTANCES[hwnd] = self
        self._paint()
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        while self._running:
            win32gui.PumpWaitingMessages()
            time.sleep(0.01)

        if win32gui.IsWindow(hwnd):
            win32gui.DestroyWindow(hwnd)
        _INSTANCES.pop(hwnd, None)

    def _paint(self) -> None:
        bgra = bytearray()
        for r, g, b, a in self._image.getdata():
            f = a / 255.0
            bgra.extend((int(b * f), int(g * f), int(r * f), a))

        screen_dc = win32gui.GetDC(0)
        mem_dc = win32gui.CreateCompatibleDC(screen_dc)

        bmi = _BitmapInfo()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
        bmi.bmiHeader.biWidth = self._w
        bmi.bmiHeader.biHeight = -self._h  # 自顶向下
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB
        bits = ctypes.c_void_p()
        hbitmap = _gdi32.CreateDIBSection(
            int(mem_dc), ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
        )
        ctypes.memmove(bits, bytes(bgra), len(bgra))

        old = win32gui.SelectObject(mem_dc, hbitmap)
        blend = (0, 0, 255, 1)  # AC_SRC_ALPHA
        win32gui.UpdateLayeredWindow(
            self.hwnd, screen_dc, None, (self._w, self._h), mem_dc, (0, 0), 0, blend,
            win32con.ULW_ALPHA,
        )
        win32gui.SelectObject(mem_dc, old)
        _gdi32.DeleteObject(hbitmap)
        win32gui.DeleteDC(mem_dc)
        win32gui.ReleaseDC(0, screen_dc)
