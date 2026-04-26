#!/usr/bin/env bash
set -euo pipefail

cd /mnt/c/Users/Ndict/Documents/Codex/2026-04-26/pc-os-windows-11-pro-wsl2/gpu-support-log-gui/backend
exec /home/ndict/.local/bin/uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
