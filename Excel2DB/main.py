# Created on Mon Jan 13 16:01:34 2025
# @author: Boxiong Lan

###############################################################################
#####            单工厂生产计划模型（一）：  标准制造企业模型
###############################################################################

import time
import os
from xlwt import *
from gurobipy import *
from collections import namedtuple,defaultdict
from core.model_definition import define_model
from core.model_solver import solve_model
from core.result_output import output_results

DATA_SOURCE = 'DB'

startime = time.time()*1000

script_dir = os.path.dirname(os.path.abspath(__file__))
savepath = os.path.join(script_dir, 'Output') + '/'

if DATA_SOURCE == 'EXCEL':
    from core.processors.data_processor import load_and_preprocess
    filepath = os.path.join(script_dir, 'Input', 'APS-JD-test02.xls')
    resultFileName = 'APS-JD-test02-拆分了数据处理-result-' + time.strftime('%Y%m%d-%H%M%S') + '.xls'
    data = load_and_preprocess(filepath)
elif DATA_SOURCE == 'DB':
    from core.processors.db_processor import load_from_db
    db_path = os.path.join(script_dir, 'data', 'aps_model.db')
    resultFileName = 'APS-JD-DB-result-' + time.strftime('%Y%m%d-%H%M%S') + '.xls'
    data = load_from_db(db_path)

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n数据读入与处理时间:  ', runtime)

msingle, model_vars, model_constrs, intager = define_model(data)

msingle = solve_model(msingle, intager, startime)

output_results(model_vars, model_constrs, data, msingle, intager, startime, savepath, resultFileName)
