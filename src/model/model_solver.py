from gurobipy import *
import time

def solve_model(msingle, intager, startime):
    if intager == 1:
        msingle.setParam(GRB.Param.MIPGap, 0.0001)

    msingle.optimize()

    startime1 = time.time()*1000
    runtime = (int(startime1) - int(startime))/1000
    print('\n求解完成:        ', runtime)

    return msingle
