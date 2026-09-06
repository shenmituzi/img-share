#!/usr/bin/env bash
# 校验 img-share 链路并输出公网地基址
set -u
BASE="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/img-share/tunnel.log 2>/dev/null | tail -1)"
[ -z "$BASE" ] && { echo "未找到隧道（先跑 setup.sh）"; exit 1; }
echo "PUBLIC_BASE=$BASE"
curl -s -o /dev/null -w 'base_live=%{http_code}\n' --max-time 20 "$BASE/" || true
