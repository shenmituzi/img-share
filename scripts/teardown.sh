#!/usr/bin/env bash
# 停止分享（停图库+隧道+清理）
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python || true)"
[ -z "$PY" ] && { echo "[!] 缺少 python"; exit 1; }
exec "$PY" "$DIR/serve.py" --stop
