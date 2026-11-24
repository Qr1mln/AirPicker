# -*- coding: utf-8 -*-
"""AirPicker 入口：界面先启动，设备连接由设置或自动连接触发。

运行：
    uv run python -m airpicker
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from airpicker.main_window import MainWindow


def main() -> None:
    print("[信息] AirPicker 已启动，暂不连接设备；可在设置中连接或开启自动连接")
    app = QApplication([])
    window = MainWindow()
    window.show()
    window.toolbar.move(20, 60)
    window.toolbar.constrain_to_window()
    QTimer.singleShot(0, window.start)
    app.exec()


if __name__ == "__main__":
    main()
