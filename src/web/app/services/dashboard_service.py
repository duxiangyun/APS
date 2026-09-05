"""工作台数据聚合服务

全部为只读查询，数据源为结果视图（res_view_*）与变量表（res_*），
不新增/修改任何数据库结构。
"""
import sqlite3

EPS = 1e-4

# 不可行松弛量类型 → 中文含义（与写入端 inf_type 枚举一致）
INF_TYPE_LABELS = {
    "PRODUCT": ("产品", "产品供给缺口（生产+库存无法平衡）"),
    "SELF": ("自制件", "自制件供给缺口（生产+库存+外协无法平衡）"),
    "RAW": ("原材料", "原材料供给缺口（采购+库存无法平衡）"),
    "EQUIP": ("设备", "设备能力不足"),
    "FIXT": ("工装", "工装能力不足"),
    "SALE": ("订单", "订单交付缺口（无法足额交付）"),
}


def _latest_run_id(conn: sqlite3.Connection):
    row = conn.execute("SELECT MAX(run_id) FROM res_solve_run").fetchone()
    return row[0] if row and row[0] is not None else None


def _fmt_money(v):
    if v is None:
        return "-"
    return f"{v:,.0f}"


def _fmt_pct(v):
    if v is None:
        return "-"
    return f"{v:.1f}%"


def get_run_info(conn: sqlite3.Connection) -> dict | None:
    """最近一次求解批次信息"""
    row = conn.execute(
        """SELECT run_id, run_time, status, solve_time_ms, mip_gap, objective, nperiod
           FROM res_solve_run ORDER BY run_id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "run_time": row["run_time"],
        "status": row["status"],
        "solve_time_s": round(row["solve_time_ms"] / 1000, 1) if row["solve_time_ms"] is not None else None,
        "mip_gap_pct": round(row["mip_gap"] * 100, 2) if row["mip_gap"] is not None else None,
        "objective": row["objective"],
        "nperiod": row["nperiod"],
    }


def get_kpis(conn: sqlite3.Connection) -> dict:
    """KPI 卡片数据：交付、收入、成本、设备负荷"""
    kpi = {
        "order_total": 0, "order_ontime": 0, "order_partial": 0,
        "order_delayed": 0, "order_undelivered": 0,
        "qty_total": 0.0, "qty_ontime": 0.0,
        "sales_revenue": None, "profit": None, "profit_rate_pct": None,
        "delay_penalty": None, "infeasible_cost": None,
        "equip_avg_load_pct": None, "equip_max_load_pct": None, "bottleneck_equip": None,
        "ontime_rate_pct": None, "qty_ontime_rate_pct": None,
    }

    # 订单交付分级汇总（res_view_order_delivery）
    row = conn.execute(
        """SELECT SUM(order_count_total) t, SUM(order_count_ontime) ot,
                  SUM(order_count_partial) pa, SUM(order_count_delayed) de,
                  SUM(order_count_undelivered) un,
                  SUM(quantity_total) qt, SUM(quantity_ontime) qo
           FROM res_view_order_delivery"""
    ).fetchone()
    if row and row["t"]:
        kpi["order_total"] = row["t"]
        kpi["order_ontime"] = row["ot"] or 0
        kpi["order_partial"] = row["pa"] or 0
        kpi["order_delayed"] = row["de"] or 0
        kpi["order_undelivered"] = row["un"] or 0
        kpi["qty_total"] = row["qt"] or 0.0
        kpi["qty_ontime"] = row["qo"] or 0.0
        kpi["ontime_rate_pct"] = round(kpi["order_ontime"] / kpi["order_total"] * 100, 1)
        if kpi["qty_total"] > 0:
            kpi["qty_ontime_rate_pct"] = round(kpi["qty_ontime"] / kpi["qty_total"] * 100, 1)

    # 财务汇总（res_view_summary）
    s = conn.execute(
        """SELECT sales_revenue, profit, delay_penalty, infeasible_cost
           FROM res_view_summary LIMIT 1"""
    ).fetchone()
    if s:
        kpi["sales_revenue"] = s["sales_revenue"]
        kpi["profit"] = s["profit"]
        kpi["delay_penalty"] = s["delay_penalty"]
        kpi["infeasible_cost"] = s["infeasible_cost"]
        if s["sales_revenue"]:
            kpi["profit_rate_pct"] = round(s["profit"] / s["sales_revenue"] * 100, 1)

    # 设备负荷（res_view_equip_load 已算好 max/avg 负荷率）
    erows = conn.execute(
        """SELECT resource_code, max_load_rate_pct, avg_load_rate_pct
           FROM res_view_equip_load"""
    ).fetchall()
    if erows:
        rates = [r["avg_load_rate_pct"] for r in erows if r["avg_load_rate_pct"] is not None]
        if rates:
            kpi["equip_avg_load_pct"] = round(sum(rates) / len(rates), 1)
        top = max(erows, key=lambda r: r["max_load_rate_pct"] or 0)
        kpi["equip_max_load_pct"] = round(top["max_load_rate_pct"], 1)
        kpi["bottleneck_equip"] = top["resource_code"]

    # 展示格式化
    kpi["display"] = {
        "sales_revenue": _fmt_money(kpi["sales_revenue"]),
        "profit": _fmt_money(kpi["profit"]),
        "profit_rate_pct": _fmt_pct(kpi["profit_rate_pct"]),
        "delay_penalty": _fmt_money(kpi["delay_penalty"]),
        "ontime_rate_pct": _fmt_pct(kpi["ontime_rate_pct"]),
        "qty_ontime_rate_pct": _fmt_pct(kpi["qty_ontime_rate_pct"]),
        "equip_avg_load_pct": _fmt_pct(kpi["equip_avg_load_pct"]),
        "equip_max_load_pct": _fmt_pct(kpi["equip_max_load_pct"]),
    }
    return kpi


def get_warnings(conn: sqlite3.Connection) -> list[dict]:
    """异常告警列表，按严重程度排序：danger > warning > info"""
    warnings = []
    run_id = _latest_run_id(conn)
    if run_id is None:
        return warnings

    # 1) 不可行松弛量（产能/物料/交付缺口，罚成本 1e6/单位，最高级别）
    inf_rows = conn.execute(
        """SELECT inf_type, COUNT(*) n, ROUND(SUM(quantity),2) qty
           FROM res_infeasible WHERE run_id = ?
           GROUP BY inf_type ORDER BY inf_type""",
        (run_id,),
    ).fetchall()
    for r in inf_rows:
        label, desc = INF_TYPE_LABELS.get(r["inf_type"], (r["inf_type"], r["inf_type"]))
        warnings.append({
            "level": "danger", "icon": "fa-ban",
            "title": f"{desc}（{r['inf_type']}）",
            "detail": f"共 {r['n']} 条松弛记录，松弛量合计 {r['qty']:g}",
            "link": "/res/inf_equip" if r["inf_type"] == "EQUIP" else None,
        })

    # 2) 未交付订单
    undelivered = conn.execute(
        """SELECT DISTINCT order_id FROM res_view_order_sale
           WHERE delivery_status LIKE '%未交付%' ORDER BY order_id"""
    ).fetchall()
    if undelivered:
        ids = "、".join(str(r["order_id"]) for r in undelivered)
        warnings.append({
            "level": "danger", "icon": "fa-times-circle",
            "title": f"{len(undelivered)} 张订单未交付",
            "detail": f"订单号：{ids}",
            "link": "/res/order_sale",
        })

    # 3) 延期交付订单（实际交付期 > 交期）
    delayed = conn.execute(
        """SELECT order_id, MIN(due_period) due, MAX(delivery_period) delivered,
                  ROUND(SUM(delay_penalty),2) penalty, SUM(delay_quantity) dqty
           FROM res_view_order_sale
           WHERE delivery_period > due_period
           GROUP BY order_id ORDER BY penalty DESC"""
    ).fetchall()
    for r in delayed:
        warnings.append({
            "level": "warning", "icon": "fa-clock",
            "title": f"订单 {r['order_id']} 延期 {r['delivered'] - r['due']} 期交付",
            "detail": f"交期第 {r['due']} 期 → 实际第 {r['delivered']} 期，"
                      f"延期罚金 ¥{r['penalty']:,.0f}" + (f"，延期量 {r['dqty']:g}" if r["dqty"] and r["dqty"] > EPS else ""),
            "link": "/res/order_sale",
        })

    # 4) 部分按期交付
    partial = conn.execute(
        """SELECT DISTINCT order_id FROM res_view_order_sale
           WHERE delivery_status LIKE '%部分%' ORDER BY order_id"""
    ).fetchall()
    if partial:
        ids = "、".join(str(r["order_id"]) for r in partial)
        warnings.append({
            "level": "warning", "icon": "fa-adjust",
            "title": f"{len(partial)} 张订单部分按期交付",
            "detail": f"订单号：{ids}（部分数量延期）",
            "link": "/res/order_sale",
        })

    # 5) 设备高负荷（峰值负荷率 ≥ 90% 视为瓶颈预警）
    busy = conn.execute(
        """SELECT resource_code, max_load_rate_pct, avg_load_rate_pct
           FROM res_view_equip_load WHERE max_load_rate_pct >= 90
           ORDER BY max_load_rate_pct DESC"""
    ).fetchall()
    for r in busy:
        warnings.append({
            "level": "warning", "icon": "fa-fire",
            "title": f"设备 {r['resource_code']} 负荷偏高",
            "detail": f"峰值负荷率 {r['max_load_rate_pct']:.1f}%，平均 {r['avg_load_rate_pct']:.1f}%",
            "link": "/res/equip_load",
        })

    # 6) 设备加班
    ot = conn.execute(
        """SELECT resource_code, COUNT(*) n, ROUND(SUM(load),1) qty
           FROM res_overload WHERE run_id = ? AND load > ?
           GROUP BY resource_code ORDER BY qty DESC""",
        (run_id, EPS),
    ).fetchall()
    for r in ot:
        warnings.append({
            "level": "info", "icon": "fa-plus-square",
            "title": f"设备 {r['resource_code']} 使用加班",
            "detail": f"{r['n']} 个周期发生加班，加班负荷合计 {r['qty']:g}",
            "link": "/res/equip_overload",
        })

    level_order = {"danger": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: level_order[w["level"]])
    return warnings


def get_equip_load_matrix(conn: sqlite3.Connection, nperiod: int) -> dict:
    """设备 × 周期 负荷矩阵（热力图数据源）

    返回 periods 列表与每台设备的 capacity / 各期负荷率 / max / avg。
    """
    periods = list(range(1, nperiod + 1))
    period_cols = [f"period_{t}" for t in periods]
    col_sql = ", ".join(
        f'"{c}"' for c in ["resource_code", "capacity", "max_load_rate_pct", "avg_load_rate_pct"] + period_cols
    )
    rows = conn.execute(
        f"""SELECT {col_sql} FROM res_view_equip_load ORDER BY max_load_rate_pct DESC"""
    ).fetchall()

    equipments = []
    for r in rows:
        loads = [r[f"period_{t}"] or 0.0 for t in periods]
        cap = r["capacity"] or 0.0
        rates = [round(ld / cap * 100, 1) if cap > 0 else 0.0 for ld in loads]
        equipments.append({
            "code": r["resource_code"],
            "capacity": round(cap, 1),
            "loads": [round(ld, 1) for ld in loads],
            "rates": rates,
            "max_rate": round(r["max_load_rate_pct"], 1) if r["max_load_rate_pct"] is not None else 0.0,
            "avg_rate": round(r["avg_load_rate_pct"], 1) if r["avg_load_rate_pct"] is not None else 0.0,
        })
    return {"periods": periods, "equipments": equipments}


def get_dashboard(conn: sqlite3.Connection) -> dict:
    """工作台页面全量数据"""
    run = get_run_info(conn)
    if run is None:
        return {"has_result": False}
    return {
        "has_result": True,
        "run": run,
        "kpis": get_kpis(conn),
        "warnings": get_warnings(conn),
        "equip_load": get_equip_load_matrix(conn, run["nperiod"] or 12),
    }
