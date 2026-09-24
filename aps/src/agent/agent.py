"""APS Agent 编排逻辑

核心循环：
  1. 将用户消息 + 系统提示 + 工具定义发送给 LLM（流式）
  2. 流式返回文本增量给前端
  3. 如果 LLM 返回工具调用 → 执行工具 → 将结果加入对话 → 回到第 1 步
  4. 直到 LLM 返回纯文本（无工具调用），对话完成

通过 yield 事件流实现 SSE 推送。
"""
import json
import uuid
from typing import Generator

from .prompts import get_system_prompt
from .llm_client import chat_stream, is_configured
from .tools import TOOL_DEFINITIONS, execute_tool

# 最大工具调用轮次（防止死循环）
MAX_TOOL_ROUNDS = 8
# 传给 LLM 的历史对话最多保留的条数（user+assistant 各算一条）
MAX_HISTORY_ITEMS = 12
# 单个工具结果进入 LLM 上下文的最大字符数
MAX_TOOL_RESULT_CHARS = 6000


def _trim_history(history: list) -> list:
    """只保留最近 N 条对话，避免长对话上下文无限增长"""
    turns = []
    for h in history or []:
        role = h.get("role")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            turns.append({"role": role, "content": content})
    return turns[-MAX_HISTORY_ITEMS:]


def _truncate_for_llm(text: str, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    """工具结果过大时截断，避免撑爆 LLM 上下文"""
    if len(text) <= max_chars:
        return text
    return (text[:max_chars]
            + f"\n...(结果过长已截断，原始长度 {len(text)} 字符。如需更多信息请缩小查询范围)")


def run_conversation(user_message: str,
                     history: list | None = None) -> Generator[dict, None, None]:
    """运行一轮对话，yield SSE 事件

    事件格式：
      {"type": "text_delta", "content": "..."}     — LLM 文本增量
      {"type": "text_done", "content": "..."}      — LLM 完整文本
      {"type": "tool_call", "name": "...", "args": {...}} — 工具调用通知
      {"type": "tool_result", "name": "...", "result": {...}} — 工具执行结果
      {"type": "error", "message": "..."}          — 错误
      {"type": "done", "text": "..."}              — 对话完成
    """
    if not is_configured():
        yield {"type": "error",
               "message": "LLM 未配置。请点击右上角设置图标配置 API Key、Base URL 和模型名称。"}
        return

    # 构建消息列表
    messages = [{"role": "system", "content": get_system_prompt()}]

    # 加入历史对话（裁剪，避免上下文无限增长）
    if history:
        messages.extend(_trim_history(history))

    # 加入当前用户消息
    messages.append({"role": "user", "content": user_message})

    full_text = ""

    for round_idx in range(MAX_TOOL_ROUNDS):
        # 调用 LLM
        tool_calls = None
        round_text = ""

        for event in chat_stream(messages, TOOL_DEFINITIONS):
            if event["type"] == "text_delta":
                round_text += event["content"]
                yield {"type": "text_delta", "content": event["content"]}
            elif event["type"] == "tool_calls":
                tool_calls = event["tool_calls"]
            elif event["type"] == "error":
                yield event
                return
            # "done" 事件无需特殊处理

        if tool_calls:
            # 将 assistant 的工具调用消息加入对话
            messages.append({
                "role": "assistant",
                "content": round_text or None,
                "tool_calls": tool_calls,
            })

            # 逐个执行工具调用
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    args = {}

                # 通知前端正在调用工具
                yield {"type": "tool_call", "name": tool_name, "args": args}

                # 执行工具
                result = execute_tool(tool_name, args)

                # 写操作需用户确认：不执行，通知前端弹确认卡片
                if isinstance(result, dict) and result.get("needs_confirmation"):
                    yield {"type": "confirm_required", "name": tool_name, "args": args}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps({
                            "status": "awaiting_user_confirmation",
                            "message": ("该工具是写操作，需要用户确认。请告知用户："
                                        "请在下方的工具卡片上点击「确认执行」或「取消」。"
                                        "确认后系统会自动执行并回传结果。"),
                        }, ensure_ascii=False),
                    })
                    continue

                # 将工具结果加入对话（截断，避免撑爆 LLM 上下文）
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": _truncate_for_llm(
                        json.dumps(result, ensure_ascii=False, default=str)),
                })

                # 通知前端工具执行完成
                # 精简结果（避免过大的数据推送到前端）
                compact_result = _compact_result(result)
                yield {"type": "tool_result", "name": tool_name,
                       "result": compact_result}

            # 继续下一轮 LLM 调用（LLM 会基于工具结果生成回复）
            continue
        else:
            # 无工具调用 → 对话完成
            full_text = round_text
            yield {"type": "text_done", "content": full_text}
            yield {"type": "done", "text": full_text}
            return

    # 超过最大轮次
    yield {"type": "text_done", "content": full_text}
    yield {"type": "error", "message": f"已达到最大工具调用轮次（{MAX_TOOL_ROUNDS}），请缩小问题范围后重试"}
    yield {"type": "done", "text": full_text}


def _compact_result(result: dict) -> dict:
    """精简工具结果用于前端展示（避免推送过大的数据）"""
    if not isinstance(result, dict):
        return {"value": result}

    # 对于列表类结果，只保留摘要
    compact = {}
    for k, v in result.items():
        if isinstance(v, list):
            if len(v) > 10:
                compact[k] = {"_summary": f"共 {len(v)} 条记录", "_preview": v[:10]}
            else:
                compact[k] = v
        elif isinstance(v, dict):
            # 嵌套字典也精简
            compact[k] = _compact_result(v)
        else:
            compact[k] = v
    return compact


def get_available_tools() -> list:
    """返回可用工具列表（用于前端展示）"""
    return [{"name": t["function"]["name"],
             "description": t["function"]["description"]}
            for t in TOOL_DEFINITIONS]
