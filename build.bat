@echo off
chcp 65001 > nul
echo ========================================
echo QueueSend 打包工具
echo ========================================
echo.

:menu
echo 请选择打包模式:
echo [1] 文件夹模式 (快速启动,体积小)
echo [2] 单文件模式 (便于分发,启动稍慢)
echo [3] 清理构建文件
echo [4] 退出
echo.
set /p choice=请输入选项 (1-4):

if "%choice%"=="1" goto build_folder
if "%choice%"=="2" goto build_onefile
if "%choice%"=="3" goto clean
if "%choice%"=="4" goto end
echo 无效选项,请重新选择!
echo.
goto menu

:build_folder
echo.
echo [步骤 1/3] 激活虚拟环境...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo 错误: 无法激活虚拟环境
    pause
    goto end
)

echo [步骤 2/3] 检查 PyInstaller...
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo PyInstaller 未安装,正在安装...
    pip install pyinstaller
)

echo [步骤 3/3] 开始打包 (文件夹模式)...
pyinstaller QueueSend.spec --clean
if errorlevel 1 (
    echo 打包失败!
    pause
    goto end
)

echo.
echo ========================================
echo 打包完成!
echo 输出位置: dist\QueueSend\QueueSend.exe
echo ========================================
pause
goto end

:build_onefile
echo.
echo [步骤 1/3] 激活虚拟环境...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo 错误: 无法激活虚拟环境
    pause
    goto end
)

echo [步骤 2/3] 检查 PyInstaller...
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo PyInstaller 未安装,正在安装...
    pip install pyinstaller
)

echo [步骤 3/3] 开始打包 (单文件模式)...
pyinstaller QueueSend_onefile.spec --clean
if errorlevel 1 (
    echo 打包失败!
    pause
    goto end
)

echo.
echo ========================================
echo 打包完成!
echo 输出位置: dist\QueueSend.exe
echo ========================================
echo.
echo 注意: 单文件模式首次启动较慢(需解压),
echo       建议发布前测试运行!
echo ========================================
pause
goto end

:clean
echo.
echo 正在清理构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
echo 清理完成!
echo.
pause
goto menu

:end
