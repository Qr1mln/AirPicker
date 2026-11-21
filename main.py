# -*- coding: utf-8 -*-
"""PyCharm 入口：直接运行本文件等价于运行 tools/template_capture_minicap.py。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.template_capture_minicap import main

if __name__ == "__main__":
    main()