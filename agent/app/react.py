"""轻量 ReAct 循环：LLM（OpenAI 兼容 function calling）+ APS 只读工具

选择轻量自研 ReAct 而非 LangGraph：
- 工具仅 4 个只读查询，单层循环足够，无需图状态机
- 少一个重依赖，SSE 事件流更可控（token/tool_call/tool_result/chart/done）

流程：
  1. 未配置 LLM → 降级：按关键词直查工具，同样推送 tool_call/tool_result/chart 事件
  2. 配置了 LLM → 流式对话；LLM 发起 tool_call 时执行工具
     （工具内部通过 HTTP 访问 aps /open/*，并记录调用日志）
  3. 工具结果含 chart 数据时额外推送 chart 事件（前端渲染图表）
  4. 结果回填消息继续下一轮，直到 LLM 输出纯文本或达到最大轮数
5. allowed_skills：前端勾选启用的技能，未被勾选的工具既不提供给 LLM 也不允许直查
"""
import json
import re
import time
import uuid
from typing import AsyncGenerator

from . import tools
from .config import MAX_TOOL_ROUNDS, SESSION_HISTORY_LIMIT
from .llm_client import chat_stream, is_configured
from . import role_config

# 角色提示词/白名单/输出策略已迁移至 role_config.py（build_system_prompt）：
#   - 角色 persona / 可用工具 / 数据范围 / 输出风格 + few-shot 输出示例
#   - 全局回答规则（先直接回答再补数据 / 多工具结果综合成结论 / 无法回答说明原因与替代建议 /
#     禁止原样堆砌工具结果）→ role_config._RULES_TEMPLATE
# 唯一在构建 system prompt 时注入，任何角色差异都在此收敛，勿在本文件重复定义。
# 内存会话历史：session_id → [{role, content}]
_SESSIONS: dict[str, list[dict]] = {}


def _history(session_id: str) -> list[dict]:
    return _SESSIONS.setdefault(session_id, [])[-SESSION_HISTORY_LIMIT:]


def _append_history(session_id: str, role: str, content: str) -> None:
    if content:
        _SESSIONS.setdefault(session_id, []).append({"role": role, "content": content})
        _SESSIONS[session_id] = _SESSIONS[session_id][-SESSION_HISTORY_LIMIT:]


# 会话 ID 统一为 UUID v4 格式：缺失或非 v4 格式一律重新生成
_UUID4_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def _norm_session(value: str | None) -> str:
    if value and _UUID4_RE.match(str(value)):
        return str(value)
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 降级模式（未配置 LLM）：同样按 token / tool_call / tool_result / chart 事件流输出，
# 保证前端「提问 → 回复 → 工具卡片 → 图表更新」闭环在无 API Key 时也能跑通
# ---------------------------------------------------------------------------
def _order_id_from(message: str) -> int | None:
    if not re.search(r"订单|order", message, re.I):
        return None
    m = re.search(r"(?:订单|order)\s*(?:号|编号|id)?\s*[:：#]?\s*(\d+)", message, re.I)
    if not m:
        m = re.search(r"(\d+)", message)
    return int(m.group(1)) if m else None


def _period_range_from(message: str) -> str:
    m = re.search(r"(\d+)\s*(?:-|~|到|至)\s*(\d+)", message)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"第?\s*(\d+)\s*(?:期|周期)", message)
    return m.group(1) if m else ""


def _degraded_plan(message: str, allowed: list[str] | None) -> list[tuple[str, dict]]:
    """关键词 → 工具调用计划（降级模式的简易意图识别）"""
    oid = _order_id_from(message)
    want_reason = any(k in message for k in ("为什么", "为何", "原因", "归因"))
    steps: list[tuple[str, dict]] = []

    if any(k in message for k in ("负荷", "产能", "瓶颈", "load")):
        steps = [("get_machine_load", {"date_range": _period_range_from(message)})]
    elif any(k in message for k in ("延期", "延迟", "delay", "罚金")):
        if oid and want_reason:
            steps = [("explain_delay", {"order_id": oid}),
                     ("get_schedule", {"order_id": oid})]
        else:
            steps = [("get_orders", {"status": "delayed"})]
    elif any(k in message for k in ("排产", "计划", "交付", "甘特", "schedule", "gantt")) and oid:
        steps = [("get_schedule", {"order_id": oid})]
    elif any(k in message for k in ("订单", "order")):
        status = "all"
        if "未交付" in message or "未交" in message:
            status = "undelivered"
        elif "按期" in message or "准时" in message:
            status = "ontime"
        steps = [("get_orders", {"status": status})]
    elif oid:
        steps = [("get_schedule", {"order_id": oid})]

    pool = set(allowed) if allowed is not None else set(tools.TOOLS)
    return [(name, args) for name, args in steps if name in pool]


def _guide_text(allowed: list[str] | None) -> str:
    pool = [n for n in tools.TOOLS if allowed is None or n in allowed]
    guide = "\n".join(f"- `POST /tools/{n}`" for n in pool)
    return (f"**[降级模式]** 未配置 LLM（`LLM_API_KEY` / `LLM_BASE_URL`），"
            f"无法进行自然语言对话。\n\n当前已启用技能可直接调用：\n{guide}\n\n"
            f"也可直接问关键词类问题，例如「查看设备负荷」「订单7的排产计划」"
            f"「哪些订单延期了」「订单2为什么延期」。")


async def _degraded_stream(message: str, session_id: str,
                           allowed: list[str] | None,
                           role: str = "default") -> AsyncGenerator[dict, None]:
    """降级模式的完整事件流（含工具卡片与图表事件）"""
    plan = _degraded_plan(message, allowed)
    if not plan:
        yield {"type": "token", "content": _guide_text(allowed)}
        return

    for name, args in plan:
        yield {"type": "tool_call", "session_id": session_id,
               "name": name, "arguments": args}
        try:
            result = await tools.execute_tool(name, args, session_id=session_id,
                                              role=role)
        except Exception as e:  # noqa: BLE001
            yield {"type": "tool_result", "session_id": session_id, "name": name,
                   "summary": f"工具执行失败: {e}"}
            yield {"type": "token", "content": f"调用 `{name}` 失败：{e}"}
            continue

        yield {"type": "tool_result", "session_id": session_id, "name": name,
               "summary": result.get("summary", ""),
               "data": {k: v for k, v in result.items()
                        if k not in ("as_text", "chart")}}
        if result.get("chart"):
            yield {"type": "chart", "session_id": session_id,
                   "name": name, "chart": result["chart"]}
        yield {"type": "token",
               "content": f"[降级模式] 已调用 `{name}`：{result.get('summary', '')}"
                          f"（未配置 LLM，仅做工具直查，明细见上方工具卡片）"}


async def run_react(
    message: str,
    role: str = "planner",
    session_id: str | None = None,
    allowed_skills: list[str] | None = None,
) -> AsyncGenerator[dict, None]:
    """运行一轮 ReAct 对话，yield 事件 dict（路由层序列化为 SSE）

    allowed_skills：前端勾选启用的技能名（None/空 = 全部可用）
    """
    session_id = _norm_session(session_id)
    role = role_config.extract_role(role)
    # 角色-工具白名单 ∩ 前端勾选启用的技能：一次计算，降级直查与 LLM schema 双路径共用
    role_tools = role_config.filter_tools(role, tools.TOOLS)
    if allowed_skills:
        allow_set = set(allowed_skills)
        role_tools = [t for t in role_tools if t in allow_set]
    yield {"type": "start", "session_id": session_id,
           "llm_configured": is_configured(), "role": role}

    if not is_configured():
        async for event in _degraded_stream(message, session_id, role_tools, role=role):
            yield event
        yield {"type": "done", "session_id": session_id}
        return

    system = role_config.build_system_prompt(role, role_tools)
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(_history(session_id))
    messages.append({"role": "user", "content": message})

    # LLM 只能看到交集内的工具 schema
    schemas = tools.tool_schemas(allowed=role_tools)
    allowed_set = {s["function"]["name"] for s in schemas}
    final_text = ""

    for _round in range(MAX_TOOL_ROUNDS):
        pending: list[dict] = []
        final_text = ""

        async for event in chat_stream(messages, schemas):
            etype = event["type"]
            if etype == "delta":
                final_text += event["content"]
                # 事件名归一：llm_client 内部用 delta，出网统一为 token
                # （与 _degraded_stream 一致；前端 reduceEvent 只认 token，
                # 直接透传 delta 会导致回答正文被前端静默丢弃）
                yield {"type": "token", "content": event["content"]}
            elif etype == "tool_call":
                pending.append(event)
            else:
                # chat_stream 只产出 delta / tool_call：既不 yield done（llm_client 里的
                # 死代码已删除），也不产其他类型 → 此分支实际不可达，
                # 内层循环靠生成器耗尽正常退出
                break

        if not pending:
            break

        ts = int(time.time() * 1000)
        messages.append({
            "role": "assistant",
            "content": final_text or None,
            "tool_calls": [{
                "id": f"call_{ts}_{i}", "type": "function",
                "function": {"name": tc["name"],
                             "arguments": json.dumps(tc["arguments"], ensure_ascii=False)},
            } for i, tc in enumerate(pending)],
        })

        for i, tc in enumerate(pending):
            name, args = tc["name"], tc["arguments"]
            yield {"type": "tool_call", "session_id": session_id,
                   "name": name, "arguments": args}
            if name not in allowed_set:
                result = {"as_text": json.dumps(
                    {"error": f"技能 {name} 当前未启用"}, ensure_ascii=False)}
                yield {"type": "tool_result", "session_id": session_id,
                       "name": name, "summary": f"技能 {name} 当前未启用"}
            else:
                try:
                    result = await tools.execute_tool(name, args, session_id=session_id,
                                                      role=role)
                except KeyError:
                    result = {"as_text": json.dumps({"error": f"未知工具 {name}"},
                                                    ensure_ascii=False)}
                    yield {"type": "tool_result", "session_id": session_id,
                           "name": name, "summary": result["as_text"]}
                except Exception as e:  # noqa: BLE001
                    result = {"as_text": json.dumps({"error": str(e)}, ensure_ascii=False)}
                    yield {"type": "tool_result", "session_id": session_id,
                           "name": name, "summary": f"工具执行失败: {e}"}
                else:
                    # 阶段一止血：按角色 output_style 裁剪 LLM 看到的工具结果
                    # （manager 隐藏工序明细 / planner 补全工序段 / supervisor 保留归因证据）
                    result = role_config.postprocess_result(role, name, result)
                    yield {"type": "tool_result", "session_id": session_id,
                           "name": name, "summary": result.get("summary", ""),
                           "data": {k: v for k, v in result.items()
                                    if k not in ("as_text", "chart")}}
                    if result.get("chart"):
                        yield {"type": "chart", "session_id": session_id,
                               "name": name, "chart": result["chart"]}
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{ts}_{i}",
                "content": result["as_text"],
            })
    else:
        # 轮数耗尽（循环未 break，最后一轮仍在调工具）：最后一轮的工具结果已回填 messages，
        # 但还没被 LLM 消费 → 补一次「不带 tools」的收尾调用，只取文本增量，
        # 保证用户始终能看到自然语言回答（该轮已移除 tools，不会再触发工具）。
        # final_text 重置为收尾回答，与正常路径「历史只存最后一轮回答」保持一致。
        final_text = ""
        async for event in chat_stream(messages, None):
            if event["type"] == "delta":
                final_text += event["content"]
                yield {"type": "token", "content": event["content"]}

    _append_history(session_id, "user", message)
    _append_history(session_id, "assistant", final_text)
    yield {"type": "done", "session_id": session_id}
