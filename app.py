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
    except sqlite3.OperationalError:
        pass

    try:
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

# DONOS
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
        qtd_marmitas = 2
    elif "tres" in texto or "três" in texto or "3" in texto:
        qtd_marmitas = 3
    elif "quatro" in texto or "4" in texto:
        qtd_marmitas = 4
    else:
        qtd_marmitas = 1

    partes = re.split(r'e|uma|outra|\,', texto)
    partes_marmitas = [p.strip() for p in partes if ("costela" in p or "carne" in p or "feijão" in p or "marmita" in p or "salada" in p or "assado" in p)]
    
    if not partes_marmitas:
        partes_marmitas = [texto_fala]

    for i in range(min(qtd_marmitas, len(partes_marmitas) if len(partes_marmitas) > 1 else qtd_marmitas)):
        detalhe_item = partes_marmitas[i] if i < len(partes_marmitas) else partes_marmitas[0]
        itens_extraidos.append({
            "quantidade": 1,
            "item_principal": f"1x Refeição Marmita #{i+1}",
            "detalhes": detalhe_item.strip().capitalize(),
            "preco": float(preco_marmita_base)
        })

    return itens_extraidos

# ==========================================
# DESIGN E ESTILO CSS COMPATÍVEL COM MODO ESCURO
# ==========================================
st.markdown("""
    <style>
    .main {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .app-header {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        padding: 20px;
        border-radius: 16px;
        color: white;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.4);
        margin-bottom: 20px;
    }
    .app-header h1 {
        color: #ffffff !important;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0;
    }
    .app-header p {
        color: #e6f4ea;
        font-size: 0.95rem;
        margin-top: 6px;
    }

    .stButton>button {
        border-radius: 12px !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.65rem 1.2rem !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25) !important;
        transition: all 0.2s ease-in-out !important;
        width: 100% !important;
    }

    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #10b981 !important;
        margin-bottom: 12px !important;
    }
    div[data-testid="stExpander"] summary span {
        color: #10b981 !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializar sessões
if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

if "form_refeicao_key" not in st.session_state:
    st.session_state.form_refeicao_key = 0

if "form_suco_key" not in st.session_state:
    st.session_state.form_suco_key = 0

menu_diario = carregar_config("menu_diario")
precos_sucos = carregar_config("precos_sucos")

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================
if st.session_state.modo_admin:
    st.markdown("""
        <div class='app-header'>
            <h1>🔒 Painel de Gestão & Administração</h1>
            <p>Cardápio, Pedidos, Estoque, Rendimento de Carnes, Fechamento de Caixa e Gestão de Sócios.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab_carnes, admin_tab8, admin_tab5, admin_tab6, admin_tab7, admin_tab4 = st.tabs([
        "⚙️ Cardápio & Preços", 
        "📋 Pedidos & Comandas", 
        "📦 Estoque",
        "🥩 Rendimento de Carnes",
        "🧾 Cupons & Gastos",
        "🤝 Fornecedores",
        "👑 Donos",
        "📈 Relatórios",
        "📊 Fechamento de Caixa"
    ])
    
    with admin_tab1:
        st.markdown("#### 🥩 Configuração de Carnes do Dia")
        novas_carnes = st.text_area("Lista de Carnes (separadas por vírgula):", value=", ".join(menu_diario["carnes"]))
        
        st.divider()
        st.markdown("#### 🍚 Opções de Acompanhamento Base")
        novos_tipos_arroz = st.text_area("Opções Base (separadas por vírgula):", value=", ".join(menu_diario["tipos_arroz"]))

        st.divider()
        st.markdown("#### 🥗 Outros Acompanhamentos")
        novos_acompanhamentos = st.text_area("Outros Acompanhamentos:", value=", ".join(menu_diario["acompanhamentos_padrao"]))
        
        st.divider()
        st.markdown("#### 💰 Preço Padrão da Refeição")
        preco_marmita_novo = st.number_input("Preço Padrão (R$):", value=float(menu_diario["preco_marmita"]), step=1.00)
        
        st.divider()
        st.markdown("#### 🧃 Gestão de Preços e Sabores de Sucos Naturais")
        
        novos_precos_sucos = {}
        for chave_suco, preco_atual in precos_sucos.items():
            novos_precos_sucos[chave_suco] = st.number_input(f"Preço ({chave_suco}) (R$):", min_value=0.0, value=float(preco_atual), step=0.50)

        st.markdown("##### ➕ Adicionar Novo Sabor / Tamanho de Suco")
        col_ns1, col_ns2, col_ns3 = st.columns(3)
        with col_ns1:
            novo_sabor_nome = st.text_input("Novo Sabor (ex: Graviola):")
        with col_ns2:
            novo_tamanho_opcao = st.selectbox("Tamanho do Suco:", ["Copo (300 ml)", "Jarra (1 L)"])
        with col_ns3:
            novo_preco_suco = st.number_input("Preço (R$):", value=8.00, step=0.50)

        if st.button("💾 Salvar Alterações do Cardápio & Sucos", type="primary"):
            menu_diario["carnes"] = [c.strip() for c in novas_carnes.split(",") if c.strip()]
            menu_diario["tipos_arroz"] = [r.strip() for r in novos_tipos_arroz.split(",") if r.strip()]
            menu_diario["acompanhamentos_padrao"] = [a.strip() for a in novos_acompanhamentos.split(",") if a.strip()]
            menu_diario["preco_marmita"] = preco_marmita_novo
            
            if novo_sabor_nome.strip():
                chave_nova = f"{novo_sabor_nome.strip().capitalize()} - {novo_tamanho_opcao}"
                novos_precos_sucos[chave_nova] = novo_preco_suco
                
            salvar_config("menu_diario", menu_diario)
            salvar_config("precos_sucos", novos_precos_sucos)
            st.success("✨ Cardápio e preços atualizados com sucesso!")
            st.rerun()
            
    with admin_tab2:
        st.markdown("#### 📥 Pedidos Recebidos & Baixa de Estoque")
        filtro_status = st.selectbox("Filtrar Pedidos por Status:", ["Todos", "Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"])
        lista_pedidos = carregar_pedidos()
        
        if filtro_status != "Todos":
            lista_pedidos = [p for p in lista_pedidos if p['estado'] == filtro_status]
            
        if not lista_pedidos:
            st.info("Nenhum pedido encontrado.")
        else:
            for ped in lista_pedidos:
                with st.expander(f"📦 Pedido #{ped['id']} - {ped['cliente']} | Status: {ped['estado']} (R$ {ped['total']:.2f})"):
                    st.write(f"📅 **Data:** {ped['data']} | ⏰ **Retirada:** {ped['horario_retirada']}")
                    st.write(f"📱 **Telefone:** {ped['telefone']}")
                    st.write(f"🍽️ **Itens:** {ped['pedido']}")
                    st.write(f"💳 **Pagamento:** {ped['pagamento']}")
                    
                    if ped['estoque_baixado']:
                        st.caption("✅ Baixa automática realizada no estoque.")

                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        novo_estado = st.selectbox("Atualizar Status do Pedido:", ["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"],
                                                   index=["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"].index(ped['estado']),
                                                   key=f"status_sel_{ped['id']}")
                        if st.button("💾 Confirmar Status", key=f"btn_status_{ped['id']}"):
                            atualizar_status_pedido(ped['id'], novo_estado)
                            st.success("Status atualizado!")
                            st.rerun()
                            
                    with col_p2:
                        st.markdown("##### 🛈 Comanda para Cozinha")
                        comanda_texto = f"=== COMANDA #{ped['id']} ===\nCliente: {ped['cliente']}\nRetirada: {ped['horario_retirada']}\n\n{ped['pedido'].replace(' | ', '\n')}\n\nTotal: R$ {ped['total']:.2f}\n====================="
                        st.code(comanda_texto, language="text")

    with admin_tab3:
        st.markdown("#### 📦 Controle de Estoque de Bebidas e Insumos")
        estoque_atual = carregar_estoque()
        with st.form("form_novo_item_estoque"):
            st.markdown("##### ➕ Cadastrar Novo Item no Estoque")
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                nome_item = st.text_input("Nome do Item (ex: Coca Cola Lata 300ml):")
                data_item = st.date_input("Data de Entrada:", value=date.today())
            with col_e2:
                cat_item = st.selectbox("Categoria:", ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"])
                subcat_item = st.selectbox("Tipo de Bebida:", ["Refrigerante", "Suco Natural", "Outros"])
                un_item = st.selectbox("Unidade:", ["UN", "KG", "Litros", "Pacotes"])
            with col_e3:
                qtd_input = st.text_input("Quantidade Inicial:", value="10.0")
                preco_unit_input = st.text_input("Preço de Venda (R$):", value="6.00")
                consumo_input = st.text_input("Gasto p/ Marmita:", value="0.0")

            if st.form_submit_button("💾 Salvar no Estoque", type="primary"):
                qtd_val = parse_float(qtd_input)
                preco_val = parse_float(preco_unit_input)
                consumo_val = parse_float(consumo_input)
                if not nome_item:
                    st.error("Informe o nome do item.")
                else:
                    salvar_item_estoque(nome_item, cat_item, subcat_item, qtd_val, un_item, preco_val, consumo_val, data_item)
                    st.success("Item salvo no estoque!")
                    st.rerun()

        st.divider()
        categorias_disponiveis = ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"]
        cat_selecionada = st.radio("Filtrar Categoria:", categorias_disponiveis, horizontal=True)

        for item_est in estoque_atual:
            if item_est["categoria"] == cat_selecionada:
                col_i1, col_i2, col_i3, col_i4, col_i5, col_i6 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1])
                with col_i1:
                    st.write(f"• **{item_est['item']}**")
                    if item_est['qtd'] <= 0:
                        st.caption("🔴 ESTOQUE ZERADO")
                with col_i2:
                    nova_subcat = st.selectbox("Tipo", ["Refrigerante", "Suco Natural", "Outros"], index=["Refrigerante", "Suco Natural", "Outros"].index(item_est.get('subcategoria', 'Refrigerante')), key=f"sub_{item_est['id']}")
                    if nova_subcat != item_est.get('subcategoria', 'Refrigerante'):
                        atualizar_item_estoque(item_est['id'], "subcategoria", nova_subcat)
                        st.rerun()
                with col_i3:
                    nova_qtd = st.number_input("Qtd", value=float(item_est['qtd']), step=1.0, key=f"est_qtd_{item_est['id']}")
                    if nova_qtd != item_est["qtd"]:
                        atualizar_item_estoque(item_est['id'], "qtd", nova_qtd)
                with col_i4:
                    novo_preco = st.number_input("Preço R$", value=float(item_est.get('preco_unitario', 5.0)), step=0.5, key=f"est_preco_{item_est['id']}")
                    if novo_preco != item_est.get('preco_unitario', 5.0):
                        atualizar_item_estoque(item_est['id'], "preco_unitario", novo_preco)
                with col_i5:
                    novo_consumo = st.number_input("Gasto/Marmita", value=float(item_est['consumo_por_marmita']), step=0.01, key=f"est_cons_{item_est['id']}")
                    if novo_consumo != item_est["consumo_por_marmita"]:
                        atualizar_item_estoque(item_est['id'], "consumo_por_marmita", novo_consumo)
                with col_i6:
                    if st.button("🗑️", key=f"del_est_{item_est['id']}"):
                        deletar_item_estoque(item_est['id'])
                        st.rerun()
                st.markdown("---")

    # RENDIMENTO DE CARNES
    with admin_tab_carnes:
        st.markdown("#### 🥩 Controle de Rendimento de Carnes (Quilos ➔ Gramas ➔ Marmitas)")
        with st.form("form_novo_rendimento_carne"):
            col_rc1, col_rc2 = st.columns(2)
            with col_rc1:
                nome_c_input = st.text_input("Nome da Carne (ex: Assado de Panela):", value="Assado de Panela")
                quilos_prep = st.text_input("Quilos Preparados na Panela (ex: 7.0):", value="7.0")
            with col_rc2:
                gramas_porc_input = st.text_input("Gramas por porção/marmita (ex: 150):", value="150")
                data_c_reg = st.date_input("Data de Preparo:", value=date.today())

            if st.form_submit_button("💾 Calcular e Salvar Rendimento", type="primary"):
                q_val = parse_float(quilos_prep)
                g_val = parse_float(gramas_porc_input)
                if not nome_c_input:
                    st.error("Informe o nome da carne.")
                else:
                    salvar_carne_rendimento(nome_c_input, q_val, g_val, data_c_reg)
                    st.success("✨ Rendimento de carne calculado e salvo!")
                    st.rerun()

        st.divider()
        lista_carnes_rend = carregar_carnes_rendimento()
        if not lista_carnes_rend:
            st.info("Nenhuma carne cadastrada.")
        else:
            for c_r in lista_carnes_rend:
                col_cr1, col_cr2, col_cr3, col_cr4 = st.columns([2, 2, 2, 1])
                with col_cr1:
                    st.write(f"• **{c_r['nome_carne']}**")
                    st.caption(f"📅 Data: {c_r['data']}")
                with col_cr2:
                    st.write(f"⚖️ {c_r['quilos_preparados']} kg | {c_r['gramas_por_porcao']}g por marmita")
                with col_cr3:
                    saldo_atual = float(c_r['qtd_atual_disponivel'])
                    st.write(f"📦 Restam: **{int(saldo_atual)} marmitas**")
                    if saldo_atual <= 0:
                        st.caption("🔴 CARNE ESGOTADA!")
                with col_cr4:
                    if st.button("🗑️", key=f"del_cr_{c_r['id']}"):
                        deletar_carne_rendimento(c_r['id'])
                        st.rerun()
                st.markdown("---")

    with admin_tab8:
        st.markdown("#### 🧾 Leitura de Cupons & Controle de Gastos")
        with st.form("form_upload_cupom"):
            foto_cupom = st.file_uploader("Enviar foto do cupom fiscal / nota:", type=["jpg", "jpeg", "png"])
            data_cupom = st.date_input("Data da Compra:", value=date.today())
            if st.form_submit_button("⚡ Processar Cupom", type="primary"):
                if foto_cupom:
                    bytes_img = foto_cupom.getvalue()
                    h_img = hashlib.md5(bytes_img).hexdigest()
                    if verificar_cupom_processado(h_img):
                        st.warning("⚠️ Cupom já processado anteriormente.")
                    else:
                        itens_cupom = [("Arroz Bco Sepe 5KG", 6.0, 137.70), ("Coca Cola Lata", 4.0, 17.16)]
                        for prod, q, p in itens_cupom:
                            salvar_cupom_item(data_cupom, prod, q, p, False, h_img)
                        st.success("✨ Cupom processado!")
                        st.rerun()
                else:
                    st.warning("Envie uma foto.")

        st.divider()
        if st.button("🗑️ Apagar Todos os Cupons"):
            apagar_todos_cupons()
            st.rerun()

        for c in carregar_cupons():
            col_cp1, col_cp2, col_cp3, col_cp4 = st.columns([3, 2, 2, 1])
            with col_cp1:
                st.write(f"• **{c['produto']}**")
            with col_cp2:
                st.write(f"R$ {c['preco']:.2f}")
            with col_cp3:
                m_pessoal = st.checkbox("👤 Uso Pessoal", value=bool(c['uso_pessoal']), key=f"pessoal_{c['id']}")
                if m_pessoal != bool(c['uso_pessoal']):
                    atualizar_status_uso_pessoal(c['id'], m_pessoal)
                    st.rerun()
            with col_cp4:
                if st.button("🗑️", key=f"del_cp_{c['id']}"):
                    deletar_cupom_item(c['id'])
                    st.rerun()

    with admin_tab5:
        st.markdown("#### 🤝 Fornecedores")
        with st.form("form_forn"):
            f_nome = st.text_input("Nome:")
            f_tel = st.text_input("Telefone:")
            if st.form_submit_button("Salvar"):
                if f_nome:
                    salvar_fornecedor(f_nome, f_tel, "Geral", "")
                    st.rerun()
        for f in carregar_fornecedores():
            st.write(f"• {f['nome']} - {f['telefone']}")

    # ABA DONOS COMPLETA E RESTAURADA
    with admin_tab6:
        st.markdown("#### 👑 Gestão de Sócios e Donos")
        st.caption("Cadastre os sócios, cargos e percentuais de participação no estabelecimento.")
        
        with st.form("form_cadastro_dono_completo"):
            st.markdown("##### ➕ Cadastrar / Atualizar Sócio")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                dono_nome = st.text_input("Nome do Sócio / Proprietário:")
                dono_cargo = st.selectbox("Cargo / Função:", ["Sócio Proprietário", "Gerente Geral", "Administrador Financeiro", "Investidor"])
            with col_d2:
                dono_contato = st.text_input("Contato / WhatsApp:")
                dono_obs = st.text_input("Observações / Participação (%):", value="50%")

            if st.form_submit_button("💾 Salvar Sócio", type="primary"):
                if not dono_nome:
                    st.error("Informe o nome do sócio.")
                else:
                    salvar_dono(dono_nome, dono_cargo, dono_contato, dono_obs)
                    st.success("✨ Sócio cadastrado com sucesso!")
                    st.rerun()

        st.divider()
        st.markdown("##### 📋 Sócios Cadastrados")
        lista_donos_cad = carregar_donos()
        if not lista_donos_cad:
            st.info("Nenhum sócio cadastrado ainda.")
        else:
            for dono_item in lista_donos_cad:
                col_dn1, col_dn2, col_dn3, col_dn4 = st.columns([2, 2, 2, 1])
                with col_dn1:
                    st.write(f"👑 **{dono_item['nome']}**")
                    st.caption(f"Cargo: {dono_item['cargo']}")
                with col_dn2:
                    st.write(f"📱 {dono_item['contato'] or 'Não informado'}")
                with col_dn3:
                    st.write(f"📝 {dono_item['observacoes'] or 'Sem observações'}")
                with col_dn4:
                    if st.button("🗑️", key=f"del_dono_{dono_item['id']}"):
                        deletar_dono(dono_item['id'])
                        st.rerun()
                st.markdown("---")

    with admin_tab7:
        st.markdown("#### 📈 Relatórios")
        lista_p = carregar_pedidos()
        if lista_p:
            st.bar_chart(pd.DataFrame(lista_p)['estado'].value_counts())

    # ABA FECHAMENTO DE CAIXA COMPLETA E RESTAURADA
    with admin_tab4:
        st.markdown("#### 📊 Fechamento e Controle de Caixa")
        
        pedidos_todos = carregar_pedidos()
        data_caixa = st.date_input("Data da Consulta de Caixa:", value=date.today())
        
        pedidos_dia = [p for p in pedidos_todos if str(p['data']) == str(data_caixa) and p['estado'] == 'Pago / Concluído']
        
        total_bruto = sum([p['total'] for p in pedidos_dia])
        total_pix = sum([p['total'] for p in pedidos_dia if 'pix' in str(p['pagamento']).lower()])
        total_dinheiro = sum([p['total'] for p in pedidos_dia if 'dinheiro' in str(p['pagamento']).lower()])
        total_cartao = sum([p['total'] for p in pedidos_dia if 'cartão' in str(p['pagamento']).lower() or 'cartao' in str(p['pagamento']).lower()])

        col_cx1, col_cx2, col_cx3, col_cx4 = st.columns(4)
        col_cx1.metric("💰 Total Vendido", f"R$ {total_bruto:.2f}")
        col_cx2.metric("⚡ Pix", f"R$ {total_pix:.2f}")
        col_cx3.metric("💵 Dinheiro", f"R$ {total_dinheiro:.2f}")
        col_cx4.metric("💳 Cartão", f"R$ {total_cartao:.2f}")

        st.divider()
        st.markdown("##### 🧮 Conciliação Físico x Esperado (Gaveta)")
        
        col_cxf1, col_cxf2 = st.columns(2)
        with col_cxf1:
            fundo_troco = st.number_input("Fundo de Troco / Abertura (R$):", min_value=0.0, value=50.0, step=10.0)
            sangrias = st.number_input("Retiradas / Sangrias do Caixa (R$):", min_value=0.0, value=0.0, step=10.0)
            dinheiro_esperado = fundo_troco + total_dinheiro - sangrias
            st.info(f"💵 Dinheiro esperado na gaveta: **R$ {dinheiro_esperado:.2f}**")
            
        with col_cxf2:
            dinheiro_contado = st.number_input("Valor Contado na Gaveta (R$):", min_value=0.0, value=dinheiro_esperado, step=1.0)
            diferenca_caixa = dinheiro_contado - dinheiro_esperado
            
            if diferenca_caixa == 0:
                st.success("✅ Caixa sem divergência (Bateu 100%)!")
            elif diferenca_caixa > 0:
                st.warning(f"⚠️ Sobra no caixa de: R$ {diferenca_caixa:.2f}")
            else:
                st.error(f"❌ Falta no caixa de: R$ {abs(diferenca_caixa):.2f}")

        if st.button("🔒 Realizar Fechamento Oficial do Dia", type="primary"):
            st.success(f"Fechamento do dia {data_caixa} concluído e gravado com sucesso!")

# ==========================================
# VISÃO DO CLIENTE (INTERFACE PRINCIPAL)
# ==========================================
else:
    st.markdown("""
        <div class='app-header'>
            <h1>🍽️ Restaurante Digital</h1>
            <p>Monte seu pedido clicando nas opções ou falando por voz/texto inteligente!</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_cli1, col_cli2 = st.columns(2)
    with col_cli1:
        nome_cliente = st.text_input("Seu Nome:")
    with col_cli2:
        telefone_cliente = st.text_input("Seu Telefone / WhatsApp com DDD:")

    horario_retirada = st.text_input("Horário Desejado para Retirada:", value="12:00")

    if "carrinho_atual" not in st.session_state:
        st.session_state.carrinho_atual = []

    st.markdown("---")
    if len(st.session_state.carrinho_atual) > 0:
        st.info(f"🛒 **Seu carrinho contém {len(st.session_state.carrinho_atual)} item(ns).** Role até o final para enviar.")

    modo_pedido = st.radio("Como prefere fazer o seu pedido?", ["📝 Modo Tradicional (Manual)", "🎙️ Modo Inteligente por Voz / Texto Livre"], horizontal=True)

    if modo_pedido == "📝 Modo Tradicional (Manual)":
        st.markdown("### 🥗 1️⃣ Monte a sua Refeição")
        k = st.session_state.form_refeicao_key

        carnes_rend_cliente = carregar_carnes_rendimento()
        carnes_disponiveis_cardapio = [c['nome_carne'] for c in carnes_rend_cliente if float(c['qtd_atual_disponivel']) > 0]
        
        if not carnes_disponiveis_cardapio:
            st.warning("⚠️ No momento todas as carnes estão esgotadas no estoque!")
            carnes_disponiveis_cardapio = ["Indisponível"]

        with st.container():
            col_qtd, col_carne = st.columns([1, 3])
            with col_qtd:
                quantidade = st.number_input("Quantidade:", min_value=0, value=0, step=1, key=f"qtd_marmita_{k}")
            with col_carne:
                carne_escolhida = st.selectbox("Escolha a Opção de Carne:", carnes_disponiveis_cardapio, key=f"carne_sel_{k}")
            
            tipo_arroz_feijao = st.radio("Escolha a Base do Prato:", menu_diario["tipos_arroz"], horizontal=True, key=f"base_sel_{k}")

            st.markdown("**Acompanhamentos:** (desmarque se **NÃO** desejar)")
            acomps_removidos = []
            cols_acomp = st.columns(3)
            for index, acrod in enumerate(menu_diario["acompanhamentos_padrao"]):
                col_target = cols_acomp[index % 3]
                if not col_target.checkbox(f"Incluir {acrod}", value=True, key=f"acomp_{acrod}_{k}"):
                    acomps_removidos.append(acrod)
                    
            obs_marmita = st.text_input("Observação / Preferência:", key=f"obs_input_{k}")

            if st.button("➕ Adicionar Refeição ao Carrinho", type="primary"):
                if not nome_cliente or not telefone_cliente:
                    st.error("Preencha seu Nome e Telefone.")
                elif quantidade <= 0:
                    st.error("Selecione quantidade maior que 0.")
                elif carne_escolhida == "Indisponível":
                    st.error("Essa carne está esgotada.")
                else:
                    estoque_carne_max = 999.0
                    for cr in carnes_rend_cliente:
                        if cr['nome_carne'] == carne_escolhida:
                            estoque_carne_max = float(cr['qtd_atual_disponivel'])

                    if quantidade > estoque_carne_max:
                        st.error(f"❌ Quantidade indisponível! Restam apenas {int(estoque_carne_max)} marmitas de '{carne_escolhida}' em estoque.")
                    else:
                        preco_unit = float(menu_diario["preco_marmita"])
                        preco_total_item = preco_unit * quantidade
                        
                        base_simp = tipo_arroz_feijao.lower()
                        if "misturado" in base_simp or "baião" in base_simp:
                            base_simp = "com arroz misturado"
                        
                        desc_principal = f"{quantidade} {carne_escolhida.lower()} {base_simp}"
                        detalhes = []
                        if acomps_removidos:
                            detalhes.append(f"sem {', '.join(acomps_removidos).lower()}")
                        if obs_marmita:
                            detalhes.append(obs_marmita)
                            
                        st.session_state.carrinho_atual.append({
                            "quantidade": quantidade,
                            "item_principal": desc_principal,
                            "detalhes": " e ".join(detalhes).capitalize() if detalhes else "",
                            "preco": preco_total_item
                        })
                        st.session_state.form_refeicao_key += 1
                        st.success("Refeição adicionada ao carrinho!")
                        st.rerun()

        st.divider()
        st.markdown("### 🥤 2️⃣ Bebidas e Sucos Naturais (Opcional)")
        
        tipo_bebida_aba = st.radio("Qual tipo de bebida deseja escolher?", ["🥤 Refrigerantes & Outros (Estoque)", "🧊 Sucos Naturais Feitos na Hora"], horizontal=True)

        if tipo_bebida_aba == "🥤 Refrigerantes & Outros (Estoque)":
            estoque_cliente = carregar_estoque()
            refris_outros = [i for i in estoque_cliente if i["categoria"] == "Bebidas" and i["qtd"] > 0]

            if not refris_outros:
                st.info("Nenhum refrigerante ou bebida disponível no momento.")
            else:
                kb = st.session_state.form_suco_key
                with st.form(key=f"form_refrig_cliente_{kb}"):
                    escolha_refrig = st.selectbox("Escolha sua Bebida:", [f"{r['item']} (R$ {r['preco_unitario']:.2f} - Estoque: {int(r['qtd'])})" for r in refris_outros], key=f"sel_refrig_{kb}")
                    
                    col_qb1, col_qb2 = st.columns(2)
                    with col_qb1:
                        qtd_bebida = st.number_input("Quantidade:", min_value=1, value=1, step=1, key=f"qtd_beb_{kb}")
                    with col_qb2:
                        obs_bebida = st.text_input("Preferência (ex: Gelada):", key=f"obs_beb_{kb}")

                    if st.form_submit_button("➕ Adicionar Refrigerante ao Carrinho", type="primary"):
                        if not nome_cliente or not telefone_cliente:
                            st.error("Preencha seu Nome e Telefone.")
                        else:
                            item_nome = escolha_refrig.split(" (R$")[0]
                            preco_b, est_max = 0.0, 0.0
                            for r in refris_outros:
                                if r["item"] == item_nome:
                                    preco_b, est_max = float(r["preco_unitario"]), float(r["qtd"])

                            if qtd_bebida > est_max:
                                st.error(f"❌ Estoque insuficiente! Restam apenas {int(est_max)} unidade(s) de '{item_nome}'.")
                            else:
                                st.session_state.carrinho_atual.append({
                                    "quantidade": qtd_bebida,
                                    "item_principal": f"{qtd_bebida}x {item_nome}" + (f" ({obs_bebida})" if obs_bebida else ""),
                                    "detalhes": "",
                                    "preco": preco_b * qtd_bebida
                                })
                                st.session_state.form_suco_key += 1
                                st.success("Refrigerante adicionado com sucesso!")
                                st.rerun()

        else:
            # SUCOS NATURAIS
            sabores_disponiveis = list(set([k.split(" - ")[0] for k in precos_sucos.keys()]))
            if not sabores_disponiveis:
                sabores_disponiveis = ["Acerola", "Cajá", "Maracujá"]

            ks = st.session_state.form_suco_key
            with st.form(key=f"form_suco_nat_{ks}"):
                col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
                with col_s1:
                    sabor_suco = st.selectbox("Sabor do Suco Natural:", sorted(sabores_disponiveis))
                with col_s2:
                    tamanho_suco = st.selectbox("Tamanho:", ["Copo de 300 ml", "Jarra de 1 L"])
                with col_s3:
                    qtd_suco = st.number_input("Qtd:", min_value=1, value=1, step=1)
                    
                chave_tamanho_busca = "Copo (300 ml)" if "Copo" in tamanho_suco else "Jarra (1 L)"
                chave_preco = f"{sabor_suco} - {chave_tamanho_busca}"
                preco_unit_suco = float(precos_sucos.get(chave_preco, 7.00))
                preco_total_suco = preco_unit_suco * qtd_suco
                
                ponto_acucar = st.radio("Açúcar:", ["Com Açúcar", "Sem Açúcar", "Pouco Açúcar"], horizontal=True)
                st.info(f"Valor Total ({qtd_suco}x): **R$ {preco_total_suco:.2f}**")

                if st.form_submit_button("➕ Adicionar Suco Natural ao Carrinho", type="primary"):
                    if not nome_cliente or not telefone_cliente:
                        st.error("Por favor, preencha o seu Nome e Telefone acima antes de adicionar.")
                    else:
                        tipo_recipiente = "copo" if "copo" in tamanho_suco.lower() else "jarra"
                        unidade_medida = "300 ml" if "copo" in tamanho_suco.lower() else "1 L"
                        
                        desc_suco = f"{qtd_suco} {tipo_recipiente}(s) de {unidade_medida} de suco de {sabor_suco.lower()} ({ponto_acucar.lower()})"
                        
                        st.session_state.carrinho_atual.append({
                            "quantidade": qtd_suco,
                            "item_principal": desc_suco,
                            "detalhes": "",
                            "preco": preco_total_suco
                        })
                        st.session_state.form_suco_key += 1
                        st.success("✅ Suco Natural adicionado ao carrinho com sucesso!")
                        st.rerun()

    else:
        st.markdown("### 🎙️ Fale ou Digite o seu Pedido Completo")
        texto_fala = st.text_area("Digite ou dite o pedido:")
        if st.button("⚡ Processar Pedido"):
            if not nome_cliente or not telefone_cliente:
                st.error("Preencha Nome e Telefone.")
            else:
                for item_det in processar_fala_inteligente(texto_fala, float(menu_diario["preco_marmita"]), precos_sucos):
                    st.session_state.carrinho_atual.append(item_det)
                st.success("Pedido inteligente adicionado!")
                st.rerun()

    st.divider()
    st.markdown("### 🛒 Seu Pedido Atual")
    if not st.session_state.carrinho_atual:
        st.info("Carrinho vazio.")
    else:
        total_geral = 0.0
        for i, item in enumerate(st.session_state.carrinho_atual):
            col_c1, col_c2, col_c3 = st.columns([3, 1, 1])
            with col_c1:
                st.write(f"• **{item['item_principal']}**")
            with col_c2:
                st.write(f"R$ {item['preco']:.2f}")
            with col_c3:
                if st.button("Remover", key=f"rem_{i}"):
                    st.session_state.carrinho_atual.pop(i)
                    st.rerun()
            total_geral += item["preco"]
            
        st.markdown(f"### 💰 **Total: R$ {total_geral:.2f}**")
        
        st.divider()
        forma_pagamento = st.selectbox("Forma de Pagamento:", ["Pix", "Dinheiro", "Cartão na Retirada"])
        info_formal = st.selectbox("Deseja informação formal / nota?", ["Não", "Sim"])

        if st.button("🚀 Finalizar e Enviar Pedido via WhatsApp", type="primary"):
            if not nome_cliente or not telefone_cliente:
                st.error("Informe seu Nome e Telefone.")
            else:
                linhas = [f"{it['item_principal']} - R$ {it['preco']:.2f}" for it in st.session_state.carrinho_atual]
                texto_itens = "\n\n".join(linhas)
                
                salvar_pedido(date.today(), nome_cliente, telefone_cliente, horario_retirada, texto_itens.replace("\n", " | "), total_geral, forma_pagamento, info_formal)
                
                link_wa = f"https://wa.me/5599981370792?text=" + urllib.parse.quote(f"NOVO PEDIDO:\nCliente: {nome_cliente}\nRetirada: {horario_retirada}\n\n{texto_itens}\n\nPagamento: {forma_pagamento}\nTotal: R$ {total_geral:.2f}")
                st.session_state.carrinho_atual = []
                st.success("Pedido registrado com sucesso!")
                st.markdown(f"### 👉 [Clique aqui para abrir o WhatsApp]({link_wa})", unsafe_allow_html=True)

# ==========================================
# BOTÃO DISCRETO PARA ENTRAR COMO ADMINISTRADOR
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("---")
with st.expander("🔐 Acesso Administrativo"):
    senha_digitada = st.text_input("Senha de Administrador:", type="password", key="adm_pass_input")
    if st.button("🔑 Entrar no Painel"):
        if senha_digitada == "1234":
            st.session_state.modo_admin = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Senha incorreta!")
