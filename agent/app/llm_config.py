"""LLM 运行时配置（可在前端「大模型配置」中在线修改，保存后立即生效）

优先级：agent/data/llm_config.json 覆盖环境变量（config.py 读到的 env 默认值）。
- API Key 只写不读：GET 配置时仅返回脱敏提示；POST 时空 Key 表示保留原值。
- save_config() 后 llm_client 每次请求都会 get_config()，无需重启服务。
"""
import json
import os
import threading
import time

from .config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_FALLBACK_MODEL, LLM_MAX_TOKENS,
    LLM_MODEL, LLM_TEMPERATURE,
)

# ---------------------------------------------------------------------------
# 常用厂商/模型预设（前端「大模型配置」下拉选择后自动填充 base_url 与模型列表）
# ---------------------------------------------------------------------------
PROVIDER_PRESETS = [
    {
        "key": "zhipu",
        "name": "智谱 GLM（OpenAI 兼容）",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4.7-flash", "glm-4.7", "glm-4-plus", "glm-4-air", "glm-4-flash"],
    },
    {
        "key": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    {
        "key": "moonshot",
        "name": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "kimi-k2-0711-preview"],
    },
    {
        "key": "dashscope",
        "name": "阿里云百炼（通义）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
    },
    {
        "key": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    },
    {
        "key": "ollama",
        "name": "Ollama（本地）",
        "base_url": "http://127.0.0.1:11434/v1",
        "models": ["qwen2.5:7b", "llama3.1:8b"],
    },
    {
        "key": "custom",
        "name": "自定义（OpenAI 兼容）",
        "base_url": "",
        "models": [],
    },
]

_LOCK = threading.Lock()
CONFIG_PATH = os.environ.get(
    "LLM_CONFIG_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "llm_config.json"),
)

_ALLOWED_KEYS = ("base_url", "api_key", "model", "fallback_model",
                 "temperature", "max_tokens")


def _defaults() -> dict:
    return {
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY,
        "model": LLM_MODEL,
        "fallback_model": LLM_FALLBACK_MODEL,
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }


def _read_file() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_config() -> dict:
    """合并后的有效配置（内部使用，含明文 api_key；严禁直接返回给前端）

    注意：JSON 覆盖文件中的空字符串对 fallback_model 是有效值（= 不使用备用模型），
    故 fallback_model 不做「空值跳过」处理，其余键空值回退环境变量默认。
    """
    cfg = _defaults()
    overrides = _read_file()
    for k in _ALLOWED_KEYS:
        v = overrides.get(k)
        if k == "fallback_model":
            if v is not None:
                cfg[k] = str(v)
            continue
        if v not in (None, ""):
            cfg[k] = v
    try:
        cfg["temperature"] = float(cfg["temperature"])
    except (TypeError, ValueError):
        cfg["temperature"] = 0.3
    try:
        cfg["max_tokens"] = int(cfg["max_tokens"])
    except (TypeError, ValueError):
        cfg["max_tokens"] = 4096
    return cfg


def save_config(patch: dict) -> dict:
    """保存配置（合并到 JSON 文件）；api_key 为空/缺失时保留原值。返回新配置。"""
    current = get_config()
    clean: dict = {}
    for k in _ALLOWED_KEYS:
        if k not in patch:
            continue
        v = patch[k]
        if k == "temperature":
            try:
                v = max(0.0, min(2.0, float(v)))
            except (TypeError, ValueError):
                continue
        elif k == "max_tokens":
            try:
                v = max(64, min(32768, int(v)))
            except (TypeError, ValueError):
                continue
        else:
            v = str(v or "").strip()
        if k == "fallback_model":
            clean[k] = v  # 允许显式清空备用模型（空字符串 = 不使用备用模型）
            continue
        if v:
            clean[k] = v
    if not clean.get("api_key"):
        clean["api_key"] = current["api_key"]

    with _LOCK:
        merged = {k: current[k] for k in _ALLOWED_KEYS}
        merged.update(clean)
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = f"{CONFIG_PATH}.{int(time.time())}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    return get_config()


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "..." + key[-4:]


def public_config() -> dict:
    """脱敏后的配置（返回给前端，不含明文 Key）"""
    cfg = get_config()
    return {
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "fallback_model": cfg["fallback_model"],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
        "has_api_key": bool(cfg["api_key"]),
        "api_key_masked": mask_key(cfg["api_key"]),
        "configured": bool(cfg["api_key"] and cfg["base_url"] and cfg["model"]),
        "presets": PROVIDER_PRESETS,
    }
