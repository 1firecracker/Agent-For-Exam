@echo off
REM 一键启动前后端服务器
REM 此脚本会在两个独立的窗口中启动后端和前端

echo ========================================
echo 启动 LightRAG Web 应用
echo ========================================
echo.

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0

REM 启动后端服务器（在新窗口中）
echo 正在启动后端服务器...
start "后端服务器 (Backend)" cmd /k "cd /d %SCRIPT_DIR%backend && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

REM 等待一下，确保后端先启动
timeout /t 2 /nobreak >nul

REM 启动前端服务器（在新窗口中）
echo 正在启动前端服务器...
start "前端服务器 (Frontend)" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

echo.
echo ========================================
echo 启动完成！
echo ========================================
echo.
echo 后端服务器: http://localhost:8000
echo 前端服务器: http://localhost:5173
echo.
echo 提示：
echo - 两个服务运行在独立的窗口中
echo - 关闭对应的窗口即可停止服务
echo - 后端日志显示在"后端服务器"窗口中
echo - 前端日志显示在"前端服务器"窗口中
echo.
pause

