CORE_MD_TABLES = [
    {"key": "material", "name": "core_md_material", "label": "物料主数据"},
    {"key": "product_ext", "name": "core_md_product_ext", "label": "产品扩展"},
    {"key": "semi_ext", "name": "core_md_semi_ext", "label": "自制件扩展"},
    {"key": "raw_ext", "name": "core_md_raw_ext", "label": "原材料扩展"},
    {"key": "resource", "name": "core_md_resource", "label": "设备/工装"},
    {"key": "line", "name": "core_md_line", "label": "生产线"},
    {"key": "operation", "name": "core_md_operation", "label": "工序定义"},
    {"key": "alt_rule", "name": "core_md_alt_rule", "label": "替代规则"},
    {"key": "outsource", "name": "core_md_outsource", "label": "外协"},
    {"key": "purchase_limit", "name": "core_md_purchase_limit", "label": "采购限制"},
]

STG_TABLES = [
    {"key": "stg_system_config", "name": "stg_system_config", "label": "系统配置"},
    {"key": "stg_orders", "name": "stg_orders", "label": "订单表"},
    {"key": "stg_bom", "name": "stg_bom", "label": "BOM表"},
    {"key": "stg_routing", "name": "stg_routing", "label": "工艺路线"},
    {"key": "stg_equipment", "name": "stg_equipment", "label": "设备表"},
    {"key": "stg_fixture", "name": "stg_fixture", "label": "工装表"},
    {"key": "stg_product", "name": "stg_product", "label": "产品表"},
    {"key": "stg_semi", "name": "stg_semi", "label": "自制件"},
    {"key": "stg_raw", "name": "stg_raw", "label": "原材料表"},
    {"key": "stg_wip", "name": "stg_wip", "label": "在制品"},
    {"key": "stg_outsource", "name": "stg_outsource", "label": "外协"},
    {"key": "stg_purchase_limit", "name": "stg_purchase_limit", "label": "采购限制"},
    {"key": "stg_alternative", "name": "stg_alternative", "label": "替代关系"},
]

BIZ_TABLES = [
    {"key": "demand_order", "name": "core_biz_demand_order", "label": "订单需求"},
    {"key": "bom", "name": "core_biz_bom", "label": "BOM"},
    {"key": "wip", "name": "core_biz_wip", "label": "在制品"},
    {"key": "outsource_limit", "name": "core_biz_outsource_period_limit", "label": "外协周期限额"},
    {"key": "purchase_limit", "name": "core_biz_purchase_period_limit", "label": "采购周期限额"},
    {"key": "alt_limit", "name": "core_biz_alt_period_limit", "label": "替代周期限额"},
    {"key": "routing_header", "name": "core_biz_routing_header", "label": "工艺路线头表"},
    {"key": "routing_step", "name": "core_biz_routing_step", "label": "工艺步骤定义"},
    {"key": "step_time_offset", "name": "core_biz_step_time_offset", "label": "步骤工时偏移"},
    {"key": "global_params", "name": "core_biz_global_params", "label": "全局排产参数"},
]

ALG_TABLES = [
    {"key": "order_demand", "name": "alg_sheet_订单表", "label": "订单需求"},
    {"key": "product_info", "name": "alg_sheet_产品表", "label": "产品信息"},
    {"key": "raw_material", "name": "alg_sheet_原材料表", "label": "原材料信息"},
    {"key": "semi_info", "name": "alg_sheet_自制件", "label": "自制件信息"},
    {"key": "bom_info", "name": "alg_sheet_BOM", "label": "BOM信息"},
    {"key": "equipment_info", "name": "alg_sheet_设备表", "label": "设备表信息"},
    {"key": "fixture_info", "name": "alg_sheet_工装表", "label": "工装表信息"},
    {"key": "wip_info", "name": "alg_sheet_在制品", "label": "在制品信息"},
    {"key": "outsource_limit", "name": "alg_sheet_外协", "label": "外协信息"},
    {"key": "purchase_limit", "name": "alg_sheet_采购限制", "label": "采购限制"},
    {"key": "alt_rule", "name": "alg_sheet_替代关系", "label": "替代关系"},
    {"key": "routing", "name": "alg_sheet_工艺路线", "label": "工艺路线"},
    {"key": "global_params", "name": "alg_sheet_综合表", "label": "综合表"},
]


def _stg_period_mapping(base: dict, with_total: bool = True) -> dict:
    result = dict(base)
    for i in range(1, 29):
        result[f"period_{i:02d}"] = str(i)
    if with_total:
        result["total"] = "合计"
    return result


def _stg_period_columns(base: list, with_total: bool = True) -> list:
    result = list(base)
    for i in range(1, 29):
        result.append(f"period_{i:02d}")
    if with_total:
        result.append("total")
    return result


def _alg_outsource_mapping() -> dict:
    result = {"序号": "序号", "物料代码": "物料代码", "外协价格": "外协价格"}
    for i in range(1, 29):
        result[str(i)] = str(i)
    result["合计"] = "合计"
    return result


def _alg_outsource_columns() -> list:
    result = ["序号", "物料代码", "外协价格"]
    result.extend(str(i) for i in range(1, 29))
    result.append("合计")
    return result


def _alg_purchase_mapping() -> dict:
    result = {"序号": "序号", "原料代码": "原料代码", "物料名称": "物料名称"}
    for i in range(1, 29):
        result[str(i)] = str(i)
    result["合计"] = "合计"
    return result


def _alg_purchase_columns() -> list:
    result = ["序号", "原料代码", "物料名称"]
    result.extend(str(i) for i in range(1, 29))
    result.append("合计")
    return result


def _alg_alt_mapping() -> dict:
    result = {
        "序号": "序号",
        "替代类型编码": "替代类型编码",
        "替代类型名称": "替代类型名称",
        "替代物料一代码": "替代物料一代码",
        "数量一": "数量一",
        "替代物料二代码": "替代物料二代码",
        "数量二": "数量二",
        "比例": "比例",
        "整批": "整批",
    }
    for i in range(1, 29):
        result[str(i)] = str(i)
    return result


def _alg_alt_columns() -> list:
    result = [
        "序号", "替代类型编码", "替代类型名称", "替代物料一代码", "数量一",
        "替代物料二代码", "数量二", "比例", "整批",
    ]
    result.extend(str(i) for i in range(1, 29))
    return result


def _alg_routing_mapping() -> dict:
    result = {
        "序号": "序号",
        "物料代码": "物料代码",
        "物料名称": "物料名称",
        "多工艺": "多工艺",
        "设备代码": "设备代码",
        "生产线": "生产线",
        "工序": "工序",
        "工装代码": "工装代码",
        "工装数量": "工装数量",
        "MaxT": "MaxT",
    }
    for i in range(1, 4):
        result[str(i)] = str(i)
    return result


def _alg_routing_columns() -> list:
    result = [
        "序号", "物料代码", "物料名称", "多工艺", "设备代码", "生产线",
        "工序", "工装代码", "工装数量", "MaxT",
    ]
    result.extend(str(i) for i in range(1, 4))
    return result


COLUMN_MAPPINGS = {
    "core_md_material": {
        "material_code": "物料代码",
        "material_name": "物料名称",
        "category": "物料分类",
        "unit": "单位",
        "initial_inventory": "初始库存",
        "target_end_inventory": "目标期末库存",
        "min_inventory": "最小库存",
        "max_inventory": "最大库存",
        "holding_cost_rate": "库存成本率",
    },
    "core_md_product_ext": {
        "material_code": "物料代码",
        "standard_cost": "标准成本",
        "standard_price": "标准价格",
        "assembly_lead_time": "装配提前期",
        "sales_status": "销售状态",
    },
    "core_md_semi_ext": {
        "material_code": "物料代码",
        "is_virtual": "是否虚拟件",
        "manufacturing_lead_time": "制造提前期",
        "default_routing_id": "默认工艺路线",
        "scrap_rate": "废品率",
    },
    "core_md_raw_ext": {
        "material_code": "物料代码",
        "purchase_cost": "采购成本",
        "purchase_lead_time": "采购提前期",
        "preferred_supplier": "首选供应商",
        "moq": "最小起订量",
    },
    "core_md_resource": {
        "resource_code": "资源代码",
        "resource_name": "资源名称",
        "resource_type": "资源类型",
        "line_code": "产线代码",
        "quantity": "数量",
        "unit_cost": "单位成本",
        "utilization_rate": "利用率",
        "overtime_rate": "加班率",
        "overtime_cost_multiplier": "加班成本倍数",
    },
    "core_md_line": {
        "line_code": "生产线代码",
        "line_name": "生产线名称",
        "line_type": "生产线类型",
    },
    "core_md_operation": {
        "operation_code": "工序代码",
        "operation_name": "工序名称",
    },
    "core_md_alt_rule": {
        "rule_id": "替代关系编号",
        "alt_type": "替代类型编号",
        "alt_type_name": "替代类型",
        "from_material_code": "被替代物料",
        "from_quantity": "替代数量",
        "to_material_code": "替代物料",
        "to_quantity": "被替代数量",
        "ratio": "比例",
        "is_batch": "整批",
        "is_active": "启用状态",
    },
    "core_md_outsource": {
        "material_code": "物料代码",
        "unit_price": "外协单价",
    },
    "core_md_purchase_limit": {
        "material_code": "物料代码",
        "note": "采购限制说明",
    },
    # === 业务数据 (core_biz_) ===
    "core_biz_demand_order": {
        "order_id": "订单编号",
        "product_code": "产品代码",
        "price": "单价",
        "quantity": "需求数量",
        "due_period": "交期",
        "priority_level": "优先级",
        "max_delay_allowed": "最大允许延期",
        "delay_penalty": "延期罚金",
    },
    "core_biz_bom": {
        "id": "ID",
        "parent_material_code": "父物料代码",
        "child_material_code": "子物料代码",
        "quantity": "数量",
        "bom_level": "BOM层级",
    },
    "core_biz_wip": {
        "id": "ID",
        "material_code": "物料代码",
        "quantity": "在制数量",
        "completed_stages": "已完成阶段",
    },
    "core_biz_outsource_period_limit": {
        "material_code": "物料代码",
        "period_index": "周期序号",
        "max_quantity": "最大外协量",
    },
    "core_biz_purchase_period_limit": {
        "material_code": "物料代码",
        "period_index": "周期序号",
        "max_purchase_quantity": "最大采购量",
    },
    "core_biz_alt_period_limit": {
        "rule_id": "替代关系编号",
        "period_index": "周期序号",
        "max_alternative_quantity": "最大替代量",
    },
    "core_biz_routing_header": {
        "routing_id": "工艺路线编号",
        "material_code": "物料代码",
        "alt_route_id": "替代路线编号",
        "total_lead_time": "整体生产周期",
        "is_default": "是否默认",
        "is_active": "是否启用",
    },
    "core_biz_routing_step": {
        "step_id": "步骤编号",
        "routing_id": "工艺路线编号",
        "step_order": "执行顺序",
        "operation_code": "工序代码",
        "equipment_code": "设备代码",
        "production_line_code": "生产线代码",
        "fixture_code": "工装代码",
        "fixture_quantity": "工装数量",
        "max_lead_time": "工序生产周期",
    },
    "core_biz_step_time_offset": {
        "step_id": "步骤编号",
        "offset_index": "偏移序号",
        "duration": "加工耗时",
    },
    "core_biz_global_params": {
        "param_key": "参数键",
        "param_value": "参数值",
        "description": "参数说明",
    },
    # === 算法输入 (alg_sheet_) ===
    "alg_sheet_订单表": {
        "订单序号": "订单序号",
        "产品代码": "产品代码",
        "订单价格": "订单价格",
        "订单数量": "订单数量",
        "订单交期": "订单交期",
        "订单等级": "订单等级",
        "允许延期": "允许延期",
        "延期罚金": "延期罚金",
        "生产提前期": "生产提前期",
    },
    "alg_sheet_产品表": {
        "序号": "序号",
        "产品代码": "产品代码",
        "产品名称": "产品名称",
        "产品成本": "产品成本",
        "产品价格": "产品价格",
        "提前期": "提前期",
        "初始库存": "初始库存",
        "期末库存": "期末库存",
        "最小库存": "最小库存",
        "最大库存": "最大库存",
        "库存成本": "库存成本",
    },
    "alg_sheet_原材料表": {
        "序号": "序号",
        "原料代码": "原料代码",
        "物料名称": "物料名称",
        "采购成本": "采购成本",
        "采购提前期": "采购提前期",
        "初始库存": "初始库存",
        "期末库存": "期末库存",
        "最小库存": "最小库存",
        "最大库存": "最大库存",
        "库存成本": "库存成本",
    },
    "alg_sheet_自制件": {
        "序号": "序号",
        "自制件代码": "自制件代码",
        "自制件名称": "自制件名称",
        "虚拟件属性": "虚拟件属性",
        "提前期": "提前期",
        "初始库存": "初始库存",
        "期末库存": "期末库存",
        "最小库存": "最小库存",
        "最大库存": "最大库存",
        "库存成本": "库存成本",
        "外协价格": "外协价格",
    },
    "alg_sheet_BOM": {
        "序号": "序号",
        "BOM层级": "BOM层级",
        "父物料": "父物料",
        "父物料名称": "父物料名称",
        "子物料": "子物料",
        "子物料名称": "子物料名称",
        "数量": "数量",
    },
    "alg_sheet_设备表": {
        "序号": "序号",
        "设备代码": "设备代码",
        "单位成本": "单位成本",
        "设备数": "设备数",
        "设备利用率": "设备利用率",
        "加班率": "加班率",
        "加班成本": "加班成本",
    },
    "alg_sheet_工装表": {
        "序号": "序号",
        "工装代码": "工装代码",
        "工装成本": "工装成本",
        "工装数": "工装数",
        "工装利用率": "工装利用率",
        "加班率": "加班率",
        "加班成本": "加班成本",
    },
    "alg_sheet_在制品": {
        "序号": "序号",
        "在制品种类代码": "在制品种类代码",
        "自制品种类": "自制品种类",
        "在制件代码": "在制件代码",
        "在制件名称": "在制件名称",
        "总制造期": "总制造期",
        "已完成阶段": "已完成阶段",
        "在制数量": "在制数量",
    },
    "alg_sheet_外协": _alg_outsource_mapping(),
    "alg_sheet_采购限制": _alg_purchase_mapping(),
    "alg_sheet_替代关系": _alg_alt_mapping(),
    "alg_sheet_工艺路线": _alg_routing_mapping(),
    "alg_sheet_综合表": {
        "主要参数": "主要参数",
        "参数值": "参数值",
    },
    # === 原始数据 (stg_) ===
    "stg_system_config": {
        "id": "ID",
        "config_key": "配置项",
        "config_value": "配置值",
    },
    "stg_orders": {
        "id": "ID",
        "order_id": "订单序号",
        "product_code": "产品代码",
        "order_price": "订单价格",
        "order_quantity": "订单数量",
        "due_period": "订单交期",
        "priority_level": "订单等级",
        "max_delay_allowed": "允许延期",
        "delay_penalty": "延期罚金",
        "production_lead_time": "生产提前期",
    },
    "stg_bom": {
        "id": "ID",
        "seq": "序号",
        "bom_level": "BOM层级",
        "parent_code": "父物料",
        "parent_name": "父物料名称",
        "child_code": "子物料",
        "child_name": "子物料名称",
        "quantity": "数量",
    },
    "stg_routing": {
        "id": "ID",
        "seq": "序号",
        "material_code": "物料代码",
        "material_name": "物料名称",
        "alt_route_id": "多工艺",
        "equipment_code": "设备代码",
        "production_line": "生产线",
        "operation_name": "工序",
        "fixture_code": "工装代码",
        "fixture_quantity": "工装数量",
        "max_lead_time": "MaxT",
        "time_offset_1": "1",
        "time_offset_2": "2",
        "time_offset_3": "3",
    },
    "stg_equipment": {
        "id": "ID",
        "seq": "序号",
        "equipment_code": "设备代码",
        "unit_cost": "单位成本",
        "quantity": "设备数",
        "utilization_rate": "设备利用率",
        "overtime_rate": "加班率",
        "overtime_cost": "加班成本",
    },
    "stg_fixture": {
        "id": "ID",
        "seq": "序号",
        "fixture_code": "工装代码",
        "unit_cost": "工装成本",
        "quantity": "工装数",
        "utilization_rate": "工装利用率",
        "overtime_rate": "加班率",
        "overtime_cost": "加班成本",
    },
    "stg_product": {
        "id": "ID",
        "seq": "序号",
        "product_code": "产品代码",
        "product_name": "产品名称",
        "product_cost": "产品成本",
        "product_price": "产品价格",
        "lead_time": "提前期",
        "initial_inventory": "初始库存",
        "target_inventory": "期末库存",
        "min_inventory": "最小库存",
        "max_inventory": "最大库存",
        "holding_cost_rate": "库存成本",
    },
    "stg_semi": {
        "id": "ID",
        "seq": "序号",
        "semi_code": "自制件代码",
        "semi_name": "自制件名称",
        "is_virtual": "虚拟件属性",
        "lead_time": "提前期",
        "initial_inventory": "初始库存",
        "target_inventory": "期末库存",
        "min_inventory": "最小库存",
        "max_inventory": "最大库存",
        "holding_cost_rate": "库存成本",
    },
    "stg_raw": {
        "id": "ID",
        "seq": "序号",
        "raw_code": "原料代码",
        "raw_name": "原料名称",
        "purchase_cost": "采购成本",
        "purchase_lead_time": "采购提前期",
        "initial_inventory": "初始库存",
        "target_inventory": "期末库存",
        "min_inventory": "最小库存",
        "max_inventory": "最大库存",
        "holding_cost_rate": "库存成本",
    },
    "stg_wip": {
        "id": "ID",
        "seq": "序号",
        "wip_category": "在制品种类代码",
        "semi_category": "自制品种类",
        "material_code": "在制件代码",
        "material_name": "在制件名称",
        "total_lead_time": "总制造期",
        "completed_stages": "已完成阶段",
        "quantity": "在制数量",
    },
    "stg_outsource": _stg_period_mapping(
        {"id": "ID", "seq": "序号", "material_code": "物料代码", "unit_price": "外协价格"},
        with_total=True,
    ),
    "stg_purchase_limit": _stg_period_mapping(
        {"id": "ID", "seq": "序号", "material_code": "原料代码", "material_name": "原料名称"},
        with_total=True,
    ),
    "stg_alternative": _stg_period_mapping(
        {
            "id": "ID",
            "seq": "序号",
            "alt_type": "替代类型",
            "from_material_code": "替代物料一代码",
            "from_quantity": "数量一",
            "to_material_code": "替代物料二代码",
            "to_quantity": "数量二",
            "ratio": "比例",
            "is_batch": "整批",
        },
        with_total=False,
    ),
}

COLUMN_DISPLAY_ORDER = {
    "core_md_material": [
        "material_code", "material_name", "category", "unit",
        "initial_inventory", "target_end_inventory",
        "min_inventory", "max_inventory", "holding_cost_rate",
    ],
    "core_md_product_ext": [
        "material_code", "standard_cost", "standard_price",
        "assembly_lead_time", "sales_status",
    ],
    "core_md_semi_ext": [
        "material_code", "is_virtual", "manufacturing_lead_time",
        "default_routing_id", "scrap_rate",
    ],
    "core_md_raw_ext": [
        "material_code", "purchase_cost", "purchase_lead_time",
        "preferred_supplier", "moq",
    ],
    "core_md_resource": [
        "resource_code", "resource_name", "resource_type", "line_code",
        "quantity", "unit_cost", "utilization_rate", "overtime_rate",
        "overtime_cost_multiplier",
    ],
    "core_md_line": [
        "line_code", "line_name", "line_type",
    ],
    "core_md_operation": [
        "operation_code", "operation_name",
    ],
    "core_md_alt_rule": [
        "rule_id", "alt_type", "alt_type_name",
        "from_material_code", "from_quantity",
        "to_material_code", "to_quantity",
        "ratio", "is_batch", "is_active",
    ],
    "core_md_outsource": [
        "material_code", "unit_price",
    ],
    "core_md_purchase_limit": [
        "material_code", "note",
    ],
    # === 业务数据 (core_biz_) ===
    "core_biz_demand_order": [
        "order_id", "product_code", "price", "quantity",
        "due_period", "priority_level", "max_delay_allowed", "delay_penalty",
    ],
    "core_biz_bom": [
        "id", "parent_material_code", "child_material_code", "quantity", "bom_level",
    ],
    "core_biz_wip": [
        "id", "material_code", "quantity", "completed_stages",
    ],
    "core_biz_outsource_period_limit": [
        "material_code", "period_index", "max_quantity",
    ],
    "core_biz_purchase_period_limit": [
        "material_code", "period_index", "max_purchase_quantity",
    ],
    "core_biz_alt_period_limit": [
        "rule_id", "period_index", "max_alternative_quantity",
    ],
    "core_biz_routing_header": [
        "routing_id", "material_code", "alt_route_id", "total_lead_time",
        "is_default", "is_active",
    ],
    "core_biz_routing_step": [
        "step_id", "routing_id", "step_order", "operation_code",
        "equipment_code", "production_line_code", "fixture_code",
        "fixture_quantity", "max_lead_time",
    ],
    "core_biz_step_time_offset": [
        "step_id", "offset_index", "duration",
    ],
    "core_biz_global_params": [
        "param_key", "param_value", "description",
    ],
    # === 算法输入 (alg_sheet_) ===
    "alg_sheet_订单表": [
        "订单序号", "产品代码", "订单价格", "订单数量",
        "订单交期", "订单等级", "允许延期", "延期罚金", "生产提前期",
    ],
    "alg_sheet_产品表": [
        "序号", "产品代码", "产品名称", "产品成本", "产品价格",
        "提前期", "初始库存", "期末库存", "最小库存", "最大库存", "库存成本",
    ],
    "alg_sheet_原材料表": [
        "序号", "原料代码", "物料名称", "采购成本", "采购提前期",
        "初始库存", "期末库存", "最小库存", "最大库存", "库存成本",
    ],
    "alg_sheet_自制件": [
        "序号", "自制件代码", "自制件名称", "虚拟件属性", "提前期",
        "初始库存", "期末库存", "最小库存", "最大库存", "库存成本", "外协价格",
    ],
    "alg_sheet_BOM": [
        "序号", "BOM层级", "父物料", "父物料名称", "子物料", "子物料名称", "数量",
    ],
    "alg_sheet_设备表": [
        "序号", "设备代码", "单位成本", "设备数", "设备利用率", "加班率", "加班成本",
    ],
    "alg_sheet_工装表": [
        "序号", "工装代码", "工装成本", "工装数", "工装利用率", "加班率", "加班成本",
    ],
    "alg_sheet_在制品": [
        "序号", "在制品种类代码", "自制品种类", "在制件代码", "在制件名称",
        "总制造期", "已完成阶段", "在制数量",
    ],
    "alg_sheet_外协": _alg_outsource_columns(),
    "alg_sheet_采购限制": _alg_purchase_columns(),
    "alg_sheet_替代关系": _alg_alt_columns(),
    "alg_sheet_工艺路线": _alg_routing_columns(),
    "alg_sheet_综合表": ["主要参数", "参数值"],
    # === 原始数据 (stg_) ===
    "stg_system_config": ["id", "config_key", "config_value"],
    "stg_orders": [
        "id", "order_id", "product_code", "order_price", "order_quantity",
        "due_period", "priority_level", "max_delay_allowed", "delay_penalty",
        "production_lead_time",
    ],
    "stg_bom": ["id", "seq", "bom_level", "parent_code", "parent_name", "child_code", "child_name", "quantity"],
    "stg_routing": [
        "id", "seq", "material_code", "material_name", "alt_route_id",
        "equipment_code", "production_line", "operation_name",
        "fixture_code", "fixture_quantity", "max_lead_time",
        "time_offset_1", "time_offset_2", "time_offset_3",
    ],
    "stg_equipment": [
        "id", "seq", "equipment_code", "unit_cost", "quantity",
        "utilization_rate", "overtime_rate", "overtime_cost",
    ],
    "stg_fixture": [
        "id", "seq", "fixture_code", "unit_cost", "quantity",
        "utilization_rate", "overtime_rate", "overtime_cost",
    ],
    "stg_product": [
        "id", "seq", "product_code", "product_name", "product_cost", "product_price",
        "lead_time", "initial_inventory", "target_inventory",
        "min_inventory", "max_inventory", "holding_cost_rate",
    ],
    "stg_semi": [
        "id", "seq", "semi_code", "semi_name", "is_virtual", "lead_time",
        "initial_inventory", "target_inventory", "min_inventory", "max_inventory",
        "holding_cost_rate",
    ],
    "stg_raw": [
        "id", "seq", "raw_code", "raw_name", "purchase_cost", "purchase_lead_time",
        "initial_inventory", "target_inventory", "min_inventory", "max_inventory",
        "holding_cost_rate",
    ],
    "stg_wip": [
        "id", "seq", "wip_category", "semi_category", "material_code", "material_name",
        "total_lead_time", "completed_stages", "quantity",
    ],
    "stg_outsource": _stg_period_columns(
        ["id", "seq", "material_code", "unit_price"], with_total=True,
    ),
    "stg_purchase_limit": _stg_period_columns(
        ["id", "seq", "material_code", "material_name"], with_total=True,
    ),
    "stg_alternative": _stg_period_columns(
        ["id", "seq", "alt_type", "from_material_code", "from_quantity",
         "to_material_code", "to_quantity", "ratio", "is_batch"],
        with_total=False,
    ),
}

ENUM_MAPPINGS = {
    "core_md_material": {
        "category": {"PRODUCT": "产品", "SEMI": "自制件", "RAW": "原材料"},
    },
    "core_md_product_ext": {
        "sales_status": {"ACTIVE": "启用", "INACTIVE": "停用", "DISCONTINUED": "停产"},
    },
    "core_md_resource": {
        "resource_type": {"EQUIPMENT": "设备", "FIXTURE": "工装"},
    },
    "core_md_line": {
        "line_type": {
            "paint": "涂装线", "welding": "焊接线", "assembly": "装配线",
            "machining": "机加线", "production": "生产线",
        },
    },
    "core_md_alt_rule": {
        "alt_type_name": {
            "产品替代": "产品替代", "自制件替代": "自制件替代", "原材料替代": "原材料替代",
        },
    },
    "stg_alternative": {
        "alt_type": {"1": "产品替代", "2": "自制件替代", "3": "原材料替代"},
    },
}

BOOL_MAPPINGS = {
    "core_md_material": {},
    "core_md_semi_ext": {
        "is_virtual": {0: "否", 1: "是"},
    },
    "core_md_alt_rule": {
        "is_batch": {0: "否", 1: "是"},
        "is_active": {0: "停用", 1: "启用"},
    },
    "stg_semi": {
        "is_virtual": {0: "否", 1: "是"},
    },
    "stg_alternative": {
        "is_batch": {0: "否", 1: "是"},
    },
    "core_biz_routing_header": {
        "is_default": {0: "否", 1: "是"},
        "is_active": {0: "停用", 1: "启用"},
    },
    "alg_sheet_自制件": {
        "虚拟件属性": {0: "否", 1: "是"},
    },
    "alg_sheet_替代关系": {
        "整批": {0: "否", 1: "是"},
    },
}

DEFAULT_SORT = {
    "core_md_material": "material_code",
    "core_md_product_ext": "material_code",
    "core_md_semi_ext": "material_code",
    "core_md_raw_ext": "material_code",
    "core_md_resource": "resource_code",
    "core_md_line": "line_code",
    "core_md_operation": "operation_code",
    "core_md_alt_rule": "rule_id",
    "core_md_outsource": "material_code",
    "core_md_purchase_limit": "material_code",
    "core_biz_demand_order": "order_id",
    "core_biz_bom": "id",
    "core_biz_wip": "id",
    "core_biz_outsource_period_limit": "material_code",
    "core_biz_purchase_period_limit": "material_code",
    "core_biz_alt_period_limit": "rule_id",
    "core_biz_routing_header": "routing_id",
    "core_biz_routing_step": "step_id",
    "core_biz_step_time_offset": "step_id",
    "core_biz_global_params": "param_key",
    "alg_sheet_订单表": "订单序号",
    "alg_sheet_产品表": "序号",
    "alg_sheet_原材料表": "序号",
    "alg_sheet_自制件": "序号",
    "alg_sheet_BOM": "序号",
    "alg_sheet_设备表": "序号",
    "alg_sheet_工装表": "序号",
    "alg_sheet_在制品": "序号",
    "alg_sheet_外协": "序号",
    "alg_sheet_采购限制": "序号",
    "alg_sheet_替代关系": "序号",
    "alg_sheet_工艺路线": "序号",
    "alg_sheet_综合表": "主要参数",
    "stg_system_config": "id",
    "stg_orders": "id",
    "stg_bom": "id",
    "stg_routing": "id",
    "stg_equipment": "id",
    "stg_fixture": "id",
    "stg_product": "id",
    "stg_semi": "id",
    "stg_raw": "id",
    "stg_wip": "id",
    "stg_outsource": "id",
    "stg_purchase_limit": "id",
    "stg_alternative": "id",
}

# =============================================================================
# 输出结果（res_view_* 求解结果视图，对应 docs/排产结果数据库设计.md 的 26 个视图）
# =============================================================================

RESULT_VIEWS = [
    {"key": "summary", "name": "res_view_summary", "label": "求解汇总"},
    {"key": "order_sale", "name": "res_view_order_sale", "label": "订单销售交付"},
    {"key": "order_delivery", "name": "res_view_order_delivery", "label": "订单交付汇总"},
    {"key": "prod_plan", "name": "res_view_prod_plan", "label": "产品生产计划"},
    {"key": "prod_sale", "name": "res_view_prod_sale", "label": "产品销售计划"},
    {"key": "self_plan", "name": "res_view_self_plan", "label": "自制件生产计划"},
    {"key": "prod_machining", "name": "res_view_prod_machining", "label": "产品加工计划"},
    {"key": "self_machining", "name": "res_view_self_machining", "label": "自制件加工计划"},
    {"key": "purchase_plan", "name": "res_view_purchase_plan", "label": "采购计划"},
    {"key": "outsource_plan", "name": "res_view_outsource_plan", "label": "外协计划"},
    {"key": "prod_inv", "name": "res_view_prod_inv", "label": "产品库存"},
    {"key": "self_inv", "name": "res_view_self_inv", "label": "自制件库存"},
    {"key": "raw_inv", "name": "res_view_raw_inv", "label": "原材料库存"},
    {"key": "equip_load", "name": "res_view_equip_load", "label": "设备负荷"},
    {"key": "equip_overload", "name": "res_view_equip_overload", "label": "设备加班负荷"},
    {"key": "equip_shadow", "name": "res_view_equip_shadow", "label": "设备影子价格"},
    {"key": "fixt_load", "name": "res_view_fixt_load", "label": "工装负荷"},
    {"key": "fixt_overload", "name": "res_view_fixt_overload", "label": "工装加班负荷"},
    {"key": "fixt_shadow", "name": "res_view_fixt_shadow", "label": "工装影子价格"},
    {"key": "shadow_prod", "name": "res_view_shadow_prod", "label": "产品影子价格"},
    {"key": "shadow_self", "name": "res_view_shadow_self", "label": "自制件影子价格"},
    {"key": "shadow_raw", "name": "res_view_shadow_raw", "label": "原材料影子价格"},
    {"key": "substitute", "name": "res_view_substitute", "label": "替代物料使用"},
    {"key": "inf_prod", "name": "res_view_inf_prod", "label": "产品不可行量"},
    {"key": "inf_self", "name": "res_view_inf_self", "label": "自制件不可行量"},
    {"key": "inf_equip", "name": "res_view_inf_equip", "label": "设备不可行量"},
]

_RESULT_P12 = [f"period_{i}" for i in range(1, 13)]
_RESULT_MADE_P12 = [f"made_period_{i}" for i in range(1, 13)]
_RESULT_CAP_P12 = [f"cap_period_{i}" for i in range(1, 13)]
_RESULT_INV_P12 = ["period_0"] + _RESULT_P12

_RESULT_VIEW_COLUMNS = {
    "res_view_summary": [
        "run_id", "run_time", "sales_revenue", "delay_penalty", "manufacturing_cost",
        "outsource_cost", "purchase_cost", "inventory_cost", "infeasible_cost",
        "fixture_cost", "profit",
    ],
    "res_view_order_sale": [
        "order_id", "material_code", "priority_level", "order_price", "order_quantity",
        "due_period", "delivery_period", "delivery_quantity", "delay_quantity",
        "delivery_status", "revenue", "delay_penalty", "shadow_price", "margin",
    ],
    "res_view_order_delivery": [
        "priority_level", "order_count_total", "order_count_ontime", "order_count_partial",
        "order_count_delayed", "order_count_undelivered", "quantity_total", "quantity_ontime",
        "quantity_partial", "quantity_delayed", "quantity_undelivered",
    ],
    "res_view_prod_plan": ["material_code", "route_id"] + _RESULT_P12 + ["quantity_total"],
    "res_view_prod_sale": ["material_code"] + _RESULT_P12 + ["quantity_total"],
    "res_view_self_plan": ["seq", "material_code", "route_id"] + _RESULT_P12 + ["quantity_total"],
    "res_view_prod_machining": (
        ["resource_code", "production_line", "operation_code", "material_code", "route_id",
         "fixture_code", "fixture_quantity"] + _RESULT_MADE_P12 + _RESULT_CAP_P12 + ["capacity_total"]
    ),
    "res_view_self_machining": (
        ["resource_code", "production_line", "operation_code", "material_code", "route_id",
         "fixture_code", "fixture_quantity"] + _RESULT_MADE_P12 + _RESULT_CAP_P12 + ["capacity_total"]
    ),
    "res_view_purchase_plan": ["seq", "material_code"] + _RESULT_P12 + ["quantity_total", "cost_total"],
    "res_view_outsource_plan": ["seq", "material_code"] + _RESULT_P12 + ["quantity_total", "cost_total"],
    "res_view_prod_inv": ["material_code"] + _RESULT_INV_P12 + ["quantity_total", "inventory_cost"],
    "res_view_self_inv": ["material_code"] + _RESULT_INV_P12 + ["quantity_total", "inventory_cost"],
    "res_view_raw_inv": ["material_code"] + _RESULT_INV_P12 + ["quantity_total", "inventory_cost"],
    "res_view_equip_load": ["resource_code", "capacity"] + _RESULT_P12
        + ["max_load_rate_pct", "avg_load_rate_pct", "normal_cost_total"],
    "res_view_fixt_load": ["resource_code", "capacity"] + _RESULT_P12
        + ["max_load_rate_pct", "avg_load_rate_pct", "normal_cost_total"],
    "res_view_equip_overload": ["resource_code", "capacity"] + _RESULT_P12 + ["overload_cost_total"],
    "res_view_fixt_overload": ["resource_code", "capacity"] + _RESULT_P12 + ["overload_cost_total"],
    "res_view_equip_shadow": ["resource_code"] + _RESULT_P12,
    "res_view_fixt_shadow": ["resource_code"] + _RESULT_P12,
    "res_view_shadow_prod": ["material_code"] + _RESULT_P12,
    "res_view_shadow_self": ["material_code"] + _RESULT_P12,
    "res_view_shadow_raw": ["material_code"] + _RESULT_P12,
    "res_view_substitute": ["alt_type_name", "from_material_code", "to_material_code"]
        + _RESULT_P12 + ["quantity_total"],
    "res_view_inf_prod": ["material_code"] + _RESULT_P12 + ["inf_total"],
    "res_view_inf_self": ["material_code"] + _RESULT_P12 + ["inf_total"],
    "res_view_inf_equip": ["resource_code"] + _RESULT_P12 + ["inf_total"],
}

# 结果视图列名中文映射（公共部分 + 各视图专属）
_RESULT_COMMON_LABELS = {
    "run_id": "求解批次", "run_time": "求解时间",
    "sales_revenue": "销售收入", "delay_penalty": "延期罚金", "manufacturing_cost": "制造成本",
    "outsource_cost": "外协成本", "purchase_cost": "采购成本", "inventory_cost": "库存成本",
    "infeasible_cost": "不可行成本", "fixture_cost": "工装成本", "profit": "利润",
    "order_id": "订单号", "material_code": "物料代码", "resource_code": "资源代码",
    "operation_code": "工序", "route_id": "工艺路线", "seq": "序号",
    "priority_level": "订单等级", "order_price": "订单单价", "order_quantity": "订单数量",
    "due_period": "交期", "delivery_period": "实际交期", "delivery_quantity": "交付数量",
    "delay_quantity": "延期数量", "delivery_status": "交付状态",
    "revenue": "销售收入", "shadow_price": "影子价格", "margin": "边际贡献",
    "order_count_total": "订单总数", "order_count_ontime": "按期交付单数",
    "order_count_partial": "部分按期单数", "order_count_delayed": "延期交付单数",
    "order_count_undelivered": "未交付单数",
    "quantity_total": "合计", "quantity_ontime": "按期交付量", "quantity_partial": "部分按期量",
    "quantity_delayed": "延期交付量", "quantity_undelivered": "未交付量",
    "capacity": "能力", "fixture_code": "工装代码", "fixture_quantity": "工装数量",
    "production_line": "生产线",
    "capacity_total": "能力占用合计", "cost_total": "成本合计",
    "max_load_rate_pct": "最大负荷率(%)", "avg_load_rate_pct": "平均负荷率(%)",
    "normal_cost_total": "正常成本合计", "overload_cost_total": "加班成本合计",
    "inf_total": "不可行量合计",
    "alt_type_name": "替代类型", "from_material_code": "被替代物料", "to_material_code": "替代物料",
    "period_0": "期初",
}

_RESULT_VIEW_LABELS = {
    "res_view_order_delivery": {"quantity_total": "订单总量"},
    "res_view_prod_machining": {"resource_code": "设备代码"},
    "res_view_self_machining": {"resource_code": "设备代码"},
    "res_view_equip_load": {"resource_code": "设备代码"},
    "res_view_equip_overload": {"resource_code": "设备代码"},
    "res_view_equip_shadow": {"resource_code": "设备代码"},
    "res_view_fixt_load": {"resource_code": "工装代码"},
    "res_view_fixt_overload": {"resource_code": "工装代码"},
    "res_view_fixt_shadow": {"resource_code": "工装代码"},
    "res_view_inf_equip": {"resource_code": "设备代码"},
}

# 注册结果视图的列顺序 / 中文映射 / 默认排序
for _v in RESULT_VIEWS:
    _name = _v["name"]
    COLUMN_DISPLAY_ORDER[_name] = _RESULT_VIEW_COLUMNS[_name]
    _labels = dict(_RESULT_COMMON_LABELS)
    _labels.update(_RESULT_VIEW_LABELS.get(_name, {}))
    for _i in range(1, 13):
        _labels[f"period_{_i}"] = f"第{_i}期"
        _labels[f"made_period_{_i}"] = f"第{_i}期产量"
        _labels[f"cap_period_{_i}"] = f"第{_i}期占用"
    COLUMN_MAPPINGS[_name] = _labels
    DEFAULT_SORT[_name] = _RESULT_VIEW_COLUMNS[_name][0]


def get_result_view_by_key(table_key: str) -> dict | None:
    for t in RESULT_VIEWS:
        if t["key"] == table_key:
            return t
    return None


SIDEBAR_MENU = [
    {"key": "dashboard", "label": "工作台", "icon": "fa-chart-pie", "enabled": True, "url": "/dashboard", "children": []},
    {
        "key": "base_data",
        "label": "基础数据",
        "icon": "fa-database",
        "enabled": True,
        "children": [
            {"key": "overview", "label": "总览", "url": "/", "icon": "fa-list"},
            {"key": "material", "label": "物料主数据", "url": "/base-data/material", "icon": "fa-box"},
            {"key": "product_ext", "label": "产品扩展", "url": "/base-data/product_ext", "icon": "fa-box-open"},
            {"key": "semi_ext", "label": "自制件扩展", "url": "/base-data/semi_ext", "icon": "fa-cogs"},
            {"key": "raw_ext", "label": "原材料扩展", "url": "/base-data/raw_ext", "icon": "fa-leaf"},
            {"key": "resource", "label": "设备/工装", "url": "/base-data/resource", "icon": "fa-microchip"},
            {"key": "line", "label": "生产线", "url": "/base-data/line", "icon": "fa-industry"},
            {"key": "operation", "label": "工序定义", "url": "/base-data/operation", "icon": "fa-cog"},
            {"key": "alt_rule", "label": "替代规则", "url": "/base-data/alt_rule", "icon": "fa-exchange-alt"},
            {"key": "outsource", "label": "外协", "url": "/base-data/outsource", "icon": "fa-truck"},
            {"key": "purchase_limit", "label": "采购限制", "url": "/base-data/purchase_limit", "icon": "fa-shopping-cart"},
        ],
    },
    {
        "key": "plan_opt",
        "label": "计划优化",
        "icon": "fa-play-circle",
        "enabled": True,
        "children": [
            {"key": "solve", "label": "排产触发", "url": "/solve", "icon": "fa-rocket"},
        ],
    },
    {
        "key": "visual",
        "label": "排程可视化",
        "icon": "fa-chart-gantt",
        "enabled": True,
        "children": [
            {"key": "vis_gantt", "label": "生产甘特图", "url": "/vis/gantt", "icon": "fa-stream"},
            {"key": "vis_orders", "label": "订单交付看板", "url": "/vis/orders", "icon": "fa-clipboard-check"},
            {"key": "equip_load_link", "label": "设备负荷明细", "url": "/res/equip_load", "icon": "fa-microchip"},
            {"key": "shadow_link", "label": "影子价格", "url": "/res/shadow_prod", "icon": "fa-dollar-sign"},
        ],
    },
    {
        "key": "analysis",
        "label": "分析中心",
        "icon": "fa-chart-line",
        "enabled": True,
        "children": [
            {"key": "analysis_delay", "label": "延期分析", "url": "/analysis/delay", "icon": "fa-clock"},
            {"key": "analysis_bottleneck", "label": "瓶颈分析", "url": "/analysis/bottleneck", "icon": "fa-fire"},
            {"key": "analysis_inventory", "label": "库存分析", "url": "/analysis/inventory", "icon": "fa-boxes"},
            {"key": "analysis_cost", "label": "成本分析", "url": "/analysis/cost", "icon": "fa-yen-sign"},
            {"key": "analysis_outsource", "label": "外协分析", "url": "/analysis/outsource", "icon": "fa-truck"},
        ],
    },
    {
        "key": "versions_menu",
        "label": "计划版本",
        "icon": "fa-history",
        "enabled": True,
        "children": [
            {"key": "versions", "label": "版本列表", "url": "/versions", "icon": "fa-list"},
            {"key": "versions_compare", "label": "方案对比", "url": "/versions/compare", "icon": "fa-balance-scale"},
        ],
    },
    {
        "key": "raw_data",
        "label": "原始数据",
        "icon": "fa-file-alt",
        "enabled": True,
        "children": [
            {"key": "stg_overview", "label": "总览", "url": "/stg", "icon": "fa-list"},
            {"key": "stg_system_config", "label": "系统配置", "url": "/stg/stg_system_config", "icon": "fa-cog"},
            {"key": "stg_orders", "label": "订单表", "url": "/stg/stg_orders", "icon": "fa-clipboard-list"},
            {"key": "stg_bom", "label": "BOM表", "url": "/stg/stg_bom", "icon": "fa-sitemap"},
            {"key": "stg_routing", "label": "工艺路线", "url": "/stg/stg_routing", "icon": "fa-route"},
            {"key": "stg_equipment", "label": "设备表", "url": "/stg/stg_equipment", "icon": "fa-microchip"},
            {"key": "stg_fixture", "label": "工装表", "url": "/stg/stg_fixture", "icon": "fa-tools"},
            {"key": "stg_product", "label": "产品表", "url": "/stg/stg_product", "icon": "fa-box"},
            {"key": "stg_semi", "label": "自制件", "url": "/stg/stg_semi", "icon": "fa-cogs"},
            {"key": "stg_raw", "label": "原材料表", "url": "/stg/stg_raw", "icon": "fa-leaf"},
            {"key": "stg_wip", "label": "在制品", "url": "/stg/stg_wip", "icon": "fa-spinner"},
            {"key": "stg_outsource", "label": "外协", "url": "/stg/stg_outsource", "icon": "fa-truck"},
            {"key": "stg_purchase_limit", "label": "采购限制", "url": "/stg/stg_purchase_limit", "icon": "fa-shopping-cart"},
            {"key": "stg_alternative", "label": "替代关系", "url": "/stg/stg_alternative", "icon": "fa-exchange-alt"},
        ],
    },
    {
        "key": "biz_data",
        "label": "业务数据",
        "icon": "fa-clipboard-list",
        "enabled": True,
        "children": [
            {"key": "biz_overview", "label": "总览", "url": "/biz", "icon": "fa-list"},
            {"key": "demand_order", "label": "订单需求", "url": "/biz/demand_order", "icon": "fa-file-invoice"},
            {"key": "bom", "label": "BOM", "url": "/biz/bom", "icon": "fa-sitemap"},
            {"key": "wip", "label": "在制品", "url": "/biz/wip", "icon": "fa-spinner"},
            {"key": "outsource_limit", "label": "外协周期限额", "url": "/biz/outsource_limit", "icon": "fa-truck"},
            {"key": "purchase_limit", "label": "采购周期限额", "url": "/biz/purchase_limit", "icon": "fa-shopping-cart"},
            {"key": "alt_limit", "label": "替代周期限额", "url": "/biz/alt_limit", "icon": "fa-exchange-alt"},
            {"key": "routing_header", "label": "工艺路线头表", "url": "/biz/routing_header", "icon": "fa-route"},
            {"key": "routing_step", "label": "工艺步骤定义", "url": "/biz/routing_step", "icon": "fa-tasks"},
            {"key": "step_time_offset", "label": "步骤工时偏移", "url": "/biz/step_time_offset", "icon": "fa-clock"},
            {"key": "global_params", "label": "全局排产参数", "url": "/biz/global_params", "icon": "fa-cogs"},
        ],
    },
    {
        "key": "alg_input",
        "label": "算法输入",
        "icon": "fa-calculator",
        "enabled": True,
        "children": [
            {"key": "alg_overview", "label": "总览", "url": "/alg", "icon": "fa-list"},
            {"key": "order_demand", "label": "订单需求", "url": "/alg/order_demand", "icon": "fa-file-invoice"},
            {"key": "product_info", "label": "产品信息", "url": "/alg/product_info", "icon": "fa-box"},
            {"key": "raw_material", "label": "原材料信息", "url": "/alg/raw_material", "icon": "fa-leaf"},
            {"key": "semi_info", "label": "自制件信息", "url": "/alg/semi_info", "icon": "fa-cogs"},
            {"key": "bom_info", "label": "BOM信息", "url": "/alg/bom_info", "icon": "fa-sitemap"},
            {"key": "equipment_info", "label": "设备表信息", "url": "/alg/equipment_info", "icon": "fa-microchip"},
            {"key": "fixture_info", "label": "工装表信息", "url": "/alg/fixture_info", "icon": "fa-tools"},
            {"key": "wip_info", "label": "在制品信息", "url": "/alg/wip_info", "icon": "fa-spinner"},
            {"key": "outsource_limit", "label": "外协信息", "url": "/alg/outsource_limit", "icon": "fa-file-signature"},
            {"key": "purchase_limit", "label": "采购限制", "url": "/alg/purchase_limit", "icon": "fa-shopping-cart"},
            {"key": "alt_rule", "label": "替代关系", "url": "/alg/alt_rule", "icon": "fa-exchange-alt"},
            {"key": "routing", "label": "工艺路线", "url": "/alg/routing", "icon": "fa-project-diagram"},
            {"key": "global_params", "label": "综合表", "url": "/alg/global_params", "icon": "fa-table"},
        ],
    },
    {
        "key": "result_output",
        "label": "输出结果",
        "icon": "fa-chart-bar",
        "enabled": True,
        "children": [
            {"key": "res_overview", "label": "总览", "url": "/res", "icon": "fa-list"},
            {"key": "summary", "label": "求解汇总", "url": "/res/summary", "icon": "fa-table"},
            {"key": "order_sale", "label": "订单销售交付", "url": "/res/order_sale", "icon": "fa-file-invoice"},
            {"key": "order_delivery", "label": "订单交付汇总", "url": "/res/order_delivery", "icon": "fa-chart-bar"},
            {"key": "prod_plan", "label": "产品生产计划", "url": "/res/prod_plan", "icon": "fa-box"},
            {"key": "prod_sale", "label": "产品销售计划", "url": "/res/prod_sale", "icon": "fa-shopping-cart"},
            {"key": "self_plan", "label": "自制件生产计划", "url": "/res/self_plan", "icon": "fa-cogs"},
            {"key": "prod_machining", "label": "产品加工计划", "url": "/res/prod_machining", "icon": "fa-tasks"},
            {"key": "self_machining", "label": "自制件加工计划", "url": "/res/self_machining", "icon": "fa-tasks"},
            {"key": "purchase_plan", "label": "采购计划", "url": "/res/purchase_plan", "icon": "fa-shopping-cart"},
            {"key": "outsource_plan", "label": "外协计划", "url": "/res/outsource_plan", "icon": "fa-truck"},
            {"key": "prod_inv", "label": "产品库存", "url": "/res/prod_inv", "icon": "fa-boxes"},
            {"key": "self_inv", "label": "自制件库存", "url": "/res/self_inv", "icon": "fa-boxes"},
            {"key": "raw_inv", "label": "原材料库存", "url": "/res/raw_inv", "icon": "fa-leaf"},
            {"key": "equip_load", "label": "设备负荷", "url": "/res/equip_load", "icon": "fa-microchip"},
            {"key": "equip_overload", "label": "设备加班负荷", "url": "/res/equip_overload", "icon": "fa-microchip"},
            {"key": "equip_shadow", "label": "设备影子价格", "url": "/res/equip_shadow", "icon": "fa-dollar-sign"},
            {"key": "fixt_load", "label": "工装负荷", "url": "/res/fixt_load", "icon": "fa-tools"},
            {"key": "fixt_overload", "label": "工装加班负荷", "url": "/res/fixt_overload", "icon": "fa-tools"},
            {"key": "fixt_shadow", "label": "工装影子价格", "url": "/res/fixt_shadow", "icon": "fa-dollar-sign"},
            {"key": "shadow_prod", "label": "产品影子价格", "url": "/res/shadow_prod", "icon": "fa-dollar-sign"},
            {"key": "shadow_self", "label": "自制件影子价格", "url": "/res/shadow_self", "icon": "fa-dollar-sign"},
            {"key": "shadow_raw", "label": "原材料影子价格", "url": "/res/shadow_raw", "icon": "fa-dollar-sign"},
            {"key": "substitute", "label": "替代物料使用", "url": "/res/substitute", "icon": "fa-exchange-alt"},
            {"key": "inf_prod", "label": "产品不可行量", "url": "/res/inf_prod", "icon": "fa-exclamation-triangle"},
            {"key": "inf_self", "label": "自制件不可行量", "url": "/res/inf_self", "icon": "fa-exclamation-triangle"},
            {"key": "inf_equip", "label": "设备不可行量", "url": "/res/inf_equip", "icon": "fa-exclamation-triangle"},
        ],
    },
    {
        "key": "system",
        "label": "系统管理",
        "icon": "fa-cogs",
        "enabled": True,
        "children": [
            {"key": "admin_validation", "label": "数据校验", "url": "/admin/validation", "icon": "fa-clipboard-check"},
        ],
    },
    {"key": "scenario", "label": "场景管理", "icon": "fa-project-diagram", "enabled": False, "children": []},
    {"key": "integration", "label": "集成管理", "icon": "fa-plug", "enabled": False, "children": []},
]


def get_table_by_key(table_key: str) -> dict | None:
    for t in CORE_MD_TABLES:
        if t["key"] == table_key:
            return t
    return None


def get_table_by_name(table_name: str) -> dict | None:
    for t in CORE_MD_TABLES:
        if t["name"] == table_name:
            return t
    return None


def get_stg_table_by_key(table_key: str) -> dict | None:
    for t in STG_TABLES:
        if t["key"] == table_key:
            return t
    return None


def get_stg_table_by_name(table_name: str) -> dict | None:
    for t in STG_TABLES:
        if t["name"] == table_name:
            return t
    return None


def get_biz_table_by_key(table_key: str) -> dict | None:
    for t in BIZ_TABLES:
        if t["key"] == table_key:
            return t
    return None


def get_biz_table_by_name(table_name: str) -> dict | None:
    for t in BIZ_TABLES:
        if t["name"] == table_name:
            return t
    return None


def get_alg_table_by_key(table_key: str) -> dict | None:
    for t in ALG_TABLES:
        if t["key"] == table_key:
            return t
    return None


def get_alg_table_by_name(table_name: str) -> dict | None:
    for t in ALG_TABLES:
        if t["name"] == table_name:
            return t
    return None
