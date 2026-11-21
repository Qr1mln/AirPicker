# AirPicker MVP 规划

> **项目名：** AirPicker

## 1. 项目背景

在 `Airtest + PyCharm` 开发模式下，经常需要从 Android 手机实时屏幕中截取按钮、图标、文字区域，并生成 Airtest 可用的模板代码：

```python
touch(Template(r"../pics/tpl_xxx.png"))
```

目前常见方式是打开 AirtestIDE 截图、框选、复制代码，但如果希望完全在 PyCharm 开发流程中完成，就需要一个独立的小工具。

本项目目标是做一个独立 Python 脚本，实现：

```text
实时显示 Android 屏幕
→ 鼠标框选目标区域
→ 保存模板图片
→ 自动生成 Airtest Template 命令
→ 复制到剪贴板
→ 在 PyCharm 中直接粘贴使用
```

---

## 2. MVP 目标

### 一句话目标

做一个可在 PyCharm 中运行的 Python 小工具，帮助 Airtest 开发者快速从 Android 实时屏幕中截取模板图片，并自动生成可粘贴的 Airtest 模板代码。

### 核心闭环

```text
运行脚本
  ↓
连接 Android 设备
  ↓
实时显示手机屏幕
  ↓
鼠标拖拽框选目标区域
  ↓
保存模板图片到 pics/
  ↓
生成 Airtest Template 代码
  ↓
复制到剪贴板
  ↓
在 PyCharm 测试脚本中 Ctrl+V 粘贴
```

---

## 3. MVP 范围

### P0：必须做

| 功能             | 说明                                |
| ---------------- | ----------------------------------- |
| Android 设备连接 | 使用 `MINICAP + MINITOUCH`          |
| 实时屏幕显示     | 使用 OpenCV 窗口显示手机画面        |
| 鼠标框选         | 左键拖拽选择模板区域                |
| 模板截图保存     | 保存到 `pics/` 目录                 |
| 自动生成代码     | 生成 `Template(r"../pics/xxx.png")` |
| 自动复制代码     | 复制到剪贴板，方便粘贴到 PyCharm    |
| 相对路径生成     | 路径基于 `scripts/` 目录生成        |
| 基本退出         | 按 `q` 退出窗口                     |

---

### P1：建议做

| 功能                 | 说明                                           |
| -------------------- | ---------------------------------------------- |
| 单设备 / 指定 serial | 通过配置填写设备序列号                         |
| MINICAP 失败提示     | 报错时给出明确说明                             |
| JAVACAP 兜底         | MINICAP 不行时快速切换                         |
| 帧率控制             | 控制到 20~30 FPS，避免占满 CPU                 |
| 显示缩放             | 大屏幕下窗口自动缩小，但保存原图尺寸           |
| 复制模式切换         | 复制 `Template(...)` 或 `touch(Template(...))` |

---

### P2：暂不做

| 功能                 | 原因                     |
| -------------------- | ------------------------ |
| PyCharm 插件         | 开发成本高，第一版没必要 |
| GUI 配置界面         | OpenCV 窗口 + 控制台足够 |
| 多设备下拉选择       | 先用 `SERIAL` 常量配置   |
| 模板重命名弹窗       | 时间戳命名够用           |
| 模板库管理           | 后续再做                 |
| 自动识别按钮         | 不是本工具 MVP 目标      |
| OCR / 图像增强       | 后续优化识别率时再做     |
| 自动生成完整测试脚本 | 第一版只生成单行代码     |

---

## 4. 技术选型

| 模块     | 技术            |
| -------- | --------------- |
| 设备连接 | Airtest Android |
| 屏幕获取 | MINICAP         |
| 触控能力 | MINITOUCH       |
| 图像显示 | OpenCV          |
| 图片处理 | Pillow          |
| 剪贴板   | pyperclip       |
| 开发环境 | PyCharm         |

### 连接参数

第一版连接字符串：

```python
Android:///?cap_method=MINICAP&touch_method=MINITOUCH
```

如果连接多个设备：

```python
Android://127.0.0.1:5037/设备序列号?cap_method=MINICAP&touch_method=MINITOUCH
```

说明：

- `MINICAP` 负责快速获取屏幕画面
- `MINITOUCH` 负责快速点击
- 模板截取工具本身主要用到 `MINICAP`
- 后续 Airtest 测试脚本中使用 `MINITOUCH`

---

## 5. 推荐目录结构

```text
AirtestProject/
├── tools/
│   └── template_capture_minicap.py
├── scripts/
│   └── test_demo.py
├── pics/
│   └── tpl_20250101_123456_789.png
├── logs/
├── requirements.txt
└── README.md
```

目录说明：

| 目录               | 用途                |
| ------------------ | ------------------- |
| `tools/`           | 放模板截取工具      |
| `scripts/`         | 放 Airtest 测试脚本 |
| `pics/`            | 放模板图片          |
| `logs/`            | 放 Airtest 日志     |
| `requirements.txt` | 依赖文件            |
| `README.md`        | 使用说明            |

---

## 6. MVP 阶段规划

### M0：环境验证版

目标：确认 `MINICAP + MINITOUCH` 能连上设备。

要做：

1. 安装依赖
2. 确认 `adb devices` 能看到设备
3. 使用 Airtest 连接 Android
4. 调用 `snapshot()` 获取一张图
5. 打印图片尺寸

验收标准：

```text
设备连接成功
screen size: (1080, 2400)
```

如果失败，要能看到明确错误，例如：

```text
MINICAP 启动失败，请尝试 JAVACAP
```

---

### M1：实时显示版

目标：把手机屏幕实时显示到电脑窗口里。

要做：

1. 使用 OpenCV 创建窗口
2. 循环调用 `snapshot()`
3. 将图片显示到窗口
4. 按 `q` 退出
5. 限制帧率，比如 30 FPS

验收标准：

- 打开脚本后能看到 Android 实时画面
- 手机画面变化后，电脑窗口同步变化
- 按 `q` 能正常退出
- CPU 占用不明显异常

---

### M2：框选裁剪版

目标：可以用鼠标框选目标区域。

要做：

1. 监听鼠标左键按下、移动、松开
2. 按下时冻结当前画面
3. 拖拽时画绿色矩形框
4. 松开时执行裁剪
5. 如果窗口做了缩放，需要把显示坐标换算回原图坐标

验收标准：

- 鼠标拖拽时能画框
- 松开后能拿到正确区域
- 框选位置和保存图片一致
- 窗口缩放后裁剪位置不偏移

---

### M3：模板生成版

目标：保存模板图片，并生成 Airtest 代码。

要做：

1. 图片保存到 `pics/`
2. 文件名用时间戳，避免覆盖
3. 生成相对于 `scripts/` 的路径
4. 生成：

```python
Template(r"../pics/tpl_xxx.png")
```

5. 生成完整操作代码：

```python
touch(Template(r"../pics/tpl_xxx.png"))
```

6. 复制到剪贴板

验收标准：

框选后控制台输出：

```text
模板已保存：/项目路径/pics/tpl_20250101_123456_789.png
Template：Template(r"../pics/tpl_20250101_123456_789.png")
完整命令：touch(Template(r"../pics/tpl_20250101_123456_789.png"))
已复制到剪贴板
```

在 PyCharm 中按 `Ctrl + V` 可以直接粘贴。

---

### M4：稳定可用版

目标：可以日常稳定使用。

要做：

1. 支持 `SERIAL` 配置
2. 支持 `COPY_MODE` 配置
3. 支持 `JAVACAP` 兜底
4. 截图失败不直接崩溃
5. 剪贴板失败时仍打印代码
6. 添加简单 README

验收标准：

- 单设备可直接运行
- 多设备可通过 serial 指定
- MINICAP 报错时能提示切换方案
- 剪贴板失败时仍能手动复制
- 按 README 可以复现

---

## 7. 核心功能设计

### 工具文件

```text
tools/template_capture_minicap.py
```

职责：

1. 读取配置
2. 连接 Android 设备
3. 循环获取屏幕帧
4. 显示实时窗口
5. 监听鼠标框选
6. 保存模板图片
7. 生成 Template 代码
8. 复制到剪贴板

---

### 第一版配置项

```python
SERIAL = ""

DEVICE_URI = "Android:///?cap_method=MINICAP&touch_method=MINITOUCH"

MAX_W = 720
MAX_H = 1000

FPS = 30

COPY_MODE = "touch"
```

配置说明：

| 配置            | 作用                                       |
| --------------- | ------------------------------------------ |
| `SERIAL`        | 多设备时指定设备                           |
| `DEVICE_URI`    | 连接参数                                   |
| `MAX_W / MAX_H` | 控制显示窗口大小                           |
| `FPS`           | 控制实时画面刷新率                         |
| `COPY_MODE`     | 控制复制 `Template` 还是 `touch(Template)` |

---

## 8. 验收用例

### 用例 1：单设备连接

前置条件：

```bash
adb devices
```

能看到一个设备。

操作：

```bash
python tools/template_capture_minicap.py
```

预期：

- 弹出实时屏幕窗口
- 画面连续刷新
- 按 `q` 退出

---

### 用例 2：截取登录按钮模板

操作：

1. 打开 App 登录页
2. 在实时窗口中框选登录按钮
3. 松开鼠标

预期：

`pics/` 下生成：

```text
tpl_20250101_123456_789.png
```

控制台输出：

```python
touch(Template(r"../pics/tpl_20250101_123456_789.png"))
```

剪贴板中也有同样代码。

---

### 用例 3：粘贴到测试脚本

在 `scripts/test_demo.py` 中粘贴：

```python
touch(Template(r"../pics/tpl_20250101_123456_789.png"))
```

运行测试脚本，能够成功点击对应按钮。

---

### 用例 4：窗口缩放后裁剪

操作：

1. 手机是 1080 x 2400
2. 显示窗口被缩小到 720 x 1600
3. 框选按钮
4. 保存模板

预期：

保存的是原始分辨率下的正确区域，不是缩放后的模糊小图。

---

### 用例 5：MINICAP 不可用

操作：

设备不支持 MINICAP。

预期：

提示：

```text
MINICAP 启动失败，建议改用：
Android:///?cap_method=JAVACAP&touch_method=MINITOUCH
```

而不是直接无提示崩溃。

---

## 9. 风险与应对

| 风险                 | 表现                         | 应对                             |
| -------------------- | ---------------------------- | -------------------------------- |
| MINICAP 兼容性差     | 黑屏、连接失败、服务启动失败 | 提供 JAVACAP 兜底                |
| 画面缩放导致裁剪偏移 | 保存区域和框选区域不一致     | 保存时做坐标换算                 |
| 模板图片不够清晰     | Airtest 识别失败             | 使用原始分辨率保存，不用窗口截图 |
| 剪贴板不可用         | `pyperclip` 报错             | 控制台打印代码，手动复制         |
| 多设备误连           | 连到错误手机                 | 配置 `SERIAL`                    |
| 实时刷新占 CPU       | 电脑卡顿                     | 限制 FPS 到 20~30                |
| 横竖屏切换           | 模板区域错乱                 | 统一在稳定页面截取               |

---

## 10. 版本路线

### v0.1：连通版

- 能连接设备
- 能 `snapshot()`
- 能打印图片尺寸

### v0.2：显示版

- 能实时显示 Android 屏幕
- 能按 `q` 退出

### v0.3：截取版

- 能鼠标框选
- 能保存到 `pics/`

### v0.4：代码生成版

- 能生成 `Template(...)`
- 能复制到剪贴板

### v0.5：稳定版

- 支持 serial
- 支持 JAVACAP fallback
- 错误处理完善

### v1.0：团队可用版

- README 完整
- 示例脚本完整
- 依赖文件完整
- 新成员可直接运行

---

## 11. MVP 最小实现原则

第一版坚持以下原则：

1. **不做 PyCharm 插件**  
   先做独立 Python 脚本，开发成本最低。

2. **不做图形化配置界面**  
   配置项直接写在脚本顶部。

3. **不做模板管理**  
   图片先全部放 `pics/`，靠时间戳命名。

4. **不做模板重命名**  
   后续再加输入弹窗。

5. **不做多设备自动选择**  
   多设备时用 `SERIAL` 常量指定。

6. **不依赖 AirtestIDE**  
   PyCharm + Python 脚本即可完成。

---

## 12. 推荐交付物

第一版只需要交付这些文件：

```text
AirtestProject/
├── tools/
│   └── template_capture_minicap.py
├── scripts/
│   └── test_demo.py
├── pics/
│   └── 模板图片.png
├── logs/
├── requirements.txt
└── README.md
```

### requirements.txt

```txt
airtest
pocoui
opencv-python
pillow
pyperclip
```

### README.md 至少包含

1. 安装依赖
2. 连接手机
3. 查看 `adb devices`
4. 运行 `template_capture_minicap.py`
5. 鼠标框选模板
6. 粘贴生成的 Airtest 代码
7. MINICAP 失败时如何切换 JAVACAP

---

## 13. 推荐实现顺序

按这个顺序做最稳：

```text
1. 先让 MINICAP 能连接并拿到图片
2. 再让 OpenCV 能实时显示
3. 再加鼠标框选
4. 再保存裁剪图片
5. 再生成 Template 代码
6. 最后加剪贴板和异常处理
```

不要一开始就把所有功能堆进去，容易排查困难。

---

## 14. 最终 MVP 定义

这个 MVP 成功的标准是：

> 你在 PyCharm 中运行一个 Python 脚本，能看到 Android 手机实时屏幕，用鼠标框选一个按钮后，自动保存模板图片，并自动生成可直接粘贴到 Airtest 脚本中的 `touch(Template(...))` 代码。

做到这一步，这个工具就已经具备实际价值。后续再考虑 GUI、多设备管理、模板重命名和自动识别。