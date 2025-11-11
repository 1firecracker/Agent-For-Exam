# 一键启动前后端服务器 (PowerShell版本)
# 此脚本会在两个独立的窗口中启动后端和前端

# 清理函数：关闭所有占用8000端口的进程
function Stop-Port8000Processes {
    Write-Host ""
    Write-Host "正在清理8000端口进程..." -ForegroundColor Yellow
    $Port8000Connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($Port8000Connections) {
        $ProcessIds = $Port8000Connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($Pid in $ProcessIds) {
            try {
                $Process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
                if ($Process) {
                    Write-Host "关闭进程: $($Process.Name) (PID: $Pid)" -ForegroundColor Gray
                    Stop-Process -Id $Pid -Force -ErrorAction SilentlyContinue
                }
            } catch {
                # 忽略已关闭的进程
            }
        }
        Write-Host "已清理8000端口进程" -ForegroundColor Green
    } else {
        Write-Host "未发现占用8000端口的进程" -ForegroundColor Gray
    }
}

# 捕获中断信号（Ctrl+C）时执行清理
trap {
    Stop-Port8000Processes
    break
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "启动 LightRAG Web 应用" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 检查并停止现有的后端进程
Write-Host "检查现有后端进程..." -ForegroundColor Yellow
$ExistingUvicorn = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
if ($ExistingUvicorn) {
    Write-Host "发现 $($ExistingUvicorn.Count) 个正在运行的后端进程，正在停止..." -ForegroundColor Yellow
    $ExistingUvicorn | Stop-Process -Force
    Start-Sleep -Seconds 1
    Write-Host "已停止所有现有后端进程" -ForegroundColor Green
}

# 检查端口 8000 是否被占用
$PortInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($PortInUse) {
    Write-Host "警告: 端口 8000 仍被占用，等待释放..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}

# 启动后端服务器
Write-Host "正在启动后端服务器..." -ForegroundColor Yellow
$BackendPath = Join-Path $ScriptDir "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendPath'; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" -WindowStyle Normal

# 等待后端启动
Start-Sleep -Seconds 2

# 启动前端服务器
Write-Host "正在启动前端服务器..." -ForegroundColor Yellow
$FrontendPath = Join-Path $ScriptDir "frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendPath'; npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "后端服务器: http://localhost:8000" -ForegroundColor Cyan
Write-Host "前端服务器: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示：" -ForegroundColor Yellow
Write-Host "- 两个服务运行在独立的窗口中" -ForegroundColor Gray
Write-Host "- 关闭对应的窗口即可停止服务" -ForegroundColor Gray
Write-Host "- 后端日志显示在后端窗口中" -ForegroundColor Gray
Write-Host "- 前端日志显示在前端窗口中" -ForegroundColor Gray
Write-Host "- 使用 stop_all.ps1 可以一键停止所有服务" -ForegroundColor Gray
Write-Host "- 按 Ctrl+C 退出脚本时会自动清理8000端口进程" -ForegroundColor Gray
Write-Host ""
Write-Host "脚本已退出，服务继续在后台运行" -ForegroundColor Green

