"""LLM 客户端（OpenAI Chat Completions 兼容，SSE 流式）

- 主模型失败（429 / 5xx / 错误码 1305）自动重试一次
- 重试仍失败切换 LLM_FALLBACK_MODEL 备用模型
- 未配置 LLM_API_KEY/LLM_BASE_URL 时 is_configured()=False，上层进降级模式
"""
import json
from typing import Any, AsyncGenerator

import httpx

from . import llm_config
from .config import LLM_RETRY_BODY_CODES, LLM_RETRY_STATUS


class LLMError(Exception):
    """LLM 调用失败（HTTP 状态码或错误码记录在消息中）"""


def is_configured() -> bool:
    cfg = llm_config.get_config()
    return bool(cfg["api_key"] and cfg["base_url"] and cfg["model"])


def _headers(cfg: dict) -> dict:
    return {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}


def _retryable_status(status: int, body: str) -> bool:
    """429/5xx 或响应体含错误码（如 1305）时需要重试"""
    if status in LLM_RETRY_STATUS:
        return True
    return any(code in body for code in LLM_RETRY_BODY_CODES)


def _payload(cfg: dict, model: str, messages: list[dict], tools: list[dict] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model, "messages": messages,
        "temperature": cfg["temperature"], "max_tokens": cfg["max_tokens"],
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
    return payload


async def _stream_once(
    cfg: dict,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
) -> AsyncGenerator[dict, None]:
    """单次流式调用，yield 事件（LLM 内部事件名，出网前由 react 层归一）：

    {"type": "delta", "content": "..."}                        文本增量
    {"type": "tool_call", "name": "...", "arguments": {...}}   工具调用

    生成器耗尽即表示本轮结束（不产 done 事件：react 层按 delta/tool_call 判定收敛，
    会话结束由 react.run_react 统一发 done）。

    失败时抛 LLMError（消息形如 "HTTP_429:..."），由上层决定重试/切换。
    """
    tool_calls: dict[int, dict] = {}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST", f"{cfg['base_url'].rstrip('/')}/chat/completions",
            headers=_headers(cfg), json=_payload(cfg, model, messages, tools),
        ) as resp:
            if resp.status_code >= 400:
                text = (await resp.aread()).decode("utf-8", "ignore")
                raise LLMError(f"HTTP_{resp.status_code}:{text[:300]}")

            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    # 响应体级错误（如 {"error":{"code":1305}}）
                    if obj.get("error"):
                        raise LLMError(f"BODY_CODE_{obj['error'].get('code', '')}")
                    continue
                delta = choices[0].get("delta") or {}

                content = delta.get("content")
                if content:
                    yield {"type": "delta", "content": content}

                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    slot = tool_calls.setdefault(idx, {"name": "", "arguments": ""})
                    if tc.get("function", {}).get("name"):
                        slot["name"] = tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        slot["arguments"] += tc["function"]["arguments"]

    for idx in sorted(tool_calls):
        slot = tool_calls[idx]
        try:
            arguments = json.loads(slot["arguments"]) if slot["arguments"] else {}
        except json.JSONDecodeError:
            arguments = {}
        yield {"type": "tool_call", "name": slot["name"], "arguments": arguments}



async def chat_stream(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """带重试与备用模型切换的流式对话。

    策略：主模型 → 失败重试 1 次 → 仍失败切换 fallback_model。
    仅当尚未产出任何内容（无 delta / tool_call）时才重试或切换；
    已开始输出的流中断则直接抛 LLMError，避免重复输出。
    """
    cfg = llm_config.get_config()
    candidates = [cfg["model"], cfg["model"]]
    if cfg["fallback_model"] and cfg["fallback_model"] != cfg["model"]:
        candidates.append(cfg["fallback_model"])

    last_error = ""
    for model in candidates:
        produced = False
        try:
            async for event in _stream_once(cfg, model, messages, tools):
                if event["type"] in ("delta", "tool_call"):
                    produced = True
                yield event
            return
        except (httpx.HTTPError, LLMError) as e:
            if produced:
                raise  # 已开始输出，不重试
            msg = str(e)
            if msg.startswith("HTTP_"):
                status_str, _, body = msg.partition(":")
                status = int(status_str.removeprefix("HTTP_") or 0)
                if not _retryable_status(status, body):
                    raise  # 不可重试错误（如 401 鉴权失败）
            last_error = f"{model}: {msg}"

    raise LLMError(f"所有模型均失败（含重试与备用模型）: {last_error}")
