from xlwt import *
import time

def output_results(model_vars, model_constrs, data, msingle, intager, startime, savepath, resultFileName):
    nfixtable    = data['nfixtable']
    nouttable    = data['nouttable']
    nperiod      = data['nperiod']
    nproduct     = data['nproduct']
    nselfmade    = data['nselfmade']
    nrawmat      = data['nrawmat']
    nequip       = data['nequip']
    nfixture     = data['nfixture']
    nordclass    = data['nordclass']
    nwiptable    = data['nwiptable']
    
    T        = data['T']
    T0       = data['T0']
    Routing  = data['Routing']
    Product  = data['Product']
    Self     = data['Self']
    Raw      = data['Raw']
    Equip    = data['Equip']
    Order    = data['Order']
    Fixture  = data['Fixture']
    
    ProdCode     = data['ProdCode']
    ProdLT       = data['ProdLT']
    ProdInvCost  = data['ProdInvCost']
    
    SelfCode     = data['SelfCode']
    SelfInvCost  = data['SelfInvCost']
    SelfLT       = data['SelfLT']
    
    ProMat    = data['ProMat']
    ProMult   = data['ProMult']
    ProEquip  = data['ProEquip']
    ProState  = data['ProState']
    ProFixt   = data['ProFixt']
    ProFixq   = data['ProFixq']
    ProMaxT   = data['ProMaxT']
    Protime   = data['Protime']
    
    EquipId     = data['EquipId']
    EquipCost   = data['EquipCost']
    EquipOverR  = data['EquipOverR']
    
    FixtCost = data['FixtCost']
    FixtId   = data['FixtId']
    Fovcost  = data['Fovcost']
    
    OrdNo    = data['OrdNo']
    OrdCls   = data['OrdCls']
    OrdProd  = data['OrdProd']
    OrdPrice = data['OrdPrice']
    OrdQunt  = data['OrdQunt']
    OrdTime  = data['OrdTime']
    OrdDly   = data['OrdDly']
    OrdFine  = data['OrdFine']
    
    OutsNo   = data['OutsNo']
    OutsCode = data['OutsCode']
    OutsCost = data['OutsCost']
    
    RawCode     = data['RawCode']
    RawCost     = data['RawCost']
    RawInvCost  = data['RawInvCost']
    
    SubstiNo   = data['SubstiNo']
    SubType    = data['SubType']
    SubCode1   = data['SubCode1']
    SubCode2   = data['SubCode2']
    
    WipNo    = data['WipNo']
    WipCode  = data['WipCode']
    WipMaxT  = data['WipMaxT']
    WipStage = data['WipStage']
    WipQunt  = data['WipQunt']
    
    Prodset  = data['Prodset']
    Prodidx  = data['Prodidx']
    Selfset  = data['Selfset']
    Selfidx  = data['Selfidx']
    
    nppro = data['nppro']
    nspro = data['nspro']
    
    EquipCap = data['EquipCap']
    FixtCap  = data['FixtCap']
    penalty  = data['penalty']

    Prodmade   = model_vars['Prodmade']
    Selfmade   = model_vars['Selfmade']
    ProdInv    = model_vars['ProdInv']
    SelfInv    = model_vars['SelfInv']
    RawInv     = model_vars['RawInv']
    Purchase   = model_vars['Purchase']
    Workload   = model_vars['Workload']
    Overload   = model_vars['Overload']
    Fixtload   = model_vars['Fixtload']
    FixtPlus   = model_vars['FixtPlus']
    OrdSale    = model_vars['OrdSale']
    OrdDelay   = model_vars['OrdDelay']
    OutSourc   = model_vars['OutSourc']
    Substi     = model_vars['Substi']
    SaleInf    = model_vars['SaleInf']
    EquipInf   = model_vars['EquipInf']
    FixtInf    = model_vars['FixtInf']
    ProdInf    = model_vars['ProdInf']
    SelfInf    = model_vars['SelfInf']
    RawInf     = model_vars['RawInf']
    
    SaleBal    = model_constrs['SaleBal']
    ProdBal    = model_constrs['ProdBal']
    Self1Bal   = model_constrs['Self1Bal']
    RawBal     = model_constrs['RawBal']
    CapBal     = model_constrs['CapBal']
    FixtBal    = model_constrs['FixtBal']

    if intager == 0:
        Proddual  = {}
        for i in Product:
            for t in T:
                Proddual[i,t] = -ProdBal[i,t].Pi        
        Self1dual = {}
        for i in Self:
            for t in T:
                Self1dual[i,t] = -Self1Bal[i,t].Pi         
        Rawdual   = {}
        for i in Raw:
            if RawCode[i] not in Selfset:
                for t in T:
                    Rawdual[i,t]  = -RawBal[i,t].Pi
        Equipdual   = {}
        for i in Equip:
            for t in T:
                Equipdual[i,t] = CapBal[i,t].Pi
        if nfixtable == 1:
            Fixtdual  = {}
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
        for k1 in range(1,3):
            for k2 in range(1,6):
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
                            Ordeliv[icls,2,4] += OrdSale[i,t].x
                            dlyfine = OrdSale[i,t].x*OrdFine[i]*(t-OrdTime[i])
                            if OrdQunt[i]-OrdSale[i,t].x-OrdDelay[i,t].x < 0.0001:
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

    j += 2
    ws2.write(j,1,'产品销售计划',styleBold)
    j += 1
    ws2.write(j,1,'产品代码',styleBold)

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

    ws6 = w.add_sheet('设备负荷')
    ws6.write(1,1,'正常负荷分布',styleBold)
    ws6.write(2,1,'设备号',styleBold)
    ws6.write(2,2,'设备能力',styleBold)

    for t in T:
        ws6.write(2,2+t,t,styleBold)
    ws6.write(2,3+nperiod,'最大负荷率 %',styleBold)
    ws6.write(2,4+nperiod,'平均负荷率 %',styleBold)
    ws6.write(2,5+nperiod,'正常成本小计',styleBold)

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
                            if t > SelfLT[ip]:
                                aa = Selfmade[ip,ml,t].x
                                if aa > 0.0001:
                                    if ProMaxT[k] > 1:
                                        for it in range(1,ProMaxT[k]+1):
                                            if t-it+1 >= 1:
                                                if Protime[k,it] > 0.0001:
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
                
                    if nwiptable == 1:
                        for iw in WipNo:
                            if WipCode[iw] == ProMat[k]:
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

    startime1 = time.time()*1000
    runtime = (int(startime1) - int(startime))/1000
    print('\n模型求解需要的全部时间:        ', runtime)
