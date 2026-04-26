#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/ndict/.local/share/fnm/node-versions/v24.15.0/installation/bin:/home/ndict/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

cd /mnt/c/Users/Ndict/Documents/Codex/2026-04-26/pc-os-windows-11-pro-wsl2/gpu-support-log-gui/frontend
exec pnpm dev --host 0.0.0.0 --port 5173
