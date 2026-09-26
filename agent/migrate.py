#!/usr/bin/env python3
"""agent 数据库迁移脚本（容器启动时先于 uvicorn 执行）。

项目未引入 Alembic，采用「幂等建表 + 增量 ALTER TABLE」完成结构迁移：

- 数据库不存在：创建完整表结构（与 app/audit.py 的 _SCHEMA 保持一致）
- 数据库已存在：对比期望列，缺失列用 ALTER TABLE 补齐（重复执行不报错）
- 迁移前：若库已存在，先用 VACUUM INTO 在同目录生成带时间戳的备份

数据库路径读取顺序：AGENT_DB_PATH > AUDIT_DB_PATH > data/audit.db

任何失败都以非 0 退出码结束，使容器启动中止，便于排查。
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

# 基础表结构：与 app/audit.py 的 _SCHEMA 保持一致
BASE_SCHEMA = """
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

# 期望列 -> 增量 ALTER 语句（仅当列缺失时执行，幂等）
# 说明：SQLite 的 ALTER TABLE ADD COLUMN 不允许默认值为括号表达式，
#       因此 created_at 用空串兜底（正常写入均由 INSERT 显式赋值）。
EXPECTED_COLUMNS: dict[str, str] = {
    "session_id": "TEXT NOT NULL DEFAULT ''",
    "role": "TEXT NOT NULL DEFAULT 'default'",
    "tool_name": "TEXT NOT NULL DEFAULT ''",
    "params": "TEXT NOT NULL DEFAULT '{}'",
    "result_summary": "TEXT NOT NULL DEFAULT ''",
    "confirmed": "INTEGER NOT NULL DEFAULT 0",
    "status": "TEXT NOT NULL DEFAULT 'success'",
    "cache_hit": "INTEGER NOT NULL DEFAULT 0",
    "duration_ms": "REAL NOT NULL DEFAULT 0",
    "created_at": "TEXT NOT NULL DEFAULT ''",
}


def log(msg: str) -> None:
    print(f"[migrate {time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def resolve_db_path() -> str:
    return (os.environ.get("AGENT_DB_PATH")
            or os.environ.get("AUDIT_DB_PATH")
            or "data/audit.db")


def backup_before_migration(conn: sqlite3.Connection, db_path: str) -> None:
    """迁移前用 VACUUM INTO 在同目录生成带时间戳备份"""
    directory, base = os.path.split(db_path)
    stem, _ = os.path.splitext(base)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = os.path.join(directory or ".", f"{stem}_backup_{stamp}.db")
    seq = 1
    while os.path.exists(target):
        target = os.path.join(directory or ".",
                              f"{stem}_backup_{stamp}_{seq}.db")
        seq += 1
    conn.execute("VACUUM INTO ?", (target,))
    log(f"迁移前备份完成: {target}")


def migrate(db_path: str) -> None:
    db_existed = os.path.exists(db_path)
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    log(f"开始迁移: {db_path} ({'已存在' if db_existed else '新建'})")
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        if db_existed:
            backup_before_migration(conn, db_path)
        else:
            log("数据库不存在，跳过备份")

        conn.executescript(BASE_SCHEMA)
        log("基础表结构检查完成 (CREATE TABLE IF NOT EXISTS)")

        existing = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
        added = 0
        for col, ddl in EXPECTED_COLUMNS.items():
            if col in existing:
                continue
            conn.execute(f"ALTER TABLE audit_log ADD COLUMN {col} {ddl}")
            log(f"增量迁移: 新增列 {col} {ddl}")
            added += 1
        conn.commit()
        if added == 0:
            log("列结构检查完成，无缺失列 (幂等，可重复执行)")

        cols = [row[1] for row in conn.execute("PRAGMA table_info(audit_log)")]
        total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        log(f"迁移完成: audit_log 现有 {len(cols)} 列, {total} 条记录")
    finally:
        conn.close()


def main() -> int:
    try:
        migrate(resolve_db_path())
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"迁移失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
