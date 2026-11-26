#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f ".venv/bin/python" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  echo "Installing dependencies..."
  .venv/bin/pip install -r requirements.txt
fi

echo "Launching Telegram Bulk Uploader Web UI..."
.venv/bin/python app.py
