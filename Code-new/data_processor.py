import xlrd

def readCell(cellName, book, toInt = False):
    cellName = cellName.lower()
    Name = book.name_map[cellName][0]
    val = Name.cell().value
    if toInt:
      val = int(val)
    result = val
    return(result)

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

def load_and_preprocess(filepath):
    book = xlrd.open_workbook(filepath)

    #  读综合表信息    
    nfixtable    = readCell('nfixtable', book, True)                            # 工装表是否存在标识
    nouttable    = readCell('nouttable', book,True)                             # 外协表是否存在标识
    nrawlimtable = readCell('nrawlimtable', book, True)                         # 采购限制表是否存在标识
    nsubtable    = readCell('nsubtable', book, True)                            # 替代关系表是否存在标识
    nwiptable    = readCell('nwiptable', book, True)                            # 自制品表是否存在标识

    nperiod   = readCell('nperiod', book, True)                              # 计划期长度（周期数）
    nbom0     = readCell('nbom', book, True)                                 # BOM表记录数
    nrouting  = readCell('nrouting', book, True)                             # 工艺路线表记录数  
    nequip    = readCell('nequip', book, True)                               # 设备种类数
    nproduct  = readCell('nproduct', book, True)                             # 产品种类数 
    nselfmade = readCell('nselfmade', book, True)                            # 自制件种类数
    nrawmat   = readCell('nrawmat', book, True)                              # 原材料种类数
    dutytime  = readCell('dutytime', book, True)                             # 每班次时长
    dayshift  = readCell('dayshift', book, True)                             # 每周期班次数
    npmaxt    = readCell('npmaxt', book, True)                               # 最大加工跨周期数 
    norder    = readCell('norder', book, True)                               # 订单数
    nordelay  = readCell('nordelay', book, True)                             # 订单最大允许延期周期数
    nordclass = readCell('nordclass', book, True)                            # 订单等级数
    nfixture  = readCell('nfixture', book, True)                             # 工装种类数（设备 1 的辅助装备） 
    ndemrate  = readCell('ndemrate', book)                                   # 需求率
    intager = 0                                                              # 整数规划表示：0 - 线性规划，1-整数规划

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
    Fcode0  = readTable('Fcode', book)                                       # 父物料代码
    Scode0  = readTable('Scode', book)                                       # 子物料代码 
    Quant0  = readTable('Quant', book)                                       # 父物料消耗子物料的数量关系
    Blevel0 = readTable('BomLevel', book, True)                              # BOM层级 

    ## 读产品表  ################################################
    ProdCode = readTable('ProdCode',book)                                   # 产品代码
    ProdCost = readTable('ProdCost',book)                                   # 产品生产成本
    Price    = readTable('Price',book)                                      # 产品销售价格
    ProdLT   = readTable('ProdLeadtime',book, True)                         # 产品生产提前期
    ProdInv0 = readTable('ProdInv0',book)                                   # 产品期初库存
    ProdInvT = readTable('ProdInvT',book)                                   # 产品期末库存
    ProdInvL = readTable('ProdInvL',book)                                   # 产品最低库存
    ProdInvU = readTable('ProdInvU',book)                                   # 产品最高库存
    ProdInvCost = readTable('ProdInvCost',book)                             # 产品库存成本

    ## 读自制件表  ###############################################
    SelfCode = readTable('SelfCode',book)
    SelfDummy= readTable('SelfDummy',book)
    SelfInv0 = readTable('SelfInv0',book)
    SelfInvT = readTable('SelfInvT',book)
    SelfInvL = readTable('SelfInvL',book)
    SelfInvU = readTable('SelfInvU',book)
    SelfInvCost = readTable('SelfInvCost',book)
    SelfLT   = readTable('SelfLeadtime',book, True)

    ## 读工艺路线表  #############################################
    ProMat   = readTable('ProMat', book)                                    # 工艺中被加工物料代码
    ProMult  = readTable('ProMult', book, True)                             # 多工艺路线标示序数
    ProEquip = readTable('ProEquip', book)                                  # 工艺加工设备
    ProState = readTable('ProState', book)                                  # 工艺加工工序
    if nfixtable == 1:
        ProFixt  = readTable('ProFixt', book)                                   # 工艺加工辅助工装代码
        ProFixq  = readTable('ProFixq', book)                                   # 工艺加工工装使用数量
    ProMaxT  = readTable('ProMaxT', book, True)                             # 工艺加工跨周期数
    ProHour  = readTable('ProHour', book)                                   # 工艺加工时间
    Protime = {}
    for p in Routing:
        if npmaxt > 1:                                                      ## ！！！！！！ 这里修改过
            for t in range(1,npmaxt+1):
                Protime[p,t] = ProHour[p][t-1]
        else:
            Protime[p,1] = ProHour[p]

    ## 读设备表  ################################################
    EquipId    = readTable('EquipId', book)                                 # 设备代码
    EquipCost  = readTable('EquipCost', book)                               # 设备单位时间加工成本
    EquipNumb  = readTable('EquipNumb', book, True)                         # 设备台数
    EquipRate  = readTable('EquipRate', book)                               # 设备平均有效时间利用率
    EquipOverT = readTable('EquipOverT', book)                              # 设备允许加班时间与正常工作时间比值
    EquipOverR = readTable('EquipOverR', book)                              # 设备加班成本与正常单位时间成本比值

    ## 读工装表  ################################################
    if nfixtable == 1:
        FixtNo   = readTable('FixtNo',book, True)
        FixtId   = readTable('FixtId',book)
        FixtCost = readTable('FixtCost',book)
        FixtQunt = readTable('FixtQunt',book)
        FixtRate = readTable('FixtRate',book)
        FixtOver = readTable('FixtOver',book)
        Fovcost  = readTable('Fovcost',book)
    else:
        FixtNo = {}

    ## 读订单表  ################################################
    OrdNo    = readTable('OrdNo', book, True)                               # 订单号
    OrdCls   = readTable('OrdCls', book)                                    # 订单等级 
    OrdProd  = readTable('OrdProd', book)                                   # 订单产品
    OrdPrice = readTable('OrdPrice', book)                                  # 订单销售价格
    OrdQunt  = readTable('OrdQunt', book)                                   # 订单数量
    OrdTime  = readTable('OrdTime', book, True)                             # 订单交期
    OrdDly   = readTable('OrdDly', book, True)                              # 订单允许延期交付的延期周期数
    OrdFine  = readTable('OrdFine', book)                                   # 订单延期交付每延期一周期需交付的罚金数

    ## 读外协表  ################################################
    if nouttable == 1:
        OutsNo   = readTable('OutsNo',book, True)
        OutsCode = readTable('OutsCode',book)
        OutsCost = readTable('OutsCost',book)
        OutsQunt = readTable('OutsQunt',book)
        OutSQ = {}
        for i in OutsNo:
            for t in T:
                OutSQ[(i,t)] = OutsQunt[i][t-1]
    else:
        OutsNo = {}

    ## 读原料表  ###############################################
    RawCode = readTable('RawCode',book)
    RawCost = readTable('RawCost',book)
    RawInv0 = readTable('RawInv0',book)
    RawInvT = readTable('RawInvT',book)
    RawInvL = readTable('RawInvL',book)
    RawInvU = readTable('RawInvU',book)
    RawInvCost = readTable('RawInvCost',book)
    RawLT   = readTable('RawLeadtime',book)

    ## 读采购限制表  ###########################################
    if nrawlimtable == 1:
        RlimNo  = readTable('RlimNo',book, True)
        RlimId  = readTable('RlimId',book)
        RlimQnt = readTable('RlimQunt',book)
        RawlimQ = {}
        for i in RlimNo:
            for t in T:
                RawlimQ[(i,t)] = RlimQnt[i][t-1]
    else:
        RlimNo = {}

    ## 读替代关系表  ###########################################
    if nsubtable == 1:
        SubstiNo   = readTable('SubstiNo',book)
        SubType    = readTable('SubType',book)
        SubCode1   = readTable('SubCode1',book)
        SubCode2   = readTable('SubCode2',book)
        SubQunt1   = readTable('SubQunt1',book)
        SubQunt2   = readTable('SubQunt2',book)
        Sublimit   = readTable('Sublimit',book)
        SubRatio   = readTable('SubRatio',book)
        SubBatch   = readTable('SubBatch',book)
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
        WipNo    = readTable('WipNo',book, True)
        WipCode    = readTable('WipCode',book)
        WipMaxT    = readTable('WipMaxT',book, True)
        WipStage   = readTable('WipStage',book, True)
        WipQunt    = readTable('WipQunt',book)
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
    else:
        FixtCap = {}

    penalty = 1e6

    data = {
        'nfixtable': nfixtable,
        'nouttable': nouttable,
        'nrawlimtable': nrawlimtable,
        'nsubtable': nsubtable,
        'nwiptable': nwiptable,
        'nperiod': nperiod,
        'nbom0': nbom0,
        'nrouting': nrouting,
        'nequip': nequip,
        'nproduct': nproduct,
        'nselfmade': nselfmade,
        'nrawmat': nrawmat,
        'dutytime': dutytime,
        'dayshift': dayshift,
        'npmaxt': npmaxt,
        'norder': norder,
        'nordelay': nordelay,
        'nordclass': nordclass,
        'nfixture': nfixture,
        'ndemrate': ndemrate,
        'intager': intager,
        'T': T,
        'T0': T0,
        'BOM0': BOM0,
        'BOMs': BOMs,
        'Routing': Routing,
        'Product': Product,
        'Self': Self,
        'Raw': Raw,
        'Equip': Equip,
        'Order': Order,
        'Fixture': Fixture,
        'Fcode': Fcode,
        'Scode': Scode,
        'Quant': Quant,
        'Blevel': Blevel,
        'ProdCode': ProdCode,
        'ProdCost': ProdCost,
        'Price': Price,
        'ProdLT': ProdLT,
        'ProdInv0': ProdInv0,
        'ProdInvT': ProdInvT,
        'ProdInvL': ProdInvL,
        'ProdInvU': ProdInvU,
        'ProdInvCost': ProdInvCost,
        'SelfCode': SelfCode,
        'SelfDummy': SelfDummy,
        'SelfInv0': SelfInv0,
        'SelfInvT': SelfInvT,
        'SelfInvL': SelfInvL,
        'SelfInvU': SelfInvU,
        'SelfInvCost': SelfInvCost,
        'SelfLT': SelfLT,
        'ProMat': ProMat,
        'ProMult': ProMult,
        'ProEquip': ProEquip,
        'ProState': ProState,
        'ProFixt': ProFixt if nfixtable == 1 else {},
        'ProFixq': ProFixq if nfixtable == 1 else {},
        'ProMaxT': ProMaxT,
        'Protime': Protime,
        'EquipId': EquipId,
        'EquipCost': EquipCost,
        'EquipNumb': EquipNumb,
        'EquipRate': EquipRate,
        'EquipOverT': EquipOverT,
        'EquipOverR': EquipOverR,
        'FixtNo': FixtNo,
        'FixtId': FixtId if nfixtable == 1 else {},
        'FixtCost': FixtCost if nfixtable == 1 else {},
        'FixtQunt': FixtQunt if nfixtable == 1 else {},
        'FixtRate': FixtRate if nfixtable == 1 else {},
        'FixtOver': FixtOver if nfixtable == 1 else {},
        'Fovcost': Fovcost if nfixtable == 1 else {},
        'OrdNo': OrdNo,
        'OrdCls': OrdCls,
        'OrdProd': OrdProd,
        'OrdPrice': OrdPrice,
        'OrdQunt': OrdQunt,
        'OrdTime': OrdTime,
        'OrdDly': OrdDly,
        'OrdFine': OrdFine,
        'OutsNo': OutsNo,
        'OutsCode': OutsCode if nouttable == 1 else {},
        'OutsCost': OutsCost if nouttable == 1 else {},
        'OutSQ': OutSQ if nouttable == 1 else {},
        'RawCode': RawCode,
        'RawCost': RawCost,
        'RawInv0': RawInv0,
        'RawInvT': RawInvT,
        'RawInvL': RawInvL,
        'RawInvU': RawInvU,
        'RawInvCost': RawInvCost,
        'RawLT': RawLT,
        'RlimNo': RlimNo,
        'RlimId': RlimId if nrawlimtable == 1 else {},
        'RawlimQ': RawlimQ if nrawlimtable == 1 else {},
        'SubstiNo': SubstiNo,
        'SubType': SubType if nsubtable == 1 else {},
        'SubCode1': SubCode1 if nsubtable == 1 else {},
        'SubCode2': SubCode2 if nsubtable == 1 else {},
        'SubQunt1': SubQunt1 if nsubtable == 1 else {},
        'SubQunt2': SubQunt2 if nsubtable == 1 else {},
        'SubRatio': SubRatio if nsubtable == 1 else {},
        'SubBatch': SubBatch if nsubtable == 1 else {},
        'SubLimit': SubLimit if nsubtable == 1 else {},
        'WipLoad': WipLoad,
        'WipNo': WipNo,
        'WipCode': WipCode if nwiptable == 1 else {},
        'WipMaxT': WipMaxT if nwiptable == 1 else {},
        'WipStage': WipStage if nwiptable == 1 else {},
        'WipQunt': WipQunt if nwiptable == 1 else {},
        'Prodset': Prodset,
        'Prodidx': Prodidx,
        'Selfset': Selfset,
        'Selfidx': Selfidx,
        'Rawset': Rawset,
        'Rawidx': Rawidx,
        'Equipidx': Equipidx,
        'Fixtidx': Fixtidx if nfixtable == 1 else {},
        'nppro': nppro,
        'nspro': nspro,
        'FbP': FbP,
        'FbS': FbS,
        'RbP': RbP,
        'RbS': RbS,
        'PeP': PeP,
        'PeS': PeS,
        'MdP': MdP if nfixtable == 1 else {},
        'MdS': MdS if nfixtable == 1 else {},
        'EquipCap': EquipCap,
        'FixtCap': FixtCap,
        'penalty': penalty
    }

    return data
