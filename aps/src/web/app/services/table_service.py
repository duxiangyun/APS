import csv
import io
import math
import sqlite3

from app.constants import (
    CORE_MD_TABLES,
    STG_TABLES,
    BIZ_TABLES,
    ALG_TABLES,
    RESULT_VIEWS,
    COLUMN_DISPLAY_ORDER,
    DEFAULT_SORT,
    get_table_by_key,
    get_stg_table_by_key,
    get_biz_table_by_key,
    get_alg_table_by_key,
    get_result_view_by_key,
)
from app.services.meta_service import get_searchable_columns, reverse_search
from config import DEFAULT_PAGE_SIZE


def validate_table(table_key: str) -> dict | None:
    return get_table_by_key(table_key)


def validate_stg_table(table_key: str) -> dict | None:
    return get_stg_table_by_key(table_key)


def validate_biz_table(table_key: str) -> dict | None:
    return get_biz_table_by_key(table_key)


def validate_alg_table(table_key: str) -> dict | None:
    return get_alg_table_by_key(table_key)


def validate_result_view(table_key: str) -> dict | None:
    return get_result_view_by_key(table_key)


def _q(col: str) -> str:
    """列名加双引号，避免数字列名（如 1~28）被解析为整数常量"""
    return f'"{col}"'


def get_table_count(
    conn: sqlite3.Connection,
    table_name: str,
    search: str = "",
) -> int:
    searchable_cols = get_searchable_columns(table_name)
    sql = f'SELECT COUNT(*) FROM "{table_name}"'
    params: list = []

    if search:
        search_terms = reverse_search(search, table_name)
        conditions = []
        for col in searchable_cols:
            for term in search_terms:
                conditions.append(f"{_q(col)} LIKE '%' || ? || '%'")
                params.append(term)
        if conditions:
            sql += " WHERE " + " OR ".join(conditions)

    return conn.execute(sql, params).fetchone()[0]


def get_table_rows(
    conn: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
) -> list[dict]:
    searchable_cols = get_searchable_columns(table_name)
    select_cols = ", ".join(_q(c) for c in columns)
    sql = f"SELECT {select_cols} FROM {_q(table_name)}"
    params: list = []

    if search:
        search_terms = reverse_search(search, table_name)
        conditions = []
        for col in searchable_cols:
            for term in search_terms:
                conditions.append(f"{_q(col)} LIKE '%' || ? || '%'")
                params.append(term)
        if conditions:
            sql += " WHERE " + " OR ".join(conditions)

    effective_sort = sort_by if sort_by in columns else DEFAULT_SORT.get(table_name, "id")
    sql += f" ORDER BY {_q(effective_sort)} {sort_order}"

    offset = (page - 1) * page_size
    sql += " LIMIT ? OFFSET ?"
    params.extend([page_size, offset])

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_all_table_counts(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for t in CORE_MD_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        result.append({**t, "count": count})
    return result


def get_all_stg_table_counts(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for t in STG_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        result.append({**t, "count": count})
    return result


def get_all_biz_table_counts(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for t in BIZ_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        result.append({**t, "count": count})
    return result


def get_all_alg_table_counts(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for t in ALG_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        result.append({**t, "count": count})
    return result


def get_all_result_view_counts(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for t in RESULT_VIEWS:
        count = conn.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        result.append({**t, "count": count})
    return result


def export_table_csv(
    conn: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
) -> str:
    from app.constants import COLUMN_MAPPINGS

    searchable_cols = get_searchable_columns(table_name)
    select_cols = ", ".join(_q(c) for c in columns)
    sql = f"SELECT {select_cols} FROM {_q(table_name)}"
    params: list = []

    if search:
        search_terms = reverse_search(search, table_name)
        conditions = []
        for col in searchable_cols:
            for term in search_terms:
                conditions.append(f"{_q(col)} LIKE '%' || ? || '%'")
                params.append(term)
        if conditions:
            sql += " WHERE " + " OR ".join(conditions)

    effective_sort = sort_by if sort_by in columns else DEFAULT_SORT.get(table_name, "id")
    sql += f" ORDER BY {_q(effective_sort)} {sort_order}"

    rows = conn.execute(sql, params).fetchall()

    mapping = COLUMN_MAPPINGS.get(table_name, {})
    header = [mapping.get(c, c) for c in columns]

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(header)
    for row in rows:
        writer.writerow([row[c] for c in columns])

    return output.getvalue()


def calc_total_pages(total: int, page_size: int) -> int:
    if page_size <= 0:
        return 1
    return math.ceil(total / page_size) if total > 0 else 1
