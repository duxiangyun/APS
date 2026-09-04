#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APS 优化算法数据库 - ETL 转换脚本
功能：将 stg_ 原始层数据抽取转换到 core_md_（主数据层）和 core_biz_（业务数据层）
使用方法：python etl_stg_to_core.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ============================================================
# 配置区
# ============================================================
DB_FILE = Path(__file__).resolve().parents[2] / "data" / "db" / "aps_or.db"

# ============================================================
# 数据库连接工具（自动开启外键约束）
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================
# ETL 主函数
# ============================================================
def run_etl():
    print("=" * 70)
    print("APS 优化算法数据库 - ETL 转换工具")
    print("stg_ → core_md_ + core_biz_ 数据抽取转换")
    print("=" * 70)

    conn = get_conn()
    cursor = conn.cursor()

    try:
        # ============================================================
        # 第一部分：清空 core_ 层所有表（全量覆盖刷新）
        # ============================================================
        print("\n【步骤 0】清空 core_ 层现有数据...")
        
        core_tables = [
            # core_md_ 主数据层
            "core_md_alt_rule",
            "core_md_raw_ext",
            "core_md_semi_ext",
            "core_md_product_ext",
            "core_md_material",
            "core_md_resource",
            "core_md_line",
            "core_md_operation",
            # core_biz_ 业务数据层
            "core_biz_wip",
            "core_biz_alt_period_limit",
            "core_biz_purchase_period_limit",
            "core_biz_outsource_period_limit",
            "core_biz_step_time_offset",
            "core_biz_routing_step",
            "core_biz_routing_header",
            "core_biz_bom",
            "core_biz_demand_order",
            "core_biz_global_params",
        ]
        
        for table in core_tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
                # 重置自增 ID 计数器，确保可重复执行时 ID 从 1 开始
                cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
            except sqlite3.OperationalError:
                pass  # 表可能不存在，跳过
        
        print("✅ core_ 层所有表已清空")
        conn.commit()

        # ============================================================
        # 第二部分：抽取 core_md_ 主数据层
        # ============================================================
        print("\n【步骤 1】抽取 core_md_ 主数据层...")

        # 1.1 生产线主数据（从 stg_routing 提取去重）
        print("  → 1.1 生产线主数据 (core_md_line)...")
        cursor.execute("""
            INSERT INTO core_md_line (line_code, line_name, line_type)
            SELECT DISTINCT 
                production_line,
                production_line,
                CASE 
                    WHEN production_line LIKE '%涂装%' THEN 'PAINT'
                    WHEN production_line LIKE '%焊接%' THEN 'WELD'
                    WHEN production_line LIKE '%总装%' THEN 'ASSEMBLY'
                    WHEN production_line LIKE '%机加%' THEN 'MACHINING'
                    ELSE NULL
                END
            FROM stg_routing
            WHERE production_line IS NOT NULL AND production_line != ''
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 1.2 工序定义主数据（从 stg_routing 提取去重）
        print("  → 1.2 工序定义 (core_md_operation)...")
        cursor.execute("""
            INSERT INTO core_md_operation (operation_code, operation_name)
            SELECT DISTINCT 
                'OP-' || REPLACE(operation_name, ' ', '_'),
                operation_name
            FROM stg_routing
            WHERE operation_name IS NOT NULL AND operation_name != ''
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 1.3 资源主数据（设备 + 工装合并）
        print("  → 1.3 资源主数据 (core_md_resource)...")
        # 先插入设备
        cursor.execute("""
            INSERT INTO core_md_resource (
                resource_code, resource_name, resource_type, 
                quantity, unit_cost, utilization_rate, overtime_rate, overtime_cost_multiplier
            )
            SELECT 
                equipment_code,
                equipment_code,
                'EQUIPMENT',
                quantity,
                unit_cost,
                utilization_rate,
                overtime_rate,
                overtime_cost
            FROM stg_equipment
            WHERE equipment_code IS NOT NULL AND equipment_code != ''
        """)
        device_count = cursor.rowcount

        # 再插入工装
        cursor.execute("""
            INSERT INTO core_md_resource (
                resource_code, resource_name, resource_type, 
                quantity, unit_cost, utilization_rate, overtime_rate, overtime_cost_multiplier
            )
            SELECT 
                fixture_code,
                fixture_code,
                'FIXTURE',
                quantity,
                unit_cost,
                utilization_rate,
                overtime_rate,
                overtime_cost
            FROM stg_fixture
            WHERE fixture_code IS NOT NULL AND fixture_code != ''
        """)
        fixture_count = cursor.rowcount
        print(f"    插入设备 {device_count} 条 + 工装 {fixture_count} 条 = {device_count + fixture_count} 条记录")

        # 1.4 物料主数据（合并产品 + 自制件 + 原材料）
        print("  → 1.4 物料主数据 (core_md_material)...")

        # 插入产品（产品名称直接取自 stg_product 的 product_name 列）
        cursor.execute("""
            INSERT INTO core_md_material (
                material_code, material_name, category,
                initial_inventory, target_end_inventory, 
                min_inventory, max_inventory, holding_cost_rate
            )
            SELECT 
                p.product_code,
                COALESCE(p.product_name, p.product_code),
                'PRODUCT',
                p.initial_inventory,
                p.target_inventory,
                p.min_inventory,
                p.max_inventory,
                p.holding_cost_rate
            FROM stg_product p
            WHERE p.product_code IS NOT NULL AND p.product_code != ''
        """)
        product_count = cursor.rowcount

        # 插入自制件
        cursor.execute("""
            INSERT INTO core_md_material (
                material_code, material_name, category,
                initial_inventory, target_end_inventory, 
                min_inventory, max_inventory, holding_cost_rate
            )
            SELECT 
                semi_code,
                semi_name,
                'SEMI',
                initial_inventory,
                target_inventory,
                min_inventory,
                max_inventory,
                holding_cost_rate
            FROM stg_semi
            WHERE semi_code IS NOT NULL AND semi_code != ''
        """)
        semi_count = cursor.rowcount

        # 插入原材料
        cursor.execute("""
            INSERT INTO core_md_material (
                material_code, material_name, category,
                initial_inventory, target_end_inventory, 
                min_inventory, max_inventory, holding_cost_rate
            )
            SELECT 
                raw_code,
                raw_name,
                'RAW',
                initial_inventory,
                target_inventory,
                min_inventory,
                max_inventory,
                holding_cost_rate
            FROM stg_raw
            WHERE raw_code IS NOT NULL AND raw_code != ''
        """)
        raw_count = cursor.rowcount
        print(f"    插入产品 {product_count} + 自制件 {semi_count} + 原材料 {raw_count} = {product_count + semi_count + raw_count} 条记录")

        # 1.5 产品扩展表
        print("  → 1.5 产品扩展 (core_md_product_ext)...")
        cursor.execute("""
            INSERT INTO core_md_product_ext (
                material_code, standard_cost, standard_price, assembly_lead_time
            )
            SELECT 
                product_code,
                product_cost,
                product_price,
                lead_time
            FROM stg_product
            WHERE product_code IS NOT NULL AND product_code != ''
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 1.6 自制件扩展表
        print("  → 1.6 自制件扩展 (core_md_semi_ext)...")
        cursor.execute("""
            INSERT INTO core_md_semi_ext (
                material_code, is_virtual, manufacturing_lead_time, scrap_rate
            )
            SELECT 
                semi_code,
                is_virtual,
                lead_time,
                0
            FROM stg_semi
            WHERE semi_code IS NOT NULL AND semi_code != ''
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 1.6.1 同步外协价格：stg_outsource.unit_price → core_md_semi_ext.outsource_price
        cursor.execute("""
            UPDATE core_md_semi_ext
            SET outsource_price = (
                SELECT o.unit_price
                FROM stg_outsource o
                WHERE o.material_code = core_md_semi_ext.material_code
            )
            WHERE material_code IN (
                SELECT material_code FROM stg_outsource
            )
        """)
        print(f"    同步外协价格 {cursor.rowcount} 条记录")

        # 1.7 原材料扩展表
        print("  → 1.7 原材料扩展 (core_md_raw_ext)...")
        cursor.execute("""
            INSERT INTO core_md_raw_ext (
                material_code, purchase_cost, purchase_lead_time, moq
            )
            SELECT 
                raw_code,
                purchase_cost,
                purchase_lead_time,
                0
            FROM stg_raw
            WHERE raw_code IS NOT NULL AND raw_code != ''
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 1.8 替代规则表（静态映射，不含周期限额）
        print("  → 1.8 替代规则 (core_md_alt_rule)...")
        cursor.execute("""
            INSERT INTO core_md_alt_rule (
                alt_type, from_material_code, to_material_code,
                from_quantity, to_quantity, ratio, is_batch
            )
            SELECT 
                alt_type,
                from_material_code,
                to_material_code,
                from_quantity,
                to_quantity,
                ratio,
                is_batch
            FROM stg_alternative
            WHERE from_material_code IS NOT NULL AND to_material_code IS NOT NULL
            ORDER BY seq
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        conn.commit()

        # ============================================================
        # 第三部分：抽取 core_biz_ 业务数据层
        # ============================================================
        print("\n【步骤 2】抽取 core_biz_ 业务数据层...")

        # 2.1 全局参数（从综合表提取）
        print("  → 2.1 全局排产参数 (core_biz_global_params)...")
        
        # 参数映射表：Excel 参数名 → 数据库 key
        param_mapping = {
            '计划期长度': ('PLAN_HORIZON', '计划期长度'),
            '每班时长（分钟）': ('SHIFT_DURATION_MINUTES', '每班时长（分钟）'),
            '每期班次数': ('SHIFTS_PER_PERIOD', '每期班次数'),
            '订单等级': ('ORDER_PRIORITY_LEVELS', '订单等级'),
            '最多替代工艺数': ('MAX_ALTERNATE_ROUTES', '最多替代工艺数'),
            '最大加工周期': ('MAX_PROCESSING_CYCLE', '最大加工周期'),
            '需求率': ('DEMAND_RATE', '需求率'),
            '订单最大允许延期': ('MAX_DELAY_ALLOWED', '订单最大允许延期'),
            '工装表': ('LOAD_FLAG_FIXTURE', '读入数据表 工装表'),
            '外协表': ('LOAD_FLAG_OUTSOURCE', '读入数据表 外协表'),
            '采购限制表': ('LOAD_FLAG_PURCHASE_LIMIT', '读入数据表 采购限制表'),
            '替代关系表': ('LOAD_FLAG_ALTERNATIVE', '读入数据表 替代关系表'),
            '在制品表': ('LOAD_FLAG_WIP', '读入数据表 在制品表'),
            'BOM表记录数': ('STAT_BOM_RECORDS', 'BOM表记录数'),
            '工艺路线表记录数': ('STAT_ROUTING_RECORDS', '工艺路线表记录数'),
            '订单表记录数': ('STAT_ORDER_RECORDS', '订单表记录数'),
            '工厂数': ('NUM_FACTORIES', '工厂数'),
            '设备数': ('STAT_NUM_EQUIPMENTS', '设备数'),
            '工装数': ('STAT_NUM_FIXTURES', '工装数'),
            '产品数': ('STAT_NUM_PRODUCTS', '产品数'),
            '自制产品数': ('STAT_NUM_SEMIS', '自制产品数'),
            '原料数': ('STAT_NUM_RAWS', '原料数'),
        }
        
        param_count = 0
        for excel_key, (db_key, desc) in param_mapping.items():
            cursor.execute(
                "SELECT config_value FROM stg_system_config WHERE config_key = ?",
                (excel_key,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "INSERT OR REPLACE INTO core_biz_global_params (param_key, param_value, description) VALUES (?, ?, ?)",
                    (db_key, row['config_value'], desc)
                )
                param_count += 1
        
        print(f"    插入 {param_count} 条记录")

        # 2.2 BOM 定义
        print("  → 2.2 BOM 定义 (core_biz_bom)...")
        cursor.execute("""
            INSERT INTO core_biz_bom (
                parent_material_code, child_material_code, quantity, bom_level
            )
            SELECT 
                parent_code,
                child_code,
                quantity,
                bom_level
            FROM stg_bom
            WHERE parent_code IS NOT NULL AND child_code IS NOT NULL
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.3 订单表
        print("  → 2.3 订单表 (core_biz_demand_order)...")
        cursor.execute("""
            INSERT INTO core_biz_demand_order (
                order_id, product_code, price, quantity, 
                due_period, priority_level, max_delay_allowed, delay_penalty
            )
            SELECT 
                order_id,
                product_code,
                order_price,
                order_quantity,
                due_period,
                priority_level,
                max_delay_allowed,
                delay_penalty
            FROM stg_orders
            WHERE order_id IS NOT NULL
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.4 工艺路线头表
        print("  → 2.4 工艺路线头表 (core_biz_routing_header)...")
        cursor.execute("""
            INSERT INTO core_biz_routing_header (
                material_code, alt_route_id, total_lead_time, is_default, is_active
            )
            SELECT 
                material_code,
                alt_route_id,
                MAX(max_lead_time),  -- 该物料+工艺的所有工序 MaxT 相同，取 MAX 即可
                1,
                1
            FROM stg_routing
            WHERE material_code IS NOT NULL AND material_code != ''
            GROUP BY material_code, alt_route_id
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.5 工艺步骤定义表
        print("  → 2.5 工艺步骤定义表 (core_biz_routing_step)...")
        cursor.execute("""
            INSERT INTO core_biz_routing_step (
                routing_id, step_order, operation_code, equipment_code,
                production_line_code, fixture_code, fixture_quantity, max_lead_time
            )
            SELECT 
                h.routing_id,
                r.seq,
                'OP-' || REPLACE(r.operation_name, ' ', '_'),
                r.equipment_code,
                r.production_line,
                r.fixture_code,
                COALESCE(r.fixture_quantity, 0),
                r.max_lead_time
            FROM stg_routing r
            JOIN core_biz_routing_header h 
                ON r.material_code = h.material_code 
                AND r.alt_route_id = h.alt_route_id
            WHERE r.equipment_code IS NOT NULL AND r.equipment_code != ''
            ORDER BY r.material_code, r.alt_route_id, r.seq
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.6 步骤工时偏移明细表（横向 1/2/3 列 → 纵向行）
        print("  → 2.6 步骤工时偏移明细 (core_biz_step_time_offset)...")
        
        # 先创建临时表，展开横向列
        cursor.execute("""
            CREATE TEMP TABLE temp_time_offsets AS
            SELECT 
                s.step_id,
                r.max_lead_time as total_lead_time,
                1 as offset_index, r.time_offset_1 as duration
            FROM stg_routing r
            JOIN core_biz_routing_header h 
                ON r.material_code = h.material_code 
                AND r.alt_route_id = h.alt_route_id
            JOIN core_biz_routing_step s
                ON h.routing_id = s.routing_id 
                AND r.seq = s.step_order
            WHERE r.time_offset_1 IS NOT NULL AND r.time_offset_1 > 0
            
            UNION ALL
            
            SELECT 
                s.step_id,
                r.max_lead_time,
                2, r.time_offset_2
            FROM stg_routing r
            JOIN core_biz_routing_header h 
                ON r.material_code = h.material_code 
                AND r.alt_route_id = h.alt_route_id
            JOIN core_biz_routing_step s
                ON h.routing_id = s.routing_id 
                AND r.seq = s.step_order
            WHERE r.time_offset_2 IS NOT NULL AND r.time_offset_2 > 0
            
            UNION ALL
            
            SELECT 
                s.step_id,
                r.max_lead_time,
                3, r.time_offset_3
            FROM stg_routing r
            JOIN core_biz_routing_header h 
                ON r.material_code = h.material_code 
                AND r.alt_route_id = h.alt_route_id
            JOIN core_biz_routing_step s
                ON h.routing_id = s.routing_id 
                AND r.seq = s.step_order
            WHERE r.time_offset_3 IS NOT NULL AND r.time_offset_3 > 0
        """)
        
        cursor.execute("""
            INSERT INTO core_biz_step_time_offset (step_id, offset_index, duration)
            SELECT step_id, offset_index, duration
            FROM temp_time_offsets
            WHERE duration > 0
            ORDER BY step_id, offset_index
        """)
        print(f"    插入 {cursor.rowcount} 条记录")
        cursor.execute("DROP TABLE temp_time_offsets")

        # 2.7 外协周期限额（横向 1~28 列 → 纵向行）
        print("  → 2.7 外协周期限额 (core_biz_outsource_period_limit)...")
        # 构建动态 SQL 展开 1~28 列
        period_values = []
        for i in range(1, 29):
            period_col = f"period_{i:02d}"
            period_values.append(f"SELECT material_code, {i} as period_index, {period_col} as max_quantity FROM stg_outsource WHERE {period_col} IS NOT NULL AND {period_col} > 0")
        
        cursor.execute(f"""
            INSERT INTO core_biz_outsource_period_limit (material_code, period_index, max_quantity)
            { ' UNION ALL '.join(period_values) }
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.8 采购周期限额（横向 1~28 列 → 纵向行）
        print("  → 2.8 采购周期限额 (core_biz_purchase_period_limit)...")
        period_values = []
        for i in range(1, 29):
            period_col = f"period_{i:02d}"
            period_values.append(f"SELECT material_code, {i} as period_index, {period_col} as max_purchase_quantity FROM stg_purchase_limit WHERE {period_col} IS NOT NULL AND {period_col} > 0")
        
        cursor.execute(f"""
            INSERT INTO core_biz_purchase_period_limit (material_code, period_index, max_purchase_quantity)
            { ' UNION ALL '.join(period_values) }
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.9 替代周期限额（横向 1~28 列 → 纵向行）
        print("  → 2.9 替代周期限额 (core_biz_alt_period_limit)...")
        # 直接关联 core_md_alt_rule 获取真实的 rule_id 主键
        period_values = []
        for i in range(1, 29):
            period_col = f"period_{i:02d}"
            period_values.append(f"""
                SELECT ar.rule_id, {i} as period_index, a.{period_col} as max_alternative_quantity
                FROM stg_alternative a
                JOIN core_md_alt_rule ar 
                    ON a.from_material_code = ar.from_material_code
                    AND a.to_material_code = ar.to_material_code
                    AND a.alt_type = ar.alt_type
                WHERE a.{period_col} IS NOT NULL AND a.{period_col} > 0
            """)
        
        cursor.execute(f"""
            INSERT INTO core_biz_alt_period_limit (rule_id, period_index, max_alternative_quantity)
            { ' UNION ALL '.join(period_values) }
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        # 2.10 在制品主表
        print("  → 2.10 在制品主表 (core_biz_wip)...")
        cursor.execute("""
            INSERT INTO core_biz_wip (
                material_code, quantity, completed_stages
            )
            SELECT 
                material_code,
                quantity,
                completed_stages
            FROM stg_wip
            WHERE material_code IS NOT NULL AND material_code != ''
        """)
        print(f"    插入 {cursor.rowcount} 条记录")

        conn.commit()

        # ============================================================
        # 第四部分：数据统计与验证
        # ============================================================
        print("\n【步骤 3】数据统计与验证...")
        print("-" * 70)
        print(f"{'表名':<40} {'记录数':>10}")
        print("-" * 70)

        stats_tables = [
            ("core_md_material",),
            ("core_md_product_ext",),
            ("core_md_semi_ext",),
            ("core_md_raw_ext",),
            ("core_md_line",),
            ("core_md_resource",),
            ("core_md_operation",),
            ("core_md_alt_rule",),
            ("core_biz_bom",),
            ("core_biz_demand_order",),
            ("core_biz_routing_header",),
            ("core_biz_routing_step",),
            ("core_biz_step_time_offset",),
            ("core_biz_outsource_period_limit",),
            ("core_biz_purchase_period_limit",),
            ("core_biz_alt_period_limit",),
            ("core_biz_wip",),
            ("core_biz_global_params",),
        ]

        total_rows = 0
        for (table_name,) in stats_tables:
            try:
                count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"{table_name:<40} {count:>10}")
                total_rows += count
            except sqlite3.OperationalError:
                print(f"{table_name:<40} {'（表不存在）':>10}")

        print("-" * 70)
        print(f"{'合计':<40} {total_rows:>10}")
        print("=" * 70)
        print("✅ ETL 转换完成！")

    except Exception as e:
        print(f"\n❌ ETL 执行失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 入口函数
# ============================================================
if __name__ == "__main__":
    run_etl()