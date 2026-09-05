import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_db_conn, get_pagination, PaginationParams
from app.services.table_service import (
    validate_table,
    validate_stg_table,
    validate_biz_table,
    validate_alg_table,
    validate_result_view,
    get_table_count,
    get_table_rows,
    get_all_table_counts,
    get_all_stg_table_counts,
    get_all_biz_table_counts,
    get_all_alg_table_counts,
    get_all_result_view_counts,
    calc_total_pages,
)
from app.services.meta_service import get_display_columns, apply_enum_display
from app.services.dashboard_service import get_dashboard
from app.constants import COLUMN_DISPLAY_ORDER, SIDEBAR_MENU

router = APIRouter(tags=["pages"])
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "app" / "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    data = get_dashboard(conn)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "data": data,
        "active_page": "dashboard",
        "sidebar_menu": SIDEBAR_MENU,
    })


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_table_counts(conn)
    total = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return templates.TemplateResponse("base_data/overview.html", {
        "request": request,
        "tables": tables,
        "total": total,
        "non_empty": non_empty,
        "active_page": "overview",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "基础数据总览",
        "page_icon": "fa-database",
        "link_base": "/base-data",
    })


@router.get("/base-data/{table_key}", response_class=HTMLResponse)
async def table_detail(
    table_key: str,
    request: Request,
    params: PaginationParams = Depends(get_pagination),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    display_columns = get_display_columns(conn, table_name)

    total = get_table_count(conn, table_name, params.search)
    rows = get_table_rows(
        conn, table_name, columns,
        params.page, params.page_size, params.search,
        params.sort_by, params.sort_order,
    )
    rows = apply_enum_display(rows, table_name)

    return templates.TemplateResponse("base_data/table_detail.html", {
        "request": request,
        "table_key": table_key,
        "table_name": table_name,
        "table_label": table_info["label"],
        "columns": display_columns,
        "rows": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": calc_total_pages(total, params.page_size),
        "search": params.search,
        "sort_by": params.sort_by,
        "sort_order": params.sort_order,
        "active_page": table_key,
        "sidebar_menu": SIDEBAR_MENU,
        "api_base": "/api/base-data",
        "back_url": "/",
    })


@router.get("/stg", response_class=HTMLResponse)
async def stg_overview(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_stg_table_counts(conn)
    total = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return templates.TemplateResponse("base_data/overview.html", {
        "request": request,
        "tables": tables,
        "total": total,
        "non_empty": non_empty,
        "active_page": "stg_overview",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "原始数据总览",
        "page_icon": "fa-file-alt",
        "link_base": "/stg",
    })


@router.get("/stg/{table_key}", response_class=HTMLResponse)
async def stg_table_detail(
    table_key: str,
    request: Request,
    params: PaginationParams = Depends(get_pagination),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_stg_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    display_columns = get_display_columns(conn, table_name)

    total = get_table_count(conn, table_name, params.search)
    rows = get_table_rows(
        conn, table_name, columns,
        params.page, params.page_size, params.search,
        params.sort_by, params.sort_order,
    )
    rows = apply_enum_display(rows, table_name)

    return templates.TemplateResponse("base_data/table_detail.html", {
        "request": request,
        "table_key": table_key,
        "table_name": table_name,
        "table_label": table_info["label"],
        "columns": display_columns,
        "rows": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": calc_total_pages(total, params.page_size),
        "search": params.search,
        "sort_by": params.sort_by,
        "sort_order": params.sort_order,
        "active_page": table_key,
        "sidebar_menu": SIDEBAR_MENU,
        "api_base": "/api/stg",
        "back_url": "/stg",
    })


@router.get("/biz", response_class=HTMLResponse)
async def biz_overview(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_biz_table_counts(conn)
    total = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return templates.TemplateResponse("base_data/overview.html", {
        "request": request,
        "tables": tables,
        "total": total,
        "non_empty": non_empty,
        "active_page": "biz_overview",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "业务数据总览",
        "page_icon": "fa-clipboard-list",
        "link_base": "/biz",
    })


@router.get("/biz/{table_key}", response_class=HTMLResponse)
async def biz_table_detail(
    table_key: str,
    request: Request,
    params: PaginationParams = Depends(get_pagination),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_biz_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    display_columns = get_display_columns(conn, table_name)

    total = get_table_count(conn, table_name, params.search)
    rows = get_table_rows(
        conn, table_name, columns,
        params.page, params.page_size, params.search,
        params.sort_by, params.sort_order,
    )
    rows = apply_enum_display(rows, table_name)

    return templates.TemplateResponse("base_data/table_detail.html", {
        "request": request,
        "table_key": table_key,
        "table_name": table_name,
        "table_label": table_info["label"],
        "columns": display_columns,
        "rows": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": calc_total_pages(total, params.page_size),
        "search": params.search,
        "sort_by": params.sort_by,
        "sort_order": params.sort_order,
        "active_page": table_key,
        "sidebar_menu": SIDEBAR_MENU,
        "api_base": "/api/biz",
        "back_url": "/biz",
    })


@router.get("/alg", response_class=HTMLResponse)
async def alg_overview(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_alg_table_counts(conn)
    total = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return templates.TemplateResponse("base_data/overview.html", {
        "request": request,
        "tables": tables,
        "total": total,
        "non_empty": non_empty,
        "active_page": "alg_overview",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "算法输入总览",
        "page_icon": "fa-calculator",
        "link_base": "/alg",
    })


@router.get("/alg/{table_key}", response_class=HTMLResponse)
async def alg_table_detail(
    table_key: str,
    request: Request,
    params: PaginationParams = Depends(get_pagination),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_alg_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    display_columns = get_display_columns(conn, table_name)

    total = get_table_count(conn, table_name, params.search)
    rows = get_table_rows(
        conn, table_name, columns,
        params.page, params.page_size, params.search,
        params.sort_by, params.sort_order,
    )
    rows = apply_enum_display(rows, table_name)

    return templates.TemplateResponse("base_data/table_detail.html", {
        "request": request,
        "table_key": table_key,
        "table_name": table_name,
        "table_label": table_info["label"],
        "columns": display_columns,
        "rows": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": calc_total_pages(total, params.page_size),
        "search": params.search,
        "sort_by": params.sort_by,
        "sort_order": params.sort_order,
        "active_page": table_key,
        "sidebar_menu": SIDEBAR_MENU,
        "api_base": "/api/alg",
        "back_url": "/alg",
    })


@router.get("/res", response_class=HTMLResponse)
async def res_overview(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_result_view_counts(conn)
    total = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return templates.TemplateResponse("base_data/overview.html", {
        "request": request,
        "tables": tables,
        "total": total,
        "non_empty": non_empty,
        "active_page": "res_overview",
        "sidebar_menu": SIDEBAR_MENU,
        "page_title": "输出结果总览",
        "page_icon": "fa-chart-bar",
        "link_base": "/res",
    })


@router.get("/res/{view_key}", response_class=HTMLResponse)
async def res_view_detail(
    view_key: str,
    request: Request,
    params: PaginationParams = Depends(get_pagination),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    view_info = validate_result_view(view_key)
    if not view_info:
        raise HTTPException(status_code=404, detail=f"结果视图 '{view_key}' 不存在")

    view_name = view_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(view_name, [])
    display_columns = get_display_columns(conn, view_name)

    total = get_table_count(conn, view_name, params.search)
    rows = get_table_rows(
        conn, view_name, columns,
        params.page, params.page_size, params.search,
        params.sort_by, params.sort_order,
    )
    rows = apply_enum_display(rows, view_name)

    return templates.TemplateResponse("base_data/table_detail.html", {
        "request": request,
        "table_key": view_key,
        "table_name": view_name,
        "table_label": view_info["label"],
        "columns": display_columns,
        "rows": rows,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": calc_total_pages(total, params.page_size),
        "search": params.search,
        "sort_by": params.sort_by,
        "sort_order": params.sort_order,
        "active_page": view_key,
        "sidebar_menu": SIDEBAR_MENU,
        "api_base": "/api/res",
        "back_url": "/res",
    })
