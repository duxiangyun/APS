#!/bin/bash
# ============================================================
# APS 智能排产系统 停止脚本
# 用法: ./stop.sh
# ============================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_DIR/aps_server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "[提示] 未找到 PID 记录文件 ($PID_FILE)"
    echo "若服务仍在运行，请手动执行: pkill -f 'uvicorn\|run.py'"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    # run.py 开启了 reload 模式，需同时结束其子进程
    PGID=$(ps -o pgid= -p "$PID" | tr -d ' ')
    kill -- "-$PGID" 2>/dev/null || kill "$PID"
    sleep 1
    kill -0 "$PID" 2>/dev/null && { kill -9 "$PID" 2>/dev/null; sleep 0.5; }
    echo "[信息] APS 服务已停止 (PID: $PID)"
else
    echo "[提示] 进程 $PID 已不存在"
fi
rm -f "$PID_FILE"
