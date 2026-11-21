# -*- coding: utf-8 -*-
"""AirPicker 全局配置常量。"""
from pathlib import Path

# -------------------------------- 设备 --------------------------------
SERIAL = ""  # 多设备时填设备序列号，例如 "emulator-5554"
DEVICE_URI = "Android:///?cap_method=MINICAP&touch_method=MINITOUCH"
MINICAP_QUALITY = 100

# -------------------------------- 显示 --------------------------------
MAX_W = 1280
MAX_H = 1200
DISPLAY_SHARPEN = True
FPS = 30
FRAME_INTERVAL_MS = max(1, int(1000 / max(1, FPS)))

# -------------------------------- 模板 --------------------------------
COPY_MODE = "template"  # "touch" -> touch(Template(...))；"template" -> Template(...)
MIN_SELECT = 4

# -------------------------------- 交互模式 --------------------------------
MODE_GESTURE = "gesture"        # 默认：鼠标模拟设备触控 / 滑动
MODE_SELECT = "select"          # 框选模板
MODE_PICK_COORD = "pick_coord"  # 获取坐标（此时触控 / 滑动失效）

TAP_SLOP = 6          # 鼠标位移小于该像素视为点击，否则视为滑动
SWIPE_DURATION = 0.3  # 模拟滑动持续时间（秒）

ROOT = Path(__file__).resolve().parent.parent
PICS_DIR = ROOT / "pics"
SCRIPTS_DIR = ROOT / "scripts"
