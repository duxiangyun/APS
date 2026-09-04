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
from app.constants import COLUMN_DISPLAY_ORDER

router = APIRouter(prefix="/api/base-data", tags=["base-data-api"])
stg_router = APIRouter(prefix="/api/stg", tags=["stg-api"])
biz_router = APIRouter(prefix="/api/biz", tags=["biz-api"])
alg_router = APIRouter(prefix="/api/alg", tags=["alg-api"])
res_router = APIRouter(prefix="/api/res", tags=["res-api"])


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
