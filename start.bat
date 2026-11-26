@echo off
setlocal
cd /d "%~dp0"
title Telegram Bulk Uploader

echo.
echo  ============================================
echo   Telegram Bulk Uploader - Web UI Launcher
echo  ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Creating virtual environment...
    python -m venv .venv
    echo [2/2] Installing dependencies...
    .\.venv\Scripts\pip.exe install -r requirements.txt
    echo.
    echo  Setup complete!
    echo.
)

echo  Starting server...
echo.

REM Open browser immediately via Windows, then start server (blocks)
start "" http://127.0.0.1:8000
timeout /t 1 /nobreak >nul

echo  Server running at http://127.0.0.1:8000
echo  Press Ctrl+C to stop.
echo  ============================================
echo.

.\.venv\Scripts\python.exe app.py --no-browser

echo.
echo  Server stopped.
pause
