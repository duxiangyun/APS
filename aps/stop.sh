#!/bin/bash
# 停止 APS Web 服务
PID_FILE="/tmp/aps_service.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null && echo "[信息] 已停止 APS (PID=$PID)"
    rm -f "$PID_FILE"
else
    echo "[提示] 未找到 PID 文件，尝试按端口 8000 查找..."
    lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill 2>/dev/null \
        && echo "[信息] 已停止 8000 端口进程" || echo "[信息] 无运行中的 APS 服务"
fi
