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
COPY_MODE = "touch"  # "touch" -> touch(Template(...))；"template" -> Template(...)
MIN_SELECT = 4

ROOT = Path(__file__).resolve().parent.parent
PICS_DIR = ROOT / "pics"
SCRIPTS_DIR = ROOT / "scripts"
