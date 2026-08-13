@echo off
chcp 65001 >nul
echo ============================================
echo   校园活动自动刷取 (autopilot)
echo ============================================
echo.

REM 通过 WSL 运行 autopilot（持续监听模式）
wsl.exe -d Ubuntu -- bash -lc "cd /home/iruri/workspace/campus-event-hub && .venv/bin/python parser/autopilot.py"

pause
