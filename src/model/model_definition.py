import sqlite3
import os

# Solver selection (same logic as APS-SPlant-v2-sqlite.py)
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

_solver_name = _select_solver()

if _solver_name == 'highs' and _HAS_HIGS:
    from highspy import Highs, ObjSense, HighsVarType, HighsModelStatus, kHighsInf
    from highspy.highs import highs_var, highs_cons, highs_linear_expression

    # ---- 兼容补丁：为 highspy 对象补充 Gurobi 风格接口 ----
    def _hi_truediv(self, other):
        return self.__mul__(1.0 / float(other))
    highs_linear_expression.__truediv__ = _hi_truediv
    highs_var.__truediv__ = _hi_truediv
    def _hi_var_x(self):
        return self.highs.allVariableValues()[self.index]
    highs_var.x = property(_hi_var_x)
    def _hi_var_getub(self):
        return self.highs.getLp().col_upper_[self.index]
    def _hi_var_setub(self, v):
        _lb = self.highs.getLp().col_lower_[self.index]
        self.highs.changeColBounds(self.index, _lb, float(v))
    highs_var.ub = property(_hi_var_getub, _hi_var_setub)
    highs_var.setub = _hi_var_setub
    def _hi_con_pi(self):
        return self.highs.allConstrDuals()[self.index]
    highs_cons.Pi = property(_hi_con_pi)

    _S_BINARY   = HighsVarType.kInteger
    _S_MAXIMIZE = ObjSense.kMaximize

    def quicksum(gen):
        """兼容 Gurobi quicksum"""
        result = None
        for term in gen:
            result = term if result is None else result + term
        return result if result is not None else 0

    _HIGHS_STATUS_MAP = {
        HighsModelStatus.kOptimal: 2,
        HighsModelStatus.kInfeasible: 3,
        HighsModelStatus.kUnboundedOrInfeasible: 4,
        HighsModelStatus.kUnbounded: 5,
        HighsModelStatus.kIterationLimit: 7,
        HighsModelStatus.kTimeLimit: 9,
        HighsModelStatus.kSolutionLimit: 10,
        HighsModelStatus.kInterrupt: 11,
        HighsModelStatus.kUnknown: 14,
    }

    class _HiModel:
        """HiGHS 模型包装，兼容 Gurobi Model 常用接口"""
        def __init__(self, name):
            self._h = Highs()
            self.Status = None; self.ObjVal = None; self.MIPGap = None
        def addVar(self, lb=0.0, ub=kHighsInf, vtype=None, name=''):
            if vtype is not None:
                return self._h.addVariable(0.0, 1.0, 0.0,
                                           HighsVarType.kInteger, name=name or None)
            return self._h.addVariable(float(lb), float(ub), 0.0,
                                       HighsVarType.kContinuous, name=name or None)
        def addVars(self, dim1, dim2, lb=0.0, ub=kHighsInf, name=''):
            return {(i, j): self._h.addVariable(float(lb), float(ub), 0.0,
                                                HighsVarType.kContinuous,
                                                name='%s[%s,%s]' % (name, i, j))
                    for i in dim1 for j in dim2}
        def addConstr(self, expr, sense=None, rhs=None, name=''):
            return self._h.addConstr(expr, name=name or None)
        def addConstrs(self, gen, name=''):
            out = {}
            for idx, e in enumerate(gen):
                out[idx] = self._h.addConstr(e, name=('%s_%d' % (name, idx)) if name else None)
            return out
        def setObjective(self, expr, sense, *_args, **_kwargs):
            self._h.setObjective(expr, sense)
        def setParam(self, param, value):
            if param == 'TimeLimit':
                self._h.setOptionValue('time_limit', float(value))
            elif param == 'MIPGap':
                self._h.setOptionValue('mip_rel_gap', float(value))
        def optimize(self):
            self._h.optimize()
            self.Status = _HIGHS_STATUS_MAP.get(self._h.getModelStatus(), 14)
            try: self.ObjVal = self._h.getObjectiveValue()
            except Exception: pass
            try:
                _info = self._h.getInfo('mip_gap')
                self.MIPGap = _info[1] if isinstance(_info, tuple) else _info
            except Exception:
                self.MIPGap = None
        def write(self, path):
            try: self._h.writeModel(path)
            except Exception: pass

    def _create_model(name):
        return _HiModel(name)
else:
    from gurobipy import *
    _S_BINARY = GRB.BINARY
    _S_MAXIMIZE = GRB.MAXIMIZE
    _create_model = Model

def define_model(data):
    nfixtable    = data['nfixtable']
    nouttable    = data['nouttable']
    nperiod      = data['nperiod']
    nproduct     = data['nproduct']
    nselfmade    = data['nselfmade']
    nrawmat      = data['nrawmat']
    nequip       = data['nequip']
    nfixture     = data['nfixture']
    intager      = data['intager']
    
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
    ProdCost     = data['ProdCost']
    Price        = data['Price']
    ProdLT       = data['ProdLT']
    ProdInvL     = data['ProdInvL']
    ProdInvU     = data['ProdInvU']
    ProdInvCost  = data['ProdInvCost']
    
    SelfCode     = data['SelfCode']
    SelfDummy    = data['SelfDummy']
    SelfInvL     = data['SelfInvL']
    SelfInvU     = data['SelfInvU']
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
    EquipNumb   = data['EquipNumb']
    EquipRate   = data['EquipRate']
    EquipOverT  = data['EquipOverT']
    EquipOverR  = data['EquipOverR']
    
    FixtCost = data['FixtCost']
    FixtQunt = data['FixtQunt']
    FixtRate = data['FixtRate']
    FixtOver = data['FixtOver']
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
    OutSQ    = data['OutSQ']
    
    RawCode     = data['RawCode']
    RawCost     = data['RawCost']
    RawInvL     = data['RawInvL']
    RawInvU     = data['RawInvU']
    RawInvCost  = data['RawInvCost']
    RawLT       = data['RawLT']
    
    RlimNo  = data['RlimNo']
    RlimId  = data['RlimId']
    RawlimQ = data['RawlimQ']
    
    SubstiNo   = data['SubstiNo']
    SubType    = data['SubType']
    SubCode1   = data['SubCode1']
    SubCode2   = data['SubCode2']
    SubQunt1   = data['SubQunt1']
    SubQunt2   = data['SubQunt2']
    SubRatio   = data['SubRatio']
    SubBatch   = data['SubBatch']
    SubLimit   = data['SubLimit']
    
    WipLoad  = data['WipLoad']
    WipNo    = data['WipNo']
    WipCode  = data['WipCode']
    WipMaxT  = data['WipMaxT']
    WipStage = data['WipStage']
    WipQunt  = data['WipQunt']
    
    Prodset  = data['Prodset']
    Prodidx  = data['Prodidx']
    Selfset  = data['Selfset']
    Selfidx  = data['Selfidx']
    Rawset   = data['Rawset']
    Rawidx   = data['Rawidx']
    Equipidx = data['Equipidx']
    
    nppro = data['nppro']
    nspro = data['nspro']
    
    FbP = data['FbP']
    FbS = data['FbS']
    RbP = data['RbP']
    RbS = data['RbS']
    
    PeP = data['PeP']
    PeS = data['PeS']
    MdP = data['MdP']
    MdS = data['MdS']
    
    EquipCap = data['EquipCap']
    FixtCap  = data['FixtCap']
    penalty  = data['penalty']

    msingle = _create_model('APS-v3')

    Prodmade = {}
    for i in Product:
        for j in range(1,nppro[i]+1):
            for t in T: 
                if t > ProdLT[i]:
                    Prodmade[i,j,t] = msingle.addVar(name = 'Pmade('+str(i)+','+str(j)+','+str(t)+')')

    Selfmade = {}                      
    for i in Self:
        for j in range(1,nspro[i]+1):
            for t in T: 
                if t > SelfLT[i]:
                    Selfmade[i,j,t] = msingle.addVar(name='Smade('+str(i)+','+str(j)+','+str(t)+')')

    ProdInv = {}                                                    
    for i in Product:
        for t in T0: 
            ProdInv[i,t] = msingle.addVar(lb=ProdInvL[i], ub=ProdInvU[i],name='Pinv('+str(i)+','+str(t)+')')
            
    SelfInv = {}                                                    
    for i in Self:
        for t in T0: 
            SelfInv[i,t] = msingle.addVar(lb=SelfInvL[i],ub=SelfInvU[i],name='Sinv('+str(i)+','+str(t)+')')

    RawInv = {}                             
    for i in Raw:
        for t in T0: 
            RawInv[i,t] = msingle.addVar(lb=RawInvL[i],ub=RawInvU[i],name='Rinv('+str(i)+','+str(t)+')')

    Purchase = {}                           
    for i in Raw:
        for t in T: 
            Purchase[i,t] = msingle.addVar(ub=1000000,name='Purc('+str(i)+','+str(t)+')')

    Workload = {}                                               
    for i in Equip:
        for t in T: 
            Workload[i,t] = msingle.addVar(ub=EquipCap[i],name='Load('+str(i)+','+str(t)+')')

    Overload = {}                                               
    for i in Equip:
        for t in T: 
            Overload[i,t] = msingle.addVar(ub=EquipCap[i]*EquipOverT[i],name='Over('+str(i)+','+str(t)+')')
       
    if nfixtable == 1:
        Fixtload = {}                                               
        for i in Fixture:
            for t in T: 
                Fixtload[i,t] = msingle.addVar(ub=FixtCap[i],name='Fixt('+str(i)+','+str(t)+')')

        FixtPlus = {}                                               
        for i in Fixture:
            for t in T: 
                FixtPlus[i,t] = msingle.addVar(ub=FixtCap[i]*FixtOver[i],name='Fpls('+str(i)+','+str(t)+')')

    OrdSale = {}                               
    for i in Order:
        for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1): 
            if t <= nperiod:
                OrdSale[i,t] = msingle.addVar(name='OrdS('+str(i)+','+str(t)+')')
                
    OrdDelay = {}                               
    for i in Order:
        for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1): 
            if t <= nperiod:
                OrdDelay[i,t] = msingle.addVar(name='OrdD('+str(i)+','+str(t)+')')
                
    if nouttable == 1:
        OutSourc = {}
        for i in OutsNo:
            for t in T:
                OutSourc[i,t] = msingle.addVar(ub=OutSQ[i,t],name='OutS('+str(i)+','+str(t)+')')

    Substi = {}
    Subbatch = {}
    if len(SubstiNo) != 0:
        for i in SubstiNo:
            for t in T:
                Substi[i,t] = msingle.addVar(ub=SubLimit[i,t],name='Substi('+str(i)+','+str(t)+')')
            if SubBatch[i] == 1:
                intager = 1
                for t in T:
                    Subbatch[i,t] = msingle.addVar(vtype = _S_BINARY, name='Subbatch('+str(i)+','+str(t)+')')

    SaleInf   = msingle.addVars(Order, T, name = 'SaleInf')
    EquipInf  = msingle.addVars(Equip, T, name = 'EquipInf')
    FixtInf   = msingle.addVars(Fixture, T, name = 'FixtInf')
    ProdInf   = msingle.addVars(Product, T, name = 'ProdInf')
    SelfInf   = msingle.addVars(Self, T, name = 'SelfInf')
    RawInf    = msingle.addVars(Raw, T, name = 'RawInf')

    msingle.setObjective(
        quicksum(OrdPrice[i]*OrdSale[i,t] for i in Order for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1) if t<=nperiod)
        - quicksum(OrdFine[i]*OrdDelay[i,t] for i in Order for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1) if t<=nperiod)
        - quicksum(RawCost[i]*Purchase[i,t] for i in Raw for t in T)
        - quicksum(OutsCost[i]*OutSourc[i,t] for i in OutsNo for t in T)
        - quicksum((EquipCost[p]*Workload[p,t] + EquipCost[p]*EquipOverR[p]*Overload[p,t]) for p in Equip for t in T)
        - quicksum((FixtCost[p]*Fixtload[p,t] + FixtCost[p]*Fovcost[p]*FixtPlus[p,t]) for p in Fixture for t in T if nfixtable == 1)
        - quicksum(ProdInvCost[i]*ProdInv[i,t] for i in Product for t in T0)
        - quicksum(SelfInvCost[i]*SelfInv[i,t] for i in Self for t in T0)
        - quicksum(RawInvCost[i]*RawInv[i,t] for i in Raw  for t in T0)
        - quicksum(penalty*ProdInf[i,t] for i in Product for t in T)
        - quicksum(penalty*SaleInf[i,t] for i in Order for t in T)
        - quicksum(penalty*SelfInf[i,t] for i in Self for t in T) 
        - quicksum(penalty*RawInf[i,t]  for i in Raw for t in T) 
        - quicksum(penalty*FixtInf[i,t]  for i in Fixture for t in T) 
        - 0.000001*quicksum(Substi[k,t] for k in SubstiNo for t in T) 
        - quicksum(penalty*EquipInf[p,t] for p in Equip for t in T), _S_MAXIMIZE
        )

    SaleBal = {}
    for i in Order:
        if OrdTime[i]+OrdDly[i] <= nperiod:
            for t in range(OrdTime[i],OrdTime[i]+OrdDly[i]+1):
                if OrdDly[i] == 0:
                    if OrdCls[i] != 3:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                    else:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                elif OrdDly[i] == 1:
                    if t == OrdTime[i]:
                        if OrdCls[i] != 3:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                        else:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                    else:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')
                elif OrdDly[i] >= 2:
                    if t == OrdTime[i]:
                        if OrdCls[i] != 3:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                        else:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                    elif t > OrdTime[i] and t < OrdTime[i]+OrdDly[i]:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')
                    else:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')
        else:
            for t in range(OrdTime[i],nperiod+1):
                if nperiod - OrdTime[i] == 0:
                    if OrdCls[i] != 3:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                    else:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                elif nperiod-OrdTime[i] == 1:
                    if t == OrdTime[i]:
                        if OrdCls[i] != 3:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                        else:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                    else:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')
                elif nperiod-OrdTime[i] >= 2:
                    if t == OrdTime[i]:
                        if OrdCls[i] != 3:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t]  + SaleInf[i,t] == OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                        else:
                            SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] <= OrdQunt[i]), name='SaleBal('+str(i)+','+str(t)+')')
                    elif t > OrdTime[i] and t < nperiod:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] + OrdDelay[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')
                    else:
                        SaleBal[(i,t)] = msingle.addConstr((OrdSale[i,t] == OrdDelay[i,t-1]), name='SaleBal('+str(i)+','+str(t)+')')

    ProdBal = {}
    for i in Product:
        for t in T:
            if t > ProdLT[i]:
                ProdBal[(i,t)] = msingle.addConstr((ProdInv[i,t-1] - ProdInv[i,t] + ProdInf[i,t]
                    + quicksum(Prodmade[i,k,t] for k in range(1,nppro[i]+1))
                    - quicksum(OrdSale[j,t] for j in Order if OrdProd[j] == ProdCode[i]
                         if t >= OrdTime[j] if t <= OrdTime[j]+OrdDly[j])
                    - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == ProdCode[i])
                    + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == ProdCode[i])
                    == 0), name = 'ProdBal('+str(i)+','+str(t)+')')
            else:
                ProdBal[(i,t)] = msingle.addConstr((ProdInv[i,t-1] - ProdInv[i,t] + ProdInf[i,t]
                    - quicksum(OrdSale[j,t] for j in Order if OrdProd[j] == ProdCode[i] if t >= OrdTime[j] if t <= OrdTime[j]+OrdDly[j])
                    - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == ProdCode[i])
                    + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == ProdCode[i])
                    == 0), name = 'ProdBal('+str(i)+','+str(t)+')')

    Self1Bal = {}
    for i in Self:
        for t in T:
            if t>SelfLT[i]:
                Self1Bal[i,t] = msingle.addConstr((SelfInv[i,t-1] - SelfInv[i,t] + SelfInf[i,t]
                    + quicksum(Selfmade[i,k,t] for k in range(1,nspro[i]+1))
                    + quicksum(OutSourc[j,t] for j in OutsNo if nouttable == 1 if OutsCode[j] == SelfCode[i])
                    - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for (j,q) in FbP[i] for k in range(1,nppro[j]+1) if t+ProdLT[j]<=nperiod)
                    - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for (j,q) in FbS[i] for k in range(1,nspro[j]+1) if t+SelfLT[j]<=nperiod)
                    - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == SelfCode[i])
                    + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == SelfCode[i])
                    == 0), name = 'SelfBal('+str(i)+','+str(t)+')')  
            else:
                if nfixtable == 1:
                    Self1Bal[i,t] = msingle.addConstr((SelfInv[i,t-1] - SelfInv[i,t] + SelfInf[i,t]
                        + quicksum(OutSourc[j,t] for j in OutsNo if OutsCode[j] == SelfCode[i])
                        - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for (j,q) in FbP[i] for k in range(1,nppro[j]+1))
                        - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for (j,q) in FbS[i] for k in range(1,nspro[j]+1))
                        - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == SelfCode[i])
                        + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == SelfCode[i])
                        + quicksum(WipQunt[k] for k in WipNo if WipCode[k] == SelfCode[i] if SelfLT[i]-WipStage[k] == t-1)
                        == 0), name = 'SelfBal('+str(i)+','+str(t)+')') 
                else:
                    Self1Bal[i,t] = msingle.addConstr((SelfInv[i,t-1] - SelfInv[i,t] + SelfInf[i,t]
                        + quicksum(OutSourc[j,t] for j in OutsNo if OutsCode[j] == SelfCode[i])
                        - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for (j,q) in FbP[i] for k in range(1,nppro[j]+1))
                        - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for (j,q) in FbS[i] for k in range(1,nspro[j]+1))
                        - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == SelfCode[i])
                        + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == SelfCode[i])
                        == 0), name = 'SelfBal('+str(i)+','+str(t)+')') 

    RawBal = {}
    for i in Raw:
        for t in T:
            RawBal[(i,t)] = msingle.addConstr((Purchase[i,t-RawLT[i]] + RawInv[i,t-1] - RawInv[i,t] + RawInf[i,t]
                    - quicksum(q*Prodmade[j,k,t+ProdLT[j]] for(j,q)in RbP[i] for k in range(1,nppro[j]+1) if t+ProdLT[j]<=nperiod)
                    - quicksum(q*Selfmade[j,k,t+SelfLT[j]] for(j,q)in RbS[i] for k in range(1,nspro[j]+1) if t+SelfLT[j]<=nperiod)
                    - quicksum(SubQunt1[k]*Substi[k,t] for k in SubstiNo if SubCode1[k] == RawCode[i])
                    + quicksum(SubQunt2[k]*Substi[k,t] for k in SubstiNo if SubCode2[k] == RawCode[i])
                    == 0), name = 'RawBal('+str(i)+','+str(t)+')') 

    CapBal = {}
    npmaxt = data['npmaxt']
    for i in Equip:
        for t in T:
            if t > npmaxt:
                CapBal[(i,t)] = msingle.addConstr((
                    quicksum(Protime[k,t1]*Prodmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeP[i]
                        for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>ProdLT[j])
                  + quicksum(Protime[k,t1]*Selfmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeS[i]
                        for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>SelfLT[j])
                  <= Workload[i,t] + Overload[i,t] + EquipInf[i,t]), name = 'CapBal('+str(i)+','+str(t)+')')
            else:
                CapBal[(i,t)] = msingle.addConstr((
                    quicksum(Protime[k,t1]*Prodmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeP[i]
                        for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>ProdLT[j])
                  + quicksum(Protime[k,t1]*Selfmade[j,ProMult[k],t+ProMaxT[k]-t1] for (j,k) in PeS[i]
                        for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>SelfLT[j])
                  <= Workload[i,t] + Overload[i,t] - WipLoad[i,t] + EquipInf[i,t]), name = 'CapBal('+str(i)+','+str(t)+')')

    FixtBal = {}
    if nfixtable == 1:
        FixtBal = {}
        for i in Fixture:
            for t in T:
                FixtBal[(i,t)] = msingle.addConstr((
                      quicksum(Protime[k,t1]*ProFixq[k]*Prodmade[j,1,t+ProMaxT[k]-t1] for (j,k) in MdP[i]
                        for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>ProdLT[j])
                    + quicksum(Protime[k,t1]*ProFixq[k]*Selfmade[j,1,t+ProMaxT[k]-t1] for (j,k) in MdS[i]
                        for t1 in range(1,ProMaxT[k]+1) if t+ProMaxT[k]-t1<=nperiod if t+ProMaxT[k]-t1>SelfLT[j])
                    <= Fixtload[i,t] + FixtPlus[i,t] + FixtInf[i,t]), name = 'FixtBal('+str(i)+','+str(t)+')')

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

    RawPurchlim = msingle.addConstrs((Purchase[Rawidx[RlimId[i]],t] <= RawlimQ[i,t] for i in RlimNo for t in T), name = 'RawPurchlim')
        
    ProdInv0lim = msingle.addConstrs((ProdInv[i,0] - data['ProdInv0'][i] == 0 for i in Product), name = 'PInv0lim')
    ProdInvTlim = msingle.addConstrs((ProdInv[i,nperiod] - data['ProdInvT'][i] == 0 for i in Product), name = 'PInvTlim')

    SelfInv0lim = msingle.addConstrs((SelfInv[i,0] - data['SelfInv0'][i] == 0 for i in Self), name = 'SInv0lim')
    SelfInvTlim = msingle.addConstrs((SelfInv[i,nperiod] - data['SelfInvT'][i] == 0 for i in Self), name = 'SInvTlim')

    RawInv0lim  = msingle.addConstrs((RawInv[i,0] - data['RawInv0'][i] == 0 for i in Raw), name = 'RInv0lim')

    model_vars = {
        'Prodmade': Prodmade,
        'Selfmade': Selfmade,
        'ProdInv': ProdInv,
        'SelfInv': SelfInv,
        'RawInv': RawInv,
        'Purchase': Purchase,
        'Workload': Workload,
        'Overload': Overload,
        'Fixtload': Fixtload if nfixtable == 1 else {},
        'FixtPlus': FixtPlus if nfixtable == 1 else {},
        'OrdSale': OrdSale,
        'OrdDelay': OrdDelay,
        'OutSourc': OutSourc if nouttable == 1 else {},
        'Substi': Substi,
        'Subbatch': Subbatch,
        'SaleInf': SaleInf,
        'EquipInf': EquipInf,
        'FixtInf': FixtInf,
        'ProdInf': ProdInf,
        'SelfInf': SelfInf,
        'RawInf': RawInf
    }

    model_constrs = {
        'SaleBal': SaleBal,
        'ProdBal': ProdBal,
        'Self1Bal': Self1Bal,
        'RawBal': RawBal,
        'CapBal': CapBal,
        'FixtBal': FixtBal,
        'Subratio': Subratio,
        'SubBch1': SubBch1,
        'SubBch2': SubBch2,
        'RawPurchlim': RawPurchlim,
        'ProdInv0lim': ProdInv0lim,
        'ProdInvTlim': ProdInvTlim,
        'SelfInv0lim': SelfInv0lim,
        'SelfInvTlim': SelfInvTlim,
        'RawInv0lim': RawInv0lim
    }

    return msingle, model_vars, model_constrs, intager
