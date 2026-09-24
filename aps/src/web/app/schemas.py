from pydantic import BaseModel


class ColumnInfo(BaseModel):
    en: str
    zh: str
    type: str


class TableDataResponse(BaseModel):
    table_key: str
    table_name: str
    table_label: str
    columns: list[ColumnInfo]
    rows: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class TableOverviewItem(BaseModel):
    key: str
    name: str
    label: str
    count: int


class TableOverviewResponse(BaseModel):
    tables: list[TableOverviewItem]
    total_records: int
    non_empty_tables: int
