# -*- coding: utf-8 -*-
"""PyCharm 入口：直接运行本文件等价于运行 airpicker 包。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airpicker.__main__ import main

if __name__ == "__main__":
    main()