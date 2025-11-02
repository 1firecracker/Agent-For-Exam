# 一键启动前后端服务器 (PowerShell版本)
# 此脚本会在两个独立的窗口中启动后端和前端

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "启动 LightRAG Web 应用" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

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
Write-Host ""
Read-Host "按 Enter 键退出"

