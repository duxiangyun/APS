from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import quote
import sqlite3

from app.dependencies import get_db_conn, get_pagination, PaginationParams
from app.schemas import TableDataResponse, TableOverviewResponse, TableOverviewItem
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
    export_table_csv,
    calc_total_pages,
)
from app.services.meta_service import get_display_columns, apply_enum_display
from app.services.dashboard_service import get_dashboard
from app.constants import COLUMN_DISPLAY_ORDER

router = APIRouter(prefix="/api/base-data", tags=["base-data-api"])
stg_router = APIRouter(prefix="/api/stg", tags=["stg-api"])
biz_router = APIRouter(prefix="/api/biz", tags=["biz-api"])
alg_router = APIRouter(prefix="/api/alg", tags=["alg-api"])
res_router = APIRouter(prefix="/api/res", tags=["res-api"])
dash_router = APIRouter(prefix="/api/dashboard", tags=["dashboard-api"])


@dash_router.get("")
async def dashboard_data(conn: sqlite3.Connection = Depends(get_db_conn)):
    """工作台聚合数据：KPI 指标 / 异常告警 / 设备负荷矩阵"""
    return get_dashboard(conn)


@router.get("", response_model=TableOverviewResponse)
async def overview(conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_table_counts(conn)
    total_records = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return TableOverviewResponse(
        tables=[TableOverviewItem(**t) for t in tables],
        total_records=total_records,
        non_empty_tables=non_empty,
    )


@router.get("/{table_key}", response_model=TableDataResponse)
async def table_data(
    table_key: str,
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

    return TableDataResponse(
        table_key=table_key,
        table_name=table_name,
        table_label=table_info["label"],
        columns=display_columns,
        rows=rows,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=calc_total_pages(total, params.page_size),
    )


@router.get("/{table_key}/export.csv")
async def export_csv(
    table_key: str,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    csv_content = export_table_csv(conn, table_name, columns, search, sort_by, sort_order)
    filename = quote(f'{table_info["label"]}.csv')

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@stg_router.get("", response_model=TableOverviewResponse)
async def stg_overview(conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_stg_table_counts(conn)
    total_records = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return TableOverviewResponse(
        tables=[TableOverviewItem(**t) for t in tables],
        total_records=total_records,
        non_empty_tables=non_empty,
    )


@stg_router.get("/{table_key}", response_model=TableDataResponse)
async def stg_table_data(
    table_key: str,
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

    return TableDataResponse(
        table_key=table_key,
        table_name=table_name,
        table_label=table_info["label"],
        columns=display_columns,
        rows=rows,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=calc_total_pages(total, params.page_size),
    )


@stg_router.get("/{table_key}/export.csv")
async def stg_export_csv(
    table_key: str,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_stg_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    csv_content = export_table_csv(conn, table_name, columns, search, sort_by, sort_order)
    filename = quote(f'{table_info["label"]}.csv')

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@biz_router.get("", response_model=TableOverviewResponse)
async def biz_overview(conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_biz_table_counts(conn)
    total_records = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return TableOverviewResponse(
        tables=[TableOverviewItem(**t) for t in tables],
        total_records=total_records,
        non_empty_tables=non_empty,
    )


@biz_router.get("/{table_key}", response_model=TableDataResponse)
async def biz_table_data(
    table_key: str,
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

    return TableDataResponse(
        table_key=table_key,
        table_name=table_name,
        table_label=table_info["label"],
        columns=display_columns,
        rows=rows,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=calc_total_pages(total, params.page_size),
    )


@biz_router.get("/{table_key}/export.csv")
async def biz_export_csv(
    table_key: str,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_biz_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    csv_content = export_table_csv(conn, table_name, columns, search, sort_by, sort_order)
    filename = quote(f'{table_info["label"]}.csv')

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@biz_router.get("/bom/tree")
async def bom_tree(conn: sqlite3.Connection = Depends(get_db_conn)):
    """BOM 树形数据：返回嵌套树结构 + 平铺列表，供前端三种视图渲染。

    树结构按 bom_level 递归，顶层为产品（bom_level=1 的父物料）。
    每节点含 material_code/material_name/category/quantity/level/children。
    """
    rows = conn.execute(
        "SELECT b.id, b.parent_material_code, b.child_material_code, b.quantity, b.bom_level, "
        "pm.material_name AS parent_name, pm.category AS parent_cat, "
        "cm.material_name AS child_name, cm.category AS child_cat "
        "FROM core_biz_bom b "
        "LEFT JOIN core_md_material pm ON pm.material_code = b.parent_material_code "
        "LEFT JOIN core_md_material cm ON cm.material_code = b.child_material_code "
        "ORDER BY b.bom_level, b.parent_material_code, b.child_material_code"
    ).fetchall()

    # 找顶层父节点（在 parent 列出现但不在 child 列出现的物料）
    parent_codes = {r["parent_material_code"] for r in rows}
    child_codes = {r["child_material_code"] for r in rows}
    top_codes = parent_codes - child_codes  # 顶层产品

    # 物料名称/分类缓存
    name_map = {}
    cat_map = {}
    for r in rows:
        name_map[r["parent_material_code"]] = r["parent_name"] or ""
        name_map[r["child_material_code"]] = r["child_name"] or ""
        cat_map[r["parent_material_code"]] = r["parent_cat"] or ""
        cat_map[r["child_material_code"]] = r["child_cat"] or ""

    # 按 parent 分组子节点
    children_map = {}
    for r in rows:
        children_map.setdefault(r["parent_material_code"], []).append({
            "code": r["child_material_code"],
            "name": r["child_name"] or "",
            "category": r["child_cat"] or "",
            "quantity": r["quantity"],
            "level": r["bom_level"],
        })

    def build_node(code, level, quantity=1):
        kids = children_map.get(code, [])
        return {
            "code": code,
            "name": name_map.get(code, ""),
            "category": cat_map.get(code, ""),
            "level": level,
            "quantity": quantity,  # 相对父节点的单位用量（顶层节点为1）
            "children": [build_node(k["code"], level + 1, k["quantity"]) for k in kids],
        }

    tree = [build_node(c, 1, 1) for c in sorted(top_codes)]

    # 平铺列表（供表格视图）
    flat = [
        {
            "id": r["id"],
            "parent_code": r["parent_material_code"],
            "parent_name": r["parent_name"] or "",
            "child_code": r["child_material_code"],
            "child_name": r["child_name"] or "",
            "child_category": r["child_cat"] or "",
            "quantity": r["quantity"],
            "bom_level": r["bom_level"],
        }
        for r in rows
    ]

    return {"tree": tree, "flat": flat, "total": len(flat)}


@alg_router.get("", response_model=TableOverviewResponse)
async def alg_overview(conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_alg_table_counts(conn)
    total_records = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return TableOverviewResponse(
        tables=[TableOverviewItem(**t) for t in tables],
        total_records=total_records,
        non_empty_tables=non_empty,
    )


@alg_router.get("/{table_key}", response_model=TableDataResponse)
async def alg_table_data(
    table_key: str,
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

    return TableDataResponse(
        table_key=table_key,
        table_name=table_name,
        table_label=table_info["label"],
        columns=display_columns,
        rows=rows,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=calc_total_pages(total, params.page_size),
    )


@alg_router.get("/{table_key}/export.csv")
async def alg_export_csv(
    table_key: str,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    table_info = validate_alg_table(table_key)
    if not table_info:
        raise HTTPException(status_code=404, detail=f"表 '{table_key}' 不存在")

    table_name = table_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(table_name, [])
    csv_content = export_table_csv(conn, table_name, columns, search, sort_by, sort_order)
    filename = quote(f'{table_info["label"]}.csv')

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@res_router.get("", response_model=TableOverviewResponse)
async def res_overview(conn: sqlite3.Connection = Depends(get_db_conn)):
    tables = get_all_result_view_counts(conn)
    total_records = sum(t["count"] for t in tables)
    non_empty = sum(1 for t in tables if t["count"] > 0)
    return TableOverviewResponse(
        tables=[TableOverviewItem(**t) for t in tables],
        total_records=total_records,
        non_empty_tables=non_empty,
    )


@res_router.get("/{view_key}", response_model=TableDataResponse)
async def res_view_data(
    view_key: str,
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

    return TableDataResponse(
        table_key=view_key,
        table_name=view_name,
        table_label=view_info["label"],
        columns=display_columns,
        rows=rows,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=calc_total_pages(total, params.page_size),
    )


@res_router.get("/{view_key}/export.csv")
async def res_export_csv(
    view_key: str,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    view_info = validate_result_view(view_key)
    if not view_info:
        raise HTTPException(status_code=404, detail=f"结果视图 '{view_key}' 不存在")

    view_name = view_info["name"]
    columns = COLUMN_DISPLAY_ORDER.get(view_name, [])
    csv_content = export_table_csv(conn, view_name, columns, search, sort_by, sort_order)
    filename = quote(f'{view_info["label"]}.csv')

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ---------------- 主数据在线编辑（P0 1-9）与排产参数（12/44） ----------------
from fastapi import Request
from app.services.edit_service import (
    EDITABLE_TABLES, get_row_raw, update_row, create_row, delete_row,
    get_global_params, update_global_params,
)

edit_router = APIRouter(prefix="/api/edit", tags=["edit-api"])
params_router = APIRouter(prefix="/api/params", tags=["params-api"])


def _edit_guard(table_name: str) -> dict:
    meta = EDITABLE_TABLES.get(table_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"表 '{table_name}' 不可编辑")
    return meta


async def _edit_body(request: Request) -> dict:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体需为 JSON 对象")
    return body


def _safe(fn, *args):
    """将字段校验的 ValueError 转为统一错误响应"""
    try:
        return fn(*args)
    except ValueError as e:
        return {"ok": False, "message": str(e)}


@edit_router.get("/{table_name}/row")
async def edit_get_row(table_name: str, pk: str, conn: sqlite3.Connection = Depends(get_db_conn)):
    """取原始行（未经枚举显示转换），pk 为 JSON 编码的主键键值对"""
    _edit_guard(table_name)
    import json as _json
    try:
        pk_values = _json.loads(pk)
    except ValueError:
        raise HTTPException(status_code=400, detail="pk 参数需为 JSON 对象")
    row = get_row_raw(conn, table_name, pk_values)
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


@edit_router.post("/{table_name}/update")
async def edit_update(table_name: str, request: Request,
                      conn: sqlite3.Connection = Depends(get_db_conn)):
    _edit_guard(table_name)
    body = await _edit_body(request)
    return _safe(update_row, conn, table_name, body.get("pk") or {}, body.get("fields") or {})


@edit_router.post("/{table_name}/create")
async def edit_create(table_name: str, request: Request,
                      conn: sqlite3.Connection = Depends(get_db_conn)):
    _edit_guard(table_name)
    body = await _edit_body(request)
    return _safe(create_row, conn, table_name, body or {})


@edit_router.post("/{table_name}/delete")
async def edit_delete(table_name: str, request: Request,
                      conn: sqlite3.Connection = Depends(get_db_conn)):
    _edit_guard(table_name)
    body = await _edit_body(request)
    return _safe(delete_row, conn, table_name, body.get("pk") or {})


@params_router.get("")
async def params_data(conn: sqlite3.Connection = Depends(get_db_conn)):
    return get_global_params(conn)


@params_router.post("")
async def params_update(request: Request):
    body = await _edit_body(request)
    return _safe(update_global_params, body)
