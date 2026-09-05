"""分析与可视化聚合服务（排程可视化 / 分析中心 / 计划版本 / 数据校验 / 排产触发）

全部为只读聚合查询（排产触发除外：仅启动子进程，不写库），
不新增/修改任何数据库表结构。
"""
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

EPS = 1e-4
_WEB_DIR = Path(__file__).resolve().parent.parent.parent          # src/web
_PROJECT_ROOT = _WEB_DIR.parent.parent                             # 项目根
_MODEL_SCRIPT = _PROJECT_ROOT / "src" / "model" / "APS-SPlant-v2-sqlite.py"

# 排产子进程句柄（单实例，模块级）
_solve_proc = None
_solve_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------
def _latest_run_id(conn: sqlite3.Connection):
    row = conn.execute("SELECT MAX(run_id) FROM res_solve_run").fetchone()
    return row[0] if row and row[0] is not None else None


def _run_periods(conn: sqlite3.Connection, run_id: int):
    row = conn.execute("SELECT nperiod FROM res_solve_run WHERE run_id = ?", (run_id,)).fetchone()
    return (row["nperiod"] if row and row["nperiod"] else 12)


# ---------------------------------------------------------------------------
# 排程可视化：订单交付看板
# ---------------------------------------------------------------------------
def get_order_delivery_board(conn: sqlite3.Connection) -> dict:
    """订单行 × 周期：交期标记 + 各期交付量 + 交付状态"""
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    periods = list(range(1, nperiod + 1))

    rows = conn.execute(
        """SELECT order_id, material_code, priority_level, order_quantity, due_period,
                  delivery_period, delivery_quantity, delay_quantity, delivery_status,
                  revenue, delay_penalty
           FROM res_view_order_sale ORDER BY order_id, delivery_period"""
    ).fetchall()

    orders = {}
    for r in rows:
        oid = r["order_id"]
        o = orders.setdefault(oid, {
            "order_id": oid, "material_code": r["material_code"],
            "priority_level": r["priority_level"], "order_quantity": r["order_quantity"],
            "due_period": r["due_period"], "deliveries": {},
            "status_set": set(), "revenue": 0.0, "penalty": 0.0, "delayed_qty": 0.0,
            "delivered_qty": 0.0, "last_period": 0,
        })
        t = r["delivery_period"]
        o["deliveries"][t] = o["deliveries"].get(t, 0.0) + (r["delivery_quantity"] or 0.0)
        o["status_set"].add(r["delivery_status"])
        o["revenue"] += r["revenue"] or 0.0
        o["penalty"] += r["delay_penalty"] or 0.0
        o["delayed_qty"] += r["delay_quantity"] or 0.0
        o["delivered_qty"] += r["delivery_quantity"] or 0.0
        o["last_period"] = max(o["last_period"], t)

    order_list = []
    for oid, o in orders.items():
        # 综合状态：未交付 > 延期 > 部分按期 > 按期
        if o["delivered_qty"] < EPS:
            status, color = "未交付", "danger"
        elif "延期交付" in o["status_set"] and "部分按期" in o["status_set"]:
            status, color = "部分按期+延期", "warning"
        elif "延期交付" in o["status_set"]:
            status, color = "延期交付", "danger"
        elif "部分按期" in o["status_set"]:
            status, color = "部分按期", "warning"
        else:
            status, color = "按期交付", "success"
        cells = []
        for t in periods:
            qty = o["deliveries"].get(t, 0.0)
            cls = ""
            if qty > EPS:
                cls = "bg-success text-white" if t <= o["due_period"] else "bg-danger text-white"
            cells.append({"period": t, "qty": round(qty, 1) if qty > EPS else None, "cls": cls})
        order_list.append({
            **{k: v for k, v in o.items() if k not in ("deliveries", "status_set")},
            "status": status, "color": color, "cells": cells,
            "delay_periods": max(o["last_period"] - o["due_period"], 0),
            "revenue": round(o["revenue"], 0), "penalty": round(o["penalty"], 0),
        })
    order_list.sort(key=lambda x: (x["order_id"]))
    return {"has_result": True, "periods": periods, "orders": order_list}


# ---------------------------------------------------------------------------
# 排程可视化：生产甘特图（设备 × 周期 占用热力 + 悬浮加工明细）
# ---------------------------------------------------------------------------
def get_gantt_data(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    periods = list(range(1, nperiod + 1))

    # 设备能力（来自负荷视图）
    cap_rows = conn.execute(
        "SELECT resource_code, capacity FROM res_view_equip_load"
    ).fetchall()
    caps = {r["resource_code"]: (r["capacity"] or 0.0) for r in cap_rows}

    # 加工计划：设备 × 周期 聚合能力占用与加工明细
    detail = {}   # (equip, t) -> list of (material, operation, route, prod_qty, cap)
    usage = {}    # (equip, t) -> cap sum
    mp_rows = conn.execute(
        """SELECT resource_code, period, material_code, operation_code, production_line,
                  route_id, is_wip, production_quantity, capacity_usage
           FROM res_machining_plan WHERE run_id = ? AND is_wip = 0""",
        (run_id,),
    ).fetchall()
    for r in mp_rows:
        t = r["period"]
        if t < 1 or t > nperiod:
            continue
        key = (r["resource_code"], t)
        cap_u = r["capacity_usage"] or 0.0
        usage[key] = usage.get(key, 0.0) + cap_u
        detail.setdefault(key, []).append({
            "material": r["material_code"], "operation": r["operation_code"],
            "line": r["production_line"], "route": r["route_id"],
            "prod": round(r["production_quantity"], 1) if r["production_quantity"] else None,
            "cap": round(cap_u, 1),
        })

    equips = []
    for eq, cap in caps.items():
        rates, cells = [], []
        for t in periods:
            u = usage.get((eq, t), 0.0)
            rate = round(u / cap * 100, 1) if cap > EPS else 0.0
            rates.append(rate)
            cells.append({"period": t, "rate": rate, "usage": round(u, 1),
                          "ops": detail.get((eq, t), [])})
        equips.append({
            "code": eq, "capacity": round(cap, 1), "cells": cells,
            "max_rate": round(max(rates), 1) if rates else 0.0,
            "avg_rate": round(sum(rates) / len(rates), 1) if rates else 0.0,
        })
    equips.sort(key=lambda e: -e["max_rate"])
    return {"has_result": True, "periods": periods, "equipments": equips}


# ---------------------------------------------------------------------------
# 分析中心：延期分析
# ---------------------------------------------------------------------------
def get_delay_analysis(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}

    delayed = conn.execute(
        """SELECT order_id, material_code, priority_level, MIN(due_period) due,
                  MAX(delivery_period) delivered, SUM(delivery_quantity) dqty,
                  SUM(delay_quantity) delayed_qty, SUM(delay_penalty) penalty,
                  AVG(shadow_price) shadow, AVG(margin) margin
           FROM res_view_order_sale
           WHERE delivery_period > due_period
           GROUP BY order_id
           ORDER BY penalty DESC"""
    ).fetchall()
    orders = [{
        "order_id": r["order_id"], "material_code": r["material_code"],
        "priority_level": r["priority_level"], "due": r["due"], "delivered": r["delivered"],
        "delay_periods": r["delivered"] - r["due"],
        "delayed_qty": round(r["delayed_qty"] or 0, 1),
        "penalty": round(r["penalty"] or 0, 0),
        "shadow": round(r["shadow"] or 0, 1), "margin": round(r["margin"] or 0, 0),
    } for r in delayed]

    # 归因：瓶颈设备（峰值负荷率 Top）
    bottlenecks = [dict(r) for r in conn.execute(
        """SELECT resource_code, max_load_rate_pct, avg_load_rate_pct
           FROM res_view_equip_load ORDER BY max_load_rate_pct DESC LIMIT 5"""
    ).fetchall()]

    # 高影子价格设备（边际价值高 = 稀缺）
    shadow_rows = conn.execute(
        """SELECT resource_code,
                  (period_1+period_2+period_3+period_4+period_5+period_6+period_7+
                   period_8+period_9+period_10+period_11+period_12)/12 AS avg_shadow
           FROM res_view_equip_shadow"""
    ).fetchall()
    top_shadow = sorted(
        ({"resource_code": r["resource_code"], "avg_shadow": round(r["avg_shadow"] or 0, 1)}
         for r in shadow_rows),
        key=lambda x: -x["avg_shadow"])[:5]

    s = conn.execute("SELECT delay_penalty, infeasible_cost FROM res_view_summary LIMIT 1").fetchone()
    return {
        "has_result": True, "orders": orders, "bottlenecks": bottlenecks,
        "top_shadow": top_shadow,
        "total_penalty": round(s["delay_penalty"], 0) if s else 0,
        "infeasible_cost": round(s["infeasible_cost"], 0) if s else 0,
        "delayed_count": len(orders),
    }


# ---------------------------------------------------------------------------
# 分析中心：瓶颈分析（设备负荷 + 影子价格双榜）
# ---------------------------------------------------------------------------
def get_bottleneck_analysis(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)

    load_rows = conn.execute(
        """SELECT resource_code, capacity, max_load_rate_pct, avg_load_rate_pct,
                  normal_cost_total FROM res_view_equip_load
           ORDER BY max_load_rate_pct DESC"""
    ).fetchall()
    loads = [{
        "code": r["resource_code"], "capacity": r["capacity"],
        "max_rate": round(r["max_load_rate_pct"] or 0, 1),
        "avg_rate": round(r["avg_load_rate_pct"] or 0, 1),
        "cost": round(r["normal_cost_total"] or 0, 0),
    } for r in load_rows]

    pcols = ", ".join(f"period_{t}" for t in range(1, nperiod + 1))
    sh_rows = conn.execute(f"SELECT resource_code, {pcols} FROM res_view_equip_shadow").fetchall()
    shadows = []
    for r in sh_rows:
        vals = [r[f"period_{t}"] or 0.0 for t in range(1, nperiod + 1)]
        shadows.append({
            "code": r["resource_code"],
            "avg": round(sum(vals) / len(vals), 1) if vals else 0.0,
            "max": round(max(vals), 1) if vals else 0.0,
        })
    shadows.sort(key=lambda x: -x["avg"])
    return {"has_result": True, "loads": loads, "shadows": shadows[:10]}


# ---------------------------------------------------------------------------
# 分析中心：库存分析（三类物料库存趋势）
# ---------------------------------------------------------------------------
_INV_VIEWS = {
    "产品": "res_view_prod_inv",
    "自制件": "res_view_self_inv",
    "原材料": "res_view_raw_inv",
}

def get_inventory_analysis(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    tcols = [f"period_{t}" for t in range(0, nperiod + 1)]

    series = {}
    material_rows = []
    for cat, view in _INV_VIEWS.items():
        rows = conn.execute(f'SELECT material_code, {", ".join(tcols)} FROM {view}').fetchall()
        totals = []
        for t in tcols:
            totals.append(round(sum(r[t] or 0.0 for r in rows), 1))
        series[cat] = totals
        for r in rows:
            vals = [round(r[t] or 0.0, 1) for t in tcols]
            material_rows.append({
                "category": cat, "code": r["material_code"],
                "initial": vals[0], "final": vals[-1],
                "peak": max(vals), "avg": round(sum(vals) / len(vals), 1),
            })
    material_rows.sort(key=lambda x: (x["category"], -x["peak"]))
    return {
        "has_result": True,
        "periods": list(range(0, nperiod + 1)),
        "series": series, "materials": material_rows,
    }


# ---------------------------------------------------------------------------
# 分析中心：成本分析
# ---------------------------------------------------------------------------
def get_cost_analysis(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    s = conn.execute(
        """SELECT sales_revenue, delay_penalty, manufacturing_cost, outsource_cost,
                  purchase_cost, inventory_cost, infeasible_cost, fixture_cost, profit
           FROM res_view_summary LIMIT 1"""
    ).fetchone()
    if s is None:
        return {"has_result": False}
    items = [
        ("制造成本", s["manufacturing_cost"], "#0d6efd"),
        ("原材料采购", s["purchase_cost"], "#6f42c1"),
        ("外协费用", s["outsource_cost"], "#fd7e14"),
        ("工装费用", s["fixture_cost"], "#20c997"),
        ("延期罚金", s["delay_penalty"], "#dc3545"),
        ("库存持有成本", s["inventory_cost"], "#0dcaf0"),
        ("不可行罚成本", s["infeasible_cost"], "#6c757d"),
    ]
    return {
        "has_result": True,
        "revenue": round(s["sales_revenue"], 0),
        "profit": round(s["profit"], 0),
        "profit_rate": round(s["profit"] / s["sales_revenue"] * 100, 1) if s["sales_revenue"] else 0,
        "cost_items": [{"name": n, "value": round(v or 0, 0), "color": c} for n, v, c in items],
        "total_cost": round(sum(v or 0 for _, v, _ in items), 0),
    }


# ---------------------------------------------------------------------------
# 分析中心：外协分析
# ---------------------------------------------------------------------------
def get_outsource_analysis(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)

    out_rows = conn.execute(
        """SELECT material_code, quantity_total, cost_total FROM res_view_outsource_plan
           WHERE quantity_total > 0 ORDER BY cost_total DESC"""
    ).fetchall()
    outs = [{"code": r["material_code"], "qty": round(r["quantity_total"], 1),
             "cost": round(r["cost_total"], 0)} for r in out_rows]
    out_cost = round(sum(o["cost"] for o in outs), 0)
    out_qty = round(sum(o["qty"] for o in outs), 1)

    # 自制产量（自制件生产计划合计）
    self_row = conn.execute(
        "SELECT SUM(quantity_total) q FROM res_view_self_plan"
    ).fetchone()
    self_qty = round(self_row["q"] or 0, 1)
    s = conn.execute(
        "SELECT manufacturing_cost, outsource_cost FROM res_view_summary LIMIT 1"
    ).fetchone()
    mfg_cost = round(s["manufacturing_cost"] or 0, 0) if s else 0
    total = out_cost + mfg_cost
    return {
        "has_result": True,
        "out_cost": out_cost, "mfg_cost": mfg_cost,
        "out_cost_pct": round(out_cost / total * 100, 1) if total > EPS else 0,
        "out_qty": out_qty, "self_qty": self_qty,
        "out_qty_pct": round(out_qty / (out_qty + self_qty) * 100, 1) if (out_qty + self_qty) > EPS else 0,
        "items": outs, "nperiod": nperiod,
    }


# ---------------------------------------------------------------------------
# 计划版本：列表与对比
# ---------------------------------------------------------------------------
def get_versions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT r.run_id, r.run_time, r.status, r.solve_time_ms, r.mip_gap,
                  r.objective, r.nperiod,
                  s.sales_revenue, s.profit, s.delay_penalty
           FROM res_solve_run r
           LEFT JOIN res_summary s ON s.run_id = r.run_id
           ORDER BY r.run_id DESC"""
    ).fetchall()
    return [{
        "run_id": r["run_id"], "run_time": r["run_time"], "status": r["status"],
        "solve_time_s": round(r["solve_time_ms"] / 1000, 1) if r["solve_time_ms"] else None,
        "mip_gap_pct": round(r["mip_gap"] * 100, 2) if r["mip_gap"] is not None else None,
        "objective": round(r["objective"], 0) if r["objective"] is not None else None,
        "nperiod": r["nperiod"],
        "sales_revenue": round(r["sales_revenue"], 0) if r["sales_revenue"] is not None else None,
        "profit": round(r["profit"], 0) if r["profit"] is not None else None,
        "delay_penalty": round(r["delay_penalty"], 0) if r["delay_penalty"] is not None else None,
    } for r in rows]


def _version_kpi(conn: sqlite3.Connection, run_id: int) -> dict:
    kpi = {"run_id": run_id}
    d = conn.execute(
        """SELECT SUM(order_count_total) t, SUM(order_count_ontime) ot,
                  SUM(order_count_delayed) de, SUM(order_count_undelivered) un
           FROM res_order_delivery WHERE run_id = ?""", (run_id,)).fetchone()
    if d and d["t"]:
        kpi["orders"] = d["t"]
        kpi["ontime_rate"] = round(d["ot"] / d["t"] * 100, 1)
        kpi["delayed"] = d["de"] or 0
        kpi["undelivered"] = d["un"] or 0
    s = conn.execute(
        """SELECT sales_revenue, profit, delay_penalty, manufacturing_cost,
                  outsource_cost, purchase_cost, fixture_cost, inventory_cost
           FROM res_summary WHERE run_id = ?""", (run_id,)).fetchone()
    if s:
        kpi.update({
            "revenue": round(s["sales_revenue"], 0), "profit": round(s["profit"], 0),
            "penalty": round(s["delay_penalty"], 0),
            "mfg_cost": round(s["manufacturing_cost"], 0),
            "out_cost": round(s["outsource_cost"], 0),
            "purchase_cost": round(s["purchase_cost"], 0),
            "fixture_cost": round(s["fixture_cost"], 0),
        })
    return kpi


def get_version_compare(conn: sqlite3.Connection, run_a: int, run_b: int) -> dict:
    ka, kb = _version_kpi(conn, run_a), _version_kpi(conn, run_b)
    metrics = [
        ("订单总数", "orders", "{:g}", False),
        ("订单准交率(%)", "ontime_rate", "{}", True),
        ("延期订单数", "delayed", "{:g}", True),
        ("未交付订单数", "undelivered", "{:g}", True),
        ("销售收入", "revenue", "¥{:,.0f}", False),
        ("利润总额", "profit", "¥{:,.0f}", False),
        ("延期罚金", "penalty", "¥{:,.0f}", True),
        ("制造成本", "mfg_cost", "¥{:,.0f}", True),
        ("外协费用", "out_cost", "¥{:,.0f}", True),
        ("采购成本", "purchase_cost", "¥{:,.0f}", True),
        ("工装费用", "fixture_cost", "¥{:,.0f}", True),
    ]
    rows = []
    for label, key, fmt, lower_better in metrics:
        va, vb = ka.get(key), kb.get(key)
        diff = None
        better = ""
        if va is not None and vb is not None:
            diff = vb - va
            if abs(diff) > EPS:
                good = diff < 0 if lower_better else diff > 0
                better = "b" if good else "a"
        rows.append({
            "label": label,
            "a": fmt.format(va) if va is not None else "-",
            "b": fmt.format(vb) if vb is not None else "-",
            "diff": (fmt.format(diff) if diff is not None and diff >= 0 else
                     ("-" + fmt.format(abs(diff))) if diff is not None else "-"),
            "better": better,
        })
    return {"has_result": True, "a": ka, "b": kb, "rows": rows}


# ---------------------------------------------------------------------------
# 系统管理：数据校验（只读完整性检查）
# ---------------------------------------------------------------------------
def get_validation_report(conn: sqlite3.Connection) -> list[dict]:
    checks = []

    def check(name, sql, detail_sql=None, ok_when_zero=True):
        try:
            n = conn.execute(sql).fetchone()[0]
            details = []
            if n and detail_sql:
                details = [str(r[0]) for r in conn.execute(detail_sql).fetchall()][:20]
            checks.append({
                "name": name, "passed": (n == 0) if ok_when_zero else (n > 0),
                "count": n, "details": details,
            })
        except sqlite3.Error as e:
            checks.append({"name": name, "passed": None, "count": 0,
                           "details": [f"检查失败: {e}"]})

    check("订单引用的产品在物料主数据中存在",
          """SELECT COUNT(*) FROM core_biz_demand_order o
             LEFT JOIN core_md_material m ON m.material_code = o.product_code
             WHERE m.material_code IS NULL""",
          """SELECT o.order_id || ':' || o.product_code FROM core_biz_demand_order o
             LEFT JOIN core_md_material m ON m.material_code = o.product_code
             WHERE m.material_code IS NULL""")
    check("BOM 父项/子项物料均在主数据中存在",
          """SELECT COUNT(*) FROM core_biz_bom b
             LEFT JOIN core_md_material p ON p.material_code = b.parent_material_code
             LEFT JOIN core_md_material c ON c.material_code = b.child_material_code
             WHERE p.material_code IS NULL OR c.material_code IS NULL""",
          """SELECT b.parent_material_code || ' -> ' || b.child_material_code FROM core_biz_bom b
             LEFT JOIN core_md_material p ON p.material_code = b.parent_material_code
             LEFT JOIN core_md_material c ON c.material_code = b.child_material_code
             WHERE p.material_code IS NULL OR c.material_code IS NULL""")
    check("工艺步骤引用的设备在资源主数据中存在",
          """SELECT COUNT(*) FROM core_biz_routing_step s
             LEFT JOIN core_md_resource r ON r.resource_code = s.equipment_code
             WHERE s.equipment_code != '' AND r.resource_code IS NULL""")
    check("产品物料均有产品扩展信息",
          """SELECT COUNT(*) FROM core_md_material m
             LEFT JOIN core_md_product_ext e ON e.material_code = m.material_code
             WHERE m.category = 'PRODUCT' AND e.material_code IS NULL""")
    check("自制件均有自制件扩展信息",
          """SELECT COUNT(*) FROM core_md_material m
             LEFT JOIN core_md_semi_ext e ON e.material_code = m.material_code
             WHERE m.category = 'SEMI' AND e.material_code IS NULL""")
    check("原材料均有原材料扩展信息",
          """SELECT COUNT(*) FROM core_md_material m
             LEFT JOIN core_md_raw_ext e ON e.material_code = m.material_code
             WHERE m.category = 'RAW' AND e.material_code IS NULL""")
    check("订单交期在计划期范围内",
          """SELECT COUNT(*) FROM core_biz_demand_order o, core_biz_global_params p
             WHERE p.param_key = '计划期长度'
               AND (o.due_period < 1 OR o.due_period > CAST(p.param_value AS INTEGER))""",
          """SELECT order_id || ' 交期=' || due_period FROM core_biz_demand_order
             WHERE due_period < 1 OR due_period > 12""")
    check("物料期初库存非负",
          "SELECT COUNT(*) FROM core_md_material WHERE initial_inventory < 0")
    check("库存上下限设置合理（下限 ≤ 上限）",
          "SELECT COUNT(*) FROM core_md_material WHERE min_inventory > max_inventory")
    check("全局排产参数完整（22 项）",
          "SELECT 22 - COUNT(*) FROM core_biz_global_params", ok_when_zero=True)
    # 结果侧检查
    rid = _latest_run_id(conn)
    if rid:
        n_inf = conn.execute(
            "SELECT COUNT(*) FROM res_infeasible WHERE run_id = ?", (rid,)).fetchone()[0]
        checks.append({
            "name": f"最新排产（#{rid}）无不可行松弛量",
            "passed": n_inf == 0, "count": n_inf, "details": [],
        })
        n_sum = conn.execute(
            "SELECT COUNT(*) FROM res_summary WHERE run_id = ?", (rid,)).fetchone()[0]
        checks.append({
            "name": f"最新排产（#{rid}）汇总结果已生成",
            "passed": n_sum > 0, "count": n_sum, "details": [],
        })
    return checks


# ---------------------------------------------------------------------------
# 计划优化：排产触发（子进程，不直接写库）
# ---------------------------------------------------------------------------
def start_solve() -> dict:
    """启动排算子进程（单实例）"""
    global _solve_proc
    with _solve_lock:
        if _solve_proc is not None and _solve_proc.poll() is None:
            return {"started": False, "message": "已有排产任务正在运行", "pid": _solve_proc.pid}
        log_path = _PROJECT_ROOT / "data" / "output" / "solve_web.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = open(log_path, "w", encoding="utf-8")
        _solve_proc = subprocess.Popen(
            [sys.executable, str(_MODEL_SCRIPT)],
            cwd=str(_PROJECT_ROOT), stdout=log_f, stderr=subprocess.STDOUT,
        )
        return {"started": True, "pid": _solve_proc.pid, "message": "排产任务已启动"}


def solve_status(conn: sqlite3.Connection) -> dict:
    global _solve_proc
    running = _solve_proc is not None and _solve_proc.poll() is None
    rid = _latest_run_id(conn)
    run = None
    if rid:
        r = conn.execute(
            "SELECT run_id, run_time, status, objective, solve_time_ms FROM res_solve_run WHERE run_id = ?",
            (rid,)).fetchone()
        run = {"run_id": r["run_id"], "run_time": r["run_time"], "status": r["status"],
               "objective": round(r["objective"], 0) if r["objective"] else None}
    return {"running": running,
            "pid": _solve_proc.pid if _solve_proc is not None else None,
            "returncode": _solve_proc.poll() if _solve_proc is not None else None,
            "latest_run": run}
