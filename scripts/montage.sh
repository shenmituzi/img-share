#!/usr/bin/env bash
# 多图拼网格(需 ffmpeg)。用法: montage.sh out.png f1.png [f2.png ...]
set -u
OUT="${1:?用法: montage.sh <输出.png> <图1> [图2 ...]}"; shift
[ "$#" -ge 1 ] || { echo "至少一张图"; exit 1; }
command -v ffmpeg >/dev/null || { echo "[!] 缺少 ffmpeg"; exit 1; }
N="$#"; W=600; H=338; COLS=2; ROWS=$(( (N + COLS - 1) / COLS ))
IN=""; FC=""; i=0
for f in "$@"; do IN="$IN -i "$f""; FC="$FC[$i:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v$i];"; i=$((i+1)); done
VARS=""; i=0; for f in "$@"; do VARS="$VARS[v$i]"; i=$((i+1)); done
ffmpeg -y $IN -filter_complex "${FC}${VARS}concat=n=${N}:v=1:a=0[cat];[cat]tile=${COLS}x${ROWS}:padding=6:margin=6:color=black" -frames:v 1 "$OUT" 2>&1 | tail -3
echo "output: $OUT"
