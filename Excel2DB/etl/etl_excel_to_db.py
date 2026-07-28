import sqlite3
import xlrd
import os

def create_tables(conn):
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS material (
            code TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            cost REAL,
            lead_time INTEGER,
            inv0 REAL,
            inv_t REAL,
            inv_l REAL,
            inv_u REAL,
            inv_cost REAL,
            price REAL,
            dummy INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row_order INTEGER,
            seq INTEGER,
            group_id INTEGER,
            material_code TEXT,
            material_name TEXT,
            process_alt INTEGER,
            equipment_code TEXT,
            production_line TEXT,
            stage_name TEXT,
            tooling_code TEXT,
            tooling_quantity INTEGER,
            max_t INTEGER,
            stage_1 REAL,
            stage_2 REAL,
            stage_3 REAL,
            stage_4 REAL,
            stage_5 REAL,
            stage_6 REAL,
            stage_7 REAL,
            stage_8 REAL,
            stage_9 REAL,
            stage_10 REAL,
            FOREIGN KEY (material_code) REFERENCES material(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            cost REAL,
            number INTEGER,
            rate REAL,
            overtime_rate REAL,
            overtime REAL,
            cost_t REAL,
            cost_u REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tooling (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT,
            cost REAL,
            quantity INTEGER,
            rate REAL,
            overtime INTEGER,
            overtime_cost REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            no TEXT,
            cls INTEGER,
            prod_code TEXT,
            price REAL,
            quantity REAL,
            time INTEGER,
            delay INTEGER,
            fine REAL,
            FOREIGN KEY (prod_code) REFERENCES material(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            seq INTEGER,
            parent_code TEXT,
            parent_name TEXT,
            child_code TEXT,
            child_name TEXT,
            quantity REAL,
            level INTEGER,
            FOREIGN KEY (parent_code) REFERENCES material(code),
            FOREIGN KEY (child_code) REFERENCES material(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outsource (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT,
            cost REAL,
            quantity_t1 REAL,
            quantity_t2 REAL,
            quantity_t3 REAL,
            quantity_t4 REAL,
            quantity_t5 REAL,
            quantity_t6 REAL,
            quantity_t7 REAL,
            quantity_t8 REAL,
            quantity_t9 REAL,
            quantity_t10 REAL,
            quantity_t11 REAL,
            quantity_t12 REAL,
            quantity_t13 REAL,
            quantity_t14 REAL,
            quantity_t15 REAL,
            quantity_t16 REAL,
            quantity_t17 REAL,
            quantity_t18 REAL,
            quantity_t19 REAL,
            quantity_t20 REAL,
            quantity_t21 REAL,
            quantity_t22 REAL,
            quantity_t23 REAL,
            quantity_t24 REAL,
            quantity_t25 REAL,
            quantity_t26 REAL,
            quantity_t27 REAL,
            quantity_t28 REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_limit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_code TEXT,
            material_name TEXT,
            quantity_t1 REAL,
            quantity_t2 REAL,
            quantity_t3 REAL,
            quantity_t4 REAL,
            quantity_t5 REAL,
            quantity_t6 REAL,
            quantity_t7 REAL,
            quantity_t8 REAL,
            quantity_t9 REAL,
            quantity_t10 REAL,
            quantity_t11 REAL,
            quantity_t12 REAL,
            quantity_t13 REAL,
            quantity_t14 REAL,
            quantity_t15 REAL,
            quantity_t16 REAL,
            quantity_t17 REAL,
            quantity_t18 REAL,
            quantity_t19 REAL,
            quantity_t20 REAL,
            quantity_t21 REAL,
            quantity_t22 REAL,
            quantity_t23 REAL,
            quantity_t24 REAL,
            quantity_t25 REAL,
            quantity_t26 REAL,
            quantity_t27 REAL,
            quantity_t28 REAL,
            FOREIGN KEY (material_code) REFERENCES material(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS substitute (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seq INTEGER,
            sub_type INTEGER,
            material_type TEXT,
            desc TEXT,
            code1 TEXT,
            quantity1 REAL,
            code2 TEXT,
            quantity2 REAL,
            ratio REAL,
            batch INTEGER,
            limit_q1 REAL,
            limit_q2 REAL,
            limit_q3 REAL,
            limit_q4 REAL,
            limit_q5 REAL,
            limit_q6 REAL,
            limit_q7 REAL,
            limit_q8 REAL,
            limit_q9 REAL,
            limit_q10 REAL,
            limit_q11 REAL,
            limit_q12 REAL,
            limit_q13 REAL,
            limit_q14 REAL,
            limit_q15 REAL,
            limit_q16 REAL,
            limit_q17 REAL,
            limit_q18 REAL,
            limit_q19 REAL,
            limit_q20 REAL,
            limit_q21 REAL,
            limit_q22 REAL,
            limit_q23 REAL,
            limit_q24 REAL,
            limit_q25 REAL,
            limit_q26 REAL,
            limit_q27 REAL,
            limit_q28 REAL,
            FOREIGN KEY (code1) REFERENCES material(code),
            FOREIGN KEY (code2) REFERENCES material(code)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wip (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_code TEXT,
            material_name TEXT,
            max_t INTEGER,
            stage INTEGER,
            quantity REAL,
            FOREIGN KEY (material_code) REFERENCES material(code)
        )
    ''')
    
    conn.commit()

def get_named_range(book, range_name):
    if range_name not in book.name_map:
        return None
    name_list = book.name_map[range_name]
    if isinstance(name_list, list) and len(name_list) > 0:
        return name_list[0]
    return name_list

def read_range(book, range_name):
    nrange = get_named_range(book, range_name)
    if nrange is None:
        return []
    area = nrange.area2d()
    sheet = area[0]
    row_first, row_last, col_first, col_last = area[1], area[2], area[3], area[4]
    
    row_first = max(0, row_first)
    row_last = min(sheet.nrows - 1, row_last)
    col_first = max(0, col_first)
    col_last = min(sheet.ncols - 1, col_last)
    
    if row_first > row_last or col_first > col_last:
        return []
    
    rows = []
    for row_idx in range(row_first, row_last + 1):
        row = []
        for col_idx in range(col_first, col_last + 1):
            val = sheet.cell_value(row_idx, col_idx)
            if isinstance(val, float) and val == int(val):
                val = int(val)
            row.append(val)
        rows.append(row)
    return rows

def read_cell(book, cell_name):
    nrange = get_named_range(book, cell_name)
    if nrange is None:
        return None
    cell_val = nrange.cell()
    if hasattr(cell_val, 'value'):
        val = cell_val.value
    elif hasattr(cell_val, 'number'):
        val = cell_val.number
    else:
        val = cell_val
    if isinstance(val, float) and val == int(val):
        val = int(val)
    return val

def load_system_config(book, conn):
    cursor = conn.cursor()
    config_items = [
        'nperiod', 'nproduct', 'nselfmade', 'nrawmat', 'nequip', 
        'norder', 'nbom', 'nrouting', 'nfixture', 'nfixtable',
        'nouttable', 'nrawlimtable', 'nsubtable', 'nwiptable',
        'ndemrate', 'nordclass', 'nordelay', 'nplant', 'npmaxt',
        'dutytime', 'dayshift', 'maxpro'
    ]
    for item in config_items:
        val = read_cell(book, item)
        if val is not None:
            cursor.execute('INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)', (item, str(val)))
    conn.commit()
    print('✅ 系统配置导入完成')

def load_materials(book, conn):
    cursor = conn.cursor()
    
    prod_sheet = book.sheet_by_name('产品表')
    for row_idx in range(2, prod_sheet.nrows):
        code = prod_sheet.cell_value(row_idx, 2)
        name = prod_sheet.cell_value(row_idx, 3)
        cost = prod_sheet.cell_value(row_idx, 4)
        price = prod_sheet.cell_value(row_idx, 5)
        lead_time = int(prod_sheet.cell_value(row_idx, 6)) if prod_sheet.cell_value(row_idx, 6) else 0
        inv0 = prod_sheet.cell_value(row_idx, 7)
        inv_t = prod_sheet.cell_value(row_idx, 8)
        inv_l = prod_sheet.cell_value(row_idx, 9)
        inv_u = prod_sheet.cell_value(row_idx, 10)
        inv_cost = prod_sheet.cell_value(row_idx, 11)
        
        cursor.execute('INSERT OR REPLACE INTO material VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (code, name, 'PRODUCT', cost, lead_time, inv0, inv_t, inv_l, inv_u, inv_cost, price, None))
    
    self_sheet = book.sheet_by_name('自制件')
    for row_idx in range(2, self_sheet.nrows):
        code = self_sheet.cell_value(row_idx, 2)
        name = self_sheet.cell_value(row_idx, 3)
        dummy = int(self_sheet.cell_value(row_idx, 4)) if self_sheet.cell_value(row_idx, 4) else 0
        lead_time = int(self_sheet.cell_value(row_idx, 5)) if self_sheet.cell_value(row_idx, 5) else 0
        inv0 = self_sheet.cell_value(row_idx, 6)
        inv_t = self_sheet.cell_value(row_idx, 7)
        inv_l = self_sheet.cell_value(row_idx, 8)
        inv_u = self_sheet.cell_value(row_idx, 9)
        inv_cost = self_sheet.cell_value(row_idx, 10)
        
        cursor.execute('INSERT OR REPLACE INTO material VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (code, name, 'SEMI', None, lead_time, inv0, inv_t, inv_l, inv_u, inv_cost, None, dummy))
    
    raw_sheet = book.sheet_by_name('原材料表')
    for row_idx in range(2, raw_sheet.nrows):
        code = raw_sheet.cell_value(row_idx, 1)
        name = raw_sheet.cell_value(row_idx, 2)
        cost = raw_sheet.cell_value(row_idx, 3)
        lead_time = int(raw_sheet.cell_value(row_idx, 4)) if raw_sheet.cell_value(row_idx, 4) else 0
        inv0 = raw_sheet.cell_value(row_idx, 5)
        inv_t = raw_sheet.cell_value(row_idx, 6)
        inv_l = raw_sheet.cell_value(row_idx, 7)
        inv_u = raw_sheet.cell_value(row_idx, 8)
        inv_cost = raw_sheet.cell_value(row_idx, 9)
        
        cursor.execute('INSERT OR REPLACE INTO material VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (code, name, 'RAW', cost, lead_time, inv0, inv_t, inv_l, inv_u, inv_cost, None, None))
    
    conn.commit()
    print('✅ 物料数据导入完成')

def load_routing(book, conn):
    cursor = conn.cursor()
    
    routing_sheet = book.sheet_by_name('工艺路线 ')
    for row_idx in range(2, routing_sheet.nrows):
        row_order = row_idx - 1
        seq = int(routing_sheet.cell_value(row_idx, 1)) if routing_sheet.cell_value(row_idx, 1) else 0
        group_id = int(routing_sheet.cell_value(row_idx, 0)) if routing_sheet.cell_value(row_idx, 0) else 0
        material_code = routing_sheet.cell_value(row_idx, 2)
        material_name = routing_sheet.cell_value(row_idx, 3)
        process_alt = int(routing_sheet.cell_value(row_idx, 4)) if routing_sheet.cell_value(row_idx, 4) else 0
        equipment_code = routing_sheet.cell_value(row_idx, 5)
        production_line = routing_sheet.cell_value(row_idx, 6)
        stage_name = routing_sheet.cell_value(row_idx, 7)
        tooling_code = routing_sheet.cell_value(row_idx, 8)
        tooling_quantity = int(routing_sheet.cell_value(row_idx, 9)) if routing_sheet.cell_value(row_idx, 9) else 0
        max_t = int(routing_sheet.cell_value(row_idx, 10)) if routing_sheet.cell_value(row_idx, 10) else 0
        
        stages = []
        for col_idx in range(11, min(21, routing_sheet.ncols)):
            stages.append(routing_sheet.cell_value(row_idx, col_idx))
        while len(stages) < 10:
            stages.append(0)
        
        cursor.execute('''
            INSERT INTO routing (row_order, seq, group_id, material_code, material_name, process_alt, equipment_code, 
                production_line, stage_name, tooling_code, tooling_quantity, max_t,
                stage_1, stage_2, stage_3, stage_4, stage_5, stage_6, stage_7, stage_8, stage_9, stage_10)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row_order, seq, group_id, material_code, material_name, process_alt, equipment_code,
            production_line, stage_name, tooling_code, tooling_quantity, max_t,
            stages[0], stages[1], stages[2], stages[3], stages[4],
            stages[5], stages[6], stages[7], stages[8], stages[9]
        ))
    
    conn.commit()
    print('✅ 工艺路线导入完成')

def load_equipment(book, conn):
    cursor = conn.cursor()
    
    equip_sheet = book.sheet_by_name('设备表')
    for row_idx in range(2, equip_sheet.nrows):
        code = equip_sheet.cell_value(row_idx, 2)
        cost = equip_sheet.cell_value(row_idx, 3)
        number = int(equip_sheet.cell_value(row_idx, 4)) if equip_sheet.cell_value(row_idx, 4) else 0
        rate = equip_sheet.cell_value(row_idx, 5)
        overtime_rate = equip_sheet.cell_value(row_idx, 6)
        overtime = equip_sheet.cell_value(row_idx, 7)
        cost_t = equip_sheet.cell_value(row_idx, 17) if equip_sheet.ncols > 17 else 0
        cost_u = equip_sheet.cell_value(row_idx, 18) if equip_sheet.ncols > 18 else 0
        
        cursor.execute('''
            INSERT INTO equipment (code, cost, number, rate, overtime_rate, overtime, cost_t, cost_u)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, cost, number, rate, overtime_rate, overtime, cost_t, cost_u))
    
    conn.commit()
    print('✅ 设备数据导入完成')

def load_tooling(book, conn):
    cursor = conn.cursor()
    
    fixt_sheet = book.sheet_by_name('工装表')
    for row_idx in range(2, fixt_sheet.nrows):
        code = fixt_sheet.cell_value(row_idx, 2)
        name = ''
        cost = fixt_sheet.cell_value(row_idx, 3)
        quantity = int(fixt_sheet.cell_value(row_idx, 4)) if fixt_sheet.cell_value(row_idx, 4) else 0
        rate = fixt_sheet.cell_value(row_idx, 5)
        overtime = fixt_sheet.cell_value(row_idx, 6)
        overtime_cost = fixt_sheet.cell_value(row_idx, 7)
        
        cursor.execute('''
            INSERT INTO tooling (code, name, cost, quantity, rate, overtime, overtime_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, cost, quantity, rate, overtime, overtime_cost))
    
    conn.commit()
    print('✅ 工装数据导入完成')

def load_orders(book, conn):
    cursor = conn.cursor()
    
    ord_sheet = book.sheet_by_name('订单表')
    for row_idx in range(2, ord_sheet.nrows):
        no = int(ord_sheet.cell_value(row_idx, 1)) if ord_sheet.cell_value(row_idx, 1) else 0
        prod_code = ord_sheet.cell_value(row_idx, 2)
        price = ord_sheet.cell_value(row_idx, 3)
        quantity = ord_sheet.cell_value(row_idx, 4)
        time = int(ord_sheet.cell_value(row_idx, 5)) if ord_sheet.cell_value(row_idx, 5) else 0
        cls = int(ord_sheet.cell_value(row_idx, 6)) if ord_sheet.cell_value(row_idx, 6) else 0
        delay = int(ord_sheet.cell_value(row_idx, 7)) if ord_sheet.cell_value(row_idx, 7) else 0
        fine = ord_sheet.cell_value(row_idx, 8)
        
        cursor.execute('''
            INSERT INTO orders (no, cls, prod_code, price, quantity, time, delay, fine)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (no, cls, prod_code, price, quantity, time, delay, fine))
    
    conn.commit()
    print('✅ 订单数据导入完成')

def load_bom(book, conn):
    cursor = conn.cursor()
    
    bom_sheet = book.sheet_by_name('BOM')
    for row_idx in range(2, bom_sheet.nrows):
        group_id = int(bom_sheet.cell_value(row_idx, 0)) if bom_sheet.cell_value(row_idx, 0) else 0
        seq = int(bom_sheet.cell_value(row_idx, 1)) if bom_sheet.cell_value(row_idx, 1) else 0
        level = int(bom_sheet.cell_value(row_idx, 2)) if bom_sheet.cell_value(row_idx, 2) else 0
        parent_code = bom_sheet.cell_value(row_idx, 3)
        parent_name = bom_sheet.cell_value(row_idx, 4)
        child_code = bom_sheet.cell_value(row_idx, 5)
        child_name = bom_sheet.cell_value(row_idx, 6)
        quantity = bom_sheet.cell_value(row_idx, 7)
        
        cursor.execute('''
            INSERT INTO bom (group_id, seq, parent_code, parent_name, child_code, child_name, quantity, level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (group_id, seq, parent_code, parent_name, child_code, child_name, quantity, level))
    
    conn.commit()
    print('✅ BOM数据导入完成')

def load_outsource(book, conn):
    cursor = conn.cursor()
    
    out_sheet = book.sheet_by_name('外协')
    
    for row_idx in range(2, out_sheet.nrows):
        code = out_sheet.cell_value(row_idx, 2)
        name = ''
        cost = out_sheet.cell_value(row_idx, 3)
        
        quantities = []
        for col_idx in range(4, min(32, out_sheet.ncols)):
            quantities.append(out_sheet.cell_value(row_idx, col_idx))
        while len(quantities) < 28:
            quantities.append(0)
        
        cursor.execute('''
            INSERT INTO outsource (code, name, cost, 
                quantity_t1, quantity_t2, quantity_t3, quantity_t4, quantity_t5, quantity_t6,
                quantity_t7, quantity_t8, quantity_t9, quantity_t10, quantity_t11, quantity_t12,
                quantity_t13, quantity_t14, quantity_t15, quantity_t16, quantity_t17, quantity_t18,
                quantity_t19, quantity_t20, quantity_t21, quantity_t22, quantity_t23, quantity_t24,
                quantity_t25, quantity_t26, quantity_t27, quantity_t28)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, cost) + tuple(quantities[:28]))
    
    conn.commit()
    print('✅ 外协数据导入完成')

def load_purchase_limit(book, conn):
    cursor = conn.cursor()
    
    lim_sheet = book.sheet_by_name('采购限制')
    
    for row_idx in range(2, lim_sheet.nrows):
        material_code = lim_sheet.cell_value(row_idx, 2)
        material_name = lim_sheet.cell_value(row_idx, 3)
        
        quantities = []
        for col_idx in range(4, min(32, lim_sheet.ncols)):
            quantities.append(lim_sheet.cell_value(row_idx, col_idx))
        while len(quantities) < 28:
            quantities.append(0)
        
        cursor.execute('''
            INSERT INTO purchase_limit (material_code, material_name, 
                quantity_t1, quantity_t2, quantity_t3, quantity_t4, quantity_t5, quantity_t6,
                quantity_t7, quantity_t8, quantity_t9, quantity_t10, quantity_t11, quantity_t12,
                quantity_t13, quantity_t14, quantity_t15, quantity_t16, quantity_t17, quantity_t18,
                quantity_t19, quantity_t20, quantity_t21, quantity_t22, quantity_t23, quantity_t24,
                quantity_t25, quantity_t26, quantity_t27, quantity_t28)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (material_code, material_name) + tuple(quantities[:28]))
    
    conn.commit()
    print('✅ 采购限制数据导入完成')

def load_substitute(book, conn):
    cursor = conn.cursor()
    
    sub_sheet = book.sheet_by_name('替代关系')
    for row_idx in range(3, sub_sheet.nrows):
        desc = sub_sheet.cell_value(row_idx, 0)
        seq = int(sub_sheet.cell_value(row_idx, 1)) if sub_sheet.cell_value(row_idx, 1) else 0
        sub_type = int(sub_sheet.cell_value(row_idx, 2)) if sub_sheet.cell_value(row_idx, 2) else 0
        material_type = sub_sheet.cell_value(row_idx, 3)
        code1 = sub_sheet.cell_value(row_idx, 4)
        quantity1 = sub_sheet.cell_value(row_idx, 5)
        code2 = sub_sheet.cell_value(row_idx, 6)
        quantity2 = sub_sheet.cell_value(row_idx, 7)
        ratio = sub_sheet.cell_value(row_idx, 8)
        batch = int(sub_sheet.cell_value(row_idx, 9)) if sub_sheet.cell_value(row_idx, 9) else 0
        
        limits = []
        for col_idx in range(10, min(38, sub_sheet.ncols)):
            limits.append(sub_sheet.cell_value(row_idx, col_idx))
        while len(limits) < 28:
            limits.append(0)
        
        cursor.execute('''
            INSERT INTO substitute (seq, sub_type, material_type, desc, code1, code2, quantity1, quantity2, ratio, batch,
                limit_q1, limit_q2, limit_q3, limit_q4, limit_q5, limit_q6,
                limit_q7, limit_q8, limit_q9, limit_q10, limit_q11, limit_q12,
                limit_q13, limit_q14, limit_q15, limit_q16, limit_q17, limit_q18,
                limit_q19, limit_q20, limit_q21, limit_q22, limit_q23, limit_q24,
                limit_q25, limit_q26, limit_q27, limit_q28)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (seq, sub_type, material_type, desc, code1, code2, quantity1, quantity2, ratio, batch) + tuple(limits[:28]))
    
    conn.commit()
    print('✅ 替代关系数据导入完成')

def load_wip(book, conn):
    cursor = conn.cursor()
    
    wip_sheet = book.sheet_by_name('在制品')
    for row_idx in range(2, wip_sheet.nrows):
        material_code = wip_sheet.cell_value(row_idx, 4)
        material_name = wip_sheet.cell_value(row_idx, 5)
        max_t = int(wip_sheet.cell_value(row_idx, 6)) if wip_sheet.cell_value(row_idx, 6) else 0
        stage = int(wip_sheet.cell_value(row_idx, 7)) if wip_sheet.cell_value(row_idx, 7) else 0
        quantity = wip_sheet.cell_value(row_idx, 8)
        
        cursor.execute('''
            INSERT INTO wip (material_code, material_name, max_t, stage, quantity)
            VALUES (?, ?, ?, ?, ?)
        ''', (material_code, material_name, max_t, stage, quantity))
    
    conn.commit()
    print('✅ 在制品数据导入完成')

def main(excel_path, db_path):
    print(f'=== 开始从Excel导入数据 ===')
    print(f'Excel文件: {excel_path}')
    print(f'数据库文件: {db_path}')
    
    if os.path.exists(db_path):
        print('⚠️  删除旧数据库文件...')
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    
    book = xlrd.open_workbook(excel_path)
    
    load_system_config(book, conn)
    load_materials(book, conn)
    load_routing(book, conn)
    load_equipment(book, conn)
    load_tooling(book, conn)
    load_orders(book, conn)
    load_bom(book, conn)
    load_outsource(book, conn)
    load_purchase_limit(book, conn)
    load_substitute(book, conn)
    load_wip(book, conn)
    
    conn.close()
    
    try:
        from .create_views import create_views
    except ImportError:
        from create_views import create_views
    create_views(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM routing')
    routing_count = cursor.fetchone()[0]
    cursor.execute('SELECT value FROM system_config WHERE key = "nrouting"')
    nrouting = cursor.fetchone()[0]
    
    print()
    print('=== 数据导入验证 ===')
    print(f'工艺路线记录数: {routing_count}')
    print(f'nrouting配置值: {nrouting}')
    print(f'数据一致性: {"✅ 匹配" if int(nrouting) == routing_count else "❌ 不匹配"}')
    
    conn.close()
    print()
    print('🎉 数据导入完成！')

if __name__ == '__main__':
    excel_path = '/Users/duxiangyun/PythonProjects/APS/Input/APS-JD.xls'
    db_path = '/Users/duxiangyun/PythonProjects/APS/Excel2DB/data/aps_model.db'
    main(excel_path, db_path)