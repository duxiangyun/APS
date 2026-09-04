import sqlite3

from app.constants import COLUMN_MAPPINGS, COLUMN_DISPLAY_ORDER, ENUM_MAPPINGS, BOOL_MAPPINGS


def get_display_columns(conn: sqlite3.Connection, table_name: str) -> list[dict]:
    order = COLUMN_DISPLAY_ORDER.get(table_name, [])
    mapping = COLUMN_MAPPINGS.get(table_name, {})
    pragma_rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    type_map = {row["name"]: row["type"] for row in pragma_rows}

    columns = []
    for col in order:
        columns.append({
            "en": col,
            "zh": mapping.get(col, col),
            "type": type_map.get(col, "TEXT"),
        })
    return columns


def get_searchable_columns(table_name: str) -> list[str]:
    return COLUMN_DISPLAY_ORDER.get(table_name, [])


def apply_enum_display(rows: list[dict], table_name: str) -> list[dict]:
    enum_map = ENUM_MAPPINGS.get(table_name, {})
    bool_map = BOOL_MAPPINGS.get(table_name, {})

    if not enum_map and not bool_map:
        return rows

    result = []
    for row in rows:
        new_row = dict(row)
        for col, value_map in enum_map.items():
            if col in new_row and new_row[col] is not None:
                new_row[col] = value_map.get(str(new_row[col]), new_row[col])
        for col, value_map in bool_map.items():
            if col in new_row and new_row[col] is not None:
                try:
                    new_row[col] = value_map.get(int(new_row[col]), new_row[col])
                except (ValueError, TypeError):
                    pass
        result.append(new_row)
    return result


def reverse_search(search: str, table_name: str) -> list[str]:
    """将搜索词反向映射回原始值。搜'原材料'时同时匹配'raw'。"""
    if not search:
        return [search]

    candidates = [search]
    enum_map = ENUM_MAPPINGS.get(table_name, {})
    bool_map = BOOL_MAPPINGS.get(table_name, {})

    for col, value_map in enum_map.items():
        for raw_val, display_val in value_map.items():
            if search in display_val or display_val in search:
                candidates.append(str(raw_val))

    for col, value_map in bool_map.items():
        for raw_val, display_val in value_map.items():
            if search in display_val or display_val in search:
                candidates.append(str(raw_val))

    return list(dict.fromkeys(candidates))
