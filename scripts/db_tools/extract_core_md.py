#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APS 主数据抽取脚本
功能：从 stg_ 原始数据表中抽取数据到 core_md_ 主数据表
使用方法：python extract_core_md.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ============================================================
# 配置区
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
DB_FILE = SCRIPT_DIR / "aps_or.db"

# ============================================================
# core_md_ 系列表结构定义
# ============================================================

CORE_MD_TABLES = {
    # 物料主数据（合并产品、自制件、原材料）
    "core_md_material": """
        CREATE TABLE core_md_material (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_code TEXT NOT NULL,
            material_name TEXT,
            material_type TEXT NOT NULL,  -- product/semi/raw
            product_cost REAL,
            product_price REAL,
            lead_time INTEGER,
            initial_inventory REAL,
            target_inventory REAL,
            min_inventory REAL,
            max_inventory REAL,
            holding_cost_rate REAL,
            is_virtual INTEGER DEFAULT 0,
            purchase_cost REAL,
            purchase_lead_time INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(material_code, material_type)
        )
    """,

    # 产品扩展
    "core_md_product_ext": """
        CREATE TABLE core_md_product_ext (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL UNIQUE,
            product_name TEXT,
            product_cost REAL,
            product_price REAL,
            lead_time INTEGER,
            initial_inventory REAL,
            target_inventory REAL,
            min_inventory REAL,
            max_inventory REAL,
            holding_cost_rate REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # 自制件扩展
    "core_md_semi_ext": """
        CREATE TABLE core_md_semi_ext (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semi_code TEXT NOT NULL UNIQUE,
            semi_name TEXT,
            is_virtual INTEGER DEFAULT 0,
            lead_time INTEGER,
            initial_inventory REAL,
            target_inventory REAL,
            min_inventory REAL,
            max_inventory REAL,
            holding_cost_rate REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # 原材料扩展
    "core_md_raw_ext": """
        CREATE TABLE core_md_raw_ext (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_code TEXT NOT NULL UNIQUE,
            raw_name TEXT,
            purchase_cost REAL,
            purchase_lead_time INTEGER,
            initial_inventory REAL,
            target_inventory REAL,
            min_inventory REAL,
            max_inventory REAL,
            holding_cost_rate REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # 设备/工装资源
    "core_md_resource": """
        CREATE TABLE core_md_resource (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_code TEXT NOT NULL,
            resource_name TEXT,
            resource_type TEXT NOT NULL,  -- equipment/fixture
            unit_cost REAL,
            quantity INTEGER,
            utilization_rate REAL,
            overtime_rate REAL,
            overtime_cost REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(resource_code, resource_type)
        )
    """,

    # 生产线
    "core_md_line": """
        CREATE TABLE core_md_line (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_code TEXT NOT NULL UNIQUE,
            line_name TEXT,
            line_type TEXT DEFAULT 'production',  -- production/assembly/welding/paint/machining
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # 工序定义
    "core_md_operation": """
        CREATE TABLE core_md_operation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_code TEXT NOT NULL UNIQUE,
            operation_name TEXT,
            line_code TEXT,
            equipment_code TEXT,
            fixture_code TEXT,
            fixture_quantity INTEGER DEFAULT 0,
            max_lead_time INTEGER,
            time_offset_1 REAL,
            time_offset_2 REAL,
            time_offset_3 REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # 替代规则静态映射
    "core_md_alt_rule": """
        CREATE TABLE core_md_alt_rule (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alt_type INTEGER NOT NULL,  -- 1:产品替代 2:自制件替代 3:原材料替代
            alt_type_name TEXT,  -- 中文名称
            from_material_code TEXT NOT NULL,
            from_quantity REAL DEFAULT 1,
            to_material_code TEXT NOT NULL,
            to_quantity REAL DEFAULT 1,
            ratio REAL DEFAULT 0,
            is_batch INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# 枚举值映射
ALT_TYPE_NAMES = {
    1: '产品替代',
    2: '自制件替代',
    3: '原材料替代',
}


def create_core_md_tables(conn):
    """创建 core_md_ 系列表"""
    print("=" * 60)
    print("创建 core_md_ 系列表...")
    print("=" * 60)

    for table_name, create_sql in CORE_MD_TABLES.items():
        # 检查表是否已存在
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if cursor.fetchone():
            print(f"  {table_name} 已存在，跳过")
        else:
            conn.execute(create_sql)
            print(f"  ✅ 创建 {table_name}")

    conn.commit()


def extract_material_master(conn):
    """抽取物料主数据（合并产品、自制件、原材料）"""
    print("\n" + "=" * 60)
    print("抽取物料主数据 (core_md_material)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_material")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_material'")

    # 1. 从产品表抽取
    df_product = pd.read_sql_query("SELECT * FROM stg_product", conn)
    product_records = []
    for _, row in df_product.iterrows():
        product_records.append({
            'material_code': row['product_code'],
            'material_name': row['product_name'],
            'material_type': 'product',
            'product_cost': row['product_cost'],
            'product_price': row['product_price'],
            'lead_time': row['lead_time'],
            'initial_inventory': row['initial_inventory'],
            'target_inventory': row['target_inventory'],
            'min_inventory': row['min_inventory'],
            'max_inventory': row['max_inventory'],
            'holding_cost_rate': row['holding_cost_rate'],
            'is_virtual': 0,
            'purchase_cost': None,
            'purchase_lead_time': None,
        })

    # 2. 从自制件表抽取
    df_semi = pd.read_sql_query("SELECT * FROM stg_semi", conn)
    semi_records = []
    for _, row in df_semi.iterrows():
        semi_records.append({
            'material_code': row['semi_code'],
            'material_name': row['semi_name'],
            'material_type': 'semi',
            'product_cost': None,
            'product_price': None,
            'lead_time': row['lead_time'],
            'initial_inventory': row['initial_inventory'],
            'target_inventory': row['target_inventory'],
            'min_inventory': row['min_inventory'],
            'max_inventory': row['max_inventory'],
            'holding_cost_rate': row['holding_cost_rate'],
            'is_virtual': row['is_virtual'],
            'purchase_cost': None,
            'purchase_lead_time': None,
        })

    # 3. 从原材料表抽取
    df_raw = pd.read_sql_query("SELECT * FROM stg_raw", conn)
    raw_records = []
    for _, row in df_raw.iterrows():
        raw_records.append({
            'material_code': row['raw_code'],
            'material_name': row['raw_name'],
            'material_type': 'raw',
            'product_cost': None,
            'product_price': None,
            'lead_time': None,
            'initial_inventory': row['initial_inventory'],
            'target_inventory': row['target_inventory'],
            'min_inventory': row['min_inventory'],
            'max_inventory': row['max_inventory'],
            'holding_cost_rate': row['holding_cost_rate'],
            'is_virtual': 0,
            'purchase_cost': row['purchase_cost'],
            'purchase_lead_time': row['purchase_lead_time'],
        })

    # 合并所有记录并插入
    all_records = product_records + semi_records + raw_records
    columns = ['material_code', 'material_name', 'material_type', 'product_cost',
               'product_price', 'lead_time', 'initial_inventory', 'target_inventory',
               'min_inventory', 'max_inventory', 'holding_cost_rate', 'is_virtual',
               'purchase_cost', 'purchase_lead_time']

    for record in all_records:
        placeholders = ', '.join(['?' for _ in columns])
        sql = f"INSERT INTO core_md_material ({', '.join(columns)}) VALUES ({placeholders})"
        values = [record.get(col) for col in columns]
        conn.execute(sql, values)

    conn.commit()
    print(f"  ✅ 共导入 {len(all_records)} 条物料记录")
    print(f"     - 产品: {len(product_records)} 条")
    print(f"     - 自制件: {len(semi_records)} 条")
    print(f"     - 原材料: {len(raw_records)} 条")


def extract_product_ext(conn):
    """抽取产品扩展数据"""
    print("\n" + "=" * 60)
    print("抽取产品扩展 (core_md_product_ext)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_product_ext")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_product_ext'")

    df = pd.read_sql_query("SELECT * FROM stg_product", conn)
    count = 0
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO core_md_product_ext 
            (product_code, product_name, product_cost, product_price, 
             lead_time, initial_inventory, target_inventory, min_inventory, 
             max_inventory, holding_cost_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['product_code'], row['product_name'], row['product_cost'],
            row['product_price'], row['lead_time'], row['initial_inventory'],
            row['target_inventory'], row['min_inventory'], row['max_inventory'],
            row['holding_cost_rate']
        ))
        count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条产品扩展记录")


def extract_semi_ext(conn):
    """抽取自制件扩展数据"""
    print("\n" + "=" * 60)
    print("抽取自制件扩展 (core_md_semi_ext)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_semi_ext")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_semi_ext'")

    df = pd.read_sql_query("SELECT * FROM stg_semi", conn)
    count = 0
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO core_md_semi_ext 
            (semi_code, semi_name, is_virtual, lead_time, initial_inventory,
             target_inventory, min_inventory, max_inventory, holding_cost_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['semi_code'], row['semi_name'], row['is_virtual'],
            row['lead_time'], row['initial_inventory'], row['target_inventory'],
            row['min_inventory'], row['max_inventory'], row['holding_cost_rate']
        ))
        count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条自制件扩展记录")


def extract_raw_ext(conn):
    """抽取原材料扩展数据"""
    print("\n" + "=" * 60)
    print("抽取原材料扩展 (core_md_raw_ext)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_raw_ext")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_raw_ext'")

    df = pd.read_sql_query("SELECT * FROM stg_raw", conn)
    count = 0
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO core_md_raw_ext 
            (raw_code, raw_name, purchase_cost, purchase_lead_time,
             initial_inventory, target_inventory, min_inventory, max_inventory,
             holding_cost_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['raw_code'], row['raw_name'], row['purchase_cost'],
            row['purchase_lead_time'], row['initial_inventory'],
            row['target_inventory'], row['min_inventory'], row['max_inventory'],
            row['holding_cost_rate']
        ))
        count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条原材料扩展记录")


def extract_resource(conn):
    """抽取设备/工装资源数据"""
    print("\n" + "=" * 60)
    print("抽取设备/工装资源 (core_md_resource)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_resource")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_resource'")

    count = 0

    # 1. 设备
    df_equipment = pd.read_sql_query("SELECT * FROM stg_equipment", conn)
    for _, row in df_equipment.iterrows():
        conn.execute("""
            INSERT INTO core_md_resource 
            (resource_code, resource_name, resource_type, unit_cost, quantity,
             utilization_rate, overtime_rate, overtime_cost)
            VALUES (?, ?, 'equipment', ?, ?, ?, ?, ?)
        """, (
            row['equipment_code'], row['equipment_code'],
            row['unit_cost'], row['quantity'],
            row['utilization_rate'], row['overtime_rate'], row['overtime_cost']
        ))
        count += 1

    # 2. 工装
    df_fixture = pd.read_sql_query("SELECT * FROM stg_fixture", conn)
    for _, row in df_fixture.iterrows():
        conn.execute("""
            INSERT INTO core_md_resource 
            (resource_code, resource_name, resource_type, unit_cost, quantity,
             utilization_rate, overtime_rate, overtime_cost)
            VALUES (?, ?, 'fixture', ?, ?, ?, ?, ?)
        """, (
            row['fixture_code'], row['fixture_code'],
            row['unit_cost'], row['quantity'],
            row['utilization_rate'], row['overtime_rate'], row['overtime_cost']
        ))
        count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条资源记录")
    print(f"     - 设备: {len(df_equipment)} 条")
    print(f"     - 工装: {len(df_fixture)} 条")


def extract_line(conn):
    """抽取生产线数据（从工艺路线表中提取唯一生产线）"""
    print("\n" + "=" * 60)
    print("抽取生产线 (core_md_line)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_line")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_line'")

    # 从工艺路线中提取唯一的生产线
    df = pd.read_sql_query(
        "SELECT DISTINCT production_line FROM stg_routing WHERE production_line IS NOT NULL",
        conn
    )

    # 生产线类型映射
    line_type_map = {
        '涂装线': 'paint',
        '焊接线': 'welding',
        '总装一线': 'assembly',
        '机加一线': 'machining',
    }

    count = 0
    for _, row in df.iterrows():
        line_code = row['production_line']
        if line_code and str(line_code).strip():
            line_type = line_type_map.get(line_code, 'production')
            conn.execute("""
                INSERT INTO core_md_line (line_code, line_name, line_type)
                VALUES (?, ?, ?)
            """, (line_code, line_code, line_type))
            count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条生产线记录")


def extract_operation(conn):
    """抽取工序定义（从工艺路线表中提取）"""
    print("\n" + "=" * 60)
    print("抽取工序定义 (core_md_operation)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_operation")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_operation'")

    # 从工艺路线中提取唯一的工序组合（生产线+工序+设备+工装）
    df = pd.read_sql_query("""
        SELECT DISTINCT 
            operation_name,
            production_line,
            equipment_code,
            fixture_code,
            fixture_quantity,
            max_lead_time,
            time_offset_1,
            time_offset_2,
            time_offset_3
        FROM stg_routing 
        WHERE operation_name IS NOT NULL
    """, conn)

    count = 0
    for idx, row in df.iterrows():
        operation_name = row['operation_name']
        if operation_name and str(operation_name).strip():
            # 生成唯一的工序代码（使用序号确保唯一性）
            op_code = f"OP-{idx+1:03d}"
            
            # 处理 None 值
            fixture_code = row['fixture_code'] if pd.notna(row['fixture_code']) else None
            fixture_quantity = row['fixture_quantity'] if pd.notna(row['fixture_quantity']) else 0
            max_lead_time = row['max_lead_time'] if pd.notna(row['max_lead_time']) else None
            
            conn.execute("""
                INSERT INTO core_md_operation 
                (operation_code, operation_name, line_code, equipment_code,
                 fixture_code, fixture_quantity, max_lead_time, time_offset_1,
                 time_offset_2, time_offset_3)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                op_code,
                operation_name,
                row['production_line'],
                row['equipment_code'],
                fixture_code,
                int(fixture_quantity) if fixture_quantity else 0,
                max_lead_time,
                row['time_offset_1'] if pd.notna(row['time_offset_1']) else None,
                row['time_offset_2'] if pd.notna(row['time_offset_2']) else None,
                row['time_offset_3'] if pd.notna(row['time_offset_3']) else None,
            ))
            count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条工序定义记录")


def extract_alt_rule(conn):
    """抽取替代规则静态映射"""
    print("\n" + "=" * 60)
    print("抽取替代规则 (core_md_alt_rule)...")
    print("=" * 60)

    conn.execute("DELETE FROM core_md_alt_rule")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'core_md_alt_rule'")

    df = pd.read_sql_query("SELECT * FROM stg_alternative", conn)

    count = 0
    for _, row in df.iterrows():
        alt_type = row['alt_type']
        alt_type_name = ALT_TYPE_NAMES.get(alt_type, '未知类型')
        
        conn.execute("""
            INSERT INTO core_md_alt_rule 
            (alt_type, alt_type_name, from_material_code, from_quantity,
             to_material_code, to_quantity, ratio, is_batch)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alt_type,
            alt_type_name,
            row['from_material_code'],
            row['from_quantity'],
            row['to_material_code'],
            row['to_quantity'],
            row['ratio'] if pd.notna(row['ratio']) else 0,
            row['is_batch'] if pd.notna(row['is_batch']) else 0,
        ))
        count += 1

    conn.commit()
    print(f"  ✅ 共导入 {count} 条替代规则记录")


def main():
    """主函数"""
    print("=" * 60)
    print("APS 主数据抽取工具")
    print("=" * 60)
    print(f"数据库文件: {DB_FILE}")
    print()

    # 连接数据库
    conn = sqlite3.connect(str(DB_FILE))

    # 1. 创建 core_md_ 系列表
    create_core_md_tables(conn)

    # 2. 抽取数据
    extract_material_master(conn)
    extract_product_ext(conn)
    extract_semi_ext(conn)
    extract_raw_ext(conn)
    extract_resource(conn)
    extract_line(conn)
    extract_operation(conn)
    extract_alt_rule(conn)

    # 3. 显示各表记录数
    print("\n" + "=" * 60)
    print("✅ 主数据抽取完成！")
    print("=" * 60)

    print("\n📊 core_md_ 各表记录数统计:")
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'core_md_%' ORDER BY name"
    )
    for (table_name,) in cursor.fetchall():
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"   {table_name}: {count} 条")

    conn.close()


if __name__ == "__main__":
    main()
