#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 aps_or.db 的 stg_* 表添加表级和字段级注释说明
使用 SQLite 3.36+ 的 COMMENT 语法
"""

import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_FILE = SCRIPT_DIR / "aps_or.db"

# ============================================================
# 表说明配置
# ============================================================
TABLE_COMMENTS = {
    "stg_system_config": "系统配置表 - 存储APS系统的关键参数和全局配置",
    "stg_orders": "订单表 - 存储客户订单信息，包括产品、数量、交期、优先级等",
    "stg_bom": "BOM表 - 物料清单，定义产品结构和父子物料关系",
    "stg_routing": "工艺路线表 - 定义物料的生产工艺路径、所需设备和工装",
    "stg_equipment": "设备表 - 存储生产设备信息、成本和利用率",
    "stg_fixture": "工装表 - 存储生产工装（夹具、模具等）信息",
    "stg_product": "产品表 - 产品表归集工厂生产的产品的相关参数，本表由序号栏、物料代码栏、生产成本栏、提前期栏、初始库存栏、期末库存栏，最小库存栏、最大库存量、库存成本栏组成。",
    "stg_semi": "自制件表 - 存储半成品/自制件信息",
    "stg_raw": "原材料表 - 存储原材料信息和采购成本",
    "stg_wip": "在制品表 - 存储在制品库存信息",
    "stg_outsource": "外协表 - 存储外协加工订单和各周期的外协需求",
    "stg_purchase_limit": "采购限制表 - 存储各原材料的采购数量限制",
    "stg_alternative": "替代关系表 - 存储物料之间的替代关系",
}

# ============================================================
# 字段说明配置 (key: 表名, value: {列名: 说明})
# ============================================================
COLUMN_COMMENTS = {
    "stg_system_config": {
        "id": "主键ID",
        "config_key": "配置项名称",
        "config_value": "配置项的值",
    },
    "stg_orders": {
        "id": "主键ID",
        "order_id": "订单序号",
        "product_code": "产品代码",
        "order_price": "订单价格（元）",
        "order_quantity": "订单数量",
        "due_period": "订单交期（周期数）",
        "priority_level": "订单等级（数值越大优先级越高）",
        "max_delay_allowed": "允许延期的最大周期数",
        "delay_penalty": "延期罚金系数",
        "production_lead_time": "生产提前期（周期数）",
    },
    "stg_bom": {
        "id": "主键ID",
        "seq": "序号",
        "bom_level": "BOM层级（1=成品, 2=半成品, 3=原材料）",
        "parent_code": "父物料代码",
        "parent_name": "父物料名称",
        "child_code": "子物料代码",
        "child_name": "子物料名称",
        "quantity": "用量",
    },
    "stg_routing": {
        "id": "主键ID",
        "seq": "序号",
        "material_code": "物料代码",
        "material_name": "物料名称",
        "alt_route_id": "多工艺路线编号（0=主工艺）",
        "equipment_code": "设备代码",
        "production_line": "生产线",
        "operation_name": "工序名称",
        "fixture_code": "工装代码",
        "fixture_quantity": "工装数量",
        "max_lead_time": "最大提前时间",
    },
    "stg_equipment": {
        "id": "主键ID",
        "seq": "序号",
        "equipment_code": "设备代码",
        "unit_cost": "单位使用成本（元/小时）",
        "quantity": "设备数量",
        "utilization_rate": "设备利用率（0-1）",
        "overtime_rate": "加班率（0-1）",
        "overtime_cost": "加班成本（元/小时）",
    },
    "stg_fixture": {
        "id": "主键ID",
        "seq": "序号",
        "fixture_code": "工装代码",
        "unit_cost": "工装使用成本（元）",
        "quantity": "工装数量",
        "utilization_rate": "工装利用率（0-1）",
        "overtime_rate": "加班率（0-1）",
        "overtime_cost": "加班成本（元）",
    },
    "stg_product": {
        "id": "主键ID",
        "seq": "序号",
        "product_code": "产品代码",
        "product_name": "产品名称",
        "product_cost": "产品成本（元）",
        "product_price": "产品价格（元）",
        "lead_time": "生产提前期（周期数）",
        "initial_inventory": "初始库存数量",
        "target_inventory": "期末目标库存",
        "min_inventory": "最小安全库存",
        "max_inventory": "最大库存上限",
        "holding_cost_rate": "库存持有成本率（0-1）",
    },
    "stg_semi": {
        "id": "主键ID",
        "seq": "序号",
        "semi_code": "自制件代码",
        "semi_name": "自制件名称",
        "is_virtual": "是否虚拟件（0=否, 1=是）",
        "lead_time": "生产提前期（周期数）",
        "initial_inventory": "初始库存数量",
        "target_inventory": "期末目标库存",
        "min_inventory": "最小安全库存",
        "max_inventory": "最大库存上限",
        "holding_cost_rate": "库存持有成本率（0-1）",
    },
    "stg_raw": {
        "id": "主键ID",
        "seq": "序号",
        "raw_code": "原材料代码",
        "raw_name": "原材料名称",
        "purchase_cost": "采购成本（元）",
        "purchase_lead_time": "采购提前期（周期数）",
        "initial_inventory": "初始库存数量",
        "target_inventory": "期末目标库存",
        "min_inventory": "最小安全库存",
        "max_inventory": "最大库存上限",
        "holding_cost_rate": "库存持有成本率（0-1）",
    },
    "stg_wip": {
        "id": "主键ID",
        "seq": "序号",
        "wip_category": "在制品种类代码",
        "semi_category": "对应自制品种类",
        "material_code": "在制件代码",
        "material_name": "在制件名称",
        "total_lead_time": "总制造周期（周期数）",
        "completed_stages": "已完成的生产阶段数",
        "quantity": "在制品数量",
    },
    "stg_outsource": {
        "id": "主键ID",
        "seq": "序号",
        "material_code": "物料代码",
        "unit_price": "外协单价（元）",
        "total": "合计数量",
    },
    "stg_purchase_limit": {
        "id": "主键ID",
        "seq": "序号",
        "material_code": "原材料代码",
        "material_name": "原材料名称",
        "total": "合计限制数量",
    },
    "stg_alternative": {
        "id": "主键ID",
        "seq": "序号",
        "alt_type": "替代类型（1=完全替代, 2=部分替代）",
        "from_material_code": "替代物料一代码",
        "from_quantity": "替代物料一数量",
        "to_material_code": "替代物料二代码",
        "to_quantity": "替代物料二数量",
        "ratio": "替代比例",
        "is_batch": "是否整批替代（0=否, 1=是）",
    },
}

# 添加周期列的通用说明
PERIOD_COMMENT_TEMPLATE = "第 {n} 周期"


def add_table_comment(conn, table_name, comment):
    """为表添加注释（通过重建表的方式）"""
    try:
        # 检查 SQLite 版本是否支持 COMMENT ON TABLE
        # SQLite 3.36+ 支持在建表时的 COMMENT 语法
        # 但 ALTER TABLE ... COMMENT ON TABLE 从 3.44 开始支持
        # 所以我们使用 PRAGMA table_info 检查当前注释，然后使用变通方法
        
        # 方法：使用 sqlite_master 中的 sql 字段来更新
        cursor = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            print(f"  ⚠️ 无法获取表 {table_name} 的建表语句")
            return False
        
        create_sql = row[0]
        
        # 检查表是否已有注释
        if '-- 表说明:' in create_sql:
            # 更新现有注释
            import re
            new_sql = re.sub(
                r'-- 表说明:.*',
                f'-- 表说明: {comment}',
                create_sql
            )
        else:
            # 在 CREATE TABLE 后添加注释
            new_sql = create_sql.replace(
                f'CREATE TABLE "{table_name}"',
                f'CREATE TABLE "{table_name}" -- 表说明: {comment}'
            )
        
        # 注意：SQLite 不支持直接修改 sqlite_master 中的 sql 字段
        # 所以我们需要另一种方法来存储表注释
        
        # 使用 metadata 表来存储注释
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _table_metadata (
                table_name TEXT PRIMARY KEY,
                comment TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            INSERT OR REPLACE INTO _table_metadata (table_name, comment)
            VALUES (?, ?)
        """, (table_name, comment))
        
        conn.commit()
        print(f"  ✅ 表 {table_name} 注释已更新")
        return True
        
    except Exception as e:
        print(f"  ❌ 表 {table_name} 注释更新失败: {e}")
        return False


def add_column_comment(conn, table_name, column_name, comment):
    """为字段添加注释"""
    try:
        # 创建列注释元数据表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _column_metadata (
                table_name TEXT,
                column_name TEXT,
                comment TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (table_name, column_name)
            )
        """)
        
        conn.execute("""
            INSERT OR REPLACE INTO _column_metadata (table_name, column_name, comment)
            VALUES (?, ?, ?)
        """, (table_name, column_name, comment))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"  ❌ 字段 {table_name}.{column_name} 注释更新失败: {e}")
        return False


def setup_sqlite_native_comments(conn):
    """
    尝试使用 SQLite 原生 COMMENT 语法（需要重建表）
    这是更优的方法，但需要谨慎操作
    """
    print("=" * 60)
    print("检查 SQLite 原生注释支持...")
    print("=" * 60)
    
    # 测试 COMMENT ON COLUMN 语法
    test_table = "_comment_test"
    try:
        # 创建测试表
        conn.execute(f"DROP TABLE IF EXISTS {test_table}")
        conn.execute(f"""
            CREATE TABLE {test_table} (
                id INTEGER COMMENT '测试ID',
                name TEXT COMMENT '测试名称'
            )
        """)
        
        # 检查注释是否被支持
        cursor = conn.execute(f"PRAGMA table_info({test_table})")
        columns = cursor.fetchall()
        
        has_comment = False
        for col in columns:
            if len(col) > 5 and col[5]:  # comment 字段
                has_comment = True
                break
        
        conn.execute(f"DROP TABLE IF EXISTS {test_table}")
        
        if has_comment:
            print("✅ SQLite 原生 COMMENT 语法可用！")
            return True
        else:
            print("⚠️  SQLite 原生 COMMENT 语法存储了但未在 PRAGMA 中返回")
            print("   将使用元数据表方式存储注释")
            return False
            
    except Exception as e:
        print(f"⚠️  SQLite 原生 COMMENT 语法不可用: {e}")
        print("   将使用元数据表方式存储注释")
        return False


def main():
    print("=" * 60)
    print("APS 数据库 - 添加表和字段注释说明")
    print("=" * 60)
    print(f"数据库: {DB_FILE}")
    print()
    
    if not DB_FILE.exists():
        print(f"❌ 数据库文件不存在: {DB_FILE}")
        return
    
    conn = sqlite3.connect(str(DB_FILE))
    
    # 检查原生注释支持
    native_supported = setup_sqlite_native_comments(conn)
    print()
    
    # 创建元数据表
    print("创建元数据表...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _table_metadata (
            table_name TEXT PRIMARY KEY,
            comment TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _column_metadata (
            table_name TEXT,
            column_name TEXT,
            comment TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (table_name, column_name)
        )
    """)
    print("✅ 元数据表创建完成")
    print()
    
    # 添加表注释
    print("=" * 60)
    print("添加表注释...")
    print("=" * 60)
    
    for table_name, comment in TABLE_COMMENTS.items():
        add_table_comment(conn, table_name, comment)
    
    print()
    
    # 添加字段注释
    print("=" * 60)
    print("添加字段注释...")
    print("=" * 60)
    
    total_columns = 0
    for table_name, columns in COLUMN_COMMENTS.items():
        print(f"\n处理表: {table_name}")
        
        # 获取实际的列名（包括 period_01 到 period_28）
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        actual_columns = {col[1] for col in cursor.fetchall()}
        
        added_count = 0
        for col_name, comment in columns.items():
            if col_name in actual_columns:
                if add_column_comment(conn, table_name, col_name, comment):
                    added_count += 1
                    total_columns += 1
                    print(f"  ✅ {col_name}: {comment}")
            else:
                print(f"  ⚠️  列 {col_name} 不存在，跳过")
        
        # 添加周期列注释
        period_cols = [c for c in actual_columns if c.startswith('period_')]
        for period_col in sorted(period_cols):
            # 提取周期数字
            n = int(period_col.replace('period_', ''))
            comment = PERIOD_COMMENT_TEMPLATE.format(n=n)
            if add_column_comment(conn, table_name, period_col, comment):
                added_count += 1
                total_columns += 1
        
        # 添加 total 列注释
        if 'total' in actual_columns:
            add_column_comment(conn, table_name, 'total', '合计数量')
            added_count += 1
            total_columns += 1
            print(f"  ✅ total: 合计数量")
        
        print(f"  共添加 {added_count} 个字段注释")
    
    # 如果原生注释可用，尝试重建表以使用原生注释
    if native_supported:
        print()
        print("=" * 60)
        print("使用 SQLite 原生 COMMENT 语法重建表...")
        print("=" * 60)
        print("⚠️  注意：此操作将重建所有表，可能需要较长时间")
        print("   如需跳过，请按 Ctrl+C")
        print()
        print("由于重建表风险较大，这里仅做说明：")
        print("   可以使用 CREATE TABLE ... COMMENT '...' 语法重建表")
        print("   但建议先备份数据库再执行")
    else:
        print()
        print("=" * 60)
        print("注释存储说明")
        print("=" * 60)
        print("由于 SQLite 版本限制，注释存储在元数据表中：")
        print("  - _table_metadata: 存储表级注释")
        print("  - _column_metadata: 存储字段级注释")
        print()
        print("在 DB Browser for SQLite 中查看：")
        print("  1. 打开 aps_or.db")
        print("  2. 查看 _table_metadata 表获取表注释")
        print("  3. 查看 _column_metadata 表获取字段注释")
    
    conn.close()
    
    print()
    print("=" * 60)
    print(f"✅ 完成！共处理 {len(TABLE_COMMENTS)} 张表，{total_columns} 个字段")
    print("=" * 60)


if __name__ == "__main__":
    main()