import xlrd
import sys
import os


def compare_excel(file1, file2, tolerance=1e-9):
    print(f"\n{'='*70}")
    print(f"对比文件1: {file1}")
    print(f"对比文件2: {file2}")
    print(f"浮点精度阈值: {tolerance}")
    print(f"{'='*70}")

    try:
        wb1 = xlrd.open_workbook(file1)
        wb2 = xlrd.open_workbook(file2)
    except Exception as e:
        print(f"打开文件失败: {e}")
        return

    sheets1 = wb1.sheet_names()
    sheets2 = wb2.sheet_names()

    all_sheets = sorted(set(sheets1 + sheets2))

    total_differences = 0
    total_precision_ignored = 0

    for sheet_name in all_sheets:
        print(f"\n--- 工作表: {sheet_name} ---")

        if sheet_name not in sheets1:
            print(f"  [警告] 文件1中不存在此工作表")
            continue
        if sheet_name not in sheets2:
            print(f"  [警告] 文件2中不存在此工作表")
            continue

        sheet1 = wb1.sheet_by_name(sheet_name)
        sheet2 = wb2.sheet_by_name(sheet_name)

        rows1 = sheet1.nrows
        rows2 = sheet2.nrows
        cols1 = sheet1.ncols
        cols2 = sheet2.ncols

        max_rows = max(rows1, rows2)
        max_cols = max(cols1, cols2)

        diff_count = 0
        precision_count = 0
        differences = []

        for r in range(max_rows):
            for c in range(max_cols):
                val1 = ""
                val2 = ""

                if r < rows1 and c < cols1:
                    val1 = sheet1.cell_value(r, c)
                    if isinstance(val1, float) and val1 == int(val1):
                        val1 = int(val1)

                if r < rows2 and c < cols2:
                    val2 = sheet2.cell_value(r, c)
                    if isinstance(val2, float) and val2 == int(val2):
                        val2 = int(val2)

                is_different = False

                if isinstance(val1, float) and isinstance(val2, float):
                    if abs(val1 - val2) > tolerance:
                        is_different = True
                    else:
                        precision_count += 1
                else:
                    if val1 != val2:
                        is_different = True

                if is_different:
                    diff_count += 1
                    if diff_count <= 20:
                        differences.append((r, c, val1, val2))

        if diff_count == 0:
            print(f"  [OK] 无差异")
            if precision_count > 0:
                print(f"       (忽略了 {precision_count} 处浮点精度差异)")
        else:
            print(f"  [差异] 发现 {diff_count} 处差异")
            if precision_count > 0:
                print(f"         (忽略了 {precision_count} 处浮点精度差异)")
            for r, c, v1, v2 in differences:
                print(f"    单元格 ({r+1}, {c+1}): 文件1={v1}, 文件2={v2}")
            if diff_count > 20:
                print(f"    ... 还有 {diff_count - 20} 处差异未显示")

        total_differences += diff_count
        total_precision_ignored += precision_count

    print(f"\n{'='*70}")
    print(f"对比结果汇总:")
    print(f"  总工作表数: {len(all_sheets)}")
    print(f"  总差异数: {total_differences}")
    print(f"  浮点精度忽略数: {total_precision_ignored}")
    print(f"{'='*70}")

    return total_differences


if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("用法: python excel_compare.py <文件1> <文件2> [精度阈值]")
        print("示例: python excel_compare.py ./Output/result1.xls ./Output/result2.xls")
        print("示例: python excel_compare.py ./Output/result1.xls ./Output/result2.xls 0.0001")
        sys.exit(1)

    file1 = sys.argv[1]
    file2 = sys.argv[2]
    tolerance = float(sys.argv[3]) if len(sys.argv) == 4 else 1e-9

    if not os.path.exists(file1):
        print(f"错误: 文件1不存在 - {file1}")
        sys.exit(1)

    if not os.path.exists(file2):
        print(f"错误: 文件2不存在 - {file2}")
        sys.exit(1)

    compare_excel(file1, file2, tolerance)
