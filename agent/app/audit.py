"""审计日志：SQLite audit_log 表（主）+ JSONL 文件（备份）

- 表结构：id, session_id, role, tool_name, params(JSON), result_summary,
  confirmed, status, cache_hit, duration_ms, created_at
- audit.log_tool_call() 由 tools.log_tool_call() 调用，失败不影响主流程
- 数据库路径可用 AUDIT_DB_PATH 覆盖（默认 agent/data/audit.db）
"""
import json
import os
import sqlite3
import threading
import time

from .config import TOOL_LOG_PATH

_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audit.db")
DB_PATH = os.environ.get("AUDIT_DB_PATH", _DEFAULT_DB)

_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT    NOT NULL DEFAULT '',
    role           TEXT    NOT NULL DEFAULT 'default',
    tool_name      TEXT    NOT NULL,
    params         TEXT    NOT NULL DEFAULT '{}',
    result_summary TEXT    NOT NULL DEFAULT '',
    confirmed      INTEGER NOT NULL DEFAULT 0,
    status         TEXT    NOT NULL DEFAULT 'success',
    cache_hit      INTEGER NOT NULL DEFAULT 0,
    duration_ms    REAL    NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_role    ON audit_log(role);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）；服务启动与首次写入前都会调用"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript(_SCHEMA)
            # 旧库补列（阶段一止血：cache_hit）
            cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_log)")}
            if "cache_hit" not in cols:
                conn.execute("ALTER TABLE audit_log ADD COLUMN cache_hit"
                             " INTEGER NOT NULL DEFAULT 0")
            conn.commit()
        finally:
            conn.close()


def _ensure() -> None:
    if not os.path.exists(DB_PATH):
        init_db()


def log_tool_call(session_id: str, role: str, tool: str, params: dict,
                  duration_ms: float, summary: str,
                  confirmed: bool = False, status: str = "success",
                  cache_hit: bool = False) -> int:
    """写入一条审计记录（JSONL 同步写一份作为备份）。返回记录 id（失败返回 -1）。

    role：发起调用的角色（planner/manager/...，未知场景传 'default'）
    status：'success' | 'failed'
    cache_hit：本次调用中任一数据源是否命中 20s 短时缓存
    """
    _ensure()
    params_json = json.dumps(params, ensure_ascii=False, default=str)[:4000]
    summary = (summary or "")[:500]
    created = time.strftime("%Y-%m-%d %H:%M:%S")
    row_id = -1
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "INSERT INTO audit_log (session_id, role, tool_name, params,"
                " result_summary, confirmed, status, cache_hit, duration_ms, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, role, tool, params_json, summary,
                 1 if confirmed else 0, status, 1 if cache_hit else 0,
                 round(float(duration_ms), 1), created),
            )
            conn.commit()
            row_id = cur.lastrowid
        except sqlite3.Error:
            row_id = -1  # 审计失败不影响主流程
        finally:
            conn.close()
    # JSONL 备份（沿用原格式 + 补充 role/status/confirmed/cache_hit）
    try:
        record = {
            "ts": created, "session_id": session_id, "role": role,
            "tool": tool, "params": params, "duration_ms": round(float(duration_ms), 1),
            "summary": summary[:300], "status": status, "confirmed": bool(confirmed),
            "cache_hit": bool(cache_hit),
        }
        os.makedirs(os.path.dirname(TOOL_LOG_PATH), exist_ok=True)
        with open(TOOL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row_id


def query_logs(session_id: str | None = None, role: str | None = None,
               tool: str | None = None, limit: int = 50) -> list[dict]:
    """按条件查询最近审计记录（created_at 倒序）"""
    _ensure()
    limit = max(1, min(int(limit or 50), 500))
    sql = ("SELECT id, session_id, role, tool_name, params, result_summary,"
           " confirmed, status, duration_ms, created_at, cache_hit FROM audit_log")
    where, args = [], []
    if session_id:
        where.append("session_id = ?")
        args.append(session_id)
    if role:
        where.append("role = ?")
        args.append(role)
    if tool:
        where.append("tool_name = ?")
        args.append(tool)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    conn = _connect()
    try:
        rows = conn.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["params"] = json.loads(d["params"])
            except (json.JSONDecodeError, TypeError):
                pass
            d["confirmed"] = bool(d["confirmed"])
            d["cache_hit"] = bool(d.get("cache_hit"))
            out.append(d)
        return out
    except sqlite3.Error:
        return []
    finally:
        conn.close()
