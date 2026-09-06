#!/usr/bin/env bash
# img-share 自举：起图库 + 起公网隧道，输出可内嵌 URL（跨平台/WSL、重试、状态复用、图库仅回环）
# 用法: setup.sh <图片目录> [可选端口]
set -u
command -v python3 >/dev/null || { echo "[!] 缺少 python3"; exit 1; }
CF="$(command -v cloudflared || true)"
[ -z "$CF" ] && CF="${CLOUDFLARED:-}"
[ -z "$CF" ] && [ -x "$HOME/.local/bin/cloudflared" ] && CF="$HOME/.local/bin/cloudflared"
[ -z "$CF" ] && { echo "[!] 未找到 cloudflared，请安装或设 CLOUDFLARED=/路径/cloudflared"; exit 1; }

IMG_DIR="${1:?用法: setup.sh <图片目录> [端口]}"
if command -v wslpath >/dev/null 2>&1 && [[ "$IMG_DIR" =~ ^[A-Za-z]: ]]; then IMG_DIR="$(wslpath "$IMG_DIR")"; fi
if [[ "$IMG_DIR" != /* ]]; then IMG_DIR="$(cd "$IMG_DIR" && pwd)"; fi
[ -d "$IMG_DIR" ] || { echo "[!] 目录不存在: $IMG_DIR"; exit 1; }

TMP="${TMPDIR:-/tmp}"
STATE="$TMP/img-share.state"
PORT="${2:-}"
LOG="$TMP/img-share-gallery.log"
[ -z "$PORT" ] && PORT="$(python3 - <<'PY'
import socket
s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()
PY
)"

BASE=""
if [ -f "$STATE" ]; then
  . "$STATE"
  if [ -n "${PUBLIC_BASE:-}" ] && curl -s -o /dev/null --max-time 8 "${PUBLIC_BASE}/"; then
    BASE="$PUBLIC_BASE"; echo "reusing existing tunnel: $BASE"
  fi
fi

if [ -z "$BASE" ]; then
  if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/"; then
    PORT="$(python3 - <<'PY'
import socket
s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()
PY
)"
  fi
  ( cd "$IMG_DIR" && PYTHONUNBUFFERED=1 python3 -m http.server "$PORT" --bind 127.0.0.1 >"$LOG" 2>&1 & )
  echo "gallery starting on :$PORT ($IMG_DIR)"
  ok=""; for _ in 1 2 3 4 5 6 7 8 9 10; do curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/" && { ok=1; break; }; sleep 1; done
  [ -z "$ok" ] && { echo "[!] 图库未就绪:"; tail -5 "$LOG"; exit 1; }
  TUN_LOG="$TMP/img-share-tunnel-$$.log"
  if command -v setsid >/dev/null 2>&1; then setsid nohup "$CF" tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate --protocol http2 >"$TUN_LOG" 2>&1 < /dev/null & else nohup "$CF" tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate --protocol http2 >"$TUN_LOG" 2>&1 < /dev/null & fi
  for _ in $(seq 1 15); do BASE="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUN_LOG" 2>/dev/null | tail -1)"; [ -n "$BASE" ] && break; sleep 3; done
  [ -z "$BASE" ] && { echo "[!] 未取到隧道域名, 看 $TUN_LOG"; tail -5 "$TUN_LOG"; exit 1; }
  cat > "$STATE" <<EOF
PUBLIC_BASE=$BASE
PORT=$PORT
IMG_DIR=$IMG_DIR
TUN_LOG=$TUN_LOG
EOF
fi
echo "IMG_DIR=$IMG_DIR"
echo "PUBLIC_BASE=$BASE"
echo "内嵌+点击全屏: [![描述]($BASE/<文件名>) ]($BASE/<文件名>)"
echo "测试: curl -sI $BASE/<文件名>"