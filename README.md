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
2. 如需调整运行参数，修改 `airpicker/config.py`：
   - `SERIAL`：多设备时指定序列号，留空则使用默认设备。
   - `COPY_MODE`：`touch` 生成 `touch(Template(...))`，`template` 只生成 `Template(...)`。
   - `MAX_W / MAX_H`、`FPS`：控制显示窗口大小与刷新率。
   工具栏横 / 竖排列保存在项目根目录 `settings.json`（`toolbar.horizontal`：`true` 横向、`false` 竖向），也可通过工具栏的设置弹窗修改并自动保存；文件缺失或损坏时自动回退默认值。
3. 运行工具：

   ```bash
   uv run python -m airpicker
   ```

   （在 PyCharm 中也可直接运行项目根目录的 `main.py`。）

4. **默认模式（鼠标模拟触控）**：在投屏画面上左键单击 → 向设备发送点击；左键按住拖拽 → 向设备发送滑动。坐标按设备原图分辨率换算。
5. **框选模板**：点击悬浮工具栏的「四角框」按钮进入框选模式，左键拖拽框选目标区域，松开后会：
   - 将原图分辨率的裁剪结果保存到 `pics/tpl_时间戳.png`；
   - 在控制台打印 `Template(...)` 与 `touch(Template(...))`；
   - 将代码复制到剪贴板；
   - 自动回到默认触控模式。
6. **获取坐标**：点击工具栏的准星按钮进入取点模式，此时触控 / 滑动**失效**；单击画面只复制坐标并自动回到默认模式，右键可取消。
7. 在 `scripts/test_demo.py` 中按 `Ctrl + V` 粘贴即可使用。
8. 关闭窗口退出；框选 / 取点过程中按右键可取消并返回默认模式。

## MINICAP 不可用时

连接或取帧失败时，控制台会提示改用 JAVACAP：

```text
Android:///?cap_method=JAVACAP&touch_method=MINITOUCH
```

将 `airpicker/config.py` 里的 `DEVICE_URI` 改为上述字符串后重试。多设备时保留 `127.0.0.1:5037/序列号` 部分，只替换 `cap_method`。

## 目录结构

```text
main.py                             PyCharm 入口
settings.json                      界面设置（工具栏横 / 竖）
airpicker/                          Python 包
  ├── __main__.py                   启动入口（python -m airpicker）
  ├── config.py                     配置常量
  ├── settings.py                   设置读写
  ├── device.py                     设备连接
  ├── image_utils.py                图像处理与坐标换算
  ├── template_store.py             模板保存与剪贴板
  ├── screen_widget.py              投屏控件
  ├── toolbar.py                    悬浮工具栏
  └── main_window.py                主窗口编排
scripts/test_demo.py                Airtest 示例脚本（粘贴目标）
pics/                               生成的模板图片
logs/                               Airtest 日志
requirements.txt                    依赖清单（uv 项目以 pyproject.toml 为准）
```
