#Requires -Version 5.0
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  MCU AI Tools - 环境安装脚本 (PowerShell)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- 检测 Python ----
try {
    $pyVersion = python --version 2>&1
} catch {
    Write-Host "[错误] 未找到 Python！请先安装 Python 3.10 或更高版本。" -ForegroundColor Red
    Write-Host "       下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "[检测] $pyVersion" -ForegroundColor Green

# 提取版本号
if ($pyVersion -match '(\d+)\.(\d+)') {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
} else {
    Write-Host "[错误] 无法解析 Python 版本号" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Host "[错误] Python 版本过低 (需要 3.10+)，当前: $pyVersion" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host "[通过] 版本符合要求。" -ForegroundColor Green

# ---- 创建虚拟环境 ----
Write-Host "`n[步骤 1/3] 正在创建虚拟环境..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "[跳过] venv 目录已存在，跳过创建。" -ForegroundColor Gray
} else {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 虚拟环境创建失败！" -ForegroundColor Red
        Read-Host "按回车键退出"
        exit 1
    }
    Write-Host "[完成] 虚拟环境已创建。" -ForegroundColor Green
}

# ---- 安装依赖 ----
Write-Host "`n[步骤 2/3] 正在安装依赖包..." -ForegroundColor Yellow

# PowerShell 中激活 venv
$venvActivate = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    . $venvActivate
} else {
    Write-Host "[错误] 找不到虚拟环境激活脚本: $venvActivate" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[警告] 部分依赖安装失败，请检查网络连接后重试。" -ForegroundColor Yellow
    Write-Host "       手动执行: pip install -r requirements.txt" -ForegroundColor Gray
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  ✅ 环境配置大功告成！" -ForegroundColor Green
Write-Host ""
Write-Host "  使用前请激活虚拟环境:" -ForegroundColor White
Write-Host "       .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "  然后启动 MCP Server:" -ForegroundColor White
Write-Host "       python mcp_server.py" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor Cyan
Read-Host "按回车键退出"
