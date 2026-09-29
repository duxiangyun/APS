"""APS 数据工具层：全部通过 HTTP 调用 aps 的 /open/* 接口。

工具体系（12 个只读工具）：
- 业务只读（6 个）：订单列表、排产计划、设备负荷、瓶颈分析、延期归因、经营 KPI
- 主数据只读（4 个）：物料主数据台账、BOM 多级展开、工艺路线、设备/工装台账
- 管理专属（2 个）：审计日志查询、系统运行状态巡检（仅 admin 角色）

约定
- 每个工具有明确的 JSON Schema（OpenAI function calling 格式，见 TOOLS）
- 每次调用记录日志：session_id / 工具名 / 参数 / 耗时 / 结果摘要（logs/tool_calls.jsonl）
- 全部只读，不做任何写操作
- 返回结果可携带 chart 字段，规范形态见下方 _gantt_chart / _load_chart / _kpi_chart
"""
import contextvars
import json
import time
from typing import Any

from . import aps_client
from . import audit
from . import role_config
from .aps_client import APSApiError
from .config import APS_CURRENT_PERIOD, APS_PERIOD_DAYS, TOOL_LOG_PATH

# 结果文本长度上限（供 LLM 消费，避免超长）
_TEXT_LIMIT = 6000
# 视图拉取条数上限（覆盖单次求解结果）
_VIEW_PAGE_SIZE = 500  # APS API page_size 上限为 500，超出会报 422


def _trim(text: str, limit: int = _TEXT_LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n...(过长已截断，原始 {len(text)} 字符)"


def _dumps(data: Any) -> str:
    return _trim(json.dumps(data, ensure_ascii=False, default=str))


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _round(v: Any, digits: int = 1) -> float:
    return round(_num(v), digits)


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
def log_tool_call(session_id: str, tool: str, params: dict,
                  duration_ms: float, summary: str,
                  role: str = "default", status: str = "success",
                  confirmed: bool = False, cache_hit: bool = False) -> None:
    """记录一条工具调用审计：SQLite audit_log 表（主）+ JSONL（备份）。

    role：发起调用的角色；status：success/failed；confirmed：是否经用户二次确认
    （当前工具全部只读且不在 requires_confirmation 白名单内，默认 False=无需确认）
    cache_hit：本次调用是否命中 20s 短时缓存（阶段一止血新增字段）
    """
    audit.log_tool_call(session_id, role, tool, params, duration_ms,
                        summary, confirmed=confirmed, status=status,
                        cache_hit=cache_hit)


# ---------------------------------------------------------------------------
# 短时缓存：一次对话常连续调用多个工具，避免重复拉全量视图
# ---------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 20.0
# 本次工具调用是否命中过短时缓存 → 写入 audit_log.cache_hit（按 asyncio 任务上下文隔离）
_CACHE_HIT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "tool_cache_hit", default=False)


async def _cached(key: str, loader) -> Any:
    hit = _CACHE.get(key)
    now = time.time()
    if hit and now - hit[0] < _CACHE_TTL:
        _CACHE_HIT.set(True)
        return hit[1]
    data = await loader()
    _CACHE[key] = (now, data)
    return data


async def _order_sale_rows() -> list[dict]:
    """res_view_order_sale 全量行（订单 × 交付点）"""
    async def load() -> list[dict]:
        data = await aps_client.aps_result_data("order_sale", page=1, page_size=_VIEW_PAGE_SIZE)
        return data.get("rows", [])
    return await _cached("order_sale", load)


async def _prod_machining_rows() -> list[dict]:
    """res_view_prod_machining 全量行（设备 × 物料 的周期产出/产能）"""
    async def load() -> list[dict]:
        data = await aps_client.aps_result_data("prod_machining", page=1, page_size=_VIEW_PAGE_SIZE)
        return data.get("rows", [])
    return await _cached("prod_machining", load)


async def _equip_load_payload() -> dict:
    """APS /open/equip-load（matrix + detail）"""
    return await _cached("equip_load", aps_client.aps_equip_load)


async def _equip_shadow_rows() -> list[dict]:
    """res_view_equip_shadow（设备周期影子价格）"""
    async def load() -> list[dict]:
        data = await aps_client.aps_result_data("equip_shadow", page=1, page_size=_VIEW_PAGE_SIZE)
        return data.get("rows", [])
    return await _cached("equip_shadow", load)


# ---------------------------------------------------------------------------
# 名称/周期解析：把口语化输入映射到 APS 中的编码
# ---------------------------------------------------------------------------
# 口语关键词 → 资源编码前缀（APS 资源：涂装-1/2、焊接设备1..5、装配1..10、机加1..3）
_RESOURCE_GROUPS: list[tuple[tuple[str, ...], str]] = [
    (("涂装", "喷涂", "喷漆", "paint"), "涂装"),
    (("焊接", "焊", "weld"), "焊接设备"),
    (("装配", "组装", "总装", "assemble"), "装配"),
    (("机加", "机加工", "加工", "cnc", "数控", "车床", "铣", "machin"), "机加"),
]


def resolve_resources(query: str, codes: list[str]) -> tuple[list[str], str]:
    """把用户对设备的表述解析为资源编码列表，返回 (命中列表, 说明)。

    支持：精确编码、编码前缀（"装配" → 装配1..10）、
          口语同义词（"CNC"/"数控" → 机加1..3）、
          末位序号（"CNC-01"/"机加#2" → 机加1 / 机加2）。
    """
    q = (query or "").strip()
    if not q:
        return codes, "未指定设备，返回全部设备"

    low = q.lower()
    exact = [c for c in codes if c.lower() == low]
    if exact:
        return exact, f"精确匹配设备 {exact[0]}"

    for words, prefix in _RESOURCE_GROUPS:
        for w in words:
            if w not in low:
                continue
            pool = [c for c in codes if c.startswith(prefix)]
            tail = low.split(w, 1)[1]
            digits = "".join(ch if ch.isdigit() else " " for ch in tail).split()
            if digits:
                seq = int(digits[0])
                hit = [c for c in pool if c[len(prefix):].lstrip("-_# ") == str(seq)]
                if hit:
                    return hit, f"'{q}' 按序号解析为设备 {hit[0]}"
                return [], (f"未找到设备 '{q}'。{prefix}类现有设备：{'、'.join(pool)}")
            return pool, f"'{q}' 解析为 {prefix} 类设备共 {len(pool)} 台"

    digits = [int(x) for x in "".join(ch if ch.isdigit() else " " for ch in low).split()]
    if digits:
        hit = [c for c in codes
               if "".join(ch for ch in c if ch.isdigit()) == str(digits[0])]
        if hit:
            return hit, f"'{q}' 按序号解析为 {hit[0]}"

    return [], ("未找到设备 '" + q + "'。可选：" + "、".join(codes[:12]) +
                ("…" if len(codes) > 12 else "") + "（也可用类别，如“装配1”“CNC-01”）")


def parse_period_range(spec: str, max_period: int) -> tuple[int, int, str]:
    """解析周期区间：支持 "1-6" / "3" / "第3期" / "最近3期" / "未来2期"；空=全部。"""
    import re
    s = (spec or "").strip()
    if not s:
        return 1, max_period, "全部周期"

    low = s.lower()
    nums = [int(x) for x in re.findall(r"\d+", low)]

    if any(k in low for k in ("最近", "过去", "以往", "recent", "last")):
        n = nums[0] if nums else 3
        start = max(1, APS_CURRENT_PERIOD - n + 1)
        return start, APS_CURRENT_PERIOD, f"最近 {n} 期（第{start}-{APS_CURRENT_PERIOD}期）"
    if any(k in low for k in ("未来", "今后", "接下来", "next", "future", "以后")):
        n = nums[0] if nums else 2
        end = min(max_period, APS_CURRENT_PERIOD + n - 1)
        return APS_CURRENT_PERIOD, end, f"未来 {n} 期（第{APS_CURRENT_PERIOD}-{end}期）"
    if any(k in low for k in ("今天", "当前", "today")):
        return APS_CURRENT_PERIOD, APS_CURRENT_PERIOD, f"当前周期（第{APS_CURRENT_PERIOD}期）"
    if len(nums) >= 2:
        a, b = min(nums[0], nums[1]), max(nums[0], nums[1])
        return max(1, a), min(max_period, b), f"第{a}-{b}期"
    if len(nums) == 1:
        return max(1, nums[0]), min(max_period, nums[0]), f"第{nums[0]}期"
    return 1, max_period, "全部周期"


# ---------------------------------------------------------------------------
# chart 规范形态（前端 RightPanel 直接消费）
#   甘特图 { "type": "gantt", "tasks": [...] }
#   负荷图 { "type": "load",  "resources": [...] }
#   KPI    { "type": "kpi",   "items": [...] }
# ---------------------------------------------------------------------------
# 交付状态（APS res_view_order_sale.delivery_status 原始取值）
STATUS_ONTIME = "按期交付"
STATUS_DELAYED = "延期交付"
STATUS_PARTIAL = "部分按期"
STATUS_UNDELIVERED = "未交付"

# 用户口语 → 原始状态取值
_STATUS_ALIAS = {
    "all": None,
    "ontime": STATUS_ONTIME,
    "delayed": STATUS_DELAYED,
    "partial": STATUS_PARTIAL,
    "undelivered": STATUS_UNDELIVERED,
    "按期": STATUS_ONTIME,
    "准时": STATUS_ONTIME,
    "延期": STATUS_DELAYED,
    "延迟": STATUS_DELAYED,
    "部分": STATUS_PARTIAL,
    "未交付": STATUS_UNDELIVERED,
}


def _gantt_chart(title: str, tasks: list[dict], periods: list[int]) -> dict:
    return {"type": "gantt", "title": title, "periods": periods, "tasks": tasks}


def _load_chart(title: str, matrix: list[dict], periods: list[int],
                highlight: list[str] | None = None) -> dict:
    """matrix（/open/equip-load）→ 负荷图数据"""
    resources: list[dict] = []
    for m in matrix:
        series = {str(p): _round(m.get(f"period_{p}", 0)) for p in periods}
        resources.append({
            "resource_code": m.get("resource_code"),
            "capacity": _round(m.get("capacity")),
            "peak_rate": _round(m.get("max_load_rate_pct")),
            "avg_rate": _round(m.get("avg_load_rate_pct")),
            "total_load": round(sum(series.values()), 1),
            "normal_cost": _round(m.get("normal_cost_total")),
            "periods": series,
        })
    resources.sort(key=lambda r: -r["total_load"])
    return {
        "type": "load",
        "title": title,
        "periods": periods,
        "resources": resources,
        "highlight": highlight or [],
    }


def _kpi_chart(title: str, items: list[dict]) -> dict:
    return {"type": "kpi", "title": title, "items": items}


def _order_row_map(rows: list[dict]) -> dict[int, dict]:
    """order_id → 该订单在排产结果中的交付汇总"""
    agg: dict[int, dict] = {}
    for r in rows:
        oid = int(r.get("order_id") or 0)
        item = agg.setdefault(oid, {
            "order_id": oid,
            "material_code": r.get("material_code"),
            "priority_level": r.get("priority_level"),
            "order_quantity": _num(r.get("order_quantity")),
            "due_period": r.get("due_period"),
            "delivered_qty": 0.0,
            "revenue": 0.0,
            "penalty": 0.0,
            "deliveries": [],
            "statuses": [],
        })
        item["delivered_qty"] += _num(r.get("delivery_quantity"))
        item["revenue"] += _num(r.get("revenue"))
        item["penalty"] += _num(r.get("delay_penalty"))
        item["statuses"].append(str(r.get("delivery_status")))
        item["deliveries"].append({
            "period": r.get("delivery_period"),
            "quantity": _round(r.get("delivery_quantity")),
            "status": r.get("delivery_status"),
            "delay_quantity": _round(r.get("delay_quantity")),
            "shadow_price": _round(r.get("shadow_price"), 2),
        })
    for item in agg.values():
        item["deliveries"].sort(key=lambda d: _num(d.get("period")))
        st = set(item["statuses"])
        item["delivery_status"] = (
            STATUS_DELAYED if STATUS_DELAYED in st
            else STATUS_PARTIAL if STATUS_PARTIAL in st
            else STATUS_ONTIME if STATUS_ONTIME in st
            else STATUS_UNDELIVERED
        )
        last = max((_num(d["period"]) for d in item["deliveries"]), default=0)
        item["last_delivery_period"] = int(last) if last else None
        item["ontime"] = item["delivery_status"] == STATUS_ONTIME
        item["satisfied_ratio"] = (
            round(item["delivered_qty"] / item["order_quantity"] * 100, 1)
            if item["order_quantity"] else 0.0
        )
    return agg



# ---------------------------------------------------------------------------
# 工具 1：get_orders —— 订单列表
# ---------------------------------------------------------------------------
async def get_orders(status: str = "all", due_before: int | None = None,
                     priority: int | None = None, limit: int = 30) -> dict:
    """查询需求订单列表，可按交付状态（ontime/delayed/undelivered/partial）、
    交期（第N期）、优先级过滤。"""
    rows = await _order_sale_rows()
    if not rows:
        return {"summary": "当前批次没有订单交付结果。请先在 APS 中执行求解。", "orders": []}

    order_map = _order_row_map(rows)
    want = _STATUS_ALIAS.get(str(status or "all").lower().strip(), None)

    items: list[dict] = []
    for item in order_map.values():
        if want and item["delivery_status"] != want:
            continue
        if due_before is not None and _num(item["due_period"]) > due_before:
            continue
        if priority is not None and int(_num(item["priority_level"])) != priority:
            continue
        items.append(item)

    items.sort(key=lambda x: (
        0 if x["delivery_status"] == STATUS_DELAYED else 1,
        _num(x["due_period"]), -_num(x["order_quantity"]),
    ))

    counts: dict[str, int] = {}
    for it in order_map.values():
        counts[it["delivery_status"]] = counts.get(it["delivery_status"], 0) + 1

    # 订单明细只保留前 limit 条（默认 30，LLM 消费够用；不传给 APS API 所以不受 500 限）
    brief = [
        {k: it[k] for k in (
            "order_id", "material_code", "priority_level", "order_quantity",
            "due_period", "last_delivery_period", "delivered_qty",
            "delivery_status", "satisfied_ratio", "penalty",
        )} for it in items[:limit]
    ]
    w = items[0] if items else None
    head = (f"最紧急：订单{w['order_id']}（交期第{w['due_period']}期，"
            f"{w['delivery_status']}，交付达成 {w['satisfied_ratio']}%）") if w else ""
    return {
        "summary": (f"共 {len(order_map)} 张订单；状态分布 "
                    + "、".join(f"{k}{v}张" for k, v in counts.items())
                    + (f"；按「{want}」过滤得 {len(items)} 张" if want else "")
                    + (f"；交期≤第{due_before}期" if due_before else "")
                    + (f"；{head}" if head else "") + "。"),
        "counts": counts,
        "matched": len(items) if want or due_before or priority else len(order_map),
        "orders": brief,
    }


# ---------------------------------------------------------------------------
# 工具 2：get_schedule —— 单订单排产计划（甘特图）
# ---------------------------------------------------------------------------
def _resource_plan_tasks(mat_code: str, prod_rows: list[dict],
                         periods: list[int], due: int | None) -> list[dict]:
    """从 prod_machining（设备 × 物料 周期产出）生成设备级甘特任务"""
    tasks: list[dict] = []
    for r in prod_rows:
        if str(r.get("material_code")) != str(mat_code):
            continue
        made = {p: _num(r.get(f"made_period_{p}")) for p in periods}
        active = [p for p, q in made.items() if q > 0]
        if not active:
            continue
        tasks.append({
            "name": f"{r.get('resource_code')} · {r.get('operation_code')}",
            "kind": "resource",
            "resource_code": r.get("resource_code"),
            "production_line": r.get("production_line"),
            "start": min(active),
            "end": max(active),
            "due": due,
            "quantity": {str(p): _round(made[p]) for p in active},
            "total": _round(sum(made.values())),
            "cap_total": _round(r.get("capacity_total")),
        })
    tasks.sort(key=lambda t: (t["start"], t["name"]))
    return tasks


async def get_schedule(order_id: int) -> dict:
    """单订单排产计划 + 交付点明细。交付点来自 res_view_order_sale；
    设备工序段来自 res_view_prod_machining（设备 × 物料），用于甘特图。"""
    order_map = _order_row_map(await _order_sale_rows())
    item = order_map.get(int(order_id))
    if not item:
        known = sorted(order_map)
        return {"summary": f"未找到订单 {order_id}。当前批次存在的订单号：{known[:20]}", "error": True}

    load = await _equip_load_payload()
    max_period = 12
    if load.get("matrix"):
        max_period = max(int(k.split("_")[1]) for k in load["matrix"][0] if k.startswith("period_"))
    periods = list(range(1, max_period + 1))

    prod_rows = await _prod_machining_rows()
    mat = item["material_code"]
    due = int(_num(item["due_period"]))
    res_tasks = _resource_plan_tasks(mat, prod_rows, periods, due)

    tasks: list[dict] = [{
        "name": f"订单{order_id} {mat}",
        "kind": "order",
        "start": min([t["start"] for t in res_tasks] or [1]),
        "end": item["last_delivery_period"] or due,
        "due": due,
        "deliveries": [{"period": d["period"], "quantity": d["quantity"], "status": d["status"]}
                       for d in item["deliveries"]],
        "status": item["delivery_status"],
    }]
    tasks.extend(res_tasks)

    last = item["last_delivery_period"] or due
    gap = last - due
    if res_tasks:
        summary = (
            f"订单{order_id}（{mat}，P{item['priority_level']}）：交期第{due}期，"
            f"{'按期交付' if gap <= 0 else f'实际最后交付第{last}期，延期 {gap} 期'}；"
            f"交付 {item['delivered_qty']:.0f}/{item['order_quantity']:.0f} 件"
            f"（达成 {item['satisfied_ratio']}%）；{len(res_tasks)} 个设备工序段"
            f"（第{res_tasks[0]['start']}-{res_tasks[-1]['end']}期）。"
        )
    else:
        summary = (f"订单{order_id}（{mat}）：交期第{due}期，交付 {item['satisfied_ratio']}%，"
                   f"未找到设备工序明细。")

    return {
        "summary": summary,
        "order": {k: item[k] for k in (
            "order_id", "material_code", "priority_level", "order_quantity",
            "due_period", "last_delivery_period", "delivered_qty",
            "delivery_status", "satisfied_ratio", "penalty", "revenue",
        )},
        "deliveries": item["deliveries"],
        "resource_tasks": res_tasks,
        "chart": _gantt_chart(f"订单{order_id}（{mat}）排产甘特图", tasks, periods),
    }




# ---------------------------------------------------------------------------
# 工具 3：get_machine_load —— 设备负荷（负荷图）
# ---------------------------------------------------------------------------
async def get_machine_load(resource: str = "", period: str = "") -> dict:
    """设备负荷查询。resource 支持精确名 / 类别前缀（涂装/装配/CNC…）/ 末位序号；
    period 支持 '1-6' / '最近3期' / '第3期' / '今天' 等。"""
    load = await _equip_load_payload()
    matrix = load.get("matrix", [])
    if not matrix:
        return {"summary": "当前批次没有设备负荷结果（equip-load 为空）。", "error": True}

    # 设备名去重：同名多行仅保留首行（命中说明 / 负荷图 / top 排名不再出现重复设备）
    codes = list(dict.fromkeys(str(m.get("resource_code")) for m in matrix))
    max_period = max(int(k.split("_")[1]) for k in matrix[0] if k.startswith("period_"))
    start, end, note = parse_period_range(period, max_period)
    periods = list(range(start, end + 1))

    hit, how = resolve_resources(resource, codes)
    if not hit:
        return {"summary": how, "error": True}
    picked = [m for m in matrix if str(m.get("resource_code")) in hit]
    dedup: dict[str, dict] = {}
    for m in picked:
        dedup.setdefault(str(m.get("resource_code")), m)
    picked = list(dedup.values())

    chart = _load_chart(f"设备负荷（{note}）", picked, periods,
                        highlight=[r["resource_code"]
                                   for r in sorted(
                                       ({"resource_code": str(m.get("resource_code")),
                                         "v": _num(m.get("max_load_rate_pct"))} for m in picked),
                                       key=lambda x: -x["v"])[:3]])

    top = sorted(
        ({"code": str(m.get("resource_code")), "peak": _num(m.get("max_load_rate_pct")),
          "avg": _num(m.get("avg_load_rate_pct"))} for m in picked),
        key=lambda x: -x["peak"],
    )
    pk = top[0] if top else None
    over95 = [t["code"] for t in top if t["peak"] >= 95]
    summary = ("「{how}」（{note}）：命中 {n} 台，峰值最高 {code} {peak:.1f}%（均值 {avg:.1f}%）；"
               "{over}").format(
        how=how, note=note, n=len(picked),
        code=pk["code"] if pk else "-", peak=pk["peak"] if pk else 0.0,
        avg=pk["avg"] if pk else 0.0,
        over="达到/接近满负荷：" + "、".join(over95) + "。" if over95 else "无设备达到 95% 负荷。",
    )
    return {"summary": summary, "periods": periods,
            "resources": chart["resources"][:50], "chart": chart}


# ---------------------------------------------------------------------------
# 工具 4：get_bottleneck —— 瓶颈设备
# ---------------------------------------------------------------------------
async def get_bottleneck(period: str = "", top_n: int = 5, resource: str = "") -> dict:
    """按峰值负荷率 + 影子价格排序识别瓶颈；影子价格来自 res_view_equip_shadow。"""
    load = await _equip_load_payload()
    matrix: list[dict] = load.get("matrix", [])
    if not matrix:
        return {"summary": "没有设备负荷数据，无法识别瓶颈。", "error": True}

    max_period = max(int(k.split("_")[1]) for k in matrix[0] if k.startswith("period_"))
    start, end, note = parse_period_range(period, max_period)
    periods = list(range(start, end + 1))

    shadow_rows = await _equip_shadow_rows()
    shadow_avg: dict[str, float] = {}
    for r in shadow_rows:
        code = str(r.get("resource_code"))
        vals = [_num(r.get(f"period_{p}")) for p in periods]
        shadow_avg[code] = round(sum(vals) / len(vals), 1) if vals else 0.0
    smax = max(shadow_avg.values()) if shadow_avg else 0.0

    rows: list[dict] = []
    for m in matrix:
        code = str(m.get("resource_code"))
        if resource and resource.lower() not in code.lower():
            continue
        cap = _num(m.get("capacity")) or 1.0
        pv = [_num(m.get(f"period_{p}")) for p in periods]
        peak_val = max(pv) if pv else 0.0
        peak_p = periods[pv.index(peak_val)] if pv and peak_val else None
        rows.append({
            "resource_code": code,
            "peak_rate": round(peak_val / cap * 100, 1),
            "peak_period": peak_p,
            "avg_rate": round((sum(pv) / len(pv)) / cap * 100, 1) if pv else 0.0,
            "total_load": round(sum(pv), 1),
            "capacity": round(cap, 1),
            "shadow_price": shadow_avg.get(code, 0.0),
            "shadow_score": round(shadow_avg.get(code, 0.0) / smax * 100, 1) if smax else 0.0,
        })
    rows.sort(key=lambda r: (-r["peak_rate"], -r["shadow_score"]))
    top = rows[: max(1, int(top_n))]
    if not top:
        return {"summary": f"未命中设备（输入‘{resource}’）。", "error": True}

    lines = [
        f"{i+1}. {r['resource_code']} 峰值 {r['peak_rate']:.1f}%（第{r['peak_period']}期）"
        f" · 均值 {r['avg_rate']:.1f}% · 影子价格 {r['shadow_price']:.1f}"
        for i, r in enumerate(top)
    ]
    over95 = [r["resource_code"] for r in top if r["peak_rate"] >= 95]
    summary = (f"瓶颈设备 Top{len(top)}（{note}）：\n" + "\n".join(lines) + "\n"
               f"判据：峰值负荷率≥95% 或影子价格显著高于他设备即视为瓶颈；"
               f"本次 {'、'.join(over95) if over95 else '无设备达到 95%'} 满负荷。")

    chart = _load_chart(f"瓶颈设备负荷对比（{note}）", top, periods,
                        highlight=[r["resource_code"] for r in top[:3]])
    chart["bottlenecks"] = [
        {"resource_code": r["resource_code"], "peak_rate": r["peak_rate"],
         "peak_period": r["peak_period"], "shadow_price": r["shadow_price"]} for r in top
    ]
    return {"summary": summary, "bottlenecks": chart["bottlenecks"],
            "periods": periods, "chart": chart}

# ---------------------------------------------------------------------------
# 辅助：explain_delay 用的周期峰值率 computation
# ---------------------------------------------------------------------------
def _period_peak_rates(matrix: list[dict], window: list[int]) -> list[dict]:
    """求每个周期的最高负荷率设备（用于 explain_delay 的产能挤占 analysis）。

    matrix 形如 /open/equip-load 返回的 matrix 列表：
        {resource_code, capacity, period_1, period_2, ..., max_load_rate_pct, ...}
    """
    rows: list[dict] = []
    for p in window:
        best_code = "-"
        best_rate = 0.0
        for m in matrix:
            cap = _num(m.get("capacity")) or 1.0
            load_val = _num(m.get(f"period_{p}", 0))
            rate = round(load_val / cap * 100, 1) if cap > 0 else 0.0
            if rate > best_rate:
                best_rate = rate
                best_code = str(m.get("resource_code", "-"))
        rows.append({
            "resource_code": best_code,
            "peak_rate": best_rate,
            "peak_period": p,
        })
    rows.sort(key=lambda r: -r["peak_rate"])
    return rows[:5]


# ---------------------------------------------------------------------------
# 工具 5：explain_delay —— 订单延期归因
# ---------------------------------------------------------------------------
async def explain_delay(order_id: int) -> dict:
    order_map = _order_row_map(await _order_sale_rows())
    item = order_map.get(int(order_id))
    if not item:
        return {"summary": f"未找到订单 {order_id}。可用：{sorted(order_map)[:20]}", "error": True}

    due = int(_num(item["due_period"]))
    last = item["last_delivery_period"] or due
    gap = last - due
    if gap <= 0 and item["delivery_status"] != STATUS_PARTIAL:
        return {
            "summary": (f"订单{order_id} 实际按期交付（交期第{due}期，"
                        f"最后交付第{last}期），不存在延期。"),
            "order": {k: item[k] for k in (
                "order_id", "material_code", "due_period",
                "last_delivery_period", "delivery_status", "penalty",
            )},
        }

    load = await _equip_load_payload()
    matrix = load.get("matrix", [])
    window = list(range(max(1, due - 1), min(last + 2, 12)))
    peaks = _period_peak_rates(matrix, window)
    # 设备名去重：同一设备跨周期只保留峰值最高的一条（证据文案 / 冲突设备不再重复）
    _best: dict[str, dict] = {}
    for p in peaks:
        code = p.get("resource_code")
        if code not in _best or _num(p.get("peak_rate")) > _num(_best[code].get("peak_rate")):
            _best[code] = p
    peaks = sorted(_best.values(), key=lambda x: -_num(x.get("peak_rate")))
    hot = [p for p in peaks if p["peak_rate"] >= 90]

    sp = [d["shadow_price"] for d in item["deliveries"] if d["shadow_price"] is not None]
    avg_sp = round(sum(sp) / len(sp), 1) if sp else 0.0
    max_sp = max(sp) if sp else 0.0

    same_due = [
        o for o in order_map.values()
        if int(_num(o["due_period"])) <= due and o["order_id"] != item["order_id"]
        and int(_num(o["priority_level"])) < int(_num(item["priority_level"]))
    ]
    higher = sorted(same_due, key=lambda o: int(_num(o["priority_level"])))[:5]

    # 证据 2 文案：设备名去重（同名设备只出现一次，不重复堆叠）
    if hot:
        hot_codes = "、".join(h["resource_code"] for h in hot)
        peak_code = peaks[0]["resource_code"] if peaks else "-"
        peak_rate = peaks[0]["peak_rate"] if peaks else 0.0
        load_seg = (f"存在满负荷设备 {hot_codes}（峰值 {peak_rate:.1f}%）"
                    if len(hot) == 1 else
                    f"存在满负荷设备 {hot_codes}；峰值最高 {peak_code} {peak_rate:.1f}%")
    else:
        load_seg = "无设备达到 90%"

    evidences = [
        f"交期第{due}期 → 实际延至第{last}期（延期 {gap} 期）；"
        f"交付 {item['delivered_qty']:.0f}/{item['order_quantity']:.0f} 件"
        f"（达成 {item['satisfied_ratio']}%），延期罚金 {item['penalty']:.0f}",
        f"交期窗口第{window[0]}-{window[-1]}期设备负荷：" + load_seg,
        f"该订单交付点影子价格：平均 {avg_sp}，峰值 {max_sp}（产能紧张度指标）",
    ]
    if higher:
        evidences.append(
            "同期更高优先级订单：" + "、".join(
                f"订单{o['order_id']}(P{o['priority_level']})" for o in higher)
            + " 可能挤占了瓶颈产能"
        )

    if hot:
        reason = (f"产能挤占：第{window[0]}-{window[-1]}期 "
                  f"{'、'.join(h['resource_code'] for h in hot[:3])} 等设备已达/接近满负荷，"
                  f"该订单被排在其后可用周期，从而延期。")
    elif avg_sp > 0:
        reason = "工序衔接与排程顺序：设备未满负荷，延期多因上下游等待与优先级排程顺序。"
    else:
        reason = "优先级排程：被更高优先级订单优先，当前批次允许在最大延期约束内后置。"

    chart = _gantt_chart(
        f"订单{order_id} 延期对比（交期第{due}期/实际第{last}期）",
        [{
            "name": f"订单{order_id} {item['material_code']}",
            "kind": "order",
            "start": min([d["period"] for d in item["deliveries"]] or [1]),
            "end": last,
            "due": due,
            "deliveries": [{"period": d["period"], "quantity": d["quantity"],
                            "status": d["status"]} for d in item["deliveries"]],
            "status": item["delivery_status"],
        }],
        list(range(1, 13)),
    )

    return {
        "summary": f"订单{order_id}（{item['material_code']}）延期归因：{reason}\n证据：\n"
                   + "\n".join(f"· {e}" for e in evidences),
        "reason": reason,
        "evidences": evidences,
        "order": {k: item[k] for k in (
            "order_id", "material_code", "priority_level", "order_quantity",
            "due_period", "last_delivery_period", "delivery_status",
            "satisfied_ratio", "penalty",
        )},
        "conflict_resources": [
            {"resource_code": p["resource_code"], "peak_rate": p["peak_rate"],
             "peak_period": p["peak_period"]} for p in peaks[:5]
        ],
        "higher_priority_orders": [
            {"order_id": o["order_id"], "priority_level": o["priority_level"],
             "delivery_status": o["delivery_status"]} for o in higher
        ],
        "chart": chart,
    }





# ---------------------------------------------------------------------------
# 工具 6：get_kpi —— 经营 KPI 卡片
# ---------------------------------------------------------------------------
async def get_kpi() -> dict:
    summary = await aps_client.aps_kpi_summary()
    kpi = (summary.get("kpi") or {}) if isinstance(summary, dict) else {}
    if not kpi:
        return {"summary": "当前没有经营 KPI 数据，请先在 APS 中完成求解。", "error": True}

    currency = "元"
    items: list[dict] = [
        {"key": "sales_revenue", "label": "销售收入", "value": _round(kpi.get("sales_revenue")),
         "unit": currency, "hint": "订单总收入"},
        {"key": "manufacturing_cost", "label": "制造成本", "value": _round(kpi.get("manufacturing_cost")),
         "unit": currency, "hint": "在制生产成本"},
        {"key": "purchase_cost", "label": "采购成本", "value": _round(kpi.get("purchase_cost")),
         "unit": currency, "hint": "外购/原料采购"},
        {"key": "outsource_cost", "label": "外协成本", "value": _round(kpi.get("outsource_cost")),
         "unit": currency, "hint": "委外加工费"},
        {"key": "inventory_cost", "label": "库存成本", "value": _round(kpi.get("inventory_cost")),
         "unit": currency, "hint": "期末库存持有成本"},
        {"key": "delay_penalty", "label": "延期罚金", "value": _round(kpi.get("delay_penalty")),
         "unit": currency, "hint": "订单延期扣除"},
        {"key": "profit", "label": "利润", "value": _round(kpi.get("profit")),
         "unit": currency, "hint": "目标函数最大值", "emphasize": True, "color": "green"},
    ]
    profit = _num(kpi.get("profit"))
    revenue = _num(kpi.get("sales_revenue"))
    ratio = round(profit / revenue * 100, 1) if revenue else 0.0

    delivery = await aps_client.aps_kpi_delivery()
    by_priority: list[dict] = []
    if isinstance(delivery, dict):
        by_priority = delivery.get("by_priority", [])
        ontime_rate = delivery.get("ontime_rate")
        items.append({"key": "ontime_rate", "label": "准交率",
                      "value": _round(ontime_rate, 1), "unit": "%",
                      "hint": "按时交付订单比例", "emphasize": True, "color": "blue"})

    rows = await _order_sale_rows()
    counts: dict[str, int] = {}
    for r in rows:
        st = str(r.get("delivery_status"))
        counts[st] = counts.get(st, 0) + 1

    parts = [f"利润 {profit:.0f} 元（毛利率 {ratio}%）" if revenue else ""]
    if by_priority:
        parts.append("准交率 " + (str(delivery.get("ontime_rate")) + "%"))
    parts = [p for p in parts if p]
    summary = "经营 KPI 概览：" + "，".join(parts) + "；" + "、".join(
        f"{k}{v}单" for k, v in counts.items()) + "。"

    chart = _kpi_chart(summary, items)
    chart["delivery_by_priority"] = by_priority
    chart["run_id"] = kpi.get("run_id")
    return {"summary": summary,
            "kpi": {k: _round(kpi.get(k)) for k in (
                "sales_revenue", "manufacturing_cost", "purchase_cost",
                "outsource_cost", "inventory_cost", "delay_penalty", "profit",
            )},
            "metrics": {"profit_margin": ratio},
            "delivery_by_priority": by_priority,
            "chart": chart}


# ---------------------------------------------------------------------------
# 工具 7：get_audit_logs —— 审计日志查询（仅 admin，阶段一止血新增）
# ---------------------------------------------------------------------------
async def get_audit_logs(session_id: str = "", role: str = "", limit: int = 20) -> dict:
    """查询 audit_log 审计记录（最近优先）。session_id/role 为空表示不过滤。"""
    limit = max(1, min(int(limit or 20), 100))
    rows = audit.query_logs(session_id=session_id or None,
                            role=role or None, limit=limit)
    ok = sum(1 for r in rows if r.get("status") == "success")
    brief = [
        {k: r.get(k) for k in (
            "id", "created_at", "session_id", "role", "tool_name",
            "status", "cache_hit", "confirmed", "duration_ms", "result_summary",
        )} for r in rows
    ]
    summary = (f"审计日志最近 {len(rows)} 条（成功 {ok} / 失败 {len(rows) - ok}）"
               + (f"，过滤 session_id={session_id}" if session_id else "")
               + (f"、role={role}" if role else "") + "。")
    return {"summary": summary, "count": len(rows), "logs": brief}


# ---------------------------------------------------------------------------
# 工具 8：get_system_status —— 系统运行状态巡检（仅 admin，阶段一止血新增）
# ---------------------------------------------------------------------------
async def get_system_status() -> dict:
    """系统状态：LLM 配置（脱敏）/ APS 连通 / 审计统计 / 短时缓存。"""
    from . import llm_config  # 局部导入，避免模块级潜在循环依赖

    cfg = llm_config.get_config()
    llm = {
        "configured": bool(cfg.get("api_key")) and bool(cfg.get("base_url")),
        "model": cfg.get("model"),
        "base_url": cfg.get("base_url"),
        "fallback_model": cfg.get("fallback_model") or "",
        # 注意：api_key 明文绝不进入结果
    }
    aps_ok = False
    aps_info: dict = {}
    try:
        aps_info = await aps_client.aps_health() or {}
        aps_ok = str(aps_info.get("status", "ok")).lower() == "ok"
    except Exception as e:  # noqa: BLE001
        aps_info, aps_ok = {"error": str(e)}, False

    recent = audit.query_logs(limit=100)
    ok = sum(1 for r in recent if r.get("status") == "success")
    lines = [
        f"- LLM：{'已配置' if llm['configured'] else '未配置'}"
        f"（{llm['model'] or '-'}，备用 {llm['fallback_model'] or '无'}）",
        "- APS：" + ("连通" if aps_ok else f"不可达（{aps_info.get('error') or aps_info}）"),
        f"- 审计：最近 {len(recent)} 条，成功 {ok} / 失败 {len(recent) - ok}",
        f"- 缓存：{len(_CACHE)} 项（TTL {int(_CACHE_TTL)}s）",
    ]
    return {"summary": "系统状态巡检：\n" + "\n".join(lines),
            "llm": llm,
            "aps": {"connected": aps_ok, "detail": aps_info},
            "audit": {"recent_calls": len(recent), "recent_success": ok,
                      "recent_failed": len(recent) - ok},
            "cache": {"entries": len(_CACHE), "ttl_sec": _CACHE_TTL}}


# ---------------------------------------------------------------------------
# 主数据工具（9-12）：物料 / BOM / 工艺路线 / 设备工装台账
#   - 全部对应 aps /open/md/*（aps 侧用只读连接 mode=ro），供 masterdata 角色核对基础数据
#   - 字段名以 aps 实际返回为准：initial_inventory / min_inventory / max_inventory /
#     step_order（数据库真实列名 step_order，非旧文档的 step_no）
#   - 列表类工具单次拉 _MD_LIST_PAGE_SIZE 条（aps page_size 上限 500）；主数据变动频率低
#     但核对要求「看到当前值」，因此不加短时缓存，每次直读 aps
# ---------------------------------------------------------------------------
_MD_LIST_PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# 工具 9：get_material_master —— 物料主数据台账
# ---------------------------------------------------------------------------
async def get_material_master(code: str = "", search: str = "",
                              category: str = "") -> dict:
    """物料台账（GET /open/md/materials）：编码精确 / 名称-编码模糊 / 类别过滤。"""
    code = str(code or "").strip()
    search = str(search or "").strip()
    category = str(category or "").strip()
    data = await aps_client.aps_md_materials(
        code=code, search=search, category=category,
        page=1, page_size=_MD_LIST_PAGE_SIZE)
    items = data.get("items") or []
    total = int(_num(data.get("total"), len(items)))
    cond = "、".join(x for x in (
        f"编码={code}" if code else "",
        f"关键字={search}" if search else "",
        f"类别={category}" if category else "",
    ) if x) or "全部物料"
    if not items:
        return {"summary": f"物料台账未命中记录（检索条件：{cond}；库中物料共 {total} 条）。",
                "total": total, "count": 0, "items": []}

    cats: dict[str, int] = {}
    incomplete: list = []
    brief: list[dict] = []
    for it in items:
        key = str(it.get("category") or "-")
        cats[key] = cats.get(key, 0) + 1
        if not it.get("unit") or not it.get("category") or it.get("min_inventory") is None:
            incomplete.append(it.get("material_code"))
        brief.append({k: it.get(k) for k in (
            "material_code", "material_name", "category", "unit",
            "initial_inventory", "target_end_inventory",
            "min_inventory", "max_inventory", "holding_cost_rate")})
    return {
        "summary": (f"物料台账命中 {len(brief)}/{total} 条（检索条件：{cond}；类别分布 "
                    + "、".join(f"{k} {v} 条" for k, v in sorted(cats.items()))
                    + (f"；{len(incomplete)} 条缺单位/类别/库存下限，需维护"
                       if incomplete else "；关键字段无缺失") + "）。"),
        "total": total, "count": len(brief), "items": brief,
        "incomplete": incomplete,
    }


# ---------------------------------------------------------------------------
# 工具 10：get_bom —— BOM 多级展开
# ---------------------------------------------------------------------------
async def get_bom(parent_material_code: str = "", material_code: str = "",
                  max_level: int = 5) -> dict:
    """BOM 多级展开（GET /open/md/bom）：父件向下逐层列出子件、用量、单位与层级。

    material_code 是 parent_material_code 的容错别名（LLM 常把两个参数名混用）；
    max_level 超出上限返回提示，截断时 summary 与 truncated 均会标注。
    """
    root = str(parent_material_code or material_code or "").strip()
    if not root:
        return {"summary": "需要提供物料编码（parent_material_code）才能展开 BOM。",
                "error": True}
    level = max(1, min(int(_num(max_level, 5) or 5), 10))
    data = await aps_client.aps_md_bom(parent_material_code=root, max_level=level)
    items = data.get("items") or []
    name = str(data.get("material_name") or "")
    label = f"{root}（{name}）" if name else root
    if not items:
        return {"summary": f"{label} 未展开出任何子件（该物料不在 BOM 中或已是最底层物料）。",
                "material_code": root, "material_name": name, "max_level": level,
                "total": 0, "truncated": False, "levels": [], "items": []}

    per_level: dict[int, int] = {}
    for it in items:
        lv = int(_num(it.get("level"), 0))
        per_level[lv] = per_level.get(lv, 0) + 1
    levels = sorted(per_level)
    truncated = bool(data.get("truncated"))
    brief = [{k: it.get(k) for k in (
        "level", "parent_code", "child_code", "child_name",
        "child_category", "unit", "quantity", "bom_level")} for it in items]
    return {
        "summary": (f"BOM 展开 {label}：共 {len(brief)} 条子件关系、{len(levels)} 层"
                    f"（最深第{levels[-1]}层："
                    + "、".join(f"第{k}层{v}条" for k, v in sorted(per_level.items())) + "）"
                    + (f"；已达 max_level={level} 上限、更深层级未展开（已截断，truncated=true），"
                       f"如需完整结构请提高 max_level" if truncated else "；已展开完整结构")
                    + "。"),
        "material_code": root, "material_name": name, "max_level": level,
        "total": len(brief), "truncated": truncated,
        "levels": levels, "per_level": per_level, "items": brief,
    }


# ---------------------------------------------------------------------------
# 工具 11：get_routing —— 工艺路线
# ---------------------------------------------------------------------------
async def get_routing(material_code: str = "", routing_id: int | None = None) -> dict:
    """工艺路线（GET /open/md/routing）：按物料返回全部路线与工序明细。

    同一物料可能维护多条路线（is_default 标记默认），因此 summary 会提示路线数。
    """
    code = str(material_code or "").strip()
    if not code:
        return {"summary": "需要提供物料编码（material_code）才能查询工艺路线。",
                "error": True}
    rid = None if routing_id in (None, "") else int(_num(routing_id))
    data = await aps_client.aps_md_routing(material_code=code, routing_id=rid)
    steps = data.get("steps") or []
    routes = data.get("routes") or []
    if not steps:
        return {"summary": f"物料 {code} 未维护工艺路线（routes / steps 均为空，需在系统侧补充）。",
                "material_code": code, "route_count": 0, "total": 0,
                "routes": [], "steps": []}

    orders = [int(_num(s.get("step_order"), 0)) for s in steps]
    # 待维护项：工序未绑定设备 / 工序的设备未绑定产线（core_md_resource.line_code 为空）
    no_equip = [s.get("step_order") for s in steps if not s.get("equipment_code")]
    no_line = [s.get("step_order") for s in steps
               if s.get("equipment_code") and not s.get("resource_line_code")]
    default_route = next((r for r in routes if r.get("is_default")), None)
    brief_routes = [{k: r.get(k) for k in (
        "routing_id", "alt_route_id", "total_lead_time", "is_default",
        "is_active", "step_count")} for r in routes]
    brief_steps = [{k: s.get(k) for k in (
        "routing_id", "step_order", "step_no", "operation_code", "operation_name",
        "equipment_code", "equipment_name", "equipment_type",
        "production_line_code", "resource_line_code",
        "fixture_code", "fixture_quantity", "max_lead_time")} for s in steps]
    return {
        "summary": (f"物料 {code} 共 {len(brief_routes)} 条工艺路线、{len(brief_steps)} 道工序"
                    f"（步序 {min(orders)}-{max(orders)}）"
                    + (f"；默认路线 routing_id={default_route.get('routing_id')}、"
                       f"总提前期 {default_route.get('total_lead_time')}"
                       if default_route else "")
                    + (f"；{len(brief_routes)} 条路线并存，需核对是否重复维护"
                       if len(brief_routes) > 1 else "")
                    + (f"；{len(no_equip)} 道工序未绑定设备，需维护" if no_equip else "")
                    + (f"；{len(no_line)} 道工序的设备未绑定产线"
                       f"（设备主数据 line_code 为空），产线归属需维护"
                       if no_line else "") + "。"),
        "material_code": code, "route_count": len(brief_routes),
        "total": len(brief_steps), "multi_route": len(brief_routes) > 1,
        "default_routing_id": default_route.get("routing_id") if default_route else None,
        "routes": brief_routes, "steps": brief_steps,
        "unbound_equipment_steps": no_equip, "unbound_line_steps": no_line,
    }


# ---------------------------------------------------------------------------
# 工具 12：get_resource_master —— 设备 / 工装台账
# ---------------------------------------------------------------------------
async def get_resource_master(code: str = "", type: str = "",  # noqa: A002 与 aps 接口同名
                              page: int = 1, page_size: int = 50) -> dict:
    """设备/工装台账（GET /open/md/resources）：编码精确 / 类型过滤 + 分页。

    type 支持数据库值 EQUIPMENT（设备）/ FIXTURE（工装）/ LINE（产线）与中文别名。
    """
    res_code = str(code or "").strip()
    res_type = str(type or "").strip()  # noqa: A002
    page = max(1, int(_num(page, 1) or 1))
    page_size = max(1, min(int(_num(page_size, 50) or 50), 500))
    data = await aps_client.aps_md_resources(
        code=res_code, resource_type=res_type, page=page, page_size=page_size)
    items = data.get("items") or []
    total = int(_num(data.get("total"), len(items)))
    cond = "、".join(x for x in (
        f"编码={res_code}" if res_code else "",
        f"类型={res_type}" if res_type else "") if x) or "全部资源"
    if not items:
        return {"summary": f"资源台账未命中记录（检索条件：{cond}；库中资源共 {total} 条）。",
                "total": total, "page": page, "page_size": page_size,
                "count": 0, "items": []}

    types: dict[str, int] = {}
    no_line: list = []
    brief: list[dict] = []
    for it in items:
        t = str(it.get("resource_type") or "-")
        types[t] = types.get(t, 0) + 1
        if not it.get("line_code"):
            no_line.append(it.get("resource_code"))
        brief.append({k: it.get(k) for k in (
            "resource_code", "resource_name", "resource_type", "line_code",
            "line_name", "line_type", "quantity", "unit_cost",
            "utilization_rate", "overtime_rate", "overtime_cost_multiplier")})
    return {
        "summary": (f"资源台账命中 {len(brief)}/{total} 条（检索条件：{cond}；类型分布 "
                    + "、".join(f"{k} {v} 条" for k, v in sorted(types.items()))
                    + (f"；{len(no_line)} 条未绑定产线（line_code 为空），产线归属待维护"
                       if no_line else "；产线归属完整") + "）。"),
        "total": total, "page": page, "page_size": page_size,
        "count": len(brief), "items": brief, "unbound_line": no_line,
    }


# ---------------------------------------------------------------------------
# What-if 沙盒工具（13-14）：plan_whatif（只读） / simulate_insert_order（写）
#   - 对应 aps /open/whatif/*；沙盒在 aps 侧运行，参数与订单行求解后自动恢复，
#     不改变正式数据（见 aps whatif_service 模块文档）
#   - simulate_insert_order 为写工具（readonly=False）：它在 aps 侧创建沙盒场景并
#     触发一次真实求解（消耗算力、产生新 run），因此在角色白名单与提示词中需明确
#     「执行前先与用户确认假设」
#   - KPI 展示名与 key 的映射：aps 返回 key（profit / ontime_rate …），
#     这里统一映射为业务中文名，便于 LLM 与用户直接解读
# ---------------------------------------------------------------------------
_KPI_LABELS = {
    "orders": "订单总数",
    "ontime_rate": "订单准交率",
    "delayed": "延期订单数",
    "undelivered": "未交付订单数",
    "revenue": "销售收入",
    "profit": "利润总额",
    "penalty": "延期罚金",
    "mfg_cost": "制造成本",
    "out_cost": "外协费用",
    "purchase_cost": "采购成本",
    "inventory_cost": "库存成本",
    "fixture_cost": "工装费用",
    "infeasible_cost": "产能不足惩罚",
}
# 解读结论时优先关注的核心指标（按 key 匹配，兼容 aps label 的单位后缀差异）
_WHATIF_FOCUS_KEYS = ("profit", "ontime_rate", "infeasible_cost", "revenue", "delayed")
# 差值展示：整数/小数量级直出，超过万位加千分位，避免 %g 输出成 4.89842e+06
def _fmt_delta(v) -> str:
    """差值格式化：None → 无数据；整数直出；带千分位"""
    if v is None:
        return "无数据"
    if float(v).is_integer():
        return f"{int(v):+,}"
    return f"{v:+.2f}"


def _kpi_block(cmp: dict) -> dict:
    """把 aps /open/whatif/compare 的响应转成 {中文名: {baseline,new,diff,unit}} 结构"""
    ka, kb, diff = cmp.get("kpi_a") or {}, cmp.get("kpi_b") or {}, cmp.get("diff") or {}
    block: dict[str, dict] = {}
    for r in cmp.get("rows") or []:
        key = r.get("key")
        if not key:
            continue
        name = r.get("label") or _KPI_LABELS.get(key, key)
        block[name] = {
            "key": key,
            "baseline": ka.get(key),
            "new": kb.get(key),
            "diff": diff.get(key),
            "a_text": r.get("a"),
            "b_text": r.get("b"),
            "direction": r.get("direction"),
            "better": r.get("better") or None,
        }
    return block


def _kpi_summary_text(block: dict, baseline_id: int, new_id: int) -> str:
    """生成 KPI 对比的中文摘要：先核心指标结论，再全量明细"""
    focus, rest = [], []
    for name, v in block.items():
        line = (f"{name}：基线 {v['a_text']} → 沙盒 {v['b_text']}"
                f"（差 {_fmt_delta(v['diff'])}）")
        (focus if v.get("key") in _WHATIF_FOCUS_KEYS else rest).append(line)
    tail = "\n".join(f"- {s}" for s in focus) or "（无核心指标数据）"
    if rest:
        tail += "\n其余指标：\n" + "\n".join(f"- {s}" for s in rest)
    return (f"KPI 对比（基线版本 #{baseline_id} vs 沙盒版本 #{new_id}）：\n" + tail)


async def plan_whatif(status: str = "all", limit: int = 20) -> dict:
    """列出 aps 侧已有的 What-if 模拟场景（只读）。"""
    data = await aps_client.aps_whatif_scenarios(status=status)
    items = (data or {}).get("scenarios") or []
    brief = [
        {
            "sid": s.get("id"),
            "name": s.get("name"),
            "status": s.get("status"),
            "orders": s.get("orders") or [],
            "order_count": len(s.get("orders") or []),
            "baseline_run_id": s.get("baseline_run_id"),
            "run_id": s.get("run_id"),
            "created_at": s.get("created_at"),
            "finished_at": s.get("finished_at"),
        }
        for s in items[:limit]
    ]
    lines = "\n".join(
        f"- {b['sid']} | {b['name']} | 状态{b['status']} | 插单{b['order_count']}条"
        f" | 基线#{b['baseline_run_id'] or '-'} 沙盒#{b['run_id'] or '-'}"
        for b in brief)
    return {
        "summary": (f"What-if 场景共 {len(items)} 个（过滤={status}）"
                    + (("：\n" + lines) if lines else "，暂无场景")),
        "total": len(items), "status_filter": status, "scenarios": brief,
    }


async def simulate_insert_order(product_code: str, quantity: float, due_period: int,
                                priority_level: int = 2, max_delay_allowed: int = 1,
                                delay_penalty: float = 0.0) -> dict:
    """插单模拟（写操作）：在 aps 沙盒中插入一张订单并重新求解，返回 KPI 对比。

    流程：创建场景 → 触发求解（阻塞，通常数秒到数十秒）→ 与基线版本对比 13 项 KPI。
    """
    order = {
        "product_code": product_code,
        "quantity": _num(quantity),
        "due_period": int(_num(due_period)),
        "priority_level": int(_num(priority_level, 2)),
        "max_delay_allowed": int(_num(max_delay_allowed, 1)),
        "delay_penalty": _num(delay_penalty),
    }
    desc = (f"Agent 插单模拟：{product_code} × {order['quantity']:g}，"
            f"交期第{order['due_period']}期，等级{order['priority_level']}，"
            f"允许延期{order['max_delay_allowed']}期，罚金{order['delay_penalty']:g}")
    created = await aps_client.aps_whatif_create(
        name=f"Agent插单模拟-{product_code}", orders=[order], description=desc)
    sid = created.get("id")
    if not sid:
        return {"summary": "场景创建成功但未返回 sid，无法继续模拟。", "error": True,
                "created": created}

    run = await aps_client.aps_whatif_run(sid)
    baseline_id, new_id = run.get("baseline_run_id"), run.get("run_id")
    if not new_id:
        return {"summary": f"场景 {sid} 求解未返回 run_id，无法对比。", "error": True,
                "sid": sid, "run": run}

    cmp = await aps_client.aps_whatif_compare(baseline_id, new_id)
    block = _kpi_block(cmp)
    summary_text = _kpi_summary_text(block, baseline_id, new_id)
    return {
        "summary": f"插单模拟完成（场景 {sid}，基线版本 #{baseline_id} → 沙盒版本 #{new_id}）。\n"
                   + summary_text,
        "sid": sid, "run_id": new_id, "baseline_run_id": baseline_id,
        "orders": [order], "kpi_diff": block, "summary_text": summary_text,
    }


# ---------------------------------------------------------------------------
# 工具注册 & 调度
#   - 每个工具有明确的 JSON Schema（OpenAI function calling 格式）
#   - execute_tool 记录日志：session_id / 工具名 / 参数 / 耗时 / 结果摘要
# ---------------------------------------------------------------------------
_STATUS_ENUM = ["all", "ontime", "delayed", "undelivered", "partial"]


def _s(name: str, description: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


# 工具元数据（供 /skills 与 LLM tools）
TOOL_META: dict[str, dict] = {
    "get_orders": {
        "description": (
            "查询需求订单列表，可按交付状态（ontime=按期/delayed=延期/undelivered=未交付/"
            "partial=部分) 与交期（第N期）、优先级过滤。"
        ),
        "parameters": {
            "status": {"type": "string", "enum": _STATUS_ENUM,
                       "description": "交付状态过滤，默认 all"},
            "due_before": {"type": "integer", "description": "仅返回交期 ≤ 该期的订单"},
            "priority": {"type": "integer", "description": "优先级等级过滤（1/2/3）"},
            "limit": {"type": "integer", "description": "返回数量上限，默认 30"},
        },
        "required": [],
        "readonly": True,
    },
    "get_schedule": {
        "description": (
            "查询单个订单的排产计划：交付点明细 + 各设备工序时间段，用于甘特图展示。"
        ),
        "parameters": {
            "order_id": {"type": "integer", "description": "订单 ID，例如 7"},
        },
        "required": ["order_id"],
        "readonly": True,
    },
    "get_machine_load": {
        "description": (
            "查询设备负荷（峰值/均值负荷率、产能、各周期负荷）。resource 支持设备名、"
            "类别前缀（涂装/装配/CNC）或末位序号；period 支持 '1-6'/'最近3期'/'今天' 等。"
        ),
        "parameters": {
            "resource": {"type": "string",
                         "description": "设备筛选，空=全部"},
            "period": {"type": "string",
                       "description": "周期区间，如 '1-12' / '最近3期' / '今天'"},
        },
        "required": [],
        "readonly": True,
    },
    "get_bottleneck": {
        "description": (
            "识别瓶颈设备（按峰值负荷率 + 影子价格排序），并给出负荷图。可指定周期区间或设备。"
        ),
        "parameters": {
            "period": {"type": "string", "description": "周期区间，默认全部"},
            "top_n": {"type": "integer", "description": "返回 Top N 瓶颈，默认 5"},
            "resource": {"type": "string", "description": "仅分析指定设备/类别"},
        },
        "required": [],
        "readonly": True,
    },
    "explain_delay": {
        "description": (
            "对单个订单的延期进行归因：交期 vs 实际、延期罚金、交期窗口设备负荷、"
            "同期更高优先级订单，同时输出延期对比甘特图。"
        ),
        "parameters": {
            "order_id": {"type": "integer", "description": "订单 ID"},
        },
        "required": ["order_id"],
        "readonly": True,
    },
    "get_kpi": {
        "description": "获取整体经营 KPI 卡片（收入/成本/利润/准交率等）与按优先级交付达成。",
        "parameters": {},
        "required": [],
        "readonly": True,
    },
    "get_audit_logs": {
        "description": "查询工具调用审计日志（最近优先，含角色/状态/缓存命中；仅 admin 角色可用）。",
        "parameters": {
            "session_id": {"type": "string", "description": "按会话 ID 过滤，空=全部"},
            "role": {"type": "string",
                     "description": "按发起角色过滤（planner/manager/...），空=全部"},
            "limit": {"type": "integer", "description": "返回条数上限，默认 20，最大 100"},
        },
        "required": [],
        "readonly": True,
    },
    "get_system_status": {
        "description": "系统运行状态巡检：LLM 配置（脱敏）/ APS 连通性 / 审计统计 / 缓存状态（仅 admin 角色可用）。",
        "parameters": {},
        "required": [],
        "readonly": True,
    },
    # ---- 主数据只读工具（供 masterdata 角色核对基础数据） ----
    "get_material_master": {
        "description": (
            "查询物料主数据台账（物料编码 / 名称 / 类别 / 单位 / 期初库存 / 库存上下限 / "
            "持有成本率），支持按编码精确、名称或编码模糊、类别过滤，用于主数据核对。"
        ),
        "parameters": {
            "code": {"type": "string", "description": "物料编码精确匹配，如 MN-TM3G2A4"},
            "search": {"type": "string", "description": "关键字模糊匹配物料编码或名称，如 驾驶室"},
            "category": {"type": "string",
                         "description": "物料类别：PRODUCT（整机）/ SEMI（半成品）/ RAW（原材料）"},
        },
        "required": [],
        "readonly": True,
    },
    "get_bom": {
        "description": (
            "展开指定物料的多级 BOM 结构（父件 → 逐层子件、用量、单位、层级），"
            "用于核对 BOM 完整性与层级；受 max_level 限制未展开完时结果中 truncated=true。"
        ),
        "parameters": {
            "parent_material_code": {"type": "string",
                                     "description": "BOM 展开起点的物料编码（必填），如 MN-TM3G2A4"},
            "max_level": {"type": "integer",
                          "description": "向下展开的最大层数，默认 5，上限 10"},
        },
        "required": ["parent_material_code"],
        "readonly": True,
    },
    "get_routing": {
        "description": (
            "查询指定物料的工艺路线：路线（routing_id / 是否默认 / 总提前期）与逐道工序"
            "（步序、工序名、设备、产线、工装、最大提前期），并标注未绑定设备或产线的待维护工序。"
        ),
        "parameters": {
            "material_code": {"type": "string", "description": "物料编码（必填），如 MN-TM3G2A4"},
            "routing_id": {"type": "integer",
                           "description": "仅查询指定路线 ID（同一物料有多条路线时使用），缺省返回全部路线"},
        },
        "required": ["material_code"],
        "readonly": True,
    },
    "get_resource_master": {
        "description": (
            "查询设备 / 工装台账（编码、名称、类型、所属产线、数量、单位成本、利用率、加班费率），"
            "可按编码与类型过滤，用于核对资源主数据与产线归属。"
        ),
        "parameters": {
            "code": {"type": "string", "description": "资源编码精确匹配，如 装配1"},
            "type": {"type": "string",
                     "description": "资源类型：EQUIPMENT（设备）/ FIXTURE（工装）/ LINE（产线），也可用中文 设备 / 工装"},
            "page": {"type": "integer", "description": "页码，默认 1"},
            "page_size": {"type": "integer", "description": "每页条数，默认 50，上限 500"},
        },
        "required": [],
        "readonly": True,
    },
    "plan_whatif": {
        "description": (
            "查询已有的 What-if 模拟场景（沙盒试算），返回每个场景的 ID、状态、"
            "插单内容、基线版本号与沙盒版本号。用于回答「之前模拟过什么」「有哪些插单方案」"
            "这类问题本身不发起新的求解。"
        ),
        "parameters": {
            "status": {"type": "string",
                       "description": "状态过滤：all（默认）/ draft / running / done / failed"},
            "limit": {"type": "integer", "description": "最多返回条数，默认 20，上限 100"},
        },
        "required": [],
        "readonly": True,
    },
    "simulate_insert_order": {
        "description": (
            "【写操作，会触发一次真实排产求解，通常耗时数秒到数十秒】"
            "插单模拟：假设在当前计划中紧急插入一张订单，重新求解后与基线版本做 13 项 KPI 对比"
            "（收入/利润/准交率/产能不足惩罚/延期罚金等），用于回答"
            "「如果插单 XX 产品 N 个会怎样」「插单对利润和准交率影响多大」。"
            "调用前必须先向用户确认插单假设（产品、数量、交期、优先级、允许延期、罚金）。"
            "【重要】当前系统不支持订单级插单明细（无法给出哪些具体订单受影响）："
            "1) 不要主动询问用户是否需要订单级明细；"
            "2) 若用户问「哪些订单受影响/哪些订单延期了/哪张订单被挤占」，"
            "必须明确告知：「当前版本的插单模拟只提供 KPI 汇总级影响"
            "（收入/利润/准交率/延期订单数等），不支持列出具体的受影响订单，"
            "订单级明细功能开发中。」；"
            "3) 严禁用 get_orders / explain_delay / get_schedule 等工具拼凑订单级插单影响分析——"
            "这些工具返回的是「当前排产结果」，不是「插单前后对比」；"
            "同样也不要建议或引导用户自行用这些工具查看、逐单归因，"
            "只说明「不支持订单级明细，功能开发中」即可，不要给出任何替代查询路径。"
        ),
        "parameters": {
            "product_code": {"type": "string",
                             "description": "产品编码（必填），必须是产品库中已维护的产品类物料"},
            "quantity": {"type": "number", "description": "订单数量（必填），须大于 0"},
            "due_period": {"type": "integer", "description": "交期期次（必填），取值 1~12"},
            "priority_level": {"type": "integer",
                               "description": "订单优先级：1（高）/ 2（中，默认）/ 3（低）"},
            "max_delay_allowed": {"type": "integer",
                                  "description": "允许延期期数：0~3，默认 1"},
            "delay_penalty": {"type": "number", "description": "延期罚金，默认 0"},
        },
        "required": ["product_code", "quantity", "due_period"],
        "readonly": False,
    },
}

# 函数实现映射
TOOL_FN: dict[str, Any] = {
    "get_orders": get_orders,
    "get_schedule": get_schedule,
    "get_machine_load": get_machine_load,
    "get_bottleneck": get_bottleneck,
    "explain_delay": explain_delay,
    "get_kpi": get_kpi,
    "get_audit_logs": get_audit_logs,
    "get_system_status": get_system_status,
    # 主数据只读工具（readonly=True）
    "get_material_master": get_material_master,
    "get_bom": get_bom,
    "get_routing": get_routing,
    "get_resource_master": get_resource_master,
    # What-if 沙盒工具
    "plan_whatif": plan_whatif,                    # 只读
    "simulate_insert_order": simulate_insert_order,  # 写（readonly=False）
}

# 可用工具名集合（供 routes.py /skills 校验用）
TOOLS: set[str] = set(TOOL_FN.keys())

# admin 专属工具（阶段一止血）：任何路径（LLM / 降级直查 / HTTP 直查）都要求 role=admin
ADMIN_ONLY_TOOLS: set[str] = {"get_audit_logs", "get_system_status"}

# OpenAI function calling 格式（LLM 直接消费）
def tool_schemas(allowed: list[str] | None = None) -> list[dict]:
    """allowed：启用的技能名列表；None = 全部可用，[] = 无可用（防空白名单泄露）"""
    pool = set(allowed) if allowed is not None else TOOLS
    return [_s(name, meta["description"], meta["parameters"], meta.get("required"))
            for name, meta in TOOL_META.items() if name in pool]

# /skills 接口消费（含参数 Schema 详情）
def tool_specs(allowed: list[str] | None = None) -> list[dict]:
    pool = set(allowed) if allowed is not None else TOOLS
    out: list[dict] = []
    for name, meta in TOOL_META.items():
        if name not in pool:
            continue
        out.append({
            "name": name,
            "description": meta["description"],
            "parameters": meta["parameters"],
            "readonly": meta.get("readonly", True),
        })
    return out


# 供 /skills 接口消费（routes.py 兼容别名）
def skills_payload(allowed: list[str] | None = None) -> list[dict]:
    return tool_specs(allowed=allowed)


async def _call_fn(name: str, fn: Any, args: dict) -> dict:
    try:
        result = await fn(**args)
    except APSApiError as e:
        return {"summary": f"APS API 错误（{e.status_code}）：{e.detail}",
                "error": True}
    except TypeError as e:
        return {"summary": f"参数错误：{e}", "error": True}
    if not isinstance(result, dict):
        result = {"summary": str(result)}
    if "summary" not in result:
        result["summary"] = f"{name} 已执行，详见 below。"
    # 兜底：确保 result 中的 chart 字段被序列化
    result.setdefault("name", name)
    # 默认分页上限 ≤500（APS API 约束）
    if "page_size" in result and result["page_size"] > 500:
        result["page_size"] = 500
    return result


async def execute_tool(name: str, args: dict | None = None,
                       session_id: str = "local",
                       role: str | None = None,
                       confirmed: bool = False) -> dict:
    """执行单个工具：权限校验 → 调用 → 审计（SQLite + JSONL）→ 返回结果。

    约定：
    - 入参仅做最小类型校验（LLM 可能传字符串数字）
    - 结果总是包含 `summary`（供 LLM 消费）与可选 `chart`（供前端渲染）
    - role/confirmed/cache_hit 透传给审计日志
    - role 非空时强制执行角色-工具白名单（role_config.filter_tools）
    - ADMIN_ONLY_TOOLS 恒要求 role == "admin"（绕过 LLM schema 的直查也会被拒绝）
    - role=None 表示免白名单的调试直查（admin 专属工具仍需显式 role="admin"）
    """
    args = args or {}
    eff_role = role_config.extract_role(role) if role is not None else None

    # ① admin 专属工具（get_audit_logs / get_system_status）
    if name in ADMIN_ONLY_TOOLS and eff_role != "admin":
        res = {"summary": f"权限拒绝：{name} 仅 admin 角色可用"
                          + (f"（当前角色：{eff_role}）" if eff_role else "（需显式传 role=admin）"),
               "error": True,
               "as_text": f"权限拒绝：{name} 仅 admin 角色可用。"}
        log_tool_call(session_id, name, args, 0.0, res["summary"],
                      role=eff_role or "default", status="failed",
                      confirmed=confirmed)
        return res

    # ② 角色-工具白名单（role 非空时强制；阶段一止血执行层兜底）
    if eff_role is not None and name not in role_config.filter_tools(eff_role, TOOLS):
        avail = "、".join(role_config.filter_tools(eff_role, TOOLS)) or "（无）"
        res = {"summary": f"权限拒绝：角色 {eff_role} 不允许调用工具 {name}",
               "error": True,
               "as_text": f"权限拒绝：角色 {eff_role} 不允许调用工具 {name}。"
                          f"当前角色可用工具：{avail}。"}
        log_tool_call(session_id, name, args, 0.0, res["summary"],
                      role=eff_role, status="failed", confirmed=confirmed)
        return res

    fn = TOOL_FN.get(name)
    if not fn:
        res = {"summary": f"未知工具：{name}", "error": True,
               "as_text": f"未知工具：{name}"}
        log_tool_call(session_id, name, args, 0.0, res["summary"],
                      role=eff_role or "default", status="failed",
                      confirmed=confirmed)
        return res

    # 参数名容错 + 类型强转
    _PARAMS_ALIAS = {
        "order": "order_id", "id": "order_id", "oid": "order_id",
        "device": "resource", "machine": "resource", "equip": "resource",
        "eqp": "resource", "resource_code": "resource", "date_range": "period",
        "range": "period", "dates": "period", "n": "top_n", "num": "top_n",
        # 主数据工具：LLM 常按 aps 接口参数名传参，这里统一收敛到工具签名
        "resource_type": "type", "parent_code": "parent_material_code",
        "mat_code": "material_code",
    }
    _INT_PARAMS = {"order_id", "top_n", "due_before", "priority", "limit",
                   "page", "page_size", "max_level", "routing_id"}
    params: dict = {}
    for k, v in args.items():
        key = _PARAMS_ALIAS.get(k, k)
        if key in _INT_PARAMS and v not in (None, ""):
            try:
                v = int(float(v))
            except (TypeError, ValueError):
                v = int(v) if v else v
        params[key] = v

    _CACHE_HIT.set(False)  # 重置缓存命中标记（本次调用内任一数据源命中则置回 True）
    t0 = time.perf_counter()
    result = await _call_fn(name, fn, params)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if "summary" not in result:
        result["summary"] = f"{name} 已执行，详见下文。"
    result.setdefault("name", name)
    result["duration_ms"] = round(elapsed_ms, 1)
    result["as_text"] = _to_as_text(name, result)
    log_tool_call(session_id, name, params, elapsed_ms, result.get("summary", ""),
                  role=eff_role or "default",
                  status="failed" if result.get("error") else "success",
                  confirmed=confirmed,
                  cache_hit=bool(_CACHE_HIT.get()))
    return result


def _to_as_text(name: str, result: dict) -> str:
    """把工具结果浓缩为 LLM tool message 的可读文本。"""
    summary = result.get("summary", "")
    if name == "get_orders":
        orders = result.get("orders", [])
        rows = "\n".join(
            f"订单 {o.get('order_id')} | {o.get('material_code')} | "
            f"交期第{o.get('due_period')}期 | 状态{o.get('delivery_status')} | "
            f"达成{o.get('satisfied_ratio')}%"
            for o in orders[:15]
        )
        return summary + ("\n" + rows if rows else "")
    if name == "get_schedule":
        order = result.get("order", {})
        dels = result.get("deliveries", [])
        ds = " | ".join(f"第{d.get('period')}期 {d.get('quantity')}件({d.get('status')})"
                        for d in dels) or "无交付明细"
        return summary + f"\n订单: {order}\n交付: {ds}"
    if name == "get_machine_load":
        res = result.get("resources", [])
        rs = "\n".join(
            f"{r.get('resource_code')} 峰值{r.get('peak_rate')}% "
            f"均值{r.get('avg_rate')}% 产能{r.get('capacity')}"
            for r in res[:15]
        )
        return summary + ("\n" + rs if rs else "")
    if name == "get_bottleneck":
        bn = result.get("bottlenecks", [])
        rs = "\n".join(
            f"{b.get('resource_code')} 峰值{b.get('peak_rate')}% 影价{b.get('shadow_price')}"
            for b in bn[:10]
        )
        return summary + ("\n" + rs if rs else "")
    if name == "explain_delay":
        ev = result.get("evidences", [])
        return summary + ("\n证据：\n" + "\n".join(f"- {e}" for e in ev) if ev else "")
    if name == "get_kpi":
        return summary + "\n指标: " + json.dumps(result.get("kpi", {}), ensure_ascii=False)
    if name == "get_material_master":
        items = result.get("items") or []
        rows = "\n".join(
            f"{it.get('material_code')} | {it.get('material_name')} | "
            f"类别{it.get('category') or '-'} | 单位{it.get('unit') or '-'} | "
            f"期初{_num(it.get('initial_inventory')):g} | "
            f"库存上下限{_num(it.get('min_inventory')):g}/{_num(it.get('max_inventory')):g} | "
            f"持有成本率{_num(it.get('holding_cost_rate')):g}"
            for it in items[:40]
        )
        tail = f"\n（仅展示前 40 条，共 {len(items)} 条）" if len(items) > 40 else ""
        return summary + ("\n" + rows if rows else "") + tail
    if name == "get_bom":
        items = result.get("items") or []
        rows = "\n".join(
            f"{'  ' * max(0, int(_num(it.get('level'), 1)) - 1)}"
            f"L{it.get('level')} {it.get('parent_code')} → {it.get('child_code')}"
            f" {it.get('child_name') or ''} 用量 {_num(it.get('quantity')):g}{it.get('unit') or ''}"
            for it in items[:80]
        )
        if result.get("truncated"):
            tail = (f"\n（因 max_level={result.get('max_level')} 截断，更深层级未展开；"
                    f"如需完整结构可提高 max_level 重新查询）")
        elif len(items) > 80:
            tail = f"\n（仅展示前 80 条，共 {len(items)} 条）"
        else:
            tail = ""
        return summary + ("\n" + rows if rows else "") + tail
    if name == "get_routing":
        steps = result.get("steps") or []
        grouped: dict = {}
        for s in steps:
            grouped.setdefault(s.get("routing_id"), []).append(s)
        lines: list[str] = []
        for r in result.get("routes") or []:
            rid = r.get("routing_id")
            lines.append(
                f"路线 {rid}（默认={'是' if r.get('is_default') else '否'}，"
                f"总提前期 {r.get('total_lead_time')}，{r.get('step_count')} 道工序）:")
            for s in grouped.get(rid, []):
                lines.append(
                    f"  步序{s.get('step_order')} {s.get('operation_code')}"
                    f" {s.get('operation_name') or ''}"
                    f" | 设备 {s.get('equipment_name') or s.get('equipment_code') or '未绑定'}"
                    f" | 产线 {s.get('production_line_code') or '未指定'}"
                    f" | 工装 {s.get('fixture_code') or '无'}"
                    f" | 最大提前期 {s.get('max_lead_time')}")
        return summary + ("\n" + "\n".join(lines) if lines else "")
    if name == "get_resource_master":
        items = result.get("items") or []
        rows = "\n".join(
            f"{it.get('resource_code')} | {it.get('resource_name')} | "
            f"类型{it.get('resource_type') or '-'} | "
            f"产线{it.get('line_code') or '未绑定'} | 数量{_num(it.get('quantity')):g} | "
            f"单位成本{_num(it.get('unit_cost')):g} | "
            f"利用率{_num(it.get('utilization_rate')):g} | "
            f"加班费率{_num(it.get('overtime_rate')):g}"
            for it in items[:40]
        )
        tail = f"\n（仅展示前 40 条，共 {len(items)} 条）" if len(items) > 40 else ""
        return summary + ("\n" + rows if rows else "") + tail
    return summary

