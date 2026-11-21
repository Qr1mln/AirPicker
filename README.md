# AirPicker

在 PyCharm 中直接从 Android 实时屏幕框选按钮/图标，自动生成 Airtest 模板代码并复制到剪贴板。

## 环境

- Python >= 3.10，Windows（剪贴板功能依赖系统）
- 使用 [uv](https://docs.astral.sh/uv/) 管理环境

## 安装

```bash
uv sync
```

## 使用

1. 手机开启 USB 调试，执行 `adb devices` 确认能看到设备。
2. 如需调整配置，修改 `tools/template_capture_minicap.py` 顶部配置区：
   - `SERIAL`：多设备时指定序列号，留空则使用默认设备。
   - `COPY_MODE`：`touch` 生成 `touch(Template(...))`，`template` 只生成 `Template(...)`。
   - `MAX_W / MAX_H`、`FPS`：控制显示窗口大小与刷新率。
3. 运行工具：

   ```bash
   uv run python tools/template_capture_minicap.py
   ```

   （在 PyCharm 中也可直接运行项目根目录的 `main.py`。）

4. 在窗口中**左键拖拽**框选目标区域，松开鼠标后会：
   - 将原图分辨率的裁剪结果保存到 `pics/tpl_时间戳.png`；
   - 在控制台打印 `Template(...)` 与 `touch(Template(...))`；
   - 将代码复制到剪贴板。
5. 在 `scripts/test_demo.py` 中按 `Ctrl + V` 粘贴即可使用。
6. 按 `q` 或 `ESC` 退出窗口；框选过程中按右键可取消。

## MINICAP 不可用时

连接或取帧失败时，控制台会提示改用 JAVACAP：

```text
Android:///?cap_method=JAVACAP&touch_method=MINITOUCH
```

将 `tools/template_capture_minicap.py` 顶部的 `DEVICE_URI` 改为上述字符串后重试。多设备时保留 `127.0.0.1:5037/序列号` 部分，只替换 `cap_method`。

## 目录结构

```text
tools/template_capture_minicap.py   模板截取工具
scripts/test_demo.py                Airtest 示例脚本（粘贴目标）
pics/                               生成的模板图片
logs/                               Airtest 日志
requirements.txt                    依赖清单（uv 项目以 pyproject.toml 为准）
```
