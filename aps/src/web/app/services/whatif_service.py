"""
What-if 沙盒模拟（规划功能 21）。

场景命名 + 假设参数 + 沙盒求解 + 版本对比闭环，不改变数据库结构：
- 场景定义存 JSON 文件（data/output/whatif/scenario_<id>.json），仅数据文件；
- 沙盒运行时临时覆盖 core_biz_global_params 数据行（写数据行，非 DDL），
  求解子进程退出后自动恢复运行前快照，正式参数不受影响；
- 每次沙盒求解产生独立 run_id（res_solve_run 天然版本化），可与基线版本对比；
- 快照与恢复通过 _active.json 状态文件保证异常安全（服务重启后自动恢复）。
"""
import json
import sqlite3
import time
import uuid
from pathlib import Path

from app.services.analysis_service import (
    _PROJECT_ROOT, start_solve, is_solve_running,
)
from app.services.edit_service import validate_global_params, update_global_params

_DB_PATH = _PROJECT_ROOT / "data" / "db" / "aps_or.db"
WHATIF_DIR = _PROJECT_ROOT / "data" / "output" / "whatif"
_ACTIVE_FILE = WHATIF_DIR / "_active.json"

# 允许假设的参数分组（统计参数仅作记录数校验，不开放假设）
OVERRIDABLE_GROUPS = {"计划参数", "数据表开关", "求解参数", "目标权重"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 参数假设的可编辑项（复用 /params 分组定义，含当前值/类型/提示）
# ---------------------------------------------------------------------------
def get_override_schema(conn: sqlite3.Connection) -> list:
    groups = [g for g in _global_param_groups(conn) if g["label"] in OVERRIDABLE_GROUPS]
    return groups


def _global_param_groups(conn: sqlite3.Connection) -> list:
    from app.services.edit_service import get_global_params
    return get_global_params(conn)


# ---------------------------------------------------------------------------
# 场景 CRUD（JSON 文件存储）
# ---------------------------------------------------------------------------
def _scenario_file(sid: str) -> Path:
    return WHATIF_DIR / f"scenario_{sid}.json"


def _load_scenario(sid: str) -> dict | None:
    f = _scenario_file(sid)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_scenario(sc: dict) -> None:
    WHATIF_DIR.mkdir(parents=True, exist_ok=True)
    _scenario_file(sc["id"]).write_text(
        json.dumps(sc, ensure_ascii=False, indent=2), encoding="utf-8")


def list_scenarios() -> list:
    ensure_params_restored()
    if not WHATIF_DIR.exists():
        return []
    out = []
    for f in WHATIF_DIR.glob("scenario_*.json"):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    out.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return out


def create_scenario(name: str, description: str, overrides: dict) -> dict:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "message": "场景名称不能为空"}
    if not isinstance(overrides, dict) or not overrides:
        return {"ok": False, "message": "请至少设置一项假设参数（覆盖值）"}
    values, err = validate_global_params(overrides)
    if err:
        return {"ok": False, "message": err}
    sc = {"id": uuid.uuid4().hex[:8], "name": name,
          "description": (description or "").strip(), "overrides": values,
          "status": "draft", "created_at": _now()}
    _save_scenario(sc)
    return {"ok": True, "scenario": sc}


def update_scenario(sid: str, name: str, description: str, overrides: dict) -> dict:
    sc = _load_scenario(sid)
    if not sc:
        return {"ok": False, "message": "场景不存在"}
    if sc.get("status") == "running":
        return {"ok": False, "message": "场景运行中，暂不可编辑"}
    if not isinstance(overrides, dict) or not overrides:
        return {"ok": False, "message": "请至少设置一项假设参数（覆盖值）"}
    values, err = validate_global_params(overrides)
    if err:
        return {"ok": False, "message": err}
    if (name or "").strip():
        sc["name"] = name.strip()
    sc["description"] = (description or "").strip()
    sc["overrides"] = values
    _save_scenario(sc)
    return {"ok": True, "scenario": sc}


def delete_scenario(sid: str) -> dict:
    f = _scenario_file(sid)
    if not f.exists():
        return {"ok": False, "message": "场景不存在"}
    sc = _load_scenario(sid) or {}
    if sc.get("status") == "running":
        return {"ok": False, "message": "场景运行中，暂不可删除"}
    f.unlink()
    return {"ok": True, "message": "已删除"}


# ---------------------------------------------------------------------------
# 沙盒运行：快照参数 → 应用假设 → 求解 → 恢复快照 → 关联 run_id
# ---------------------------------------------------------------------------
def _write_active(scenario_id: str, snapshot_rows: list) -> None:
    WHATIF_DIR.mkdir(parents=True, exist_ok=True)
    _ACTIVE_FILE.write_text(json.dumps(
        {"scenario_id": scenario_id, "snapshot": snapshot_rows, "started_at": _now()},
        ensure_ascii=False), encoding="utf-8")


def _restore_snapshot() -> bool:
    """按 _active.json 恢复参数快照；成功或无文件返回 True"""
    if not _ACTIVE_FILE.exists():
        return True
    try:
        data = json.loads(_ACTIVE_FILE.read_text(encoding="utf-8"))
        # 元组顺序与 SQL 列顺序 (param_key, param_value, description) 严格一致
        rows = [(r["param_key"], r["param_value"], r["description"])
                for r in data.get("snapshot") or []]
        if not rows:
            _ACTIVE_FILE.unlink()
            return True
        conn = sqlite3.connect(_DB_PATH)
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO core_biz_global_params "
                "(param_key, param_value, description) VALUES (?, ?, ?)", rows)
            conn.commit()
            # 校验恢复结果：逐键核对快照值
            marks = [r[0] for r in rows]
            ph = ",".join("?" * len(marks))
            cur = conn.execute(
                f"SELECT param_key, param_value FROM core_biz_global_params WHERE param_key IN ({ph})",
                marks)
            actual = dict(cur.fetchall())
            expect = {r[0]: r[1] for r in rows}
            if actual != expect:
                raise RuntimeError(f"参数恢复不一致: { {k: (expect[k], actual.get(k)) for k in expect if actual.get(k) != expect[k]} }")
        finally:
            conn.close()
        _ACTIVE_FILE.unlink()
        return True
    except Exception:
        return False


def ensure_params_restored() -> None:
    """服务重启/异常中断后的安全恢复：存在遗留快照则立即恢复正式参数"""
    _restore_snapshot()


def _latest_run_id() -> int | None:
    conn = _conn()
    try:
        row = conn.execute("SELECT MAX(run_id) FROM res_solve_run").fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def run_scenario(sid: str) -> dict:
    sc = _load_scenario(sid)
    if not sc:
        return {"started": False, "message": "场景不存在"}
    if sc.get("status") == "running" or is_solve_running():
        return {"started": False, "message": "已有排产任务正在运行"}
    values, err = validate_global_params(sc.get("overrides") or {})
    if err:
        return {"started": False, "message": f"场景参数校验失败: {err}"}

    # 1) 快照当前全部参数（含 description，保证完整恢复）
    conn = _conn()
    try:
        snapshot_rows = [dict(r) for r in conn.execute(
            "SELECT param_key, param_value, description FROM core_biz_global_params")]
    finally:
        conn.close()
    baseline_run_id = _latest_run_id()
    _write_active(sid, snapshot_rows)

    # 2) 应用假设参数（UPDATE 数据行，复用 /params 校验与写入）
    apply_res = update_global_params(sc["overrides"])
    if not apply_res.get("updated"):
        _restore_snapshot()
        return {"started": False, "message": apply_res.get("message", "假设参数应用失败")}

    # 3) 启动沙盒求解（独立日志，完成回调恢复参数并关联版本）
    sc["status"] = "running"
    sc["started_at"] = _now()
    sc["baseline_run_id"] = baseline_run_id
    _save_scenario(sc)

    def _on_finish(returncode: int):
        _restore_snapshot()
        new_rid = _latest_run_id()
        sc2 = _load_scenario(sid)
        if sc2:
            sc2["status"] = "done" if returncode == 0 else "failed"
            sc2["run_id"] = new_rid
            sc2["finished_at"] = _now()
            _save_scenario(sc2)

    res = start_solve(log_name=f"whatif_{sid}.log", on_finish=_on_finish)
    if not res.get("started"):
        # 启动失败（如被其他实例占用）：立即恢复参数与场景状态
        _restore_snapshot()
        sc["status"] = "draft"
        _save_scenario(sc)
        return res
    return {"started": True, "message": f"场景「{sc['name']}」沙盒求解已启动（PID {res.get('pid')}）"}


def scenario_status(sid: str) -> dict:
    """沙盒运行状态：场景 + 是否运行 + 日志尾部 + 版本关联结果"""
    sc = _load_scenario(sid)
    if not sc:
        return {"scenario": None, "running": False, "log_tail": ""}
    running = sc.get("status") == "running" and is_solve_running()
    log_tail = ""
    log_path = WHATIF_DIR / f"whatif_{sid}.log"
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            log_tail = "\n".join(lines[-30:])
        except Exception:
            pass
    run_info = None
    rid = sc.get("run_id")
    if rid:
        conn = _conn()
        try:
            r = conn.execute(
                "SELECT run_id, run_time, status, objective, solve_time_ms FROM res_solve_run "
                "WHERE run_id = ?", (rid,)).fetchone()
            if r:
                run_info = {"run_id": r["run_id"], "run_time": r["run_time"],
                            "status": r["status"],
                            "objective": round(r["objective"], 0) if r["objective"] else None,
                            "solve_time_s": round(r["solve_time_ms"] / 1000, 1) if r["solve_time_ms"] else None}
        finally:
            conn.close()
    return {"scenario": sc, "running": running, "log_tail": log_tail, "run_info": run_info}
