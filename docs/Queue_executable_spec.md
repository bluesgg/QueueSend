# 跨平台 ROI 变化驱动自动化工具 可执行规格

版本: v1.1-精简版  
日期: 2026-01-02

---

## 0. 本文定位

- 本规格是"可执行契约":实现必须逐条满足"必须(MUST)"条款;"建议(SHOULD)"可在不影响验收的前提下调整
- 任何未在本文定义的行为,一律不做隐式推断;实现需给出可见的错误提示或使用安全默认
- 核心前提:目标窗口运行期间不移动/不缩放/不滚动;每次运行重新标定

---

## 1. 全局常量

- `T_COUNTDOWN_SEC = 2.0`(Start后倒计时)
- `T_COOL_SEC = 1.0`(每条消息发送后冷却)
- `SAMPLE_HZ = 1.0`(ROI采样频率1 FPS)
- `HOLD_HITS_REQUIRED = 2`(连续命中次数)
- `TH_HOLD_DEFAULT = 0.02`(未校准前阈值兜底)
- `CALIB_FRAMES_K = 5..10`(阈值校准帧数区间,默认建议8)
- `CAPTURE_RETRY_N = 3`(截图失败重试次数)
- `CAPTURE_RETRY_INTERVAL_MS = 500`(截图重试间隔)

---

## 2. 坐标体系与截图来源

### 2.1 坐标
- MUST使用"虚拟桌面绝对坐标"记录:输入点input_point、发送点send_point、ROI矩形roi_rect

### 2.2 截图来源
- MUST从"整个虚拟桌面"截图并裁剪ROI
- MUST保证ROI裁剪与坐标体系一致(同一虚拟桌面空间)

### 2.3 平台特性
**Windows**:
- MUST设置Per-Monitor DPI aware(至少PMv2),防止缩放偏移
- MUST在main.py启动时(Qt初始化前)调用SetProcessDpiAwarenessContext
- MUST检查返回值和错误码;若真正失败(系统不支持,非"已设置过"情况),在主窗口显示可关闭的警告横幅(黄色背景):"⚠️ DPI感知设置失败,坐标可能偏移。建议在100%缩放下运行或重启应用"

**macOS**:
- MUST进行权限自检:屏幕录制(截图)、辅助功能(鼠标/键盘注入)
- 未授权MUST禁用Start,并显示明确引导
- MUST明确限制:**仅支持单显示器环境**,多显示器配置暂不支持(在README中说明)

---

## 3. UI与交互(运行面板)

### 3.1 窗口行为
- MUST Always on top
- MUST在Start后将运行面板吸附到**发送按钮坐标所在屏幕**的右下角:
  - 判定屏幕:遍历所有屏幕,找到包含send_point坐标的屏幕
  - 定位计算:(screen.right - panel.width - 12, screen.bottom - panel.height - 12)
  - 12为逻辑像素(Qt device-independent pixels)
  - 验收标准:面板右边距与下边距均在[10px, 14px]范围内(允许±2px容差)
- MUST在Start后显示倒计时T_COUNTDOWN_SEC,倒计时结束才开始自动化

### 3.2 显示字段
运行面板MUST显示:
- 进度:i/N(i从1开始显示;N为有效消息条数;例如第一条消息显示1/5)
- 状态(枚举):Idle | Countdown | Sending | Cooling | WaitingHold | Paused
- 控件:Pause/Resume/Stop
- 简要日志(环形缓冲,最多200条;包含:状态变化、i/N、diff、hold_hits、错误)

### 3.3 运行中用户输入
- MUST不因用户在目标应用中的键鼠操作而改变自动化逻辑
- MUST在运行面板顶部显示固定提示条(黄色背景):"运行中请勿操作目标窗口";Start时显示,Stop后隐藏

---

## 4. 标定(每次运行必须)

### 4.1 标定项
每次运行Start前MUST完成:
1. ROI(矩形或圆形)
2. 输入位置(点击点,用于抢焦点)
3. 发送按钮(点击点,单击)

### 4.2 ROI形状
- ROI MUST支持:矩形、圆形
- 圆形ROI MUST由"用户拖拽矩形"生成内切圆:cx=x+w/2, cy=y+h/2, r=min(w,h)/2
- 圆形ROI的diff计算MUST仅统计圆内像素(mask)

### 4.3 重合规则
- MUST允许ROI与发送点重合

### 4.4 Start前校验
Start前MUST校验:
- ROI的w>0 && h>0
- 输入点、发送点、ROI均在虚拟桌面范围内
- 未通过MUST阻止Start并提示"重新标定"

---

## 5. 消息输入(列表模式)

### 5.1 编辑规则
- MUST一条消息一个条目,条目支持多行
- MUST Enter=换行,不触发发送
- MUST在列表尾部自动保持一个空条目:当最后条目从空→非空时自动追加一个空条目
- MUST在运行发送时忽略空条目:
  - messages = [m for m in messages_raw if trim(m) != ""]
  - Start时过滤空条目生成有效消息列表并锁定N=len(messages);运行期间不再重新过滤

### 5.2 输入方式
- MUST通过"剪贴板粘贴"将消息写入目标输入框
- MUST保留换行(多行文本粘贴后换行结构一致)

---

## 6. 自动化流程(逐条一致)

### 6.1 处理单条消息i的步骤(MUST严格顺序)
对第i条消息(1-based显示,0-based存储):
1. 点击输入位置(抢焦点)
2. 粘贴消息i(保留换行)
3. 单击发送按钮
4. 冷却T_COOL_SEC
5. 冷却结束抓取ROI帧作为参考:frame_t0(每条消息都会重置)
6. 进入WaitingHold:每秒采样1次,计算diff(frame_t, frame_t0)
7. 若diff>=TH_HOLD连续命中HOLD_HITS_REQUIRED次→判定通过,进入下一条i+1
8. 若未满足,持续等待(无限等待;靠Pause/Stop控制)

### 6.2 发送失败处理
- MUST不做任何除ROI判定之外的失败判断或重试
- MUST在UI/日志中提醒:ROI需要与"发送后状态变化"强相关

---

## 7. 变化检测(diff与阈值)

### 7.1 diff定义(默认且必须实现)
输入:frame_t0(参考帧),frame_t(当前帧),均为ROI灰度图

步骤:
1. ROI转灰度(uint8)
2. absdiff = abs(frame_t - frame_t0)
3. 圆形ROI:仅统计mask内像素
4. d = mean(absdiff) / 255.0,范围[0,1]

输出:d(float)

### 7.2 HOLD口径
- MUST在SAMPLE_HZ=1下以"连续2次命中"作为"保持2秒"的判定
- 若diff<TH_HOLD,MUST将hold_hits归零重新计数

---

## 8. TH_HOLD阈值策略(校准按钮)

### 8.1 校准触发
- MUST提供"校准按钮"
- 校准可在以下时机触发:用户手动点击"校准"、SHOULD:冷却结束后校准按钮高亮提示(非强制弹出)

### 8.2 校准采样
- MUST采集K帧(K∈[5,10],默认建议8)
- SHOULD采样间隔100–200ms

### 8.3 噪声估计与推荐阈值(必须可复现)
MUST使用以下推荐算法(或等价且在日志中注明):
1. 取第一帧为ref
2. 对后续帧计算di = diff(frame_i, ref)
3. 计算mu = mean(di), sigma = std(di)
4. TH_rec = clamp(mu + 3*sigma, 0.005, 0.2)
   - 3*sigma:覆盖99.7%正常噪声(假设正态分布)
   - 0.005:最小阈值,避免静止画面的量化噪声误判
   - 0.2:最大阈值,避免过高阈值导致明显变化也无法检测
   - 若mu+3*sigma>0.2,使用0.2并在日志警告"噪声异常,建议重新选择ROI"
- MUST在UI显示TH_rec作为推荐值
- MUST允许用户手动修改TH_HOLD,并以用户值为准

### 8.4 未校准兜底
- MUST在未校准时使用TH_HOLD_DEFAULT=0.02

---

## 9. 状态机(必须实现的行为约束)

### 9.1 状态枚举
- Idle(未运行)
- Countdown(倒计时阶段,不执行自动化)
- Sending(执行点击/粘贴/发送)
- Cooling(冷却等待)
- WaitingHold(等待ROI变化满足条件)
- Paused(暂停)

### 9.2 状态可见性
- MUST在运行面板显示当前状态

### 9.3 状态转移与动作(规范化表)

**事件**:
- EV_START(用户点击Start)
- EV_COUNTDOWN_DONE(倒计时结束)
- EV_SENT_STEP_DONE(Sending三步完成)
- EV_COOL_DONE(冷却完成)
- EV_HOLD_PASS(连续命中达标)
- EV_PAUSE(用户点击Pause)
- EV_RESUME(用户点击Resume)
- EV_STOP(用户点击Stop)
- EV_ERROR_FATAL(不可恢复错误,如权限缺失、连续截图失败)
- EV_MSG_LIST_CHANGED(Resume时检测到消息列表变化)

**转移规则(MUST)**:
1. Idle + EV_START →(校验通过后)吸附右下角 → Countdown
2. Countdown等待T_COUNTDOWN_SEC完成 → 触发EV_COUNTDOWN_DONE → Sending(i=0,第一条消息)
3. Sending完成点击/粘贴/点击后 → Cooling
4. Cooling等待T_COOL_SEC完成 →(抓取frame_t0,hold_hits=0)→ WaitingHold
5. WaitingHold:每秒采样diff;当连续命中达标触发EV_HOLD_PASS:若还有下一条消息→Sending(i+1);若无下一条消息→Idle
6. 任意非Idle/Countdown状态 + EV_PAUSE → Paused
7. Paused + EV_RESUME →(先检测消息列表变化):若消息列表未变化:返回暂停前状态,继续沿用同一个frame_t0与hold_hits;若消息列表已变化:触发EV_MSG_LIST_CHANGED → EV_STOP,弹窗提示"检测到消息列表已修改,自动化已停止,请重新Start",回到Idle
8. 任意状态 + EV_STOP → 立即进入Idle(停止自动化)
9. 任意状态 + EV_ERROR_FATAL → Idle并提示错误

---

## 10. Pause/Resume/Stop精确定义

### 10.1 Pause
MUST冻结:当前状态、当前消息索引i、frame_t0、hold_hits、当前消息列表快照(用于Resume时检测变化)
MUST停止采样与自动点击/粘贴动作
MUST在Paused状态下禁用UI控件(灰化):标定按钮、阈值校准按钮、TH_HOLD手动输入框
MUST允许:消息列表编辑(但Resume时会检测变化)、Stop按钮、日志查看

### 10.2 Resume
- MUST先检测消息列表是否变化(与Pause时的快照比对)
- 若未变化:MUST恢复到Pause前的状态;MUST继续使用同一个frame_t0与hold_hits
- 若已变化:MUST触发Stop行为(回到Idle);MUST弹出提示对话框:"检测到消息列表已修改,自动化已停止。若需继续,请重新Start。"

### 10.3 Stop
- MUST立即停止自动化并回到Idle
- MUST不再执行任何后续点击/粘贴/采样

---

## 11. 错误处理(最小集合)

### 11.1 macOS权限缺失
- MUST在UI启动自检并列出缺失项
- MUST禁用Start

### 11.2 截图失败
- MUST重试CAPTURE_RETRY_N=3次,每次间隔CAPTURE_RETRY_INTERVAL_MS=500ms
- 仍失败MUST触发EV_ERROR_FATAL,回Idle并弹出模态对话框:
  - 标题:"无法获取屏幕截图"
  - 内容:"已重试3次失败 / 可能原因:macOS权限被撤销/Windows DPI设置异常/显示器配置变化 / 建议操作:检查权限设置、重启应用、重新标定"
  - 按钮:"重试"(重新尝试3次)、"查看日志"(打开日志文件或复制到剪贴板)、"关闭"(回到Idle)

### 11.3 坐标越界
- MUST在Start前检测并阻止

### 11.4 运行中用户干预
- MUST不改变逻辑;仅提示"不要操作"(固定提示条)

---

## 12. 日志与可观测性(必须最低实现)

MUST输出并显示:
- 状态变化(Idle→Countdown→Sending→Cooling→WaitingHold→Paused→…),含时间戳
- 当前消息i/N(1-based显示)
- WaitingHold下每秒的diff与hold_hits(格式如:"[10:30:15] diff=0.025, hold_hits=1")
- 关键错误(权限、截图失败、坐标越界、消息列表变化)
- 完整消息内容(调试用,无需脱敏)
- 使用环形缓冲限制条数(默认200)

---

## 13. 验收用最小检查表(必须全部满足)

1. Start后:吸附到发送按钮坐标所在屏幕的右下角(边距12±2px逻辑像素)+状态显示Countdown+倒计时从2.0递减到0+倒计时结束状态切换到Sending。日志显示Start时间戳T0,第一次点击输入点时间戳T1,T1-T0应在[1.9, 2.1]秒范围内
2. 每条消息严格执行:点击输入点→粘贴→点击发送→冷却1秒→采集frame_t0→1Hz采样diff
3. diff≥TH_HOLD连续命中2次才推进;中断后hold_hits归零重新计数
4. 未命中无限等待,直到命中或Stop
5. Pause冻结frame_t0与hold_hits;Resume检测消息列表变化,未变化则沿用frame_t0,已变化则停止并提示
6. Stop立即回Idle
7. ROI:矩形/圆形;圆形为内切圆并启用mask
8. 消息列表:Enter换行;尾部空条目自动补;Start时过滤空条目并锁定N;多行粘贴保留换行
9. Windows:DPI aware设置,失败时显示警告横幅
10. macOS:权限自检,未授权禁用Start;仅支持单显示器

---

## 14. 允许实现差异(显式许可)

- 吸附右下角的边距可在[10px, 14px]范围内调整(默认12px),但必须在验收文档中明确说明
- 校准算法可等价替代,但必须可解释、可复现,并在日志中打印推荐阈值与关键统计量(mu、sigma、TH_rec)
- 截图失败重试间隔可在[300ms, 1000ms]范围内调整(默认500ms)
