# -*- coding: utf-8 -*-
"""AirPicker 入口：从 Android 实时屏幕框选模板，并生成 Airtest 代码。

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

from airpicker.device import connect, device_screen_wh


def main() -> None:
    print("[信息] 正在连接设备：...")
    try:
        device = connect()
    except Exception as exc:
        print(f"[错误] 设备连接失败：{exc}")
        print("[提示] MINICAP 不可用时可改用：")
        print("       Android:///?cap_method=JAVACAP&touch_method=MINITOUCH")
        raise SystemExit(1) from exc

    screen_wh = device_screen_wh(device)
    if screen_wh:
        print(f"[信息] 设备屏幕：{screen_wh[0]} x {screen_wh[1]}")

    from airpicker.main_window import MainWindow

    app = QApplication([])
    window = MainWindow(device, screen_wh)
    window.show()
    window.toolbar.move(
        window.x() + window.width() - window.toolbar.width() - 20,
        window.y() + 60,
    )
    window.toolbar.constrain_to_window()
    window.toolbar.sync_offset()
    window.toolbar.show()
    window.toolbar.raise_above_main()
    QTimer.singleShot(0, window.start)
    app.exec()


if __name__ == "__main__":
    main()
