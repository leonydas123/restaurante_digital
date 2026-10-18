import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import sqlite3
import json
import re
import hashlib

# Configuração da página com layout amplo e visual mobile-first
st.set_page_config(
    page_title="App Restaurante - Pedidos e Gestão", 
    page_icon="🍽️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# CONEXÃO E BANCO DE DADOS PERSISTENTE (SQLITE)
# ==========================================
DB_FILE = "restaurante.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            categoria TEXT,
            subcategoria TEXT DEFAULT 'Refrigerante',
            qtd REAL,
            unidade TEXT,
            preco_unitario REAL DEFAULT 5.00,
            consumo_por_marmita REAL,
            data TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rendimento_carnes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_carne TEXT,
            quilos_preparados REAL,
            gramas_por_porcao REAL,
            rendimento_total_marmitas INTEGER,
            qtd_atual_disponivel REAL,
            data TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE estoque ADD COLUMN subcategoria TEXT DEFAULT 'Refrigerante'")
        cursor.execute("ALTER TABLE estoque ADD COLUMN preco_unitario REAL DEFAULT 5.00")
    except sqlite3.OperationalError:
        pass
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cupons_gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            produto TEXT,
            quantidade REAL,
            preco REAL,
            uso_pessoal INTEGER DEFAULT 0,
            hash_cupom TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE cupons_gastos ADD COLUMN hash_cupom TEXT")
    except sqlite3.OperationalError:
        pass
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            telefone TEXT,
            categoria TEXT,
            observacao TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS donos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cargo TEXT,
            contato TEXT,
            observacoes TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            cliente TEXT,
            telefone TEXT,
            horario_retirada TEXT,
            pedido TEXT,
            total REAL,
            pagamento TEXT,
            nota_info TEXT,
            estado TEXT,
            estoque_baixado INTEGER DEFAULT 0
        )
    """)

    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN estoque_baixado INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT COUNT(*) FROM configuracoes")
    if cursor.fetchone()[0] == 0:
        menu_padrao = {
            "carnes": ["Panelada", "Assado de Panela", "Costela", "Chambaril", "Frango Grelhado", "Peixe Frito"],
            "tipos_arroz": ["Arroz com feijão de caldo", "Arroz misturado / arroz baião", "Sem feijão"],
            "acompanhamentos_padrao": ["Salada", "Macarrão", "Farofa"],
            "preco_marmita": 20.00
        }
        sucos_padrao = {
            "Acerola - Copo (300 ml)": 7.00,
            "Acerola - Jarra (1 L)": 14.00,
            "Cajá - Copo (300 ml)": 9.00,
            "Cajá - Jarra (1 L)": 18.00,
            "Maracujá - Copo (300 ml)": 10.00,
            "Maracujá - Jarra (1 L)": 20.00
        }
        cursor.execute("INSERT INTO configuracoes VALUES ('menu_diario', ?)", (json.dumps(menu_padrao),))
        cursor.execute("INSERT INTO configuracoes VALUES ('precos_sucos', ?)", (json.dumps(sucos_padrao),))

    cursor.execute("SELECT COUNT(*) FROM estoque")
    if cursor.fetchone()[0] == 0:
        itens_estoque_padrao = [
            ("Coca Cola Lata 300ml", "Bebidas", "Refrigerante", 10.0, "UN", 6.00, 0.0, str(date.today())),
            ("Fanta Lata 300ml", "Bebidas", "Refrigerante", 20.0, "UN", 6.00, 0.0, str(date.today())),
            ("Água Mineral 500ml", "Bebidas", "Outros", 30.0, "UN", 4.00, 0.0, str(date.today())),
            ("Arroz", "Cozinha / Estocáveis", "Refrigerante", 25.0, "KG", 0.0, 0.150, str(date.today())),
            ("Feijão", "Cozinha / Estocáveis", "Refrigerante", 15.0, "KG", 0.0, 0.100, str(date.today())),
            ("Marmita / Embalagem PBR", "Embalagens e Marmitas", "Refrigerante", 100.0, "UN", 0.0, 1.0, str(date.today()))
        ]
        cursor.executemany("INSERT INTO estoque (item, categoria, subcategoria, qtd, unidade, preco_unitario, consumo_por_marmita, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", itens_estoque_padrao)

    cursor.execute("SELECT COUNT(*) FROM rendimento_carnes")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO rendimento_carnes (nome_carne, quilos_preparados, gramas_por_porcao, rendimento_total_marmitas, qtd_atual_disponivel, data) VALUES (?, ?, ?, ?, ?, ?)",
                       ("Assado de Panela", 7.0, 150.0, 46, 46.0, str(date.today())))

    conn.commit()
    conn.close()

init_db()

# ==========================================
# FUNÇÕES DE BANCO E REGRA DE NEGÓCIO
# ==========================================
def parse_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace(",", ".").strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def carregar_config(chave):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row["valor"]) if row else {}

def salvar_config(chave, dados):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)", (chave, json.dumps(dados)))
    conn.commit()
    conn.close()

def carregar_estoque():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM estoque", conn)
    conn.close()
    return df.to_dict("records")

def salvar_item_estoque(item, categoria, subcategoria, qtd, unidade, preco_unit, consumo, data_ent):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO estoque (item, categoria, subcategoria, qtd, unidade, preco_unitario, consumo_por_marmita, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (item, categoria, subcategoria, qtd, unidade, preco_unit, consumo, str(data_ent)))
    conn.commit()
    conn.close()

def atualizar_item_estoque(id_item, campo, valor):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE estoque SET {campo} = ? WHERE id = ?", (valor, id_item))
    conn.commit()
    conn.close()

def deletar_item_estoque(id_item):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM estoque WHERE id = ?", (id_item,))
    conn.commit()
    conn.close()

# RENDIMENTO DE CARNES
def carregar_carnes_rendimento():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM rendimento_carnes ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def salvar_carne_rendimento(nome_carne, quilos, gramas_porc, data_reg):
    quilos_g = float(quilos) * 1000.0
    rendimento = int(quilos_g / float(gramas_porc)) if float(gramas_porc) > 0 else 0
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO rendimento_carnes (nome_carne, quilos_preparados, gramas_por_porcao, rendimento_total_marmitas, qtd_atual_disponivel, data) VALUES (?, ?, ?, ?, ?, ?)",
                   (nome_carne, float(quilos), float(gramas_porc), rendimento, float(rendimento), str(data_reg)))
    conn.commit()
    conn.close()

def atualizar_carne_rendimento(id_c, campo, valor):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE rendimento_carnes SET {campo} = ? WHERE id = ?", (valor, id_c))
    conn.commit()
    conn.close()

def deletar_carne_rendimento(id_c):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rendimento_carnes WHERE id = ?", (id_c,))
    conn.commit()
    conn.close()

# CUPONS E GASTOS
def carregar_cupons():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM cupons_gastos ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def verificar_cupom_processado(hash_val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cupons_gastos WHERE hash_cupom = ?", (hash_val,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def salvar_cupom_item(data_gasto, produto, qtd, preco, uso_pessoal, hash_val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cupons_gastos (data, produto, quantidade, preco, uso_pessoal, hash_cupom) VALUES (?, ?, ?, ?, ?, ?)",
                   (str(data_gasto), produto, qtd, preco, 1 if uso_pessoal else 0, hash_val))
    conn.commit()
    conn.close()

def atualizar_status_uso_pessoal(id_cupom, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cupons_gastos SET uso_pessoal = ? WHERE id = ?", (1 if val else 0, id_cupom))
    conn.commit()
    conn.close()

def deletar_cupom_item(id_cupom):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cupons_gastos WHERE id = ?", (id_cupom,))
    conn.commit()
    conn.close()

def apagar_todos_cupons():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cupons_gastos")
    conn.commit()
    conn.close()

def carregar_fornecedores():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM fornecedores ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def salvar_fornecedor(nome, telefone, categoria, obs):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO fornecedores (nome, telefone, categoria, observacao) VALUES (?, ?, ?, ?)",
                   (nome, telefone, categoria, obs))
    conn.commit()
    conn.close()

def deletar_fornecedor(id_forn):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fornecedores WHERE id = ?", (id_forn,))
    conn.commit()
    conn.close()

def carregar_donos():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM donos ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def salvar_dono(nome, cargo, contato, obs):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO donos (nome, cargo, contato, observacoes) VALUES (?, ?, ?, ?)",
                   (nome, cargo, contato, obs))
    conn.commit()
    conn.close()

def deletar_dono(id_dono):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM donos WHERE id = ?", (id_dono,))
    conn.commit()
    conn.close()

def carregar_pedidos():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM pedidos ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def salvar_pedido(data_ped, cliente, telefone, horario, pedido_str, total, pagamento, nota_info):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pedidos (data, cliente, telefone, horario_retirada, pedido, total, pagamento, nota_info, estado, estoque_baixado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pendente', 0)
    """, (str(data_ped), str(cliente), str(telefone), str(horario), str(pedido_str), float(total), str(pagamento), str(nota_info)))
    conn.commit()
    conn.close()

def dar_baixa_estoque_completo(pedido_texto):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    estoque = pd.read_sql_query("SELECT * FROM estoque", conn).to_dict("records")
    linhas = pedido_texto.split("|")
    
    for linha in linhas:
        linha_lower = linha.lower()
        partes = linha.strip().split()
        qtd_pedido = 1
        if partes and partes[0].isdigit():
            qtd_pedido = int(partes[0])

        for item in estoque:
            if item["item"].lower() in linha_lower:
                nova_qtd = max(0.0, item["qtd"] - qtd_pedido)
                cursor.execute("UPDATE estoque SET qtd = ? WHERE id = ?", (nova_qtd, item["id"]))
        
        carnes_db = pd.read_sql_query("SELECT * FROM rendimento_carnes", conn).to_dict("records")
        for carne in carnes_db:
            if carne["nome_carne"].lower() in linha_lower:
                nova_qtd_carne = max(0.0, float(carne["qtd_atual_disponivel"]) - qtd_pedido)
                cursor.execute("UPDATE rendimento_carnes SET qtd_atual_disponivel = ? WHERE id = ?", (nova_qtd_carne, carne["id"]))

    conn.commit()
    conn.close()

def atualizar_status_pedido(id_ped, novo_estado):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT estado, estoque_baixado, pedido FROM pedidos WHERE id = ?", (id_ped,))
    row = cursor.fetchone()
    
    if row:
        ja_baixou = row["estoque_baixado"]
        pedido_texto = row["pedido"]
        
        if novo_estado == "Pago / Concluído" and not ja_baixou:
            dar_baixa_estoque_completo(pedido_texto)
            cursor.execute("UPDATE pedidos SET estado = ?, estoque_baixado = 1 WHERE id = ?", (novo_estado, id_ped))
        else:
            cursor.execute("UPDATE pedidos SET estado = ? WHERE id = ?", (novo_estado, id_ped))
            
    conn.commit()
    conn.close()

# ==========================================
# PARSER INTELIGENTE DE ÁUDIO / TEXTO LIVRE
# ==========================================
def processar_fala_inteligente(texto_fala, preco_marmita_base, precos_sucos_dict):
    itens_extraidos = []
    texto = texto_fala.lower()
    
    preco_suco_encontrado = 0.0
    suco_desc = ""
    
    for chave_suco, preco_suco in precos_sucos_dict.items():
        sabor = chave_suco.split(" - ")[0].lower()
        if sabor in texto:
            if "jarra" in texto or "1 l" in texto:
                if "jarra" in chave_suco.lower() or "1 l" in chave_suco.lower():
                    suco_desc = f"1x Suco de {sabor.capitalize()} (Jarra 1L)"
                    preco_suco_encontrado = float(preco_suco)
                    break
            else:
                if "copo" in chave_suco.lower() or "300 ml" in chave_suco.lower():
                    suco_desc = f"1x Suco de {sabor.capitalize()} (Copo 300ml)"
                    preco_suco_encontrado = float(preco_suco)
                    break

    if suco_desc and preco_suco_encontrado > 0:
        itens_extraidos.append({
            "quantidade": 1,
            "item_principal": suco_desc,
            "detalhes": "Adicionado via Pedido Inteligente",
            "preco": preco_suco_encontrado
        })

    qtd_marmitas = 0
    if "duas" in texto or "2" in texto or "outro" in texto or "outra" in texto:
        qtd_marmitas
