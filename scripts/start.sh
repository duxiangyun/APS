#!/bin/bash
# ============================================================
# APS 智能排产系统 启动脚本
# 用法: ./start.sh [端口]
# 默认端口 8000，可通过参数或环境变量 HOST/PORT 覆盖
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$PROJECT_DIR/src/web"
HOST="${HOST:-0.0.0.0}"
PORT="${1:-${PORT:-8000}}"
LOG_FILE="$PROJECT_DIR/aps_server.log"
PID_FILE="$PROJECT_DIR/aps_server.pid"

cd "$APP_DIR"

# ---------- 1. 定位 Python 解释器 ----------
PYTHON=""
for candidate in \
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
    "$(command -v python3.13)" \
    "$(command -v python3)"; do
    if [ -n "$candidate" ] && "$candidate" -c "import uvicorn, fastapi" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[错误] 未找到安装了 uvicorn/fastapi 的 Python 解释器"
    echo "请先安装依赖: pip install -r $APP_DIR/requirements.txt"
    exit 1
fi
echo "[信息] 使用解释器: $PYTHON ($($PYTHON --version))"

# ---------- 2. 依赖自检（缺失时自动安装）----------
if ! "$PYTHON" -c "
import importlib.metadata as m, sys
deps = ['fastapi', 'uvicorn', 'jinja2', 'python-multipart']
def has(name):
    try:
        m.version(name); return True
    except Exception:
        return False
sys.exit(0 if all(has(d) for d in deps) else 1)" 2>/dev/null; then
    echo "[信息] 缺少依赖，正在安装 requirements.txt ..."
    "$PYTHON" -m pip install -r "$APP_DIR/requirements.txt"
fi

# ---------- 3. 检查数据库文件 ----------
DB_FILE="$PROJECT_DIR/data/db/aps_or.db"
if [ ! -f "$DB_FILE" ]; then
    echo "[错误] 数据库文件不存在: $DB_FILE"
    exit 1
fi

# ---------- 4. 端口占用检查 ----------
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[警告] 端口 $PORT 已被占用："
    lsof -iTCP:"$PORT" -sTCP:LISTEN | tail -n +2
    read -p "是否结束占用进程并继续? (y/N): " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        # 结束旧的 APS 服务进程（若有 PID 记录）
        if [ -f "$PID_FILE" ]; then
            OLD_PID=$(cat "$PID_FILE")
            kill "$OLD_PID" 2>/dev/null && echo "[信息] 已停止旧进程 PID=$OLD_PID"
            rm -f "$PID_FILE"
            sleep 1
        fi
        # 若端口仍被占用则报错退出
        if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
            echo "[错误] 端口仍被其他程序占用，请手动处理"
            exit 1
        fi
    else
        echo "[提示] 可改用其他端口启动: ./start.sh 8080"
        exit 1
    fi
fi

# ---------- 5. 启动服务 ----------
echo "[信息] 启动 APS 服务: http://$HOST:$PORT/"
HOST="$HOST" PORT="$PORT" nohup "$PYTHON" run.py > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

sleep 2
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[错误] 服务启动失败，最近日志如下:"
    tail -20 "$LOG_FILE"
    exit 1
fi

LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "<本机IP>")
echo ""
echo "=============================================="
echo "  APS 服务已启动 (PID: $SERVER_PID)"
echo "  本机访问:   http://127.0.0.1:$PORT/"
echo "  局域网访问: http://$LOCAL_IP:$PORT/"
echo "  日志文件:   $LOG_FILE"
echo "  停止服务:   kill \$(cat $PID_FILE)  或  ./stop.sh"
echo "=============================================="
