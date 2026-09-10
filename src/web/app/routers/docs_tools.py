"""项目文档与开发工具页面路由。

- /docs        文档中心：列出 docs/ 下所有 Markdown 文档
- /docs/view   在线渲染指定 Markdown 文档（前端 marked.js 渲染 + 目录导航）
- /tools       开发工具总览：汇集开发/验证/测试类工具入口
"""
import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import SIDEBAR_MENU

router = APIRouter(tags=["docs_tools"])

# 本文件位于 src/web/app/routers/，_BASE_DIR 指向 src/web
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 项目根目录 = src/web 向上两级
_PROJECT_ROOT = _BASE_DIR.parent.parent
_DOCS_DIR = _PROJECT_ROOT / "docs"

templates = Jinja2Templates(directory=str(_BASE_DIR / "app" / "templates"))
templates.env.cache = None


def _list_docs() -> list:
    """扫描 docs 目录下的 .md 文件，提取标题（取第一个一级标题）。"""
    docs = []
    if _DOCS_DIR.exists():
        for p in sorted(_DOCS_DIR.glob("*.md")):
            text = p.read_text(encoding="utf-8", errors="ignore")
            title = None
            for line in text.splitlines():
                m = re.match(r"^#\s+(.+?)\s*$", line.strip())
                if m:
                    title = m.group(1).strip()
                    break
            # 摘要：取第一段非标题、非空文本
            summary = ""
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith("#") and not s.startswith("|") and not s.startswith("-"):
                    summary = s[:80]
                    break
            docs.append({
                "file": p.name,
                "title": title or p.stem,
                "summary": summary,
                "size_kb": round(p.stat().st_size / 1024, 1),
            })
    return docs


@router.get("/docs", response_class=HTMLResponse)
async def docs_home(request: Request):
    return templates.TemplateResponse(request, "docs/index.html", {
        "request": request,
        "docs": _list_docs(),
        "active_page": "docs_home",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "项目文档",
        "page_icon": "fa-book",
    })


@router.get("/docs/view", response_class=HTMLResponse)
async def docs_view(request: Request, file: str):
    # 白名单校验：只允许 docs 目录下实际存在的 .md 文件，防止路径穿越
    allowed = {d["file"] for d in _list_docs()}
    if file not in allowed:
        return HTMLResponse(status_code=404, content="<h1>404 - 文档不存在</h1>")
    path = _DOCS_DIR / file
    md_content = path.read_text(encoding="utf-8", errors="ignore")
    title = next((d["title"] for d in _list_docs() if d["file"] == file), file)
    return templates.TemplateResponse(request, "docs/view.html", {
        "request": request,
        "title": title,
        "file": file,
        "md_content": md_content,
        "active_page": "docs_home",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "项目文档",
        "page_icon": "fa-book",
    })


@router.get("/tools", response_class=HTMLResponse)
async def tools_home(request: Request):
    # 已可用 / 规划中的工具入口；后续新增验证测试工具时在此登记
    tools = [
        {"name": "数据校验", "desc": "对排产输入数据做完整性、一致性校验，输出问题清单。",
         "url": "/admin/validation", "icon": "fa-clipboard-check", "status": "available"},
        {"name": "API 接口文档", "desc": "FastAPI 自动生成的接口文档（Swagger UI），可在线调试各 API。",
         "url": "/api-docs", "icon": "fa-plug", "status": "available"},
        {"name": "求解器对比", "desc": "同一模型分别用 Gurobi / HiGHS 求解，对比目标值与耗时。",
         "url": "#", "icon": "fa-balance-scale", "status": "planned"},
        {"name": "ETL 导入验证", "desc": "检查 staging → 核心层数据转换结果与记录数。",
         "url": "#", "icon": "fa-file-import", "status": "planned"},
        {"name": "模型一致性检查", "desc": "校验物料平衡、能力约束等模型结构与数据匹配情况。",
         "url": "#", "icon": "fa-project-diagram", "status": "planned"},
    ]
    return templates.TemplateResponse(request, "tools/index.html", {
        "request": request,
        "tools": tools,
        "active_page": "tools_home",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "开发工具",
        "page_icon": "fa-tools",
    })
