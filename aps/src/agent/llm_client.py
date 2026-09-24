"""LLM 客户端 — 支持 OpenAI 兼容 API（GPT / DeepSeek / Qwen / 本地模型）

通过 httpx 调用 /v1/chat/completions 接口，支持流式输出和 Function Calling。
配置文件：data/agent_config.json
"""
import json
import os
from pathlib import Path
from typing import Generator

try:
    import httpx
except ImportError:
    httpx = None  # 延迟报错，使用时提示安装

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # agent → src → 项目根
CONFIG_FILE = _PROJECT_ROOT / "data" / "agent_config.json"

# 默认配置
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.3,
    "max_tokens": 4096,
}


def load_config() -> dict:
    """加载配置（文件 > 环境变量 > 默认值）"""
    config = dict(DEFAULT_CONFIG)
    # 环境变量覆盖
    if os.environ.get("AGENT_API_KEY"):
        config["api_key"] = os.environ["AGENT_API_KEY"]
    if os.environ.get("AGENT_BASE_URL"):
        config["base_url"] = os.environ["AGENT_BASE_URL"]
    if os.environ.get("AGENT_MODEL"):
        config["model"] = os.environ["AGENT_MODEL"]
    # 文件覆盖
    if CONFIG_FILE.exists():
        try:
            file_config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            config.update({k: v for k, v in file_config.items() if v})
        except Exception:
            pass
    return config


def save_config(config: dict) -> dict:
    """保存配置到文件"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 只保存可持久化的字段
    saveable = {
        "api_key": config.get("api_key", ""),
        "base_url": config.get("base_url", DEFAULT_CONFIG["base_url"]),
        "model": config.get("model", DEFAULT_CONFIG["model"]),
        "temperature": config.get("temperature", 0.3),
        "max_tokens": config.get("max_tokens", 4096),
    }
    CONFIG_FILE.write_text(json.dumps(saveable, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    return saveable


def is_configured() -> bool:
    """检查是否已配置（至少有 API key）"""
    cfg = load_config()
    return bool(cfg.get("api_key"))


def _build_headers() -> dict:
    cfg = load_config()
    return {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }


def _build_payload(messages: list, tools: list | None = None,
                   stream: bool = True) -> dict:
    cfg = load_config()
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg.get("temperature", 0.3),
        "max_tokens": cfg.get("max_tokens", 4096),
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def _get_api_url() -> str:
    cfg = load_config()
    base = cfg["base_url"].rstrip("/")
    return f"{base}/chat/completions"


def chat_stream(messages: list, tools: list | None = None
               ) -> Generator[dict, None, None]:
    """流式调用 LLM，yield 事件字典

    事件类型：
      {"type": "text_delta", "content": "..."}  — 文本增量
      {"type": "tool_calls", "tool_calls": [...]} — 工具调用（流结束时一次性返回）
      {"type": "done"}                          — 流结束
      {"type": "error", "message": "..."}       — 错误
    """
    if httpx is None:
        yield {"type": "error", "message": "httpx 未安装，请运行: pip install httpx"}
        return

    cfg = load_config()
    if not cfg.get("api_key"):
        yield {"type": "error",
               "message": "LLM 未配置。请在设置中填写 API Key，或设置环境变量 AGENT_API_KEY"}
        return

    payload = _build_payload(messages, tools, stream=True)
    url = _get_api_url()
    headers = _build_headers()

    accumulated_text = ""
    tool_calls_accum = {}  # index → {id, function: {name, arguments}}

    try:
        with httpx.Client(timeout=120.0) as client:
            with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    yield {"type": "error",
                           "message": f"API 返回 {resp.status_code}: {body[:500]}"}
                    return

                for line in resp.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                    elif line.startswith("data:"):
                        data_str = line[5:]
                    else:
                        continue
                    data_str = data_str.strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    # 文本增量
                    if delta.get("content"):
                        accumulated_text += delta["content"]
                        yield {"type": "text_delta", "content": delta["content"]}

                    # 工具调用增量
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_accum:
                                tool_calls_accum[idx] = {
                                    "id": tc.get("id", ""),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.get("id"):
                                tool_calls_accum[idx]["id"] = tc["id"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                tool_calls_accum[idx]["function"]["name"] = func["name"]
                            if func.get("arguments"):
                                tool_calls_accum[idx]["function"]["arguments"] += func["arguments"]

                    # 流结束标记
                    if choices[0].get("finish_reason"):
                        if tool_calls_accum:
                            yield {"type": "tool_calls",
                                   "tool_calls": list(tool_calls_accum.values())}
                        else:
                            yield {"type": "done"}
                        return

    except httpx.ConnectError as e:
        yield {"type": "error", "message": f"连接失败: {e}"}
    except httpx.TimeoutException:
        yield {"type": "error", "message": "请求超时（120s），请检查网络或减少 max_tokens"}
    except Exception as e:
        yield {"type": "error", "message": f"LLM 调用异常: {e}"}
