#!/usr/bin/env bash
set -u
TMP="${TMPDIR:-/tmp}"
STATE="$TMP/img-share.state"
[ -f "$STATE" ] || { echo "[!] 未发现状态(先跑 setup.sh)"; exit 1; }
. "$STATE"
[ -n "${PUBLIC_BASE:-}" ] || { echo "[!] 状态缺 PUBLIC_BASE"; exit 1; }
echo "PUBLIC_BASE=$PUBLIC_BASE"
echo "IMG_DIR=${IMG_DIR:-?}"
curl -s -o /dev/null -w 'base_live=%{http_code}\n' --max-time 20 "$PUBLIC_BASE/" || true
