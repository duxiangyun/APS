-- ============================================================
-- 排产结果库 DDL：表 + 索引 + 视图
-- 数据库: data/db/aps_or.db (SQLite)
-- 生成时间: 2026-09-04
-- 计划期数: 12（PLAN_HORIZON，视图 PIVOT 列数依据；库存视图含 0 期共 13 列）
-- 视图设计: 一个 Excel Sheet 内的每个子表对应一个视图，字段严格对齐 Excel 列
-- 执行方式: sqlite3 data/db/aps_or.db < scripts/db_tools/create_result_tables.sql
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 零、重建视图（先删旧视图，保证脚本可重复执行）
-- 被拆分替换的旧视图: purchase / inventory / machining / shadow / infeasible
-- ============================================================
DROP VIEW IF EXISTS res_view_order_sale;
DROP VIEW IF EXISTS res_view_prod_plan;
DROP VIEW IF EXISTS res_view_prod_sale;
DROP VIEW IF EXISTS res_view_self_plan;
DROP VIEW IF EXISTS res_view_outsource_plan;
DROP VIEW IF EXISTS res_view_purchase_plan;
DROP VIEW IF EXISTS res_view_prod_inv;
DROP VIEW IF EXISTS res_view_self_inv;
DROP VIEW IF EXISTS res_view_raw_inv;
DROP VIEW IF EXISTS res_view_equip_load;
DROP VIEW IF EXISTS res_view_equip_overload;
DROP VIEW IF EXISTS res_view_equip_shadow;
DROP VIEW IF EXISTS res_view_prod_machining;
DROP VIEW IF EXISTS res_view_self_machining;
DROP VIEW IF EXISTS res_view_shadow_prod;
DROP VIEW IF EXISTS res_view_shadow_self;
DROP VIEW IF EXISTS res_view_shadow_raw;
DROP VIEW IF EXISTS res_view_fixt_load;
DROP VIEW IF EXISTS res_view_fixt_overload;
DROP VIEW IF EXISTS res_view_fixt_shadow;
DROP VIEW IF EXISTS res_view_inf_prod;
DROP VIEW IF EXISTS res_view_inf_self;
DROP VIEW IF EXISTS res_view_inf_equip;
DROP VIEW IF EXISTS res_view_substitute;
DROP VIEW IF EXISTS res_view_summary;
DROP VIEW IF EXISTS res_view_order_delivery;
-- 被拆分替换的旧视图（历史遗留）
DROP VIEW IF EXISTS res_view_purchase;
DROP VIEW IF EXISTS res_view_inventory;
DROP VIEW IF EXISTS res_view_machining;
DROP VIEW IF EXISTS res_view_shadow;
DROP VIEW IF EXISTS res_view_infeasible;

-- ============================================================
-- 一、版本管理
-- ============================================================

CREATE TABLE IF NOT EXISTS res_solve_run (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_time      TEXT    NOT NULL,
    objective     REAL,
    mip_gap       REAL,
    solve_time_ms REAL,
    status        TEXT,
    nperiod       INTEGER,
    intager       INTEGER,
    nfixtable     INTEGER,
    nouttable     INTEGER,
    nrawlimtable  INTEGER,
    nsubtable     INTEGER,
    nwiptable     INTEGER,
    created_at    TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 二、生产变量表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_prod_made (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    route_id      INTEGER NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, route_id, period)
);

CREATE TABLE IF NOT EXISTS res_self_made (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    route_id      INTEGER NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, route_id, period)
);

-- ============================================================
-- 三、库存变量表（period 含 0 期初始库存）
-- ============================================================

CREATE TABLE IF NOT EXISTS res_prod_inv (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, period)
);

CREATE TABLE IF NOT EXISTS res_self_inv (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, period)
);

CREATE TABLE IF NOT EXISTS res_raw_inv (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, period)
);

-- ============================================================
-- 四、采购与外协变量表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_purchase (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, period)
);

CREATE TABLE IF NOT EXISTS res_outsource (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, material_code, period)
);

-- ============================================================
-- 五、设备/工装负荷变量表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_workload (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    load          REAL,
    PRIMARY KEY (run_id, resource_code, period)
);

CREATE TABLE IF NOT EXISTS res_overload (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    load          REAL,
    PRIMARY KEY (run_id, resource_code, period)
);

CREATE TABLE IF NOT EXISTS res_fixtload (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    load          REAL,
    PRIMARY KEY (run_id, resource_code, period)
);

CREATE TABLE IF NOT EXISTS res_fixt_plus (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    load          REAL,
    PRIMARY KEY (run_id, resource_code, period)
);

-- ============================================================
-- 六、订单变量表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_order_sale (
    run_id   INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    order_id INTEGER NOT NULL,
    period   INTEGER NOT NULL,
    quantity REAL,
    PRIMARY KEY (run_id, order_id, period)
);

CREATE TABLE IF NOT EXISTS res_order_delay (
    run_id   INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    order_id INTEGER NOT NULL,
    period   INTEGER NOT NULL,
    quantity REAL,
    PRIMARY KEY (run_id, order_id, period)
);

-- ============================================================
-- 七、替代变量表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_substi (
    run_id   INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    rule_id  INTEGER NOT NULL,
    period   INTEGER NOT NULL,
    quantity REAL,
    PRIMARY KEY (run_id, rule_id, period)
);

-- ============================================================
-- 八、不可行松弛变量表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_infeasible (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    inf_type      TEXT    NOT NULL,   -- PRODUCT / SELF / RAW / EQUIP / FIXT / SALE
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    quantity      REAL,
    PRIMARY KEY (run_id, inf_type, resource_code, period)
);

-- ============================================================
-- 九、对偶解（影子价格）表（仅 intager=0 时写入）
-- ============================================================

CREATE TABLE IF NOT EXISTS res_dual_prod (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    dual_value    REAL,
    PRIMARY KEY (run_id, material_code, period)
);

CREATE TABLE IF NOT EXISTS res_dual_self (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    dual_value    REAL,
    PRIMARY KEY (run_id, material_code, period)
);

CREATE TABLE IF NOT EXISTS res_dual_raw (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    material_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    dual_value    REAL,
    PRIMARY KEY (run_id, material_code, period)
);

CREATE TABLE IF NOT EXISTS res_dual_equip (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    dual_value    REAL,
    PRIMARY KEY (run_id, resource_code, period)
);

CREATE TABLE IF NOT EXISTS res_dual_fixt (
    run_id        INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code TEXT    NOT NULL,
    period        INTEGER NOT NULL,
    dual_value    REAL,
    PRIMARY KEY (run_id, resource_code, period)
);

-- ============================================================
-- 十、汇总表
-- ============================================================

CREATE TABLE IF NOT EXISTS res_summary (
    run_id             INTEGER PRIMARY KEY REFERENCES res_solve_run(run_id),
    sales_revenue      REAL,
    delay_penalty      REAL,
    manufacturing_cost REAL,
    outsource_cost     REAL,
    purchase_cost      REAL,
    inventory_cost     REAL,
    fixture_cost       REAL,
    infeasible_cost    REAL,
    profit             REAL
);

CREATE TABLE IF NOT EXISTS res_order_delivery (
    run_id                  INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    priority_level          INTEGER NOT NULL,
    order_count_total       INTEGER,
    order_count_ontime      INTEGER,
    order_count_partial     INTEGER,
    order_count_delayed     INTEGER,
    order_count_undelivered INTEGER,
    quantity_total          REAL,
    quantity_ontime         REAL,
    quantity_partial        REAL,
    quantity_delayed        REAL,
    quantity_undelivered    REAL,
    PRIMARY KEY (run_id, priority_level)
);

-- 加工计划：按工序步骤拆行（同设备同生产线上的多道工序各占一行，对齐 Excel「加工计划」Sheet 行数），
--          operation_code 存工序代码（OP-精铣/OP-粗镗…），production_line 存生产线（Excel「工序代码」列口径）
--          production_quantity 存"加工数量"（产品=完工期，自制品=开工期展开），
--          capacity_usage 存"占用能力"（多周期工序向前摊铺），is_wip=1 为在制品行（route_id='wip'）
CREATE TABLE IF NOT EXISTS res_machining_plan (
    run_id             INTEGER NOT NULL REFERENCES res_solve_run(run_id),
    resource_code      TEXT    NOT NULL,
    operation_code     TEXT    NOT NULL,
    production_line    TEXT,
    material_code      TEXT    NOT NULL,
    route_id           TEXT    NOT NULL,
    fixture_code       TEXT,
    fixture_quantity   REAL,
    period             INTEGER NOT NULL,
    production_quantity REAL,
    capacity_usage     REAL,
    is_wip             INTEGER DEFAULT 0,
    PRIMARY KEY (run_id, resource_code, operation_code, material_code, route_id, period)
);

-- ============================================================
-- 十一、索引
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_res_solve_run_time      ON res_solve_run(run_time);

CREATE INDEX IF NOT EXISTS idx_res_prod_made_material  ON res_prod_made(material_code);
CREATE INDEX IF NOT EXISTS idx_res_self_made_material  ON res_self_made(material_code);

CREATE INDEX IF NOT EXISTS idx_res_prod_inv_material   ON res_prod_inv(material_code);
CREATE INDEX IF NOT EXISTS idx_res_self_inv_material   ON res_self_inv(material_code);
CREATE INDEX IF NOT EXISTS idx_res_raw_inv_material    ON res_raw_inv(material_code);

CREATE INDEX IF NOT EXISTS idx_res_purchase_material   ON res_purchase(material_code);
CREATE INDEX IF NOT EXISTS idx_res_outsource_material  ON res_outsource(material_code);

CREATE INDEX IF NOT EXISTS idx_res_workload_resource   ON res_workload(resource_code);
CREATE INDEX IF NOT EXISTS idx_res_overload_resource   ON res_overload(resource_code);
CREATE INDEX IF NOT EXISTS idx_res_fixtload_resource   ON res_fixtload(resource_code);
CREATE INDEX IF NOT EXISTS idx_res_fixt_plus_resource  ON res_fixt_plus(resource_code);

CREATE INDEX IF NOT EXISTS idx_res_order_sale_order    ON res_order_sale(order_id);
CREATE INDEX IF NOT EXISTS idx_res_order_delay_order   ON res_order_delay(order_id);

CREATE INDEX IF NOT EXISTS idx_res_substi_rule         ON res_substi(rule_id);

CREATE INDEX IF NOT EXISTS idx_res_infeasible_type     ON res_infeasible(inf_type);

CREATE INDEX IF NOT EXISTS idx_res_dual_prod_material  ON res_dual_prod(material_code);
CREATE INDEX IF NOT EXISTS idx_res_dual_self_material  ON res_dual_self(material_code);
CREATE INDEX IF NOT EXISTS idx_res_dual_raw_material   ON res_dual_raw(material_code);
CREATE INDEX IF NOT EXISTS idx_res_dual_equip_resource ON res_dual_equip(resource_code);
CREATE INDEX IF NOT EXISTS idx_res_dual_fixt_resource  ON res_dual_fixt(resource_code);

CREATE INDEX IF NOT EXISTS idx_res_machining_resource  ON res_machining_plan(resource_code);
CREATE INDEX IF NOT EXISTS idx_res_machining_material  ON res_machining_plan(material_code);

-- ============================================================
-- 十二、结果视图（26 个，对应 Excel 输出 Sheet 及其子表）
-- 约定：
--   * 所有视图默认读取最新版本 run_id = MAX(res_solve_run)
--   * 行过滤阈值 eps=0.0001（与算法 eps 一致；Excel 部分子表用 0.001，差异可忽略）
--   * 影子价格类视图仅在 intager=0（连续松弛）时输出，否则为空
--   * PIVOT 列：T=1..12（PLAN_HORIZON）；库存视图 T0=0..12
-- ============================================================

-- ------------------------------------------------------------
-- 1. 订单销售（Sheet: 订单销售，14 列严格对齐）
--    算法口径（APS-SPlant-v2-sqlite.py L1225-1295）：
--      延期罚金 = 交付量 × 罚率 × 延期期数（仅延期交付行）
--      影子价格 = 交付周期（未交付订单取交期）的产品影子价格，仅 intager=0
--      交付状态 5 态：按期交付 / 部分按期交付 / 部分按期 / 延期交付 / 未交付
-- ------------------------------------------------------------
CREATE VIEW res_view_order_sale AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run)
SELECT
    o.order_id                                        AS order_id,          -- 1  订单号
    o.product_code                                    AS material_code,     -- 2  产品代码
    o.priority_level                                  AS priority_level,    -- 3  订单等级
    o.price                                           AS order_price,       -- 4  订单价格
    o.quantity                                        AS order_quantity,    -- 5  订单数量
    o.due_period                                      AS due_period,        -- 6  订单交期
    os.period                                         AS delivery_period,   -- 7  实际交期
    os.quantity                                       AS delivery_quantity, -- 8  交付数量
    COALESCE(d.quantity, 0)                           AS delay_quantity,    -- 9  延期数量
    CASE                                                                    -- 10 交付状态
        WHEN os.quantity IS NULL OR os.quantity = 0 THEN '未交付'
        WHEN os.period = o.due_period THEN
            CASE
                WHEN o.quantity - os.quantity < 1e-4 THEN '按期交付'
                WHEN o.quantity - os.quantity - COALESCE(d.quantity, 0) > 1e-4 THEN '部分按期交付'
                ELSE '部分按期'
            END
        ELSE '延期交付'
    END                                               AS delivery_status,
    COALESCE(os.quantity, 0) * o.price                AS revenue,           -- 11 销售收入
    CASE                                                                    -- 12 延期罚金
        WHEN os.period > o.due_period
        THEN os.quantity * o.delay_penalty * (os.period - o.due_period)
        ELSE 0
    END                                               AS delay_penalty,
    CASE WHEN (SELECT intager FROM res_solve_run
               WHERE run_id = (SELECT rid FROM latest)) = 0
         THEN dp.dual_value END                          AS shadow_price,      -- 13 影子价格
    CASE WHEN (SELECT intager FROM res_solve_run
               WHERE run_id = (SELECT rid FROM latest)) = 0
         THEN o.price - dp.dual_value END                AS margin             -- 14 边际贡献
FROM core_biz_demand_order o
LEFT JOIN res_order_sale os
       ON os.order_id = o.order_id AND os.run_id = (SELECT rid FROM latest)
LEFT JOIN res_order_delay d
       ON d.order_id = o.order_id AND d.period = os.period
      AND d.run_id = (SELECT rid FROM latest)
LEFT JOIN res_dual_prod dp
       ON dp.material_code = o.product_code
      AND dp.period = COALESCE(os.period, o.due_period)   -- 未交付订单取交期影子价格
      AND dp.run_id = (SELECT rid FROM latest)
ORDER BY o.priority_level, o.order_id, os.period;

-- ------------------------------------------------------------
-- 2. 产品生产计划（Sheet: 产品计划 - 子表1「产品生产计划」）
--    列: 产品代码, 多工艺序号, 周期1..12, 数量小计
-- ------------------------------------------------------------
CREATE VIEW res_view_prod_plan AS
SELECT
    pm.material_code,                                                       -- 产品代码
    pm.route_id,                                                            -- 多工艺序号
    SUM(CASE WHEN pm.period = 1  THEN pm.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN pm.period = 2  THEN pm.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN pm.period = 3  THEN pm.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN pm.period = 4  THEN pm.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN pm.period = 5  THEN pm.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN pm.period = 6  THEN pm.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN pm.period = 7  THEN pm.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN pm.period = 8  THEN pm.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN pm.period = 9  THEN pm.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN pm.period = 10 THEN pm.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN pm.period = 11 THEN pm.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN pm.period = 12 THEN pm.quantity ELSE 0 END) AS period_12,
    SUM(pm.quantity) AS quantity_total                                      -- 数量小计
FROM res_prod_made pm
WHERE pm.run_id = (SELECT MAX(run_id) FROM res_solve_run)
GROUP BY pm.material_code, pm.route_id
HAVING SUM(pm.quantity) > 0.0001
ORDER BY pm.material_code, pm.route_id;

-- ------------------------------------------------------------
-- 3. 产品销售计划（Sheet: 产品计划 - 子表2「产品销售计划」）
--    列: 产品代码, 周期1..12, 数量小计；全部产品均输出一行（未销售为 0）
--    口径: 按产品聚合各订单交付量（res_order_sale × 订单主表）
-- ------------------------------------------------------------
CREATE VIEW res_view_prod_sale AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
sale AS (
    SELECT o.product_code AS material_code, s.period, SUM(s.quantity) AS qty
    FROM res_order_sale s
    JOIN core_biz_demand_order o ON o.order_id = s.order_id
    WHERE s.run_id = (SELECT rid FROM latest)
    GROUP BY o.product_code, s.period
)
SELECT
    m.material_code,                                                        -- 产品代码
    COALESCE(SUM(CASE WHEN sa.period = 1  THEN sa.qty END), 0) AS period_1,
    COALESCE(SUM(CASE WHEN sa.period = 2  THEN sa.qty END), 0) AS period_2,
    COALESCE(SUM(CASE WHEN sa.period = 3  THEN sa.qty END), 0) AS period_3,
    COALESCE(SUM(CASE WHEN sa.period = 4  THEN sa.qty END), 0) AS period_4,
    COALESCE(SUM(CASE WHEN sa.period = 5  THEN sa.qty END), 0) AS period_5,
    COALESCE(SUM(CASE WHEN sa.period = 6  THEN sa.qty END), 0) AS period_6,
    COALESCE(SUM(CASE WHEN sa.period = 7  THEN sa.qty END), 0) AS period_7,
    COALESCE(SUM(CASE WHEN sa.period = 8  THEN sa.qty END), 0) AS period_8,
    COALESCE(SUM(CASE WHEN sa.period = 9  THEN sa.qty END), 0) AS period_9,
    COALESCE(SUM(CASE WHEN sa.period = 10 THEN sa.qty END), 0) AS period_10,
    COALESCE(SUM(CASE WHEN sa.period = 11 THEN sa.qty END), 0) AS period_11,
    COALESCE(SUM(CASE WHEN sa.period = 12 THEN sa.qty END), 0) AS period_12,
    COALESCE(SUM(sa.qty), 0) AS quantity_total                              -- 数量小计
FROM core_md_material m
LEFT JOIN sale sa ON sa.material_code = m.material_code
WHERE m.category = 'PRODUCT'
GROUP BY m.material_code
ORDER BY m.material_code;

-- ------------------------------------------------------------
-- 4. 自制件生产计划（Sheet: 自制件计划）
--    列: 自制件序号, 自制件代码, 多工艺号, 周期1..12, 数量小计
--    在制品行（多工艺号='wip'）由 core_biz_wip × 默认工艺路线派生：
--      完工周期 = 总制造期(WipMaxT) - 已完成阶段(WipStage)，数量 = 在制数量
-- ------------------------------------------------------------
CREATE VIEW res_view_self_plan AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
prod AS (
    SELECT sm.material_code, CAST(sm.route_id AS TEXT) AS route_id, sm.period, sm.quantity
    FROM res_self_made sm
    WHERE sm.run_id = (SELECT rid FROM latest)
),
wip AS (
    SELECT w.material_code, 'wip' AS route_id,
           h.total_lead_time - w.completed_stages AS period,
           w.quantity
    FROM core_biz_wip w
    JOIN core_biz_routing_header h
      ON h.material_code = w.material_code AND h.is_default = 1
    WHERE w.quantity > 0
),
allrows AS (SELECT * FROM prod UNION ALL SELECT * FROM wip)
SELECT
    ROW_NUMBER() OVER (ORDER BY r.material_code, r.route_id) AS seq,        -- 自制件序号
    r.material_code,                                                        -- 自制件代码
    r.route_id,                                                             -- 多工艺号
    SUM(CASE WHEN r.period = 1  THEN r.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN r.period = 2  THEN r.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN r.period = 3  THEN r.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN r.period = 4  THEN r.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN r.period = 5  THEN r.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN r.period = 6  THEN r.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN r.period = 7  THEN r.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN r.period = 8  THEN r.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN r.period = 9  THEN r.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN r.period = 10 THEN r.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN r.period = 11 THEN r.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN r.period = 12 THEN r.quantity ELSE 0 END) AS period_12,
    SUM(r.quantity) AS quantity_total                                       -- 数量小计
FROM allrows r
GROUP BY r.material_code, r.route_id
HAVING SUM(r.quantity) > 0.0001
ORDER BY r.material_code, r.route_id;

-- ------------------------------------------------------------
-- 5. 外协采购计划（Sheet: 采购 - 子表1「自制件外协采购」）
--    列: 自制件外协序号, 自制件代码, 周期1..12, 数量小计, 成本小计
--    成本小计 = Σ量 × 外协价格（core_md_semi_ext.outsource_price）
-- ------------------------------------------------------------
CREATE VIEW res_view_outsource_plan AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
agg AS (
    SELECT
        o.material_code,
        SUM(CASE WHEN o.period = 1  THEN o.quantity ELSE 0 END) AS period_1,
        SUM(CASE WHEN o.period = 2  THEN o.quantity ELSE 0 END) AS period_2,
        SUM(CASE WHEN o.period = 3  THEN o.quantity ELSE 0 END) AS period_3,
        SUM(CASE WHEN o.period = 4  THEN o.quantity ELSE 0 END) AS period_4,
        SUM(CASE WHEN o.period = 5  THEN o.quantity ELSE 0 END) AS period_5,
        SUM(CASE WHEN o.period = 6  THEN o.quantity ELSE 0 END) AS period_6,
        SUM(CASE WHEN o.period = 7  THEN o.quantity ELSE 0 END) AS period_7,
        SUM(CASE WHEN o.period = 8  THEN o.quantity ELSE 0 END) AS period_8,
        SUM(CASE WHEN o.period = 9  THEN o.quantity ELSE 0 END) AS period_9,
        SUM(CASE WHEN o.period = 10 THEN o.quantity ELSE 0 END) AS period_10,
        SUM(CASE WHEN o.period = 11 THEN o.quantity ELSE 0 END) AS period_11,
        SUM(CASE WHEN o.period = 12 THEN o.quantity ELSE 0 END) AS period_12,
        SUM(o.quantity) AS quantity_total
    FROM res_outsource o
    WHERE o.run_id = (SELECT rid FROM latest)
    GROUP BY o.material_code
    HAVING SUM(o.quantity) > 0.0001
)
SELECT
    ROW_NUMBER() OVER (ORDER BY a.material_code) AS seq,                    -- 自制件外协序号
    a.material_code,                                                        -- 自制件代码
    a.period_1, a.period_2, a.period_3, a.period_4, a.period_5, a.period_6,
    a.period_7, a.period_8, a.period_9, a.period_10, a.period_11, a.period_12,
    a.quantity_total,                                                       -- 数量小计
    a.quantity_total * se.outsource_price AS cost_total                     -- 成本小计
FROM agg a
LEFT JOIN core_md_semi_ext se ON se.material_code = a.material_code
ORDER BY a.material_code;

-- ------------------------------------------------------------
-- 6. 原材料采购计划（Sheet: 采购 - 子表2「原材料采购」）
--    列: 物料序号, 物料代码, 周期1..12, 数量小计, 成本小计
--    成本小计 = Σ量 × 采购价格（core_md_raw_ext.purchase_cost）
-- ------------------------------------------------------------
CREATE VIEW res_view_purchase_plan AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
agg AS (
    SELECT
        p.material_code,
        SUM(CASE WHEN p.period = 1  THEN p.quantity ELSE 0 END) AS period_1,
        SUM(CASE WHEN p.period = 2  THEN p.quantity ELSE 0 END) AS period_2,
        SUM(CASE WHEN p.period = 3  THEN p.quantity ELSE 0 END) AS period_3,
        SUM(CASE WHEN p.period = 4  THEN p.quantity ELSE 0 END) AS period_4,
        SUM(CASE WHEN p.period = 5  THEN p.quantity ELSE 0 END) AS period_5,
        SUM(CASE WHEN p.period = 6  THEN p.quantity ELSE 0 END) AS period_6,
        SUM(CASE WHEN p.period = 7  THEN p.quantity ELSE 0 END) AS period_7,
        SUM(CASE WHEN p.period = 8  THEN p.quantity ELSE 0 END) AS period_8,
        SUM(CASE WHEN p.period = 9  THEN p.quantity ELSE 0 END) AS period_9,
        SUM(CASE WHEN p.period = 10 THEN p.quantity ELSE 0 END) AS period_10,
        SUM(CASE WHEN p.period = 11 THEN p.quantity ELSE 0 END) AS period_11,
        SUM(CASE WHEN p.period = 12 THEN p.quantity ELSE 0 END) AS period_12,
        SUM(p.quantity) AS quantity_total
    FROM res_purchase p
    WHERE p.run_id = (SELECT rid FROM latest)
    GROUP BY p.material_code
    HAVING SUM(p.quantity) > 0.0001
)
SELECT
    ROW_NUMBER() OVER (ORDER BY a.material_code) AS seq,                    -- 物料序号
    a.material_code,                                                        -- 物料代码
    a.period_1, a.period_2, a.period_3, a.period_4, a.period_5, a.period_6,
    a.period_7, a.period_8, a.period_9, a.period_10, a.period_11, a.period_12,
    a.quantity_total,                                                       -- 数量小计
    a.quantity_total * re.purchase_cost AS cost_total                       -- 成本小计
FROM agg a
LEFT JOIN core_md_raw_ext re ON re.material_code = a.material_code
ORDER BY a.material_code;

-- ------------------------------------------------------------
-- 7. 产品库存（Sheet: 库存 - 子表1「产品库存」）
--    列: 物料号, 周期0..12（含 0 期初始库存）, 成本小计
--    成本口径与算法一致（L1487-1497）：成本小计 = Σ期库存量 × 库存成本费率
--    （库存成本费率 = core_md_material.holding_cost_rate，算法直接使用输入值，无换算）
-- ------------------------------------------------------------
CREATE VIEW res_view_prod_inv AS
SELECT
    pi.material_code,                                                       -- 物料号
    SUM(CASE WHEN pi.period = 0  THEN pi.quantity ELSE 0 END) AS period_0,
    SUM(CASE WHEN pi.period = 1  THEN pi.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN pi.period = 2  THEN pi.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN pi.period = 3  THEN pi.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN pi.period = 4  THEN pi.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN pi.period = 5  THEN pi.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN pi.period = 6  THEN pi.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN pi.period = 7  THEN pi.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN pi.period = 8  THEN pi.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN pi.period = 9  THEN pi.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN pi.period = 10 THEN pi.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN pi.period = 11 THEN pi.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN pi.period = 12 THEN pi.quantity ELSE 0 END) AS period_12,
    SUM(pi.quantity) AS quantity_total,
    SUM(pi.quantity) * m.holding_cost_rate AS inventory_cost                -- 成本小计
FROM res_prod_inv pi
JOIN core_md_material m ON m.material_code = pi.material_code
WHERE pi.run_id = (SELECT MAX(run_id) FROM res_solve_run)
GROUP BY pi.material_code, m.holding_cost_rate
HAVING SUM(pi.quantity) > 0.0001
ORDER BY pi.material_code;

-- ------------------------------------------------------------
-- 8. 自制件库存（Sheet: 库存 - 子表2「自制产品库存」）
--    成本口径同上（L1512-1521）：Σ期库存量 × 库存成本费率
-- ------------------------------------------------------------
CREATE VIEW res_view_self_inv AS
SELECT
    si.material_code,                                                       -- 代码
    SUM(CASE WHEN si.period = 0  THEN si.quantity ELSE 0 END) AS period_0,
    SUM(CASE WHEN si.period = 1  THEN si.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN si.period = 2  THEN si.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN si.period = 3  THEN si.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN si.period = 4  THEN si.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN si.period = 5  THEN si.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN si.period = 6  THEN si.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN si.period = 7  THEN si.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN si.period = 8  THEN si.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN si.period = 9  THEN si.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN si.period = 10 THEN si.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN si.period = 11 THEN si.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN si.period = 12 THEN si.quantity ELSE 0 END) AS period_12,
    SUM(si.quantity) AS quantity_total,
    SUM(si.quantity) * m.holding_cost_rate AS inventory_cost                -- 成本小计
FROM res_self_inv si
JOIN core_md_material m ON m.material_code = si.material_code
WHERE si.run_id = (SELECT MAX(run_id) FROM res_solve_run)
GROUP BY si.material_code, m.holding_cost_rate
HAVING SUM(si.quantity) > 0.0001
ORDER BY si.material_code;

-- ------------------------------------------------------------
-- 9. 原材料库存（Sheet: 库存 - 子表3「原材料库存」）
--    成本口径同上（L1537-1546）：Σ期库存量 × 库存成本费率
-- ------------------------------------------------------------
CREATE VIEW res_view_raw_inv AS
SELECT
    ri.material_code,                                                       -- 代码
    SUM(CASE WHEN ri.period = 0  THEN ri.quantity ELSE 0 END) AS period_0,
    SUM(CASE WHEN ri.period = 1  THEN ri.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN ri.period = 2  THEN ri.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN ri.period = 3  THEN ri.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN ri.period = 4  THEN ri.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN ri.period = 5  THEN ri.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN ri.period = 6  THEN ri.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN ri.period = 7  THEN ri.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN ri.period = 8  THEN ri.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN ri.period = 9  THEN ri.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN ri.period = 10 THEN ri.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN ri.period = 11 THEN ri.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN ri.period = 12 THEN ri.quantity ELSE 0 END) AS period_12,
    SUM(ri.quantity) AS quantity_total,
    SUM(ri.quantity) * m.holding_cost_rate AS inventory_cost                -- 成本小计
FROM res_raw_inv ri
JOIN core_md_material m ON m.material_code = ri.material_code
WHERE ri.run_id = (SELECT MAX(run_id) FROM res_solve_run)
GROUP BY ri.material_code, m.holding_cost_rate
HAVING SUM(ri.quantity) > 0.0001
ORDER BY ri.material_code;

-- ------------------------------------------------------------
-- 10. 设备正常负荷（Sheet: 设备负荷 - 子表1「正常负荷分布」）
--     列: 设备号, 设备能力, 周期1..12, 最大负荷率%, 平均负荷率%, 正常成本小计
--     能力 = 每班时长 × 班次数 × 设备数 × 利用率（算法 L702-705 EquipCap）
--     最大负荷率 = MAX(负荷/能力)×100（仅计负荷>eps 的期）
--     平均负荷率 = Σ(负荷/能力)×100 / 期数（仅计负荷>eps 的期，除以总期数）
--     正常成本小计 = Σ负荷 × 设备单位成本（core_md_resource.unit_cost）
-- ------------------------------------------------------------
CREATE VIEW res_view_equip_load AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
gp AS (
    SELECT CAST(MAX(CASE WHEN param_key = 'SHIFTS_PER_PERIOD'      THEN param_value END) AS REAL) AS shifts,
           CAST(MAX(CASE WHEN param_key = 'SHIFT_DURATION_MINUTES' THEN param_value END) AS REAL) AS minutes,
           CAST(MAX(CASE WHEN param_key = 'PLAN_HORIZON'           THEN param_value END) AS REAL) AS nperiod
    FROM core_biz_global_params
),
agg AS (
    SELECT
        wl.resource_code,
        SUM(CASE WHEN wl.period = 1  THEN wl.load ELSE 0 END) AS period_1,
        SUM(CASE WHEN wl.period = 2  THEN wl.load ELSE 0 END) AS period_2,
        SUM(CASE WHEN wl.period = 3  THEN wl.load ELSE 0 END) AS period_3,
        SUM(CASE WHEN wl.period = 4  THEN wl.load ELSE 0 END) AS period_4,
        SUM(CASE WHEN wl.period = 5  THEN wl.load ELSE 0 END) AS period_5,
        SUM(CASE WHEN wl.period = 6  THEN wl.load ELSE 0 END) AS period_6,
        SUM(CASE WHEN wl.period = 7  THEN wl.load ELSE 0 END) AS period_7,
        SUM(CASE WHEN wl.period = 8  THEN wl.load ELSE 0 END) AS period_8,
        SUM(CASE WHEN wl.period = 9  THEN wl.load ELSE 0 END) AS period_9,
        SUM(CASE WHEN wl.period = 10 THEN wl.load ELSE 0 END) AS period_10,
        SUM(CASE WHEN wl.period = 11 THEN wl.load ELSE 0 END) AS period_11,
        SUM(CASE WHEN wl.period = 12 THEN wl.load ELSE 0 END) AS period_12,
        SUM(wl.load) AS load_total,
        MAX(CASE WHEN wl.load > 0.0001 THEN wl.load END) AS max_load,
        SUM(CASE WHEN wl.load > 0.0001 THEN wl.load ELSE 0 END) AS active_load
    FROM res_workload wl
    WHERE wl.run_id = (SELECT rid FROM latest)
    GROUP BY wl.resource_code
    HAVING SUM(wl.load) > 0.0001
)
SELECT
    a.resource_code,                                                        -- 设备号
    r.quantity * r.utilization_rate * gp.minutes * gp.shifts AS capacity,   -- 设备能力
    a.period_1, a.period_2, a.period_3, a.period_4, a.period_5, a.period_6,
    a.period_7, a.period_8, a.period_9, a.period_10, a.period_11, a.period_12,
    a.max_load * 100.0
        / NULLIF(r.quantity * r.utilization_rate * gp.minutes * gp.shifts, 0)
        AS max_load_rate_pct,                                               -- 最大负荷率 %
    a.active_load * 100.0
        / NULLIF(r.quantity * r.utilization_rate * gp.minutes * gp.shifts, 0)
        / gp.nperiod AS avg_load_rate_pct,                                  -- 平均负荷率 %
    a.load_total * r.unit_cost AS normal_cost_total                         -- 正常成本小计
FROM agg a
JOIN core_md_resource r ON r.resource_code = a.resource_code
CROSS JOIN gp
ORDER BY a.resource_code;

-- ------------------------------------------------------------
-- 11. 设备加班负荷（Sheet: 设备负荷 - 子表2「超时（加班）负荷分布」）
--     列: 设备号, 设备能力, 周期1..12, 超时成本小计
--     超时成本小计 = Σ加班负荷 × 单位成本 × 加班成本倍数（算法 L1627）
-- ------------------------------------------------------------
CREATE VIEW res_view_equip_overload AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
gp AS (
    SELECT CAST(MAX(CASE WHEN param_key = 'SHIFTS_PER_PERIOD'      THEN param_value END) AS REAL) AS shifts,
           CAST(MAX(CASE WHEN param_key = 'SHIFT_DURATION_MINUTES' THEN param_value END) AS REAL) AS minutes
    FROM core_biz_global_params
),
agg AS (
    SELECT
        ol.resource_code,
        SUM(CASE WHEN ol.period = 1  THEN ol.load ELSE 0 END) AS period_1,
        SUM(CASE WHEN ol.period = 2  THEN ol.load ELSE 0 END) AS period_2,
        SUM(CASE WHEN ol.period = 3  THEN ol.load ELSE 0 END) AS period_3,
        SUM(CASE WHEN ol.period = 4  THEN ol.load ELSE 0 END) AS period_4,
        SUM(CASE WHEN ol.period = 5  THEN ol.load ELSE 0 END) AS period_5,
        SUM(CASE WHEN ol.period = 6  THEN ol.load ELSE 0 END) AS period_6,
        SUM(CASE WHEN ol.period = 7  THEN ol.load ELSE 0 END) AS period_7,
        SUM(CASE WHEN ol.period = 8  THEN ol.load ELSE 0 END) AS period_8,
        SUM(CASE WHEN ol.period = 9  THEN ol.load ELSE 0 END) AS period_9,
        SUM(CASE WHEN ol.period = 10 THEN ol.load ELSE 0 END) AS period_10,
        SUM(CASE WHEN ol.period = 11 THEN ol.load ELSE 0 END) AS period_11,
        SUM(CASE WHEN ol.period = 12 THEN ol.load ELSE 0 END) AS period_12,
        SUM(ol.load) AS load_total
    FROM res_overload ol
    WHERE ol.run_id = (SELECT rid FROM latest)
    GROUP BY ol.resource_code
    HAVING SUM(ol.load) > 0.0001
)
SELECT
    a.resource_code,                                                        -- 设备号
    r.quantity * r.utilization_rate * gp.minutes * gp.shifts AS capacity,   -- 设备能力
    a.period_1, a.period_2, a.period_3, a.period_4, a.period_5, a.period_6,
    a.period_7, a.period_8, a.period_9, a.period_10, a.period_11, a.period_12,
    a.load_total * r.unit_cost * r.overtime_cost_multiplier
        AS overload_cost_total                                              -- 超时成本小计
FROM agg a
JOIN core_md_resource r ON r.resource_code = a.resource_code
CROSS JOIN gp
ORDER BY a.resource_code;

-- ------------------------------------------------------------
-- 12. 设备影子价格（Sheet: 设备负荷 - 子表3「设备加工能力影子价格」）
--     列: 设备号, 周期1..12；全部设备输出（算法 L1641-1645），仅 intager=0
-- ------------------------------------------------------------
CREATE VIEW res_view_equip_shadow AS
SELECT
    de.resource_code,                                                       -- 设备号
    MAX(CASE WHEN de.period = 1  THEN de.dual_value END) AS period_1,
    MAX(CASE WHEN de.period = 2  THEN de.dual_value END) AS period_2,
    MAX(CASE WHEN de.period = 3  THEN de.dual_value END) AS period_3,
    MAX(CASE WHEN de.period = 4  THEN de.dual_value END) AS period_4,
    MAX(CASE WHEN de.period = 5  THEN de.dual_value END) AS period_5,
    MAX(CASE WHEN de.period = 6  THEN de.dual_value END) AS period_6,
    MAX(CASE WHEN de.period = 7  THEN de.dual_value END) AS period_7,
    MAX(CASE WHEN de.period = 8  THEN de.dual_value END) AS period_8,
    MAX(CASE WHEN de.period = 9  THEN de.dual_value END) AS period_9,
    MAX(CASE WHEN de.period = 10 THEN de.dual_value END) AS period_10,
    MAX(CASE WHEN de.period = 11 THEN de.dual_value END) AS period_11,
    MAX(CASE WHEN de.period = 12 THEN de.dual_value END) AS period_12
FROM res_dual_equip de
WHERE de.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND (SELECT intager FROM res_solve_run
       WHERE run_id = (SELECT MAX(run_id) FROM res_solve_run)) = 0
GROUP BY de.resource_code
ORDER BY de.resource_code;

-- ------------------------------------------------------------
-- 13. 产品加工计划（Sheet: 加工计划 - 子表1「产品加工计划」）
--     列: 设备代码, 工序代码, 产品代码, 多工艺号, [工装代码, 工装数量],
--         加工数量 周期1..12, 占用能力 周期1..12, 能力合计
--     production_quantity 存于完工期（t > 产品提前期）
--     capacity_usage 存于能力占用期（多周期工序 ProMaxT>1 时向前摊铺，算法 L1697-1708）
--     工装两列在 nfixtable=1 时有值，否则为 NULL
-- ------------------------------------------------------------
CREATE VIEW res_view_prod_machining AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run)
SELECT
    mp.resource_code,                                                       -- 设备代码
    mp.production_line,                                                     -- 工序代码（生产线，对齐 Excel）
    mp.operation_code,                                                      -- 工序编码（OP-精铣/OP-粗镗…）
    mp.material_code,                                                       -- 产品代码
    mp.route_id,                                                            -- 多工艺号
    mp.fixture_code,                                                        -- 工装代码
    mp.fixture_quantity,                                                    -- 工装数量
    SUM(CASE WHEN mp.period = 1  THEN mp.production_quantity ELSE 0 END) AS made_period_1,
    SUM(CASE WHEN mp.period = 2  THEN mp.production_quantity ELSE 0 END) AS made_period_2,
    SUM(CASE WHEN mp.period = 3  THEN mp.production_quantity ELSE 0 END) AS made_period_3,
    SUM(CASE WHEN mp.period = 4  THEN mp.production_quantity ELSE 0 END) AS made_period_4,
    SUM(CASE WHEN mp.period = 5  THEN mp.production_quantity ELSE 0 END) AS made_period_5,
    SUM(CASE WHEN mp.period = 6  THEN mp.production_quantity ELSE 0 END) AS made_period_6,
    SUM(CASE WHEN mp.period = 7  THEN mp.production_quantity ELSE 0 END) AS made_period_7,
    SUM(CASE WHEN mp.period = 8  THEN mp.production_quantity ELSE 0 END) AS made_period_8,
    SUM(CASE WHEN mp.period = 9  THEN mp.production_quantity ELSE 0 END) AS made_period_9,
    SUM(CASE WHEN mp.period = 10 THEN mp.production_quantity ELSE 0 END) AS made_period_10,
    SUM(CASE WHEN mp.period = 11 THEN mp.production_quantity ELSE 0 END) AS made_period_11,
    SUM(CASE WHEN mp.period = 12 THEN mp.production_quantity ELSE 0 END) AS made_period_12,
    SUM(CASE WHEN mp.period = 1  THEN mp.capacity_usage ELSE 0 END) AS cap_period_1,
    SUM(CASE WHEN mp.period = 2  THEN mp.capacity_usage ELSE 0 END) AS cap_period_2,
    SUM(CASE WHEN mp.period = 3  THEN mp.capacity_usage ELSE 0 END) AS cap_period_3,
    SUM(CASE WHEN mp.period = 4  THEN mp.capacity_usage ELSE 0 END) AS cap_period_4,
    SUM(CASE WHEN mp.period = 5  THEN mp.capacity_usage ELSE 0 END) AS cap_period_5,
    SUM(CASE WHEN mp.period = 6  THEN mp.capacity_usage ELSE 0 END) AS cap_period_6,
    SUM(CASE WHEN mp.period = 7  THEN mp.capacity_usage ELSE 0 END) AS cap_period_7,
    SUM(CASE WHEN mp.period = 8  THEN mp.capacity_usage ELSE 0 END) AS cap_period_8,
    SUM(CASE WHEN mp.period = 9  THEN mp.capacity_usage ELSE 0 END) AS cap_period_9,
    SUM(CASE WHEN mp.period = 10 THEN mp.capacity_usage ELSE 0 END) AS cap_period_10,
    SUM(CASE WHEN mp.period = 11 THEN mp.capacity_usage ELSE 0 END) AS cap_period_11,
    SUM(CASE WHEN mp.period = 12 THEN mp.capacity_usage ELSE 0 END) AS cap_period_12,
    SUM(mp.capacity_usage) AS capacity_total                                -- 能力合计
FROM res_machining_plan mp
JOIN core_md_material m ON m.material_code = mp.material_code
WHERE mp.run_id = (SELECT rid FROM latest)
  AND m.category = 'PRODUCT'
GROUP BY mp.resource_code, mp.operation_code, mp.production_line, mp.material_code, mp.route_id,
         mp.fixture_code, mp.fixture_quantity
HAVING SUM(mp.production_quantity) > 0.0001
ORDER BY mp.resource_code, mp.material_code, mp.route_id;

-- ------------------------------------------------------------
-- 14. 自制件加工计划（Sheet: 加工计划 - 子表2「自制件加工计划」）
--     列同产品加工计划；含在制品行（多工艺号='wip'，is_wip=1）
--     在制品行：加工数量 = 在制数量存于 it-WipStage 期（it=WipStage+1..总制造期），
--               占用能力 = 在制数量 × 工时（算法 L1784-1803）
-- ------------------------------------------------------------
CREATE VIEW res_view_self_machining AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run)
SELECT
    mp.resource_code,                                                       -- 设备代码
    mp.production_line,                                                     -- 工序代码（生产线，对齐 Excel）
    mp.operation_code,                                                      -- 工序编码（OP-精铣/OP-粗镗…）
    mp.material_code,                                                       -- 产品代码
    mp.route_id,                                                            -- 多工艺号
    mp.fixture_code,                                                        -- 工装代码
    mp.fixture_quantity,                                                    -- 工装数量
    SUM(CASE WHEN mp.period = 1  THEN mp.production_quantity ELSE 0 END) AS made_period_1,
    SUM(CASE WHEN mp.period = 2  THEN mp.production_quantity ELSE 0 END) AS made_period_2,
    SUM(CASE WHEN mp.period = 3  THEN mp.production_quantity ELSE 0 END) AS made_period_3,
    SUM(CASE WHEN mp.period = 4  THEN mp.production_quantity ELSE 0 END) AS made_period_4,
    SUM(CASE WHEN mp.period = 5  THEN mp.production_quantity ELSE 0 END) AS made_period_5,
    SUM(CASE WHEN mp.period = 6  THEN mp.production_quantity ELSE 0 END) AS made_period_6,
    SUM(CASE WHEN mp.period = 7  THEN mp.production_quantity ELSE 0 END) AS made_period_7,
    SUM(CASE WHEN mp.period = 8  THEN mp.production_quantity ELSE 0 END) AS made_period_8,
    SUM(CASE WHEN mp.period = 9  THEN mp.production_quantity ELSE 0 END) AS made_period_9,
    SUM(CASE WHEN mp.period = 10 THEN mp.production_quantity ELSE 0 END) AS made_period_10,
    SUM(CASE WHEN mp.period = 11 THEN mp.production_quantity ELSE 0 END) AS made_period_11,
    SUM(CASE WHEN mp.period = 12 THEN mp.production_quantity ELSE 0 END) AS made_period_12,
    SUM(CASE WHEN mp.period = 1  THEN mp.capacity_usage ELSE 0 END) AS cap_period_1,
    SUM(CASE WHEN mp.period = 2  THEN mp.capacity_usage ELSE 0 END) AS cap_period_2,
    SUM(CASE WHEN mp.period = 3  THEN mp.capacity_usage ELSE 0 END) AS cap_period_3,
    SUM(CASE WHEN mp.period = 4  THEN mp.capacity_usage ELSE 0 END) AS cap_period_4,
    SUM(CASE WHEN mp.period = 5  THEN mp.capacity_usage ELSE 0 END) AS cap_period_5,
    SUM(CASE WHEN mp.period = 6  THEN mp.capacity_usage ELSE 0 END) AS cap_period_6,
    SUM(CASE WHEN mp.period = 7  THEN mp.capacity_usage ELSE 0 END) AS cap_period_7,
    SUM(CASE WHEN mp.period = 8  THEN mp.capacity_usage ELSE 0 END) AS cap_period_8,
    SUM(CASE WHEN mp.period = 9  THEN mp.capacity_usage ELSE 0 END) AS cap_period_9,
    SUM(CASE WHEN mp.period = 10 THEN mp.capacity_usage ELSE 0 END) AS cap_period_10,
    SUM(CASE WHEN mp.period = 11 THEN mp.capacity_usage ELSE 0 END) AS cap_period_11,
    SUM(CASE WHEN mp.period = 12 THEN mp.capacity_usage ELSE 0 END) AS cap_period_12,
    SUM(mp.capacity_usage) AS capacity_total                                -- 能力合计
FROM res_machining_plan mp
JOIN core_md_material m ON m.material_code = mp.material_code
WHERE mp.run_id = (SELECT rid FROM latest)
  AND m.category = 'SEMI'
GROUP BY mp.resource_code, mp.operation_code, mp.production_line, mp.material_code, mp.route_id,
         mp.fixture_code, mp.fixture_quantity
HAVING SUM(mp.production_quantity) > 0.0001
ORDER BY mp.resource_code, mp.material_code, mp.route_id;

-- ------------------------------------------------------------
-- 15. 产品影子价格（Sheet: 影子价格 - 子表1「产品影子价格」）
--     列: 物料号, 周期1..12；全部产品输出，仅 intager=0
-- ------------------------------------------------------------
CREATE VIEW res_view_shadow_prod AS
SELECT
    dp.material_code,                                                       -- 物料号
    MAX(CASE WHEN dp.period = 1  THEN dp.dual_value END) AS period_1,
    MAX(CASE WHEN dp.period = 2  THEN dp.dual_value END) AS period_2,
    MAX(CASE WHEN dp.period = 3  THEN dp.dual_value END) AS period_3,
    MAX(CASE WHEN dp.period = 4  THEN dp.dual_value END) AS period_4,
    MAX(CASE WHEN dp.period = 5  THEN dp.dual_value END) AS period_5,
    MAX(CASE WHEN dp.period = 6  THEN dp.dual_value END) AS period_6,
    MAX(CASE WHEN dp.period = 7  THEN dp.dual_value END) AS period_7,
    MAX(CASE WHEN dp.period = 8  THEN dp.dual_value END) AS period_8,
    MAX(CASE WHEN dp.period = 9  THEN dp.dual_value END) AS period_9,
    MAX(CASE WHEN dp.period = 10 THEN dp.dual_value END) AS period_10,
    MAX(CASE WHEN dp.period = 11 THEN dp.dual_value END) AS period_11,
    MAX(CASE WHEN dp.period = 12 THEN dp.dual_value END) AS period_12
FROM res_dual_prod dp
WHERE dp.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND (SELECT intager FROM res_solve_run
       WHERE run_id = (SELECT MAX(run_id) FROM res_solve_run)) = 0
GROUP BY dp.material_code
ORDER BY dp.material_code;

-- ------------------------------------------------------------
-- 16. 自制品影子价格（Sheet: 影子价格 - 子表2「自制品影子价格」）
-- ------------------------------------------------------------
CREATE VIEW res_view_shadow_self AS
SELECT
    ds.material_code,                                                       -- 物料号
    MAX(CASE WHEN ds.period = 1  THEN ds.dual_value END) AS period_1,
    MAX(CASE WHEN ds.period = 2  THEN ds.dual_value END) AS period_2,
    MAX(CASE WHEN ds.period = 3  THEN ds.dual_value END) AS period_3,
    MAX(CASE WHEN ds.period = 4  THEN ds.dual_value END) AS period_4,
    MAX(CASE WHEN ds.period = 5  THEN ds.dual_value END) AS period_5,
    MAX(CASE WHEN ds.period = 6  THEN ds.dual_value END) AS period_6,
    MAX(CASE WHEN ds.period = 7  THEN ds.dual_value END) AS period_7,
    MAX(CASE WHEN ds.period = 8  THEN ds.dual_value END) AS period_8,
    MAX(CASE WHEN ds.period = 9  THEN ds.dual_value END) AS period_9,
    MAX(CASE WHEN ds.period = 10 THEN ds.dual_value END) AS period_10,
    MAX(CASE WHEN ds.period = 11 THEN ds.dual_value END) AS period_11,
    MAX(CASE WHEN ds.period = 12 THEN ds.dual_value END) AS period_12
FROM res_dual_self ds
WHERE ds.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND (SELECT intager FROM res_solve_run
       WHERE run_id = (SELECT MAX(run_id) FROM res_solve_run)) = 0
GROUP BY ds.material_code
ORDER BY ds.material_code;

-- ------------------------------------------------------------
-- 17. 原材料影子价格（Sheet: 影子价格 - 子表3「原材料影子价格」）
--     排除同时为自制件的物料（算法 L1836：RawCode not in Selfset）
-- ------------------------------------------------------------
CREATE VIEW res_view_shadow_raw AS
SELECT
    dr.material_code,                                                       -- 物料号
    MAX(CASE WHEN dr.period = 1  THEN dr.dual_value END) AS period_1,
    MAX(CASE WHEN dr.period = 2  THEN dr.dual_value END) AS period_2,
    MAX(CASE WHEN dr.period = 3  THEN dr.dual_value END) AS period_3,
    MAX(CASE WHEN dr.period = 4  THEN dr.dual_value END) AS period_4,
    MAX(CASE WHEN dr.period = 5  THEN dr.dual_value END) AS period_5,
    MAX(CASE WHEN dr.period = 6  THEN dr.dual_value END) AS period_6,
    MAX(CASE WHEN dr.period = 7  THEN dr.dual_value END) AS period_7,
    MAX(CASE WHEN dr.period = 8  THEN dr.dual_value END) AS period_8,
    MAX(CASE WHEN dr.period = 9  THEN dr.dual_value END) AS period_9,
    MAX(CASE WHEN dr.period = 10 THEN dr.dual_value END) AS period_10,
    MAX(CASE WHEN dr.period = 11 THEN dr.dual_value END) AS period_11,
    MAX(CASE WHEN dr.period = 12 THEN dr.dual_value END) AS period_12
FROM res_dual_raw dr
WHERE dr.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND (SELECT intager FROM res_solve_run
       WHERE run_id = (SELECT MAX(run_id) FROM res_solve_run)) = 0
  AND dr.material_code NOT IN (
        SELECT material_code FROM core_md_material WHERE category = 'SEMI')
GROUP BY dr.material_code
ORDER BY dr.material_code;

-- ------------------------------------------------------------
-- 18. 工装正常负荷（Sheet: 工装负荷 - 正常负荷块）
--     列: 工装代码, 周期1..12, 最大负荷率%, 平均负荷率%, 成本小计
--     能力 = 每班时长 × 班次数 × 工装数 × 利用率（算法 L709-711 FixtCap，不输出仅参与比率）
--     成本小计 = Σ负荷 × 工装单位成本（算法 L1935）
-- ------------------------------------------------------------
CREATE VIEW res_view_fixt_load AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
gp AS (
    SELECT CAST(MAX(CASE WHEN param_key = 'SHIFTS_PER_PERIOD'      THEN param_value END) AS REAL) AS shifts,
           CAST(MAX(CASE WHEN param_key = 'SHIFT_DURATION_MINUTES' THEN param_value END) AS REAL) AS minutes,
           CAST(MAX(CASE WHEN param_key = 'PLAN_HORIZON'           THEN param_value END) AS REAL) AS nperiod
    FROM core_biz_global_params
),
agg AS (
    SELECT
        fl.resource_code,
        SUM(CASE WHEN fl.period = 1  THEN fl.load ELSE 0 END) AS period_1,
        SUM(CASE WHEN fl.period = 2  THEN fl.load ELSE 0 END) AS period_2,
        SUM(CASE WHEN fl.period = 3  THEN fl.load ELSE 0 END) AS period_3,
        SUM(CASE WHEN fl.period = 4  THEN fl.load ELSE 0 END) AS period_4,
        SUM(CASE WHEN fl.period = 5  THEN fl.load ELSE 0 END) AS period_5,
        SUM(CASE WHEN fl.period = 6  THEN fl.load ELSE 0 END) AS period_6,
        SUM(CASE WHEN fl.period = 7  THEN fl.load ELSE 0 END) AS period_7,
        SUM(CASE WHEN fl.period = 8  THEN fl.load ELSE 0 END) AS period_8,
        SUM(CASE WHEN fl.period = 9  THEN fl.load ELSE 0 END) AS period_9,
        SUM(CASE WHEN fl.period = 10 THEN fl.load ELSE 0 END) AS period_10,
        SUM(CASE WHEN fl.period = 11 THEN fl.load ELSE 0 END) AS period_11,
        SUM(CASE WHEN fl.period = 12 THEN fl.load ELSE 0 END) AS period_12,
        SUM(fl.load) AS load_total,
        MAX(CASE WHEN fl.load > 0.0001 THEN fl.load END) AS max_load,
        SUM(CASE WHEN fl.load > 0.0001 THEN fl.load ELSE 0 END) AS active_load
    FROM res_fixtload fl
    WHERE fl.run_id = (SELECT rid FROM latest)
    GROUP BY fl.resource_code
    HAVING SUM(fl.load) > 0.0001
)
SELECT
    a.resource_code,                                                        -- 工装代码
    a.period_1, a.period_2, a.period_3, a.period_4, a.period_5, a.period_6,
    a.period_7, a.period_8, a.period_9, a.period_10, a.period_11, a.period_12,
    a.max_load * 100.0
        / NULLIF(r.quantity * r.utilization_rate * gp.minutes * gp.shifts, 0)
        AS max_load_rate_pct,                                               -- 最大负荷率 %
    a.active_load * 100.0
        / NULLIF(r.quantity * r.utilization_rate * gp.minutes * gp.shifts, 0)
        / gp.nperiod AS avg_load_rate_pct,                                  -- 平均负荷率 %
    a.load_total * r.unit_cost AS normal_cost_total                         -- 成本小计
FROM agg a
JOIN core_md_resource r ON r.resource_code = a.resource_code
CROSS JOIN gp
ORDER BY a.resource_code;

-- ------------------------------------------------------------
-- 19. 工装超时负荷（Sheet: 工装负荷 - 超时负荷块）
--     列: 工装代码, 周期1..12, 成本小计
--     成本小计 = Σ超时负荷 × 单位成本 × 加班成本倍数（算法 L1942-1943）
-- ------------------------------------------------------------
CREATE VIEW res_view_fixt_overload AS
WITH latest AS (SELECT MAX(run_id) AS rid FROM res_solve_run),
agg AS (
    SELECT
        fp.resource_code,
        SUM(CASE WHEN fp.period = 1  THEN fp.load ELSE 0 END) AS period_1,
        SUM(CASE WHEN fp.period = 2  THEN fp.load ELSE 0 END) AS period_2,
        SUM(CASE WHEN fp.period = 3  THEN fp.load ELSE 0 END) AS period_3,
        SUM(CASE WHEN fp.period = 4  THEN fp.load ELSE 0 END) AS period_4,
        SUM(CASE WHEN fp.period = 5  THEN fp.load ELSE 0 END) AS period_5,
        SUM(CASE WHEN fp.period = 6  THEN fp.load ELSE 0 END) AS period_6,
        SUM(CASE WHEN fp.period = 7  THEN fp.load ELSE 0 END) AS period_7,
        SUM(CASE WHEN fp.period = 8  THEN fp.load ELSE 0 END) AS period_8,
        SUM(CASE WHEN fp.period = 9  THEN fp.load ELSE 0 END) AS period_9,
        SUM(CASE WHEN fp.period = 10 THEN fp.load ELSE 0 END) AS period_10,
        SUM(CASE WHEN fp.period = 11 THEN fp.load ELSE 0 END) AS period_11,
        SUM(CASE WHEN fp.period = 12 THEN fp.load ELSE 0 END) AS period_12,
        SUM(fp.load) AS load_total
    FROM res_fixt_plus fp
    WHERE fp.run_id = (SELECT rid FROM latest)
    GROUP BY fp.resource_code
    HAVING SUM(fp.load) > 0.0001
)
SELECT
    a.resource_code,                                                        -- 工装代码
    a.period_1, a.period_2, a.period_3, a.period_4, a.period_5, a.period_6,
    a.period_7, a.period_8, a.period_9, a.period_10, a.period_11, a.period_12,
    a.load_total * r.unit_cost * r.overtime_cost_multiplier
        AS overload_cost_total                                              -- 成本小计
FROM agg a
JOIN core_md_resource r ON r.resource_code = a.resource_code
ORDER BY a.resource_code;

-- ------------------------------------------------------------
-- 20. 工装影子价格（Sheet: 工装负荷 - 影子价格块）
--     列: 工装代码, 周期1..12；仅 intager=0（算法 L1941）
-- ------------------------------------------------------------
CREATE VIEW res_view_fixt_shadow AS
SELECT
    df.resource_code,                                                       -- 工装代码
    MAX(CASE WHEN df.period = 1  THEN df.dual_value END) AS period_1,
    MAX(CASE WHEN df.period = 2  THEN df.dual_value END) AS period_2,
    MAX(CASE WHEN df.period = 3  THEN df.dual_value END) AS period_3,
    MAX(CASE WHEN df.period = 4  THEN df.dual_value END) AS period_4,
    MAX(CASE WHEN df.period = 5  THEN df.dual_value END) AS period_5,
    MAX(CASE WHEN df.period = 6  THEN df.dual_value END) AS period_6,
    MAX(CASE WHEN df.period = 7  THEN df.dual_value END) AS period_7,
    MAX(CASE WHEN df.period = 8  THEN df.dual_value END) AS period_8,
    MAX(CASE WHEN df.period = 9  THEN df.dual_value END) AS period_9,
    MAX(CASE WHEN df.period = 10 THEN df.dual_value END) AS period_10,
    MAX(CASE WHEN df.period = 11 THEN df.dual_value END) AS period_11,
    MAX(CASE WHEN df.period = 12 THEN df.dual_value END) AS period_12
FROM res_dual_fixt df
WHERE df.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND (SELECT intager FROM res_solve_run
       WHERE run_id = (SELECT MAX(run_id) FROM res_solve_run)) = 0
GROUP BY df.resource_code
ORDER BY df.resource_code;

-- ------------------------------------------------------------
-- 21. 产品不可行（Sheet: 不可行 - 子表1「产品不可行」）
--     列: 物料号, 周期1..12, 小计；Excel 仅输出产品/自制件/设备三类（L1852-1890）
-- ------------------------------------------------------------
CREATE VIEW res_view_inf_prod AS
SELECT
    inf.resource_code AS material_code,                                     -- 物料号
    SUM(CASE WHEN inf.period = 1  THEN inf.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN inf.period = 2  THEN inf.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN inf.period = 3  THEN inf.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN inf.period = 4  THEN inf.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN inf.period = 5  THEN inf.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN inf.period = 6  THEN inf.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN inf.period = 7  THEN inf.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN inf.period = 8  THEN inf.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN inf.period = 9  THEN inf.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN inf.period = 10 THEN inf.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN inf.period = 11 THEN inf.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN inf.period = 12 THEN inf.quantity ELSE 0 END) AS period_12,
    SUM(inf.quantity) AS inf_total                                          -- 小计
FROM res_infeasible inf
WHERE inf.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND inf.inf_type = 'PRODUCT'
GROUP BY inf.resource_code
HAVING SUM(inf.quantity) > 0.0001
ORDER BY inf.resource_code;

-- ------------------------------------------------------------
-- 22. 自制件平衡不可行（Sheet: 不可行 - 子表2「自制件平衡不可行」）
-- ------------------------------------------------------------
CREATE VIEW res_view_inf_self AS
SELECT
    inf.resource_code AS material_code,                                     -- 物料号
    SUM(CASE WHEN inf.period = 1  THEN inf.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN inf.period = 2  THEN inf.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN inf.period = 3  THEN inf.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN inf.period = 4  THEN inf.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN inf.period = 5  THEN inf.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN inf.period = 6  THEN inf.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN inf.period = 7  THEN inf.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN inf.period = 8  THEN inf.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN inf.period = 9  THEN inf.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN inf.period = 10 THEN inf.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN inf.period = 11 THEN inf.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN inf.period = 12 THEN inf.quantity ELSE 0 END) AS period_12,
    SUM(inf.quantity) AS inf_total                                          -- 小计
FROM res_infeasible inf
WHERE inf.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND inf.inf_type = 'SELF'
GROUP BY inf.resource_code
HAVING SUM(inf.quantity) > 0.0001
ORDER BY inf.resource_code;

-- ------------------------------------------------------------
-- 23. 设备能力平衡不可行（Sheet: 不可行 - 子表3「设备能力平衡不可行」）
-- ------------------------------------------------------------
CREATE VIEW res_view_inf_equip AS
SELECT
    inf.resource_code,                                                      -- 设备号
    SUM(CASE WHEN inf.period = 1  THEN inf.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN inf.period = 2  THEN inf.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN inf.period = 3  THEN inf.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN inf.period = 4  THEN inf.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN inf.period = 5  THEN inf.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN inf.period = 6  THEN inf.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN inf.period = 7  THEN inf.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN inf.period = 8  THEN inf.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN inf.period = 9  THEN inf.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN inf.period = 10 THEN inf.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN inf.period = 11 THEN inf.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN inf.period = 12 THEN inf.quantity ELSE 0 END) AS period_12,
    SUM(inf.quantity) AS inf_total                                          -- 小计
FROM res_infeasible inf
WHERE inf.run_id = (SELECT MAX(run_id) FROM res_solve_run)
  AND inf.inf_type = 'EQUIP'
GROUP BY inf.resource_code
HAVING SUM(inf.quantity) > 0.0001
ORDER BY inf.resource_code;

-- ------------------------------------------------------------
-- 24. 替代物料（Sheet: 替代物料）
--     列: 替代物料类型, 替代物料一, 替代物料二, 周期1..12, 数量小计
--     口径（算法 L1954-1974）：按替代规则聚合，仅输出有替代量的规则
-- ------------------------------------------------------------
CREATE VIEW res_view_substitute AS
SELECT
    ar.alt_type_name,                                                       -- 替代物料类型
    ar.from_material_code,                                                  -- 替代物料一（被替代）
    ar.to_material_code,                                                    -- 替代物料二（替代）
    SUM(CASE WHEN s.period = 1  THEN s.quantity ELSE 0 END) AS period_1,
    SUM(CASE WHEN s.period = 2  THEN s.quantity ELSE 0 END) AS period_2,
    SUM(CASE WHEN s.period = 3  THEN s.quantity ELSE 0 END) AS period_3,
    SUM(CASE WHEN s.period = 4  THEN s.quantity ELSE 0 END) AS period_4,
    SUM(CASE WHEN s.period = 5  THEN s.quantity ELSE 0 END) AS period_5,
    SUM(CASE WHEN s.period = 6  THEN s.quantity ELSE 0 END) AS period_6,
    SUM(CASE WHEN s.period = 7  THEN s.quantity ELSE 0 END) AS period_7,
    SUM(CASE WHEN s.period = 8  THEN s.quantity ELSE 0 END) AS period_8,
    SUM(CASE WHEN s.period = 9  THEN s.quantity ELSE 0 END) AS period_9,
    SUM(CASE WHEN s.period = 10 THEN s.quantity ELSE 0 END) AS period_10,
    SUM(CASE WHEN s.period = 11 THEN s.quantity ELSE 0 END) AS period_11,
    SUM(CASE WHEN s.period = 12 THEN s.quantity ELSE 0 END) AS period_12,
    SUM(s.quantity) AS quantity_total                                       -- 数量小计
FROM res_substi s
JOIN core_md_alt_rule ar ON ar.rule_id = s.rule_id
WHERE s.run_id = (SELECT MAX(run_id) FROM res_solve_run)
GROUP BY s.rule_id, ar.alt_type_name, ar.from_material_code, ar.to_material_code
HAVING SUM(s.quantity) > 0.0001
ORDER BY s.rule_id;

-- ------------------------------------------------------------
-- 25. 综合表（Sheet: 综合 - 成本利润块）
-- ------------------------------------------------------------
CREATE VIEW res_view_summary AS
SELECT
    s.run_id,
    sr.run_time,
    s.sales_revenue,                                                        -- 销售收入
    s.delay_penalty,                                                        -- 延期成本
    s.manufacturing_cost,                                                   -- 制造成本
    s.outsource_cost,                                                       -- 外协采购成本
    s.purchase_cost,                                                        -- 原料采购成本
    s.inventory_cost,                                                       -- 库存成本
    s.infeasible_cost,                                                      -- 不可行成本
    s.fixture_cost,                                                         -- 模具成本
    s.profit                                                                -- 利润合计
FROM res_summary s
JOIN res_solve_run sr ON sr.run_id = s.run_id
WHERE s.run_id = (SELECT MAX(run_id) FROM res_solve_run);

-- ------------------------------------------------------------
-- 26. 订单交付汇总（Sheet: 综合 - 订单交付汇总块；占比行由展示层计算）
-- ------------------------------------------------------------
CREATE VIEW res_view_order_delivery AS
SELECT
    od.priority_level,                                                      -- 订单等级
    od.order_count_total,                                                   -- 订单总数
    od.order_count_ontime,                                                  -- 按期交付
    od.order_count_partial,                                                 -- 部分按期
    od.order_count_delayed,                                                 -- 延期交付
    od.order_count_undelivered,                                             -- 未交付
    od.quantity_total,                                                      -- 订单总量
    od.quantity_ontime,                                                     -- 按期交付量
    od.quantity_partial,                                                    -- 部分按期量
    od.quantity_delayed,                                                    -- 延期交付量
    od.quantity_undelivered                                                 -- 未交付量
FROM res_order_delivery od
WHERE od.run_id = (SELECT MAX(run_id) FROM res_solve_run)
ORDER BY od.priority_level;
