import sqlite3
from dataclasses import dataclass

from fastapi import Query

from config import DB_PATH


def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@dataclass
class PaginationParams:
    page: int
    page_size: int
    search: str
    sort_by: str
    sort_order: str


def get_pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: str = Query("", description="全表模糊搜索"),
    sort_by: str = Query("", description="排序字段（英文列名）"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
) -> PaginationParams:
    return PaginationParams(
        page=page,
        page_size=page_size,
        search=search.strip(),
        sort_by=sort_by.strip(),
        sort_order=sort_order,
    )
