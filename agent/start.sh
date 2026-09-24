#!/bin/bash
# Web Agent 后端启动脚本（默认端口 8100）
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PORT="${1:-${PORT:-8100}}"

PYTHON=""
for candidate in "$(command -v python3.13)" "$(command -v python3)"; do
    if [ -n "$candidate" ] && "$candidate" -c "import fastapi, httpx, uvicorn" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[错误] 未找到安装了 fastapi/httpx/uvicorn 的 Python，请先执行:"
    echo "  pip install -r $DIR/requirements.txt"
    exit 1
fi

echo "[信息] 启动 Web Agent 后端: http://0.0.0.0:$PORT (APS: ${APS_BASE_URL:-http://127.0.0.1:8000})"
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
