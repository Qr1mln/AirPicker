# -*- coding: utf-8 -*-
"""悬浮工具栏图标的纯绘制逻辑。"""
from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPolygonF


def draw_refresh(p: QPainter, cx: float, cy: float) -> None:
    r = 10.0
    box = (int(cx - r), int(cy - r), int(2 * r), int(2 * r))
    p.drawArc(*box, -60 * 16, 255 * 16)
    p.drawArc(*box, 120 * 16, 255 * 16)
    for angle in (-60, 120):
        a = math.radians(angle)
        tip = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
        p.drawLine(tip, QPointF(tip.x() - 4, tip.y() - 1))
        p.drawLine(tip, QPointF(tip.x() + 1, tip.y() - 4))


def draw_back(p: QPainter, cx: float, cy: float) -> None:
    p.drawLine(int(cx - 10), int(cy), int(cx + 10), int(cy))
    p.drawLine(int(cx - 10), int(cy), int(cx - 3), int(cy - 7))
    p.drawLine(int(cx - 10), int(cy), int(cx - 3), int(cy + 7))


def draw_home(p: QPainter, cx: float, cy: float) -> None:
    p.drawLine(int(cx - 11), int(cy - 1), int(cx), int(cy - 11))
    p.drawLine(int(cx), int(cy - 11), int(cx + 11), int(cy - 1))
    p.drawLine(int(cx - 9), int(cy - 3), int(cx - 9), int(cy + 10))
    p.drawLine(int(cx + 9), int(cy - 3), int(cx + 9), int(cy + 10))
    p.drawLine(int(cx - 9), int(cy + 10), int(cx + 9), int(cy + 10))
    p.drawRect(int(cx - 3), int(cy + 2), 6, 8)


def draw_coord(p: QPainter, cx: float, cy: float) -> None:
    p.drawEllipse(QPointF(cx, cy), 9, 9)
    p.drawEllipse(QPointF(cx, cy), 2, 2)
    p.drawLine(int(cx - 13), int(cy), int(cx - 4), int(cy))
    p.drawLine(int(cx + 4), int(cy), int(cx + 13), int(cy))
    p.drawLine(int(cx), int(cy - 13), int(cx), int(cy - 4))
    p.drawLine(int(cx), int(cy + 4), int(cx), int(cy + 13))


def draw_select(p: QPainter, cx: float, cy: float) -> None:
    x1, y1, x2, y2 = int(cx - 10), int(cy - 9), int(cx + 10), int(cy + 9)
    for ax, ay, sx, sy in (
        (x1, y1, 1, 1), (x2, y1, -1, 1),
        (x1, y2, 1, -1), (x2, y2, -1, -1),
    ):
        p.drawLine(ax, ay, ax + 5 * sx, ay)
        p.drawLine(ax, ay, ax, ay + 5 * sy)


def draw_swipe(p: QPainter, cx: float, cy: float) -> None:
    sx, sy, ex, ey = int(cx - 10), int(cy + 8), int(cx + 10), int(cy - 8)
    p.drawLine(sx, sy, ex, ey)
    p.drawEllipse(QPointF(sx, sy), 2.5, 2.5)
    p.drawLine(ex, ey, ex - 7, ey + 1)
    p.drawLine(ex, ey, ex - 1, ey + 7)


def draw_screenshot(p: QPainter, cx: float, cy: float) -> None:
    p.drawRoundedRect(QRectF(cx - 11, cy - 7, 22, 16), 3, 3)
    p.drawLine(int(cx - 6), int(cy - 7), int(cx - 4), int(cy - 11))
    p.drawLine(int(cx - 4), int(cy - 11), int(cx + 4), int(cy - 11))
    p.drawLine(int(cx + 4), int(cy - 11), int(cx + 6), int(cy - 7))
    p.drawEllipse(QPointF(cx, cy + 1), 5, 5)
    p.drawEllipse(QPointF(cx + 7.5, cy - 3.5), 1.2, 1.2)


def draw_settings(p: QPainter, cx: float, cy: float) -> None:
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


ICON_DRAWERS: dict[str, Callable[[QPainter, float, float], None]] = {
    "refresh": draw_refresh,
    "back": draw_back,
    "home": draw_home,
    "coord": draw_coord,
    "select": draw_select,
    "swipe": draw_swipe,
    "screenshot": draw_screenshot,
    "settings": draw_settings,
}
