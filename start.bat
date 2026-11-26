@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Installing dependencies...
    .\.venv\Scripts\pip.exe install -r requirements.txt
)

echo Launching Telegram Bulk Uploader Web UI...
.\.venv\Scripts\python.exe app.py
pause
