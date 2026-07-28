import sqlite3
import xlrd

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

def compare_data(excel_data, db_data, name):
    excel_rows = len(excel_data)
    db_rows = len(db_data)
    
    if excel_rows != db_rows:
        print(f'❌ {name}: 行数不一致 - Excel: {excel_rows}, DB: {db_rows}')
        return False
    
    all_match = True
    for i in range(excel_rows):
        excel_row = excel_data[i]
        db_row = list(db_data[i])
        
        for j in range(min(len(excel_row), len(db_row))):
            excel_val = excel_row[j]
            db_val = db_row[j]
            
            if isinstance(excel_val, float) and isinstance(db_val, (int, float)):
                if abs(excel_val - float(db_val)) > 0.0001:
                    print(f'❌ {name}[{i+1}][{j+1}]: 值不一致 - Excel: {excel_val}, DB: {db_val}')
                    all_match = False
            elif isinstance(excel_val, int) and isinstance(db_val, (int, float)):
                if excel_val != int(db_val):
                    print(f'❌ {name}[{i+1}][{j+1}]: 值不一致 - Excel: {excel_val}, DB: {db_val}')
                    all_match = False
            elif str(excel_val) != str(db_val):
                print(f'❌ {name}[{i+1}][{j+1}]: 值不一致 - Excel: {excel_val}, DB: {db_val}')
                all_match = False
    
    if all_match:
        print(f'✅ {name}: 数据完全一致 ({excel_rows}行)')
    return all_match

def main():
    print('=== 数据一致性验证 ===')
    print()
    
    excel_path = '/Users/duxiangyun/PythonProjects/APS/Input/APS-JD.xls'
    db_path = '/Users/duxiangyun/PythonProjects/APS/Excel2DB/aps_model.db'
    
    book = xlrd.open_workbook(excel_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    all_passed = True
    
    print('--- 系统配置验证 ---')
    config_items = ['nperiod', 'nproduct', 'nselfmade', 'nrawmat', 'nequip', 
                    'norder', 'nbom', 'nrouting', 'nfixture', 'nfixtable',
                    'nouttable', 'nrawlimtable', 'nsubtable', 'nwiptable']
    for item in config_items:
        excel_val = read_cell(book, item)
        cursor = conn.execute('SELECT value FROM system_config WHERE key = ?', (item,))
        row = cursor.fetchone()
        db_val = int(row['value']) if row else None
        
        if item == 'nrouting':
            excel_routing_count = len(read_range(book, 'promat'))
            if db_val == excel_routing_count:
                print(f'✅ {item}: DB={db_val} (实际数据行数)，Excel配置值={excel_val} (已修正)')
            else:
                print(f'❌ {item}: Excel={excel_val}, DB={db_val}, 实际数据行数={excel_routing_count}')
                all_passed = False
        elif excel_val != db_val:
            print(f'❌ {item}: Excel={excel_val}, DB={db_val}')
            all_passed = False
        else:
            print(f'✅ {item}: {excel_val}')
    
    print()
    print('--- 产品数据验证 ---')
    excel_prod = read_range(book, 'prodcode')
    db_prod = conn.execute('SELECT code FROM v_product').fetchall()
    all_passed = compare_data(excel_prod, db_prod, 'prodcode') and all_passed
    
    print()
    print('--- 自制件数据验证 ---')
    excel_semi = read_range(book, 'selfcode')
    db_semi = conn.execute('SELECT code FROM v_semi').fetchall()
    all_passed = compare_data(excel_semi, db_semi, 'selfcode') and all_passed
    
    print()
    print('--- 原材料数据验证 ---')
    excel_raw = read_range(book, 'rawcode')
    db_raw = conn.execute('SELECT code FROM v_raw').fetchall()
    all_passed = compare_data(excel_raw, db_raw, 'rawcode') and all_passed
    
    print()
    print('--- 设备数据验证 ---')
    excel_equip = read_range(book, 'equipid')
    db_equip = conn.execute('SELECT code FROM v_equipment').fetchall()
    all_passed = compare_data(excel_equip, db_equip, 'equipid') and all_passed
    
    print()
    print('--- 订单数据验证 ---')
    excel_order = read_range(book, 'ordno')
    db_order = conn.execute('SELECT no FROM v_orders').fetchall()
    all_passed = compare_data(excel_order, db_order, 'ordno') and all_passed
    
    print()
    print('--- BOM数据验证 ---')
    excel_fcode = read_range(book, 'fcode')
    db_fcode = conn.execute('SELECT parent_code FROM v_bom').fetchall()
    all_passed = compare_data(excel_fcode, db_fcode, 'fcode') and all_passed
    
    excel_scode = read_range(book, 'scode')
    db_scode = conn.execute('SELECT child_code FROM v_bom').fetchall()
    all_passed = compare_data(excel_scode, db_scode, 'scode') and all_passed
    
    print()
    print('--- 工艺路线数据验证 ---')
    excel_promat = read_range(book, 'promat')
    db_promat = conn.execute('SELECT material_code FROM v_routing_excel').fetchall()
    all_passed = compare_data(excel_promat, db_promat, 'promat') and all_passed
    
    excel_promult = read_range(book, 'promult')
    db_promult = conn.execute('SELECT process_alt FROM v_routing_excel').fetchall()
    all_passed = compare_data(excel_promult, db_promult, 'promult') and all_passed
    
    excel_proequip = read_range(book, 'proequip')
    db_proequip = conn.execute('SELECT equipment_code FROM v_routing_excel').fetchall()
    all_passed = compare_data(excel_proequip, db_proequip, 'proequip') and all_passed
    
    print()
    print('--- 外协数据验证 ---')
    if read_cell(book, 'nouttable') == 1:
        excel_outscode = read_range(book, 'outscode')
        db_outscode = conn.execute('SELECT code FROM v_outsource').fetchall()
        all_passed = compare_data(excel_outscode, db_outscode, 'outscode') and all_passed
    
    print()
    print('--- 采购限制数据验证 ---')
    if read_cell(book, 'nrawlimtable') == 1:
        excel_rlimid = read_range(book, 'rlimid')
        db_rlimid = conn.execute('SELECT material_code FROM v_purchase_limit').fetchall()
        all_passed = compare_data(excel_rlimid, db_rlimid, 'rlimid') and all_passed
    
    print()
    print('--- 替代关系数据验证 ---')
    if read_cell(book, 'nsubtable') == 1:
        excel_subtype = read_range(book, 'subtype')
        db_subtype = conn.execute('SELECT type FROM v_substitute').fetchall()
        all_passed = compare_data(excel_subtype, db_subtype, 'subtype') and all_passed
    
    print()
    print('--- 在制品数据验证 ---')
    if read_cell(book, 'nwiptable') == 1:
        excel_wipcode = read_range(book, 'wipcode')
        db_wipcode = conn.execute('SELECT material_code FROM v_wip').fetchall()
        all_passed = compare_data(excel_wipcode, db_wipcode, 'wipcode') and all_passed
    
    print()
    print('=======================')
    if all_passed:
        print('🎉 所有数据验证通过！数据库视图数据与Excel完全一致')
    else:
        print('❌ 部分数据验证失败，请检查上述错误信息')
    
    conn.close()

if __name__ == '__main__':
    main()