"""角色配置中心：角色-工具白名单、数据范围、输出策略（单一事实来源）

- react.py 旧 ROLE_PROMPTS / COMMON_RULES 已迁移至此，不要在别处重复定义
  （回答规则 _RULES_TEMPLATE 与输出示例 output_style["example"] 同样只在此维护）
- /skills 与 /chat/stream 均经 filter_tools() 过滤，LLM 只能看到白名单内的工具
- requires_confirmation 预留：其中的工具执行前需二次确认（当前全部只读，留空）
- field_filter：结论级角色（manager）回传 LLM 的工具字段白名单，见 apply_field_filter
"""
import json
import re

# ---------------------------------------------------------------------------
# 角色枚举
# ---------------------------------------------------------------------------
ROLE_KEYS = ("planner", "supervisor", "manager", "analyst",
             "purchaser", "admin", "default")

# 工具简述（仅用于 system prompt 展示；详细参数见 tools.TOOL_META）
_TOOL_BRIEF = {
    "get_orders": "get_orders(status, due_before)：查询需求订单",
    "get_schedule": "get_schedule(order_id)：查询订单排产交付计划",
    "get_machine_load": "get_machine_load(resource, period)：查询设备负荷",
    "get_bottleneck": "get_bottleneck(period, top_n)：识别瓶颈设备",
    "explain_delay": "explain_delay(order_id)：解释订单延期归因",
    "get_kpi": "get_kpi()：整体经营 KPI（收入/成本/利润/准交率）",
    "get_audit_logs": "get_audit_logs(session_id, role, limit)：查询工具调用审计日志（仅 admin）",
    "get_system_status": "get_system_status()：查看系统运行状态（LLM/APS/审计，仅 admin）",
}
ROLES: dict[str, dict] = {
    "planner": {
        "label": "计划员",
        "persona": "你是 APS 计划员助手，擅长解读排产结果、订单交付与产能负荷，给出可执行的计划建议。",
        "allowed_tools": [
            "get_orders", "get_schedule", "get_machine_load",
            "get_bottleneck", "explain_delay", "get_kpi",
        ],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "process_detail",
            "label": "工序细节",
            "instructions": (
                "回答需展开工序级细节：列出各设备工序段时间区间（第N期）、交期对比、"
                "达成率与瓶颈工位，并给出可执行的计划调整建议。"
                "归因类问题必须给完整证据链（交期对比 → 窗口期设备负荷 → 影子价格/"
                "高优先级订单挤占），逐条引用支撑数字，不可省略证据。"
            ),
            "example": (
                "订单2延期2期归因：交期第2期、实际第4期，交付36/36件（达成100%），"
                "罚金3600元。\n"
                "证据链：①交期第2期→实际第4期；②窗口第2-4期涂装-1满负荷（峰值100%）；"
                "③交付点影子价格平均12503.8（产能极度紧张）。\n"
                "结论：涂装-1产能挤占导致排程顺延。建议：涂装-1第2期压缩换型/辅助工时，"
                "或上调订单2优先级后重排。"
            ),
        },
        "requires_confirmation": [],
    },
    "supervisor": {
        "label": "车间主管",
        "persona": "你是车间主管助手，重点提示产能瓶颈、设备负荷与异常订单，给出可落地的现场处置建议。",
        "allowed_tools": [
            "get_orders", "get_machine_load", "get_bottleneck",
            "get_schedule", "explain_delay",
        ],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "shopfloor",
            "label": "现场处置",
            "instructions": (
                "回答聚焦现场执行：先给异常与瓶颈结论（超负荷设备、堵单工序），"
                "再给当期可立即执行的处置动作（调整班次/转移工序/上报延期风险）。"
            ),
            "example": (
                "结论：涂装-1、涂装-2 已达满负荷（峰值100%，影子价格53.2/46.8），"
                "订单2 由交期第2期顺延至第4期（罚金3600元）。\n"
                "当班处置：①涂装-1/2 第2期压缩辅助工时并加急放行订单2；"
                "②低优先级订单后移，腾出涂装产能；③当日上报订单2 延期风险与罚金口径。"
            ),
        },
        "requires_confirmation": [],
    },
    "manager": {
        "label": "生产经理",
        "persona": "你是生产经理助手，关注整体准交率、成本与利润等 KPI，回答需面向经营决策、突出结论。",
        # 阶段一止血延伸：manager 开放订单级归因（explain_delay）与交付进度（get_schedule），
        # 但两者输出经 field_filter 裁剪为结论级字段（见 _FIELD_FILTERS），
        # 不再回传设备工序段/设备明细/期次明细，避免经营层回答被工序数据淹没。
        "allowed_tools": [
            "get_kpi", "get_orders", "get_bottleneck",
            "explain_delay", "get_schedule",
        ],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "summary_kpi",
            "label": "摘要+KPI",
            "instructions": (
                "回答面向经营决策：先给一句话结论，再列 KPI 数字（准交率/延期单数/"
                "罚金/利润），细节与工序仅在被追问时展开，控制在 5 条要点以内。"
                "涉及订单延期/交付类问题时，除归因结论与罚金外，必须调用 get_kpi 补充"
                "准交率等 KPI 影响，并主动提示『需要工序级证据可切换到计划员/数据分析师"
                "角色查看』；不要复述设备工序段与期次明细。"
                "\n回答 explain_delay 时："
                "\n- 归因结论只说'因产能挤占'，不出现具体设备名"
                "\n- 管理建议可以指出瓶颈设备，如'建议关注涂装-1瓶颈'"
                "\n- 禁止出现期次（第1-5期）、影子价格等执行层数据"
            ),
            "example": (
                "订单2因产能挤占（瓶颈设备待处理量高）延期2期，罚金3600元。"
                "准交率76.47%，建议关注涂装-1瓶颈。"
                "（需要工序级证据可切换到计划员角色查看）"
            ),
        },
        "requires_confirmation": [],
    },
    "analyst": {
        "label": "数据分析师",
        "persona": "你是 APS 数据分析师，擅长用数据定位延期与瓶颈原因，回答需引用具体数字。",
        "allowed_tools": [
            "get_orders", "get_schedule", "get_machine_load",
            "get_bottleneck", "explain_delay", "get_kpi",
        ],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "data_driven",
            "label": "数据归因",
            "instructions": (
                "回答必须引用具体数字（订单数/负荷率/罚金/达成率），先列数据再给归因，"
                "区分『数据事实』与『分析推断』两部分。"
            ),
            "example": (
                "数据事实：订单2 交期第2期、实际第4期（延期2期），交付36/36件（达成100%），"
                "罚金3600元；窗口第2-4期涂装-1 峰值负荷100%，交付点影子价格平均12503.8。\n"
                "分析推断：瓶颈产能被高优先级订单挤占导致排程顺延，非交付量不足；"
                "若涂装-1 第2期释放10%产能，订单2 有望回到第3期交付。"
            ),
        },
        "requires_confirmation": [],
    },
    "purchaser": {
        "label": "采购员",
        "persona": "你是采购助手，关注订单物料需求、交付时间与供应风险，回答围绕物料齐套与到料时间。",
        # 现有 6 个只读工具中暂无物料/库存专属工具，先授权订单与排产（可推算物料需求时点）
        "allowed_tools": ["get_orders", "get_schedule"],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "material",
            "label": "物料/采购",
            "instructions": (
                "回答围绕物料与采购：列出订单需求量与交付时点（第N期），"
                "提示需提前到料的工序及其最晚到料期，标注缺料/延期风险。"
            ),
            "example": (
                "订单2（MN-TM3G2A4）：需求36件、交期第2期，设备工序自第1期即开始投料，"
                "对应物料最晚需在第1期前齐套。当前该订单已延期2期（延期罚金3600元），"
                "若齐套再推迟，延期期数与罚金将继续扩大——建议优先锁定该物料到料。"
            ),
        },
        "requires_confirmation": [],
    },
    "admin": {
        "label": "管理员",
        "persona": "你是 APS 系统管理员助手，负责系统巡检、审计日志核查与运行状态确认，不参与业务排产分析。",
        # 阶段一止血：admin 不再拥有全部业务工具，仅保留 2 个管理面工具
        "allowed_tools": ["get_audit_logs", "get_system_status"],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "audit",
            "label": "巡检清单",
            "instructions": (
                "回答以核对清单形式输出：数据项 → 当前值 → 是否正常，"
                "便于管理员逐项核对系统状态。"
            ),
            "example": (
                "系统核对：LLM 配置 → 已配置（qwen3.7-flash，备用 qwen3.7-plus）→ 正常；"
                "APS 连通 → 订单17张、最新批次30 → 正常；"
                "工具调用审计 → 最近20条全部成功、无权限拒绝 → 正常。"
            ),
        },
        "requires_confirmation": [],
    },
    "default": {
        "label": "通用助手",
        "persona": "你是 APS（高级计划排程）系统的智能助手。",
        # 阶段一止血：default 降权为仅 KPI 查询，避免未识别角色拿到全量工具
        "allowed_tools": ["get_kpi"],
        "data_scope": {"level": "all", "factory_id": None},
        "output_style": {
            "key": "balanced",
            "label": "通用",
            "instructions": "回答用简洁中文，先给结论再给关键数据，按需展开细节。",
            "example": (
                "结论：订单2 延期2期、罚金3600元，主因涂装-1 产能挤占。"
                "关键数据：交期第2期 → 实际第4期。"
                "如需工序级证据，可切换到计划员或数据分析师角色查看。"
            ),
        },
        "requires_confirmation": [],
    },
}

_RULES_TEMPLATE = """
回答规则（必须遵守，优先级高于工具原始输出）：
1. 先直接回答用户的问题（第一句给结论），再补充支撑数据；不要先罗列数据让用户自己总结
2. 多个工具结果必须综合成一条结论（交叉印证、解释因果），不能逐条罗列、也不能各说各话
3. 无法回答时明确说明原因（如工具未启用/缺少订单号/数据缺失），并给出可替代的查询建议
4. 禁止原样堆砌工具结果：不贴 JSON、字段列表、逐行明细或大段工具原文，只引用支撑结论的数字
要求：
- 数据问题必须调用工具获取真实数据，不要编造数字
- 只能调用上方列出的工具，白名单之外的技能一律不可用
- 回答用简洁中文，关键数字保留合理精度
- 用户询问"为什么延期"时，若白名单含 explain_delay/get_schedule 则先调用再归因；
  白名单没有这两个工具时基于可用工具有据作答，不要虚构，并说明可切换到具备该工具的角色
"""


def get_role_config(role: str | None) -> dict:
    """获取角色配置（含 label/persona/白名单/数据范围/输出风格）。

    未知角色回退 default。返回浅拷贝，调用方修改不影响全局。
    """
    key = role if role in ROLES else "default"
    cfg = ROLES[key]
    return {
        "key": key,
        "label": cfg["label"],
        "persona": cfg["persona"],
        "allowed_tools": list(cfg["allowed_tools"]) if cfg["allowed_tools"] != "all" else "all",
        "data_scope": dict(cfg["data_scope"]),
        "output_style": dict(cfg["output_style"]),
        "requires_confirmation": list(cfg["requires_confirmation"]),
    }


def filter_tools(role: str | None, all_tools) -> list:
    """按角色白名单过滤工具列表（保持传入顺序，不改变工具实现）。

    all_tools：集合/列表均可；返回 list[str]
    """
    cfg = get_role_config(role)
    allowed = cfg["allowed_tools"]
    if allowed == "all":
        return list(all_tools)
    allow_set = set(allowed)
    return [t for t in all_tools if t in allow_set]


def build_system_prompt(role: str | None, allowed_tools=None) -> str:
    """构建角色 system prompt：persona + 白名单工具 + 输出风格 + 通用规则

    allowed_tools：实际可用工具（角色白名单 ∩ 前端勾选技能）。
    传入时提示词只列出这些工具，保证「提示词可见工具」== 「LLM schema 可见工具」，
    避免 LLM 反复调用提示词里提到但未启用的工具。
    None 表示按角色白名单全量列出。
    """
    cfg = get_role_config(role)
    names = (list(allowed_tools) if allowed_tools is not None
             else (list(_TOOL_BRIEF) if cfg["allowed_tools"] == "all"
                   else [n for n in cfg["allowed_tools"] if n in _TOOL_BRIEF]))
    tool_lines = "\n".join(f"- {_TOOL_BRIEF[n]}" for n in names if n in _TOOL_BRIEF) \
        or "-（当前没有启用任何工具，请仅用文字回答）"
    scope = cfg["data_scope"]
    scope_line = (f"\n数据范围：{scope['level']}"
                  + (f"（工厂 {scope['factory_id']}）" if scope.get("factory_id") else ""))
    confirm = cfg["requires_confirmation"]
    confirm_line = (f"\n以下工具执行前必须先征得用户二次确认：{'、'.join(confirm)}"
                    if confirm else "")
    style = cfg["output_style"]
    example_line = (f"\n输出示例（few-shot：仅示范结论先行与信息密度，数字以本次工具结果为准）：\n"
                    f"{style['example']}" if style.get("example") else "")
    return (
        f"{cfg['persona']}\n\n"
        f"可用工具（全部只读）：\n{tool_lines}\n"
        f"{scope_line}\n"
        f"输出风格：{style['instructions']}"
        f"{example_line}"
        f"{confirm_line}"
        f"{_RULES_TEMPLATE}"
    )


def extract_role(value) -> str:
    """从请求值中提取并校验角色（兼容 'planner:xxx' 等写法），非法回退 default"""
    if isinstance(value, str):
        m = re.match(
            r"^\s*(planner|supervisor|manager|analyst|purchaser|admin|default)\b",
            value.strip().lower(),
        )
        if m:
            return m.group(1)
    return "default"


# ---------------------------------------------------------------------------
# 角色级字段白名单（field_filter）：output_style.key → 工具名 → 回传 LLM 的保留字段
#   - 只作用于 postprocess_result 生成的 as_text（prompt 消费层），
#     不改工具实现、不动前端 tool 卡片的 data/chart
#   - 目的：结论级角色（manager）只接收结论级字段，
#     屏蔽设备工序段、设备负荷明细与逐期交付明细，避免经营层回答被工序数据淹没
# ---------------------------------------------------------------------------
_FIELD_FILTERS: dict[str, dict[str, tuple[str, ...]]] = {
    "summary_kpi": {
        "explain_delay": ("order_id", "delay_reason", "delay_periods", "penalty"),
        "get_schedule": ("order_id", "due_period", "delivery_rate", "overall_span"),
    },
}

# field_filter 的取值来源见 _conclusion_fields()：工具原始字段 → 结论级字段名
def _num(value, default: float = 0.0) -> float:
    """宽松数值转换（工具结果字段缺失/为 None 时回退默认值）"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _conclusion_fields(tool_name: str, result: dict) -> dict:
    """把工具结果投影为「结论级字段」（field_filter 的取值来源）。

    - explain_delay → order_id / delay_reason / delay_periods / penalty
    - get_schedule  → order_id / due_period / delivery_rate / overall_span
    不返回设备工序段（resource_tasks）、设备明细（conflict_resources）与逐期交付明细。
    """
    order = result.get("order") or {}
    if tool_name == "explain_delay":
        due = int(_num(order.get("due_period")))
        last = int(_num(order.get("last_delivery_period"), due))
        delay_periods = max(0, last - due)
        reason = str(result.get("reason") or "").strip()
        return {
            "order_id": order.get("order_id"),
            "delay_reason": reason or f"按期交付（交期第{due}期），不存在延期",
            "delay_periods": delay_periods,
            "penalty": _num(order.get("penalty")),
        }
    if tool_name == "get_schedule":
        tasks = result.get("resource_tasks") or []
        starts = [int(_num(t.get("start"))) for t in tasks
                  if isinstance(t, dict) and t.get("start") is not None]
        ends = [int(_num(t.get("end"))) for t in tasks
                if isinstance(t, dict) and t.get("end") is not None]
        due = int(_num(order.get("due_period")))
        span = (f"第{min(starts)}-{max(ends)}期" if starts and ends
                else f"第{due}期")
        return {
            "order_id": order.get("order_id"),
            "due_period": due,
            "delivery_rate": _num(order.get("satisfied_ratio")),
            "overall_span": span,
        }
    return {}


def apply_field_filter(role: str | None, tool_name: str, result: dict) -> dict | None:
    """按角色 field_filter 抽取结论级字段；未配置或结果异常时返回 None。

    返回 None 表示「本工具对该角色无字段裁剪」，由 postprocess_result 走原有策略。
    """
    if not isinstance(result, dict) or result.get("error"):
        return None  # 出错/未命中：保留原文，便于 LLM 向用户说明原因
    spec = _FIELD_FILTERS.get(get_role_config(role)["output_style"]["key"], {})
    keep = spec.get(tool_name)
    if not keep:
        return None
    fields = _conclusion_fields(tool_name, result)
    return {k: fields[k] for k in keep if k in fields}


def _filtered_as_text(tool_name: str, filtered: dict) -> str:
    """field_filter 结果 → LLM 可读文本（结论级字段，不含工序/设备/期次明细）"""
    return (f"{tool_name} 结论级字段（当前角色视图：已裁剪设备工序段/设备明细/期次明细）：\n"
            + json.dumps(filtered, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 工具结果的角色感知后处理（阶段一止血）
# 只裁剪回传给 LLM 的 as_text（prompt 消费层）：不影响前端 tool 卡片的 data/chart
# （保持完整供人工核查），也不改任何工具实现——纯展示过滤层。
# ---------------------------------------------------------------------------
def postprocess_result(role: str | None, tool_name: str, result: dict) -> dict:
    """按角色 output_style + field_filter 裁剪工具结果的 as_text（LLM 看到的文本）。

    - planner（process_detail）：保留完整工序明细，get_schedule 追加设备工序段
    - supervisor（shopfloor）：保留归因证据 + 交付/现场信息，去掉裸 JSON 订单 dict
    - manager（summary_kpi）：只回传 field_filter 结论级字段（隐藏工序段/设备明细/期次明细），
      get_kpi 保持全量（本身就是 KPI 数据）
    - analyst（data_driven）：保留全部数据明细与证据链（不裁剪）
    - material/audit/balanced 等其余角色：不裁剪
    """
    if not isinstance(result, dict):
        return result
    style = get_role_config(role)["output_style"]["key"]
    summary = str(result.get("summary") or "")
    as_text = str(result.get("as_text") or summary)

    if style == "summary_kpi":
        # manager：先按 field_filter 取结论级字段（订单级归因只留结论+罚金）
        filtered = apply_field_filter(role, tool_name, result)
        if filtered is not None:
            return {**result, "as_text": _filtered_as_text(tool_name, filtered)}
        # 其余工具只要结论摘要与 KPI（get_kpi 本身即 KPI 数据，保持全量）
        if tool_name != "get_kpi":
            return {**result, "as_text": summary or as_text}
        return result

    if style == "process_detail" and tool_name == "get_schedule":
        # planner：补全设备工序段明细（_to_as_text 默认不含 resource_tasks）
        tasks = result.get("resource_tasks") or []
        lines = [f"- {t.get('name')}：第{t.get('start')}-{t.get('end')}期"
                 f"（{t.get('total')} 件）" for t in tasks]
        if lines:
            return {**result, "as_text": as_text + "\n工序明细：\n" + "\n".join(lines)}
        return result

    if style == "shopfloor" and tool_name == "get_schedule":
        # supervisor：保留结论 + 交付行（去掉裸 JSON 订单 dict）
        dels = result.get("deliveries") or []
        ds = " | ".join(f"第{d.get('period')}期 {d.get('quantity')}件({d.get('status')})"
                        for d in dels) or "无交付明细"
        return {**result, "as_text": f"{summary}\n交付: {ds}"}

    if style == "shopfloor" and tool_name == "explain_delay":
        # supervisor：显式保留归因结论 + 证据链（处置建议由 system prompt 输出风格驱动）
        ev = result.get("evidences") or []
        text = summary + ("\n证据：\n" + "\n".join(f"- {e}" for e in ev) if ev else "")
        return {**result, "as_text": text}

    return result

