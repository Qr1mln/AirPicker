# -*- coding: utf-8 -*-
"""场景动作：解析 airtest 语法的点击 / 滑动 / 按键，并下发到已连接设备。

支持的语法（每行一条，# 后为注释）：
    touch((540, 1200))
    swipe((540, 1500), (540, 600))
    swipe((540, 1500), (540, 600), duration=0.5)
    keyevent("HOME")
    keyevent('BACK')
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

_NUM = r"-?\d+(?:\.\d+)?"
_POINT = rf"\(\s*({_NUM})\s*,\s*({_NUM})\s*\)"
_TOUCH_RE = re.compile(
    rf"^touch\s*\(\s*{_POINT}\s*\)\s*(?:#.*)?$"
)
_SWIPE_RE = re.compile(
    rf"^swipe\s*\(\s*{_POINT}\s*,\s*{_POINT}\s*"
    rf"(?:,\s*duration\s*=\s*({_NUM})\s*)?\)\s*(?:#.*)?$"
)
_KEY_RE = re.compile(
    r"^keyevent\s*\(\s*(?:([\"'])([^\"']+)\1|([A-Za-z_][A-Za-z0-9_]*|\d+))\s*\)"
    r"\s*(?:#.*)?$"
)

DEFAULT_DURATION = 0.3
DEFAULT_DELAY = 0.3


@dataclass(frozen=True)
class Action:
    """一条已解析的动作。"""

    kind: str
    start: tuple[int, int] = (0, 0)
    end: tuple[int, int] | None = None
    duration: float = DEFAULT_DURATION
    raw: str = ""
    line: int = 0
    key: str = ""

    def summary(self) -> str:
        if self.kind == "touch":
            return f"touch{self.start}"
        if self.kind == "keyevent":
            return f"keyevent(\"{self.key}\")"
        return f"swipe{self.start}→{self.end}"


def parse_actions(text: str) -> tuple[list[Action], list[str]]:
    """解析动作文本，返回 (动作列表, 错误列表)。错误含行号，便于在编辑器中定位。"""
    actions: list[Action] = []
    errors: list[str] = []
    for lineno, raw_line in enumerate((text or "").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        touch = _TOUCH_RE.match(line)
        if touch:
            x, y = (int(float(touch.group(i))) for i in (1, 2))
            actions.append(Action("touch", (x, y), raw=line, line=lineno))
            continue
        swipe = _SWIPE_RE.match(line)
        if swipe:
            x1, y1, x2, y2 = (int(float(swipe.group(i))) for i in (1, 2, 3, 4))
            duration = float(swipe.group(5)) if swipe.group(5) else DEFAULT_DURATION
            actions.append(
                Action(
                    "swipe", (x1, y1), (x2, y2),
                    duration=duration, raw=line, line=lineno,
                )
            )
            continue
        keyevent = _KEY_RE.match(line)
        if keyevent:
            key = keyevent.group(2) or keyevent.group(3)
            actions.append(
                Action("keyevent", key=key, raw=line, line=lineno)
            )
            continue
        errors.append(
            f"第 {lineno} 行无法识别：{line}"
            "（支持 touch((x, y)) / swipe((x1, y1), (x2, y2)) / keyevent(\"HOME\")）"
        )
    return actions, errors


def dispatch_command(action: Action) -> str:
    """动作对应的设备下发命令描述（纯本地执行，不涉及 VLM）。"""
    if action.kind == "touch":
        return f"device.touch({action.start})"
    if action.kind == "swipe":
        return f"device.swipe({action.start}, {action.end}, duration={action.duration})"
    return f"device.keyevent({action.key!r})"


def execute_actions(
    actions: list[Action],
    device,
    *,
    delay: float = DEFAULT_DELAY,
    on_dispatch=None,
    on_step=None,
) -> int:
    """顺序执行动作，返回已执行条数。device 须为已连接的 airtest 设备。

    on_dispatch 在调用设备 API 前触发，on_step 在 API 无异常返回后触发，
    两者配合可区分「未下发」与「已下发但设备无反应」。
    """
    executed = 0
    for index, action in enumerate(actions):
        if on_dispatch is not None:
            on_dispatch(index + 1, len(actions), action)
        if action.kind == "touch":
            device.touch(action.start)
        elif action.kind == "swipe":
            device.swipe(action.start, action.end, duration=action.duration)
        else:
            device.keyevent(action.key)
        executed += 1
        if on_step is not None:
            on_step(index + 1, len(actions), action)
        if delay > 0 and index < len(actions) - 1:
            time.sleep(delay)
    return executed
