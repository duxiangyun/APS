import sqlite3

def create_views(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    views = [
        """
        CREATE VIEW IF NOT EXISTS v_routing_excel AS
        SELECT 
            group_id,
            seq,
            material_code,
            material_name,
            process_alt,
            equipment_code,
            production_line,
            stage_name,
            tooling_code,
            tooling_quantity,
            max_t,
            stage_1,
            stage_2,
            stage_3,
            stage_4,
            stage_5,
            stage_6,
            stage_7,
            stage_8,
            stage_9,
            stage_10
        FROM routing
        ORDER BY row_order
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_product AS
        SELECT 
            code,
            name,
            cost,
            price,
            lead_time,
            inv0,
            inv_t,
            inv_l,
            inv_u,
            inv_cost
        FROM material
        WHERE type = 'PRODUCT'
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_semi AS
        SELECT 
            code,
            name,
            dummy,
            lead_time,
            inv0,
            inv_t,
            inv_l,
            inv_u,
            inv_cost
        FROM material
        WHERE type = 'SEMI'
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_raw AS
        SELECT 
            code,
            name,
            cost,
            inv0,
            inv_t,
            inv_l,
            inv_u,
            inv_cost,
            lead_time
        FROM material
        WHERE type = 'RAW'
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_equipment AS
        SELECT 
            code,
            cost,
            number,
            rate,
            overtime_rate,
            overtime,
            cost_t,
            cost_u
        FROM equipment
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_tooling AS
        SELECT 
            code,
            name,
            cost,
            quantity,
            rate,
            overtime,
            overtime_cost
        FROM tooling
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_orders AS
        SELECT 
            no,
            cls,
            prod_code,
            price,
            quantity,
            time,
            delay,
            fine
        FROM orders
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_bom AS
        SELECT 
            group_id,
            seq,
            level,
            parent_code,
            parent_name,
            child_code,
            child_name,
            quantity
        FROM bom
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_outsource AS
        SELECT 
            code,
            name,
            cost,
            quantity_t1,
            quantity_t2,
            quantity_t3,
            quantity_t4,
            quantity_t5,
            quantity_t6,
            quantity_t7,
            quantity_t8,
            quantity_t9,
            quantity_t10,
            quantity_t11,
            quantity_t12,
            quantity_t13,
            quantity_t14,
            quantity_t15,
            quantity_t16,
            quantity_t17,
            quantity_t18,
            quantity_t19,
            quantity_t20,
            quantity_t21,
            quantity_t22,
            quantity_t23,
            quantity_t24,
            quantity_t25,
            quantity_t26,
            quantity_t27,
            quantity_t28
        FROM outsource
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_purchase_limit AS
        SELECT 
            material_code,
            material_name,
            quantity_t1,
            quantity_t2,
            quantity_t3,
            quantity_t4,
            quantity_t5,
            quantity_t6,
            quantity_t7,
            quantity_t8,
            quantity_t9,
            quantity_t10,
            quantity_t11,
            quantity_t12,
            quantity_t13,
            quantity_t14,
            quantity_t15,
            quantity_t16,
            quantity_t17,
            quantity_t18,
            quantity_t19,
            quantity_t20,
            quantity_t21,
            quantity_t22,
            quantity_t23,
            quantity_t24,
            quantity_t25,
            quantity_t26,
            quantity_t27,
            quantity_t28
        FROM purchase_limit
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_substitute AS
        SELECT 
            desc,
            seq,
            sub_type,
            material_type,
            code1,
            quantity1,
            code2,
            quantity2,
            ratio,
            batch,
            limit_q1,
            limit_q2,
            limit_q3,
            limit_q4,
            limit_q5,
            limit_q6,
            limit_q7,
            limit_q8,
            limit_q9,
            limit_q10,
            limit_q11,
            limit_q12,
            limit_q13,
            limit_q14,
            limit_q15,
            limit_q16,
            limit_q17,
            limit_q18,
            limit_q19,
            limit_q20,
            limit_q21,
            limit_q22,
            limit_q23,
            limit_q24,
            limit_q25,
            limit_q26,
            limit_q27,
            limit_q28
        FROM substitute
        """,
        
        """
        CREATE VIEW IF NOT EXISTS v_wip AS
        SELECT 
            material_code,
            material_name,
            max_t,
            stage,
            quantity
        FROM wip
        """
    ]
    
    for i, view_sql in enumerate(views, 1):
        cursor.execute(f'DROP VIEW IF EXISTS {view_sql.split()[5]}')
        cursor.execute(view_sql)
        print(f'✓ 视图 {i} 创建成功')
    
    conn.commit()
    conn.close()
    print()
    print('所有视图创建完成！')

if __name__ == '__main__':
    create_views('/Users/duxiangyun/PythonProjects/APS/Excel2DB/data/aps_model.db')