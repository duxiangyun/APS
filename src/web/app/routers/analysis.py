"""排程可视化 / 分析中心 / 计划版本 / 数据校验 / 排产触发 路由

页面采用服务端渲染（表格/热力网格），图表页通过 JSON 注入 Chart.js；
排产触发为子进程调用，轮询 /api/solve/status。
"""
import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_db_conn
from app.services.analysis_service import (
    get_order_delivery_board, get_gantt_data, get_delay_analysis,
    get_bottleneck_analysis, get_inventory_analysis, get_cost_analysis,
    get_outsource_analysis, get_versions, get_version_compare,
    get_validation_report, start_solve, solve_status,
)
from app.constants import SIDEBAR_MENU

router = APIRouter(tags=["analysis"])
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "app" / "templates"))


def _ctx(request: Request, active: str, **kw):
    return {"request": request, "active_page": active, "sidebar_menu": SIDEBAR_MENU, **kw}


# ---------------- 排程可视化 ----------------

@router.get("/vis/gantt", response_class=HTMLResponse)
async def vis_gantt(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("vis/gantt.html",
                                      _ctx(request, "vis_gantt", data=get_gantt_data(conn)))


@router.get("/vis/orders", response_class=HTMLResponse)
async def vis_orders(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("vis/orders.html",
                                      _ctx(request, "vis_orders", data=get_order_delivery_board(conn)))


# ---------------- 分析中心 ----------------

@router.get("/analysis/delay", response_class=HTMLResponse)
async def analysis_delay(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("analysis/delay.html",
                                      _ctx(request, "analysis_delay", data=get_delay_analysis(conn)))


@router.get("/analysis/bottleneck", response_class=HTMLResponse)
async def analysis_bottleneck(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("analysis/bottleneck.html",
                                      _ctx(request, "analysis_bottleneck", data=get_bottleneck_analysis(conn)))


@router.get("/analysis/inventory", response_class=HTMLResponse)
async def analysis_inventory(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    data = get_inventory_analysis(conn)
    return templates.TemplateResponse(
        "analysis/inventory.html",
        _ctx(request, "analysis_inventory", data=data, chart_json=json.dumps(data, ensure_ascii=False)))


@router.get("/analysis/cost", response_class=HTMLResponse)
async def analysis_cost(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    data = get_cost_analysis(conn)
    return templates.TemplateResponse(
        "analysis/cost.html",
        _ctx(request, "analysis_cost", data=data, chart_json=json.dumps(data, ensure_ascii=False)))


@router.get("/analysis/outsource", response_class=HTMLResponse)
async def analysis_outsource(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    data = get_outsource_analysis(conn)
    return templates.TemplateResponse(
        "analysis/outsource.html",
        _ctx(request, "analysis_outsource", data=data, chart_json=json.dumps(data, ensure_ascii=False)))


# ---------------- 计划版本 ----------------

@router.get("/versions", response_class=HTMLResponse)
async def versions(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("versions/list.html",
                                      _ctx(request, "versions", versions=get_versions(conn)))


@router.get("/versions/compare", response_class=HTMLResponse)
async def versions_compare(
    request: Request, a: int = 0, b: int = 0,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    versions_all = get_versions(conn)
    ids = [v["run_id"] for v in versions_all]
    if not ids:
        raise HTTPException(404, "暂无排产结果")
    a = a if a else (ids[-1] if len(ids) > 1 else ids[0])
    b = b if b else ids[0]
    if a not in ids or b not in ids:
        raise HTTPException(404, "指定的版本不存在")
    data = get_version_compare(conn, a, b)
    return templates.TemplateResponse(
        "versions/compare.html",
        _ctx(request, "versions", data=data, versions=versions_all, a=a, b=b))


# ---------------- 系统管理 ----------------

@router.get("/admin/validation", response_class=HTMLResponse)
async def admin_validation(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("admin/validation.html",
                                      _ctx(request, "admin_validation", checks=get_validation_report(conn)))


# ---------------- 计划优化：排产触发 ----------------

@router.get("/solve", response_class=HTMLResponse)
async def solve_page(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    return templates.TemplateResponse("solve.html",
                                      _ctx(request, "solve", status=solve_status(conn)))


@router.post("/api/solve/start")
async def api_solve_start():
    return JSONResponse(start_solve())


@router.get("/api/solve/status")
async def api_solve_status(conn: sqlite3.Connection = Depends(get_db_conn)):
    return JSONResponse(solve_status(conn))
