# 跨平台 ROI 变化驱动自动化工具 Repo Contract

版本: v1.1-精简版  
日期: 2026-01-02

---

## 1. 技术栈与版本约束

### 1.1 语言与运行时
- MUST: Python >= 3.11
- SHOULD: 固定在.python-version/uv/pyenv中

### 1.2 主要依赖
- MUST: PySide6(UI)、mss(全虚拟桌面截图)、numpy(灰度/diff/mask)、pynput(点击与粘贴快捷键)
- macOS ONLY MUST: pyobjc(权限检测:ScreenCapture/Accessibility)

### 1.3 依赖管理
- MUST: 使用pyproject.toml统一依赖声明(推荐Poetry/uv/pip-tools任一)
- MUST: 提供requirements.lock或等价锁文件

---

## 2. 仓库目录结构

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
    main.py                    # 应用入口(创建QApplication、权限检查、DPI设置、启动主UI)

    ui/
      run_panel.py             # 运行面板(置顶、吸附、倒计时、进度/状态/日志、固定提示条)
      calibration_overlay.py   # 标定overlay(ROI/点位采集)
      message_editor.py        # 消息列表编辑器(尾部空条目、Enter换行)
      widgets.py               # 通用UI组件

    core/
      engine.py                # 状态机+自动化流程(含消息变化检测)
      capture.py               # mss抓图、虚拟桌面元信息、ROI裁剪
      diff.py                  # 灰度、mask、diff、校准算法
      model.py                 # 数据模型(ROI/Point/Config/Enums)
      logging.py               # 日志队列、环形缓冲200条、格式化
      os_adapter/
        __init__.py
        input_inject.py        # 点击/快捷键粘贴(跨平台抽象)
        win_dpi.py             # Windows DPI aware设置(Qt初始化前调用)+智能检测
        mac_permissions.py     # macOS权限检测与引导信息

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
    build_windows.ps1          # 可选:打包脚本
    build_macos.sh             # 可选:打包脚本
```

**职责边界(MUST)**:
- ui/不得直接调用OS细节;通过core/或os_adapter/统一入口
- core/engine.py不得直接操作Qt控件;仅通过回调/事件/信号上报状态与日志

---

## 3. 代码规范与约束

### 3.1 风格与静态检查
- MUST: PEP8;推荐ruff+black(或ruff format)
- MUST: 类型标注(至少核心数据结构与核心函数签名)
- SHOULD: mypy或pyright(二选一)用于最低限度类型检查

### 3.2 线程与并发
- MUST: 自动化逻辑运行在后台线程(或Qt Worker),UI操作仅在UI线程
- MUST: Pause/Stop为线程安全原子控制(如threading.Event),且每个"检查点"能及时响应Stop

### 3.3 可观测性
MUST日志接口统一(core/logging.py),支持:
- 状态变化(含Countdown状态)
- i/N(1-based显示)
- WaitingHold下每秒diff与hold_hits
- 错误(权限/截图失败/越界/消息列表变化)
- 完整消息内容(无需脱敏)
- 日志采用环形缓冲限制条数(默认200)

---

## 4. 配置与数据

### 4.1 运行期配置对象
MUST在core/model.py定义:
- ROI(rect/circle + circle derived params)
- input_point, send_point
- th_hold(默认/校准/手动)
- messages(Start时过滤空条目后的列表,锁定N)
- messages_snapshot(Pause时保存)

### 4.2 持久化策略
- MUST: 默认不跨次持久化标定结果
- SHOULD: 允许通过开发开关保存到本地(如~/.appname/config.json),但必须在README明确"仅本地存储,不上传"

---

## 5. 运行、构建与打包命令

### 5.1 本地运行

**Windows**:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock
python -m app.main
```

**macOS**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
# macOS需额外安装pyobjc(权限检测依赖)
pip install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
python -m app.main
```

### 5.2 打包(最小要求)
- Windows: MUST输出可运行.exe(onefile或onedir均可)
- macOS: MUST输出.app(可运行),并在README说明权限授权步骤与单显示器限制
- 推荐工具: PyInstaller

### 5.3 平台专项构建约束

**Windows DPI**:
- MUST: Qt初始化前调用DPI aware设置(见os_adapter/win_dpi.py)
- MUST: 智能检测设置失败原因(区分"已设置过"与"真正失败")
- 若真正失败,显示警告横幅

**macOS权限**:
- MUST: UI中完成启动自检,缺失时禁用Start
- MUST: README提供明确路径:系统设置→隐私与安全性→屏幕录制/辅助功能
- MUST: README明确说明:**仅支持单显示器环境,多显示器配置暂不支持**
- SHOULD: 提示"授权后可尝试Start;若仍提示缺失则重启应用"

### 5.4 构建脚本
SHOULD提供脚本(scripts/build_windows.ps1、scripts/build_macos.sh)完成:
- 清理旧产物
- 安装依赖(或检查已安装)
- 执行打包
- 输出产物路径到控制台

---

## 6. 最小测试套件

### 6.1 单元测试范围
MUST在tests/提供并可运行以下测试(不依赖真实截图/真实输入注入):
1. diff正确性: 给定两帧数组,输出在[0,1]且符合预期
2. 圆形mask生效: 圆外变化不影响diff;圆内变化正确计入
3. 阈值校准算法: 对一组di,输出clamp后的TH_rec(mu+3*sigma, 0.005, 0.2),且可复现
4. 状态机核心: Pause冻结变量;Resume沿用frame_t0/hold_hits;Stop回Idle
5. 消息过滤逻辑: 过滤空条目后N正确;索引显示为1-based
6. hold_hits重置: diff<TH_HOLD后hold_hits归零
7. 坐标越界校验: ROI/点位在虚拟桌面外时Start被阻止
8. 圆形ROI内切圆计算: 给定矩形rect,圆心与半径符合公式(cx=x+w/2, cy=y+h/2, r=min(w,h)/2)

### 6.2 测试命令
MUST在README提供: `pytest -q`

---

## 7. CI

### 7.1 算法核心测试(MUST)
MUST至少在GitHub Actions或等价CI中运行:
- tests/test_diff.py
- tests/test_mask.py
- tests/test_calibration_threshold.py
- tests/test_hold_hits_reset.py
- tests/test_circular_roi.py

### 7.2 完整测试套件(SHOULD)
SHOULD提供GitHub Actions(或等价CI)执行:
- 安装依赖
- 运行ruff/black检查
- 运行完整pytest

> UI/OS注入部分可在CI跳过,确保算法与状态机逻辑稳定

---

## 8. 安全与合规

- MUST: 不收集、不上传任何屏幕内容;所有截图仅用于内存计算diff
- MUST: README明确说明需要屏幕录制与辅助功能权限的原因与用途
- MUST: 日志记录完整消息内容(调试用,无需脱敏;用户应自行保护日志文件)

---

## 9. 交付清单

### 9.1 必须交付(MUST)
1. 源码仓库(含本Repo Contract、Executable Spec、PRD/TDD/Test Plan)
2. Windows可执行程序: dist/<appname>.exe或dist/<appname>/...
3. macOS应用包: dist/<appname>.app
4. README(必须包含):
   - 项目简介
   - 系统要求(Python版本、操作系统、macOS单显示器限制)
   - 安装与运行(含macOS pyobjc安装)
   - 构建与打包
   - macOS权限授权步骤(含说明:"系统设置→隐私与安全性→屏幕录制/辅助功能")
   - Windows DPI注意事项(建议100%缩放)
   - 使用说明(标定流程、ROI选择建议)
   - 故障排查(Troubleshooting),至少覆盖:
     * macOS授权后仍无法启动:需重启应用
     * Windows点击位置偏移:检查DPI缩放,建议100%
     * 无限等待不推进:ROI选择建议与校准阈值调整
     * 粘贴失败/换行丢失:目标应用是否支持多行粘贴
   - 许可证
5. 最小测试套件与可运行命令: pytest -q

### 9.2 不增加的交付物(明确不包含)
- CHANGELOG.md(暂不要求)
- examples/sample_messages.txt(暂不要求)
- docs/ROI_selection_guide.md独立文档(暂不要求)
- logs/目录自动导出(暂不要求)

---

## 10. 定义"完成"(DoD)

一个版本满足DoD的条件:
- 满足《可执行规格》中"验收用最小检查表"全部条目
- P0测试用例100%通过
- Windows至少在100%与150% DPI下跑通一次;macOS至少完成"未授权禁止Start"和"授权后运行"两项
- **打包产物必须在无Python环境的干净虚拟机/新用户账户下启动并完成一次标定+单条消息发送测试**:
  - Windows:在未安装Python的Win10虚拟机下运行.exe
  - macOS:在新用户账户(无homebrew/Python)下运行.app
- 单元测试(8项)全部通过

---

## 11. 实现中的明确禁止

- MUST NOT 在运行中自动移动/缩放/滚动目标窗口
- MUST NOT 依赖目标应用内部API/DOM/插件
- MUST NOT 将屏幕截图或用户消息内容上传到网络
- MUST NOT 在未通过权限/坐标校验时允许Start
- MUST NOT 支持macOS多显示器环境(本版本明确限制)

---

## 12. 版本管理

- MUST: pyproject.toml的version字段与文档版本(PRD/TDD/Executable Spec)保持一致(当前v1.1)
- 代码提交时应在commit message中注明对应的规格文档版本
