# 停止所有前后端服务器 (PowerShell版本)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "停止 LightRAG Web 应用" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 停止后端进程（通过进程名）
Write-Host "正在停止后端进程..." -ForegroundColor Yellow
$UvicornProcesses = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
if ($UvicornProcesses) {
    Write-Host "发现 $($UvicornProcesses.Count) 个后端进程" -ForegroundColor Yellow
    $UvicornProcesses | Stop-Process -Force
    Write-Host "已停止所有后端进程" -ForegroundColor Green
} else {
    Write-Host "未发现运行中的后端进程" -ForegroundColor Gray
}

# 停止所有占用8000端口的进程（更彻底的清理）
Write-Host "正在清理8000端口进程..." -ForegroundColor Yellow
$Port8000Connections = Get-NetTCPConnection -LocalPort 8000 -State Listen,Established -ErrorAction SilentlyContinue
if ($Port8000Connections) {
    $ProcessIds = $Port8000Connections | Where-Object { $_.OwningProcess -ne 0 } | Select-Object -ExpandProperty OwningProcess -Unique
    if ($ProcessIds) {
        foreach ($Pid in $ProcessIds) {
            try {
                $Process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
                if ($Process) {
                    Write-Host "关闭占用8000端口的进程: $($Process.Name) (PID: $Pid)" -ForegroundColor Gray
                    Stop-Process -Id $Pid -Force -ErrorAction SilentlyContinue
                }
            } catch {
                # 忽略已关闭的进程
            }
        }
        Write-Host "已清理8000端口进程" -ForegroundColor Green
    } else {
        Write-Host "8000端口只有TIME_WAIT状态的连接（会自动消失）" -ForegroundColor Gray
    }
} else {
    Write-Host "未发现占用8000端口的监听进程" -ForegroundColor Gray
}

# 停止前端进程（node/npm）
Write-Host "正在停止前端进程..." -ForegroundColor Yellow
$NodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($NodeProcesses) {
    # 尝试识别与前端相关的 node 进程（通过端口 5173）
    $FrontendProcesses = $NodeProcesses | Where-Object {
        $_.Path -like "*node*" -and 
        (Get-NetTCPConnection -OwningProcess $_.Id -LocalPort 5173 -ErrorAction SilentlyContinue)
    }
    if ($FrontendProcesses) {
        Write-Host "发现 $($FrontendProcesses.Count) 个前端进程" -ForegroundColor Yellow
        $FrontendProcesses | Stop-Process -Force
        Write-Host "已停止前端进程" -ForegroundColor Green
    } else {
        Write-Host "未发现运行中的前端进程（端口 5173）" -ForegroundColor Gray
    }
} else {
    Write-Host "未发现运行中的前端进程" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "停止完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Read-Host "按 Enter 键退出"

