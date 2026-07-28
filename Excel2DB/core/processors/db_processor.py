import sqlite3

def load_from_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def get_config(key, to_int=False):
        cursor = conn.execute('SELECT value FROM system_config WHERE key = ?', (key,))
        row = cursor.fetchone()
        if row is None:
            return 0 if to_int else 0.0
        val = row['value']
        return int(val) if to_int else val

    nfixtable = get_config('nfixtable', True)
    nouttable = get_config('nouttable', True)
    nrawlimtable = get_config('nrawlimtable', True)
    nsubtable = get_config('nsubtable', True)
    nwiptable = get_config('nwiptable', True)

    nperiod = get_config('nperiod', True)
    nbom0 = get_config('nbom', True)
    nrouting = get_config('nrouting', True)
    nequip = get_config('nequip', True)
    nproduct = get_config('nproduct', True)
    nselfmade = get_config('nselfmade', True)
    nrawmat = get_config('nrawmat', True)
    dutytime = get_config('dutytime', True)
    dayshift = get_config('dayshift', True)
    npmaxt = get_config('npmaxt', True)
    norder = get_config('norder', True)
    nordelay = get_config('nordelay', True)
    nordclass = get_config('nordclass', True)
    nfixture = get_config('nfixture', True)
    ndemrate = float(get_config('ndemrate'))
    intager = 0

    T = list(range(1, nperiod + 1))
    T0 = list(range(0, nperiod + 1))
    BOM0 = list(range(1, nbom0 + 1))
    Product = list(range(1, nproduct + 1))
    Self = list(range(1, nselfmade + 1))
    Raw = list(range(1, nrawmat + 1))
    Equip = list(range(1, nequip + 1))
    Order = list(range(1, norder + 1))
    Fixture = list(range(1, nfixture + 1))

    df_routing_view = conn.execute('SELECT * FROM v_routing_excel LIMIT ?', (nrouting,)).fetchall()
    Routing = list(range(1, nrouting + 1))

    df_bom = conn.execute('SELECT parent_code, child_code, quantity, level FROM v_bom').fetchall()
    Fcode0 = {i: row['parent_code'] for i, row in enumerate(df_bom, 1)}
    Scode0 = {i: row['child_code'] for i, row in enumerate(df_bom, 1)}
    Quant0 = {i: float(row['quantity']) if row['quantity'] else 0.0 for i, row in enumerate(df_bom, 1)}
    Blevel0 = {i: int(row['level']) if row['level'] else 0 for i, row in enumerate(df_bom, 1)}

    df_product = conn.execute('SELECT * FROM v_product').fetchall()
    ProdCode = {i: row['code'] for i, row in enumerate(df_product, 1)}
    ProdCost = {i: float(row['cost']) if row['cost'] else 0.0 for i, row in enumerate(df_product, 1)}
    Price = {i: float(row['price']) if row['price'] else 0.0 for i, row in enumerate(df_product, 1)}
    ProdLT = {i: int(row['lead_time']) if row['lead_time'] else 0 for i, row in enumerate(df_product, 1)}
    ProdInv0 = {i: float(row['inv0']) if row['inv0'] else 0.0 for i, row in enumerate(df_product, 1)}
    ProdInvT = {i: float(row['inv_t']) if row['inv_t'] else 0.0 for i, row in enumerate(df_product, 1)}
    ProdInvL = {i: float(row['inv_l']) if row['inv_l'] else 0.0 for i, row in enumerate(df_product, 1)}
    ProdInvU = {i: float(row['inv_u']) if row['inv_u'] else 0.0 for i, row in enumerate(df_product, 1)}
    ProdInvCost = {i: float(row['inv_cost']) if row['inv_cost'] else 0.0 for i, row in enumerate(df_product, 1)}

    df_semi = conn.execute('SELECT * FROM v_semi').fetchall()
    SelfCode = {i: row['code'] for i, row in enumerate(df_semi, 1)}
    SelfDummy = {i: int(row['dummy']) if row['dummy'] else 0 for i, row in enumerate(df_semi, 1)}
    SelfLT = {i: int(row['lead_time']) if row['lead_time'] else 0 for i, row in enumerate(df_semi, 1)}
    SelfInv0 = {i: float(row['inv0']) if row['inv0'] else 0.0 for i, row in enumerate(df_semi, 1)}
    SelfInvT = {i: float(row['inv_t']) if row['inv_t'] else 0.0 for i, row in enumerate(df_semi, 1)}
    SelfInvL = {i: float(row['inv_l']) if row['inv_l'] else 0.0 for i, row in enumerate(df_semi, 1)}
    SelfInvU = {i: float(row['inv_u']) if row['inv_u'] else 0.0 for i, row in enumerate(df_semi, 1)}
    SelfInvCost = {i: float(row['inv_cost']) if row['inv_cost'] else 0.0 for i, row in enumerate(df_semi, 1)}

    df_routing = df_routing_view
    ProMat = {}
    ProMult = {}
    ProEquip = {}
    ProState = {}
    ProFixt = {} if nfixtable == 1 else {}
    ProFixq = {} if nfixtable == 1 else {}
    ProMaxT = {}
    ProHour = {}

    for i, row in enumerate(df_routing, 1):
        ProMat[i] = row['material_code']
        ProMult[i] = int(row['process_alt']) if row['process_alt'] else 1
        ProEquip[i] = row['equipment_code']
        if nfixtable == 1:
            ProFixt[i] = row['tooling_code']
            ProFixq[i] = int(row['tooling_quantity']) if row['tooling_quantity'] else 0
        ProMaxT[i] = int(row['max_t']) if row['max_t'] else 0
        ProHour[i] = []
        for s_idx in range(1, 11):
            col_name = f'stage_{s_idx}'
            s = row[col_name]
            try:
                val = float(s) if s else 0
                ProHour[i].append(val)
            except (ValueError, TypeError):
                ProHour[i].append(0)
        max_t_val = ProMaxT[i] if i in ProMaxT else 1
        while len(ProHour[i]) < max_t_val:
            ProHour[i].append(0)
        while len(ProHour[i]) < npmaxt:
            ProHour[i].append(0)
        ProState[i] = row['production_line'] if row['production_line'] else ''

    Protime = {}
    for p in Routing:
        for t in range(1, npmaxt + 1):
            Protime[p, t] = ProHour[p][t - 1] if p in ProHour and t - 1 < len(ProHour[p]) else 0

    df_equip = conn.execute('SELECT * FROM v_equipment').fetchall()
    EquipId = {i: row['code'] for i, row in enumerate(df_equip, 1)}
    EquipCost = {i: float(row['cost']) if row['cost'] else 0.0 for i, row in enumerate(df_equip, 1)}
    EquipNumb = {i: int(row['number']) if row['number'] else 0 for i, row in enumerate(df_equip, 1)}
    EquipRate = {i: float(row['rate']) if row['rate'] else 0.0 for i, row in enumerate(df_equip, 1)}
    EquipOverT = {i: float(row['overtime_rate']) if row['overtime_rate'] else 0.0 for i, row in enumerate(df_equip, 1)}
    EquipOverR = {i: float(row['overtime']) if row['overtime'] else 0.0 for i, row in enumerate(df_equip, 1)}

    FixtNo = {}
    FixtId = {}
    FixtCost = {}
    FixtQunt = {}
    FixtRate = {}
    FixtOver = {}
    Fovcost = {}

    if nfixtable == 1:
        df_tooling = conn.execute('SELECT * FROM v_tooling').fetchall()
        FixtNo = {i: i for i in range(1, nfixture + 1)}
        FixtId = {i: row['code'] for i, row in enumerate(df_tooling, 1)}
        FixtCost = {i: float(row['cost']) if row['cost'] else 0.0 for i, row in enumerate(df_tooling, 1)}
        FixtQunt = {i: int(row['quantity']) if row['quantity'] else 0 for i, row in enumerate(df_tooling, 1)}
        FixtRate = {i: float(row['rate']) if row['rate'] else 0.0 for i, row in enumerate(df_tooling, 1)}
        FixtOver = {i: float(row['overtime']) if row['overtime'] else 0.0 for i, row in enumerate(df_tooling, 1)}
        Fovcost = {i: float(row['overtime_cost']) if row['overtime_cost'] else 0.0 for i, row in enumerate(df_tooling, 1)}

    df_orders = conn.execute('SELECT * FROM v_orders').fetchall()
    OrdNo = {i: int(row['no']) if row['no'] else 0 for i, row in enumerate(df_orders, 1)}
    OrdCls = {i: row['cls'] for i, row in enumerate(df_orders, 1)}
    OrdProd = {i: row['prod_code'] for i, row in enumerate(df_orders, 1)}
    OrdPrice = {i: float(row['price']) if row['price'] else 0.0 for i, row in enumerate(df_orders, 1)}
    OrdQunt = {i: float(row['quantity']) if row['quantity'] else 0.0 for i, row in enumerate(df_orders, 1)}
    OrdTime = {i: int(row['time']) if row['time'] else 0 for i, row in enumerate(df_orders, 1)}
    OrdDly = {i: int(row['delay']) if row['delay'] else 0 for i, row in enumerate(df_orders, 1)}
    OrdFine = {i: float(row['fine']) if row['fine'] else 0.0 for i, row in enumerate(df_orders, 1)}

    OutsNo = {}
    OutsCode = {}
    OutsCost = {}
    OutSQ = {}

    if nouttable == 1:
        df_outsource = conn.execute('SELECT * FROM v_outsource').fetchall()
        OutsNo = {i: i for i in range(1, len(df_outsource) + 1)}
        OutsCode = {i: row['code'] for i, row in enumerate(df_outsource, 1)}
        OutsCost = {i: float(row['cost']) if row['cost'] else 0.0 for i, row in enumerate(df_outsource, 1)}
        for i in OutsNo:
            for t in T:
                OutSQ[(i, t)] = 0
        for i, row in enumerate(df_outsource, 1):
            for t in T:
                col_name = f'quantity_t{t}'
                OutSQ[(i, t)] = float(row[col_name]) if row[col_name] else 0

    df_raw = conn.execute('SELECT * FROM v_raw').fetchall()
    RawCode = {i: row['code'] for i, row in enumerate(df_raw, 1)}
    RawCost = {i: float(row['cost']) if row['cost'] else 0.0 for i, row in enumerate(df_raw, 1)}
    RawInv0 = {i: float(row['inv0']) if row['inv0'] else 0.0 for i, row in enumerate(df_raw, 1)}
    RawInvT = {i: float(row['inv_t']) if row['inv_t'] else 0.0 for i, row in enumerate(df_raw, 1)}
    RawInvL = {i: float(row['inv_l']) if row['inv_l'] else 0.0 for i, row in enumerate(df_raw, 1)}
    RawInvU = {i: float(row['inv_u']) if row['inv_u'] else 0.0 for i, row in enumerate(df_raw, 1)}
    RawInvCost = {i: float(row['inv_cost']) if row['inv_cost'] else 0.0 for i, row in enumerate(df_raw, 1)}
    RawLT = {i: int(row['lead_time']) if row['lead_time'] else 0 for i, row in enumerate(df_raw, 1)}

    RlimNo = {}
    RlimId = {}
    RawlimQ = {}

    if nrawlimtable == 1:
        df_purchase_limit = conn.execute('SELECT * FROM v_purchase_limit').fetchall()
        RlimNo = {i: i for i in range(1, len(df_purchase_limit) + 1)}
        RlimId = {i: row['material_code'] for i, row in enumerate(df_purchase_limit, 1)}
        for i in RlimNo:
            for t in T:
                RawlimQ[(i, t)] = 0
        for i, row in enumerate(df_purchase_limit, 1):
            for t in T:
                col_name = f'quantity_t{t}'
                RawlimQ[(i, t)] = float(row[col_name]) if row[col_name] else 0

    SubstiNo = {}
    SubType = {}
    SubCode1 = {}
    SubCode2 = {}
    SubQunt1 = {}
    SubQunt2 = {}
    Sublimit = {}
    SubRatio = {}
    SubBatch = {}
    SubLimit = {}

    if nsubtable == 1:
        df_substitute = conn.execute('SELECT * FROM v_substitute').fetchall()
        SubstiNo = {i: i for i in range(1, len(df_substitute) + 1)}
        SubType = {i: row['sub_type'] for i, row in enumerate(df_substitute, 1)}
        SubCode1 = {i: row['code1'] for i, row in enumerate(df_substitute, 1)}
        SubCode2 = {i: row['code2'] for i, row in enumerate(df_substitute, 1)}
        SubQunt1 = {i: float(row['quantity1']) if row['quantity1'] else 0.0 for i, row in enumerate(df_substitute, 1)}
        SubQunt2 = {i: float(row['quantity2']) if row['quantity2'] else 0.0 for i, row in enumerate(df_substitute, 1)}
        Sublimit = {i: row['desc'] for i, row in enumerate(df_substitute, 1)}
        SubRatio = {i: float(row['ratio']) if row['ratio'] else 0.0 for i, row in enumerate(df_substitute, 1)}
        SubBatch = {i: float(row['batch']) if row['batch'] else 0.0 for i, row in enumerate(df_substitute, 1)}
        
        for i in SubstiNo:
            for t in T:
                SubLimit[i, t] = 0
        for i, row in enumerate(df_substitute, 1):
            for t in T:
                col_name = f'limit_q{t}'
                SubLimit[i, t] = float(row[col_name]) if row[col_name] else 0

    WipLoad = {}
    for i in Equip:
        for t in range(1, npmaxt + 1):
            WipLoad[i, t] = 0

    WipNo = {}
    WipCode = {}
    WipMaxT = {}
    WipStage = {}
    WipQunt = {}

    if nwiptable == 1:
        df_wip = conn.execute('SELECT * FROM v_wip').fetchall()
        WipNo = {i: i for i in range(1, len(df_wip) + 1)}
        WipCode = {i: row['material_code'] for i, row in enumerate(df_wip, 1)}
        WipMaxT = {i: int(row['max_t']) if row['max_t'] else 0 for i, row in enumerate(df_wip, 1)}
        WipStage = {i: int(row['stage']) if row['stage'] else 0 for i, row in enumerate(df_wip, 1)}
        WipQunt = {i: float(row['quantity']) if row['quantity'] else 0.0 for i, row in enumerate(df_wip, 1)}

        Equipidx = {EquipId[i]: i for i in Equip}
        for i in WipNo:
            for j in Routing:
                if j in ProMat and WipCode[i] == ProMat[j]:
                    for q in Equip:
                        if j in ProEquip and ProEquip[j] == EquipId[q]:
                            for t in range(1, ProMaxT[j] - WipStage[i] + 1):
                                key = (j, WipStage[i] + t)
                                WipLoad[q, t] += WipQunt[i] * (Protime[key] if key in Protime else 0)

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
            j += 1
            ii += 1
            Bomfidx[Fcode0[i]] = j
            BomS[j] = []
            BomF[j] = Fcode0[i]
            BomS[j].append(Scode0[i])
            Fcode[ii] = Fcode0[i]
            Scode[ii] = Scode0[i]
            Quant[ii] = Quant0[i]
            Blevel[ii] = Blevel0[i]
        else:
            jj = Bomfidx[Fcode0[i]]
            if Scode0[i] not in BomS[jj]:
                ii += 1
                BomS[j].append(Scode0[i])
                Fcode[ii] = Fcode0[i]
                Scode[ii] = Scode0[i]
                Quant[ii] = Quant0[i]
                Blevel[ii] = Blevel0[i]
    nbom = ii
    BOMs = list(range(1, nbom + 1))

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

    Equipidx = {}
    for i in Equip:
        Equipidx[EquipId[i]] = i

    Fixtidx = {}
    if nfixtable == 1:
        for i in Fixture:
            Fixtidx[FixtId[i]] = i

    nppro = {}
    nspro = {}
    RoutingMat = []
    for i in Product:
        nppro[i] = 1
    for i in Self:
        nspro[i] = 1
    for i in Routing:
        if i in ProMat and ProMat[i] not in RoutingMat:
            RoutingMat.append(ProMat[i])
        if i in ProMult and ProMult[i] != 1:
            if ProMat[i] in Prodset:
                nppro[Prodidx[ProMat[i]]] = ProMult[i]
            elif ProMat[i] in Selfset:
                nspro[Selfidx[ProMat[i]]] = ProMult[i]

    FbP = {}
    FbS = {}
    RbP = {}
    RbS = {}
    for j in Self:
        FbP[j] = []
        FbS[j] = []
    for j in Raw:
        RbP[j] = []
        RbS[j] = []

    for i in BOMs:
        if Scode[i] in Selfset:
            j = Selfidx[Scode[i]]
            if Fcode[i] in Prodset:
                k = Prodidx[Fcode[i]]
                q = Quant[i]
                FbP[j].append((k, q))
            elif Fcode[i] in Selfset:
                k = Selfidx[Fcode[i]]
                q = Quant[i]
                FbS[j].append((k, q))
        elif Scode[i] in Rawset:
            j = Rawidx[Scode[i]]
            if Fcode[i] in Prodset:
                k = Prodidx[Fcode[i]]
                q = Quant[i]
                RbP[j].append((k, q))
            elif Fcode[i] in Selfset:
                k = Selfidx[Fcode[i]]
                q = Quant[i]
                RbS[j].append((k, q))

    PeP = {}
    PeS = {}
    for i in Equip:
        PeP[i] = []
        PeS[i] = []

    if nfixtable == 1:
        MdP = {}
        MdS = {}
        for i in Fixture:
            MdP[i] = []
            MdS[i] = []

    for j in Routing:
        if j not in ProMat:
            continue
        i = Equipidx.get(ProEquip[j], 0)
        i1 = 0
        if nfixtable == 1:
            if j in ProFixt and ProFixt[j] != '' and ProFixt[j] is not None:
                i1 = Fixtidx.get(ProFixt[j], 0)

        if ProMat[j] in Prodset:
            k = Prodidx[ProMat[j]]
            PeP[i].append((k, j))
            if i1 != 0 and nfixtable == 1:
                MdP[i1].append((k, j))
        elif ProMat[j] in Selfset:
            k = Selfidx[ProMat[j]]
            PeS[i].append((k, j))
            if i1 != 0 and nfixtable == 1:
                MdS[i1].append((k, j))

    EquipCap = {}
    for p in Equip:
        EquipCap[p] = dutytime * dayshift * EquipRate[p] * EquipNumb[p]

    FixtCap = {}
    if nfixtable == 1:
        for p in Fixture:
            FixtCap[p] = dutytime * dayshift * FixtRate[p] * FixtQunt[p]

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
        'ProFixt': ProFixt,
        'ProFixq': ProFixq,
        'ProMaxT': ProMaxT,
        'Protime': Protime,
        'EquipId': EquipId,
        'EquipCost': EquipCost,
        'EquipNumb': EquipNumb,
        'EquipRate': EquipRate,
        'EquipOverT': EquipOverT,
        'EquipOverR': EquipOverR,
        'FixtNo': FixtNo,
        'FixtId': FixtId,
        'FixtCost': FixtCost,
        'FixtQunt': FixtQunt,
        'FixtRate': FixtRate,
        'FixtOver': FixtOver,
        'Fovcost': Fovcost,
        'OrdNo': OrdNo,
        'OrdCls': OrdCls,
        'OrdProd': OrdProd,
        'OrdPrice': OrdPrice,
        'OrdQunt': OrdQunt,
        'OrdTime': OrdTime,
        'OrdDly': OrdDly,
        'OrdFine': OrdFine,
        'OutsNo': OutsNo,
        'OutsCode': OutsCode,
        'OutsCost': OutsCost,
        'OutSQ': OutSQ,
        'RawCode': RawCode,
        'RawCost': RawCost,
        'RawInv0': RawInv0,
        'RawInvT': RawInvT,
        'RawInvL': RawInvL,
        'RawInvU': RawInvU,
        'RawInvCost': RawInvCost,
        'RawLT': RawLT,
        'RlimNo': RlimNo,
        'RlimId': RlimId,
        'RawlimQ': RawlimQ,
        'SubstiNo': SubstiNo,
        'SubType': SubType,
        'SubCode1': SubCode1,
        'SubCode2': SubCode2,
        'SubQunt1': SubQunt1,
        'SubQunt2': SubQunt2,
        'SubRatio': SubRatio,
        'SubBatch': SubBatch,
        'SubLimit': SubLimit,
        'WipLoad': WipLoad,
        'WipNo': WipNo,
        'WipCode': WipCode,
        'WipMaxT': WipMaxT,
        'WipStage': WipStage,
        'WipQunt': WipQunt,
        'Prodset': Prodset,
        'Prodidx': Prodidx,
        'Selfset': Selfset,
        'Selfidx': Selfidx,
        'Rawset': Rawset,
        'Rawidx': Rawidx,
        'Equipidx': Equipidx,
        'Fixtidx': Fixtidx,
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

    conn.close()
    return data