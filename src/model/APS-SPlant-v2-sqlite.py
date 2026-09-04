# Created on Mon Jan 13 16:01:34 2025
# @author: Boxiong Lan

###############################################################################
#####            单工厂生产计划模型（一）：  标准制造企业模型
###############################################################################

# 模型基本设定：
#    1 考虑工厂的重要生产要素，包括物料清单（BOM）、工艺路线（Routing）、设备种类、工装种类，设备、工装能力等
#    2 需求订单：模型通过需求订单提供驱动模型优化的需求数据，需求订单规定产品种类、订单交期、交付数量、单价、订单等级等参数
#      可以为不同等级订单规定是否可以延期交付、最大允许延期天数，以及延期惩罚成本
#      目前模型暂时设定了三类订单，一类订单必须按期交付，二类订单允许延期若干周期交付，三类订单可以不交付（如预测需求的内部订单）
#    3 BOM表：模型通过BOM表建立工厂中产品、中间产品（自制品）、原材料之间的相互关系，并通过BOM关系建立物料平衡关系；  
#    4 替代BOM：模型允许存在产品的替代BOM，通过对BOM表的简单扩展实现替代BOM；
#    5 工艺路线：工艺路线规定了产品与中间产品加工过程中使用的设备与工序的种类与加工时间，以及是否使用工装教具等辅助工具
#    6 多工艺路线：模型允许在产品制造或中间产品制造过程中存在多工艺路线，并在工艺路线表中的多工艺列中标注工艺路线序号
#    7 工装：模型在工艺路线表上列入工装使用信息，建立工装与产品（自制品）生产、加工工艺之间的关系，并通过工装能力平衡约束，
#      合理安排工装使用；
#    8 提前期：模型考虑了产品、自制品的制造提前期，并规定：若提前期为 0，当期投料生产可以当期使用，制造可以在一个周期内完成，
#      若提前期为 1，则当期投料生产，下一期完成制造，制造过程需要跨一个周期，并在两个周期内完成，依次类推；
#    9 原材料采购：模型没有考虑原材料的采购提前期，计算得到的原材料需求是即时的，需要采购部门根据模型对原材料的需求考虑采购计划
#      原材料采购价格是固定的，可以按过去采购的平均价格、也可以按预测价格给出 
#   10 关键物料限制：模型允许给出关键原材料的供应数量限制 
#   11 外协采购：允许自制件外协采购，需在外协采购表中给定外协采购品种、价格与按时间分布的采购数量限制
#   12 外协工艺处理方法：外协工艺可以视同本厂工艺，用相同的方法定义外协工艺和外协工艺的加工成本，并在工艺路线表中的多工艺路线中将
#      含有外协工艺的工艺路线设为备选工艺方案，

####！！！！ 本程序是调试中的程序

## 注意的要点：
# 1、关于外协件的定义，外协件一定也是可以自行制造的自制件，模型可以选择是自制还是外协采购。如果不能自制，这样的所谓外协件应放入原材料 


import xlrd
import time
from xlwt import *
from gurobipy import *
from collections import namedtuple,defaultdict
import sqlite3    #支持从sqlite中读取数据
import os
from datetime import datetime  #求解结果写入DB时记录run_time

# =============================================================================
#  utility functions
# =============================================================================

# 读取Excel中单个cell数据的子程序
def readCell(cellName, book, toInt = False):
    cellName = cellName.lower()
    Name = book.name_map[cellName][0]
    val = Name.cell().value
    if toInt:
      val = int(val)
    result = val
    return(result)

# 从DB视图读取单个cell数据的子程序（视图名 alg_named_<cellName>）
def readCellDB(cellName, toInt=False):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM alg_named_{cellName}')
        row = cur.fetchone()
        val = row[0] if row else None
        if val is not None:
            # DB视图中参数值以文本存储，需做数值转换以匹配Excel数值单元格行为
            val = int(val) if toInt else float(val)
        return val
    finally:
        conn.close()

# 从DB视图读取数据表的子程序（视图名 alg_named_<tableName>）
def readTableDB(tableName, toInt=False, toFloat=False):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM alg_named_{tableName}')
        rows = cur.fetchall()
        ncol = len(cur.description)
        result = {}
        index = 1
        for r in rows:
            if ncol == 1:
                val = r[0]
                # DB中None对应Excel空单元格，转为空字符串''以保持行为一致
                if val is None:
                    val = ''
                else:
                    if toInt:
                        val = int(val)
                    elif toFloat:
                        val = float(val)
                result[index] = val
            else:
                vals = []
                for v in r:
                    if v is None or v == '':
                        continue
                    if toInt:
                        v = int(v)
                    elif toFloat:
                        v = float(v)
                    vals.append(v)
                result[index] = vals
            index = index + 1
        return result
    finally:
        conn.close()

# 读取Excel中数据表的子程序
def readTable(tableName, book, toInt = False):
    tableName = tableName.lower()
    Name = book.name_map[tableName][0]
    Sheet, rowxlo, rowxhi, colxlo, colxhi = Name.area2d()
    result = {}
    index = 1
    if colxhi == colxlo + 1:
        for i in range(rowxlo, rowxhi):
            val = Sheet.cell(i,colxlo).value
            if toInt:
                val = int(val)
            result[index] = val
            index = index + 1
    elif rowxhi == rowxlo + 1:
        for j in range(colxlo, colxhi):
            val = Sheet.cell(rowxlo,j).value
            if toInt:
                val = int(val)
            result[index] = val
            index = index + 1
    else:
        for i in range(rowxlo, rowxhi):
            result[index] = []
            for j in range(colxlo, colxhi):
                val = Sheet.cell(i,j).value
                if val !='':
                    if toInt:
                        val = int(val)
                    result[index].append(val)
            index = index + 1
    return(result)


# 从DB读取算法输入数据的配置
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(_PROJECT_DIR, 'data', 'db', 'aps_or.db')


## ===============================================================================================
##   从Excel表读入数据
## ===============================================================================================

startime = time.time()*1000

#打开Excel文件
# filepath = 'D:/My_Model/1-模型整理汇总/单一工厂制造模型/标准制造模型/APS-JD.xls'          # 读入数据文件
# savepath = 'D:/My_Model/1-模型整理汇总/单一工厂制造模型/标准制造模型/'                      # 输出数据文件路径
# resultFileName = 'APS-JD-result.xls'                                                    # 输出数据文件

filepath = os.path.join(_PROJECT_DIR, 'data', 'input', 'APS-JD.xls')
savepath = os.path.join(_PROJECT_DIR, 'data', 'output') + '/'
resultFileName = 'APS-JD-sqlite-mac-result-' + time.strftime('%Y%m%d-%H%M%S') + '.xls'


book = xlrd.open_workbook(filepath)

#  读综合表信息    
# nfixtable    = readCell('nfixtable', book, True)                          # 工装表是否存在标识
nfixtable    = readCellDB('nfixtable', True)                                # 工装表是否存在标识（从DB读取）                          # 工装表是否存在标识
# nouttable    = readCell('nouttable', book,True)                             # 外协表是否存在标识
nouttable    = readCellDB('nouttable', True)                            # 外协表是否存在标识（从DB读取）
# nrawlimtable = readCell('nrawlimtable', book, True)                         # 采购限制表是否存在标识
nrawlimtable = readCellDB('nrawlimtable', True)                        # 采购限制表是否存在标识（从DB读取）
# nsubtable    = readCell('nsubtable', book, True)                            # 替代关系表是否存在标识
nsubtable    = readCellDB('nsubtable', True)                           # 替代关系表是否存在标识（从DB读取）
# nwiptable    = readCell('nwiptable', book, True)                            # 自制品表是否存在标识
nwiptable    = readCellDB('nwiptable', True)                           # 自制品表是否存在标识（从DB读取）

# nperiod   = readCell('nperiod', book, True)                              # 计划期长度（周期数）
nperiod   = readCellDB('nperiod', True)                              # 计划期长度（周期数）（从DB读取）
# nbom0     = readCell('nbom', book, True)                                 # BOM表记录数
nbom0     = readCellDB('nbom', True)                                 # BOM表记录数（从DB读取）
# nrouting  = readCell('nrouting', book, True)                             # 工艺路线表记录数
nrouting  = readCellDB('nrouting', True)                             # 工艺路线表记录数（从DB读取）
# nequip    = readCell('nequip', book, True)                               # 设备种类数
nequip    = readCellDB('nequip', True)                               # 设备种类数（从DB读取）
# nproduct  = readCell('nproduct', book, True)                             # 产品种类数
nproduct  = readCellDB('nproduct', True)                             # 产品种类数（从DB读取）
# nselfmade = readCell('nselfmade', book, True)                            # 自制件种类数
nselfmade = readCellDB('nselfmade', True)                            # 自制件种类数（从DB读取）
# nrawmat   = readCell('nrawmat', book, True)                              # 原材料种类数
nrawmat   = readCellDB('nrawmat', True)                              # 原材料种类数（从DB读取）
# dutytime  = readCell('dutytime', book, True)                             # 每班次时长
dutytime  = readCellDB('dutytime', True)                             # 每班次时长（从DB读取）
# dayshift  = readCell('dayshift', book, True)                             # 每周期班次数
dayshift  = readCellDB('dayshift', True)                             # 每周期班次数（从DB读取）
# npmaxt    = readCell('npmaxt', book, True)                               # 最大加工跨周期数
npmaxt    = readCellDB('npmaxt', True)                               # 最大加工跨周期数（从DB读取）
# norder    = readCell('norder', book, True)                               # 订单数
norder    = readCellDB('norder', True)                               # 订单数（从DB读取）
# nordelay  = readCell('nordelay', book, True)                             # 订单最大允许延期周期数
nordelay  = readCellDB('nordelay', True)                             # 订单最大允许延期周期数（从DB读取）
# nordclass = readCell('nordclass', book, True)                            # 订单等级数
nordclass = readCellDB('nordclass', True)                            # 订单等级数（从DB读取）
# nfixture  = readCell('nfixture', book, True)                             # 工装种类数（设备 1 的辅助装备）
nfixture  = readCellDB('nfixture', True)                             # 工装种类数（从DB读取）
#nsubsti   = readCell('nsubsti', book, True)                              # 物料替代数
#nwip      = readCell('nwip', book, True)                                 # 自制品数
# ndemrate  = readCell('ndemrate', book)                                   # 需求率
ndemrate  = readCellDB('ndemrate', False)                             # 需求率（从DB读取，转为float）
intager = 0                                                                # 整数规划表示：0 - 线性规划，1-整数规划


# 设置索引列表
T        = list(range(1, nperiod + 1))
T0       = list(range(0, nperiod + 1))
BOM0     = list(range(1, nbom0 + 1))
Routing  = list(range(1, nrouting + 1))
Product  = list(range(1, nproduct + 1))
Self     = list(range(1, nselfmade + 1))
Raw      = list(range(1, nrawmat + 1))
Equip    = list(range(1, nequip + 1))
Order    = list(range(1, norder + 1))
Fixture  = list(range(1, nfixture + 1))

## 读BOM表信息 ##############################################
# Fcode0  = readTable('Fcode', book)                                       # 父物料代码
Fcode0  = readTableDB('Fcode')                                          # 父物料代码（从DB读取）
# Scode0  = readTable('Scode', book)                                       # 子物料代码
Scode0  = readTableDB('Scode')                                          # 子物料代码（从DB读取）
# Quant0  = readTable('Quant', book)                                       # 父物料消耗子物料的数量关系
Quant0  = readTableDB('Quant', toFloat=True)                           # 父物料消耗子物料的数量关系（从DB读取，转为float）
# Blevel0 = readTable('BomLevel', book, True)                              # BOM层级
Blevel0 = readTableDB('BomLevel', toInt=True)                          # BOM层级（从DB读取）

## 读产品表  ################################################
# ProdCode = readTable('ProdCode',book)                                   # 产品代码
ProdCode = readTableDB('ProdCode')                                  # 产品代码（从DB读取）
# ProdCost = readTable('ProdCost',book)                                   # 产品生产成本
ProdCost = readTableDB('ProdCost', toFloat=True)                   # 产品生产成本（从DB读取，转为float）
# Price    = readTable('Price',book)                                      # 产品销售价格
Price    = readTableDB('Price', toFloat=True)                      # 产品销售价格（从DB读取，转为float）
# ProdLT   = readTable('ProdLeadtime',book, True)                         # 产品生产提前期
ProdLT   = readTableDB('ProdLeadtime', toInt=True)                 # 产品生产提前期（从DB读取）
# ProdInv0 = readTable('ProdInv0',book)                                   # 产品期初库存
ProdInv0 = readTableDB('ProdInv0', toFloat=True)                   # 产品期初库存（从DB读取，转为float）
# ProdInvT = readTable('ProdInvT',book)                                   # 产品期末库存
ProdInvT = readTableDB('ProdInvT', toFloat=True)                   # 产品期末库存（从DB读取，转为float）
# ProdInvL = readTable('ProdInvL',book)                                   # 产品最低库存
ProdInvL = readTableDB('ProdInvL', toFloat=True)                   # 产品最低库存（从DB读取，转为float）
# ProdInvU = readTable('ProdInvU',book)                                   # 产品最高库存
ProdInvU = readTableDB('ProdInvU', toFloat=True)                   # 产品最高库存（从DB读取，转为float）
# ProdInvCost = readTable('ProdInvCost',book)                             # 产品库存成本
ProdInvCost = readTableDB('ProdInvCost', toFloat=True)             # 产品库存成本（从DB读取，转为float）

## 读自制件表  ###############################################
# SelfCode = readTable('SelfCode',book)
SelfCode = readTableDB('SelfCode')                                 # 自制件代码（从DB读取）
# SelfDummy= readTable('SelfDummy',book)
SelfDummy= readTableDB('SelfDummy', toFloat=True)                  # 自制件虚拟标识（从DB读取，转为float）
# SelfInv0 = readTable('SelfInv0',book)
SelfInv0 = readTableDB('SelfInv0', toFloat=True)                   # 自制件期初库存（从DB读取，转为float）
# SelfInvT = readTable('SelfInvT',book)
SelfInvT = readTableDB('SelfInvT', toFloat=True)                   # 自制件期末库存（从DB读取，转为float）
# SelfInvL = readTable('SelfInvL',book)
SelfInvL = readTableDB('SelfInvL', toFloat=True)                   # 自制件最低库存（从DB读取，转为float）
# SelfInvU = readTable('SelfInvU',book)
SelfInvU = readTableDB('SelfInvU', toFloat=True)                   # 自制件最高库存（从DB读取，转为float）
# SelfInvCost = readTable('SelfInvCost',book)
SelfInvCost = readTableDB('SelfInvCost', toFloat=True)             # 自制件库存成本（从DB读取，转为float）
# SelfLT   = readTable('SelfLeadtime',book, True)
SelfLT   = readTableDB('SelfLeadtime', toInt=True)                 # 自制件生产提前期（从DB读取）

## 读工艺路线表  #############################################
# ProMat   = readTable('ProMat', book)                                    # 工艺中被加工物料代码
ProMat   = readTableDB('ProMat')                                    # 工艺中被加工物料代码（从DB读取）
# ProMult  = readTable('ProMult', book, True)                             # 多工艺路线标示序数
ProMult  = readTableDB('ProMult', toInt=True)                       # 多工艺路线标示序数（从DB读取）
# ProEquip = readTable('ProEquip', book)                                  # 工艺加工设备
ProEquip = readTableDB('ProEquip')                                  # 工艺加工设备（从DB读取）
# ProState = readTable('ProState', book)                                  # 工艺加工工序
ProState = readTableDB('ProState')                                  # 工艺加工工序（从DB读取）
ProOper  = readTableDB('ProOper')                                   # 工艺工序代码（OP-精铣/OP-粗镗…，从DB读取）
if nfixtable == 1:
    # ProFixt  = readTable('ProFixt', book)                                   # 工艺加工辅助工装代码
    ProFixt  = readTableDB('ProFixt')                                   # 工艺加工辅助工装代码（从DB读取）
    # ProFixq  = readTable('ProFixq', book)                                   # 工艺加工工装使用数量
    ProFixq  = readTableDB('ProFixq', toFloat=True)                     # 工艺加工工装使用数量（从DB读取，转为float）
# ProMaxT  = readTable('ProMaxT', book, True)                             # 工艺加工跨周期数
ProMaxT  = readTableDB('ProMaxT', toInt=True)                       # 工艺加工跨周期数（从DB读取）
# ProHour  = readTable('ProHour', book)                                   # 工艺加工时间
ProHour  = readTableDB('ProHour', toFloat=True)                     # 工艺加工时间（从DB读取，多列转为float）
Protime = {}
for p in Routing:
    if npmaxt > 1:                                                      ## ！！！！！！ 这里修改过
        for t in range(1,npmaxt+1):
            Protime[p,t] = ProHour[p][t-1]
    else:
        Protime[p,1] = ProHour[p]

## 读设备表  ################################################
# EquipId    = readTable('EquipId', book)                                 # 设备代码
EquipId    = readTableDB('EquipId')                                 # 设备代码（从DB读取）
# EquipCost  = readTable('EquipCost', book)                               # 设备单位时间加工成本
EquipCost  = readTableDB('EquipCost', toFloat=True)                 # 设备单位时间加工成本（从DB读取，转为float）
# EquipNumb  = readTable('EquipNumb', book, True)                         # 设备台数
EquipNumb  = readTableDB('EquipNumb', toInt=True)                   # 设备台数（从DB读取）
# EquipRate  = readTable('EquipRate', book)                               # 设备平均有效时间利用率
EquipRate  = readTableDB('EquipRate', toFloat=True)                 # 设备平均有效时间利用率（从DB读取，转为float）
# EquipOverT = readTable('EquipOverT', book)                              # 设备允许加班时间与正常工作时间比值
EquipOverT = readTableDB('EquipOverT', toFloat=True)                # 设备允许加班时间与正常工作时间比值（从DB读取，转为float）
# EquipOverR = readTable('EquipOverR', book)                              # 设备加班成本与正常单位时间成本比值
EquipOverR = readTableDB('EquipOverR', toFloat=True)                # 设备加班成本与正常单位时间成本比值（从DB读取，转为float）

## 读工装表  ################################################
if nfixtable == 1:
    # FixtNo   = readTable('FixtNo',book, True)
    FixtNo   = readTableDB('FixtNo', toInt=True)               # 工装序号（从DB读取）
    # FixtId   = readTable('FixtId',book)
    FixtId   = readTableDB('FixtId')                           # 工装代码（从DB读取）
    # FixtCost = readTable('FixtCost',book)
    FixtCost = readTableDB('FixtCost', toFloat=True)           # 工装加工成本（从DB读取，转为float）
    # FixtQunt = readTable('FixtQunt',book)
    FixtQunt = readTableDB('FixtQunt', toFloat=True)           # 工装数量（从DB读取，转为float）
    # FixtRate = readTable('FixtRate',book)
    FixtRate = readTableDB('FixtRate', toFloat=True)           # 工装时间利用率（从DB读取，转为float）
    # FixtOver = readTable('FixtOver',book)
    FixtOver = readTableDB('FixtOver', toFloat=True)           # 工装加班时间比值（从DB读取，转为float）
    # Fovcost  = readTable('Fovcost',book)
    Fovcost  = readTableDB('Fovcost', toFloat=True)            # 工装加班成本比值（从DB读取，转为float）
else:
    FixNo = {}

## 读订单表  ################################################
# OrdNo    = readTable('OrdNo', book, True)                               # 订单号
OrdNo    = readTableDB('OrdNo', toInt=True)                         # 订单号（从DB读取）
# OrdCls   = readTable('OrdCls', book)                                    # 订单等级
OrdCls   = readTableDB('OrdCls', toFloat=True)                      # 订单等级（从DB读取，转为float）
# OrdProd  = readTable('OrdProd', book)                                   # 订单产品
OrdProd  = readTableDB('OrdProd')                                   # 订单产品（从DB读取）
# OrdPrice = readTable('OrdPrice', book)                                  # 订单销售价格
OrdPrice = readTableDB('OrdPrice', toFloat=True)                    # 订单销售价格（从DB读取，转为float）
# OrdQunt  = readTable('OrdQunt', book)                                   # 订单数量
OrdQunt  = readTableDB('OrdQunt', toFloat=True)                     # 订单数量（从DB读取，转为float）
# OrdTime  = readTable('OrdTime', book, True)                             # 订单交期
OrdTime  = readTableDB('OrdTime', toInt=True)                       # 订单交期（从DB读取）
# OrdDly   = readTable('OrdDly', book, True)                              # 订单允许延期交付的延期周期数
OrdDly   = readTableDB('OrdDly', toInt=True)                        # 订单允许延期交付的延期周期数（从DB读取）
# OrdFine  = readTable('OrdFine', book)                                   # 订单延期交付每延期一周期需交付的罚金数
OrdFine  = readTableDB('OrdFine', toFloat=True)                     # 订单延期交付每延期一周期需交付的罚金数（从DB读取，转为float）

## 读外协表  ################################################
if nouttable == 1:
    # OutsNo   = readTable('OutsNo',book, True)
    OutsNo   = readTableDB('OutsNo', toInt=True)                # 外协序号（从DB读取）
    # OutsCode = readTable('OutsCode',book)
    OutsCode = readTableDB('OutsCode')                          # 外协物料代码（从DB读取）
    # OutsCost = readTable('OutsCost',book)
    OutsCost = readTableDB('OutsCost', toFloat=True)            # 外协加工成本（从DB读取，转为float）
    # OutsQunt = readTable('OutsQunt',book)
    OutsQunt = readTableDB('OutsQunt', toFloat=True)            # 外协周期用量（从DB读取，多列转为float）
    OutSQ = {}
    for i in OutsNo:
        for t in T:
            OutSQ[(i,t)] = OutsQunt[i][t-1]
else:
    OutsNo = {}

## 读原料表  ###############################################
# RawCode = readTable('RawCode',book)
RawCode = readTableDB('RawCode')                                   # 原料代码（从DB读取）
# RawCost = readTable('RawCost',book)
RawCost = readTableDB('RawCost', toFloat=True)                     # 原料采购价格（从DB读取，转为float）
# RawInv0 = readTable('RawInv0',book)
RawInv0 = readTableDB('RawInv0', toFloat=True)                     # 原料期初库存（从DB读取，转为float）
# RawInvT = readTable('RawInvT',book)
RawInvT = readTableDB('RawInvT', toFloat=True)                     # 原料期末库存（从DB读取，转为float）
# RawInvL = readTable('RawInvL',book)
RawInvL = readTableDB('RawInvL', toFloat=True)                     # 原料最低库存（从DB读取，转为float）
# RawInvU = readTable('RawInvU',book)
RawInvU = readTableDB('RawInvU', toFloat=True)                     # 原料最高库存（从DB读取，转为float）
# RawInvCost = readTable('RawInvCost',book)
RawInvCost = readTableDB('RawInvCost', toFloat=True)               # 原料库存成本（从DB读取，转为float）
# RawLT   = readTable('RawLeadtime',book)
RawLT   = readTableDB('RawLeadtime', toFloat=True)                 # 原料采购提前期（从DB读取，转为float）

## 读采购限制表  ###########################################
if nrawlimtable == 1:
    # RlimNo  = readTable('RlimNo',book, True)
    RlimNo  = readTableDB('RlimNo', toInt=True)               # 采购限制序号（从DB读取）
    # RlimId  = readTable('RlimId',book)
    RlimId  = readTableDB('RlimId')                           # 采购限制物料代码（从DB读取）
    # RlimQnt = readTable('RlimQunt',book)
    RlimQnt = readTableDB('RlimQunt', toFloat=True)           # 采购周期限制量（从DB读取，多列转为float）
    RawlimQ = {}
    for i in RlimNo:
        for t in T:
            RawlimQ[(i,t)] = RlimQnt[i][t-1]
else:
    RlimNo = {}

## 读替代关系表  ###########################################
#SubtsiNo = {}
if nsubtable == 1:
    # SubstiNo   = readTable('SubstiNo',book)
    SubstiNo   = readTableDB('SubstiNo', toFloat=True)           # 替代关系序号（从DB读取，转为float）
    # SubType    = readTable('SubType',book)
    SubType    = readTableDB('SubType', toFloat=True)            # 替代类型（从DB读取，转为float）
    # SubCode1   = readTable('SubCode1',book)
    SubCode1   = readTableDB('SubCode1')                          # 被替代物料代码（从DB读取）
    # SubCode2   = readTable('SubCode2',book)
    SubCode2   = readTableDB('SubCode2')                          # 替代物料代码（从DB读取）
    # SubQunt1   = readTable('SubQunt1',book)
    SubQunt1   = readTableDB('SubQunt1', toFloat=True)            # 被替代物料数量（从DB读取，转为float）
    # SubQunt2   = readTable('SubQunt2',book)
    SubQunt2   = readTableDB('SubQunt2', toFloat=True)            # 替代物料数量（从DB读取，转为float）
    # Sublimit   = readTable('Sublimit',book)
    Sublimit   = readTableDB('Sublimit', toFloat=True)            # 替代周期限额（从DB读取，多列转为float）
    # SubRatio   = readTable('SubRatio',book)
    SubRatio   = readTableDB('SubRatio', toFloat=True)            # 替代比例（从DB读取，转为float）
    # SubBatch   = readTable('SubBatch',book)
    SubBatch   = readTableDB('SubBatch', toFloat=True)            # 替代批量（从DB读取，转为float）
    SubLimit = {}
    if len(SubstiNo) != 1:
        for i in SubstiNo:
            for t in T:
                SubLimit[i,t] = Sublimit[i][t-1]
    else:
        for t in T:
            SubLimit[1,t] = Sublimit[t]
else:
    SubstiNo = {}

## 读在制品表  ###########################################
    # 计算在制品需要扣除的设备占用能力：
    # 在制品数量不是变量，是常量，但需要进行后续加工，因此其消耗的设备资源需要在模型中的设备能力平衡约束中扣除
WipLoad = {}                                                            # 在制品占用的设备能力
for i in Equip:                                                         # 为该参数初始化（全赋值为0），时间维度不超过所有在制品的最大加工周期（参数npmaxt给定）
    for t in range(1,npmaxt+1):
        WipLoad[i,t] = 0
if nwiptable == 1:
   # 读在制品表
    # WipNo    = readTable('WipNo',book, True)
    WipNo    = readTableDB('WipNo', toInt=True)                  # 在制品序号（从DB读取）
    # WipCode    = readTable('WipCode',book)
    WipCode    = readTableDB('WipCode')                           # 在制品代码（从DB读取）
    # WipMaxT    = readTable('WipMaxT',book, True)
    WipMaxT    = readTableDB('WipMaxT', toInt=True)               # 在制品最大加工周期（从DB读取）
    # WipStage   = readTable('WipStage',book, True)
    WipStage   = readTableDB('WipStage', toInt=True)              # 在制品已完成工序（从DB读取）
    # WipQunt    = readTable('WipQunt',book)
    WipQunt    = readTableDB('WipQunt', toFloat=True)             # 在制品数量（从DB读取，转为float）
    for i in WipNo:                                                         # 遍历在制品表
        for j in Routing:                                                       # 遍历工艺路线
            if WipCode[i] == ProMat[j]:                                             # 找到在制品在工艺路线中的加工位置
                for q in Equip:                                                         # 遍历设备
                    if ProEquip[j] == EquipId[q]:                                           # 找到加工的设备
                        for t in range(1, ProMaxT[j]-WipStage[i]+1):                            # 遍历在制品后续未完成的加工期
                            WipLoad[q,t] += WipQunt[i]*Protime[j,WipStage[i]+t]                     # 累加需要的设备负荷 
else:
    WipNo = {}

###############################################################################
##       读入数据校核检验
###############################################################################


## 检验 BOM表 规范  ############################################################

## BOM 表中不能出现相同（冗余）的父-子物料关系记录项，若出现需删除
Fcode = {}
Scode = {}
Quant = {}
Blevel = {}
BomF = {}
BomS = {}
BomFcode = []
BomScode = []
Bomfidx = {}
j = 0
ii = 0
for i in BOM0:
    if Scode0[i] not in BomScode:
        BomScode.append(Scode0[i])
    if Fcode0[i] not in BomFcode:
        BomFcode.append(Fcode0[i])
        j += 1                                                  # 父物料数
        ii += 1                                                 # 有效 BOM 记录数
        Bomfidx[Fcode0[i]] = j                                  # 父物料索引数
        BomS[j] = []
        BomF[j] = Fcode0[i]
        BomS[j].append(Scode0[i])
        Fcode[ii] = Fcode0[i]
        Scode[ii] = Scode0[i]
        Quant[ii] = Quant0[i]
        Blevel[ii] = Blevel0[i]
    else:                                                       # 是已经存在的父物料
        jj = Bomfidx[Fcode0[i]]                                     # 查找BOM索引
        if Scode0[i] not in BomS[jj]:                                # 是新的子物料
            ii += 1
            BomS[j].append(Scode0[i])
            Fcode[ii] = Fcode0[i]
            Scode[ii] = Scode0[i]
            Quant[ii] = Quant0[i]
            Blevel[ii] = Blevel0[i]
        else:
            print(' 警告：BOM表有冗余记录：', i,' ,',Scode0[i])
nbom = ii
BOMs     = list(range(1, nbom + 1))

       
for j in Product:
    if ProdCode[j] not in BomFcode:
        print(' 警告: 产品表中的产品代码 ', j, ' ', ProdCode[j], '不在 BOM 表的父物料中')
        
for j in Self:
    if SelfCode[j] not in BomFcode:
        print(' 警告: 自制件表中的自制件代码 ', j, ' ', SelfCode[j], '不在 BOM 表的父物料中')
    if SelfCode[j] not in BomScode:
        print(' 警告: 自制件表中的自制件代码 ', j, ' ', SelfCode[j], '不在 BOM 表的子物料中')

for j in Raw:
    if RawCode[j] not in BomScode:
        print(' 警告: 原材料表中的原材料代码 ', j, ' ', RawCode[j], '不在 BOM 表的子物料中')
        
        

## 建立产品/自制品/原材料代码集合和索引关系
Prodset = set()
Prodidx = {}
for i in Product:
    Prodset.add(ProdCode[i])
    Prodidx[ProdCode[i]] = i

Selfset = set()
Selfidx = {}
for i in Self:
    Selfset.add(SelfCode[i])
    Selfidx[SelfCode[i]] = i

Rawset = set()
Rawidx = {}
for i in Raw:
    Rawset.add(RawCode[i])
    Rawidx[RawCode[i]] = i
    
# 工艺设备索引关系，主键是设备代码，值是设备代码在列表中的位置
Equipidx = {}                         
for i in Equip:
    Equipidx[EquipId[i]] = i


# 工装索引关系，主键是工装代码，值是工装代码在列表中的位置
if nfixtable == 1:
    Fixtidx = {}                        
    for i in Fixture:                                               # 遍历工装列表
        Fixtidx[FixtId[i]] = i                                          # 建立模具索引


##    确定工艺路线中产品与自制品的多工艺属性
###############################################################################

nppro = {}                                                          # 存储生产各种产品的多工艺数组
nspro = {}                                                          # 存储生产各种自制品的多工艺数组
RoutingMat = []                                                     # 归集出现在工艺路线表中的物料
for i in Product: nppro[i] = 1                                      # 多工艺初值都设为 1
for i in Self: nspro[i] = 1
for i in Routing:
    if ProMat[i] not in RoutingMat:
        RoutingMat.append(ProMat[i])
    if ProMult[i] != 1:
        if ProMat [i] in Prodset:
            nppro[Prodidx[ProMat[i]]] = ProMult[i]
        elif ProMat [i] in Selfset:
            nspro[Selfidx[ProMat[i]]] = ProMult[i]
        else:
            print(' 警告: 工艺路线表中的物料 ', ProMat[i], '不在产品与自制件中')
            
            
##    检查生产的产品与自制件是否有对应的工艺路线数据
###############################################################################
            
for j in Product:
    if ProdCode[j] not in RoutingMat:
        print(' 警告:产品表中的产品 ', j, ' ', ProdCode[j], '不在工艺路线表中')
for j in Self:
    if SelfCode[j] not in RoutingMat:
        if SelfDummy[j] != 1:                                                               # 该自制件不是虚拟件
            print(' 警告: 自制件表中的自制件 ', j, ' ', SelfCode[j], '不在工艺路线表中')


########################################################################################
##                       建立BOM表的索引关系
########################################################################################

## 说明：建立索引关系可以大大减少模型生成时的运算工作量，显著减少模型生成时间，尤其在处理大规模
##       模型时效果更为显著。例如在生成物料平衡约束时，生成每一种物料的平衡约束都要遍历整个BOM
##       表，而建立索引关系后便可精准找到与该物料相关的BOM数据，减少遍历整个BOM表的工作量。       

## 建立自制件(s)与最终产品(s-p)和高一层级自制件(s-s)的索引关系  ############################
             
FbP = {}                                        # FbP存储消耗子物料自制品的产品（父物料）的序号与消耗数量集合
FbS = {}                                        # FbS存储消耗子物料自制品的自制品（父物料）的序号与消耗数量集合
RbP = {}                                        # RbP存储消耗原材料的产品（父物料）的序号与消耗数量集合
RbS = {}                                        # RbS存储消耗原材料的自制品（父物料）的序号与消耗数量集合
for j in Self:                                  # 初始化自制件索引数组
    FbP[j]  = []
    FbS[j]  = []
for j in Raw:                                   # 初始化原材料索引数组
    RbP[j] = []
    RbS[j] = []

for i in BOMs:                                  # 遍历BOM表

    ## 建立自制件(s)与最终产品(s-p)和自制件(s-s)的索引关系
    if Scode[i] in Selfset:                         # 若子物料为自制件
        j = Selfidx[Scode[i]]                           # 取子物料代码（自制品代码）
        if Fcode[i] in Prodset:                         # 若父物料是最终产品
            k = Prodidx[Fcode[i]]                           # 或取父物料（产品变量）序号
            q = Quant[i]                                    # 获取子物料消耗数量
            FbP[j].append((k,q))                            # 存储上面两个参数
        elif Fcode[i] in Selfset:                       # 若父物料为自制件
            k = Selfidx[Fcode[i]]                           # 或取父物料（自制品变量）序号
            q = Quant[i]                                    # 获取子物料消耗数量
            FbS[j].append((k,q))                            # 存储上面两个参数
        else:            
            print('警告：BOM表中的父物料 ', Fcode[i],' 不在产品与自制件与中')

    ## 建立原材料(r)与最终产品(r-p)和自制件(r-s)的索引关系              
    elif Scode[i] in Rawset:                          # 若子物料是原材料
        j = Rawidx[Scode[i]]                            # 取子物料代码（原材料代码）
        if Fcode[i] in Prodset:                         # 若父物料是最终产品
            k = Prodidx[Fcode[i]]                           # 或取父物料（产品变量）序号
            q = Quant[i]                                    # 获取子物料消耗数量
            RbP[j].append((k,q)) 
        elif Fcode[i] in Selfset:                       # 父物料是自制品
            k = Selfidx[Fcode[i]]                           # 或取父物料（自制品变量）序号
            q = Quant[i]                                    # 获取子物料消耗数量
            RbS[j].append((k,q))
        else:            
            print('警告：BOM表中的父物料 ', Fcode[i],' 不在产品与自制件与中')
    else:
        print('警告：BOM表中的子物料 ', Scode[i],' 不在自制件与原材料中')


## 建立工艺路线表中加工设备（Equip）、工序（Process）、工装（Fixture）与产品(p)、自制品(s)的索引关系  #################

PeP = {}                                                    # PeP记录工艺生产的产品序号与在工艺路线表上的位置两个参数的集合
PeS = {}                                                    # PeS记录工艺生产的自制品序号与在工艺路线表上的位置两个参数的集合
for i in Equip:                                             # 设备索引数组初始化
    PeP[i] = []
    PeS[i] = []

if nfixtable == 1:
    MdP  = {}                                                   # MdP 归集每种工装（md表示Fixt）需要加工的产品（第二个p表示product）集合
    MdS  = {}                                                   # MdS 归集每种工装（md表示Fixt）需要加工的自制品（第二个s表示selfmade）集合
    for i in Fixture:                                           # 工装索引数组初始化
        MdP[i] = []
        MdS[i] = []
    
for j in Routing:                                           # 遍历工艺路线表
    i = Equipidx[ProEquip[j]]                                   # 提取工艺设备序号
    i1 = 0
    if nfixtable == 1:
        if ProFixt[j] != '':
            i1 = Fixtidx[ProFixt[j]]                                    # 提取工装序号
    
    if ProMat [j] in Prodset:                                   # 加工的最终产品
        k = Prodidx[ProMat [j]]                                     # 获取产品的（变量）序号
        PeP[i].append((k,j))                                        # 在PeP记录序号 k 与在工艺路线表的位置 j 
        if i1 != 0 and nfixtable == 1:
            MdP[i1].append((k,j))                          # 记录产品代码序号（位置）在工装使用表中的位置
    elif ProMat [j] in Selfset:                                 # 加工的是自制件
        k = Selfidx[ProMat [j]]                                     # 获取自制品的（变量）序号
        PeS[i].append((k,j))                                        # 在PeS记录序号 k 与在工艺路线表的位置 j 
        if i1 != 0 and nfixtable == 1: 
            MdS[i1].append((k,j))                          # 记录产品代码序号（位置）在工装使用表中的位置
#    else:
#        print('警告：工艺表中的物料 ', ProMat [j],' 不在物料列表中')


## 检查自制件与产品是否在工艺路线表中

for i in Product:
    ifind = 0
    for j in Routing:
        if ProdCode[i] == ProMat[j]:
            ifind = 1
            break
    if ifind == 0:
        print('警告：产品表中的物料 ', ProdCode[i],' 不在工艺路线表中')
        
for i in Self:
    ifind = 0
    for j in Routing:
        if SelfCode[i] == ProMat[j] or SelfDummy[i] == 1:                   # 在工艺路线表中找到该物料，或该物料是虚拟物料
            ifind = 1
            break
    if ifind == 0:
        print('警告：自制件表中的物料 ', SelfCode[i],' 不在工艺路线表中')
 

        
## 计算工艺能力：每班时长*每周期班次*设备台数*时间利用率
EquipCap = {}                                                     
for p in Equip:
    EquipCap[p] = dutytime*dayshift*EquipRate[p]*EquipNumb[p]

# 计算工装能力
if nfixtable == 1:
    FixtCap = {}
    for p in Fixture:
        FixtCap[p] = dutytime*dayshift*FixtRate[p]*FixtQunt[p]

penalty = 1e6

# 读取数据处理结束的时间
startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n数据读入与处理时间:  ', runtime)

## =============================================================================
##  定义模型 Optimization Model
## =============================================================================

msingle = Model('APS-v3')

## 定义变量

## 最终产品制造变量：其中的 t 参数，表示产品在t期可以制造出来，可以用于交付订单需求，或放入库存
Prodmade = {}
for i in Product:
    for j in range(1,nppro[i]+1):
        for t in T: 
            if t > ProdLT[i]:
                Prodmade[i,j,t] = msingle.addVar(name = 'Pmade('+str(i)+','+str(j)+','+str(t)+')')

## 自制品制造变量：其中的 t 参数，表示自制品在 t 期可以制造出来，可以用于交付后续高层级物料的生产，或作为中间产品出售，或放入库存
Selfmade = {}                      
for i in Self:
    for j in range(1,nspro[i]+1):
        for t in T: 
            if t > SelfLT[i]:
                Selfmade[i,j,t] = msingle.addVar(name='Smade('+str(i)+','+str(j)+','+str(t)+')')

## 最终产品的库存数量变量
ProdInv = {}                                                    
for i in Product:
    for t in T0: 
        ProdInv[i,t] = msingle.addVar(lb=ProdInvL[i], ub=ProdInvU[i],name='Pinv('+str(i)+','+str(t)+')')
            
## 自制品库存数量变量           
SelfInv = {}                                                    
for i in Self:
    for t in T0: 
        SelfInv[i,t] = msingle.addVar(lb=SelfInvL[i],ub=SelfInvU[i],name='Sinv('+str(i)+','+str(t)+')')

## 原材料库存数量变量 
RawInv = {}                             
for i in Raw:
    for t in T0: 
        RawInv[i,t] = msingle.addVar(lb=RawInvL[i],ub=RawInvU[i],name='Rinv('+str(i)+','+str(t)+')')

## 采购原材料数量变量
Purchase = {}                           
for i in Raw:
    for t in T: 
        Purchase[i,t] = msingle.addVar(ub=1000000,name='Purc('+str(i)+','+str(t)+')')

## 工艺设备正常工作负荷变量
Workload = {}                                               
for i in Equip:
    for t in T: 
        Workload[i,t] = msingle.addVar(ub=EquipCap[i],name='Load('+str(i)+','+str(t)+')')

## 工艺设备超时工作负荷变量
Overload = {}                                               
for i in Equip:
    for t in T: 
        Overload[i,t] = msingle.addVar(ub=EquipCap[i]*EquipOverT[i],name='Over('+str(i)+','+str(t)+')')
       
if nfixtable == 1:
    ## 模具正常使用负荷变量
    Fixtload = {}                                               
    for i in Fixture:
        for t in T: 
            Fixtload[i,t] = msingle.addVar(ub=FixtCap[i],name='Fixt('+str(i)+','+str(t)+')')

    ## 模具超时负荷变量
    FixtPlus = {}                                               
    for i in Fixture:
        for t in T: 
            FixtPlus[i,t] = msingle.addVar(ub=FixtCap[i]*FixtOver[i],name='Fpls('+str(i)+','+str(t)+')')

## 产品销售数量变量
OrdSale = {}                               
for i in Order:
#    for t in T:
    for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1): 
        if t <= nperiod:
            OrdSale[i,t] = msingle.addVar(name='OrdS('+str(i)+','+str(t)+')')
            
## 产品延期数量变量
OrdDelay = {}                               
for i in Order:
    for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1): 
        if t <= nperiod:
            OrdDelay[i,t] = msingle.addVar(name='OrdD('+str(i)+','+str(t)+')')
            
## 自制品外协采购数量变量
if nouttable == 1:
    OutSourc = {}
    for i in OutsNo:
        for t in T:
            OutSourc[i,t] = msingle.addVar(ub=OutSQ[i,t],name='OutS('+str(i)+','+str(t)+')')

## 物料替代变量
if len(SubstiNo) != 0:
    
    # 设置替代变量：
    Substi = {}
    Subbatch = {}
    for i in SubstiNo:
        for t in T:
            Substi[i,t] = msingle.addVar(ub=SubLimit[i,t],name='Substi('+str(i)+','+str(t)+')')
        if SubBatch[i] == 1:
            intager = 1
            # 设置整批替代的0-1整数变量
            for t in T:
                Subbatch[i,t] = msingle.addVar(vtype = GRB.BINARY, name='Subbatch('+str(i)+','+str(t)+')')
            
            

    
## 不可行变量
SaleInf   = msingle.addVars(Order, T, name = 'SaleInf')
EquipInf  = msingle.addVars(Equip, T, name = 'EquipInf')                                    # 设备能力不可行变量
FixtInf   = msingle.addVars(Fixture, T, name = 'FixtInf')                                   # 工装能力不可行变量
ProdInf   = msingle.addVars(Product, T, name = 'ProdInf')                                   # 产品生产不可行变量
SelfInf   = msingle.addVars(Self, T, name = 'SelfInf')                                      # 自制品生产不可行变量
RawInf    = msingle.addVars(Raw, T, name = 'RawInf')                                        # 原材料不可行变量


## 目标函数：生产利润最大
## ==============================================================================================

msingle.setObjective(
    quicksum(OrdPrice[i]*OrdSale[i,t] for i in Order for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1) if t<=nperiod)               # 销售收入
    - quicksum(OrdFine[i]*OrdDelay[i,t] for i in Order for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1) if t<=nperiod)             # 延迟交付成本
    - quicksum(RawCost[i]*Purchase[i,t] for i in Raw for t in T)                                                                    # 原材料采购成本
    - quicksum(OutsCost[i]*OutSourc[i,t] for i in OutsNo for t in T)                                                                # 外协件采购成本
    - quicksum((EquipCost[p]*Workload[p,t] + EquipCost[p]*EquipOverR[p]*Overload[p,t]) for p in Equip for t in T)                   # 工艺加工成本
    - quicksum((FixtCost[p]*Fixtload[p,t] + FixtCost[p]*Fovcost[p]*FixtPlus[p,t]) for p in Fixture for t in T if nfixtable == 1)    # 模具使用成本
    - quicksum(ProdInvCost[i]*ProdInv[i,t] for i in Product for t in T0)                                                            # 产品库存成本
    - quicksum(SelfInvCost[i]*SelfInv[i,t] for i in Self for t in T0)                                                               # 自制件库存成本
    - quicksum(RawInvCost[i]*RawInv[i,t] for i in Raw  for t in T0)                                                                 # 原材料库存成本
    - quicksum(penalty*ProdInf[i,t] for i in Product for t in T)                                                                    # 不可行罚成本，分别是产品、自制品、原材料、工艺能力
    - quicksum(penalty*SaleInf[i,t] for i in Order for t in T)
    - quicksum(penalty*SelfInf[i,t] for i in Self for t in T) 
    - quicksum(penalty*RawInf[i,t]  for i in Raw for t in T) 
    - quicksum(penalty*FixtInf[i,t]  for i in Fixture for t in T) 
    - 0.000001*quicksum(Substi[k,t] for k in SubstiNo for t in T) 
    - quicksum(penalty*EquipInf[p,t] for p in Equip for t in T), GRB.MAXIMIZE 
    )

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n生成目标函数时间:  ', runtime)


# 订单销售数量平衡约束：
#      订单交付当期： 本期销售数量 + 本期延迟数量  ==  订单数量 -  - 不可行数量
#      订单交付期： 本期销售数量 - 前期延迟数量  ==  订单数量 - 本期延迟数量 - 不可行数量
# ===============================================================================================

SaleBal = {}
for i in Order:
    if OrdTime[i]+OrdDly[i] <= nperiod:                                                                                                             # 延期交付期在计划期内
        for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1):
            if OrdDly[i] == 0:                                                                                                                          # 不允许延期
                if OrdCls[i] != 3:                                                                                                                          # 必须交付
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                      # 交付量 + 不可行 = 订单量
                else:                                                                                                                                       # 可以不交付
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                                     # 交付量  <= 订单量  ！！！！！ + SaleInf[i,t] 

            elif OrdDly[i] == 1:                                                                                                                        # 允许延期 1 个周期
                if t == OrdTime[i]:                                                                                                                         # 交付当期 
                    if OrdCls[i] != 3:                                                                                                                          # 必须交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')      # 交付量 + 延期交付 + 不可行 = 订单量
                    else:                                                                                                                                       # 可以不交付
#                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] - OrdDelay[i,t-1] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                  # 交付量 - ??? 前期延期交付 = 订单量  
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                     # 交付量 + 延期交付 <= 订单量  

                else:                                                                                                                                       # 不是交付当期
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')                            # 当期交付量 = 前期延期交付量

            elif OrdDly[i] >= 2:                                                                                                                        # 允许延期超过 1 个周期（2个周期以上）
                if t == OrdTime[i]:                                                                                                                         # 交付当期 
                    if OrdCls[i] != 3:                                                                                                                          # 必须交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')       # 交付量 + 延期交付 + 不可行 = 订单量
                    else:                                                                                                                                       # 可以不交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                      # 交付量 + 延期交付 <= 订单量
                        
                elif t > OrdTime[i] and t < OrdTime[i]+OrdDly[i]:                                                                                           # 不是交付当期，也不是交付最后期
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')                # 交付量 + 当期延期交付 = 前期延期交付  
                else:                                                                                                                                       # 交付最后期
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')                                # 交付量 = 前期延期交付
                    
    else:                                                                                                                                           # 延期交付期超出计划期范围
        for t in range(OrdTime[i],nperiod+1):
            if nperiod - OrdTime[i] == 0:                                                                                                               # 交付期正好是计划期末
                if OrdCls[i] != 3:                                                                                                                          # 必须交付
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                      # 交付量 + 不可行 = 订单量
                else:                                                                                                                                       # 可以不交付
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                                     # 交付量  <= 订单量
            elif nperiod-OrdTime[i] == 1:                                                                                                               # 交付期是计划期末的前一期
                if t == OrdTime[i]:                                                                                                                         # 交付当期 
                    if OrdCls[i] != 3:                                                                                                                          # 必须交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')      # 交付量 + 延期交付 + 不可行 = 订单量
                    else:                                                                                                                                       # 可以不交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                     # 交付量 + 延期交付 <= 订单量  

                else:                                                                                                                                       # 不是交付当期
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')                                # 当期交付量 = 前期延期交付量
            elif nperiod-OrdTime[i] >= 2:                                                                                                               # 交付期与计划期末差值大于等于 2
                if t == OrdTime[i]:                                                                                                                         # 交付当期
                    if OrdCls[i] != 3:                                                                                                                          # 必须交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t]  + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')     # 交付量 + 延期交付 + 不可行 = 订单量
                    else:                                                                                                                                       # 可以不交付
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')                     # 交付量 + 延期交付 <= 订单量 
                elif t > OrdTime[i] and t < nperiod:                                                                                                        # 不是交付当期，也不是交付最后期
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')                # 交付量 + 当期延期交付 = 前期延期交付 
                else:                                                                                                                                       # 交付最后期
                    SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')                                # 交付量 = 前期延期交付


## 最终产品数量平衡约束                                                                           !!!! 加产品的在制品
## ==============================================================================================
ProdBal = {}
for i in Product:
    for t in T:
        if t > ProdLT[i]:                                                                                                       # 当前期大于制造提前期，可以制造出
            ProdBal[(i,t)] = msingle.addConstr((ProdInv[i,t-1] - ProdInv[i,t] + ProdInf[i,t]                                        # + 前期库存 - 当期库存 + 不可行
                + quicksum(Prodmade[i,k,t] for k in range(1,nppro[i]+1))                                                            # + 本期生产
                - quicksum(OrdSale[j,t] for j in Order if OrdProd[j] == ProdCode[i]                                                 # - 本期销售
                     if t >= OrdTime[j] if t <= OrdTime[j]+OrdDly[j])
                - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == ProdCode[i])                                 # - 替代其他物料的数量
                + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == ProdCode[i])                                 # + 被其他物料替代的数量 
                == 0), name = 'ProdBal('+str(i)+','+str(t)+')')
        else:
            ProdBal[(i,t)] = msingle.addConstr((ProdInv[i,t-1] - ProdInv[i,t] + ProdInf[i,t]
                - quicksum(OrdSale[j,t] for j in Order if OrdProd[j] == ProdCode[i] if t >= OrdTime[j] if t <= OrdTime[j]+OrdDly[j])
                - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == ProdCode[i])                                 # - 替代其他物料的数量
                + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == ProdCode[i])                                 # + 被其他物料替代的数量 
                == 0), name = 'ProdBal('+str(i)+','+str(t)+')')

        
## 自制物料数量平衡约束
## ==============================================================================================
Self1Bal = {}
for i in Self:
    for t in T:
        if t>SelfLT[i]:                                                                                                         # 当前期大于制造提前期(t>SelfLT[i])，则自制件可以生产出来,也可以动用库存或采购；
            Self1Bal[i,t] = msingle.addConstr((SelfInv[i,t-1] - SelfInv[i,t] + SelfInf[i,t]                                         # + 前期库存 - 当期库存 + 不可行
                + quicksum(Selfmade[i,k,t] for k in range(1,nspro[i]+1))                                                            # + 本期生产
                + quicksum(OutSourc[j,t] for j in OutsNo if nouttable == 1 if OutsCode[j] == SelfCode[i])                                             # + 外协采购
                - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for (j,q) in FbP[i] for k in range(1,nppro[j]+1) if t+ProdLT[j]<=nperiod)    # - 生产最终产品消耗的自制物料
                - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for (j,q) in FbS[i] for k in range(1,nspro[j]+1) if t+SelfLT[j]<=nperiod)    # - 生产上级自制品消耗的自制品物料
                - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == SelfCode[i])                                 # - 替代其他物料的数量
                + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == SelfCode[i])                                  # + 被其他物料替代的数量
                == 0), name = 'SelfBal('+str(i)+','+str(t)+')')  
        
        # 当前期小于等于制造提前期（t <= SelfLT[i]），则自制件不能生产出来，只能动用在制品、库存或采购；  
        else:                                                                                                                   # 当前期小于制造提前期，在制品数量需进入物料平衡约束
            if nwiptable == 1:
                Self1Bal[i,t] = msingle.addConstr((SelfInv[i,t-1] - SelfInv[i,t] + SelfInf[i,t]                                         # + 前期库存 - 当期库存 + 不可行
                    + quicksum(OutSourc[j,t] for j in OutsNo if OutsCode[j] == SelfCode[i])                                             # + 外协采购
                    - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for (j,q) in FbP[i] for k in range(1,nppro[j]+1))                            # - 生产最终产品消耗的自制物料
                    - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for (j,q) in FbS[i] for k in range(1,nspro[j]+1))                            # - 生产上级自制品消耗的自制品物料
                    - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == SelfCode[i])                                 # - 替代其他物料的数量
                    + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == SelfCode[i])                                 # + 被其他物料替代的数量
                    + quicksum(WipQunt[k] for k in WipNo if WipCode[k] == SelfCode[i] if SelfLT[i]-WipStage[k] == t-1)                  # + 在制品数量
                    == 0), name = 'SelfBal('+str(i)+','+str(t)+')') 
            else:
                Self1Bal[i,t] = msingle.addConstr((SelfInv[i,t-1] - SelfInv[i,t] + SelfInf[i,t]                                         # + 前期库存 - 当期库存 + 不可行
                    + quicksum(OutSourc[j,t] for j in OutsNo if OutsCode[j] == SelfCode[i])                                             # + 外协采购
                    - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for (j,q) in FbP[i] for k in range(1,nppro[j]+1))                            # - 生产最终产品消耗的自制物料
                    - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for (j,q) in FbS[i] for k in range(1,nspro[j]+1))                            # - 生产上级自制品消耗的自制品物料
                    - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == SelfCode[i])                                 # - 替代其他物料的数量
                    + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == SelfCode[i])                                 # + 被其他物料替代的数量
                    == 0), name = 'SelfBal('+str(i)+','+str(t)+')') 


## 原材料数量平衡约束，
## ==============================================================================================
RawBal = {}
for i in Raw:
    for t in T:
        RawBal[(i,t)] = msingle.addConstr((Purchase[i,t-RawLT[i]] + RawInv[i,t-1] - RawInv[i,t] + RawInf[i,t]                       # + 本期采购 + 前期库存 - 当期库存 + 不可行
                - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for(j,q)in RbP[i] for k in range(1,nppro[j]+1) if t+ProdLT[j]<=nperiod)      # - 生产最终产品消耗的原材料
                - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for(j,q)in RbS[i] for k in range(1,nspro[j]+1) if t+SelfLT[j]<=nperiod)      # - 生产自制品消耗的原材料
                - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == RawCode[i])                                  # - 替代其他物料的数量
                + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == RawCode[i])                                  # + 被其他物料替代的数量
                == 0), name = 'RawBal('+str(i)+','+str(t)+')') 

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n生成物料平衡约束:  ', runtime)


## 工艺能力平衡约束
## ==============================================================================================
CapBal = {}
for i in Equip:
    for t in T:
        if t > npmaxt:
            CapBal[(i,t)] = msingle.addConstr((
                quicksum(Protime[k,t1]*Prodmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeP[i]                       # 加工产品消耗工艺能力 
                    for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>ProdLT[j])
              + quicksum(Protime[k,t1]*Selfmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeS[i]                       # 加工自制品消耗工艺能力
                    for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>SelfLT[j])
              <= Workload[i,t] + Overload[i,t] + EquipInf[i,t]), name = 'CapBal('+str(i)+','+str(t)+')')                                                                         # 正常能力 + 加班能力
        else:
            CapBal[(i,t)] = msingle.addConstr((
                quicksum(Protime[k,t1]*Prodmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeP[i]                           # 加工产品消耗工艺能力 
                    for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>ProdLT[j])
              + quicksum(Protime[k,t1]*Selfmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeS[i]                           # 加工自制品消耗工艺能力
                    for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>SelfLT[j])
              <= Workload[i,t] + Overload[i,t] - WipLoad[i,t] + EquipInf[i,t]), name = 'CapBal('+str(i)+','+str(t)+')')     # 正常能力 + 加班能力 - 自制品占用 + 不可行



## 工装能力平衡约束
## ==============================================================================================
if nfixtable == 1:
    FixtBal = {}
    for i in Fixture:
        for t in T:
            FixtBal[(i,t)] = msingle.addConstr((
                  quicksum(Protime[k,t1]*ProFixq[k]*Prodmade[j,1,t+ProMaxT[k]-t1] for (j,k) in MdP[i]                        # 加工产品消耗 
                    for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>ProdLT[j])
                + quicksum(Protime[k,t1]*ProFixq[k]*Selfmade[j,1,t+ProMaxT[k]-t1] for (j,k) in MdS[i]                        # 加工自制品消耗
                    for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>SelfLT[j])
                <= Fixtload[i,t] + FixtPlus[i,t] + FixtInf[i,t]), name = 'FixtBal('+str(i)+','+str(t)+')')


## 虚拟件替代比例约束
## ==============================================================================================
#SubRatio = {}
#for i in range(1,nsubstiself+1):
#    for t in T:
#        if SubRatioS[i] > 0.000001:
#            SubRatio[(i,t)] = msingle.addConstr((
#                  quicksum(Selfmade[k,1,t]/SubRatioS[i] for k in Self if SelfCode[k] == SubstiSelf1[i]) -
#                  quicksum(Selfmade[k,1,t] for k in Self if SelfCode[k] == SubstiSelf2[i])
#                  == 0), name = 'SuRatio('+str(i)+','+str(t)+')') 

Subratio = {}
for i in SubstiNo:
    if SubRatio[i] > 0.000001:
        if SubType[i] == 1:
            Subratio[i] = msingle.addConstr((
                quicksum(Prodmade[k,j,t] for k in Product for j in range(1,nppro[k]+1) for t in T if ProdCode[k] == SubCode1[i])/SubRatio[i] -
                quicksum(Prodmade[k,j,t] for k in Product for j in range(1,nppro[k]+1) for t in T if ProdCode[k] == SubCode2[i]) 
                == 0), name = 'SuRatio(' + str(i) + ')')
                      
        elif SubType[i] == 2:
            Subratio[i] = msingle.addConstr((
                quicksum(Selfmade[k,j,t] for k in Self for j in range(1,nspro[k]+1) for t in T if SelfCode[k] == SubCode1[i])/SubRatio[i] -
                quicksum(Selfmade[k,j,t] for k in Self for j in range(1,nspro[k]+1) for t in T if SelfCode[k] == SubCode2[i])
                      == 0), name = 'SuRatio(' + str(i) + ')') 
            
        elif SubType[i] == 3:
            Subratio[i] = msingle.addConstr((
                quicksum(Purchase[k,t] for k in Raw for t in T if RawCode[k] == SubCode1[i])/SubRatio[i] -
                quicksum(Purchase[k,t] for k in Raw for t in T if RawCode[k] == SubCode2[i])
                      == 0), name = 'SuRatio(' + str(i) + ')')

SubBch1 = {}
SubBch2 = {}
for i in SubstiNo: 
    if SubBatch[i] == 1 and SubType[i] == 1:
        for t in T: 
            SubBch1[i,t] = msingle.addConstr((
                quicksum(Prodmade[Prodidx[SubCode1[i]],j,t] for j in range(1,nppro[Prodidx[SubCode1[i]]]+1))
                <= 100000*Subbatch[i,t]), name = 'Subbach(' + str(i) + ')')
            SubBch2[i,t] = msingle.addConstr((
                quicksum(Prodmade[Prodidx[SubCode2[i]],j,t] for j in range(1,nppro[Prodidx[SubCode2[i]]]+1))
                <= 100000*(1-Subbatch[i,t])), name = 'Subbach(' + str(i) + ')')

    elif SubBatch[i] == 1 and SubType[i] == 2:
        for t in T: 
            SubBch1[i,t] = msingle.addConstr((
                quicksum(Selfmade[Selfidx[SubCode1[i]],j,t] for j in range(1,nspro[Selfidx[SubCode1[i]]]+1))
                <= 100000*Subbatch[i,t]), name = 'SubBach(' + str(i) + ')')
            SubBch2[i,t] = msingle.addConstr((
                quicksum(Selfmade[Selfidx[SubCode2[i]],j,t] for j in range(1,nspro[Selfidx[SubCode2[i]]]+1))
                <= 100000*(1-Subbatch[i,t])), name = 'Subbach(' + str(i) + ')')

    elif SubBatch[i] == 1 and SubType[i] == 3:
        SubBch1[i,t] = msingle.addConstr((quicksum(Purchase[Rawidx[SubCode1[i]],t] for t in T)
                <= 100000*Subbatch[i,t]), name = 'SubBach(' + str(i) + ')')
        SubBch2[i,t] = msingle.addConstr((quicksum(Purchase[Rawidx[SubCode2[i]],t] for t in T)
                <= 100000*(1-Subbatch[i,t])), name = 'Subbach(' + str(i) + ')')
 
startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n生成能力平衡约束:  ', runtime) 

## ==============================================================================================
##     界约束
## ==============================================================================================

## 关键原材料采购数量限制约束（界约束）
RawPurchlim = msingle.addConstrs((Purchase[Rawidx[RlimId[i]],t] <= RawlimQ[i,t] for i in RlimNo for t in T), name = 'RawPurchlim')
        
ProdInv0lim = msingle.addConstrs((ProdInv[i,0] - ProdInv0[i] == 0 for i in Product), name = 'PInv0lim')
ProdInvTlim = msingle.addConstrs((ProdInv[i,nperiod] - ProdInvT[i] == 0 for i in Product), name = 'PInvTlim')

SelfInv0lim = msingle.addConstrs((SelfInv[i,0] - SelfInv0[i] == 0 for i in Self), name = 'SInv0lim')
SelfInvTlim = msingle.addConstrs((SelfInv[i,nperiod] - SelfInvT[i] == 0 for i in Self), name = 'SInvTlim')

RawInv0lim  = msingle.addConstrs((RawInv[i,0] - RawInv0[i] == 0 for i in Raw), name = 'RInv0lim')

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n生成界平衡约束:  ', runtime)
print()

if intager == 1:
    msingle.setParam(GRB.Param.MIPGap, 0.0001)                               ## 求解精度限制（收敛标准）
#msingle.setParam(GRB.Paramsingle.TimeLimit, 100)                               ## 求解时间限制
#msingle.setParam(GRB.Param.Method,2)                                            ## 参数设置： -1 自动， 0 primal， 1 对偶， 2 内点法，3 并行 

# 调用存储的基
#filename2 = 'D:/My_Model/APS-New/single/FM/msingle-2.bas'
#msingle.update()
#msingle.read(filename2)

## 调用优化软件
msingle.optimize()

# 输出LP文件
#filename1 = 'D:/My_Model/APS-New/single/FM/fff.lp'
#msingle.write(filename1)

# 输出基文件
#msingle.write(filename2)

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n求解完成:        ', runtime)


#############################################################################################
##            输出计算结果
#############################################################################################


## 获取模型主要资源的影子价格（对偶解）
if intager == 0:
    Proddual  = {}                                                  # 最终产品影子价格（对偶解）
    for i in Product:
        for t in T:
            Proddual[i,t] = -ProdBal[i,t].Pi        
    Self1dual = {}                                                  # 自制品影子价格（对偶解）
    for i in Self:
        for t in T:
            Self1dual[i,t] = -Self1Bal[i,t].Pi         
    Rawdual   = {}                                                  # 原材料影子价格（对偶解）
    for i in Raw:
        if RawCode[i] not in Selfset:
            for t in T:
                Rawdual[i,t]  = -RawBal[i,t].Pi
    Equipdual   = {}                                                  # 工艺设备能力影子价格（对偶解）
    for i in Equip:
        for t in T:
            Equipdual[i,t] = CapBal[i,t].Pi
    if nfixtable == 1:
        Fixtdual  = {}                                                  # 自模具使用能力影子价格（对偶解）
        for i in Fixture:
            for t in T:
                Fixtdual[i,t] = FixtBal[i,t].Pi


eps = 1e-4
w = Workbook()

fontBold = Font()
fontBold.name = 'Bold Font'
fontBold.bold = True
styleBold = XFStyle()
styleBold.font = fontBold

# =============================================================================
# Sheet 1: 订单销售计划
# =============================================================================
            
ws1 = w.add_sheet('订单销售')
ws1.write(1,1,'订单号',  styleBold) 
ws1.write(1,2,'产品代码',styleBold)
ws1.write(1,3,'订单等级',styleBold)
ws1.write(1,4,'订单价格',styleBold)
ws1.write(1,5,'订单数量',styleBold)
ws1.write(1,6,'订单交期',styleBold)
ws1.write(1,7,'实际交期',styleBold)
ws1.write(1,8,'交付数量',styleBold)
ws1.write(1,9,'延期数量',styleBold)
ws1.write(1,10,'交付状态',styleBold)
ws1.write(1,11,'销售收入',styleBold)
ws1.write(1,12,'延期罚金',styleBold)
ws1.write(1,13,'影子价格',styleBold)
ws1.write(1,14,'边际贡献',styleBold)

Sale = {}
SumSale = 0
SumDly = 0
SumIncome = 0
SumDlyFine = 0
j = 1
Ordeliv = {}
for k in range(1,nordclass+1):
    for k1 in range(1,3):                       # 这里的 3 是 2+1，k1循环2次，第一次是统计订单单次，第二是统计订单交付数量
        for k2 in range(1,6):                   # 这里的 6 是 5+1，k2循环5次，分别对应订单总数、按期交付、部分按期、延期、未交付
            Ordeliv[k,k1,k2] = 0
            
for i in Order:
    sumQ = 0                                  
    icls = OrdCls[i]
    Ordeliv[icls,1,1] += 1
    Ordeliv[icls,2,1] += OrdQunt[i]
    for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1):
        if t <= nperiod:
            if OrdSale[i,t].x>0.0001:
                dlyfine = 0
                j += 1
                ws1.write(j,1,OrdNo[i])
                ws1.write(j,2,OrdProd[i])
                ws1.write(j,3,OrdCls[i])
                ws1.write(j,4,OrdPrice[i])
                ws1.write(j,5,OrdQunt[i])
                ws1.write(j,6,OrdTime[i])
                if OrdSale[i,t].x > 0.0001: 
                    ws1.write(j,7,t)
                    sumQ += OrdSale[i,t].x
                    if t == OrdTime[i]:
                        if OrdQunt[i] - OrdSale[i,t].x < 0.0001 :
                            ws1.write(j,10,'按期交付')
                            Ordeliv[icls,1,2] += 1
                            Ordeliv[icls,2,2] += OrdSale[i,t].x
                        else:
                            if OrdQunt[i]-OrdSale[i,t].x-OrdDelay[i,t].x > 0.0001:
                                ws1.write(j,10,'部分按期交付',styleBold)
                            else:
                                ws1.write(j,10,'部分按期')
                            Ordeliv[icls,1,3] += 1
                            Ordeliv[icls,2,3] += OrdSale[i,t].x
                    else:
                        ws1.write(j,10,'延期交付',styleBold)
                        Ordeliv[icls,2,4] += OrdSale[i,t].x                                         # 计算延期数量
                        dlyfine = OrdSale[i,t].x*OrdFine[i]*(t-OrdTime[i])                          # 延期交付罚金
                        if OrdQunt[i]-OrdSale[i,t].x-OrdDelay[i,t].x < 0.0001:                      # 全部延期交付计入延期单数
                            Ordeliv[icls,1,4] += 1       
                ws1.write(j,8,OrdSale[i,t].x)
                ws1.write(j,9,OrdDelay[i,t].x)
                ws1.write(j,11,OrdSale[i,t].x*OrdPrice[i])
                ws1.write(j,12,dlyfine)
                if intager == 0:
                    ws1.write(j,13,Proddual[Prodidx[OrdProd[i]],t])
                    Marjin = OrdPrice[i]-Proddual[Prodidx[OrdProd[i]],t]
                    ws1.write(j,14,Marjin)
                SumSale += OrdSale[i,t].x
                SumIncome += OrdSale[i,t].x*OrdPrice[i]
                SumDly += OrdDelay[i,t].x
                SumDlyFine += dlyfine
    if sumQ == 0 and OrdQunt[i] != 0:
        Ordeliv[icls,1,5] += 1
        Ordeliv[icls,2,5] += OrdQunt[i]
        j += 1
        ws1.write(j,1,OrdNo[i])
        ws1.write(j,2,OrdProd[i])
        ws1.write(j,3,OrdCls[i])
        ws1.write(j,4,OrdPrice[i])
        ws1.write(j,5,OrdQunt[i])
        ws1.write(j,6,OrdTime[i])
        ws1.write(j,10,'未交付',styleBold)
        if intager == 0:
            ws1.write(j,13,Proddual[Prodidx[OrdProd[i]],OrdTime[i]])
            if intager == 0:
                Marjin = OrdPrice[i]-Proddual[Prodidx[OrdProd[i]],OrdTime[i]]
                ws1.write(j,14,Marjin)
j += 1
ws1.write(j,7,'合计')
ws1.write(j,8,SumSale)
ws1.write(j,9,SumDly)
ws1.write(j,11,SumIncome)
ws1.write(j,12,SumDlyFine)

# =============================================================================
# Sheet 2: 产品生产计划
# =============================================================================

ws2 = w.add_sheet('产品计划')
ws2.write(1,1,'产品生产计划',styleBold)
ws2.write(2,1,'产品代码',styleBold)
ws2.write(2,2,'多工艺序号',styleBold)

sumtotal = 0
for t in T:
    ws2.write(2,2+t,t,styleBold)
ws2.write(2,3+len(T),'数量小计',styleBold)
j = 2
for i in Product:
    for k in range(1,nppro[i]+1):
        sumProd = sum(Prodmade[i,k,t].x for t in T if t>ProdLT[i])
        if sumProd > 0.001:
            j += 1
            ws2.write(j,1,ProdCode[i])
            ws2.write(j,2,k)
            for t in T:
                if t>ProdLT[i] and Prodmade[i,k,t].x>eps:
                    ws2.write(j,2+t,Prodmade[i,k,t].x)
            sumtotal += sumProd
            ws2.write(j,3+len(T),sumProd)
j += 1
ws2.write(j,2+len(T),'数量合计',styleBold)
ws2.write(j,3+len(T),sumtotal,styleBold)

## 产品销售计划
j += 2
ws2.write(j,1,'产品销售计划',styleBold)
j += 1
ws2.write(j,1,'产品代码',styleBold)
#ws2.write(j,2,'订单等级',styleBold)

sumtotal = 0
for t in T:
    ws2.write(j,2+t,t,styleBold)
ws2.write(j,3+len(T),'数量小计',styleBold)
OrdPlan = {}
for i in Product:
    for t in T:
        OrdPlan[i,t] = 0
for i in Order:
    for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1):
        if t <= nperiod:
            if OrdSale[i,t].x > 0.0001:
                p = Prodidx[OrdProd[i]]
                OrdPlan[p,t] += OrdSale[i,t].x
for p in Product:
    j += 1
    ws2.write(j,1,ProdCode[p])
    sump = 0
    for t in T:
        if OrdPlan[p,t] > 0.001:
            ws2.write(j,2+t,OrdPlan[p,t])
            sump += OrdPlan[p,t]
    ws2.write(j,3+len(T),sump)
    sumtotal += sump
j += 1
ws2.write(j,2+len(T),'数量合计',styleBold)
ws2.write(j,3+len(T),sumtotal,styleBold)
        
# =============================================================================
# Sheet 3: 自制件生产计划
# =============================================================================

ws3 = w.add_sheet('自制件计划')
ws3.write(1,0,'自制件序号',styleBold)
ws3.write(1,1,'自制件代码',styleBold)
ws3.write(1,2,'多工艺号',styleBold)
sumtotal = 0
for t in T: ws3.write(1,2+t,t,styleBold)
ws3.write(1,3+len(T),'数量小计',styleBold)
j = 1
for i in Self:
    for k in range(1,nspro[i]+1):
        sumSelf = sum(Selfmade[i,k,t].x for t in T if t>SelfLT[i])
        if sumSelf > 0.0001:
            j += 1
            ws3.write(j,0,i)
            ws3.write(j,1,SelfCode[i])
            ws3.write(j,2,k)
            for t in T:
                if t>SelfLT[i]: 
                    if Selfmade[i,k,t].x>eps:
                        ws3.write(j,2+t,Selfmade[i,k,t].x)
            sumtotal += sumSelf
            ws3.write(j,3+len(T),sumSelf)
    if nwiptable == 1:
        for k in WipNo:
            if SelfCode[i] == WipCode[k]:
                j += 1
                ws3.write(j,0,i)
                ws3.write(j,1,SelfCode[i])
                ws3.write(j,2,'wip')
                ws3.write(j,2+WipMaxT[k]-WipStage[k],WipQunt[k])
j += 1
ws3.write(j,2+len(T),'数量合计',styleBold)
ws3.write(j,3+len(T),sumtotal,styleBold)
        
# =============================================================================
# Sheet 4: 采购计划
# =============================================================================
            
ws4 = w.add_sheet('采购')
j = 0
sumOut = 0
for i in OutsNo:
    for t in T: 
        sumOut += OutSourc[i,t].x
OutsumQunt = 0
OutsumCost = 0
if sumOut > 0.001:
    ws4.write(1,1,'自制件外协采购',styleBold)
    ws4.write(2,0,'自制件外协序号',styleBold)
    ws4.write(2,1,'自制件代码',styleBold)
    for t in T:
        ws4.write(2,1+t,t,styleBold)
    ws4.write(2,2+nperiod,'数量小计',styleBold)
    ws4.write(2,3+nperiod,'成本小计',styleBold)
    j = 2
    for i in OutsNo:
        sumOut = 0
        for t in T: sumOut += OutSourc[i,t].x
        if sumOut > 0.001:
            j += 1
            ws4.write(j,0,i)
            ws4.write(j,1,OutsCode[i])
            for t in T:
                if OutSourc[i,t].x > eps:
                    ws4.write(j,1+t,OutSourc[i,t].x)
            cc = sumOut*OutsCost[i]
            ws4.write(j,2+nperiod,sumOut)
            ws4.write(j,3+nperiod,cc)
            OutsumCost += cc
            OutsumQunt += sumOut
    j += 1
    ws4.write(j,1+nperiod,'合计',styleBold)        
    ws4.write(j,2+nperiod,OutsumQunt)        
    ws4.write(j,3+nperiod,OutsumCost) 

j += 1
ws4.write(j,1,'原材料采购',styleBold)
j += 1
ws4.write(j,0,'物料序号',styleBold)
ws4.write(j,1,'物料代码',styleBold)
for t in T:
    ws4.write(j,1+t,t,styleBold)
ws4.write(j,2+nperiod,'数量小计',styleBold)
ws4.write(j,3+nperiod,'成本小计',styleBold)
RawsumQunt = 0
RawsumCost = 0
for i in Raw:
    sumRaw = 0
    for t in T: sumRaw += Purchase[i,t].x
    if sumRaw > 0.001:
        j += 1
        ws4.write(j,0,i)
        ws4.write(j,1,RawCode[i])
        for t in T: 
            if Purchase[i,t].x > eps:
                ws4.write(j,1+t,Purchase[i,t].x)
        cc = sumRaw*RawCost[i]
        ws4.write(j,2+nperiod,sumRaw)
        ws4.write(j,3+nperiod,cc)
        RawsumCost += cc
        RawsumQunt += sumRaw
j += 1
ws4.write(j,1+nperiod,'合计',styleBold)        
ws4.write(j,2+nperiod,RawsumQunt)        
ws4.write(j,3+nperiod,RawsumCost)        

# =============================================================================
# Sheet 5: 库存
# =============================================================================
            
ws5 = w.add_sheet('库存')
ws5.write(1,0,'产品库存',styleBold)
ws5.write(1,1,'物料号',styleBold)
PinvSumCost = 0
TotalCost = 0
for t in T0:
    ws5.write(1,2+t,t,styleBold)
ws5.write(1,3+nperiod,'成本小计',styleBold)
j = 1
for i in Product:
    sump = 0
    for t in T0: sump += ProdInv[i,t].x
    if sump > 0.0001:
        j += 1
        ws5.write(j,1,ProdCode[i])
        for t in T0:
            if ProdInv[i,t].x > eps:
                ws5.write(j,2+t,ProdInv[i,t].x)
            else:
                pass
        sumcost = sump*ProdInvCost[i] 
        ws5.write(j,3+nperiod,sumcost)
        PinvSumCost += sumcost
ws5.write(j+1,2+nperiod,'成本合计')
ws5.write(j+1,3+nperiod,PinvSumCost)
TotalCost += PinvSumCost

j += 2
ws5.write(j,0,'自制产品库存',styleBold)
j += 1
ws5.write(j,1,'代码',styleBold)
for t in T0:
    ws5.write(j,2+t,t,styleBold)
ws5.write(j,3+nperiod,'成本小计',styleBold)
SinvSumCost = 0
for i in Self:
    suminv = 0
    for t in T0: suminv += SelfInv[i,t].x
    if suminv > 0.001:
        j += 1
        ws5.write(j,1,SelfCode[i])
        for t in T0:
            if SelfInv[i,t].x > eps:
                ws5.write(j,2+t,SelfInv[i,t].x)
        sumcost = suminv*SelfInvCost[i] 
        ws5.write(j,3+nperiod,sumcost)
        SinvSumCost += sumcost
ws5.write(j+1,2+nperiod,'成本合计')
ws5.write(j+1,3+nperiod,SinvSumCost)
TotalCost += SinvSumCost

j += 2
ws5.write(j,0,'原材料库存',styleBold)
j += 1
ws5.write(j,1,'代码',styleBold)
for t in T0:
    ws5.write(j,2+t,t,styleBold)
ws5.write(j,3+nperiod,'成本小计',styleBold)
RinvSumCost = 0
for i in Raw:
    sumr = 0
    for t in T0: sumr+= RawInv[i,t].x
    if sumr > 0.001:
        j += 1
        ws5.write(j,1,RawCode[i])
        suminv = 0
        for t in T0:
            if RawInv[i,t].x > eps:
                ws5.write(j,2+t,RawInv[i,t].x)
        sumcost = sumr*RawInvCost[i] 
        ws5.write(j,3+nperiod,sumcost)
        RinvSumCost += sumcost
ws5.write(j+1,2+nperiod,'成本合计',styleBold)
ws5.write(j+1,3+nperiod,RinvSumCost)
TotalCost += RinvSumCost


ws5.write(j+2,2+nperiod,'成本总计',styleBold)
ws5.write(j+2,3+nperiod,TotalCost)

# =============================================================================
# Sheet 6: 设备负荷与影子价格
# =============================================================================
            
ws6 = w.add_sheet('设备负荷')
ws6.write(1,1,'正常负荷分布',styleBold)
ws6.write(2,1,'设备号',styleBold)
ws6.write(2,2,'设备能力',styleBold)

for t in T:
    ws6.write(2,2+t,t,styleBold)
#    ws6.write(2,5+nperiod+t,t,styleBold)
#    ws6.write(2,7+2*nperiod+t,t,styleBold)
ws6.write(2,3+nperiod,'最大负荷率 %',styleBold)
ws6.write(2,4+nperiod,'平均负荷率 %',styleBold)
ws6.write(2,5+nperiod,'正常成本小计',styleBold)
#ws6.write(2,6+2*nperiod,'成本小计',styleBold)

j = 2
ProSumCost1 = 0
for i in Equip:
    sumload1 = 0
    sumload2 = 0
    sumrate = 0
    for t in T: sumload1 += Workload[i,t].x
    if sumload1 > 0.001:
        j += 1
        ws6.write(j,1,EquipId[i])
        ws6.write(j,2,EquipCap[i])
        maxload = 0
        for t in T:
            if Workload[i,t].x > eps:
                ws6.write(j,2+t,Workload[i,t].x)
                Loadrate = Workload[i,t].x/EquipCap[i]
                sumrate += Loadrate
                if Loadrate > maxload: maxload = Loadrate
        ws6.write(j,3+nperiod,maxload*100)
        ws6.write(j,4+nperiod,100*sumrate/nperiod)
        ws6.write(j,5+nperiod,sumload1*EquipCost[i])
        ProSumCost1 += sumload1*EquipCost[i]
ws6.write(j+1,4+nperiod,'成本合计')
ws6.write(j+1,5+nperiod,ProSumCost1)

sumover = 0
for i in Equip:
    for t in T:
        sumover += Overload[i,t].x


ProSumCost2 = 0
if sumover > 0.0001:
    j += 2              
    ws6.write(j,1,'超时（加班）负荷分布',styleBold)
    j += 1
    ws6.write(j,1,'设备号',styleBold)
    ws6.write(j,2,'设备能力',styleBold)
    for t in T:
        ws6.write(j,2+t,t,styleBold)
    ws6.write(j,3+nperiod,'超时成本小计',styleBold)
    for i in Equip:
        sumload1 = 0
        sumload2 = 0
        sumrcost = 0
        for t in T: sumload1 += Overload[i,t].x
        if sumload1 > 0.001:
            j += 1
            ws6.write(j,1,EquipId[i])
            for t in T:
                if Overload[i,t].x > eps:
                    ws6.write(j,2+t,Overload[i,t].x)
                    sumload2 += Overload[i,t].x
            sumcost = sumload2*EquipCost[i]*EquipOverR[i]
            ProSumCost2 += sumcost
            ws6.write(j,3+nperiod,sumcost)
    ws6.write(j+1,2+nperiod,'成本合计')
    ws6.write(j+1,3+nperiod,ProSumCost2)

if intager == 0:                 
    j += 3              
    ws6.write(j,1,'设备加工能力影子价格',styleBold)
    j += 1
    ws6.write(j,1,'设备号',styleBold)
    for t in T:
        ws6.write(j,2+t,t,styleBold)
        
    for i in Equip:
        j += 1
        ws6.write(j,1,EquipId[i])
        for t in T:
            ws6.write(j,2+t,Equipdual[i,t])

                

# =============================================================================
# Sheet 7: 设备加工计划
# =============================================================================

## 产品加工计划
ws7 = w.add_sheet('加工计划')
ws7.write(1, 1, '产品加工计划', styleBold)
ws7.write(1, 7, '加工数量', styleBold)
ws7.write(1, 8+nperiod, '占用能力', styleBold)
ws7.write(1, 8+2*nperiod, '能力合计', styleBold)

ws7.write(2, 1, '设备代码', styleBold)
ws7.write(2, 2, '工序代码', styleBold)
ws7.write(2, 3, '产品代码', styleBold)
ws7.write(2, 4, '多工艺号', styleBold)
wk = 4
if nfixtable == 1:
    ws7.write(2, 5, '工装代码', styleBold)
    ws7.write(2, 6, '工装数量', styleBold)
    wk = 6

for t in T:
    ws7.write(2, wk+t, t, styleBold)
    ws7.write(2, wk+1+nperiod+t, t, styleBold)
    
j = 2
sumcap = {}
sumprod = 0
for i in Equip:
    for k in Routing:
        if EquipId[i] == ProEquip[k]:
            ml = ProMult[k]
            mcode = ProMat [k]
            if mcode in Prodset:
                ip = Prodidx[mcode]
                sump = 0
                for t in T:
                    if t > ProdLT[ip]:
                        sump += Prodmade[ip,ml,t].x
                if sump > 0.0001:
                    j += 1
                    ws7.write(j, 1, EquipId[i])
                    ws7.write(j, 2, ProState[k])
                    ws7.write(j, 3, mcode)
                    ws7.write(j, 4, ml)
                    if nfixtable == 1:
                        ws7.write(j, 5, ProFixt[k])
                        ws7.write(j, 6, ProFixq[k])
                    for t in T:
                        sumcap[t] = 0
                        if t > ProdLT[ip]:
                            aa = Prodmade[ip,ml,t].x
                            if aa > 0.0001:
                                ws7.write(j, wk+t, aa)
                                if ProMaxT[k] > 1:
                                    for it in range(1,ProMaxT[k]+1):
                                        if t-it+1 >= 1:
                                            sumcap[t-it+1] += aa*Protime[k,ProMaxT[k]-it+1]
                                else:
                                    sumcap[t] += aa*Protime[k,1]
                    sumPeP = 0
                    for t in T:
                        if t > ProdLT[ip] and sumcap[t] > 0.0001:
                            ws7.write(j, wk+1+nperiod+t,sumcap[t])
                            sumPeP += sumcap[t]
                    ws7.write(j,wk+2+2*nperiod,sumPeP)
                    sumprod += sumPeP
j += 1
ws7.write(j,wk+1+2*nperiod,'合计')
ws7.write(j,wk+2+2*nperiod,sumprod)

## 自制件加工计划
sumself = 0
j += 2                        
ws7.write(j, 1, '自制件加工计划', styleBold)
ws7.write(j, 4, '加工数量', styleBold)
ws7.write(j, 8+nperiod, '占用能力', styleBold)
ws7.write(j, 8+2*nperiod, '能力合计', styleBold)
j += 1
ws7.write(j, 1, '设备代码', styleBold)
ws7.write(j, 2, '工序代码', styleBold)
ws7.write(j, 3, '产品代码', styleBold)
ws7.write(j, 4, '多工艺号', styleBold)
if nfixtable == 1:
    ws7.write(j, 5, '工装代码', styleBold)
    ws7.write(j, 6, '工装数量', styleBold)
for t in T:
    ws7.write(j, wk+t, t, styleBold)
    ws7.write(j, wk+1+nperiod+t, t, styleBold)

for i in Equip:
    for k in Routing:
        if EquipId[i] == ProEquip[k]:
            ml = ProMult[k]
            mcode = ProMat[k]
            if mcode in Selfset:
                ip = Selfidx[mcode]
                sump = 0
                for t in T:
                    if t > SelfLT[ip]:
                        sump += Selfmade[ip,ml,t].x
                if sump > 0.00001:
                    j += 1
                    ws7.write(j, 1, EquipId[i])
                    ws7.write(j, 2, ProState[k])
                    ws7.write(j, 3, mcode)
                    ws7.write(j, 4, ml)
                    if nfixtable == 1:
                        ws7.write(j, 5, ProFixt[k])
                        ws7.write(j, 6, ProFixq[k])
                    for t in T: sumcap[t] = 0
                    for t in T:
                        if t > SelfLT[ip]:                                          # 加工时间应大于生产提前期，否则无法生产出，能力分布无法展开
                            aa = Selfmade[ip,ml,t].x
                            if aa > 0.0001:
                                if ProMaxT[k] > 1:
                                    for it in range(1,ProMaxT[k]+1):                                # 遍历制造期 若ProMaxT[k] = 3， it= 1，2，3
                                        if t-it+1 >= 1:
                                            if Protime[k,it] > 0.0001:                                      # 
                                                ws7.write(j, wk+t-ProMaxT[k]+it, aa)
                                                sumcap[t-ProMaxT[k]+it] += aa*Protime[k,it]
                                else:
                                    sumcap[t] += aa*Protime[k,1]
                                    ws7.write(j, 6+t, aa)
                    sumPeP = 0
                    for t in T:
                        if sumcap[t] > 0.0001:
                            ws7.write(j, wk+1+nperiod+t,sumcap[t])
                            sumPeP += sumcap[t]
                    ws7.write(j,wk+2+2*nperiod,sumPeP)
                    sumself += sumPeP
                #ws7.write(j,8+2*nperiod,sumPeP)
                #sumself += sumPeP
                    
                if nwiptable == 1:
                    for iw in WipNo:                                                # 遍历在制品
                        if WipCode[iw] == ProMat[k]:                                    # 如果当前自制品有在制品
                            wipsum = 0
                            for it in range(WipStage[iw]+1,ProMaxT[k]+1):
                                wipsum += WipQunt[iw]*Protime[k,it]
                            if wipsum > 0.0001:
                                j += 1
                                ws7.write(j, 1, EquipId[i])
                                ws7.write(j, 2, ProState[k])
                                ws7.write(j, 3, mcode)
                                ws7.write(j, 4, 'wip')
                                if nfixtable == 1:
                                    ws7.write(j, 5, ProFixt[k])
                                    ws7.write(j, 6, ProFixq[k])
                                for it in range(WipStage[iw]+1,ProMaxT[k]+1):
                                    if Protime[k,it] > 0.0001:
                                        ws7.write(j, wk+it-WipStage[iw],WipQunt[iw])
                                        ws7.write(j, wk+1+nperiod+it-WipStage[iw],WipQunt[iw]*Protime[k,it])
                                ws7.write(j,wk+2+2*nperiod,wipsum)
                                sumself += wipsum
j += 1
ws7.write(j,wk+1+2*nperiod,'合计')
ws7.write(j,wk+2+2*nperiod,sumself)

# =============================================================================
# Sheet 8: 物料影子价格，按产品、自制品、原材料排列
# =============================================================================

if intager == 0:
    ws8 = w.add_sheet('影子价格')
    ws8.write(1,1,'物料号',styleBold)
    for t in T:
        ws8.write(1,1+t,t,styleBold)
    j = 2
    ws8.write(j,1,'产品影子价格',styleBold)
    for i in Product:
        j += 1
        ws8.write(j,1,ProdCode[i])
        for t in T:
            ws8.write(j,1+t,Proddual[i,t])
    
    j += 2
    ws8.write(j,1,'自制品影子价格',styleBold)
    for i in Self:
        j += 1
        ws8.write(j,1,SelfCode[i])
        for t in T:
            ws8.write(j,1+t,Self1dual[i,t])
    
    j += 2
    ws8.write(j,1,'原材料影子价格',styleBold)
    for i in Raw:
        if RawCode[i] not in Selfset:
            j += 1
            ws8.write(j,1,RawCode[i])
            for t in T:
                ws8.write(j,1+t,Rawdual[i,t])

# =============================================================================
# Sheet 9: 不可行数量
# =============================================================================

sumtotal = 0
ws9 = w.add_sheet('不可行')
ws9.write(1,2,'物料号',styleBold)
for t in T:
    ws9.write(1,2+t,t,styleBold)
j = 2
ws9.write(j,1,'产品不可行',styleBold)        
for i in Product:
    suminf = 0
    for t in T: suminf += ProdInf[i,t].x
    if suminf > 0.001:
        j += 1
        ws9.write(j,2,ProdCode[i])
        for t in T:
            if ProdInf[i,t].x > 0.0001:
                ws9.write(j,2+t,ProdInf[i,t].x)
        ws9.write(j,3+nperiod,suminf)
        sumtotal += suminf
j += 2
ws9.write(j,1,'自制件平衡不可行',styleBold)        
for i in Self:
    suminf = 0
    for t in T: suminf += SelfInf[i,t].x 
    if suminf > 0.0001:
        j += 1
        ws9.write(j,2,SelfCode[i])
        for t in T:
            if SelfInf[i,t].x > eps:
                ws9.write(j,2+t,SelfInf[i,t].x)
        ws9.write(j,3+nperiod,suminf)
        sumtotal += suminf

j += 2
ws9.write(j,1,'设备能力平衡不可行',styleBold)        
for i in Equip:
    suminf = 0
    for t in T: suminf += EquipInf[i,t].x
    if suminf > 0.001:
        j += 1
        ws9.write(j,2,EquipId[i])
        for t in T:
            if EquipInf[i,t].x > eps:
                ws9.write(j,2+t,EquipInf[i,t].x)
        ws9.write(j,3+nperiod,suminf)
        sumtotal += suminf
sumfine = sumtotal*penalty
j += 1
ws9.write(j,2+nperiod,'合计',styleBold)        
ws9.write(j,3+nperiod,sumtotal,styleBold)        
ws9.write(j,4+nperiod,sumfine)        

# =============================================================================
# Sheet 10: 工装表
# =============================================================================

if nfixtable == 1:            
    ws10 = w.add_sheet('工装负荷')
    ws10.write(1,1,'一般工装',styleBold)
    ws10.write(2,1,'工装代码',styleBold)
    for t in T:
        ws10.write(2,1+t,t,styleBold)
        ws10.write(2,5+nperiod+t,t,styleBold)
        ws10.write(2,7+2*nperiod+t,t,styleBold)
    ws10.write(2,2+nperiod,'最大负荷率 %',styleBold)
    ws10.write(2,3+nperiod,'平均负荷率 %',styleBold)
    ws10.write(2,4+nperiod,'成本小计',styleBold)
    ws10.write(2,6+2*nperiod,'成本小计',styleBold)
    
    j = 2
    MSumCost1 = 0
    MSumCost2 = 0
    for i in Fixture:
        sumcost = 0
        sumload1 = 0
        sumload2 = 0
        sumrate = 0
        for t in T: sumload1 += Fixtload[i,t].x
        if sumload1 >= 0.001:
            j += 1
            ws10.write(j,1,FixtId[i])
            maxload = 0
            for t in T:
                if Fixtload[i,t].x > eps:
                    ws10.write(j,1+t,Fixtload[i,t].x)
                    Loadrate = Fixtload[i,t].x/FixtCap[i]
                    sumrate += Loadrate
                    if Loadrate > maxload: maxload = Loadrate
            ws10.write(j,2+nperiod,maxload*100)
            ws10.write(j,3+nperiod,100*sumrate/nperiod)
            ws10.write(j,4+nperiod,sumload1*FixtCost[i])
            MSumCost1 += sumload1*FixtCost[i]
            for t in T:
                if FixtPlus[i,t].x > eps:
                    ws10.write(j,5+nperiod+t,FixtPlus[i,t].x)
                    sumload2 += FixtPlus[i,t].x
                if intager == 0: ws10.write(j,7+2*nperiod+t,Fixtdual[i,t])
            MSumCost2 += sumload2*FixtCost[i]*Fovcost[i]
            ws10.write(j,6+2*nperiod,sumload2*FixtCost[i]*Fovcost[i])
    
    ws10.write(j+1,3+nperiod,'成本合计')
    ws10.write(j+1,4+nperiod,MSumCost1)
    ws10.write(j+1,5+2*nperiod,'成本合计')
    ws10.write(j+1,6+2*nperiod,MSumCost2)

# =============================================================================
# Sheet 13: 替代物料表
# =============================================================================

if len(SubstiNo) != 0:
    ws13 = w.add_sheet('替代物料')
    ws13.write(0,1,'替代关系',styleBold)
    ws13.write(0,4,'替代数量',styleBold)
    ws13.write(1,1,'替代物料类型',styleBold)
    ws13.write(1,2,'替代物料一',styleBold)
    ws13.write(1,3,'替代物料二',styleBold)
    for t in T:
        ws13.write(1,3+t,t,styleBold)
    j = 1
    for i in SubstiNo:
        sumtotal = 0
        for t in T: sumtotal += Substi[i,t].x
        if sumtotal > 0.001:
            j = j+1
            ws13.write(j,1,SubType[i])
            ws13.write(j,2,SubCode1[i])
            ws13.write(j,3,SubCode2[i])
            for t in T:
                if Substi[i,t].x > eps:
                    ws13.write(j,3+t,Substi[i,t].x)
                            

# =============================================================================
# Sheet 12: 综合表
# =============================================================================

sumcost0 = 0
ws12 = w.add_sheet('综合')
ws12.write(1,1,'销售收入',styleBold)
ws12.write(1,2,SumIncome)

ws12.write(2,1,'延期成本',styleBold)
ws12.write(2,2,SumDlyFine)

ws12.write(3,1,'制造成本',styleBold)
ws12.write(3,2,ProSumCost1+ProSumCost2)

ws12.write(4,1,'外协采购成本',styleBold)
ws12.write(4,2,OutsumCost)

ws12.write(5,1,'原料采购成本',styleBold)
ws12.write(5,2,RawsumCost)

ws12.write(6,1,'库存成本',styleBold)
ws12.write(6,2,TotalCost)

ws12.write(7,1,'不可行成本',styleBold)
ws12.write(7,2,sumfine)

if nfixtable == 1:
    ws12.write(8,1,'模具成本',styleBold)
    ws12.write(8,2,MSumCost1+MSumCost2)
    sumcost0 += MSumCost1 + MSumCost2
    
Profit = SumIncome-SumDlyFine-ProSumCost1-ProSumCost2-OutsumCost-RawsumCost-TotalCost-sumcost0-sumfine

ws12.write(10,1,'利润合计',styleBold)
ws12.write(10,2,Profit)

## 订单交付汇总
j = 12
ws12.write(j,1,'订单交付汇总',styleBold)
ws12.write(j,4,'订单交付单数',styleBold)
ws12.write(j,10,'订单交付数量',styleBold)
j += 1
ws12.write(j,1,'订单等级',styleBold)
ws12.write(j,2,'订单总数',styleBold)
ws12.write(j,3,'按期交付',styleBold)
ws12.write(j,4,'部分按期',styleBold)
ws12.write(j,5,'延期交付',styleBold)
ws12.write(j,6,'未交付',styleBold)
           
ws12.write(j,8,'订单总量',styleBold)
ws12.write(j,9,'按期交付量',styleBold)
ws12.write(j,10,'部分按期量',styleBold)
ws12.write(j,11,'延期交付量',styleBold)
ws12.write(j,12,'未交付量',styleBold)
           
sumdel = {}
for k1 in range(1,6):
    sumdel[k1,1] = 0
    sumdel[k1,2] = 0
for k1 in range(1,nordclass+1):
    j += 1
    aa = '订单等级 ' + str(k1)
    ws12.write(j,1,aa,styleBold)
    for k2 in range(1,6):
        ws12.write(j,1+k2,Ordeliv[k1,1,k2])
        ws12.write(j,7+k2,Ordeliv[k1,2,k2])
        sumdel[k2,1] += Ordeliv[k1,1,k2]
        sumdel[k2,2] += Ordeliv[k1,2,k2]
j += 1
ws12.write(j,1,'合计',styleBold)
for k in range(1,6):
    ws12.write(j,1+k,sumdel[k,1])
    ws12.write(j,7+k,sumdel[k,2])
j += 1
ws12.write(j,1,'占比（%）',styleBold)
to1 = sumdel[1,1]
to2 = sumdel[1,2]
for k in range(2,6):
    if to1 > 0.01:
        ws12.write(j,1+k,100*sumdel[k,1]/to1)
    if to2 > 0.01:
        ws12.write(j,7+k,100*sumdel[k,2]/to2)



w.save(savepath+resultFileName)


## =============================================================================
## 求解结果写入数据库（res_* 变量表，长格式 3NF，仅非零值 eps=1e-4）
## 表/视图结构与计算口径见 docs/排产结果数据库设计.md
## DDL 见 scripts/db_tools/create_result_tables.sql
## =============================================================================
def writeResultsToDB():
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        ## ---- 步骤 1: 写入求解版本记录，获取 run_id ----
        try:
            objval = msingle.ObjVal                                   # 目标函数值（利润）
        except Exception:
            objval = None
        try:
            mipgap = msingle.MIPGap                                   # MIPGap
        except Exception:
            mipgap = None
        status_names = {1:'LOADED', 2:'OPTIMAL', 3:'INFEASIBLE', 4:'INF_OR_UNBD',
                        5:'UNBOUNDED', 6:'CUTOFF', 7:'ITERATION_LIMIT', 8:'NODE_LIMIT',
                        9:'TIME_LIMIT', 10:'SOLUTION_LIMIT', 11:'INTERRUPTED',
                        12:'NUMERIC', 13:'SUBOPTIMAL', 14:'INPROGRESS', 15:'USER_OBJ_LIMIT'}
        try:
            run_status = status_names.get(msingle.Status, str(msingle.Status))
        except Exception:
            run_status = None
        cur.execute(
            '''INSERT INTO res_solve_run
               (run_time, objective, mip_gap, solve_time_ms, status, nperiod, intager,
                nfixtable, nouttable, nrawlimtable, nsubtable, nwiptable)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), objval, mipgap,
             round(time.time()*1000 - startime), run_status,
             nperiod, intager, nfixtable, nouttable, nrawlimtable, nsubtable, nwiptable))
        run_id = cur.lastrowid

        ## ---- 步骤 2: 批量写入变量表（仅非零值，eps=1e-4）----

        # 2.1 生产变量：Prodmade / Selfmade（变量仅在 t > 提前期 时存在）
        cur.executemany('INSERT INTO res_prod_made VALUES (?,?,?,?,?)',
            [(run_id, ProdCode[i], j, t, v.x) for (i,j,t), v in Prodmade.items() if v.x > eps])
        cur.executemany('INSERT INTO res_self_made VALUES (?,?,?,?,?)',
            [(run_id, SelfCode[i], j, t, v.x) for (i,j,t), v in Selfmade.items() if v.x > eps])

        # 2.2 订单交付/延期（变量仅在 交期~交期+允许延期 且 t<=nperiod 时存在；order_id 用订单号）
        cur.executemany('INSERT INTO res_order_sale VALUES (?,?,?,?)',
            [(run_id, OrdNo[i], t, v.x) for (i,t), v in OrdSale.items() if v.x > eps])
        cur.executemany('INSERT INTO res_order_delay VALUES (?,?,?,?)',
            [(run_id, OrdNo[i], t, v.x) for (i,t), v in OrdDelay.items() if v.x > eps])

        # 2.3 库存变量（t ∈ 0..nperiod，0 期为期初库存）
        cur.executemany('INSERT INTO res_prod_inv VALUES (?,?,?,?)',
            [(run_id, ProdCode[i], t, v.x) for (i,t), v in ProdInv.items() if v.x > eps])
        cur.executemany('INSERT INTO res_self_inv VALUES (?,?,?,?)',
            [(run_id, SelfCode[i], t, v.x) for (i,t), v in SelfInv.items() if v.x > eps])
        cur.executemany('INSERT INTO res_raw_inv VALUES (?,?,?,?)',
            [(run_id, RawCode[i], t, v.x) for (i,t), v in RawInv.items() if v.x > eps])

        # 2.4 采购/外协（外协变量仅在 nouttable=1 时存在）
        cur.executemany('INSERT INTO res_purchase VALUES (?,?,?,?)',
            [(run_id, RawCode[i], t, v.x) for (i,t), v in Purchase.items() if v.x > eps])
        if nouttable == 1:
            cur.executemany('INSERT INTO res_outsource VALUES (?,?,?,?)',
                [(run_id, OutsCode[i], t, v.x) for (i,t), v in OutSourc.items() if v.x > eps])

        # 2.5 设备/工装负荷（工装变量仅在 nfixtable=1 时存在）
        cur.executemany('INSERT INTO res_workload VALUES (?,?,?,?)',
            [(run_id, EquipId[i], t, v.x) for (i,t), v in Workload.items() if v.x > eps])
        cur.executemany('INSERT INTO res_overload VALUES (?,?,?,?)',
            [(run_id, EquipId[i], t, v.x) for (i,t), v in Overload.items() if v.x > eps])
        if nfixtable == 1:
            cur.executemany('INSERT INTO res_fixtload VALUES (?,?,?,?)',
                [(run_id, FixtId[i], t, v.x) for (i,t), v in Fixtload.items() if v.x > eps])
            cur.executemany('INSERT INTO res_fixt_plus VALUES (?,?,?,?)',
                [(run_id, FixtId[i], t, v.x) for (i,t), v in FixtPlus.items() if v.x > eps])

        # 2.6 替代量（替代变量仅在替代关系表存在时定义）
        if len(SubstiNo) != 0:
            cur.executemany('INSERT INTO res_substi VALUES (?,?,?,?)',
                [(run_id, i, t, v.x) for (i,t), v in Substi.items() if v.x > eps])

        # 2.7 不可行松弛量（6 类全部入库；Excel「不可行」Sheet 仅展示其中 3 类）
        inf_rows = []
        for (i,t), v in ProdInf.items():
            if v.x > eps:  inf_rows.append((run_id, 'PRODUCT', ProdCode[i], t, v.x))
        for (i,t), v in SelfInf.items():
            if v.x > eps:  inf_rows.append((run_id, 'SELF', SelfCode[i], t, v.x))
        for (i,t), v in RawInf.items():
            if v.x > eps:  inf_rows.append((run_id, 'RAW', RawCode[i], t, v.x))
        for (i,t), v in EquipInf.items():
            if v.x > eps:  inf_rows.append((run_id, 'EQUIP', EquipId[i], t, v.x))
        for (i,t), v in FixtInf.items():
            if v.x > eps:  inf_rows.append((run_id, 'FIXT', FixtId[i], t, v.x))
        for (i,t), v in SaleInf.items():
            if v.x > eps:  inf_rows.append((run_id, 'SALE', OrdNo[i], t, v.x))
        cur.executemany('INSERT INTO res_infeasible VALUES (?,?,?,?,?)', inf_rows)

        # 2.8 对偶解/影子价格（仅连续松弛 intager=0 时有意义）
        if intager == 0:
            cur.executemany('INSERT INTO res_dual_prod VALUES (?,?,?,?)',
                [(run_id, ProdCode[i], t, v) for (i,t), v in Proddual.items()])
            cur.executemany('INSERT INTO res_dual_self VALUES (?,?,?,?)',
                [(run_id, SelfCode[i], t, v) for (i,t), v in Self1dual.items()])
            cur.executemany('INSERT INTO res_dual_raw VALUES (?,?,?,?)',
                [(run_id, RawCode[i], t, v) for (i,t), v in Rawdual.items()])
            cur.executemany('INSERT INTO res_dual_equip VALUES (?,?,?,?)',
                [(run_id, EquipId[i], t, v) for (i,t), v in Equipdual.items()])
            if nfixtable == 1:
                # 工装影子价格仅写有负荷的工装（对齐 Excel L1941，影子价格块只在负荷行内输出）
                fixt_loaded = {i for i in Fixture if sum(Fixtload[i,t].x for t in T) > 0.0001}
                cur.executemany('INSERT INTO res_dual_fixt VALUES (?,?,?,?)',
                    [(run_id, FixtId[i], t, Fixtdual[i,t]) for i in fixt_loaded for t in T])

        # 2.9 加工计划（对齐 Excel Sheet 7「加工计划」逻辑，L1654-1806）：
        #     产品：加工数量存完工期；占用能力按 ProMaxT 向前摊铺（仅写 t>产品提前期 的期，L1711）
        #     自制品：加工数量与占用能力均摊铺到开工期（t-ProMaxT+it）；多个完工期摊铺到
        #             同一开工期时累加（Excel 单元格为覆盖写，DB 取累计口径）
        #     在制品：is_wip=1、route_id='wip'，完工期 = it - 已完成阶段
        # 键中的 opc 为工序代码 ProOper[k]（同设备同生产线的多道工序各占一行，对齐 Excel 行数），
        # 生产线 ProState[k] 仅作为 production_line 列存储（Excel「工序代码」列口径）
        mach = {}
        def mach_add(resc, opc, mc, rid, period, prod=None, cap=None, fcode=None, fqunt=None, pline=None):
            key = (resc, opc, mc, str(rid), int(period))
            rec = mach.get(key)
            if rec is None:
                rec = mach[key] = [0.0, 0.0, fcode, fqunt, pline]
            else:
                if rec[2] is None and fcode is not None: rec[2] = fcode
                if rec[3] is None and fqunt is not None: rec[3] = fqunt
                if rec[4] is None and pline is not None: rec[4] = pline
            if prod is not None: rec[0] += prod
            if cap  is not None: rec[1] += cap

        for i in Equip:
            for k in Routing:
                if EquipId[i] != ProEquip[k]:
                    continue
                ml    = ProMult[k]
                mcode = ProMat[k]
                fcode = ProFixt[k] if (nfixtable == 1 and ProFixt[k] not in ('', None)) else None
                fqunt = ProFixq[k] if (nfixtable == 1 and ProFixt[k] not in ('', None)) else None
                if mcode in Prodset:
                    ip = Prodidx[mcode]
                    sump = sum(Prodmade[ip,ml,t].x for t in T if t > ProdLT[ip])
                    if sump > 0.0001:
                        sumcap = {t: 0.0 for t in T}
                        for t in T:
                            if t > ProdLT[ip]:
                                aa = Prodmade[ip,ml,t].x
                                if aa > 0.0001:
                                    mach_add(EquipId[i], ProOper[k], mcode, ml, t, prod=aa,
                                             fcode=fcode, fqunt=fqunt, pline=ProState[k])
                                    if ProMaxT[k] > 1:
                                        for it in range(1, ProMaxT[k]+1):
                                            if t-it+1 >= 1:
                                                sumcap[t-it+1] += aa*Protime[k,ProMaxT[k]-it+1]
                                    else:
                                        sumcap[t] += aa*Protime[k,1]
                        for t in T:
                            if t > ProdLT[ip] and sumcap[t] > 0.0001:
                                mach_add(EquipId[i], ProOper[k], mcode, ml, t, cap=sumcap[t],
                                         fcode=fcode, fqunt=fqunt, pline=ProState[k])
                elif mcode in Selfset:
                    ip = Selfidx[mcode]
                    sump = sum(Selfmade[ip,ml,t].x for t in T if t > SelfLT[ip])
                    if sump > 0.00001:
                        for t in T:
                            if t > SelfLT[ip]:
                                aa = Selfmade[ip,ml,t].x
                                if aa > 0.0001:
                                    if ProMaxT[k] > 1:
                                        for it in range(1, ProMaxT[k]+1):
                                            if t-it+1 >= 1 and Protime[k,it] > 0.0001:
                                                mach_add(EquipId[i], ProOper[k], mcode, ml,
                                                         t-ProMaxT[k]+it, prod=aa,
                                                         cap=aa*Protime[k,it],
                                                         fcode=fcode, fqunt=fqunt, pline=ProState[k])
                                    else:
                                        mach_add(EquipId[i], ProOper[k], mcode, ml, t, prod=aa,
                                                 cap=aa*Protime[k,1], fcode=fcode, fqunt=fqunt,
                                                 pline=ProState[k])
                    # 在制品行（与 Excel 一致：不依赖该物料是否有新增产量）
                    if nwiptable == 1:
                        for iw in WipNo:
                            if WipCode[iw] == mcode:
                                wipsum = sum(WipQunt[iw]*Protime[k,it]
                                             for it in range(WipStage[iw]+1, ProMaxT[k]+1))
                                if wipsum > 0.0001:
                                    for it in range(WipStage[iw]+1, ProMaxT[k]+1):
                                        if Protime[k,it] > 0.0001:
                                            mach_add(EquipId[i], ProOper[k], mcode, 'wip',
                                                     it-WipStage[iw], prod=WipQunt[iw],
                                                     cap=WipQunt[iw]*Protime[k,it],
                                                     fcode=fcode, fqunt=fqunt, pline=ProState[k])
        cur.executemany('INSERT INTO res_machining_plan VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            [(run_id, key[0], key[1], rec[4], key[2], key[3], rec[2], rec[3], key[4],
              rec[0] if rec[0] > 0 else None,
              rec[1] if rec[1] > 0 else None,
              1 if key[3] == 'wip' else 0)
             for key, rec in mach.items()])

        # 2.10 汇总表 + 订单交付汇总（口径与 Excel 综合表完全一致，直接复用其聚合值）
        cur.execute('INSERT INTO res_summary VALUES (?,?,?,?,?,?,?,?,?,?)',
            (run_id, SumIncome, SumDlyFine, ProSumCost1+ProSumCost2, OutsumCost,
             RawsumCost, TotalCost, (MSumCost1+MSumCost2) if nfixtable == 1 else 0,
             sumfine, Profit))
        cur.executemany('INSERT INTO res_order_delivery VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            [(run_id, k1,
              Ordeliv[k1,1,1], Ordeliv[k1,1,2], Ordeliv[k1,1,3], Ordeliv[k1,1,4], Ordeliv[k1,1,5],
              Ordeliv[k1,2,1], Ordeliv[k1,2,2], Ordeliv[k1,2,3], Ordeliv[k1,2,4], Ordeliv[k1,2,5])
             for k1 in range(1, nordclass+1)])

        conn.commit()
        print('\n求解结果已写入数据库: %s (run_id=%d)' % (DB_PATH, run_id))
    finally:
        conn.close()

writeResultsToDB()

startime1 = time.time()*1000
runtime = (int(startime1) - int(startime))/1000
print('\n模型求解需要的全部时间:        ', runtime)

w.save(savepath+resultFileName)
