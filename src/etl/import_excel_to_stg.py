#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APS 优化算法数据库 - Excel 数据导入脚本
功能：将 APS-JD.xls 各 Sheet 导入到 aps_or.db 的 stg_ 原始表中
使用方法：python import_excel_to_stg.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ============================================================
# 配置区
# ============================================================
_PROJECT_DIR = Path(__file__).resolve().parents[2]
EXCEL_FILE = str(_PROJECT_DIR / "data" / "input" / "APS-JD.xls")   # Excel 文件路径
DB_FILE = str(_PROJECT_DIR / "data" / "db" / "aps_or.db")         # SQLite 数据库文件路径


def get_sheet_mapping():
    """
    定义 Excel Sheet 名称与目标表名、字段映射的对应关系
    """
    mapping = {
        "综合表": {
            "table": "stg_system_config",
            "columns": {"主要参数": "config_key", "参数值": "config_value"},
            "skip_rows": 3,
        },
        "订单表": {
            "table": "stg_orders",
            "columns": {
                "订单序号": "order_id",
                "产品代码": "product_code",
                "订单价格": "order_price",
                "订单数量": "order_quantity",
                "订单交期": "due_period",
                "订单等级": "priority_level",
                "允许延期": "max_delay_allowed",
                "延期罚金": "delay_penalty",
                "生产提前期": "production_lead_time",
            }
        },
        "BOM": {
            "table": "stg_bom",
            "columns": {
                "序号": "seq",
                "BOM层级": "bom_level",
                "父物料": "parent_code",
                "父物料名称": "parent_name",
                "子物料": "child_code",
                "子物料名称": "child_name",
                "数量": "quantity",
            }
        },
        "工艺路线": {
            "table": "stg_routing",
            "columns": {
                "序号": "seq",
                "物料代码": "material_code",
                "物料名称": "material_name",
                "多工艺": "alt_route_id",
                "设备代码": "equipment_code",
                "生产线": "production_line",
                "工序": "operation_name",
                "工装代码": "fixture_code",
                "工装数量": "fixture_quantity",
                "MaxT": "max_lead_time",
                "1": "time_offset_1",
                "2": "time_offset_2",
                "3": "time_offset_3",
            }
        },
        "设备表": {
            "table": "stg_equipment",
            "columns": {
                "序号": "seq",
                "设备代码": "equipment_code",
                "单位成本": "unit_cost",
                "设备数": "quantity",
                "设备利用率": "utilization_rate",
                "加班率": "overtime_rate",
                "加班成本": "overtime_cost",
            }
        },
        "工装表": {
            "table": "stg_fixture",
            "columns": {
                "序号": "seq",
                "工装代码": "fixture_code",
                "工装成本": "unit_cost",
                "工装数": "quantity",
                "工装利用率": "utilization_rate",
                "加班率": "overtime_rate",
                "加班成本": "overtime_cost",
            }
        },
        "产品表": {
            "table": "stg_product",
            "columns": {
                "序号": "seq",
                "产品代码": "product_code",
                "产品成本": "product_cost",
                "产品价格": "product_price",
                "提前期": "lead_time",
                "初始库存": "initial_inventory",
                "期末库存": "target_inventory",
                "最小库存": "min_inventory",
                "最大库存": "max_inventory",
                "库存成本": "holding_cost_rate",
            }
        },
        "自制件": {
            "table": "stg_semi",
            "columns": {
                "序号": "seq",
                "自制件代码": "semi_code",
                "自制件名称": "semi_name",
                "虚拟件属性": "is_virtual",
                "提前期": "lead_time",
                "初始库存": "initial_inventory",
                "期末库存": "target_inventory",
                "最小库存": "min_inventory",
                "最大库存": "max_inventory",
                "库存成本": "holding_cost_rate",
            }
        },
        "原材料表": {
            "table": "stg_raw",
            "columns": {
                "序号": "seq",
                "原料代码": "raw_code",
                "": "raw_name",  # 第3列无列名
                "采购成本": "purchase_cost",
                "采购提前期": "purchase_lead_time",
                "初始库存": "initial_inventory",
                "期末库存": "target_inventory",
                "最小库存": "min_inventory",
                "最大库存": "max_inventory",
                "库存成本": "holding_cost_rate",
            }
        },
        "在制品": {
            "table": "stg_wip",
            "columns": {
                "序号": "seq",
                "在制品种类代码": "wip_category",
                "自制品种类": "semi_category",
                "在制件代码": "material_code",
                "在制件名称": "material_name",
                "总制造期": "total_lead_time",
                "已完成阶段": "completed_stages",
                "在制数量": "quantity",
            }
        },
        "外协": {
            "table": "stg_outsource",
            "columns": {
                "序号": "seq",
                "物料代码": "material_code",
                "外协价格": "unit_price",
                "1": "period_01",
                "2": "period_02",
                # ... 3~28 省略，完整版见前文
                "合计": "total",
            }
        },
        "采购限制": {
            "table": "stg_purchase_limit",
            "columns": {
                "序号": "seq",
                "原料代码": "material_code",
                "": "material_name",
                "1": "period_01",
                # ... 2~28 省略
                "合计": "total",
            }
        },
        "替代关系": {
            "table": "stg_alternative",
            "columns": {
                "序号": "seq",
                "替代类型": "alt_type",
                "替代物料一代码": "from_material_code",
                "数量一": "from_quantity",
                "替代物料二代码": "to_material_code",
                "数量二": "to_quantity",
                "比例": "ratio",
                "整批": "is_batch",
                "1": "period_01",
                # ... 2~28 省略
            }
        },
    }
    return mapping


def import_sheet(conn, sheet_name, sheet_df, table_name, column_mapping, skip_rows=0):
    """将单个 Sheet 的数据导入到指定的 stg_ 表中"""
    # ...（完整逻辑见前文）


def import_system_config(conn, excel_file):
    """特殊处理：从综合表中提取主要参数"""
    # ...（完整逻辑见前文）


def main():
    # ...（完整逻辑见前文）


if __name__ == "__main__":
    main()