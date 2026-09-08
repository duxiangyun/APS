"""主数据在线编辑服务（P0 功能 1-9）与排产参数在线配置（12/44）

设计约定：
- 算法输入视图（alg_sheet_*）直接读 core_* 层，编辑 core 表即对算法生效；
- 重跑 ETL（etl_stg_to_core.py）会以 Excel 数据覆盖手工编辑，页面需提示；
- 仅白名单表可编辑，字段类型/必填在此声明，UPDATE 时主键列不可修改；
- global_params 参数按组配置，数值/开关类型校验后 UPDATE，不新增行。
"""
import sqlite3

# ---------------------------------------------------------------------------
# 可编辑表白名单：P0 主数据 1-9 + 订单/采购限制
# 列类型: text | int | number | select(select 需 options=[[value, label], ...])
# pk: 主键列名列表（复合主键为多列）；auto: 自增列，INSERT 时不填
# ---------------------------------------------------------------------------
EDITABLE_TABLES = {
    # 1 物料主数据
    "core_md_material": {
        "label": "物料主数据", "pk": ["material_code"], "insert": True,
        "columns": [
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "material_name", "zh": "物料名称", "type": "text"},
            {"name": "category", "zh": "物料分类", "type": "select",
             "options": [["PRODUCT", "产品"], ["SEMI", "自制件"], ["RAW", "原材料"]]},
            {"name": "unit", "zh": "单位", "type": "text"},
            {"name": "initial_inventory", "zh": "初始库存", "type": "number"},
            {"name": "target_end_inventory", "zh": "目标期末库存", "type": "number"},
            {"name": "min_inventory", "zh": "最低库存", "type": "number"},
            {"name": "max_inventory", "zh": "最高库存", "type": "number"},
            {"name": "holding_cost_rate", "zh": "库存成本费率", "type": "number"},
        ],
    },
    # 1a 产品扩展
    "core_md_product_ext": {
        "label": "产品扩展属性", "pk": ["material_code"], "insert": True,
        "columns": [
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "standard_cost", "zh": "标准成本", "type": "number"},
            {"name": "standard_price", "zh": "标准售价", "type": "number"},
            {"name": "assembly_lead_time", "zh": "装配提前期", "type": "int"},
            {"name": "sales_status", "zh": "销售状态", "type": "select",
             "options": [["ACTIVE", "启用"], ["INACTIVE", "停用"], ["DISCONTINUED", "停产"]]},
        ],
    },
    # 1b 自制件扩展（含外协单价 → 功能 8）
    "core_md_semi_ext": {
        "label": "自制件扩展属性", "pk": ["material_code"], "insert": True,
        "columns": [
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "is_virtual", "zh": "是否虚拟件", "type": "select", "int_value": True,
             "options": [[0, "否"], [1, "是"]]},
            {"name": "manufacturing_lead_time", "zh": "制造提前期", "type": "int"},
            {"name": "default_routing_id", "zh": "默认工艺路线", "type": "int"},
            {"name": "scrap_rate", "zh": "废品率", "type": "number"},
        ],
    },
    # 6 原材料管理
    "core_md_raw_ext": {
        "label": "原材料扩展属性", "pk": ["material_code"], "insert": True,
        "columns": [
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "purchase_cost", "zh": "采购单价", "type": "number"},
            {"name": "purchase_lead_time", "zh": "采购提前期", "type": "int"},
            {"name": "preferred_supplier", "zh": "首选供应商", "type": "text"},
            {"name": "moq", "zh": "最小起订量", "type": "int"},
        ],
    },
    # 4 设备 / 5 工装
    "core_md_resource": {
        "label": "设备与工装台账", "pk": ["resource_code"], "insert": True,
        "columns": [
            {"name": "resource_code", "zh": "资源代码", "type": "text", "required": True},
            {"name": "resource_name", "zh": "资源名称", "type": "text"},
            {"name": "resource_type", "zh": "资源类型", "type": "select", "required": True,
             "options": [["EQUIPMENT", "设备"], ["FIXTURE", "工装"]]},
            {"name": "line_code", "zh": "所属产线", "type": "text"},
            {"name": "quantity", "zh": "数量", "type": "int"},
            {"name": "unit_cost", "zh": "单位成本", "type": "number"},
            {"name": "utilization_rate", "zh": "利用率", "type": "number"},
            {"name": "overtime_rate", "zh": "加班率上限", "type": "number"},
            {"name": "overtime_cost_multiplier", "zh": "加班成本系数", "type": "number"},
        ],
    },
    "core_md_line": {
        "label": "产线主数据", "pk": ["line_code"], "insert": True,
        "columns": [
            {"name": "line_code", "zh": "产线代码", "type": "text", "required": True},
            {"name": "line_name", "zh": "产线名称", "type": "text"},
            {"name": "line_type", "zh": "产线类型", "type": "select",
             "options": [["production", "生产线"], ["machining", "机加线"],
                         ["assembly", "装配线"], ["welding", "焊接线"], ["paint", "涂装线"]]},
        ],
    },
    "core_md_operation": {
        "label": "工序主数据", "pk": ["operation_code"], "insert": True,
        "columns": [
            {"name": "operation_code", "zh": "工序代码", "type": "text", "required": True},
            {"name": "operation_name", "zh": "工序名称", "type": "text"},
        ],
    },
    # 9 替代关系
    "core_md_alt_rule": {
        "label": "替代关系", "pk": ["rule_id"], "insert": True,
        "columns": [
            {"name": "rule_id", "zh": "规则ID", "type": "int", "auto": True},
            {"name": "alt_type", "zh": "替代类型编号", "type": "int", "required": True},
            {"name": "alt_type_name", "zh": "替代类型", "type": "select",
             "options": [["产品替代", "产品替代"], ["自制件替代", "自制件替代"],
                         ["原材料替代", "原材料替代"]]},
            {"name": "from_material_code", "zh": "被替代物料", "type": "text", "required": True},
            {"name": "from_quantity", "zh": "被替代数量", "type": "number"},
            {"name": "to_material_code", "zh": "替代物料", "type": "text", "required": True},
            {"name": "to_quantity", "zh": "替代数量", "type": "number"},
            {"name": "ratio", "zh": "替代比例", "type": "number"},
            {"name": "is_batch", "zh": "整批替代", "type": "select", "int_value": True,
             "options": [[0, "否"], [1, "是"]]},
            {"name": "is_active", "zh": "是否启用", "type": "select", "int_value": True,
             "options": [[0, "停用"], [1, "启用"]]},
        ],
    },
    # 2 BOM
    "core_biz_bom": {
        "label": "BOM 清单", "pk": ["id"], "insert": True,
        "columns": [
            {"name": "id", "zh": "ID", "type": "int", "auto": True},
            {"name": "parent_material_code", "zh": "父物料", "type": "text", "required": True},
            {"name": "child_material_code", "zh": "子物料", "type": "text", "required": True},
            {"name": "quantity", "zh": "单位用量", "type": "number"},
            {"name": "bom_level", "zh": "BOM层级", "type": "int"},
        ],
    },
    # 7 在制品
    "core_biz_wip": {
        "label": "在制品", "pk": ["id"], "insert": True,
        "columns": [
            {"name": "id", "zh": "ID", "type": "int", "auto": True},
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "quantity", "zh": "数量", "type": "number", "required": True},
            {"name": "completed_stages", "zh": "已完成阶段数", "type": "int"},
        ],
    },
    # 8 外协
    "core_md_outsource": {
        "label": "外协价格表", "pk": ["material_code"], "insert": True,
        "columns": [
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "unit_price", "zh": "外协单价", "type": "number"},
        ],
    },
    "core_md_purchase_limit": {
        "label": "采购限制", "pk": ["material_code"], "insert": True,
        "columns": [
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "note", "zh": "限制说明", "type": "text"},
        ],
    },
    # 订单（排产输入核心）
    "core_biz_demand_order": {
        "label": "需求订单", "pk": ["order_id"], "insert": True,
        "columns": [
            {"name": "order_id", "zh": "订单编号", "type": "int", "required": True},
            {"name": "product_code", "zh": "产品代码", "type": "text", "required": True},
            {"name": "price", "zh": "订单单价", "type": "number"},
            {"name": "quantity", "zh": "订单数量", "type": "number", "required": True},
            {"name": "due_period", "zh": "交期(期)", "type": "int", "required": True},
            {"name": "priority_level", "zh": "订单等级", "type": "int"},
            {"name": "max_delay_allowed", "zh": "最大允许延期", "type": "int"},
            {"name": "delay_penalty", "zh": "延期罚金率", "type": "number"},
        ],
    },
    # 3 工艺路线（header / step / 时偏移）
    "core_biz_routing_header": {
        "label": "工艺路线头", "pk": ["routing_id"], "insert": True,
        "columns": [
            {"name": "routing_id", "zh": "路线ID", "type": "int", "auto": True},
            {"name": "material_code", "zh": "物料代码", "type": "text", "required": True},
            {"name": "alt_route_id", "zh": "多工艺编号", "type": "int"},
            {"name": "total_lead_time", "zh": "最大加工周期", "type": "int", "required": True},
            {"name": "is_default", "zh": "默认路线", "type": "select", "int_value": True,
             "options": [[0, "否"], [1, "是"]]},
            {"name": "is_active", "zh": "是否启用", "type": "select", "int_value": True,
             "options": [[0, "停用"], [1, "启用"]]},
        ],
    },
    "core_biz_routing_step": {
        "label": "工艺路线工序", "pk": ["step_id"], "insert": True,
        "columns": [
            {"name": "step_id", "zh": "工序ID", "type": "int", "auto": True},
            {"name": "routing_id", "zh": "路线ID", "type": "int", "required": True},
            {"name": "step_order", "zh": "工序顺序", "type": "int", "required": True},
            {"name": "operation_code", "zh": "工序代码", "type": "text", "required": True},
            {"name": "equipment_code", "zh": "设备代码", "type": "text", "required": True},
            {"name": "production_line_code", "zh": "生产线", "type": "text"},
            {"name": "fixture_code", "zh": "工装代码", "type": "text"},
            {"name": "fixture_quantity", "zh": "工装数量", "type": "int"},
            {"name": "max_lead_time", "zh": "工序加工周期", "type": "int", "required": True},
        ],
    },
    "core_biz_step_time_offset": {
        "label": "工序时偏移", "pk": ["step_id", "offset_index"], "insert": True,
        "columns": [
            {"name": "step_id", "zh": "工序ID", "type": "int", "required": True},
            {"name": "offset_index", "zh": "偏移序号", "type": "int", "required": True},
            {"name": "duration", "zh": "加工时长", "type": "number"},
        ],
    },
}


def get_editable_config(table_name: str) -> dict | None:
    """返回可直接 JSON 序列化的编辑配置（含操作所需全部信息）"""
    meta = EDITABLE_TABLES.get(table_name)
    if not meta:
        return None
    return {
        "label": meta["label"],
        "pk": meta["pk"],
        "insert": meta.get("insert", False),
        "columns": meta["columns"],
    }


def _clean_value(col: dict, value, for_insert: bool):
    """按列定义清洗/校验单个值，返回入库值"""
    v = "" if value is None else str(value).strip()
    if v == "":
        if for_insert and col.get("required"):
            raise ValueError(f"字段「{col['zh']}」为必填项")
        return None
    t = col["type"]
    try:
        if t == "int":
            return int(float(v))
        if t == "number":
            return float(v)
    except ValueError:
        raise ValueError(f"字段「{col['zh']}」需为数值（输入: {v}）")
    if t == "select":
        opts = [str(o[0]) for o in col.get("options", [])]
        if v not in opts:
            raise ValueError(f"字段「{col['zh']}」的取值需为: {'/'.join(opts)}")
        return int(float(v)) if col.get("int_value") else v
    return v


def _check_fields(meta: dict, fields: dict, for_insert: bool) -> dict:
    cols = {c["name"]: c for c in meta["columns"]}
    unknown = set(fields) - set(cols)
    if unknown:
        raise ValueError(f"不支持的字段: {', '.join(sorted(unknown))}")
    clean = {}
    for name, value in fields.items():
        col = cols[name]
        if not for_insert and col.get("auto"):
            continue  # 自增列不允许 UPDATE
        clean[name] = _clean_value(col, value, for_insert)
    return clean


def _where_pk(meta: dict, pk_values: dict):
    pk_cols = meta["pk"]
    missing = [k for k in pk_cols if k not in pk_values]
    if missing:
        raise ValueError(f"缺少主键字段: {', '.join(missing)}")
    conds, args = [], []
    for k in pk_cols:
        col = next(c for c in meta["columns"] if c["name"] == k)
        conds.append(f"{k} = ?")
        args.append(_clean_value(col, pk_values[k], False))
    return " AND ".join(conds), args


def get_row_raw(conn: sqlite3.Connection, table_name: str, pk_values: dict) -> dict | None:
    """取原始行数据（未经枚举显示转换），供编辑表单回显"""
    meta = EDITABLE_TABLES.get(table_name)
    if not meta:
        return None
    where, args = _where_pk(meta, pk_values)
    row = conn.execute(f"SELECT * FROM {table_name} WHERE {where} LIMIT 1", args).fetchone()
    return dict(row) if row else None


def update_row(conn: sqlite3.Connection, table_name: str, pk_values: dict, fields: dict) -> dict:
    meta = EDITABLE_TABLES.get(table_name)
    if not meta:
        raise ValueError(f"表 {table_name} 不可编辑")
    clean = _check_fields(meta, fields, for_insert=False)
    if not clean:
        return {"ok": True, "message": "无变更"}
    where, args = _where_pk(meta, pk_values)
    sets = ", ".join(f"{k} = ?" for k in clean)
    try:
        cur = conn.execute(f"UPDATE {table_name} SET {sets} WHERE {where}",
                           list(clean.values()) + args)
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return {"ok": False, "message": f"数据约束冲突: {e}"}
    if cur.rowcount == 0:
        return {"ok": False, "message": "未找到对应记录（可能已被删除）"}
    return {"ok": True, "message": "已保存"}


def create_row(conn: sqlite3.Connection, table_name: str, fields: dict) -> dict:
    meta = EDITABLE_TABLES.get(table_name)
    if not meta:
        raise ValueError(f"表 {table_name} 不可编辑")
    if not meta.get("insert"):
        raise ValueError(f"表 {table_name} 不支持新增")
    clean = _check_fields(meta, fields, for_insert=True)
    cols = list(clean.keys())
    phs = ", ".join("?" for _ in cols)
    try:
        conn.execute(f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({phs})",
                     list(clean.values()))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return {"ok": False, "message": f"新增失败（主键重复或引用不存在）: {e}"}
    return {"ok": True, "message": "已新增"}


def delete_row(conn: sqlite3.Connection, table_name: str, pk_values: dict) -> dict:
    meta = EDITABLE_TABLES.get(table_name)
    if not meta:
        raise ValueError(f"表 {table_name} 不可编辑")
    where, args = _where_pk(meta, pk_values)
    try:
        cur = conn.execute(f"DELETE FROM {table_name} WHERE {where}", args)
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return {"ok": False, "message": f"删除失败（被其他数据引用）: {e}"}
    if cur.rowcount == 0:
        return {"ok": False, "message": "未找到对应记录"}
    return {"ok": True, "message": "已删除"}


# ---------------------------------------------------------------------------
# 排产参数在线配置（12/44）：core_biz_global_params 按组编辑
# ---------------------------------------------------------------------------
GLOBAL_PARAM_GROUPS = [
    {"label": "计划参数", "icon": "fa-calendar-alt", "keys": [
        "PLAN_HORIZON", "SHIFT_DURATION_MINUTES", "SHIFTS_PER_PERIOD",
        "ORDER_PRIORITY_LEVELS", "MAX_ALTERNATE_ROUTES", "MAX_PROCESSING_CYCLE",
        "DEMAND_RATE", "MAX_DELAY_ALLOWED",
    ]},
    {"label": "数据表开关", "icon": "fa-toggle-on", "keys": [
        "LOAD_FLAG_FIXTURE", "LOAD_FLAG_OUTSOURCE", "LOAD_FLAG_PURCHASE_LIMIT",
        "LOAD_FLAG_ALTERNATIVE", "LOAD_FLAG_WIP",
    ]},
    {"label": "统计参数（记录数校验用）", "icon": "fa-list-ol", "keys": [
        "STAT_BOM_RECORDS", "STAT_ROUTING_RECORDS", "STAT_ORDER_RECORDS",
        "NUM_FACTORIES", "STAT_NUM_EQUIPMENTS", "STAT_NUM_FIXTURES",
        "STAT_NUM_PRODUCTS", "STAT_NUM_SEMIS", "STAT_NUM_RAWS",
    ]},
    {"label": "求解参数", "icon": "fa-sliders-h", "keys": [
        "SOLVE_MODE", "SOLVE_MIPGAP", "SOLVE_TIME_LIMIT",
    ]},
    {"label": "目标权重", "icon": "fa-balance-scale", "keys": [
        "W_SALES", "W_DELAY", "W_PURCHASE", "W_PROCESS", "W_INVENTORY",
    ]},
]
# 参数值类型（用于校验）：缺省视为正整数
_PARAM_INT = {
    "PLAN_HORIZON", "SHIFT_DURATION_MINUTES", "SHIFTS_PER_PERIOD",
    "ORDER_PRIORITY_LEVELS", "MAX_ALTERNATE_ROUTES", "MAX_PROCESSING_CYCLE",
    "MAX_DELAY_ALLOWED", "LOAD_FLAG_FIXTURE", "LOAD_FLAG_OUTSOURCE",
    "LOAD_FLAG_PURCHASE_LIMIT", "LOAD_FLAG_ALTERNATIVE", "LOAD_FLAG_WIP",
    "STAT_BOM_RECORDS", "STAT_ROUTING_RECORDS", "STAT_ORDER_RECORDS",
    "NUM_FACTORIES", "STAT_NUM_EQUIPMENTS", "STAT_NUM_FIXTURES",
    "STAT_NUM_PRODUCTS", "STAT_NUM_SEMIS", "STAT_NUM_RAWS",
}
_PARAM_NUMBER = {"DEMAND_RATE", "SOLVE_MIPGAP", "SOLVE_TIME_LIMIT",
                 "W_SALES", "W_DELAY", "W_PURCHASE", "W_PROCESS", "W_INVENTORY"}
_PARAM_SELECT = {
    "SOLVE_MODE": [["auto", "auto（自动选择）"], ["milp", "milp（强制整数规划）"]],
}
_PARAM_HINTS = {
    "PLAN_HORIZON": "计划期长度（期）。注意：结果视图按 12 期 PIVOT，修改后需同步调整视图",
    "DEMAND_RATE": "需求率（可为小数）",
    "SOLVE_MIPGAP": "MILP 收敛精度，0~1 之间",
    "SOLVE_TIME_LIMIT": "求解时间限制（秒），0=不限制",
    "SOLVE_MODE": "auto=按数据自动选择，milp=强制整数规划",
    "W_SALES": "销售收入权重，≥0，默认 1.0；调大倾向多产多销",
    "W_DELAY": "延迟交付罚金权重，≥0，默认 1.0；调大倾向保交期",
    "W_PURCHASE": "采购成本权重（原材料+外协），≥0，默认 1.0；调大倾向少采购/少外协",
    "W_PROCESS": "加工成本权重（工艺+模具，含加班），≥0，默认 1.0；调大倾向少占用产能",
    "W_INVENTORY": "库存成本权重（产品/自制件/原材料），≥0，默认 1.0；调大倾向低库存",
}


def get_global_params(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT param_key, param_value, description FROM core_biz_global_params ORDER BY param_key").fetchall()
    by_key = {r["param_key"]: r for r in rows}
    groups = []
    covered = set()
    for g in GLOBAL_PARAM_GROUPS:
        items = []
        for k in g["keys"]:
            r = by_key.get(k)
            if not r:
                continue
            covered.add(k)
            items.append({
                "key": k, "value": r["param_value"],
                "description": r["description"] or "",
                "hint": _PARAM_HINTS.get(k, ""),
                "type": ("select" if k in _PARAM_SELECT else
                         "number" if k in _PARAM_NUMBER else "int"),
                "options": _PARAM_SELECT.get(k, []),
            })
        groups.append({"label": g["label"], "icon": g["icon"], "items": items})
    # 兜底：未分组的参数也展示，避免遗漏
    rest = [{"key": k, "value": r["param_value"], "description": r["description"] or "",
             "hint": "", "type": "text", "options": []}
            for k, r in by_key.items() if k not in covered]
    if rest:
        groups.append({"label": "其他参数", "icon": "fa-ellipsis-h", "items": rest})
    return groups


def validate_global_params(payload: dict) -> tuple:
    """校验参数键与值，返回 (规范化后的 {key: value}, 错误消息)。错误消息为空表示通过。"""
    conn = sqlite3.connect(_db_path())
    try:
        known = {r[0] for r in conn.execute("SELECT param_key FROM core_biz_global_params").fetchall()}
    finally:
        conn.close()
    updates = {}
    for k, v in payload.items():
        if k not in known:
            return {}, f"未知参数: {k}"
        s = str(v).strip()
        if k in _PARAM_SELECT:
            allowed = [str(o[0]) for o in _PARAM_SELECT[k]]
            if s not in allowed:
                return {}, f"{k} 仅支持: {'/'.join(allowed)}"
        if k in _PARAM_INT:
            try:
                iv = int(float(s))
                assert iv >= 0
            except (ValueError, AssertionError):
                return {}, f"{k} 需为非负整数"
            if k.startswith("LOAD_FLAG") and iv not in (0, 1):
                return {}, f"{k} 开关仅支持 0/1"
            s = str(iv)
        elif k in _PARAM_NUMBER:
            try:
                nv = float(s)
                assert nv >= 0
                if k == "SOLVE_MIPGAP":
                    assert nv <= 1
            except (ValueError, AssertionError):
                return {}, f"{k} 需为合法数值（非负）"
            s = repr(nv)
        updates[k] = s
    return updates, ""


def update_global_params(payload: dict) -> dict:
    if not isinstance(payload, dict) or not payload:
        return {"updated": 0, "message": "无有效参数"}
    # 求解运行期间禁止修改：What-if 沙盒依赖"覆盖 → 求解 → 恢复快照"的完整周期
    from app.services.analysis_service import is_solve_running
    if is_solve_running():
        return {"updated": 0, "message": "排产运行中，暂不能修改参数，请稍后再试"}
    updates, err = validate_global_params(payload)
    if err:
        return {"updated": 0, "message": err}
    conn = sqlite3.connect(_db_path())
    try:
        conn.executemany("UPDATE core_biz_global_params SET param_value = ? WHERE param_key = ?",
                         [(v, k) for k, v in updates.items()])
        conn.commit()
        return {"updated": len(updates), "message": "已保存，下次排产生效"}
    finally:
        conn.close()


def _db_path() -> str:
    from app.services.analysis_service import _PROJECT_ROOT
    return str(_PROJECT_ROOT / "data" / "db" / "aps_or.db")
