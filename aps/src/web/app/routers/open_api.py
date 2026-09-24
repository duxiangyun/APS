"""APS 开放 REST API（/open/*）

将排产结果、设备负荷、订单、IIS 诊断、KPI 等封装为只读 REST 接口，
供外部系统（如 agent/ Web Agent 后端）通过 HTTP 调用。

本模块自包含：直接以只读方式访问 SQLite（config.DB_PATH），
不修改任何现有业务逻辑与数据库结构。
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from config import DB_PATH
from app.services.analysis_service import start_solve, solve_status

router = APIRouter(prefix="/open", tags=["open-api"])


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MAX(run_id) AS rid FROM res_solve_run").fetchone()
    return row["rid"] if row and row["rid"] is not None else None


def _run_info(conn: sqlite3.Connection, run_id: int | None) -> dict | None:
    if run_id is None:
        return None
    row = conn.execute(
        "SELECT * FROM res_solve_run WHERE run_id = ?", (run_id,)
    ).fetchone()
    return dict(row) if row else None


def _require_run(conn: sqlite3.Connection) -> int:
    run_id = _latest_run_id(conn)
    if run_id is None:
        raise HTTPException(status_code=404, detail="尚无排产求解结果")
    return run_id


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
@router.get("/health")
async def health(conn: sqlite3.Connection = Depends(get_conn)):
    orders = conn.execute("SELECT COUNT(*) FROM core_biz_demand_order").fetchone()[0]
    return {"status": "ok", "service": "aps", "orders": orders,
            "latest_run_id": _latest_run_id(conn)}


# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------
@router.get("/kpi/summary")
async def kpi_summary(conn: sqlite3.Connection = Depends(get_conn)):
    """最新一次求解的核心 KPI：收入 / 各项成本 / 利润"""
    run_id = _require_run(conn)
    row = conn.execute(
        """SELECT run_id, sales_revenue, delay_penalty, manufacturing_cost,
                  outsource_cost, purchase_cost, inventory_cost,
                  infeasible_cost, fixture_cost, profit
           FROM res_summary WHERE run_id = ?""", (run_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"run_id={run_id} 无汇总数据")
    return {"run": _run_info(conn, run_id), "kpi": dict(row)}


@router.get("/kpi/delivery")
async def kpi_delivery(conn: sqlite3.Connection = Depends(get_conn)):
    """按订单优先级的交付达成（准交率等）"""
    run_id = _require_run(conn)
    rows = conn.execute(
        """SELECT priority_level, order_count_total, order_count_ontime,
                  order_count_partial, order_count_delayed, order_count_undelivered,
                  quantity_total, quantity_ontime, quantity_partial,
                  quantity_delayed, quantity_undelivered
           FROM res_order_delivery WHERE run_id = ? ORDER BY priority_level""",
        (run_id,),
    ).fetchall()
    total = sum(r["order_count_total"] or 0 for r in rows)
    ontime = sum(r["order_count_ontime"] or 0 for r in rows)
    return {
        "run_id": run_id,
        "ontime_rate": round(ontime / total * 100, 2) if total else None,
        "by_priority": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# 订单
# ---------------------------------------------------------------------------
@router.get("/orders")
async def orders(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """需求订单列表（支持订单号/产品编码模糊搜索 + 分页）"""
    where, params = "", []
    if search:
        where = "WHERE CAST(order_id AS TEXT) LIKE ? OR product_code LIKE ?"
        params = [f"%{search}%", f"%{search}%"]
    total = conn.execute(
        f"SELECT COUNT(*) FROM core_biz_demand_order {where}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT * FROM core_biz_demand_order {where}
            ORDER BY order_id LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"total": total, "page": page, "page_size": page_size,
            "orders": [dict(r) for r in rows]}


@router.get("/orders/{order_id}")
async def order_detail(order_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute(
        "SELECT * FROM core_biz_demand_order WHERE order_id = ?", (order_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    return {"order": dict(row)}

# ---------------------------------------------------------------------------
# 排产结果
# ---------------------------------------------------------------------------
@router.get("/results/runs")
async def result_runs(conn: sqlite3.Connection = Depends(get_conn)):
    """历史求解批次列表"""
    rows = conn.execute(
        "SELECT * FROM res_solve_run ORDER BY run_id DESC LIMIT 50"
    ).fetchall()
    return {"runs": [dict(r) for r in rows]}


@router.get("/results/views")
async def result_views(conn: sqlite3.Connection = Depends(get_conn)):
    """可查询的结果视图清单（res_view_*）及行数（最新批次）"""
    run_id = _latest_run_id(conn)
    names = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'res_view_%' "
        "ORDER BY name"
    ).fetchall()]
    views = []
    for n in names:
        try:
            sql = f'SELECT COUNT(*) FROM "{n}"'
            if run_id is not None:
                cols = [c[0] for c in conn.execute(f'SELECT * FROM "{n}" LIMIT 0').description]
                if "run_id" in cols:
                    sql = f'SELECT COUNT(*) FROM "{n}" WHERE run_id = {int(run_id)}'
            count = conn.execute(sql).fetchone()[0]
        except sqlite3.Error:
            count = None
        views.append({"view": n, "rows": count})
    return {"latest_run_id": run_id, "views": views}


@router.get("/results/{view_key}")
async def result_data(
    view_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """通用排产结果明细查询，view_key 为 res_view_* 视图名（可省略前缀）"""
    if not view_key.startswith("res_view_"):
        view_key = "res_view_" + view_key
    ok = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name = ?", (view_key,)
    ).fetchone()
    if not ok:
        raise HTTPException(status_code=404, detail=f"结果视图 '{view_key}' 不存在")

    run_id = _latest_run_id(conn)
    cols = [c[0] for c in conn.execute(f'SELECT * FROM "{view_key}" LIMIT 0').description]
    where, params = "", []
    if "run_id" in cols:
        where, params = "WHERE run_id = ?", [run_id]
    total = conn.execute(f'SELECT COUNT(*) FROM "{view_key}" {where}', params).fetchone()[0]
    rows = conn.execute(
        f'SELECT * FROM "{view_key}" {where} LIMIT ? OFFSET ?',
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"view": view_key, "run_id": run_id, "total": total,
            "page": page, "page_size": page_size,
            "columns": cols, "rows": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# 设备负荷
# ---------------------------------------------------------------------------
@router.get("/equip-load")
async def equip_load(conn: sqlite3.Connection = Depends(get_conn)):
    """最新批次的设备负荷：各周期负荷矩阵 + 明细时间序列"""
    run_id = _require_run(conn)
    matrix = conn.execute("SELECT * FROM res_view_equip_load").fetchall()
    detail = conn.execute(
        """SELECT resource_code, period, load FROM res_workload
           WHERE run_id = ? ORDER BY resource_code, period""", (run_id,)
    ).fetchall()
    return {"run_id": run_id,
            "matrix": [dict(r) for r in matrix],
            "detail": [dict(r) for r in detail]}


# ---------------------------------------------------------------------------
# IIS（不可约不可行子系统）诊断
# ---------------------------------------------------------------------------
_INF_TYPE_LABELS = {
    "PRODUCT": "产品供给缺口", "SELF": "自制件供给缺口", "RAW": "原材料供给缺口",
    "EQUIP": "设备能力不足", "FIXT": "工装能力不足", "SALE": "订单交付缺口",
}


@router.get("/iis")
async def iis(
    inf_type: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    """最新批次的不可行（IIS）诊断记录，可按 inf_type 过滤"""
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"run_id": None, "total": 0, "items": []}
    where, params = "WHERE run_id = ?", [run_id]
    if inf_type:
        where += " AND inf_type = ?"
        params.append(inf_type)
    rows = conn.execute(
        f"""SELECT inf_type, resource_code, period, quantity
            FROM res_infeasible {where}
            ORDER BY inf_type, resource_code, period""", params
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["label"] = _INF_TYPE_LABELS.get(r["inf_type"], r["inf_type"])
        items.append(d)
    return {"run_id": run_id, "total": len(items), "items": items}


# ---------------------------------------------------------------------------
# 排产求解（复用现有 analysis_service，不做逻辑改动）
# ---------------------------------------------------------------------------
@router.post("/solve/start")
async def solve_start():
    """触发一次排产求解（异步，启动子进程）"""
    return start_solve()


@router.get("/solve/status")
async def solve_status_api(conn: sqlite3.Connection = Depends(get_conn)):
    """查询求解状态与最近批次"""
    return solve_status(conn)
