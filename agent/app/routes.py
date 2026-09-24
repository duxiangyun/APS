"""Agent API 路由

- POST /chat/stream     SSE 流式对话（token / tool_call / tool_result / chart / done）
- GET  /skills          可用技能（工具）清单，供前端左侧栏
- GET  /health          健康检查（含 APS 连通性）
- POST /tools/{name}    工具直查（不经 LLM，调试/降级用）

兼容路由（供 web/ 前端旧调用）：
- GET  /api/health      等价 /health
- GET  /api/aps/open/{path}  APS /open/* 只读透传
- POST /api/chat        等价 /chat/stream
"""
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import aps_client, react, tools
from .aps_client import APSApiError
from . import audit, llm_config
from .llm_client import is_configured

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    role: str = Field("planner", description="角色：planner / analyst / default")
    session_id: str | None = Field(None, description="会话 ID，缺省自动生成")
    skills: list[str] | None = Field(None, description="启用的技能名，缺省为全部")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# 核心接口
# ---------------------------------------------------------------------------
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话：token → tool_call → tool_result → chart → done"""

    async def event_stream():
        # start 事件由 run_react 统一发出（含 session_id / llm_configured / role）
        try:
            async for event in react.run_react(
                req.message.strip(), role=req.role, session_id=req.session_id,
                allowed_skills=req.skills,
            ):
                yield _sse(event)
        except APSApiError as e:
            yield _sse({"type": "error", "message": f"APS 调用失败: {e}"})
        except Exception as e:  # noqa: BLE001
            yield _sse({"type": "error", "message": f"服务异常: {e}"})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


@router.get("/skills")
async def skills(role: str | None = None):
    """可用技能/工具清单（按角色白名单过滤，供前端左侧栏展示）"""
    from . import role_config
    return {
        "role": role_config.extract_role(role),
        "skills": tools.skills_payload(allowed=role_config.filter_tools(role, tools.TOOLS)),
    }


@router.get("/health")
async def health():
    cfg = llm_config.get_config()
    configured = is_configured()
    data: dict = {"status": "ok", "service": "agent",
                  "llm_configured": configured,
                  "llm_model": cfg["model"] if configured else None,
                  "llm_fallback_model": cfg["fallback_model"] if configured else None}
    try:
        data["aps"] = await aps_client.aps_health()
        data["aps_connected"] = True
    except Exception as e:  # noqa: BLE001
        data["aps_connected"] = False
        data["aps_error"] = str(e)
    return data


@router.post("/tools/{name}")
async def call_tool(name: str, req: Request):
    """工具直查（不经 LLM）：请求体为工具参数 JSON 对象

    保留键（不传给工具函数）：
    - session_id：审计/会话标识（缺省 "-"）
    - role：角色，用于强制执行角色-工具白名单与 admin 专属工具校验
    - confirmed：是否已二次确认（写入型工具预留）
    """
    if name not in tools.TOOLS:
        raise HTTPException(status_code=404, detail=f"工具 '{name}' 不存在")
    try:
        body = await req.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    session_id = str(body.pop("session_id", "-") or "-")
    # 缺省 role 按 "default" 处理：HTTP 层不留白名单绕过口子
    # （进程内调试如需免白名单，直接调用 tools.execute_tool(role=None)）
    role = str(body.pop("role", None) or "default")
    confirmed = bool(body.pop("confirmed", False))
    try:
        result = await tools.execute_tool(name, body, session_id=session_id,
                                          role=role, confirmed=confirmed)
    except APSApiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    result.pop("as_text", None)
    return {"tool": name, "session_id": session_id, "role": role, "result": result}


@router.get("/audit/logs")
async def audit_logs(session_id: str | None = None, role: str | None = None,
                     tool: str | None = None, limit: int = 50):
    """审计日志查询（最近记录，按时间倒序）

    - session_id：按会话过滤
    - role：按角色过滤（planner/manager/...）
    - tool：按工具名过滤
    - limit：返回条数上限（默认 50，最大 500）
    """
    logs = audit.query_logs(session_id=session_id, role=role,
                            tool=tool, limit=limit)
    return {"count": len(logs), "logs": logs}


@router.get("/roles")
async def roles():
    """角色清单（含白名单/输出风格，供前端角色切换展示能力差异）"""
    from . import role_config
    return {
        "roles": [
            {
                "key": cfg["key"],
                "label": cfg["label"],
                "allowed_tools": cfg["allowed_tools"],
                "output_style": cfg["output_style"]["label"],
                "requires_confirmation": cfg["requires_confirmation"],
            }
            for cfg in (role_config.get_role_config(k) for k in role_config.ROLE_KEYS)
        ]
    }


# ---------------------------------------------------------------------------
# 大模型配置（前端「大模型配置」页面）
# ---------------------------------------------------------------------------
@router.get("/llm/config")
async def llm_get_config():
    """当前 LLM 配置（API Key 脱敏）+ 厂商/模型预设"""
    return llm_config.public_config()


@router.post("/llm/config")
async def llm_save_config(req: Request):
    """保存 LLM 配置；api_key 为空表示保留原值。保存后立即生效（无需重启）"""
    try:
        body = await req.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
    saved = llm_config.save_config(body)
    return {
        "ok": True,
        "config": {
            "base_url": saved["base_url"],
            "model": saved["model"],
            "fallback_model": saved["fallback_model"],
            "temperature": saved["temperature"],
            "max_tokens": saved["max_tokens"],
            "has_api_key": bool(saved["api_key"]),
            "api_key_masked": llm_config.mask_key(saved["api_key"]),
            "configured": is_configured(),
        },
    }


@router.post("/llm/test")
async def llm_test(req: Request):
    """连通性测试：用给定配置发一次极小的非流式补全，返回时延与结果摘要。

    请求体：{base_url, api_key, model}；api_key 为空时使用已保存的 Key。
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")

    saved = llm_config.get_config()
    base_url = str(body.get("base_url") or saved["base_url"]).strip().rstrip("/")
    api_key = str(body.get("api_key") or saved["api_key"]).strip()
    model = str(body.get("model") or saved["model"]).strip()
    if not (base_url and api_key and model):
        return {"ok": False, "message": "base_url / api_key / model 均不能为空"}

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "回复“连接成功”四个字"}],
        "max_tokens": 16, "temperature": 0, "stream": False,
    }
    import time as _time

    import httpx
    started = _time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json=payload,
            )
        latency_ms = int((_time.monotonic() - started) * 1000)
        if resp.status_code >= 400:
            return {"ok": False, "latency_ms": latency_ms,
                    "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        return {"ok": True, "latency_ms": latency_ms,
                "model": model, "reply": str(content)[:60]}
    except (httpx.HTTPError, ValueError) as e:
        latency_ms = int((_time.monotonic() - started) * 1000)
        return {"ok": False, "latency_ms": latency_ms, "message": str(e)[:300]}


# ---------------------------------------------------------------------------
# 兼容路由（web/ 前端旧调用）
# ---------------------------------------------------------------------------
@router.get("/api/health")
async def health_alias():
    return await health()


@router.get("/api/aps/open/{path:path}")
async def aps_proxy(path: str, request: Request):
    """APS /open/* 开放接口只读透传"""
    try:
        return await aps_client.aps_request(
            "GET", f"/open/{path}", params=dict(request.query_params))
    except APSApiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/api/chat")
async def chat_alias(req: ChatRequest):
    return await chat_stream(req)
