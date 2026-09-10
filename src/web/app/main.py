from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import api, pages, analysis, docs_tools

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(
    title="APS 智能排产系统",
    version="0.1.0",
    # /docs 让给“项目文档”，FastAPI 自带的接口文档迁移到 /api-docs、/api-redoc
    docs_url="/api-docs",
    redoc_url="/api-redoc",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages.router)
app.include_router(api.router)
app.include_router(api.stg_router)
app.include_router(api.biz_router)
app.include_router(api.alg_router)
app.include_router(api.res_router)
app.include_router(api.dash_router)
app.include_router(api.edit_router)
app.include_router(api.params_router)
app.include_router(analysis.router)
app.include_router(docs_tools.router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": str(exc.detail)})
    return HTMLResponse(content="<h1>404 - 页面不存在</h1>", status_code=404)
