# Created on Mon Jan 13 16:01:34 2025
# @author: Boxiong Lan

###############################################################################
#####            单工厂生产计划模型（一）：  标准制造企业模型
###############################################################################

import time
from xlwt import *
from gurobipy import *
from collections import namedtuple,defaultdict
from data_processor import load_and_preprocess
from model_definition import define_model
from model_solver import solve_model
from result_output import output_results

startime = time.time()*1000

filepath = './Input/APS-JD.xls'
savepath = './Output/'
resultFileName = 'APS-JD-拆分了数据处理-result-' + time.strftime('%Y%m%d-%H%M%S') + '.xls'

data = load_and_preprocess(filepath)

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n数据读入与处理时间:  ', runtime)

msingle, model_vars, model_constrs, intager = define_model(data)

msingle = solve_model(msingle, intager, startime)

output_results(model_vars, model_constrs, data, msingle, intager, startime, savepath, resultFileName)
