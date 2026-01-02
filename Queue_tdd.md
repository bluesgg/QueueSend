# 跨平台 ROI 变化驱动自动化工具（Windows / macOS）技术设计（TDD）

版本：v1.1（根据可交付性审查反馈修订）  
作者：ChatGPT（全栈/架构视角）  
日期：2026-01-01

---

## 1. 设计目标
- 在 Windows/macOS 上实现"点击输入点 → 粘贴 → 点击发送 → 冷却 → ROI 变化保持判定 → 下一条"的自动化流程。
- 完全依赖屏幕 ROI 变化判定推进；不读取目标应用内部状态。
- 支持多显示器（虚拟桌面坐标，Windows）；macOS 本版本仅支持单显示器。
- Windows Per-Monitor DPI aware、macOS 权限自检（屏幕录制/辅助功能）。
- UI 具备 Always on top 的运行面板、标定（ROI/点位）、阈值校准、日志、Pause/Resume/Stop。
- Pause 时检测消息列表变化。

---

## 2. 技术选型（推荐 MVP 路线）

### 2.1 推荐：Python + Qt（PySide6）
**理由**：跨平台 UI 成熟；屏幕捕获/输入注入生态完善；实现速度快；1 FPS 采样对性能压力低；适合快速迭代。

- UI：PySide6（Qt 6）
- 屏幕捕获：mss（支持全虚拟桌面抓取）
- 图像处理：numpy（灰度转换、diff 计算、mask）
- 输入注入（点击/移动）：pynput（或 pyautogui 作为备选）
- 剪贴板：Qt Clipboard（优先）或 pyperclip（备选）
- Windows DPI：ctypes 调用 SetProcessDpiAwarenessContext / SetProcessDpiAwareness
- macOS 权限检测：pyobjc 访问 Quartz / ApplicationServices（CGPreflightScreenCaptureAccess、AXIsProcessTrustedWithOptions）
- 打包：
  - Windows：PyInstaller
  - macOS：py2app 或 PyInstaller（结合 codesign/notarization）

> 备选路线（不作为本 TDD 的默认实现）：Tauri/Rust 或 Electron/Node。若后续需要更深度原生集成/更严格的分发体验，可在稳定后迁移。

---

## 3. 总体架构

### 3.1 模块划分
1. **UI Shell（Qt）**
   - 运行面板（Always on top、小窗、吸附到发送按钮所在屏幕右下角、倒计时）
   - 消息列表编辑器
   - 标定向导（ROI/输入点/发送点）
   - 阈值校准 UI（推荐值展示 + 手动微调）
   - 日志展示（环形缓冲 200 条）
   - 固定提示条（黄色背景）

2. **Automation Engine（自动化引擎）**
   - 状态机（Idle/Countdown/Sending/Cooling/WaitingHold/Paused）
   - 消息队列与进度 i/N
   - Pause/Resume/Stop 控制（线程安全）
   - 消息列表变化检测（Pause 时保存快照，Resume 时比对）

3. **Capture & Diff（截图与变化检测）**
   - 从"虚拟桌面"截图
   - ROI 裁剪、灰度化
   - 圆形 ROI mask
   - diff 计算与连续命中逻辑（hold_hits 重置）
   - 校准采样与 TH_HOLD 推荐值计算

4. **OS Adapter（平台适配）**
   - 坐标体系（虚拟桌面绝对坐标）
   - DPI/缩放处理（Windows，智能检测失败原因）
   - 权限检测与引导（macOS）
   - 输入注入（点击）

5. **Persistence（可选）**
   - 本 PRD 要求每次运行重标定；实现可选保存上次配置到本地（需明确"仅存本地、不上传"）。

### 3.2 线程与并发模型
- **UI 线程**：所有 Qt UI 操作。
- **自动化线程（Worker）**：执行点击/粘贴/冷却/采样/等待逻辑。
- 通讯：Qt Signals/Slots 或线程安全队列（Queue）+ 信号。

**原则**：
- 自动化线程不得直接操作 UI 控件；只发送状态更新/日志事件。
- Pause/Stop 使用原子标志（threading.Event）保证即时生效。

---

## 4. 坐标体系与多显示器

### 4.1 虚拟桌面绝对坐标
- 坐标原点：虚拟桌面左上角（可能为负值，取决于显示器布局）。
- ROI、输入点、发送点均记录为虚拟桌面坐标。

### 4.2 Windows DPI（Per-Monitor DPI aware）
目标：避免系统缩放导致的坐标偏移。

实现建议（启动时执行，Qt 初始化前）：
- Windows 10+：调用 `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)`
- 旧系统回退：`SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)` 或 `SetProcessDPIAware()`
- **检测与警告**：
  ```python
  try:
      result = SetProcessDpiAwarenessContext(...)
      if not result:
          error_code = GetLastError()
          if error_code == ERROR_ACCESS_DENIED:  # 已设置过，正常
              pass
          else:  # 真正失败
              显示警告横幅
  except Exception:
      显示警告横幅
  ```

> 关键点：必须在创建任何窗口（Qt 初始化）前设置 DPI awareness。

### 4.3 macOS 权限
- 屏幕录制权限：无则无法获取屏幕像素。
- 辅助功能权限（Accessibility）：无则无法注入鼠标点击/键盘事件。
- **单显示器限制**：本版本明确不支持多显示器，在README中说明。

设计：
- 启动自检：显示"缺失权限"清单，禁用 Start。
- 提供引导文案：系统设置 → 隐私与安全性 → 屏幕录制 / 辅助功能。

---

## 5. 标定（Calibration）设计

### 5.1 标定流程（每次运行）
1. 选择 ROI：拖拽矩形（虚拟桌面坐标）
2. 选择 ROI 形状：矩形 / 圆形（拖拽后选择形状）
   - 圆形 ROI：由矩形生成内切圆
3. 选择输入点：单击记录
4. 选择发送点：单击记录

允许 ROI 与发送点重合。

### 5.2 标定 UI 实现方案
- 使用透明全屏（或"覆盖所有屏幕"）的 Qt Overlay 捕获鼠标事件：
  - ROI：鼠标按下-拖拽-抬起形成矩形
  - 点位：点击记录坐标

**macOS  单屏实现**：
- 创建一个覆盖主屏幕的透明窗口
- 坐标记录为虚拟桌面坐标（虽然单屏，但保持虚拟桌面架构便于扩展）

### 5.3 数据结构
```text
Point { x: int, y: int }  // 虚拟桌面坐标
Rect  { x: int, y: int, w: int, h: int }
Circle{ cx: float, cy: float, r: float }
ROI   { shape: 'rect'|'circle', rect: Rect, circle?: Circle }

CalibrationConfig {
  roi: ROI,
  input_point: Point,
  send_point: Point,
  th_hold: float,
}
```

---

## 6. 截图与 ROI 裁剪

### 6.1 截图来源
- 使用 mss 抓取 **monitor=0**（全虚拟桌面）
- mss 返回 BGRA/RGB 数据；转换为 numpy array

### 6.2 ROI 裁剪
- 以虚拟桌面坐标裁剪：
  - 先获取虚拟桌面左上角偏移（vx, vy）
  - 将 ROI rect 映射到截图数组索引：
    - x0 = roi.x - vx
    - y0 = roi.y - vy

### 6.3 灰度化
- gray = (0.299*R + 0.587*G + 0.114*B)  或用向量化近似
- 输出 dtype=uint8

### 6.4 圆形 ROI mask
- 由矩形生成内切圆：
  - cx = x + w/2
  - cy = y + h/2
  - r = min(w, h)/2
- 在 ROI 局部坐标生成 mask：
  - mask[i,j] = ((j-cx_local)^2 + (i-cy_local)^2) <= r^2

---

## 7. diff 与阈值（TH_HOLD）

### 7.1 diff 默认定义
- 输入：frame_t、frame_t0（均为 ROI 灰度图）
- 输出：d ∈ [0,1]

算法：
- absdiff = abs(frame_t - frame_t0)
- 若圆形 ROI：absdiff = absdiff[mask]
- d = mean(absdiff) / 255.0

### 7.2 "保持 2 秒"的实现
- 采样频率：1 FPS（每秒一次）
- 连续命中计数：
  - if d >= TH_HOLD: hold_hits += 1 else hold_hits = 0
  - 当 hold_hits >= 2 判定通过

### 7.3 阈值校准（推荐实现细节）
触发：用户点击"校准"；SHOULD：冷却结束后按钮高亮提示。

采样：K 帧（K=5~10，默认 8），间隔可取 100~200ms（校准阶段不必 1Hz）。

噪声估计：
- 方案（实现简单、鲁棒）：
  1) 取第一帧为 ref
  2) 对后续帧计算 di = diff(frame_i, ref)
  3) noise_mu = mean(di), noise_sigma = std(di)
  4) TH_rec = clamp(noise_mu + 3*noise_sigma, 0.005, 0.2)
     - **3*sigma**：覆盖 99.7% 正常噪声（假设正态分布）
     - **0.005**：最小阈值，避免静止画面的量化噪声误判
     - **0.2**：最大阈值，避免过高阈值导致明显变化也无法检测
     - 若 mu + 3*sigma > 0.2，使用 0.2 并在日志警告"噪声异常，建议重新选择 ROI"

显示：
- UI 显示 TH_rec；用户可编辑；保存为 th_hold。
- 日志输出 mu、sigma、TH_rec 便于调试。

默认兜底：
- 未校准前 th_hold=0.02。

---

## 8. 自动化引擎（状态机与关键流程）

### 8.1 状态定义
- Idle：未运行
- Countdown：倒计时（不执行自动化）
- Sending：执行"点击输入点 → 粘贴 → 点击发送"
- Cooling：冷却 1 秒
- WaitingHold：采样 diff，等待连续 2 次命中
- Paused：冻结（保持 frame_t0 与计数器与消息快照）

### 8.2 核心变量
```text
messages: List[str]          // Start 时过滤空条目后的有效消息，锁定 N
idx: int                     // 当前消息索引 i（0-based）
frame_t0: np.ndarray|None    // 当前轮参考帧（ROI 灰度）
hold_hits: int               // 连续命中次数
th_hold: float
messages_snapshot: List[str] //  Pause 时保存，Resume 时比对

pause_event: threading.Event
stop_event: threading.Event
```

### 8.3 流程伪代码（单轮）
```text
# Start 时
messages = [m.strip() for m in messages_raw if m.strip() != ""]
N = len(messages)
messages_snapshot = None

state = Countdown
countdown(2.0)  # 倒计时

for idx in range(len(messages)):
  if stop: break

  state = Sending
  click(input_point)
  paste(messages[idx])
  click(send_point)

  state = Cooling
  sleep(1.0)

  frame_t0 = capture_roi_gray()
  hold_hits = 0

  state = WaitingHold
  while True:
    if stop: goto Idle
    if paused:
        messages_snapshot = copy(messages)  # 保存快照
        wait_until_resume()
        # Resume 时检测
        if messages != messages_snapshot:
            弹窗提示并 goto Idle
        # 未变化则继续，沿用 frame_t0 与 hold_hits

    frame_t = capture_roi_gray()
    d = diff(frame_t, frame_t0)
    if d >= th_hold: hold_hits += 1 else hold_hits = 0
    if hold_hits >= 2: break

    sleep(1.0)  // 1 FPS

goto Idle
```

### 8.4 Pause/Resume/Stop 语义
- Pause：
  - 进入 Paused
  - 冻结：状态、idx、frame_t0、hold_hits
  - 保存消息列表快照：messages_snapshot = copy(messages)
  - 自动化线程阻塞等待 resume
  - UI 禁用：标定按钮、阈值校准按钮、TH_HOLD 输入框
  - UI 允许：消息列表编辑、Stop 按钮、日志查看
- Resume：
  - 先检测：if messages != messages_snapshot: 弹窗并 Stop
  - 未变化：返回 WaitingHold（或暂停前状态），继续沿用 frame_t0 与 hold_hits
- Stop：
  - 立即设置 stop_event
  - 自动化线程在下一次检查点退出，状态回 Idle

检查点位置（必须频繁）：
- 每个 sleep 前后
- 每次点击/粘贴前后
- WaitingHold 循环每次迭代

---

## 9. 输入注入与剪贴板

### 9.1 点击
- 使用 pynput Controller：
  - move to (x,y)
  - click left

注意：
- 坐标必须是屏幕绝对坐标（虚拟桌面）。
- macOS 上输入注入依赖辅助功能权限。

### 9.2 粘贴（保留换行）
**优先策略：Qt Clipboard + 系统粘贴快捷键**
1. 将消息写入剪贴板（QGuiApplication.clipboard().setText）。
2. 发送粘贴快捷键：
   - Windows：Ctrl+V
   - macOS：Cmd+V
   - 其他平台：抛出 NotImplementedError

说明：
- 不使用逐字符输入，避免 IME/键盘布局差异。
- 多行文本由剪贴板自然保留换行。

---

## 10. UI 关键实现细节

### 10.1 Always on top
- Qt Window Flags：Qt.WindowStaysOnTopHint

### 10.2 吸附右下角（发送按钮所在屏幕）
- 算法：
  ```python
  target_screen = None
  for screen in QApplication.screens():
      if screen.geometry().contains(send_point):
          target_screen = screen
          break
  if target_screen is None:
      target_screen = QApplication.primaryScreen()  # 回退
  
  available = target_screen.availableGeometry()
  panel_pos = (available.right() - panel.width() - 12,
               available.bottom() - panel.height() - 12)
  panel.move(panel_pos)
  ```

### 10.3 倒计时 2 秒
- 状态切换到 Countdown
- UI 侧展示倒计时数值（从 2.0 递减到 0）
- 倒计时结束后状态切换到 Sending，自动化线程才启动

### 10.4 日志
- 线程安全日志队列：Worker push；UI 定时拉取刷新。
- 环形缓冲（200 条），防止无限增长。
- 包含：状态变化、i/N、diff、hold_hits、错误、完整消息内容（无需脱敏）

### 10.5 固定提示条
- 黄色背景，显示"运行中请勿操作目标窗口"
- Start 时显示（状态从 Idle 切换到 Countdown 时）
- Stop 后隐藏（状态回到 Idle 时）

---

## 11. 异常与容错策略（实现必须落地）

### 11.1 权限缺失（macOS）
- 发现未授权：
  - UI 显示缺失项（屏幕录制/辅助功能）
  - 禁用 Start
  - 提供"打开系统设置"的提示文案（可选实现一键跳转）

### 11.2 坐标与 ROI 校验
- Start 前校验：
  - ROI w/h > 0 且在虚拟桌面范围内
  - 输入点、发送点在虚拟桌面范围内
- 不通过：阻止 Start 并提示重新标定。

### 11.3 截图失败
- 重试 3 次，每次间隔 500ms
- 日志记录每次重试
- 仍失败：弹出模态对话框（见 PRD 6.2）
- 对话框按钮："重试"（重新尝试 3 次）、"查看日志"（打开日志文件或复制到剪贴板）、"关闭"（回 Idle）

### 11.4 粘贴失败/目标失焦
- 无法可靠检测"是否粘贴成功"，仅记录操作已执行。
- 若导致 ROI 永不变化，用户可 Stop；UI 在 WaitingHold 时持续显示当前 diff 和 hold_hits 以帮助诊断。

---

## 12. 可测试性与调试开关

### 12.1 运行期可观测数据
- 状态（枚举）
- idx / N
- 当前 diff 值
- hold_hits
- th_hold

### 12.2 调试模式（MUST 实现最小集）
- MUST：
  - "抓取 ROI 预览图"按钮（标定后可用，保存为 PNG 供用户确认）
  - WaitingHold 状态下每秒在日志输出 diff 值（已在 Executable Spec 要求）
- SHOULD：
  - 显示 ROI 边框预览（半透明覆盖层，非运行时）
  - 导出 diff 曲线到 CSV（调试专用）

---

## 13. 打包与发布（MVP 最小要求）

### 13.1 Windows
- PyInstaller onefile 或 onedir
- 安装/运行说明包含：
  - DPI/缩放建议（尽量固定缩放；运行中勿移动目标窗口）

### 13.2 macOS
- PyInstaller/py2app + codesign（开发阶段可先本地自签）
- README 明确：
  - **仅支持单显示器环境**
  - 首次运行需授权"屏幕录制""辅助功能"
  - 授权后可尝试 Start 测试；若仍提示权限缺失则重启应用

---

## 14. 目录结构建议（Repo Layout）
```text
app/
  main.py
  ui/
    run_panel.py
    calibration_overlay.py
    message_editor.py
    widgets.py
  core/
    engine.py          # 状态机与流程（含消息变化检测）
    capture.py         # mss 抓图与ROI裁剪
    diff.py            # diff/mask/校准
    os_adapter/
      win_dpi.py       # DPI aware 设置与智能检测
      mac_permissions.py
      input.py         # 点击/快捷键粘贴
  assets/
  tests/
    test_diff.py
    test_mask.py
    test_message_filter.py
    test_hold_hits_reset.py
README.md
```

---

## 15. 关键决策回顾（与规格对齐）
- 截图来源：全虚拟桌面 → ROI 裁剪（满足多屏，Windows；macOS 单屏）
- 坐标：虚拟桌面绝对坐标记录所有点位/ROI
- 判定：diff ≥ TH_HOLD 连续 2 次（1 FPS）即通过；中断后 hold_hits 归零
- 每条消息：冷却后重置 frame_t0
- Pause：冻结 frame_t0 与计数器，保存消息快照；Resume 检测变化
- 发送成功/失败：完全依赖 ROI 变化，不做其它兜底
- 吸附策略：发送按钮坐标所在屏幕的右下角
- 倒计时：独立 Countdown 状态，UI 显示倒计时数值

---

## 16. 未来增强（不属于 MVP）
- macOS 多显示器支持
- 目标窗口变化跟踪（窗口句柄绑定、相对坐标跟随）
- ROI 自动建议（从 UI 变化检测热点推荐 ROI）
- 超时与失败策略（可选"等待 X 秒失败并提示"）
-更强的输入可靠性（例如更稳健的粘贴重试）
