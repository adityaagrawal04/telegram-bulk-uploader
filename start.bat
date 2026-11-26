@echo off
setlocal
cd /d "%~dp0"
title Telegram Bulk Uploader

echo.
echo  ============================================
echo   Telegram Bulk Uploader - Web UI Launcher
echo  ============================================
echo.

REM Check if Python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Download it from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Create venv if missing
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [2/2] Installing dependencies...
    .\.venv\Scripts\pip.exe install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo.
    echo  Setup complete!
    echo.
)

echo  Starting server at http://127.0.0.1:8000
echo  Opening browser in 2 seconds...
echo.
echo  Press Ctrl+C to stop the server.
echo  ============================================
echo.

.\.venv\Scripts\python.exe app.py

echo.
echo  Server stopped.
pause
