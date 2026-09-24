"""排产助手 Agent 路由

提供聊天页面、SSE 流式对话接口、配置管理。
"""
import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

try:
    from agent.agent import run_conversation, get_available_tools
    from agent.llm_client import load_config, save_config, is_configured
    from agent.tools import WRITE_TOOLS, execute_tool
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

router = APIRouter(tags=["agent"])
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "app" / "templates"))
templates.env.cache = None

from app.constants import SIDEBAR_MENU


def _ctx(request: Request, active: str, **kw):
    return {"request": request, "active_page": active, "sidebar_menu": SIDEBAR_MENU, **kw}


@router.get("/agent", response_class=HTMLResponse)
async def agent_chat(request: Request):
    return templates.TemplateResponse(
        request, "agent_chat.html",
        _ctx(request, "agent_chat",
             configured=is_configured(),
             tools=get_available_tools()))


@router.post("/api/agent/chat")
async def agent_chat_api(request: Request):
    """SSE 流式对话接口"""
    body = await request.json()
    user_message = body.get("message", "").strip()
    history = body.get("history", [])

    if not user_message:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)

    def event_stream():
        try:
            for event in run_conversation(user_message, history):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'服务异常: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/agent/config")
async def agent_get_config():
    """获取 LLM 配置（API key 脱敏）"""
    cfg = load_config()
    return {
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
        "temperature": cfg.get("temperature", 0.3),
        "max_tokens": cfg.get("max_tokens", 4096),
        "has_api_key": bool(cfg.get("api_key")),
        "api_key_masked": _mask_key(cfg.get("api_key", "")),
        "configured": is_configured(),
    }


@router.post("/api/agent/config")
async def agent_save_config(request: Request):
    """保存 LLM 配置"""
    body = await request.json()
    config = {
        "api_key": body.get("api_key", ""),
        "base_url": body.get("base_url", "https://api.openai.com/v1"),
        "model": body.get("model", "gpt-4o-mini"),
        "temperature": float(body.get("temperature", 0.3)),
        "max_tokens": int(body.get("max_tokens", 4096)),
    }
    # 如果 api_key 为空字符串，不覆盖现有 key
    if not config["api_key"]:
        existing = load_config()
        config["api_key"] = existing.get("api_key", "")

    saved = save_config(config)
    return {"ok": True, "config": {
        "base_url": saved["base_url"],
        "model": saved["model"],
        "has_api_key": bool(saved["api_key"]),
    }}


@router.post("/api/agent/tool/execute")
async def agent_tool_execute(request: Request):
    """执行需人工确认的写操作工具（仅限 WRITE_TOOLS 白名单）。

    前端在收到 confirm_required 事件、用户点击「确认执行」后调用本接口，
    以 confirmed=True 真正执行写操作并返回结果。
    """
    body = await request.json()
    name = body.get("name", "")
    args = body.get("args") or {}
    if not isinstance(args, dict):
        return JSONResponse({"ok": False, "error": "args 必须是对象"}, status_code=400)
    if name not in WRITE_TOOLS:
        return JSONResponse(
            {"ok": False, "error": f"工具 {name} 不在可确认执行的写操作白名单内"},
            status_code=400)

    result = execute_tool(name, args, confirmed=True)
    ok = not (isinstance(result, dict)
              and (result.get("error") or result.get("ok") is False))
    return {"ok": ok, "name": name, "result": result}


@router.get("/api/agent/tools")
async def agent_list_tools():
    """列出可用工具"""
    return {"tools": get_available_tools()}


@router.get("/api/agent/status")
async def agent_status():
    """Agent 状态"""
    return {"configured": is_configured()}


def _mask_key(key: str) -> str:
    """API key 脱敏"""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "..." + key[-4:]
