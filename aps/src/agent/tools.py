"""APS Agent 工具层

将现有 Service API 封装为 LLM Function Calling 可调用的标准化工具。
每个工具包含：名称、描述、参数 JSON Schema、执行函数。
"""
import sqlite3
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# 数据库路径（与 config.DB_PATH 一致）
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # agent → src → 项目根
_DB_PATH = str(_PROJECT_ROOT / "data" / "db" / "aps_or.db")


def _get_conn() -> sqlite3.Connection:
    """创建一个新的数据库连接（工具执行后关闭）"""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _round_float(v, digits=1):
    if v is None:
        return None
    return round(float(v), digits)


# ===========================================================================
# 工具实现
# ===========================================================================

def _tool_query_params(args: dict) -> dict:
    """查询排产全局参数，按分组返回"""
    from app.services.edit_service import get_global_params
    conn = _get_conn()
    try:
        groups = get_global_params(conn)
        # 精简输出：只保留 key/value/description/hint
        result = []
        for g in groups:
            items = [{"key": i["key"], "value": i["value"],
                      "description": i.get("description", ""),
                      "hint": i.get("hint", "")} for i in g["items"]]
            result.append({"group": g["label"], "items": items})
        return {"params": result}
    finally:
        conn.close()


def _tool_update_params(args: dict) -> dict:
    """修改排产参数（键值对），返回修改结果"""
    from app.services.edit_service import update_global_params
    payload = args.get("params", {})
    if not payload:
        return {"ok": False, "message": "未提供任何参数"}
    return update_global_params(payload)


def _tool_query_orders(args: dict) -> dict:
    """查询需求订单列表"""
    conn = _get_conn()
    try:
        search = args.get("search", "")
        sql = """SELECT order_id, product_code, price, quantity, due_period,
                       priority_level, max_delay_allowed, delay_penalty
                FROM core_biz_demand_order"""
        params = []
        if search:
            sql += " WHERE CAST(order_id AS TEXT) LIKE ? OR product_code LIKE ?"
            params = [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY order_id"
        rows = conn.execute(sql, params).fetchall()
        orders = [dict(r) for r in rows]
        return {"orders": orders, "total": len(orders)}
    finally:
        conn.close()


def _tool_update_order(args: dict) -> dict:
    """修改订单字段（订单号必填，可改数量/交期/优先级等）"""
    from app.services.edit_service import update_row
    order_id = args.get("order_id")
    if order_id is None:
        return {"ok": False, "message": "必须提供 order_id"}
    fields = args.get("fields", {})
    if not fields:
        return {"ok": False, "message": "未提供修改字段"}
    conn = _get_conn()
    try:
        return update_row(conn, "core_biz_demand_order",
                         {"order_id": int(order_id)}, fields)
    finally:
        conn.close()


def _tool_start_solve(args: dict) -> dict:
    """触发排产求解（异步，返回 PID）"""
    from app.services.analysis_service import start_solve
    return start_solve()


def _tool_get_solve_status(args: dict) -> dict:
    """查询排产求解状态"""
    from app.services.analysis_service import solve_status
    conn = _get_conn()
    try:
        status = solve_status(conn)
        # 精简输出
        return {
            "running": status.get("running", False),
            "latest_run": status.get("latest_run"),
        }
    finally:
        conn.close()


def _tool_get_result_summary(args: dict) -> dict:
    """查询最新排产结果摘要（利润、成本、准交率等核心 KPI）"""
    conn = _get_conn()
    try:
        from app.services.analysis_service import _latest_run_id
        run_id = _latest_run_id(conn)
        if run_id is None:
            return {"has_result": False, "message": "暂无排产结果"}

        s = conn.execute(
            """SELECT sales_revenue, delay_penalty, manufacturing_cost,
                      outsource_cost, purchase_cost, inventory_cost,
                      infeasible_cost, fixture_cost, profit
               FROM res_view_summary LIMIT 1""").fetchone()
        if s is None:
            return {"has_result": False, "message": "结果汇总未生成"}

        # 订单准交率
        d = conn.execute(
            """SELECT SUM(order_count_total) t, SUM(order_count_ontime) ot,
                      SUM(order_count_delayed) de, SUM(order_count_undelivered) un
               FROM res_order_delivery WHERE run_id = ?""", (run_id,)).fetchone()
        ontime_rate = round(d["ot"] / d["t"] * 100, 1) if d and d["t"] else None

        return {
            "has_result": True, "run_id": run_id,
            "revenue": _round_float(s["sales_revenue"], 0),
            "profit": _round_float(s["profit"], 0),
            "profit_rate": round(s["profit"] / s["sales_revenue"] * 100, 1) if s["sales_revenue"] else 0,
            "manufacturing_cost": _round_float(s["manufacturing_cost"], 0),
            "purchase_cost": _round_float(s["purchase_cost"], 0),
            "outsource_cost": _round_float(s["outsource_cost"], 0),
            "fixture_cost": _round_float(s["fixture_cost"], 0),
            "inventory_cost": _round_float(s["inventory_cost"], 0),
            "delay_penalty": _round_float(s["delay_penalty"], 0),
            "infeasible_cost": _round_float(s["infeasible_cost"], 0),
            "ontime_rate": ontime_rate,
            "delayed_orders": d["de"] if d else 0,
            "undelivered_orders": d["un"] if d else 0,
        }
    finally:
        conn.close()


def _tool_get_cost_analysis(args: dict) -> dict:
    """查询成本分析明细"""
    from app.services.analysis_service import get_cost_analysis
    conn = _get_conn()
    try:
        return get_cost_analysis(conn)
    finally:
        conn.close()


def _tool_get_delay_analysis(args: dict) -> dict:
    """查询延期订单分析及瓶颈归因"""
    from app.services.analysis_service import get_delay_analysis
    conn = _get_conn()
    try:
        return get_delay_analysis(conn)
    finally:
        conn.close()


def _tool_get_bottleneck_analysis(args: dict) -> dict:
    """查询设备瓶颈分析（负荷率 + 影子价格排名）"""
    from app.services.analysis_service import get_bottleneck_analysis
    conn = _get_conn()
    try:
        return get_bottleneck_analysis(conn)
    finally:
        conn.close()


def _tool_list_versions(args: dict) -> dict:
    """列出所有排产版本（含 KPI）"""
    from app.services.analysis_service import get_versions
    conn = _get_conn()
    try:
        versions = get_versions(conn)
        return {"versions": versions}
    finally:
        conn.close()


def _tool_compare_versions(args: dict) -> dict:
    """对比两个排产版本的 KPI 差异"""
    from app.services.analysis_service import get_version_compare
    run_a = args.get("run_a")
    run_b = args.get("run_b")
    if not run_a or not run_b:
        return {"ok": False, "message": "必须提供 run_a 和 run_b"}
    conn = _get_conn()
    try:
        return get_version_compare(conn, int(run_a), int(run_b))
    finally:
        conn.close()


def _tool_get_data_validation(args: dict) -> dict:
    """数据质量校验（检查 BOM 闭合、工艺路线、参数完整性等）"""
    from app.services.analysis_service import get_validation_report
    conn = _get_conn()
    try:
        checks = get_validation_report(conn)
        passed = sum(1 for c in checks if c["passed"])
        return {"total": len(checks), "passed": passed,
                "failed": len(checks) - passed, "checks": checks}
    finally:
        conn.close()


def _tool_list_whatif_scenarios(args: dict) -> dict:
    """列出所有 What-if 场景"""
    from app.services.whatif_service import list_scenarios
    scenarios = list_scenarios()
    # 精简输出
    result = []
    for s in scenarios:
        result.append({
            "id": s.get("id"), "name": s.get("name"),
            "status": s.get("status"), "description": s.get("description", ""),
            "overrides": s.get("overrides", {}),
            "run_id": s.get("run_id"),
            "baseline_run_id": s.get("baseline_run_id"),
            "created_at": s.get("created_at"),
        })
    return {"scenarios": result}


def _tool_create_whatif_scenario(args: dict) -> dict:
    """创建 What-if 假设分析场景"""
    from app.services.whatif_service import create_scenario
    name = args.get("name", "")
    description = args.get("description", "")
    overrides = args.get("overrides", {})
    return create_scenario(name, description, overrides)


def _tool_run_whatif_scenario(args: dict) -> dict:
    """运行 What-if 场景（启动沙盒求解）"""
    from app.services.whatif_service import run_scenario
    sid = args.get("scenario_id", "")
    if not sid:
        return {"started": False, "message": "必须提供 scenario_id"}
    return run_scenario(sid)


def _tool_get_inventory_analysis(args: dict) -> dict:
    """查询库存分析（三类物料库存趋势）"""
    from app.services.analysis_service import get_inventory_analysis
    conn = _get_conn()
    try:
        return get_inventory_analysis(conn)
    finally:
        conn.close()


# ===========================================================================
# 工具定义（OpenAI Function Calling 格式）
# ===========================================================================
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_params",
            "description": "查询排产全局参数（计划期长度、目标权重、求解参数等），按分组返回",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_params",
            "description": "修改排产参数。params 为键值对，可用 key 包括：PLAN_HORIZON(计划期长度), W_SALES(销售收入权重), W_DELAY(延期罚金权重), W_PURCHASE(采购成本权重), W_PROCESS(加工成本权重), W_INVENTORY(库存成本权重), SOLVE_SOLVER(求解器:gurobi/highs), SOLVE_MIPGAP(收敛精度), SOLVE_TIME_LIMIT(时间限制秒)等",
            "parameters": {
                "type": "object",
                "properties": {
                    "params": {
                        "type": "object",
                        "description": "参数键值对，如 {\"W_SALES\": 2.0, \"W_DELAY\": 1.5}",
                    }
                },
                "required": ["params"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_orders",
            "description": "查询需求订单列表（支持按订单号或产品代码搜索）",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "搜索关键词（订单号或产品代码）"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order",
            "description": "修改需求订单字段。可修改：quantity(数量), due_period(交期), priority_level(优先级), price(单价), max_delay_allowed(最大允许延期), delay_penalty(延期罚金率)",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "订单编号"},
                    "fields": {
                        "type": "object",
                        "description": "要修改的字段键值对，如 {\"quantity\": 500, \"due_period\": 8}",
                    },
                },
                "required": ["order_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_solve",
            "description": "触发排产求解（异步执行，返回启动状态和 PID）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_solve_status",
            "description": "查询排产求解状态（是否运行中、最新运行结果）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_result_summary",
            "description": "查询最新排产结果摘要（利润、成本构成、准交率等核心 KPI）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cost_analysis",
            "description": "查询成本分析明细（制造/采购/外协/工装/延期/库存成本构成）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_delay_analysis",
            "description": "查询延期订单分析（延期订单列表、瓶颈设备、影子价格）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bottleneck_analysis",
            "description": "查询设备瓶颈分析（设备负荷率排名、影子价格排名）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_versions",
            "description": "列出所有排产版本（含运行时间、状态、利润等 KPI）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_versions",
            "description": "对比两个排产版本的 KPI 差异",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_a": {"type": "integer", "description": "基准版本 run_id"},
                    "run_b": {"type": "integer", "description": "对比版本 run_id"},
                },
                "required": ["run_a", "run_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_validation",
            "description": "数据质量校验（检查 BOM 闭合、工艺路线、参数完整性、库存合理性等）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_whatif_scenarios",
            "description": "列出所有 What-if 假设分析场景",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_whatif_scenario",
            "description": "创建 What-if 假设分析场景（不立即运行，仅创建）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "场景名称"},
                    "description": {"type": "string", "description": "场景描述"},
                    "overrides": {
                        "type": "object",
                        "description": "假设参数覆盖值，如 {\"W_SALES\": 2.0}",
                    },
                },
                "required": ["name", "overrides"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_whatif_scenario",
            "description": "运行 What-if 场景（启动沙盒求解，完成后自动恢复参数）",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string", "description": "场景 ID"},
                },
                "required": ["scenario_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_analysis",
            "description": "查询库存分析（产品/自制件/原材料三类物料库存趋势）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# 工具名 → 执行函数映射
TOOL_HANDLERS = {
    "query_params": _tool_query_params,
    "update_params": _tool_update_params,
    "query_orders": _tool_query_orders,
    "update_order": _tool_update_order,
    "start_solve": _tool_start_solve,
    "get_solve_status": _tool_get_solve_status,
    "get_result_summary": _tool_get_result_summary,
    "get_cost_analysis": _tool_get_cost_analysis,
    "get_delay_analysis": _tool_get_delay_analysis,
    "get_bottleneck_analysis": _tool_get_bottleneck_analysis,
    "list_versions": _tool_list_versions,
    "compare_versions": _tool_compare_versions,
    "get_data_validation": _tool_get_data_validation,
    "list_whatif_scenarios": _tool_list_whatif_scenarios,
    "create_whatif_scenario": _tool_create_whatif_scenario,
    "run_whatif_scenario": _tool_run_whatif_scenario,
    "get_inventory_analysis": _tool_get_inventory_analysis,
}


# 需要用户在界面上二次确认才能执行的写操作工具（防止 LLM 意外修改数据/触发求解）
WRITE_TOOLS = {"update_params", "update_order", "start_solve", "run_whatif_scenario"}


def execute_tool(name: str, args: dict, confirmed: bool = False) -> dict:
    """执行工具调用，返回结果字典。

    写操作工具（WRITE_TOOLS）在 confirmed=False 时不会真正执行，
    返回 needs_confirmation 标记，由前端弹确认卡片、用户点击后
    经 /api/agent/tool/execute 以 confirmed=True 再次调用。
    """
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"未知工具: {name}"}
    if name in WRITE_TOOLS and not confirmed:
        return {
            "needs_confirmation": True,
            "tool": name,
            "args": args,
            "message": "写操作需用户在界面确认后执行",
        }
    try:
        result = handler(args or {})
        # 确保可序列化
        return _make_serializable(result)
    except Exception as e:
        return {"error": f"工具执行失败: {name} - {e}"}


def _make_serializable(obj):
    """递归将 Row/datetime 等转为可 JSON 序列化的值"""
    if isinstance(obj, sqlite3.Row):
        return _make_serializable(dict(obj))
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, set):
        return [_make_serializable(v) for v in obj]
    return obj
