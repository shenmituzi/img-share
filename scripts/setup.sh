#!/usr/bin/env bash
# img-share 自举：起图库 + 起公网隧道，输出可内嵌的图片 URL（可在任意机器跑，幂等）
# 用法: setup.sh <图片目录> [可选端口]
set -u
IMG_DIR="${1:?用法: setup.sh <图片目录> [端口]}"
PORT="${2:-}"
LOG_DIR=/tmp/img-share
mkdir -p "$LOG_DIR"

command -v python3 >/dev/null || { echo "缺少 python3"; exit 1; }
CF="$(command -v cloudflared || echo /home/dumeizhuang/.local/bin/cloudflared)"
[ -x "$CF" ] || { echo "缺少 cloudflared（参考 https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/ ）"; exit 1; }

if [ -z "$PORT" ]; then
  PORT=8055
  while ss -tln 2>/dev/null | grep -q ":$PORT "; do PORT=$((PORT+1)); done
fi
echo "IMG_DIR=$IMG_DIR  PORT=$PORT"

if ! curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/"; then
  ( cd "$IMG_DIR" && setsid nohup python3 -m http.server "$PORT" --bind 0.0.0.0 >"$LOG_DIR/gallery.log" 2>&1 < /dev/null & )
  echo "gallery started on :$PORT  ($IMG_DIR)"
  sleep 2
else
  echo "gallery already serving on :$PORT"
fi
curl -s -o /dev/null -w 'gallery_live=%{http_code}\n' --max-time 3 "http://127.0.0.1:$PORT/"

TUN_LOG="$LOG_DIR/tunnel.log"
BASE="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUN_LOG" 2>/dev/null | tail -1)"
if [ -z "$BASE" ] || ! grep -q "127.0.0.1:$PORT" "$TUN_LOG" 2>/dev/null; then
  pkill -f "cloudflared tunnel --url http://127.0.0.1:$PORT" 2>/dev/null || true
  setsid nohup "$CF" tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate --protocol http2 >"$TUN_LOG" 2>&1 < /dev/null &
  echo "cloudflared tunnel starting..."
  sleep 10
  BASE="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUN_LOG" | tail -1)"
fi
[ -z "$BASE" ] && { echo "未取得隧道域名，请查看 $TUN_LOG"; exit 1; }

echo "PUBLIC_BASE=$BASE"
echo "聊天内嵌+点击全屏: [![描述]($BASE/<文件名>) ]($BASE/<文件名>)"
echo "测试: curl -sI $BASE/<文件名>"
