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

book = xlrd.open_workbook('/Users/duxiangyun/PythonProjects/APS/Input/APS-JD.xls')

pro_mat = read_range(book, 'promat')
pro_mult = read_range(book, 'promult')
pro_equip = read_range(book, 'proequip')
pro_max_t = read_range(book, 'promaxt')
pro_hour = read_range(book, 'prohour')
nrouting = read_cell(book, 'nrouting')

print(f'nrouting配置值: {nrouting}')
print(f'promat行数: {len(pro_mat)}')
print(f'promult行数: {len(pro_mult)}')
print(f'proequip行数: {len(pro_equip)}')
print(f'promaxt行数: {len(pro_max_t)}')
print(f'prohour行数: {len(pro_hour)}')

print(f'\n后10行promat:')
for i, row in enumerate(pro_mat[-10:]):
    print(f'  [{len(pro_mat)-9+i}] {row}')

print(f'\n第134行所有字段:')
print(f'  pro_mat[133]: {pro_mat[133]}')
print(f'  pro_mult[133]: {pro_mult[133]}')
print(f'  pro_equip[133]: {pro_equip[133]}')
print(f'  pro_max_t[133]: {pro_max_t[133]}')
print(f'  pro_hour[133]: {pro_hour[133]}')