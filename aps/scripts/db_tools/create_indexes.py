#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APS 数据库索引创建脚本
功能：为 aps_or.db 中的 core_ 系列表创建缺失的索引
使用方法：python create_indexes.py
"""

import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_FILE = SCRIPT_DIR / "aps_or.db"

# ============================================================
# 索引定义
# ============================================================
# 设计原则：
# 1. 外键列必须有索引（SQLite 不会自动为外键创建索引）
# 2. JOIN 高频列
# 3. WHERE 高频过滤列
# 4. ORDER BY 排序列

INDEXES = [
    # ==================== 已存在的索引（保留，幂等执行） ====================
    # core_biz_routing_header
    "CREATE INDEX IF NOT EXISTS idx_core_biz_routing_material ON core_biz_routing_header(material_code)",
    # core_biz_routing_step
    "CREATE INDEX IF NOT EXISTS idx_core_biz_step_routing ON core_biz_routing_step(routing_id)",
    "CREATE INDEX IF NOT EXISTS idx_core_biz_step_equipment ON core_biz_routing_step(equipment_code)",
    "CREATE INDEX IF NOT EXISTS idx_core_biz_step_line ON core_biz_routing_step(production_line_code)",
    # core_biz_alt_period_limit
    "CREATE INDEX IF NOT EXISTS idx_core_biz_alt_period ON core_biz_alt_period_limit(period_index)",
    # core_biz_outsource_period_limit
    "CREATE INDEX IF NOT EXISTS idx_core_biz_outsource_period ON core_biz_outsource_period_limit(period_index)",
    # core_biz_purchase_period_limit
    "CREATE INDEX IF NOT EXISTS idx_core_biz_purchase_period ON core_biz_purchase_period_limit(period_index)",

    # ==================== 外键列索引（缺失补全） ====================
    # core_biz_bom: 两个外键都指向 core_md_material.material_code
    "CREATE INDEX IF NOT EXISTS idx_core_biz_bom_parent ON core_biz_bom(parent_material_code)",
    "CREATE INDEX IF NOT EXISTS idx_core_biz_bom_child ON core_biz_bom(child_material_code)",
    # core_biz_demand_order.product_code → core_md_material.material_code
    "CREATE INDEX IF NOT EXISTS idx_core_biz_order_product ON core_biz_demand_order(product_code)",
    # core_biz_wip.material_code → core_md_material.material_code
    "CREATE INDEX IF NOT EXISTS idx_core_biz_wip_material ON core_biz_wip(material_code)",
    # core_biz_routing_step 两个缺失外键
    "CREATE INDEX IF NOT EXISTS idx_core_biz_step_fixture ON core_biz_routing_step(fixture_code)",
    "CREATE INDEX IF NOT EXISTS idx_core_biz_step_operation ON core_biz_routing_step(operation_code)",
    # core_md_resource.line_code → core_md_line.line_code
    "CREATE INDEX IF NOT EXISTS idx_core_md_resource_line ON core_md_resource(line_code)",

    # ==================== JOIN 高频列（非外键但参与 JOIN） ====================
    # core_md_alt_rule: 替代关系视图中频繁 JOIN material_code
    "CREATE INDEX IF NOT EXISTS idx_core_md_alt_from ON core_md_alt_rule(from_material_code)",
    "CREATE INDEX IF NOT EXISTS idx_core_md_alt_to ON core_md_alt_rule(to_material_code)",

    # ==================== WHERE 高频过滤列 ====================
    # core_md_material: WHERE category = 'PRODUCT'/'SEMI'/'RAW'
    "CREATE INDEX IF NOT EXISTS idx_core_md_material_category ON core_md_material(category)",
    # core_md_resource: WHERE resource_type = 'EQUIPMENT'/'FIXTURE'
    "CREATE INDEX IF NOT EXISTS idx_core_md_resource_type ON core_md_resource(resource_type)",
    # core_biz_routing_header: WHERE is_active = 1
    "CREATE INDEX IF NOT EXISTS idx_core_biz_routing_active ON core_biz_routing_header(is_active)",
    # core_biz_demand_order: 排程查询按交期过滤
    "CREATE INDEX IF NOT EXISTS idx_core_biz_order_due ON core_biz_demand_order(due_period)",
    # core_md_alt_rule: WHERE is_active 过滤
    "CREATE INDEX IF NOT EXISTS idx_core_md_alt_active ON core_md_alt_rule(is_active)",

    # ==================== 复合索引（覆盖 JOIN + ORDER BY） ====================
    # core_biz_routing_step: (routing_id, step_order) 覆盖 JOIN + ORDER BY
    "CREATE INDEX IF NOT EXISTS idx_core_biz_step_order ON core_biz_routing_step(routing_id, step_order)",
]


def create_indexes(db_path):
    """创建所有索引"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print(f"连接数据库: {db_path}")
    print(f"共有 {len(INDEXES)} 个索引待创建\n")

    success = 0
    failed = 0
    skipped = 0

    for sql in INDEXES:
        idx_name = sql.split("CREATE INDEX IF NOT EXISTS ")[1].split(" ON ")[0]
        try:
            cursor.execute(sql)
            # 检查是否真正创建了还是跳过了
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (idx_name,),
            )
            if cursor.fetchone():
                # 检查是否是 sqlite 自动创建的（pk 索引）还是我们新建的
                success += 1
                print(f"  ✅ {idx_name}")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                skipped += 1
                print(f"  ⏭️  {idx_name} (已存在，跳过)")
            else:
                failed += 1
                print(f"  ❌ {idx_name}: {e}")

    conn.commit()
    conn.close()

    print(f"\n完成！成功: {success}, 跳过: {skipped}, 失败: {failed}")
    return failed == 0


def list_indexes(db_path):
    """列出所有用户创建的索引"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tbl_name, name FROM sqlite_master
        WHERE type='index' AND name NOT LIKE 'sqlite_%'
        ORDER BY tbl_name, name
    """)
    indexes = cursor.fetchall()

    print(f"\n=== 当前所有用户索引 ({len(indexes)} 个) ===")
    for tbl, name in indexes:
        print(f"  [{tbl}] {name}")

    conn.close()
    return indexes


if __name__ == "__main__":
    if not DB_FILE.exists():
        print(f"错误：数据库文件不存在: {DB_FILE}")
    else:
        ok = create_indexes(DB_FILE)
        list_indexes(DB_FILE)
        exit(0 if ok else 1)
