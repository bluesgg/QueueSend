# 跨平台 ROI 变化驱动自动化工具 TDD

版本: v1.1-精简版  
日期: 2026-01-02

---

## 1. 技术选型

**推荐路线**: Python 3.11+ + PySide6

- UI: PySide6(Qt 6)
- 屏幕捕获: mss(全虚拟桌面截图)
- 图像处理: numpy(灰度/diff/mask)
- 输入注入: pynput(点击/粘贴快捷键)
- 剪贴板: Qt Clipboard或pyperclip
- Windows DPI: ctypes调用SetProcessDpiAwarenessContext
- macOS权限: pyobjc访问Quartz/ApplicationServices(CGPreflightScreenCaptureAccess, AXIsProcessTrustedWithOptions)
- 打包: PyInstaller(Windows/macOS)

---

## 2. 架构

### 2.1 模块划分
1. **UI Shell(Qt)**: 运行面板(Always on top、吸附、倒计时)、消息列表编辑器、标定向导、阈值校准UI、日志展示、固定提示条
2. **Automation Engine**: 状态机(Idle/Countdown/Sending/Cooling/WaitingHold/Paused)、消息队列i/N、Pause/Resume/Stop、消息列表变化检测
3. **Capture & Diff**: 虚拟桌面截图、ROI裁剪/灰度化、圆形ROI mask、diff计算与连续命中逻辑(hold_hits重置)、校准采样与TH_HOLD推荐
4. **OS Adapter**: 坐标体系(虚拟桌面)、DPI/缩放处理(Windows智能检测)、权限检测(macOS)、输入注入

### 2.2 线程模型
- **UI线程**: 所有Qt UI操作
- **自动化线程(Worker)**: 执行点击/粘贴/冷却/采样/等待
- 通讯: Qt Signals/Slots或线程安全队列+信号
- Pause/Stop使用原子标志(threading.Event)保证即时生效

---

## 3. 坐标体系与平台适配

### 3.1 坐标
- 虚拟桌面绝对坐标记录ROI、输入点、发送点
- 原点为虚拟桌面左上角(可能为负值)

### 3.2 Windows DPI
- 目标: 避免系统缩放导致坐标偏移
- Qt初始化前调用SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
- 智能检测:
```python
result = SetProcessDpiAwarenessContext(...)
if not result:
    error_code = GetLastError()
    if error_code == ERROR_ACCESS_DENIED:  # 已设置过,正常
        pass
    else:  # 真正失败
        显示警告横幅
```

### 3.3 macOS权限
- 屏幕录制权限(截图)、辅助功能权限(点击/键盘注入)
- 启动自检,显示缺失项,禁用Start
- **单显示器限制**: 仅支持单显示器,在README说明

---

## 4. 标定

### 4.1 流程
1. 选择ROI: 拖拽矩形(虚拟桌面坐标)
2. 选择ROI形状: 矩形/圆形(圆形由矩形生成内切圆)
3. 选择输入点、发送点: 单击记录

允许ROI与发送点重合。

### 4.2 数据结构
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

## 5. 截图与ROI

### 5.1 截图来源
- mss抓取monitor=0(全虚拟桌面)
- 转换为numpy array

### 5.2 ROI裁剪
以虚拟桌面坐标裁剪:
- 获取虚拟桌面左上角偏移(vx, vy)
- ROI映射到截图数组: x0=roi.x-vx, y0=roi.y-vy

### 5.3 灰度化
- gray = 0.299*R + 0.587*G + 0.114*B
- 输出dtype=uint8

### 5.4 圆形ROI mask
- 由矩形生成内切圆: cx=x+w/2, cy=y+h/2, r=min(w,h)/2
- mask[i,j] = ((j-cx_local)^2 + (i-cy_local)^2) <= r^2

---

## 6. diff与阈值

### 6.1 diff定义
- 输入: frame_t、frame_t0(均为ROI灰度图)
- 输出: d ∈ [0,1]
- 算法:
  - absdiff = abs(frame_t - frame_t0)
  - 若圆形ROI: absdiff = absdiff[mask]
  - d = mean(absdiff) / 255.0

### 6.2 "保持2秒"实现
- 采样频率: 1 FPS
- 连续命中计数: if d>=TH_HOLD: hold_hits+=1 else hold_hits=0
- 当hold_hits>=2判定通过

### 6.3 阈值校准
- 触发: 用户点击"校准"或冷却后按钮高亮提示
- 采样: K帧(K=5~10,默认8),间隔100~200ms
- 噪声估计:
  1. 取第一帧为ref
  2. 对后续帧计算di = diff(frame_i, ref)
  3. noise_mu = mean(di), noise_sigma = std(di)
  4. TH_rec = clamp(mu+3*sigma, 0.005, 0.2)
     - 3*sigma: 覆盖99.7%正常噪声
     - 0.005: 最小阈值,避免量化噪声误判
     - 0.2: 最大阈值,避免过高阈值漏检
     - 若mu+3*sigma>0.2,使用0.2并日志警告"噪声异常,建议重新选择ROI"
- UI显示TH_rec并允许手动修改
- 默认兜底: th_hold=0.02

---

## 7. 自动化引擎

### 7.1 状态定义
- Idle: 未运行
- Countdown: 倒计时(不执行自动化)
- Sending: 执行"点击输入点→粘贴→点击发送"
- Cooling: 冷却1秒
- WaitingHold: 采样diff,等待连续2次命中
- Paused: 冻结(保持frame_t0与计数器与消息快照)

### 7.2 核心变量
```text
messages: List[str]          // Start时过滤空条目后的有效消息,锁定N
idx: int                     // 当前消息索引i(0-based)
frame_t0: np.ndarray|None    // 当前轮参考帧(ROI灰度)
hold_hits: int               // 连续命中次数
th_hold: float
messages_snapshot: List[str] // Pause时保存,Resume时比对

pause_event: threading.Event
stop_event: threading.Event
```

### 7.3 流程伪代码
```text
# Start时
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
        # Resume时检测
        if messages != messages_snapshot:
            弹窗提示并goto Idle
        # 未变化则继续,沿用frame_t0与hold_hits

    frame_t = capture_roi_gray()
    d = diff(frame_t, frame_t0)
    if d >= th_hold: hold_hits += 1 else hold_hits = 0
    if hold_hits >= 2: break

    sleep(1.0)  // 1 FPS

goto Idle
```

### 7.4 Pause/Resume/Stop语义
**Pause**:
- 进入Paused
- 冻结: 状态、idx、frame_t0、hold_hits
- 保存消息列表快照: messages_snapshot = copy(messages)
- UI禁用: 标定按钮、阈值校准按钮、TH_HOLD输入框
- UI允许: 消息列表编辑、Stop按钮、日志查看

**Resume**:
- 检测: if messages != messages_snapshot: 弹窗并Stop
- 未变化: 返回WaitingHold(或暂停前状态),继续沿用frame_t0与hold_hits

**Stop**:
- 立即设置stop_event
- 自动化线程在检查点退出,状态回Idle

---

## 8. 输入注入与剪贴板

### 8.1 点击
- pynput Controller: move to (x,y) + click left
- 坐标为虚拟桌面绝对坐标
- macOS依赖辅助功能权限

### 8.2 粘贴(保留换行)
- 优先策略: Qt Clipboard + 系统粘贴快捷键
  1. 将消息写入剪贴板(QGuiApplication.clipboard().setText)
  2. 发送粘贴快捷键: Windows Ctrl+V, macOS Cmd+V

---

## 9. UI关键实现

### 9.1 Always on top
- Qt Window Flags: Qt.WindowStaysOnTopHint

### 9.2 吸附右下角(发送按钮所在屏幕)
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

### 9.3 倒计时2秒
- 状态切换到Countdown
- UI展示倒计时数值(从2.0递减到0)
- 倒计时结束状态切换到Sending,自动化线程启动

### 9.4 日志
- 线程安全日志队列: Worker push, UI定时拉取刷新
- 环形缓冲200条,防止无限增长
- 包含: 状态变化、i/N、diff、hold_hits、错误、完整消息内容

### 9.5 固定提示条
- 黄色背景,显示"运行中请勿操作目标窗口"
- Start时显示(状态从Idle切换到Countdown时)
- Stop后隐藏(状态回到Idle时)

---

## 10. 异常与容错

### 10.1 权限缺失(macOS)
- UI显示缺失项(屏幕录制/辅助功能)
- 禁用Start
- 提供"打开系统设置"提示文案

### 10.2 坐标与ROI校验
- Start前校验: ROI w/h>0且在虚拟桌面范围内, 输入点/发送点在虚拟桌面范围内
- 不通过: 阻止Start并提示重新标定

### 10.3 截图失败
- 重试3次,每次间隔500ms
- 日志记录每次重试
- 仍失败: 弹出模态对话框,按钮"重试"/"查看日志"/"关闭"(回Idle)

### 10.4 粘贴失败/目标失焦
- 无法可靠检测是否粘贴成功,仅记录操作已执行
- 若导致ROI永不变化,用户可Stop; UI在WaitingHold时持续显示diff和hold_hits帮助诊断

---

## 11. 可测试性与调试开关

### 11.1 运行期可观测数据
- 状态(枚举)、idx/N、当前diff值、hold_hits、th_hold

### 11.2 调试模式(MUST最小集)
- MUST:
  - "抓取ROI预览图"按钮(标定后可用,保存为PNG供确认)
  - WaitingHold状态下每秒在日志输出diff值
- SHOULD:
  - 显示ROI边框预览(半透明覆盖层,非运行时)
  - 导出diff曲线到CSV

---

## 12. 打包与发布(MVP最小要求)

### 12.1 Windows
- PyInstaller onefile或onedir
- 安装/运行说明: DPI/缩放建议(尽量固定缩放;运行中勿移动目标窗口)

### 12.2 macOS
- PyInstaller/py2app + codesign(开发阶段可本地自签)
- README明确:
  - **仅支持单显示器环境**
  - 首次运行需授权"屏幕录制""辅助功能"
  - 授权后可尝试Start测试;若仍提示权限缺失则重启应用

---

## 13. 目录结构建议

```text
repo/
  pyproject.toml
  README.md
  app/
    main.py
    ui/
      run_panel.py
      calibration_overlay.py
      message_editor.py
      widgets.py
    core/
      engine.py          # 状态机与流程(含消息变化检测)
      capture.py         # mss抓图与ROI裁剪
      diff.py            # diff/mask/校准
      os_adapter/
        win_dpi.py       # DPI aware设置与智能检测
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

## 14. 关键决策回顾

- 截图来源: 全虚拟桌面→ROI裁剪(满足多屏Windows;macOS单屏)
- 坐标: 虚拟桌面绝对坐标记录所有点位/ROI
- 判定: diff≥TH_HOLD连续2次(1 FPS)即通过;中断后hold_hits归零
- 每条消息: 冷却后重置frame_t0
- Pause: 冻结frame_t0与计数器,保存消息快照;Resume检测变化
- 发送成功/失败: 完全依赖ROI变化,不做其它兜底
- 吸附策略: 发送按钮坐标所在屏幕的右下角
- 倒计时: 独立Countdown状态,UI显示倒计时数值
