@echo off
chcp 65001 >nul
title MCU AI Tools Setup

echo ============================================
echo   MCU AI Tools - 环境安装脚本 (CMD)
echo ============================================
echo.

REM ---- 检测 Python ----
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python！请先安装 Python 3.10 或更高版本。
    echo        下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM ---- 检查 Python 版本号 ----
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo [检测] Python %pyver%

REM 提取主版本号
for /f "tokens=1,2 delims=." %%a in ("%pyver%") do (
    set pymajor=%%a
    set pyminor=%%b
)

if %pymajor% lss 3 (
    echo [错误] Python 版本过低 (需要 3.10+)，当前版本: %pyver%
    pause
    exit /b 1
)
if %pymajor% equ 3 if %pyminor% lss 10 (
    echo [错误] Python 版本过低 (需要 3.10+)，当前版本: %pyver%
    pause
    exit /b 1
)
echo [通过] 版本符合要求。

REM ---- 创建虚拟环境 ----
echo.
echo [步骤 1/3] 正在创建虚拟环境...
if exist venv\ (
    echo [跳过] venv 目录已存在，跳过创建。
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败！
        pause
        exit /b 1
    )
    echo [完成] 虚拟环境已创建。
)

REM ---- 激活虚拟环境 ----
echo.
echo [步骤 2/3] 正在安装依赖包...
call .\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [错误] 虚拟环境激活失败！
    pause
    exit /b 1
)

REM ---- 安装依赖 ----
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [警告] 部分依赖安装失败，请检查网络连接后重试。
    echo        手动执行: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ 环境配置大功告成！
echo.
echo   使用前请激活虚拟环境:
echo       .\venv\Scripts\activate
echo.
echo   然后启动 MCP Server:
echo       python mcp_server.py
echo ============================================
echo.
pause
