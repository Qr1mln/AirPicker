# -*- coding: utf-8 -*-
"""Airtest 示例脚本：把 AirPicker 生成的代码粘贴到下面的 touch() 处。"""
from airtest.core.api import Template, connect_device, touch

connect_device("Android:///?cap_method=MINICAP&touch_method=MINITOUCH")

# 在 AirPicker 窗口框选目标后，将剪贴板中的代码粘贴到此处：
# touch(Template(r"../pics/tpl_20250101_123456_789.png"))
