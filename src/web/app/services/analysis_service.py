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
    # 工装负荷（period 列为占用工时；峰值/平均负荷率取视图汇总列）
    fixtures = []
    for r in conn.execute(
            f'SELECT resource_code c, {", ".join(f"period_{t}" for t in range(1, nperiod + 1))}, '
            f'max_load_rate_pct, avg_load_rate_pct FROM res_view_fixt_load'):
        loads = [round(r[f"period_{t}"] or 0.0, 1) for t in range(1, nperiod + 1)]
        fixtures.append({"code": r["c"], "loads": loads,
                         "max_rate": round(r["max_load_rate_pct"] or 0, 1),
                         "avg_rate": round(r["avg_load_rate_pct"] or 0, 1)})
    fixt_overload_n = conn.execute(
        "SELECT COUNT(*) FROM res_fixt_plus WHERE run_id = ? AND load > ?", (run_id, EPS)).fetchone()[0]
    equip_overload_n = conn.execute(
        "SELECT COUNT(*) FROM res_overload WHERE run_id = ? AND load > ?", (run_id, EPS)).fetchone()[0]
    return {"has_result": True, "periods": periods, "equipments": equips,
            "fixtures": fixtures,
            "fixt_max_load": round(max((max(f["loads"]) for f in fixtures), default=0.0), 1),
            "fixt_overload_n": fixt_overload_n, "equip_overload_n": equip_overload_n}


# ---------------------------------------------------------------------------
# 排程可视化：产销存看板（生产 / 销售 / 库存 合一）
# ---------------------------------------------------------------------------
def get_psi_board(conn: sqlite3.Connection) -> dict:
    """产品级产销存：各期产量、销量（交付量）、库存量，用于产销平衡分析"""
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    pcols = [f"period_{t}" for t in range(1, nperiod + 1)]

    def load(view, code_col="material_code"):
        out = {}
        for r in conn.execute(f'SELECT {code_col} c, {", ".join(pcols)} FROM {view}'):
            acc = out.setdefault(r["c"], [0.0] * nperiod)
            for i, c in enumerate(pcols):
                acc[i] += r[c] or 0.0
        return {k: [round(v, 1) for v in vs] for k, vs in out.items()}

    prod = load("res_view_prod_plan")    # 产量（产品×路线已在视图聚合）
    sale = load("res_view_prod_sale")    # 销售量/交付量
    # 库存含 0 期
    inv_rows = conn.execute(
        f'SELECT material_code c, {", ".join(f"period_{t}" for t in range(0, nperiod + 1))} '
        f'FROM res_view_prod_inv').fetchall()
    inv = {r["c"]: [round(r[f"period_{t}"] or 0.0, 1) for t in range(0, nperiod + 1)] for r in inv_rows}

    names = {r["material_code"]: r["material_name"] for r in conn.execute(
        "SELECT material_code, material_name FROM core_md_material WHERE category = 'PRODUCT'")}

    codes = sorted(set(prod) | set(sale) | set(inv))
    products = []
    for c in codes:
        p, s, iv = prod.get(c, [0.0] * nperiod), sale.get(c, [0.0] * nperiod), inv.get(c, [0.0] * (nperiod + 1))
        products.append({
            "code": c, "name": names.get(c, ""),
            "prod": p, "sale": s, "inv": iv,
            "tot_prod": round(sum(p), 1), "tot_sale": round(sum(s), 1),
            "init_inv": iv[0], "final_inv": iv[-1],
        })
    products.sort(key=lambda x: -(x["tot_prod"] + x["tot_sale"]))

    # 各期合计（图表用）
    period_tot = {
        "prod": [round(sum(p["prod"][t] for p in products), 1) for t in range(nperiod)],
        "sale": [round(sum(p["sale"][t] for p in products), 1) for t in range(nperiod)],
        "inv": [round(sum(p["inv"][t + 1] for p in products), 1) for t in range(nperiod)],
    }
    return {
        "has_result": True, "nperiod": nperiod,
        "periods": list(range(1, nperiod + 1)),
        "products": products, "period_tot": period_tot,
        "tot_prod": round(sum(period_tot["prod"]), 1),
        "tot_sale": round(sum(period_tot["sale"]), 1),
        "tot_final_inv": round(period_tot["inv"][-1], 1),
    }


# ---------------------------------------------------------------------------
# 排程可视化：供应计划看板（自制件生产 / 原材料采购 / 外协）
# ---------------------------------------------------------------------------
def get_supply_board(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    pcols = [f"period_{t}" for t in range(1, nperiod + 1)]

    def agg(view, extra_cols=""):
        out = {}
        sql = f'SELECT material_code c, {", ".join(pcols)} {extra_cols} FROM {view}'
        for r in conn.execute(sql):
            acc = out.setdefault(r["c"], {"vals": [0.0] * nperiod, "cost": 0.0, "routes": set()})
            for i, c in enumerate(pcols):
                acc["vals"][i] += r[c] or 0.0
            if extra_cols and "cost_total" in r.keys() and r["cost_total"]:
                acc["cost"] += r["cost_total"]
            if extra_cols and "route_id" in r.keys() and r["route_id"] is not None:
                acc["routes"].add(r["route_id"])
        return out

    self_ = agg("res_view_self_plan", ", route_id, quantity_total")
    purch = agg("res_view_purchase_plan", ", quantity_total, cost_total")
    outs = agg("res_view_outsource_plan", ", quantity_total, cost_total")

    names = {r["material_code"]: r for r in conn.execute(
        """SELECT m.material_code, m.material_name, m.category,
                  r.purchase_lead_time AS plt FROM core_md_material m
           LEFT JOIN core_md_raw_ext r ON r.material_code = m.material_code""")}

    def rows(mat, is_purchase=False):
        res = []
        for code, d in mat.items():
            n = names.get(code)
            vals = [round(v, 1) for v in d["vals"]]
            total = round(sum(vals), 1)
            if total <= EPS and d["cost"] <= EPS:
                continue
            res.append({
                "code": code, "name": (n["material_name"] if n else "") or "",
                "category": _CATEGORY_LABELS.get(n["category"], "?") if n else "?",
                "vals": vals, "total": total,
                "cost": round(d["cost"], 0),
                "plt": (n["plt"] if n and n["plt"] is not None else None) if is_purchase else None,
                "routes": sorted(d["routes"]),
            })
        res.sort(key=lambda x: -x["total"])
        return res

    self_rows, purch_rows, out_rows = rows(self_), rows(purch, True), rows(outs, True)
    period_tot = {
        "self": [round(sum(r["vals"][t] for r in self_rows), 1) for t in range(nperiod)],
        "purch": [round(sum(r["vals"][t] for r in purch_rows), 1) for t in range(nperiod)],
        "out": [round(sum(r["vals"][t] for r in out_rows), 1) for t in range(nperiod)],
    }
    return {
        "has_result": True, "nperiod": nperiod, "periods": list(range(1, nperiod + 1)),
        "self_rows": self_rows, "purch_rows": purch_rows, "out_rows": out_rows,
        "period_tot": period_tot,
        "self_total": round(sum(r["total"] for r in self_rows), 1),
        "purch_total": round(sum(r["total"] for r in purch_rows), 1),
        "purch_cost": round(sum(r["cost"] for r in purch_rows), 0),
        "out_total": round(sum(r["total"] for r in out_rows), 1),
        "out_cost": round(sum(r["cost"] for r in out_rows), 0),
    }


# ---------------------------------------------------------------------------
# 排程可视化：资源影子价格热力图（设备/工装/产品/自制件/原材料 + 替代使用）
# ---------------------------------------------------------------------------
def get_shadow_heat(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    pcols = [f"period_{t}" for t in range(1, nperiod + 1)]

    def heat(view, code_col):
        out = []
        for r in conn.execute(f'SELECT {code_col} c, {", ".join(pcols)} FROM {view}'):
            vals = [round(r[c] or 0.0, 2) for c in pcols]
            if max(vals) <= EPS:
                continue
            out.append({"code": r["c"], "vals": vals,
                        "avg": round(sum(vals) / len(vals), 2),
                        "max": round(max(vals), 2)})
        out.sort(key=lambda x: -x["avg"])
        return out

    names = {r["material_code"]: r["material_name"] for r in conn.execute(
        "SELECT material_code, material_name FROM core_md_material")}
    tabs = {
        "equip": {"label": "设备", "rows": heat("res_view_equip_shadow", "resource_code"), "unit": "元/工时"},
        "fixt": {"label": "工装", "rows": heat("res_view_fixt_shadow", "resource_code"), "unit": "元/工时"},
        "prod": {"label": "产品", "rows": heat("res_view_shadow_prod", "material_code"), "unit": "元/件"},
        "self": {"label": "自制件", "rows": heat("res_view_shadow_self", "material_code"), "unit": "元/件"},
        "raw": {"label": "原材料", "rows": heat("res_view_shadow_raw", "material_code"), "unit": "元/件"},
    }
    for key in ("prod", "self", "raw"):
        for row in tabs[key]["rows"]:
            row["name"] = names.get(row["code"], "")

    # 替代关系使用
    subs = []
    for r in conn.execute(
            """SELECT alt_type_name, from_material_code, to_material_code, quantity_total
               FROM res_view_substitute WHERE quantity_total > 0
               ORDER BY quantity_total DESC"""):
        subs.append({"type": r["alt_type_name"], "f": r["from_material_code"],
                     "t": r["to_material_code"], "qty": round(r["quantity_total"], 1)})
    return {"has_result": True, "nperiod": nperiod, "periods": list(range(1, nperiod + 1)),
            "tabs": tabs, "substitutes": subs}


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
# 排程可视化：物料需求（MRP 口径，按模型自身平衡恒等式推算毛需求）
# ---------------------------------------------------------------------------
def _material_supply_map(conn: sqlite3.Connection, run_id: int, nperiod: int) -> dict:
    """汇总各物料的供给/库存/松弛（单位：件）

    毛需求（实际消耗）= 期初库存 + 计划供给 − 期末库存（模型物料平衡恒等式）。
    该口径自动涵盖虚拟件/外协/物料替代/在制品/损耗，与模型完全一致。
    """
    sup = {}

    def get(code):
        return sup.setdefault(code, {
            "prod": 0.0, "self": 0.0, "out": 0.0, "pur": 0.0,
            "init": 0.0, "final": 0.0, "slack": 0.0,
        })

    for tbl, col in (("res_prod_made", "prod"), ("res_self_made", "self"),
                     ("res_outsource", "out"), ("res_purchase", "pur")):
        rows = conn.execute(
            f"SELECT material_code m, SUM(quantity) q FROM {tbl} WHERE run_id = ? GROUP BY m",
            (run_id,)).fetchall()
        for r in rows:
            get(r["m"])[col] += r["q"] or 0.0

    for tbl in ("res_prod_inv", "res_self_inv", "res_raw_inv"):
        rows = conn.execute(
            f"SELECT material_code m, period, quantity q FROM {tbl} WHERE run_id = ? AND period IN (0, ?)",
            (run_id, nperiod)).fetchall()
        for r in rows:
            s = get(r["m"])
            if r["period"] == 0:
                s["init"] += r["q"] or 0.0
            else:
                s["final"] += r["q"] or 0.0

    for r in conn.execute(
            "SELECT inf_type, resource_code m, SUM(quantity) q FROM res_infeasible "
            "WHERE run_id = ? GROUP BY inf_type, m", (run_id,)).fetchall():
        get(r["m"])["slack"] += r["q"] or 0.0
    return sup


_CATEGORY_LABELS = {"PRODUCT": "产品", "SEMI": "自制件", "RAW": "原材料"}

def get_material_requirements(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    sup = _material_supply_map(conn, run_id, nperiod)

    masters = {r["material_code"]: r for r in conn.execute(
        """SELECT m.material_code, m.material_name, m.category,
                  r.purchase_lead_time AS pur_lt
           FROM core_md_material m
           LEFT JOIN core_md_raw_ext r ON r.material_code = m.material_code""").fetchall()}
    rows = []
    for code, s in sup.items():
        supply = s["prod"] + s["self"] + s["out"] + s["pur"]
        gross = s["init"] + supply - s["final"]
        if gross <= EPS and supply <= EPS and s["init"] <= EPS and s["slack"] <= EPS:
            continue
        mst = masters.get(code)
        cat = mst["category"] if mst else None
        rows.append({
            "category": _CATEGORY_LABELS.get(cat, "其他"),
            "category_key": cat or "?",
            "code": code,
            "name": (mst["material_name"] if mst else "") or "",
            "init": round(s["init"], 1),
            "prod": round(s["prod"], 1), "self": round(s["self"], 1),
            "out": round(s["out"], 1), "pur": round(s["pur"], 1),
            "gross": round(max(gross, 0.0), 1),
            "final": round(s["final"], 1),
            "slack": round(s["slack"], 1),
            "pur_lt": (mst["pur_lt"] if mst and mst["pur_lt"] is not None else None),
        })
    cat_order = {"PRODUCT": 0, "SEMI": 1, "RAW": 2}
    rows.sort(key=lambda x: (cat_order.get(x["category_key"], 9), -x["gross"]))

    summary = {
        "total_gross": round(sum(r["gross"] for r in rows), 1),
        "n_short": sum(1 for r in rows if r["slack"] > EPS),
        "n_semi": sum(1 for r in rows if r["category_key"] == "SEMI"),
        "n_raw": sum(1 for r in rows if r["category_key"] == "RAW"),
    }
    return {"has_result": True, "rows": rows, "summary": summary, "run_id": run_id}


# ---------------------------------------------------------------------------
# 排程可视化：订单齐套视图
# ---------------------------------------------------------------------------
def _bom_edges(conn: sqlite3.Connection) -> dict:
    edges = {}
    for r in conn.execute(
            "SELECT parent_material_code p, child_material_code c, quantity q "
            "FROM core_biz_bom"):
        edges.setdefault(r["p"], []).append((r["c"], r["q"] or 1.0))
    return edges


def _explode_components(edges: dict, product: str, order_qty: float) -> list[dict]:
    """BOM 多级递归展开（标准用量），返回 [{code, level, qty}]，共享子件累计"""
    req = {}
    def rec(parent, parent_qty, level, path):
        if level > 12:
            return
        for child, q in edges.get(parent, []):
            if child in path:          # 环保护
                continue
            need = parent_qty * q
            req[child] = req.get(child, 0.0) + need
            rec(child, need, level + 1, path + [child])
    rec(product, order_qty, 1, [product])
    return [{"code": c, "qty": round(q, 2)} for c, q in sorted(req.items(), key=lambda x: -x[1])]


def get_order_kitting(conn: sqlite3.Connection) -> dict:
    run_id = _latest_run_id(conn)
    if run_id is None:
        return {"has_result": False}
    nperiod = _run_periods(conn, run_id)
    sup = _material_supply_map(conn, run_id, nperiod)
    edges = _bom_edges(conn)

    # 全局松弛：SALE=交付缺口(按订单号)，RAW/SELF=物料缺口，EQUIP/FIXT=产能缺口
    sale_slack = set()
    mat_short = cap_short = False
    for r in conn.execute(
            "SELECT inf_type, resource_code m FROM res_infeasible WHERE run_id = ?", (run_id,)):
        if r["inf_type"] == "SALE":
            sale_slack.add(str(r["m"]))
        elif r["inf_type"] in ("RAW", "SELF"):
            mat_short = True
        else:
            cap_short = True

    # 订单聚合
    order_rows = conn.execute(
        """SELECT order_id, material_code, priority_level, order_quantity, due_period,
                  MAX(delivery_period) last_deliver, SUM(delivery_quantity) delivered,
                  SUM(delay_quantity) delayed_qty, SUM(delay_penalty) penalty
           FROM res_view_order_sale GROUP BY order_id
           ORDER BY order_id""").fetchall()
    masters = {r["material_code"]: r for r in conn.execute(
        "SELECT material_code, material_name, category FROM core_md_material")}
    orders = []
    n_ontime = n_partial = n_late = n_undelivered = 0
    for r in order_rows:
        delivered = r["delivered"] or 0.0
        qty = r["order_quantity"] or 0.0
        is_late = r["last_deliver"] is not None and r["last_deliver"] > r["due_period"]
        is_partial = (r["delayed_qty"] or 0.0) > EPS
        if delivered < EPS:
            status, color, n_undelivered = "未齐套", "danger", n_undelivered + 1
        elif is_late and is_partial:
            status, color, n_partial = "部分齐套(延期)", "warning", n_partial + 1
        elif is_late:
            status, color, n_late = "延期齐套", "danger", n_late + 1
        elif is_partial:
            status, color, n_partial = "部分齐套", "warning", n_partial + 1
        else:
            status, color, n_ontime = "齐套", "success", n_ontime + 1
        # 归因
        reasons = []
        if str(r["order_id"]) in sale_slack:
            reasons.append("存在交付缺口（订单无法足额交付）")
        if mat_short:
            reasons.append("物料供给缺口（原材料/自制件松弛）")
        if cap_short:
            reasons.append("设备/工装能力缺口")
        if is_late and not reasons:
            # 无硬缺口仍延期 → 产能时序紧张（瓶颈）
            reasons.append("产能时序紧张（建议关注瓶颈设备排程）")
        # BOM 标准展开
        comps = _explode_components(edges, r["material_code"], qty)
        for c in comps:
            mst = masters.get(c["code"])
            s = sup.get(c["code"])
            c["category"] = _CATEGORY_LABELS.get(mst["category"], "?") if mst else "?"
            c["name"] = (mst["material_name"] if mst else "") or ""
            supply = s if s else None
            c["plan_supply"] = round(s["self"] + s["out"] + s["pur"], 1) if supply else 0.0
        orders.append({
            "order_id": r["order_id"], "product": r["material_code"],
            "product_name": (masters.get(r["material_code"])["material_name"]
                             if masters.get(r["material_code"]) else "") or "",
            "priority": r["priority_level"], "qty": round(qty, 1),
            "due": r["due_period"], "last_deliver": r["last_deliver"],
            "delayed_qty": round(r["delayed_qty"] or 0, 1),
            "penalty": round(r["penalty"] or 0, 0),
            "status": status, "color": color,
            "reasons": reasons, "components": comps,
        })
    total = len(orders)
    return {
        "has_result": True, "orders": orders,
        "kitting_rate": round(n_ontime / total * 100, 1) if total else 0.0,
        "n_ontime": n_ontime, "n_partial": n_partial,
        "n_late": n_late, "n_undelivered": n_undelivered, "total": total,
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
