# -*- coding: utf-8 -*-
"""截图文件名表达式：随机 / 序号两种模式共用同一套占位符。"""
from __future__ import annotations

import random
import re
from datetime import datetime
from pathlib import Path

SCREENSHOT_NAME_RANDOM = "random"
SCREENSHOT_NAME_SEQUENCE = "sequence"
DEFAULT_RANDOM_EXPR = "screen_{datetime}_{ms}"
DEFAULT_SEQUENCE_EXPR = "screen_{0000}"

TOKEN_RE = re.compile(r"\{([^{}]+)\}")
INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')

NAME_HINT = "变量：{date}=年月日，{time}=时分秒，{datetime}=年月日_时分秒，{ms}=毫秒，{random}=三位随机数"
SEQ_HINT = "序号变量：{0000} 表示 4 位补零（0 的个数即位数），{seq} 表示不加零的序号，每次加 1"


def render_name(expr: str, number: int | None = None, now: datetime | None = None) -> str:
    """按表达式生成文件名；number=None 为随机模式，否则为序号模式。"""
    now = now or datetime.now()
    date = now.strftime("%Y%m%d")
    clock = now.strftime("%H%M%S")
    values = {
        "date": date,
        "time": clock,
        "datetime": f"{date}_{clock}",
        "ms": f"{now.microsecond // 1000:03d}",
        "random": f"{random.randint(0, 999):03d}",
    }
    has_number = False

    def replace(match: re.Match[str]) -> str:
        nonlocal has_number
        token = match.group(1)
        if token and set(token) == {"0"}:
            has_number = True
            return f"{number or 0:0{len(token)}d}"
        if token == "seq":
            has_number = True
            return str(number or 0)
        return values.get(token, match.group(0))

    text = TOKEN_RE.sub(replace, (expr or "").strip() or DEFAULT_RANDOM_EXPR)
    text = INVALID_CHARS_RE.sub("_", text).strip(" .")
    if number is not None and not has_number:
        stem, ext = (text[:-4], ".png") if text.lower().endswith(".png") else (text, ".png")
        text = f"{stem}_{number}{ext}"
    return text if text.lower().endswith(".png") else text + ".png"


def sequence_pattern(expr: str) -> re.Pattern[str]:
    """把序号表达式转成匹配已有文件的正则，序号位作为捕获组。"""
    text = (expr or "").strip() or DEFAULT_SEQUENCE_EXPR
    parts: list[str] = []
    last = 0
    for match in TOKEN_RE.finditer(text):
        parts.append(re.escape(text[last:match.start()]))
        token = match.group(1)
        if (token and set(token) == {"0"}) or token == "seq":
            parts.append(r"(\d+)")
        else:
            parts.append(r"[^\s]*?")
        last = match.end()
    tail = text[last:]
    if not tail.lower().endswith(".png"):
        parts.append(r"(?:\.png)?")
    parts.append(re.escape(tail))
    return re.compile("^" + "".join(parts) + "$", re.IGNORECASE)


def next_sequence_number(out_dir: Path, expr: str) -> int:
    """扫描目录内已有文件，返回下一个序号；新目录从 0 开始。"""
    try:
        entries = list(out_dir.iterdir())
    except OSError:
        return 0
    pattern = sequence_pattern(expr)
    highest = -1
    for entry in entries:
        match = pattern.match(entry.name)
        if not match:
            continue
        if match.groups():
            try:
                highest = max(highest, int(match.group(1)))
            except (TypeError, ValueError):
                pass
        else:
            highest += 1
    return max(0, highest + 1)


def resolve_sequence_number(out_dir: Path, expr: str, start: int | None = None) -> int:
    """从指定计数开始，若生成的文件名已存在就 +1，直到找到可用文件名。"""
    number = next_sequence_number(out_dir, expr) if start is None else max(0, start)
    while (out_dir / render_name(expr, number)).exists():
        number += 1
    return number


def preview_name(expr: str, mode: str, out_dir: Path, next_number: int | None = None) -> str:
    """设置弹窗用的预览：序号模式按当前计数/目录推断，随机模式按当前时间渲染。"""
    if mode == SCREENSHOT_NAME_SEQUENCE:
        return render_name(expr, resolve_sequence_number(out_dir, expr, next_number))
    return render_name(expr)
