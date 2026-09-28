"""APS 开放 REST API（/open/*）

将排产结果、设备负荷、订单、主数据、IIS 诊断、KPI 等封装为只读 REST 接口，
供外部系统（如 agent/ Web Agent 后端）通过 HTTP 调用。

本模块自包含：直接以只读方式访问 SQLite（config.DB_PATH），
不修改任何现有业务逻辑与数据库结构。

接口分区：
  - /open/health            健康检查
  - /open/kpi/*             最新批次 KPI（收入/成本/利润、按优先级交付达成）
  - /open/orders*           需求订单（core_biz_demand_order）
  - /open/results/*         排产结果（res_solve_run / res_view_*）
  - /open/equip-load        设备负荷
  - /open/iis               IIS（不可行子系统）诊断
  - /open/md/*              主数据只读接口（物料 / BOM / 工艺路线 / 设备台账），
                            供 Agent 的 masterdata 角色核对基础数据一致性
  - /open/solve/*           排产求解触发与状态（唯一写语义入口，复用 analysis_service）

本模块全部为只读接口（/open/solve/start 仅触发既有求解流程，不直接写库）；
主数据的写操作仍走 APS Web 页面的 /api/edit/{table}/*，此处不提供任何写接口。
"""
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query

from config import DB_PATH
from app.services.analysis_service import start_solve, solve_status

router = APIRouter(prefix="/open", tags=["open-api"])


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# 主数据接口专用连接：URI 只读模式（mode=ro），物理上无法执行写操作
_MD_RO_URI = f"file:{quote(DB_PATH)}?mode=ro"


def get_md_conn() -> sqlite3.Connection:
    """主数据只读连接（/open/md/* 专用）

    使用 SQLite URI 只读模式打开：即使上层漏改代码，写操作也会被 DB 拒绝，
    不会影响 aps_or.db 的结构与数据（符合"只读开放接口"约束）。
    """
    conn = sqlite3.connect(_MD_RO_URI, uri=True, check_same_thread=False)
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
# 主数据只读接口（/open/md/*）
#   供 Agent（masterdata 角色）核对物料 / BOM / 工艺路线 / 设备台账等基础数据。
#   - 全部为 GET，仅执行 SELECT，使用只读连接（get_md_conn，mode=ro）
#   - 字段名与数据库真实列名一致（见 app/constants.py COLUMN_DISPLAY_ORDER）
#   - 必填参数缺失 → 400；查询无结果 → 空列表（不返回 404）
#   - 主数据写操作不在此处提供，仍走 APS Web 页面的 /api/edit/{table}/*
# ---------------------------------------------------------------------------

# 物料主数据字段（core_md_material 真实列名）
_MD_MATERIAL_COLS = (
    "material_code, material_name, category, unit, initial_inventory, "
    "target_end_inventory, min_inventory, max_inventory, holding_cost_rate"
)


@router.get("/md/materials")
async def md_materials(
    code: str = "",
    search: str = "",
    category: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_md_conn),
):
    """物料主数据列表（core_md_material）：编码精确查 + 名称/编码模糊查 + 分类过滤 + 分页

    - code：物料编码精确匹配
    - search：物料编码 / 物料名称模糊匹配
    - category：物料分类精确匹配（大小写不敏感；数据中为 PRODUCT / SEMI / RAW）
    - page / page_size：分页（page_size 上限 500）
    返回 {items, total, page, page_size}；无匹配时 items 为空列表。
    """
    where, params = [], []
    if code:
        where.append("material_code = ?")
        params.append(code)
    if search:
        where.append("(material_code LIKE ? OR material_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category:
        where.append("UPPER(category) = UPPER(?)")
        params.append(category)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM core_md_material {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT {_MD_MATERIAL_COLS} FROM core_md_material {where_sql} "
        f"ORDER BY material_code LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [dict(r) for r in rows]}


# BOM 展开 SQL：与 /api/biz/bom/tree（app/routers/api.py 的 BOM 树接口）保持同一套
# JOIN 写法（core_biz_bom 左连 core_md_material 取父/子名称与分类），此处额外取子件单位
_MD_BOM_SQL = (
    "SELECT b.id, b.parent_material_code, b.child_material_code, b.quantity, b.bom_level, "
    "pm.material_name AS parent_name, pm.category AS parent_cat, "
    "cm.material_name AS child_name, cm.category AS child_cat, cm.unit AS child_unit "
    "FROM core_biz_bom b "
    "LEFT JOIN core_md_material pm ON pm.material_code = b.parent_material_code "
    "LEFT JOIN core_md_material cm ON cm.material_code = b.child_material_code "
    "ORDER BY b.bom_level, b.parent_material_code, b.child_material_code"
)


@router.get("/md/bom")
async def md_bom(
    parent_material_code: str = "",
    max_level: int = Query(5, ge=1, le=10),
    conn: sqlite3.Connection = Depends(get_md_conn),
):
    """多级 BOM 树（core_biz_bom LEFT JOIN core_md_material），从指定父物料向下展开

    - parent_material_code（必填）：展开起点物料编码，缺失返回 400
    - max_level：向下展开的最大层数（默认 5，上限 10），超出部分不再展开（truncated=true）

    返回 {material_code, material_name, max_level, total, truncated, tree, items}：
      - tree：嵌套树，根节点为 parent_material_code（level=0，children 为各层子件）
      - items：同内容的平铺列表（按 level 升序，同层按父/子编码排序），每层含 level /
        parent_code / child_code / child_name / child_category / unit / quantity / bom_level
      - truncated：是否因 max_level 限制而截断（被截断节点仍可见，只是不再展开其子件）
    多级树构建方式与 /api/biz/bom/tree 一致（按父物料分组 + 递归展开），并加了循环 BOM 保护。
    物料不在 BOM 中时返回空 items（不返回 404）。
    """
    root = (parent_material_code or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="缺少必填参数 parent_material_code")

    rows = conn.execute(_MD_BOM_SQL).fetchall()
    root_row = conn.execute(
        "SELECT material_code, material_name, category, unit FROM core_md_material "
        "WHERE material_code = ?", (root,)
    ).fetchone()

    children_map: dict[str, list[dict]] = {}
    for r in rows:
        children_map.setdefault(r["parent_material_code"], []).append({
            "code": r["child_material_code"],
            "name": r["child_name"] or "",
            "category": r["child_cat"] or "",
            "unit": r["child_unit"] or "",
            "quantity": r["quantity"],
            "bom_level": r["bom_level"],
        })

    flat: list[dict] = []

    def walk(code: str, level: int, seen: frozenset) -> list[dict]:
        """递归展开子件；seen 用于阻断异常循环 BOM"""
        if level >= max_level:
            return []
        nodes = []
        for k in children_map.get(code, []):
            node = {
                "level": level + 1,
                "parent_code": code,
                "child_code": k["code"],
                "child_name": k["name"],
                "child_category": k["category"],
                "unit": k["unit"],
                "quantity": k["quantity"],
                "bom_level": k["bom_level"],
                "children": [],
            }
            if k["code"] not in seen:
                node["children"] = walk(k["code"], level + 1, seen | {k["code"]})
            nodes.append(node)
            flat.append({kk: vv for kk, vv in node.items() if kk != "children"})
        return nodes

    children = walk(root, 0, frozenset({root}))
    # 平铺列表按层级排序（同层按父/子编码），便于 Agent 逐层核对
    flat.sort(key=lambda n: (n["level"], n["parent_code"], n["child_code"]))
    tree = {
        "code": root,
        "name": root_row["material_name"] if root_row else "",
        "category": root_row["category"] if root_row else "",
        "unit": root_row["unit"] if root_row else "",
        "level": 0,
        "quantity": 1,
        "children": children,
    }
    truncated = any(n["level"] >= max_level and children_map.get(n["child_code"])
                    for n in flat)
    return {"material_code": root, "material_name": tree["name"],
            "max_level": max_level, "total": len(flat), "truncated": truncated,
            "tree": tree, "items": flat}


# 工艺路线 SQL：header → step → operation（工序主数据），设备用 LEFT JOIN
# （设备缺失时 equipment_name 为 null，便于 masterdata 角色识别待维护项）
_MD_ROUTING_SQL = (
    "SELECT h.routing_id, h.material_code, h.alt_route_id, h.total_lead_time, "
    "h.is_default, h.is_active, "
    "s.step_id, s.step_order, s.operation_code, s.equipment_code, "
    "s.production_line_code, s.fixture_code, s.fixture_quantity, s.max_lead_time, "
    "o.operation_name, "
    "r.resource_name AS equipment_name, r.resource_type AS equipment_type, "
    "r.line_code AS equipment_line_code "
    "FROM core_biz_routing_header h "
    "JOIN core_biz_routing_step s ON s.routing_id = h.routing_id "
    "JOIN core_md_operation o ON o.operation_code = s.operation_code "
    "LEFT JOIN core_md_resource r ON r.resource_code = s.equipment_code "
    "WHERE h.material_code = ?"
)


@router.get("/md/routing")
async def md_routing(
    material_code: str = "",
    routing_id: int | None = Query(None),
    conn: sqlite3.Connection = Depends(get_md_conn),
):
    """工艺路线（routing_header JOIN routing_step JOIN core_md_operation LEFT JOIN core_md_resource）

    - material_code（必填）：物料编码，缺失返回 400（同一物料可能有多条路线，见 routes）
    - routing_id（可选）：只返回指定路线

    返回 {material_code, routing_id, route_count, total, routes, steps}：
      - routes：按路线分组的工序明细（含 routing_id / alt_route_id / total_lead_time /
        is_default / is_active / step_count / steps）
      - steps：全部命中路线的工序平铺列表（便于 Agent 直接遍历）
      每个工序含 step_order（= 需求中的 step_no，数据库真实列名为 step_order）、
      operation_code / operation_name / equipment_code / equipment_name / equipment_type /
      production_line_code / fixture_code / fixture_quantity / max_lead_time。
    工序必须存在于 core_md_operation（JOIN）；设备允许缺失（LEFT JOIN）。
    无该物料的工艺路线时返回空 routes / steps（不返回 404）。
    """
    code = (material_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="缺少必填参数 material_code")

    sql, params = _MD_ROUTING_SQL, [code]
    if routing_id is not None:
        sql += " AND h.routing_id = ?"
        params.append(routing_id)
    sql += " ORDER BY h.is_default DESC, h.routing_id, s.step_order"
    rows = conn.execute(sql, params).fetchall()

    routes: list[dict] = []
    steps: list[dict] = []
    by_id: dict[int, dict] = {}
    for r in rows:
        rid = r["routing_id"]
        route = by_id.get(rid)
        if route is None:
            route = {
                "routing_id": rid, "material_code": r["material_code"],
                "alt_route_id": r["alt_route_id"], "total_lead_time": r["total_lead_time"],
                "is_default": r["is_default"], "is_active": r["is_active"],
                "step_count": 0, "steps": [],
            }
            by_id[rid] = route
            routes.append(route)
        step = {
            "routing_id": rid,
            "step_id": r["step_id"],
            "step_order": r["step_order"],
            "step_no": r["step_order"],
            "operation_code": r["operation_code"],
            "operation_name": r["operation_name"],
            "equipment_code": r["equipment_code"],
            "equipment_name": r["equipment_name"],
            "equipment_type": r["equipment_type"],
            "production_line_code": r["production_line_code"],
            "resource_line_code": r["equipment_line_code"],
            "fixture_code": r["fixture_code"],
            "fixture_quantity": r["fixture_quantity"],
            "max_lead_time": r["max_lead_time"],
        }
        route["steps"].append(step)
        route["step_count"] = len(route["steps"])
        steps.append(step)

    return {"material_code": code, "routing_id": routing_id,
            "route_count": len(routes), "total": len(steps),
            "routes": routes, "steps": steps}


# 设备/工装资源类型别名（Agent 可用中文类型名查询）
_MD_RESOURCE_TYPE_ALIAS = {"设备": "EQUIPMENT", "工装": "FIXTURE", "产线": "LINE"}

# 资源台账字段（core_md_resource 真实列名） + 所属产线信息
_MD_RESOURCE_COLS = (
    "r.resource_code, r.resource_name, r.resource_type, r.line_code, r.quantity, "
    "r.unit_cost, r.utilization_rate, r.overtime_rate, r.overtime_cost_multiplier, "
    "l.line_name, l.line_type"
)


@router.get("/md/resources")
async def md_resources(
    code: str = "",
    type: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_md_conn),
):
    """设备/工装台账（core_md_resource LEFT JOIN core_md_line）：编码查 + 类型过滤 + 分页

    - code：资源编码精确匹配
    - type：资源类型精确匹配（大小写不敏感），支持数据库值 EQUIPMENT / FIXTURE
      与中文别名 设备 / 工装 / 产线
    - page / page_size：分页（page_size 上限 500）
    返回 {items, total, page, page_size}；字段含 resource_code / resource_name /
    resource_type / line_code / line_name / line_type / quantity / unit_cost /
    utilization_rate / overtime_rate / overtime_cost_multiplier。
    无匹配时 items 为空列表。
    """
    where, params = [], []
    if code:
        where.append("r.resource_code = ?")
        params.append(code)
    if type:
        where.append("UPPER(r.resource_type) = UPPER(?)")
        params.append(_MD_RESOURCE_TYPE_ALIAS.get(type, type))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    base = "FROM core_md_resource r LEFT JOIN core_md_line l ON l.line_code = r.line_code"
    total = conn.execute(
        f"SELECT COUNT(*) {base} {where_sql}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT {_MD_RESOURCE_COLS} {base} {where_sql} "
        f"ORDER BY r.resource_code LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [dict(r) for r in rows]}


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
