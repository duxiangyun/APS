"""
What-if 沙盒模拟（规划功能 21）。

场景命名 + 假设参数 + 插单 + 沙盒求解 + 版本对比闭环，不改变数据库结构：
- 场景定义存 JSON 文件（data/output/whatif/scenario_<id>.json），仅数据文件；
- 沙盒运行时临时覆盖 core_biz_global_params 数据行（写数据行，非 DDL），
  求解子进程退出后自动恢复运行前快照，正式参数不受影响；
- 插单假设：运行时临时向 core_biz_demand_order 注入订单行（写数据行，非 DDL），
  order_id 由服务端按 MAX(order_id)+1 分配，并把 STAT_ORDER_RECORDS 同步为实际订单数
  （模型订单范围 norder 取该参数，不一致会静默漏单或 KeyError），
  求解结束后按快照删除注入行、还原被覆盖的参数；
- 每次沙盒求解产生独立 run_id（res_solve_run 天然版本化），可与基线版本对比；
- 快照与恢复通过 _active.json 状态文件保证异常安全（服务重启后自动恢复）；
- 不改动 Gurobi 模型定义：模型按 Order=range(1,norder+1) 数据驱动取数，只要插单的
  产品代码已在产品库（产品类物料 + 产品扩展）中即可被建模。
"""
import json
import math
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

# 允许假设的参数分组（统计参数仅作记录数校验，不开放假设；
# STAT_ORDER_RECORDS 不开放给用户假设，由插单流程自动同步为实际订单数）
OVERRIDABLE_GROUPS = {"计划参数", "数据表开关", "求解参数", "目标权重"}

# 插单假设：临时注入 core_biz_demand_order 的字段（order_id 由服务端分配）
# _ORDER_COLUMNS 为入库/快照/还原共用的列顺序，必须与 _apply_orders 的取值顺序一致
_ORDER_TABLE = "core_biz_demand_order"
_ORDER_FIELDS = ("product_code", "quantity", "due_period", "priority_level",
                 "max_delay_allowed", "delay_penalty")
_ORDER_COLUMNS = ("order_id", "product_code", "price", "quantity", "due_period",
                  "priority_level", "max_delay_allowed", "delay_penalty")
_ORDER_MAX = 20                              # 单场景插单条数上限（防御性）
_ORDER_COUNT_PARAM = "STAT_ORDER_RECORDS"    # 订单数参数：必须与订单表实际行数一致


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
# 插单：解析 / 校验 / 注入 / 订单数同步
#
# 校验规则与 Gurobi 模型的数据假设严格对齐（模型对订单表按行取值），否则会出现
# 求解期崩溃（OrdPrice 为 NULL → 空字符串参与运算）或静默漏单（norder 与实际行数不符）。
# ---------------------------------------------------------------------------
def _param_int(conn: sqlite3.Connection, key: str, default: int) -> int:
    """读整型全局参数（缺失或非法时回退默认值）"""
    row = conn.execute(
        "SELECT param_value FROM core_biz_global_params WHERE param_key = ?", (key,)).fetchone()
    try:
        return int(float(row[0]))
    except (TypeError, ValueError):
        return default


def _order_bounds(conn: sqlite3.Connection) -> dict:
    """插单合法区间（取自当前全局参数，与模型约束一致）"""
    return {
        "nperiod": _param_int(conn, "PLAN_HORIZON", 12),
        "ncls": _param_int(conn, "ORDER_PRIORITY_LEVELS", 3),
        "maxdelay": _param_int(conn, "MAX_DELAY_ALLOWED", 0),
    }


def _product_catalog(conn: sqlite3.Connection) -> dict:
    """产品代码 → 标准售价。

    取数口径与 alg_sheet_产品表 一致（产品类物料 + 已维护产品扩展），
    保证插单产品能被模型的 Prodidx 索引到。
    """
    rows = conn.execute(
        "SELECT m.material_code, p.standard_price FROM core_md_material m "
        "JOIN core_md_product_ext p ON m.material_code = p.material_code "
        "WHERE m.category = 'PRODUCT'").fetchall()
    return {r[0]: r[1] for r in rows}


def _num_field(value, label: str) -> tuple:
    """解析有限数值，返回 (值, 错误消息)"""
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        return None, f"{label}需为数值"
    if not math.isfinite(v):
        return None, f"{label}需为有限数值"
    return v, ""


def _int_field(value, label: str, lo: int, hi: int) -> tuple:
    """解析 [lo, hi] 区间内的整数（小数/超界均视为非法），返回 (值, 错误消息)"""
    try:
        f = float(str(value).strip())
    except (TypeError, ValueError):
        return None, f"{label}需为整数"
    if not math.isfinite(f) or f != int(f):
        return None, f"{label}需为整数"
    iv = int(f)
    if not (lo <= iv <= hi):
        return None, f"{label}需在 {lo}~{hi} 之间"
    return iv, ""


def _validate_orders(conn: sqlite3.Connection, orders) -> tuple:
    """校验插单列表，返回 (规范化后的 list, 错误消息)；错误消息为空表示通过。

    规则：
    - product_code 须在产品库中（产品类物料且已维护产品扩展 → 模型 Prodidx 可索引）；
    - quantity > 0；due_period ∈ [1, PLAN_HORIZON]（超期订单模型不建模，等价漏单）；
    - priority_level ∈ [1, ORDER_PRIORITY_LEVELS]（模型按等级预建 Ordeliv，超界会 KeyError）；
    - max_delay_allowed ∈ [0, MAX_DELAY_ALLOWED]；delay_penalty ≥ 0；
    - price 可省略（缺省取产品标准售价），显式给定则落盘保存（模型按行读 OrdPrice，不可为空）。
    """
    if orders is None or orders == "":
        return [], ""
    if not isinstance(orders, list):
        return [], "插单列表需为数组"
    if len(orders) > _ORDER_MAX:
        return [], f"单个场景最多支持 {_ORDER_MAX} 条插单"
    catalog = _product_catalog(conn)
    b = _order_bounds(conn)
    allowed = set(_ORDER_FIELDS) | {"price"}
    out = []
    for idx, item in enumerate(orders, 1):
        tag = f"第 {idx} 条插单"
        if not isinstance(item, dict):
            return [], f"{tag}需为对象"
        unknown = set(item) - allowed
        if unknown:
            return [], f"{tag}含不支持的字段: {', '.join(sorted(unknown))}"
        pcode = str(item.get("product_code") or "").strip()
        if not pcode:
            return [], f"{tag}的产品代码不能为空"
        if pcode not in catalog:
            return [], f"{tag}的产品代码「{pcode}」不在产品库中（须为产品类物料且已维护产品扩展）"

        qty, err = _num_field(item.get("quantity"), f"{tag}的数量")
        if err:
            return [], err
        if qty <= 0:
            return [], f"{tag}的数量需大于 0"
        due, err = _int_field(item.get("due_period"), f"{tag}的交期", 1, b["nperiod"])
        if err:
            return [], err
        lvl, err = _int_field(item.get("priority_level"), f"{tag}的订单等级", 1, b["ncls"])
        if err:
            return [], err
        dly, err = _int_field(item.get("max_delay_allowed"), f"{tag}的允许延期", 0, b["maxdelay"])
        if err:
            return [], err
        pen, err = _num_field(item.get("delay_penalty"), f"{tag}的延期罚金")
        if err:
            return [], err
        if pen < 0:
            return [], f"{tag}的延期罚金不能为负"

        norm = {"product_code": pcode, "quantity": qty, "due_period": due,
                "priority_level": lvl, "max_delay_allowed": dly, "delay_penalty": pen}
        raw_price = item.get("price")
        if raw_price is not None and str(raw_price).strip() != "":
            price, err = _num_field(raw_price, f"{tag}的订单单价")
            if err:
                return [], err
            if price < 0:
                return [], f"{tag}的订单单价不能为负"
            norm["price"] = price       # 显式单价才落盘；缺省价在注入时按产品标准售价解析
        elif catalog.get(pcode) is None:
            return [], f"{tag}未提供订单单价，且产品「{pcode}」无标准售价可作默认值"
        out.append(norm)
    return out, ""


def _next_order_ids(conn: sqlite3.Connection, n: int) -> list:
    """按 MAX(order_id)+1 预分配 n 个订单号（与现有订单号不冲突）"""
    if n <= 0:
        return []
    cur = conn.execute(f"SELECT IFNULL(MAX(order_id), 0) FROM {_ORDER_TABLE}").fetchone()
    base = int(cur[0] or 0)
    return list(range(base + 1, base + 1 + n))


def _order_rows_by_ids(conn: sqlite3.Connection, ids: list) -> list:
    """取指定订单号的现有行（用于异常回滚；正常无冲突时为空）"""
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT {', '.join(_ORDER_COLUMNS)} FROM {_ORDER_TABLE} "
        f"WHERE order_id IN ({ph})", list(ids)).fetchall()
    return [list(r) for r in rows]


def _apply_orders(conn: sqlite3.Connection, orders: list, ids: list) -> None:
    """按预分配的订单号注入订单行（不提交，由调用方 commit/rollback）。

    全部列显式赋值：模型按行读订单列，NULL 会被读成空字符串并导致求解期崩溃。
    """
    catalog = _product_catalog(conn)
    payload = []
    for oid, o in zip(ids, orders):
        price = o.get("price")
        if price is None:
            price = catalog.get(o["product_code"])
        payload.append((oid, o["product_code"], price, o["quantity"], o["due_period"],
                        o["priority_level"], o["max_delay_allowed"], o["delay_penalty"]))
    ph = ",".join("?" * len(_ORDER_COLUMNS))
    conn.executemany(
        f"INSERT INTO {_ORDER_TABLE} ({', '.join(_ORDER_COLUMNS)}) VALUES ({ph})", payload)


def _sync_order_count(conn: sqlite3.Connection) -> int:
    """把 STAT_ORDER_RECORDS 同步为订单表实际行数，返回订单总数。

    模型订单数为 Order = range(1, norder+1)，norder 取自该参数：
    参数偏小 → 新订单被静默忽略；参数偏大 → 读订单列时 KeyError。
    """
    n = int(conn.execute(f"SELECT COUNT(*) FROM {_ORDER_TABLE}").fetchone()[0])
    conn.execute("UPDATE core_biz_global_params SET param_value = ? WHERE param_key = ?",
                 (str(n), _ORDER_COUNT_PARAM))
    return n


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


def create_scenario(name: str, description: str, overrides: dict,
                    orders: list | None = None) -> dict:
    """新建场景：参数假设（overrides）与插单假设（orders）至少提供一项"""
    name = (name or "").strip()
    if not name:
        return {"ok": False, "message": "场景名称不能为空"}
    values, err = validate_global_params(overrides or {})
    if err:
        return {"ok": False, "message": err}
    conn = _conn()
    try:
        order_list, oerr = _validate_orders(conn, orders)
    finally:
        conn.close()
    if oerr:
        return {"ok": False, "message": f"插单校验失败: {oerr}"}
    if not values and not order_list:
        return {"ok": False, "message": "请至少设置一项假设：参数覆盖或插单订单"}
    sc = {"id": uuid.uuid4().hex[:8], "name": name,
          "description": (description or "").strip(), "overrides": values,
          "orders": order_list, "status": "draft", "created_at": _now()}
    _save_scenario(sc)
    return {"ok": True, "scenario": sc}


def update_scenario(sid: str, name: str, description: str, overrides: dict,
                    orders: list | None = None) -> dict:
    """更新场景。

    orders=None 表示不修改插单假设（沿用原值）；orders=[] 表示清空插单假设。
    """
    sc = _load_scenario(sid)
    if not sc:
        return {"ok": False, "message": "场景不存在"}
    if sc.get("status") == "running":
        return {"ok": False, "message": "场景运行中，暂不可编辑"}
    values, err = validate_global_params(overrides or {})
    if err:
        return {"ok": False, "message": err}
    if orders is None:
        order_list = [dict(o) for o in (sc.get("orders") or [])]
    else:
        conn = _conn()
        try:
            order_list, oerr = _validate_orders(conn, orders)
        finally:
            conn.close()
        if oerr:
            return {"ok": False, "message": f"插单校验失败: {oerr}"}
    if not values and not order_list:
        return {"ok": False, "message": "请至少设置一项假设：参数覆盖或插单订单"}
    if (name or "").strip():
        sc["name"] = name.strip()
    sc["description"] = (description or "").strip()
    sc["overrides"] = values
    sc["orders"] = order_list
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
# 沙盒运行：快照（参数 + 待注入订单行）→ 应用假设 → 求解 → 恢复 → 关联 run_id
# ---------------------------------------------------------------------------
def _write_active(scenario_id: str, snapshot_rows: list, order_snapshot: dict | None = None) -> None:
    """写运行期快照状态文件（_active.json）。

    order_snapshot = {"ids": [待注入订单号], "rows": [这些订单号上原有行]}，
    用于求解结束后精确删除注入行（并还原被占用的原行）。
    """
    WHATIF_DIR.mkdir(parents=True, exist_ok=True)
    _ACTIVE_FILE.write_text(json.dumps(
        {"scenario_id": scenario_id, "snapshot": snapshot_rows,
         "orders": order_snapshot or {"ids": [], "rows": []}, "started_at": _now()},
        ensure_ascii=False), encoding="utf-8")


def _restore_snapshot() -> bool:
    """按 _active.json 恢复沙盒改动（参数快照 + 删除插单行）；成功或无文件返回 True"""
    if not _ACTIVE_FILE.exists():
        return True
    try:
        data = json.loads(_ACTIVE_FILE.read_text(encoding="utf-8"))
        # 元组顺序与 SQL 列顺序 (param_key, param_value, description) 严格一致
        rows = [(r["param_key"], r["param_value"], r["description"])
                for r in data.get("snapshot") or []]
        o_snap = data.get("orders") or {}
        oids = [int(i) for i in (o_snap.get("ids") or [])]
        orows = [list(r) for r in (o_snap.get("rows") or [])]
        if not rows and not oids:
            _ACTIVE_FILE.unlink()
            return True
        conn = sqlite3.connect(_DB_PATH)
        try:
            conn.execute("BEGIN")
            if oids:
                ph = ",".join("?" * len(oids))
                # 先删除本次注入的订单行，再还原被占用的原有行（正常为空）
                conn.execute(f"DELETE FROM {_ORDER_TABLE} WHERE order_id IN ({ph})", oids)
                if orows:
                    ph2 = ",".join("?" * len(_ORDER_COLUMNS))
                    conn.executemany(
                        f"INSERT OR REPLACE INTO {_ORDER_TABLE} ({', '.join(_ORDER_COLUMNS)}) "
                        f"VALUES ({ph2})", orows)
            if rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO core_biz_global_params "
                    "(param_key, param_value, description) VALUES (?, ?, ?)", rows)

            # 校验恢复结果（提交前校验：不一致则回滚，快照文件保留待下次重试）
            if rows:
                marks = [r[0] for r in rows]
                ph = ",".join("?" * len(marks))
                cur = conn.execute(
                    f"SELECT param_key, param_value FROM core_biz_global_params WHERE param_key IN ({ph})",
                    marks)
                actual = dict(cur.fetchall())
                expect = {r[0]: r[1] for r in rows}
                if actual != expect:
                    raise RuntimeError(f"参数恢复不一致: { {k: (expect[k], actual.get(k)) for k in expect if actual.get(k) != expect[k]} }")
            if oids:
                ph = ",".join("?" * len(oids))
                cur = conn.execute(
                    f"SELECT order_id FROM {_ORDER_TABLE} WHERE order_id IN ({ph})", oids)
                left = {r[0] for r in cur.fetchall()}
                want = {int(r[0]) for r in orows}
                if left != want:
                    raise RuntimeError(f"插单行恢复不一致: 残留 {sorted(left - want)}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _ACTIVE_FILE.unlink()
        return True
    except Exception:
        return False


def ensure_params_restored() -> None:
    """服务重启/异常中断后的安全恢复：存在遗留快照则立即还原参数与订单表"""
    _restore_snapshot()


def _latest_run_id() -> int | None:
    conn = _conn()
    try:
        row = conn.execute("SELECT MAX(run_id) FROM res_solve_run").fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def run_scenario(sid: str) -> dict:
    """沙盒运行：快照 → 覆盖参数 → 注入插单 → 求解 → 恢复快照 → 关联 run_id"""
    sc = _load_scenario(sid)
    if not sc:
        return {"started": False, "message": "场景不存在"}
    if sc.get("status") == "running" or is_solve_running():
        return {"started": False, "message": "已有排产任务正在运行"}
    values, err = validate_global_params(sc.get("overrides") or {})
    if err:
        return {"started": False, "message": f"场景参数校验失败: {err}"}

    # 1) 快照：当前全部参数（含 description，保证完整恢复）+ 待注入订单号上已有的行
    conn = _conn()
    try:
        # 运行期重新校验插单（场景创建后产品库/参数可能已变化）
        orders, oerr = _validate_orders(conn, sc.get("orders") or [])
        if oerr:
            return {"started": False, "message": f"场景插单校验失败: {oerr}"}
        snapshot_rows = [dict(r) for r in conn.execute(
            "SELECT param_key, param_value, description FROM core_biz_global_params")]
        order_ids = _next_order_ids(conn, len(orders))
        order_rows = _order_rows_by_ids(conn, order_ids)
    finally:
        conn.close()
    baseline_run_id = _latest_run_id()
    _write_active(sid, snapshot_rows, {"ids": order_ids, "rows": order_rows})

    # 2) 应用假设参数（UPDATE 数据行，复用 /params 校验与写入；无参数假设则跳过）
    if values:
        apply_res = update_global_params(values)
        if not apply_res.get("updated"):
            _restore_snapshot()
            return {"started": False, "message": apply_res.get("message", "假设参数应用失败")}

    # 3) 注入插单（订单行 + 同步订单数参数；任一步失败即整体回滚）
    n_ord = None
    if orders:
        conn = _conn()
        try:
            _apply_orders(conn, orders, order_ids)
            n_ord = _sync_order_count(conn)
            conn.commit()
        except Exception as e:
            conn.rollback()
            _restore_snapshot()
            return {"started": False, "message": f"插单写入失败: {e}"}
        finally:
            conn.close()

    # 4) 启动沙盒求解（独立日志，完成回调恢复参数/订单行并关联版本）
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
        # 启动失败（如被其他实例占用）：立即恢复参数/订单行与场景状态
        _restore_snapshot()
        sc["status"] = "draft"
        _save_scenario(sc)
        return res
    tail = f"；已插单 {len(orders)} 条，订单总数 {n_ord}" if orders else ""
    return {"started": True, "message": f"场景「{sc['name']}」沙盒求解已启动（PID {res.get('pid')}{tail}）"}


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
