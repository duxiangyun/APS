import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# APS 后端地址（docker-compose 中为服务名 aps，本地开发默认 127.0.0.1:8000）
# ---------------------------------------------------------------------------
APS_BASE_URL = os.environ.get("APS_BASE_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# LLM 配置（OpenAI 兼容接口）
#   LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
#   LLM_FALLBACK_MODEL：备用模型，主模型重试仍失败时自动切换
# ---------------------------------------------------------------------------
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4.7-flash")
LLM_FALLBACK_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "glm-4.7-flash")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
# 遇到这些状态码/错误码时重试一次，再失败切换备用模型
LLM_RETRY_STATUS = {429, 500, 502, 503}
LLM_RETRY_BODY_CODES = {"1305"}

# ---------------------------------------------------------------------------
# 服务
# ---------------------------------------------------------------------------
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8100"))

# 工具调用日志（JSONL，每行一条）
TOOL_LOG_PATH = os.environ.get(
    "TOOL_LOG_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "tool_calls.jsonl"),
)

# ReAct 循环最大轮数（防止死循环）
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "6"))

# ---------------------------------------------------------------------------
# 周期语义（APS 模型为「周期」粒度，数据库中没有周期↔日期的映射表）
#   APS_CURRENT_PERIOD：把「今天 / 当前」映射到哪个周期（默认第 1 期）
#   APS_PERIOD_DAYS   ：一个周期折合多少天，用于换算「最近 N 天 / 未来 N 天」
# ---------------------------------------------------------------------------
APS_CURRENT_PERIOD = int(os.environ.get("APS_CURRENT_PERIOD", "1"))
APS_PERIOD_DAYS = int(os.environ.get("APS_PERIOD_DAYS", "7"))

# 会话历史保留条数（内存态）
SESSION_HISTORY_LIMIT = int(os.environ.get("SESSION_HISTORY_LIMIT", "24"))
