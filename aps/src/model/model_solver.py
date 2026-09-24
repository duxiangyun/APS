import sqlite3
import os
import time

try:
    import highspy
    _HAS_HIGS = True
except Exception:
    _HAS_HIGS = False

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'data', 'db', 'aps_or.db')

def _select_solver():
    conn = sqlite3.connect(_DB_PATH)
    try:
        row = conn.execute(
            "SELECT param_value FROM core_biz_global_params WHERE param_key='SOLVE_SOLVER'"
        ).fetchone()
        return (row[0] or 'gurobi').strip().lower()
    finally:
        conn.close()

if _select_solver() == 'highs' and _HAS_HIGS:
    def solve_model(msingle, intager, startime):
        msingle.optimize()
        startime1 = time.time()*1000
        runtime = (int(startime1) - int(startime))/1000
        print('\n求解完成:        ', runtime)
        return msingle
else:
    from gurobipy import *
    def solve_model(msingle, intager, startime):
        if intager == 1:
            msingle.setParam('MIPGap', 0.0001)
        msingle.optimize()
        startime1 = time.time()*1000
        runtime = (int(startime1) - int(startime))/1000
        print('\n求解完成:        ', runtime)
        return msingle
