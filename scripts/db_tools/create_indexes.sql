-- ============================================================
-- aps_or.db 索引脚本
-- 自动生成自 create_indexes.py，请勿手工编辑
-- 数据库: data/db/aps_or.db
-- 生成时间: 2026-09-04
-- ============================================================
-- 设计原则：
-- 1. 外键列必须有索引（SQLite 不会自动为外键创建索引）
-- 2. JOIN 高频列
-- 3. WHERE 高频过滤列
-- 4. ORDER BY 排序列
-- 使用方法：sqlite3 data/db/aps_or.db < scripts/db_tools/create_indexes.sql
-- ============================================================

-- ============================================================
-- 一、已存在的索引（幂等执行，IF NOT EXISTS 保障可重复运行）
-- ============================================================

-- core_biz_routing_header
CREATE INDEX IF NOT EXISTS idx_core_biz_routing_material ON core_biz_routing_header(material_code);

-- core_biz_routing_step
CREATE INDEX IF NOT EXISTS idx_core_biz_step_routing ON core_biz_routing_step(routing_id);
CREATE INDEX IF NOT EXISTS idx_core_biz_step_equipment ON core_biz_routing_step(equipment_code);
CREATE INDEX IF NOT EXISTS idx_core_biz_step_line ON core_biz_routing_step(production_line_code);

-- core_biz_alt_period_limit
CREATE INDEX IF NOT EXISTS idx_core_biz_alt_period ON core_biz_alt_period_limit(period_index);

-- core_biz_outsource_period_limit
CREATE INDEX IF NOT EXISTS idx_core_biz_outsource_period ON core_biz_outsource_period_limit(period_index);

-- core_biz_purchase_period_limit
CREATE INDEX IF NOT EXISTS idx_core_biz_purchase_period ON core_biz_purchase_period_limit(period_index);

-- ============================================================
-- 二、外键列索引（缺失补全）
-- ============================================================

-- core_biz_bom: 两个外键都指向 core_md_material.material_code
CREATE INDEX IF NOT EXISTS idx_core_biz_bom_parent ON core_biz_bom(parent_material_code);
CREATE INDEX IF NOT EXISTS idx_core_biz_bom_child ON core_biz_bom(child_material_code);

-- core_biz_demand_order.product_code → core_md_material.material_code
CREATE INDEX IF NOT EXISTS idx_core_biz_order_product ON core_biz_demand_order(product_code);

-- core_biz_wip.material_code → core_md_material.material_code
CREATE INDEX IF NOT EXISTS idx_core_biz_wip_material ON core_biz_wip(material_code);

-- core_biz_routing_step 两个缺失外键
CREATE INDEX IF NOT EXISTS idx_core_biz_step_fixture ON core_biz_routing_step(fixture_code);
CREATE INDEX IF NOT EXISTS idx_core_biz_step_operation ON core_biz_routing_step(operation_code);

-- core_md_resource.line_code → core_md_line.line_code
CREATE INDEX IF NOT EXISTS idx_core_md_resource_line ON core_md_resource(line_code);

-- ============================================================
-- 三、JOIN 高频列（非外键但参与 JOIN）
-- ============================================================

-- core_md_alt_rule: 替代关系视图中频繁 JOIN material_code
CREATE INDEX IF NOT EXISTS idx_core_md_alt_from ON core_md_alt_rule(from_material_code);
CREATE INDEX IF NOT EXISTS idx_core_md_alt_to ON core_md_alt_rule(to_material_code);

-- ============================================================
-- 四、WHERE 高频过滤列
-- ============================================================

-- core_md_material: WHERE category = 'PRODUCT'/'SEMI'/'RAW'
CREATE INDEX IF NOT EXISTS idx_core_md_material_category ON core_md_material(category);

-- core_md_resource: WHERE resource_type = 'EQUIPMENT'/'FIXTURE'
CREATE INDEX IF NOT EXISTS idx_core_md_resource_type ON core_md_resource(resource_type);

-- core_biz_routing_header: WHERE is_active = 1
CREATE INDEX IF NOT EXISTS idx_core_biz_routing_active ON core_biz_routing_header(is_active);

-- core_biz_demand_order: 排程查询按交期过滤
CREATE INDEX IF NOT EXISTS idx_core_biz_order_due ON core_biz_demand_order(due_period);

-- core_md_alt_rule: WHERE is_active 过滤
CREATE INDEX IF NOT EXISTS idx_core_md_alt_active ON core_md_alt_rule(is_active);

-- ============================================================
-- 五、复合索引（覆盖 JOIN + ORDER BY）
-- ============================================================

-- core_biz_routing_step: (routing_id, step_order) 覆盖 JOIN + ORDER BY
CREATE INDEX IF NOT EXISTS idx_core_biz_step_order ON core_biz_routing_step(routing_id, step_order);
