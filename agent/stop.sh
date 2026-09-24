#!/bin/bash
# 停止 Web Agent 后端
PID_FILE="/tmp/aps_agent.pid"
if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null && echo "[信息] 已停止 agent (PID=$(cat "$PID_FILE"))"
    rm -f "$PID_FILE"
else
    echo "[提示] 未找到 PID 文件，尝试按端口查找..."
    lsof -tiTCP:8100 -sTCP:LISTEN | xargs kill 2>/dev/null && echo "[信息] 已停止 8100 端口进程" || echo "[信息] 无运行中的 agent"
fi
