#!/bin/bash
# APS Web 服务启动脚本（默认端口 8000）
# 用法: ./start.sh [端口]
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$DIR/src/web"
PORT="${1:-${PORT:-8000}}"
LOG_FILE="/tmp/aps_service.log"
PID_FILE="/tmp/aps_service.pid"

PYTHON=""
for candidate in "$(command -v python3.13)" "$(command -v python3)"; do
    if [ -n "$candidate" ] && "$candidate" -c "import fastapi, uvicorn" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[错误] 未找到安装了 fastapi/uvicorn 的 Python，请先执行:"
    echo "  pip install -r $WEB_DIR/requirements.txt"
    exit 1
fi

# 端口占用时提示（不自动杀进程）
if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[错误] 端口 $PORT 已被占用 (PID: $(lsof -tiTCP:$PORT -sTCP:LISTEN | tr '\n' ' '))"
    echo "停止: kill \$(lsof -tiTCP:$PORT -sTCP:LISTEN) 或 ./aps/stop.sh"
    exit 1
fi

cd "$WEB_DIR"
export PYTHONPATH="$DIR/src${PYTHONPATH:+:$PYTHONPATH}"
nohup "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
    > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 3
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[错误] 启动失败，日志:"
    tail -20 "$LOG_FILE"
    exit 1
fi
echo "[信息] APS Web 已启动: http://127.0.0.1:$PORT  (PID: $(cat "$PID_FILE"))"
echo "[信息] 开放 API 文档: http://127.0.0.1:$PORT/api-docs"
echo "[信息] 停止: ./stop.sh 或 kill \$(cat $PID_FILE)"
