-- ============================================================
-- aps_or.db 建表脚本 (DDL)
-- 自动生成，请勿手工编辑
-- 数据库: data/db/aps_or.db
-- 生成时间: 2026-09-04 11:15:30
-- 注意: 索引请见 create_indexes.sql
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 一、建表（stg_ 原始数据层 + core_ 核心数据层）
-- ============================================================

CREATE TABLE stg_system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT,
    config_value TEXT
);
CREATE TABLE stg_bom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    bom_level INTEGER,
    parent_code TEXT,
    parent_name TEXT,
    child_code TEXT,
    child_name TEXT,
    quantity REAL
);
CREATE TABLE stg_routing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    material_code TEXT,
    material_name TEXT,
    alt_route_id INTEGER,
    equipment_code TEXT,
    production_line TEXT,
    operation_name TEXT,
    fixture_code TEXT,
    fixture_quantity INTEGER,
    max_lead_time INTEGER,
    time_offset_1 REAL,
    time_offset_2 REAL,
    time_offset_3 REAL
);
CREATE TABLE stg_equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    equipment_code TEXT,
    unit_cost REAL,
    quantity INTEGER,
    utilization_rate REAL,
    overtime_rate REAL,
    overtime_cost REAL
);
CREATE TABLE stg_fixture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    fixture_code TEXT,
    unit_cost REAL,
    quantity INTEGER,
    utilization_rate REAL,
    overtime_rate REAL,
    overtime_cost REAL
);
CREATE TABLE stg_semi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    semi_code TEXT,
    semi_name TEXT,
    is_virtual INTEGER,
    lead_time INTEGER,
    initial_inventory REAL,
    target_inventory REAL,
    min_inventory REAL,
    max_inventory REAL,
    holding_cost_rate REAL
);
CREATE TABLE stg_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    raw_code TEXT,
    raw_name TEXT,
    purchase_cost REAL,
    purchase_lead_time INTEGER,
    initial_inventory REAL,
    target_inventory REAL,
    min_inventory REAL,
    max_inventory REAL,
    holding_cost_rate REAL
);
CREATE TABLE stg_wip (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    wip_category TEXT,
    semi_category TEXT,
    material_code TEXT,
    material_name TEXT,
    total_lead_time INTEGER,
    completed_stages INTEGER,
    quantity REAL
);
CREATE TABLE stg_outsource (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    material_code TEXT,
    unit_price REAL,
    period_01 REAL, period_02 REAL, period_03 REAL, period_04 REAL,
    period_05 REAL, period_06 REAL, period_07 REAL, period_08 REAL,
    period_09 REAL, period_10 REAL, period_11 REAL, period_12 REAL,
    period_13 REAL, period_14 REAL, period_15 REAL, period_16 REAL,
    period_17 REAL, period_18 REAL, period_19 REAL, period_20 REAL,
    period_21 REAL, period_22 REAL, period_23 REAL, period_24 REAL,
    period_25 REAL, period_26 REAL, period_27 REAL, period_28 REAL,
    total REAL
);
CREATE TABLE stg_purchase_limit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    material_code TEXT,
    material_name TEXT,
    period_01 REAL, period_02 REAL, period_03 REAL, period_04 REAL,
    period_05 REAL, period_06 REAL, period_07 REAL, period_08 REAL,
    period_09 REAL, period_10 REAL, period_11 REAL, period_12 REAL,
    period_13 REAL, period_14 REAL, period_15 REAL, period_16 REAL,
    period_17 REAL, period_18 REAL, period_19 REAL, period_20 REAL,
    period_21 REAL, period_22 REAL, period_23 REAL, period_24 REAL,
    period_25 REAL, period_26 REAL, period_27 REAL, period_28 REAL,
    total REAL
);
CREATE TABLE stg_alternative (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    alt_type INTEGER,
    from_material_code TEXT,
    from_quantity REAL,
    to_material_code TEXT,
    to_quantity REAL,
    ratio REAL,
    is_batch INTEGER,
    period_01 REAL, period_02 REAL, period_03 REAL, period_04 REAL,
    period_05 REAL, period_06 REAL, period_07 REAL, period_08 REAL,
    period_09 REAL, period_10 REAL, period_11 REAL, period_12 REAL,
    period_13 REAL, period_14 REAL, period_15 REAL, period_16 REAL,
    period_17 REAL, period_18 REAL, period_19 REAL, period_20 REAL,
    period_21 REAL, period_22 REAL, period_23 REAL, period_24 REAL,
    period_25 REAL, period_26 REAL, period_27 REAL, period_28 REAL
);
            table_name TEXT PRIMARY KEY,
            comment TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
            table_name TEXT,
            column_name TEXT,
            comment TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (table_name, column_name)
        );
CREATE TABLE IF NOT EXISTS "stg_orders" (
	"id"	INTEGER,
	"order_id"	TEXT,
	"product_code"	TEXT,
	"order_price"	REAL,
	"order_quantity"	REAL,
	"due_period"	INTEGER,
	"priority_level"	INTEGER,
	"max_delay_allowed"	REAL,
	"delay_penalty"	REAL,
	"production_lead_time"	INTEGER,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE stg_product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER,
    product_code TEXT,
    product_name TEXT,
    product_cost REAL,
    product_price REAL,
    lead_time INTEGER,
    initial_inventory REAL,
    target_inventory REAL,
    min_inventory REAL,
    max_inventory REAL,
    holding_cost_rate REAL
);
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
        );
CREATE TABLE IF NOT EXISTS "core_md_operation" (
    operation_code TEXT PRIMARY KEY,
    operation_name TEXT
);
CREATE TABLE IF NOT EXISTS "core_md_purchase_limit" (
	"material_code"	TEXT,
	"note"	TEXT,
	PRIMARY KEY("material_code"),
	FOREIGN KEY("material_code") REFERENCES "MATERIAL_MASTER"("material_code") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "core_md_outsource" (
	"material_code"	TEXT,
	"unit_price"	NUMERIC(18, 4),
	PRIMARY KEY("material_code"),
	FOREIGN KEY("material_code") REFERENCES "MATERIAL_MASTER"("material_code") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "core_md_material" (
    material_code        TEXT PRIMARY KEY,
    material_name       TEXT NOT NULL,
    category             TEXT NOT NULL CHECK(category IN ('PRODUCT', 'SEMI', 'RAW')),
    unit                 TEXT DEFAULT '个',
    initial_inventory    NUMERIC(18,4) DEFAULT 0,
    target_end_inventory NUMERIC(18,4) DEFAULT 0,
    min_inventory        NUMERIC(18,4) DEFAULT 0,
    max_inventory        NUMERIC(18,4) DEFAULT 100000,
    holding_cost_rate    NUMERIC(10,6) DEFAULT 0
);
CREATE TABLE IF NOT EXISTS "core_md_product_ext" (
    material_code       TEXT PRIMARY KEY,
    standard_cost       NUMERIC(18,4),
    standard_price      NUMERIC(18,4),
    assembly_lead_time  INTEGER DEFAULT 0,
    sales_status        TEXT DEFAULT 'ACTIVE',
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "core_md_semi_ext" (
    material_code          TEXT PRIMARY KEY,
    is_virtual             INTEGER DEFAULT 0 CHECK(is_virtual IN (0,1)),
    manufacturing_lead_time INTEGER DEFAULT 0,
    default_routing_id     INTEGER,
    scrap_rate             NUMERIC(10,6) DEFAULT 0, outsource_price NUMERIC(18,4) DEFAULT 0,
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "core_md_raw_ext" (
    material_code      TEXT PRIMARY KEY,
    purchase_cost      NUMERIC(18,4),
    purchase_lead_time INTEGER DEFAULT 0,
    preferred_supplier TEXT,
    moq                INTEGER DEFAULT 0,
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "core_md_resource" (
    resource_code           TEXT PRIMARY KEY,
    resource_name           TEXT,
    resource_type           TEXT NOT NULL CHECK(resource_type IN ('EQUIPMENT', 'FIXTURE')),
    line_code               TEXT,
    quantity                INTEGER DEFAULT 1,
    unit_cost               NUMERIC(18,4),
    utilization_rate        NUMERIC(10,6) DEFAULT 0.9,
    overtime_rate           NUMERIC(10,6) DEFAULT 0,
    overtime_cost_multiplier NUMERIC(10,6) DEFAULT 1.0,
    FOREIGN KEY (line_code) REFERENCES core_md_line(line_code) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "core_md_line" (
    line_code   TEXT PRIMARY KEY,
    line_name   TEXT,
    line_type   TEXT DEFAULT 'production',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE core_biz_demand_order (
    order_id              INTEGER PRIMARY KEY,
    product_code          TEXT NOT NULL,
    price                 NUMERIC(18,4),
    quantity              NUMERIC(18,4) NOT NULL,
    due_period            INTEGER NOT NULL,
    priority_level        INTEGER DEFAULT 3,
    max_delay_allowed     INTEGER DEFAULT 0,
    delay_penalty         NUMERIC(18,4) DEFAULT 0,
    FOREIGN KEY (product_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE core_biz_bom (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_material_code  TEXT NOT NULL,
    child_material_code   TEXT NOT NULL,
    quantity              NUMERIC(18,4) DEFAULT 1,
    bom_level             INTEGER,
    FOREIGN KEY (parent_material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE,
    FOREIGN KEY (child_material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE core_biz_wip (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code            TEXT NOT NULL,
    quantity                 NUMERIC(18,4) NOT NULL,
    completed_stages         INTEGER DEFAULT 0,
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE core_biz_outsource_period_limit (
    material_code        TEXT NOT NULL,
    period_index         INTEGER NOT NULL,
    max_quantity         NUMERIC(18,4),
    PRIMARY KEY (material_code, period_index),
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE core_biz_purchase_period_limit (
    material_code        TEXT NOT NULL,
    period_index         INTEGER NOT NULL,
    max_purchase_quantity NUMERIC(18,4),
    PRIMARY KEY (material_code, period_index),
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE core_biz_alt_period_limit (
    rule_id                 INTEGER NOT NULL,
    period_index            INTEGER NOT NULL,
    max_alternative_quantity NUMERIC(18,4),
    PRIMARY KEY (rule_id, period_index),
    FOREIGN KEY (rule_id) REFERENCES core_md_alt_rule(rule_id) ON DELETE CASCADE
);
CREATE TABLE core_biz_routing_header (
    routing_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code         TEXT NOT NULL,
    alt_route_id          INTEGER DEFAULT 1,
    total_lead_time       INTEGER NOT NULL,
    is_default            INTEGER DEFAULT 1 CHECK(is_default IN (0,1)),
    is_active             INTEGER DEFAULT 1 CHECK(is_active IN (0,1)),
    FOREIGN KEY (material_code) REFERENCES core_md_material(material_code) ON DELETE CASCADE
);
CREATE TABLE core_biz_routing_step (
    step_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    routing_id            INTEGER NOT NULL,
    step_order            INTEGER NOT NULL,
    operation_code        TEXT NOT NULL,
    equipment_code        TEXT NOT NULL,
    production_line_code  TEXT,
    fixture_code          TEXT,
    fixture_quantity      INTEGER DEFAULT 0,
    max_lead_time         INTEGER NOT NULL,
    FOREIGN KEY (routing_id) REFERENCES core_biz_routing_header(routing_id) ON DELETE CASCADE,
    FOREIGN KEY (operation_code) REFERENCES core_md_operation(operation_code) ON DELETE CASCADE,
    FOREIGN KEY (equipment_code) REFERENCES core_md_resource(resource_code) ON DELETE CASCADE,
    FOREIGN KEY (production_line_code) REFERENCES core_md_line(line_code) ON DELETE SET NULL,
    FOREIGN KEY (fixture_code) REFERENCES core_md_resource(resource_code) ON DELETE SET NULL
);
CREATE TABLE core_biz_step_time_offset (
    step_id               INTEGER NOT NULL,
    offset_index          INTEGER NOT NULL,
    duration              NUMERIC(18,4) DEFAULT 0,
    PRIMARY KEY (step_id, offset_index),
    FOREIGN KEY (step_id) REFERENCES core_biz_routing_step(step_id) ON DELETE CASCADE
);
CREATE TABLE core_biz_global_params (
    param_key            TEXT PRIMARY KEY,
    param_value          TEXT,
    description          TEXT
);
/* "alg_sheet_订单表"("订单序号","产品代码","订单价格","订单数量","订单交期","订单等级","允许延期","延期罚金","生产提前期") */;
/* "alg_sheet_产品表"("序号","产品代码","产品名称","产品成本","产品价格","提前期","初始库存","期末库存","最小库存","最大库存","库存成本") */;
/* "alg_sheet_原材料表"("序号","原料代码","物料名称","采购成本","采购提前期","初始库存","期末库存","最小库存","最大库存","库存成本") */;
/* alg_sheet_BOM("序号","BOM层级","父物料","父物料名称","子物料","子物料名称","数量") */;
/* "alg_sheet_设备表"("序号","设备代码","单位成本","设备数","设备利用率","加班率","加班成本") */;
/* "alg_sheet_工装表"("序号","工装代码","工装成本","工装数","工装利用率","加班率","加班成本") */;
/* "alg_sheet_在制品"("序号","在制品种类代码","自制品种类","在制件代码","在制件名称","总制造期","已完成阶段","在制数量") */;
/* "alg_sheet_自制件"("序号","自制件代码","自制件名称","虚拟件属性","提前期","初始库存","期末库存","最小库存","最大库存","库存成本","外协价格") */;
/* "alg_sheet_外协"("序号","物料代码","外协价格","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28","合计") */;
/* "alg_sheet_采购限制"("序号","原料代码","物料名称","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28","合计") */;
/* "alg_sheet_替代关系"("序号","替代类型编码","替代类型名称","替代物料一代码","数量一","替代物料二代码","数量二","比例","整批","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28") */;
/* "alg_sheet_工艺路线"("序号","物料代码","物料名称","多工艺","设备代码","生产线","工序","工装代码","工装数量",MaxT,"1","2","3") */;
/* "alg_sheet_综合表"("主要参数","参数值") */;
/* alg_named_dayshift(dayshift) */;
/* alg_named_dutytime(dutytime) */;
/* alg_named_maxpro(maxpro) */;
/* alg_named_nbom(nbom) */;
/* alg_named_ndemrate(ndemrate) */;
/* alg_named_nequip(nequip) */;
/* alg_named_nfixtable(nfixtable) */;
/* alg_named_nfixture(nfixture) */;
/* alg_named_nordclass(nordclass) */;
/* alg_named_nordelay(nordelay) */;
/* alg_named_norder(norder) */;
/* alg_named_nouttable(nouttable) */;
/* alg_named_nperiod(nperiod) */;
/* alg_named_nplant(nplant) */;
/* alg_named_npmaxt(npmaxt) */;
/* alg_named_nproduct(nproduct) */;
/* alg_named_nrawlimtable(nrawlimtable) */;
/* alg_named_nrawmat(nrawmat) */;
/* alg_named_nrouting(nrouting) */;
/* alg_named_nselfmade(nselfmade) */;
/* alg_named_nsubtable(nsubtable) */;
/* alg_named_nwiptable(nwiptable) */;
/* alg_named_OrdCls(OrdCls) */;
/* alg_named_OrdDly(OrdDly) */;
/* alg_named_OrdFine(OrdFine) */;
/* alg_named_OrdNo(OrdNo) */;
/* alg_named_OrdPrice(OrdPrice) */;
/* alg_named_OrdProd(OrdProd) */;
/* alg_named_OrdQunt(OrdQunt) */;
/* alg_named_OrdTime(OrdTime) */;
/* alg_named_BomLevel(BomLevel) */;
/* alg_named_Fcode(Fcode) */;
/* alg_named_Quant(Quant) */;
/* alg_named_Scode(Scode) */;
/* alg_named_EquipCost(EquipCost) */;
/* alg_named_EquipId(EquipId) */;
/* alg_named_EquipNumb(EquipNumb) */;
/* alg_named_EquipOverR(EquipOverR) */;
/* alg_named_EquipOverT(EquipOverT) */;
/* alg_named_EquipRate(EquipRate) */;
/* alg_named_FixtCost(FixtCost) */;
/* alg_named_FixtId(FixtId) */;
/* alg_named_FixtNo(FixtNo) */;
/* alg_named_FixtOver(FixtOver) */;
/* alg_named_FixtQunt(FixtQunt) */;
/* alg_named_FixtRate(FixtRate) */;
/* alg_named_Fovcost(Fovcost) */;
/* alg_named_Price(Price) */;
/* alg_named_ProdCode(ProdCode) */;
/* alg_named_ProdCost(ProdCost) */;
/* alg_named_ProdInv0(ProdInv0) */;
/* alg_named_ProdInvCost(ProdInvCost) */;
/* alg_named_ProdInvL(ProdInvL) */;
/* alg_named_ProdInvT(ProdInvT) */;
/* alg_named_ProdInvU(ProdInvU) */;
/* alg_named_ProdLeadtime(ProdLeadtime) */;
/* alg_named_ProEquip(ProEquip) */;
/* alg_named_ProFixq(ProFixq) */;
/* alg_named_ProFixt(ProFixt) */;
/* alg_named_ProHour("1","2","3") */;
/* alg_named_ProMat(ProMat) */;
/* alg_named_ProMaxT(ProMaxT) */;
/* alg_named_ProMult(ProMult) */;
/* alg_named_ProState(ProState) */;
/* alg_named_RawCode(RawCode) */;
/* alg_named_RawCost(RawCost) */;
/* alg_named_RawInv0(RawInv0) */;
/* alg_named_RawInvCost(RawInvCost) */;
/* alg_named_RawInvL(RawInvL) */;
/* alg_named_RawInvT(RawInvT) */;
/* alg_named_RawInvU(RawInvU) */;
/* alg_named_RawLeadtime(RawLeadtime) */;
/* alg_named_RlimId(RlimId) */;
/* alg_named_RlimNo(RlimNo) */;
SELECT
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28"
FROM alg_sheet_采购限制
/* alg_named_RlimQunt("1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28") */;
/* alg_named_OutsCode(OutsCode) */;
/* alg_named_OutsCost(OutsCost) */;
/* alg_named_OutsNo(OutsNo) */;
SELECT
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28"
FROM alg_sheet_外协
/* alg_named_OutsQunt("1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28") */;
/* alg_named_SubBatch(SubBatch) */;
/* alg_named_SubCode1(SubCode1) */;
/* alg_named_SubCode2(SubCode2) */;
/* alg_named_SubQunt1(SubQunt1) */;
/* alg_named_SubQunt2(SubQunt2) */;
/* alg_named_SubRatio(SubRatio) */;
/* alg_named_SubstiNo(SubstiNo) */;
/* alg_named_SubType(SubType) */;
SELECT
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28"
FROM alg_sheet_替代关系
/* alg_named_Sublimit("1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28") */;
/* alg_named_WipCode(WipCode) */;
/* alg_named_WipMaxT(WipMaxT) */;
/* alg_named_WipNo(WipNo) */;
/* alg_named_WipQunt(WipQunt) */;
/* alg_named_WipStage(WipStage) */;
/* alg_named_SelfCode(SelfCode) */;
/* alg_named_SelfDummy(SelfDummy) */;
/* alg_named_SelfLeadtime(SelfLeadtime) */;
/* alg_named_SelfInv0(SelfInv0) */;
/* alg_named_SelfInvT(SelfInvT) */;
/* alg_named_SelfInvL(SelfInvL) */;
/* alg_named_SelfInvU(SelfInvU) */;
/* alg_named_SelfInvCost(SelfInvCost) */;
