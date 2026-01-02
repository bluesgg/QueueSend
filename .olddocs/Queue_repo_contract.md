# 跨平台 ROI 变化驱动自动化工具（Windows / macOS）开发约束与交付清单（Repo Contract）

版本：v1.1（根据可交付性审查反馈修订）  
日期：2026-01-01

---

## 1. 适用范围
- 本 Repo Contract 约束代码仓库结构、工程规范、构建与打包方式、最小测试与交付产物。
- 本 Contract 默认采用技术路线：**Python 3.11+ + PySide6（Qt6）**，并与《TDD》保持一致。
- 若替换技术栈（如 Tauri/Electron），仍应保留本文件的"交付清单、运行/构建命令、测试与可观测性、跨平台注意事项"的等价内容。

---

## 2. 技术栈与版本约束（MUST）

### 2.1 语言与运行时
- MUST：Python >= 3.11
- SHOULD：固定在 .python-version / uv / pyenv 中，确保一致性。

### 2.2 主要依赖
- MUST：PySide6（UI）
- MUST：mss（全虚拟桌面截图）
- MUST：numpy（灰度/diff/mask）
- MUST：pynput（鼠标点击与粘贴快捷键注入）
- macOS ONLY MUST：pyobjc（权限检测：ScreenCapture/Accessibility）

### 2.3 依赖管理
- MUST：使用 `pyproject.toml` 统一依赖声明（推荐 Poetry / uv / pip-tools 任一；实现需二选一并写入 README）。
- MUST：提供 `requirements.lock` 或等价锁文件（可复现安装）。

---

## 3. 仓库目录结构（MUST）
实现 MUST 遵循如下结构（允许在不破坏职责边界前提下增补）：

```text
repo/
  pyproject.toml
  README.md
  LICENSE
  .gitignore
  .editorconfig
  .python-version              # 可选但建议

  app/
    __init__.py
    main.py                    # 应用入口（创建 QApplication、权限检查、DPI 设置、启动主 UI）

    ui/
      run_panel.py             # 运行面板（置顶、吸附、倒计时、进度/状态/日志、固定提示条）
      calibration_overlay.py   # 标定 overlay（ROI/点位采集）
      message_editor.py        # 消息列表编辑器（尾部空条目、Enter 换行）
      widgets.py               # 通用 UI 组件

    core/
      engine.py                # 状态机 + 自动化流程（含消息变化检测）
      capture.py               # mss 抓图、虚拟桌面元信息、ROI 裁剪
      diff.py                  # 灰度、mask、diff、校准算法
      model.py                 # 数据模型（ROI/Point/Config/Enums）
      logging.py               # 日志队列、环形缓冲200条、格式化
      os_adapter/
        __init__.py
        input_inject.py        # 点击/快捷键粘贴（跨平台抽象）
        win_dpi.py             # Windows DPI aware 设置（Qt 初始化前调用）+ 智能检测
        mac_permissions.py     # macOS 权限检测与引导信息

    assets/
      icons/
      styles/

  tests/
    test_diff.py
    test_mask.py
    test_calibration_threshold.py
    test_state_machine.py
    test_message_filter.py                # 新增
    test_hold_hits_reset.py               # 新增
    test_circular_roi.py                  # 新增
    test_coordinate_validation.py         # 新增

  scripts/
    build_windows.ps1          # 可选：打包脚本
    build_macos.sh             # 可选：打包脚本

  ci/
    github_workflows.yml       # 可选：CI 定义
```

职责边界（MUST）：
- `ui/` 不得直接调用 OS 细节；通过 `core/` 或 `os_adapter/` 统一入口。
- `core/engine.py` 不得直接操作 Qt 控件；仅通过回调/事件/信号上报状态与日志。

---

## 4. 代码规范与约束（MUST）

### 4.1 风格与静态检查
- MUST：PEP8；推荐 `ruff` + `black`（或 `ruff format`）。
- MUST：类型标注（至少核心数据结构与核心函数签名）。
- SHOULD：`mypy` 或 `pyright`（二选一）用于最低限度类型检查。

### 4.2 线程与并发
- MUST：自动化逻辑运行在后台线程（或 Qt Worker），UI 操作仅在 UI 线程。
- MUST：Pause/Stop 为线程安全原子控制（如 `threading.Event`），且每个"检查点"能及时响应 Stop。

### 4.3 可观测性
- MUST：日志接口统一（`core/logging.py`），支持：
  - 状态变化（含 Countdown 状态）
  - i/N（1-based 显示）
  - WaitingHold 下每秒 diff 与 hold_hits
  - 错误（权限/截图失败/越界/消息列表变化）
  - 完整消息内容（无需脱敏）
- MUST：日志采用环形缓冲限制条数（默认 200，可配置）。

---

## 5. 配置与数据（MUST）

### 5.1 运行期配置对象
- MUST：在 `core/model.py` 定义并贯穿：
  - ROI（rect/circle + circle derived params）
  - input_point, send_point
  - th_hold（默认/校准/手动）
  - messages（Start 时过滤空条目后的列表，锁定 N）
  - messages_snapshot（Pause 时保存）

### 5.2 持久化策略
- PRD 约束：每次运行必须重新标定。
- Repo 层面：
  - MUST：默认不跨次持久化标定结果。
  - SHOULD：允许通过开发开关保存到本地（如 `~/.appname/config.json`），但必须在 README 中明确"仅本地存储，不上传"。

---

## 6. 运行、构建与打包命令（MUST）

### 6.1 本地运行
- MUST：提供一条"从干净环境到可运行"的命令路径，并写在 README：

#### Windows：
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock
python -m app.main
```

#### macOS：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
# macOS 需额外安装 pyobjc（权限检测依赖）
pip install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
python -m app.main
```

### 6.2 打包（最小要求）
- Windows：MUST 输出可运行 `.exe`（onefile 或 onedir 均可）。
- macOS：MUST 输出 `.app`（可运行），并在 README 说明权限授权步骤与单显示器限制。

推荐工具：PyInstaller。

### 6.3 平台专项构建约束

#### Windows DPI
- MUST：在 Qt 初始化前调用 DPI aware 设置（见 `os_adapter/win_dpi.py`）。
- MUST：智能检测设置失败原因（区分"已设置过"与"真正失败"）。
- 若真正失败，显示警告横幅。

#### macOS 权限
- MUST：在 UI 中完成启动自检，缺失时禁用 Start。
- MUST：README 提供明确路径：系统设置 → 隐私与安全性 → 屏幕录制 / 辅助功能。
- MUST：README 明确说明：**仅支持单显示器环境，多显示器配置暂不支持**。
- SHOULD：提示"授权后可尝试 Start；若仍提示缺失则重启应用"。

### 6.4 构建脚本
- SHOULD：提供脚本以减少手工步骤：
  - `scripts/build_windows.ps1`
  - `scripts/build_macos.sh`

脚本 MUST：
- 清理旧产物
- 安装依赖（或检查已安装）
- 执行打包
- 输出产物路径到控制台

---

## 7. 最小测试套件（MUST）

### 7.1 单元测试范围
- MUST 在 `tests/` 提供并可运行以下测试（不依赖真实截图/真实输入注入）：
  1. **diff 正确性**：给定两帧数组，输出在 [0,1] 且符合预期
  2. **圆形 mask 生效**：圆外变化不影响 diff；圆内变化正确计入
  3. **阈值校准算法**：对一组 di，输出 clamp 后的 TH_rec（mu+3*sigma, 0.005, 0.2），且可复现
  4. **状态机核心**：Pause 冻结变量；Resume 沿用 frame_t0/hold_hits；Stop 回 Idle
  5. **消息过滤逻辑**：过滤空条目后 N 正确；索引显示为 1-based
  6. **hold_hits 重置**：diff < TH_HOLD 后 hold_hits 归零
  7. **坐标越界校验**：ROI/点位在虚拟桌面外时 Start 被阻止
  8. **圆形 ROI 内切圆计算**：给定矩形 rect，圆心与半径符合公式（cx=x+w/2, cy=y+h/2, r=min(w,h)/2）

### 7.2 测试命令
- MUST：在 README 提供：
  - `pytest -q`

---

## 8. CI（部分 MUST）

### 8.1 算法核心测试（MUST）
- MUST：至少在 GitHub Actions 或等价 CI 中运行：
  - `tests/test_diff.py`
  - `tests/test_mask.py`
  - `tests/test_calibration_threshold.py`
  - `tests/test_hold_hits_reset.py`
  - `tests/test_circular_roi.py`

### 8.2 完整测试套件（SHOULD）
- SHOULD：提供 GitHub Actions（或等价 CI）执行：
  - 安装依赖
  - 运行 `ruff` / `black` 检查
  - 运行完整 `pytest`

> UI/OS 注入部分可在 CI 跳过，确保算法与状态机逻辑稳定。

---

## 9. 安全与合规（MUST）
- MUST：不收集、不上传任何屏幕内容；所有截图仅用于内存计算 diff。
- MUST：README 明确说明需要屏幕录制与辅助功能权限的原因与用途。
- MUST：日志记录完整消息内容（调试用，无需脱敏；用户应自行保护日志文件）。

---

## 10. 交付清单（Deliverables）

### 10.1 必须交付（MUST）
1. 源码仓库（含本 Repo Contract、Executable Spec、PRD/TDD/Test Plan）
2. Windows 可执行程序：
   - `dist/<appname>.exe` 或 `dist/<appname>/...`
3. macOS 应用包：
   - `dist/<appname>.app`
4. README（必须包含以下章节）：
   - 项目简介
   - 系统要求（Python 版本、操作系统、macOS 单显示器限制）
   - 安装与运行（含 macOS pyobjc 安装）
   - 构建与打包
   - **macOS 权限授权步骤**（含说明："系统设置 → 隐私与安全性 → 屏幕录制 / 辅助功能"）
   - **Windows DPI 注意事项**（建议 100% 缩放）
   - **使用说明**（标定流程、ROI 选择建议）
   - **故障排查（Troubleshooting）**，至少覆盖：
     * macOS 授权后仍无法启动：需重启应用
     * Windows 点击位置偏移：检查 DPI 缩放，建议 100%
     * 无限等待不推进：ROI 选择建议与校准阈值调整
     * 粘贴失败/换行丢失：目标应用是否支持多行粘贴
   - 许可证
5. 最小测试套件与可运行命令：`pytest -q`

### 10.2 不增加的交付物（明确不包含）
- CHANGELOG.md（暂不要求）
- examples/sample_messages.txt（暂不要求）
- docs/ROI_selection_guide.md 独立文档（暂不要求）
- logs/ 目录自动导出（暂不要求）

---

## 11. 定义"完成"（Definition of Done, DoD）
一个版本满足 DoD 的条件：
- 满足《可执行规格（Executable Spec）》中"验收用最小检查表"全部条目。
- P0 测试用例 100% 通过。
- Windows 至少在 100% 与 150% DPI 下跑通一次；macOS 至少完成"未授权禁止 Start"和"授权后运行"两项。
- **打包产物必须在无 Python 环境的干净虚拟机/新用户账户下启动并完成一次标定+单条消息发送测试**：
  - Windows：在未安装 Python 的 Win10 虚拟机下运行 .exe
  - macOS：在新用户账户（无 homebrew/Python）下运行 .app
- 单元测试（8 项）全部通过。

---

## 12. 实现中的明确禁止（MUST NOT）
- MUST NOT 在运行中自动移动/缩放/滚动目标窗口。
- MUST NOT 依赖目标应用内部 API/DOM/插件。
- MUST NOT 将屏幕截图或用户消息内容上传到网络。
- MUST NOT 在未通过权限/坐标校验时允许 Start。
- MUST NOT 支持 macOS 多显示器环境（本版本明确限制）。

---

## 13. 版本管理（MUST）
- MUST：pyproject.toml 的 version 字段与文档版本（PRD/TDD/Executable Spec）保持一致（当前 v1.1）。
- 代码提交时应在 commit message 中注明对应的规格文档版本。
