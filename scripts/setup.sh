#!/usr/bin/env bash
# img-share 薄壳：把要分享的 文件 交给跨平台编排器 serve.py（Windows 原生亦可）
# 用法: setup.sh <文件> [更多文件...] [--port N]
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python || true)"
[ -z "$PY" ] && { echo "[!] 缺少 python(python3)"; exit 1; }
exec "$PY" "$DIR/serve.py" --share "$@"
