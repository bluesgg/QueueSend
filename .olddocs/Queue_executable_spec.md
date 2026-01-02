# 跨平台 ROI 变化驱动自动化工具（Windows / macOS）可执行规格（Executable Spec）

版本：v1.1（根据可交付性审查反馈修订）  
日期：2026-01-01

---

## 0. 本文定位与约束
- 本规格是"可执行契约"：实现必须逐条满足"必须（MUST）"条款；"建议（SHOULD）"可在不影响验收的前提下调整。
- 任何未在本文定义的行为，一律不做隐式推断；实现需给出可见的错误提示或使用安全默认。
- 核心前提：目标窗口运行期间不移动/不缩放/不滚动；每次运行重新标定。

---

## 1. 平台与目标应用

### 1.1 平台
- MUST 支持：Windows、macOS

### 1.2 目标应用（被操作窗口）
- MUST 能操作：浏览器、Cursor、VS Code、antigravity
- MUST 以"屏幕坐标 + 输入注入"方式操作；不得依赖目标应用内部 API。

---

## 2. 全局时间与常量
- `T_COUNTDOWN_SEC = 2.0`（Start 后倒计时）
- `T_COOL_SEC = 1.0`（每条消息发送后冷却）
- `SAMPLE_HZ = 1.0`（ROI 采样频率 1 FPS）
- `HOLD_HITS_REQUIRED = 2`（连续命中次数）
- `TH_HOLD_DEFAULT = 0.02`（未校准前阈值兜底）
- `CALIB_FRAMES_K = 5..10`（阈值校准帧数区间，默认建议 8）
- `CAPTURE_RETRY_N = 3`（截图失败重试次数）
- `CAPTURE_RETRY_INTERVAL_MS = 500`（截图重试间隔）

---

## 3. 坐标体系与截图来源

### 3.1 坐标
- MUST 使用"虚拟桌面绝对坐标"记录以下实体：
  - 输入点 `input_point`
  - 发送点 `send_point`
  - ROI 矩形 `roi_rect`

### 3.2 截图来源
- MUST 从"整个虚拟桌面"截图并裁剪 ROI。
- MUST 保证 ROI 裁剪与坐标体系一致（同一虚拟桌面空间）。

### 3.3 平台特性
- Windows：MUST 设置 Per-Monitor DPI aware（至少 PMv2），防止缩放偏移。
  - MUST 在 main.py 启动时（Qt 初始化前）调用 SetProcessDpiAwarenessContext
  - MUST 检查返回值和错误码；若真正失败（系统不支持，非"已设置过"情况），在主窗口显示可关闭的警告横幅（黄色背景）：
    "⚠️ DPI 感知设置失败，坐标可能偏移。建议在 100% 缩放下运行或重启应用"
  - 横幅每次启动显示直到设置成功
- macOS：MUST 进行权限自检：
  - 屏幕录制（用于截图）
  - 辅助功能（用于鼠标/键盘注入）
  - 未授权 MUST 禁用 Start，并显示明确引导。
  - MUST 明确限制：**仅支持单显示器环境**，多显示器配置暂不支持（在 README 中说明）

---

## 4. UI 与交互（运行面板）

### 4.1 窗口行为
- MUST Always on top。
- MUST 在 Start 后将运行面板吸附到**发送按钮坐标所在屏幕**的右下角：
  - 判定屏幕：遍历所有屏幕，找到包含 `send_point` 坐标的屏幕
  - 定位计算：`(screen.right - panel.width - 12, screen.bottom - panel.height - 12)`
  - 12 为逻辑像素（Qt device-independent pixels）
  - 验收标准：面板右边距与下边距均在 [10px, 14px] 范围内（允许 ±2px 容差）
- MUST 在 Start 后显示倒计时 `T_COUNTDOWN_SEC`，倒计时结束才开始自动化。

### 4.2 显示字段
运行面板 MUST 显示：
- 进度：`i/N`（i 从 1 开始显示；N 为有效消息条数；例如第一条消息显示 1/5）
- 状态（枚举）：`Idle | Countdown | Sending | Cooling | WaitingHold | Paused`
- 控件：`Pause/Resume/Stop`
- 简要日志（环形缓冲，最多 200 条；旧条目自动删除；至少包含：状态变化、i/N、diff、hold_hits、错误）

### 4.3 运行中用户输入
- MUST 不因用户在目标应用中的键鼠操作而改变自动化逻辑（即"不干预"）。
- MUST 在运行面板顶部显示固定提示条（黄色背景）："运行中请勿操作目标窗口"；Start 时显示，Stop 后隐藏。

---

## 5. 标定（每次运行必须）

### 5.1 标定项
每次运行 Start 前 MUST 完成：
1. ROI（矩形或圆形）
2. 输入位置（点击点，用于抢焦点）
3. 发送按钮（点击点，单击）

### 5.2 ROI 形状
- ROI MUST 支持：矩形、圆形。
- 圆形 ROI MUST 由"用户拖拽矩形"生成内切圆：
  - `cx = x + w/2`，`cy = y + h/2`
  - `r = min(w, h)/2`
- 圆形 ROI 的 diff 计算 MUST 仅统计圆内像素（mask）。

### 5.3 重合规则
- MUST 允许 ROI 与发送点重合。

### 5.4 Start 前校验
Start 前 MUST 校验：
- ROI 的 `w>0 && h>0`
- 输入点、发送点、ROI 均在虚拟桌面范围内
- 未通过 MUST 阻止 Start 并提示"重新标定"。

---

## 6. 消息输入（列表模式）

### 6.1 数据结构
- 消息以"条目列表"存在：`messages_raw: List[str]`。

### 6.2 编辑规则
- MUST 一条消息一个条目，条目支持多行。
- MUST `Enter = 换行`，不触发发送。
- MUST 在列表尾部自动保持一个空条目：当最后条目从空→非空时自动追加一个空条目。
- MUST 在运行发送时忽略空条目：
  - `messages = [m for m in messages_raw if trim(m) != ""]`
  - Start 时过滤空条目生成有效消息列表并锁定 `N = len(messages)`；运行期间不再重新过滤

### 6.3 输入方式
- MUST 通过"剪贴板粘贴"将消息写入目标输入框。
- MUST 保留换行（多行文本粘贴后换行结构一致）。

---

## 7. 自动化流程（逐条一致）

### 7.1 处理单条消息 i 的步骤（MUST 严格顺序）
对第 `i` 条消息（1-based 显示，0-based 存储）：
1. 点击输入位置（抢焦点）
2. 粘贴消息 i（保留换行）
3. 单击发送按钮
4. 冷却 `T_COOL_SEC`
5. 冷却结束抓取 ROI 帧作为参考：`frame_t0`（每条消息都会重置）
6. 进入 WaitingHold：每秒采样 1 次，计算 `diff(frame_t, frame_t0)`
7. 若 `diff >= TH_HOLD` 连续命中 `HOLD_HITS_REQUIRED` 次
   - 判定通过，进入下一条 i+1
8. 若未满足，持续等待（无限等待；靠 Pause/Stop 控制）

### 7.2 发送失败处理
- MUST 不做任何除 ROI 判定之外的失败判断或重试。
- MUST 在 UI/日志中提醒：ROI 需要与"发送后状态变化"强相关。

---

## 8. 变化检测（diff 与阈值）

### 8.1 diff 定义（默认且必须实现）
输入：
- `frame_t0`：参考帧（ROI 灰度）
- `frame_t`：当前帧（ROI 灰度）

步骤：
1. ROI 转灰度（uint8）
2. `absdiff = abs(frame_t - frame_t0)`
3. 圆形 ROI：仅统计 mask 内像素
4. `d = mean(absdiff) / 255.0`，范围 [0,1]

输出：`d`（float）

### 8.2 HOLD 口径
- MUST 在 `SAMPLE_HZ=1` 下以"连续 2 次命中"作为"保持 2 秒"的判定。
- 若 `diff < TH_HOLD`，MUST 将 `hold_hits` 归零重新计数。

---

## 9. TH_HOLD 阈值策略（校准按钮）

### 9.1 校准触发
- MUST 提供"校准按钮"。
- 校准可在以下时机触发：
  - 用户手动点击"校准"
  - SHOULD：冷却结束后校准按钮高亮提示（非强制弹出）

### 9.2 校准采样
- MUST 采集 `K` 帧（K ∈ [5,10]，默认建议 8）。
- SHOULD 采样间隔 100–200ms（校准阶段不要求 1Hz）。

### 9.3 噪声估计与推荐阈值（必须可复现）
- MUST 使用以下推荐算法（或等价且在日志中注明）：
  1) 取第一帧为 `ref`
  2) 对后续帧计算 `di = diff(frame_i, ref)`
  3) 计算 `mu = mean(di)`，`sigma = std(di)`
  4) `TH_rec = clamp(mu + 3*sigma, 0.005, 0.2)`
     - 3*sigma：覆盖 99.7% 正常噪声（假设正态分布）
     - 0.005：最小阈值，避免静止画面的量化噪声误判
     - 0.2：最大阈值，避免过高阈值导致明显变化也无法检测
     - 若 mu + 3*sigma > 0.2，使用 0.2 并在日志警告"噪声异常，建议重新选择 ROI"
- MUST 在 UI 显示 `TH_rec` 作为推荐值。
- MUST 允许用户手动修改 TH_HOLD，并以用户值为准。

### 9.4 未校准兜底
- MUST 在未校准时使用 `TH_HOLD_DEFAULT=0.02`。

---

## 10. 状态机（必须实现的行为约束）

### 10.1 状态枚举
- `Idle`（未运行）
- `Countdown`（倒计时阶段，不执行自动化）
- `Sending`（执行点击/粘贴/发送）
- `Cooling`（冷却等待）
- `WaitingHold`（等待 ROI 变化满足条件）
- `Paused`（暂停）

### 10.2 状态可见性
- MUST 在运行面板显示当前状态。

### 10.3 状态转移与动作（规范化表）

#### 10.3.1 事件
- `EV_START`（用户点击 Start）
- `EV_COUNTDOWN_DONE`（倒计时结束）
- `EV_SENT_STEP_DONE`（Sending 三步完成）
- `EV_COOL_DONE`（冷却完成）
- `EV_HOLD_PASS`（连续命中达标）
- `EV_PAUSE`（用户点击 Pause）
- `EV_RESUME`（用户点击 Resume）
- `EV_STOP`（用户点击 Stop）
- `EV_ERROR_FATAL`（不可恢复错误，如权限缺失、连续截图失败）
- `EV_MSG_LIST_CHANGED`（Resume 时检测到消息列表变化）

#### 10.3.2 转移规则（MUST）
1. `Idle` + `EV_START` →（校验通过后）吸附右下角 → `Countdown`
2. `Countdown` 等待 `T_COUNTDOWN_SEC` 完成 → 触发 `EV_COUNTDOWN_DONE` → `Sending`（i=0，第一条消息）
3. `Sending` 完成点击/粘贴/点击后 → `Cooling`
4. `Cooling` 等待 `T_COOL_SEC` 完成 →（抓取 frame_t0，hold_hits=0）→ `WaitingHold`
5. `WaitingHold`：每秒采样 diff；当连续命中达标触发 `EV_HOLD_PASS`：
   - 若还有下一条消息 → `Sending`（i+1）
   - 若无下一条消息 → `Idle`
6. 任意非 Idle/Countdown 状态 + `EV_PAUSE` → `Paused`
7. `Paused` + `EV_RESUME` →（先检测消息列表变化）：
   - 若消息列表未变化：返回暂停前状态，继续沿用同一个 frame_t0 与 hold_hits
   - 若消息列表已变化：触发 `EV_MSG_LIST_CHANGED` → `EV_STOP`，弹窗提示"检测到消息列表已修改，自动化已停止，请重新 Start"，回到 `Idle`
8. 任意状态 + `EV_STOP` → 立即进入 `Idle`（停止自动化）
9. 任意状态 + `EV_ERROR_FATAL` → `Idle` 并提示错误

---

## 11. Pause/Resume/Stop 精确定义（必须遵守）

### 11.1 Pause
- MUST 冻结：
  - 当前状态
  - 当前消息索引 i
  - `frame_t0`
  - `hold_hits`
  - 当前消息列表快照（用于 Resume 时检测变化）
- MUST 停止采样与自动点击/粘贴动作。
- MUST 在 Paused 状态下禁用以下 UI 控件（灰化）：
  - 标定按钮（ROI/输入点/发送点）
  - 阈值校准按钮
  - TH_HOLD 手动输入框
- MUST 允许：
  - 消息列表编辑（但 Resume 时会检测变化）
  - Stop 按钮
  - 日志查看

### 11.2 Resume
- MUST 先检测消息列表是否变化（与 Pause 时的快照比对）。
- 若未变化：
  - MUST 恢复到 Pause 前的状态
  - MUST 继续使用同一个 `frame_t0` 与 `hold_hits`
- 若已变化：
  - MUST 触发 Stop 行为（回到 Idle）
  - MUST 弹出提示对话框："检测到消息列表已修改，自动化已停止。若需继续，请重新 Start。"

### 11.3 Stop
- MUST 立即停止自动化并回到 `Idle`。
- MUST 不再执行任何后续点击/粘贴/采样。

---

## 12. 错误处理（最小集合）

### 12.1 macOS 权限缺失
- MUST 在 UI 启动自检并列出缺失项。
- MUST 禁用 Start。

### 12.2 截图失败
- MUST 重试 `CAPTURE_RETRY_N = 3` 次，每次间隔 `CAPTURE_RETRY_INTERVAL_MS = 500ms`。
- 仍失败 MUST 触发 `EV_ERROR_FATAL`，回 Idle 并弹出模态对话框：
  - 标题："无法获取屏幕截图"
  - 内容：
    * "已重试 3 次失败"
    * "可能原因：macOS 权限被撤销 / Windows DPI 设置异常 / 显示器配置变化"
    * "建议操作：检查权限设置、重启应用、重新标定"
  - 按钮："重试"（重新尝试 3 次）、"查看日志"（打开日志文件或复制到剪贴板）、"关闭"（回到 Idle）

### 12.3 坐标越界
- MUST 在 Start 前检测并阻止。

### 12.4 运行中用户干预
- MUST 不改变逻辑；仅提示"不要操作"（固定提示条）。

---

## 13. 日志与可观测性（必须最低实现）
- MUST 输出并显示：
  - 状态变化（Idle→Countdown→Sending→Cooling→WaitingHold→Paused→…），含时间戳
  - 当前消息 i/N（1-based 显示）
  - WaitingHold 下每秒的 `diff` 与 `hold_hits`（格式如："[10:30:15] diff=0.025, hold_hits=1"）
  - 关键错误（权限、截图失败、坐标越界、消息列表变化）
  - 完整消息内容（调试用，无需脱敏）
- MUST 使用环形缓冲限制条数（默认 200，实现可通过配置调整）。

---

## 14. 验收用最小检查表（必须全部满足）
1. Start 后：吸附到发送按钮坐标所在屏幕的右下角（边距 12±2px 逻辑像素）+ 状态显示 Countdown + 倒计时从 2.0 递减到 0 + 倒计时结束状态切换到 Sending。日志显示 Start 时间戳 T0，第一次点击输入点时间戳 T1，T1-T0 应在 [1.9, 2.1] 秒范围内。
2. 每条消息严格执行：点击输入点→粘贴→点击发送→冷却 1 秒→采集 frame_t0→1Hz 采样 diff。
3. diff≥TH_HOLD 连续命中 2 次才推进；中断后 hold_hits 归零重新计数。
4. 未命中无限等待，直到命中或 Stop。
5. Pause 冻结 frame_t0 与 hold_hits；Resume 检测消息列表变化，未变化则沿用 frame_t0，已变化则停止并提示。
6. Stop 立即回 Idle。
7. ROI：矩形/圆形；圆形为内切圆并启用 mask。
8. 消息列表：Enter 换行；尾部空条目自动补；Start 时过滤空条目并锁定 N；多行粘贴保留换行。
9. Windows：DPI aware 设置，失败时显示警告横幅。
10. macOS：权限自检，未授权禁用 Start；仅支持单显示器。

---

## 15. 允许实现差异（显式许可）
- 吸附右下角的边距可在 [10px, 14px] 范围内调整（默认 12px），但必须在验收文档中明确说明。
- 校准算法可等价替代，但必须可解释、可复现，并在日志中打印推荐阈值与关键统计量（mu、sigma、TH_rec）。
- 截图失败重试间隔可在 [300ms, 1000ms] 范围内调整（默认 500ms）。
