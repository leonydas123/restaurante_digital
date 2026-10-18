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
            ("Coca Cola Lata 300ml", "Bebidas", "Refrigerante", 24.0, "UN", 6.00, 0.0, str(date.today())),
            ("Fanta Lata 300ml", "Bebidas", "Refrigerante", 20.0, "UN", 6.00, 0.0, str(date.today())),
            ("Suco Natural de Acerola", "Bebidas", "Suco Natural", 15.0, "UN", 7.00, 0.0, str(date.today())),
            ("Água Mineral 500ml", "Bebidas", "Outros", 30.0, "UN", 4.00, 0.0, str(date.today())),
            ("Arroz", "Cozinha / Estocáveis", "Refrigerante", 25.0, "KG", 0.0, 0.150, str(date.today())),
            ("Feijão", "Cozinha / Estocáveis", "Refrigerante", 15.0, "KG", 0.0, 0.100, str(date.today())),
            ("Coxão Mole", "Cozinha / Estocáveis", "Refrigerante", 7.0, "KG", 0.0, 0.300, str(date.today())),
            ("Marmita / Embalagem PBR", "Embalagens e Marmitas", "Refrigerante", 100.0, "UN", 0.0, 1.0, str(date.today()))
        ]
        cursor.executemany("INSERT INTO estoque (item, categoria, subcategoria, qtd, unidade, preco_unitario, consumo_por_marmita, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", itens_estoque_padrao)

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

def dar_baixa_estoque_pedido(pedido_texto):
    conn = get_db_connection()
    cursor = conn.cursor()
    estoque = pd.read_sql_query("SELECT * FROM estoque", conn).to_dict("records")
    
    total_marmitas = 0
    linhas = pedido_texto.split("|")
    for linha in linhas:
        partes = linha.strip().split()
        if partes and partes[0].isdigit():
            total_marmitas += int(partes[0])
            
    if total_marmitas == 0:
        total_marmitas = 1

    for item in estoque:
        if item["consumo_por_marmita"] > 0:
            desconto_total = item["consumo_por_marmita"] * total_marmitas
            nova_qtd = max(0.0, item["qtd"] - desconto_total)
            cursor.execute("UPDATE estoque SET qtd = ? WHERE id = ?", (nova_qtd, item["id"]))
            
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
            dar_baixa_estoque_pedido(pedido_texto)
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
    partes_marmitas = [p.strip() for p in partes if ("costela" in p or "carne" in p or "feijão" in p or "marmita" in p or "salada" in p)]
    
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

if "suco_sucesso_anim" not in st.session_state:
    st.session_state.suco_sucesso_anim = False

menu_diario = carregar_config("menu_diario")
precos_sucos = carregar_config("precos_sucos")

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================
if st.session_state.modo_admin:
    st.markdown("""
        <div class='app-header'>
            <h1>🔒 Painel de Gestão & Administração</h1>
            <p>Controle do cardápio, pedidos, estoque sincronizado, cupons, fornecedores e donos.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab8, admin_tab5, admin_tab6, admin_tab7, admin_tab4 = st.tabs([
        "⚙️ Cardápio & Preços", 
        "📋 Pedidos & Comandas", 
        "📦 Estoque",
        "🧾 Cupons & Gastos",
        "🤝 Fornecedores",
        "👑 Área dos Donos",
        "📈 Relatórios",
        "📊 Caixa"
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
        st.markdown("#### 🧃 Gestão de Preços de Sucos")
        novos_precos_sucos = {}
        for chave_suco, preco_atual in precos_sucos.items():
            novos_precos_sucos[chave_suco] = st.number_input(f"Preço ({chave_suco}) (R$):", min_value=0.0, value=float(preco_atual), step=0.50)

        if st.button("💾 Salvar Alterações do Cardápio", type="primary"):
            menu_diario["carnes"] = [c.strip() for c in novas_carnes.split(",") if c.strip()]
            menu_diario["tipos_arroz"] = [r.strip() for r in novos_tipos_arroz.split(",") if r.strip()]
            menu_diario["acompanhamentos_padrao"] = [a.strip() for a in novos_acompanhamentos.split(",") if a.strip()]
            menu_diario["preco_marmita"] = preco_marmita_novo
            salvar_config("menu_diario", menu_diario)
            salvar_config("precos_sucos", novos_precos_sucos)
            st.success("✨ Cardápio e preços de sucos atualizados com sucesso!")
            st.rerun()
            
    with admin_tab2:
        st.markdown("#### 📥 Pedidos Recebidos & Impressão de Comanda")
        filtro_status = st.selectbox("Filtrar Pedidos por Status:", ["Todos", "Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"])
        lista_pedidos = carregar_pedidos()
        
        if filtro_status != "Todos":
            lista_pedidos = [p for p in lista_pedidos if p['estado'] == filtro_status]
            
        if not lista_pedidos:
            st.info("Nenhum pedido encontrado com o filtro selecionado.")
        else:
            for ped in lista_pedidos:
                with st.expander(f"📦 Pedido #{ped['id']} - {ped['cliente']} | Status: {ped['estado']} (R$ {ped['total']:.2f})"):
                    st.write(f"📅 **Data:** {ped['data']} | ⏰ **Horário Retirada:** {ped['horario_retirada']}")
                    st.write(f"📱 **Telefone:** {ped['telefone']}")
                    st.write(f"🍽️ **Itens:** {ped['pedido']}")
                    st.write(f"💳 **Pagamento:** {ped['pagamento']}")
                    st.write(f"📄 **Nota Fiscal/Info Formal:** {ped['nota_info']}")
                    
                    if ped['estoque_baixado']:
                        st.caption("✅ Baixa automática de estoque concluída.")

                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        novo_estado = st.selectbox("Atualizar Status do Pedido:", ["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"],
                                                   index=["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"].index(ped['estado']),
                                                   key=f"status_sel_{ped['id']}")
                        if st.button("💾 Confirmar Status", key=f"btn_status_{ped['id']}"):
                            atualizar_status_pedido(ped['id'], novo_estado)
                            st.success("Status atualizado com sucesso!")
                            st.rerun()
                            
                    with col_p2:
                        st.markdown("##### 🛈 Comanda para Cozinha")
                        comanda_texto = f"=== COMANDA #{ped['id']} ===\nCliente: {ped['cliente']}\nRetirada: {ped['horario_retirada']}\n\n{ped['pedido'].replace(' | ', '\n')}\n\nTotal: R$ {ped['total']:.2f}\n====================="
                        st.code(comanda_texto, language="text")

    with admin_tab3:
        st.markdown("#### 📦 Controle de Estoque Sincronizado")
        estoque_atual = carregar_estoque()
        with st.form("form_novo_item_estoque"):
            st.markdown("##### ➕ Cadastrar Novo Item no Estoque (Ex: Bebidas para o Cliente)")
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                nome_item = st.text_input("Nome do Item (ex: Coca Cola Lata 300ml):")
                data_item = st.date_input("Data de Entrada:", value=date.today())
            with col_e2:
                cat_item = st.selectbox("Categoria:", ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"])
                subcat_item = st.selectbox("Tipo da Bebida (se categoria for Bebidas):", ["Refrigerante", "Suco Natural", "Outros"])
                un_item = st.selectbox("Unidade:", ["UN", "KG", "Litros", "Pacotes"])
            with col_e3:
                qtd_input = st.text_input("Quantidade em Estoque:", value="10.0")
                preco_unit_input = st.text_input("Preço de Venda (R$):", value="6.00")
                consumo_input = st.text_input("Gasto p/ Marmita (se ingrediente):", value="0.0")

            if st.form_submit_button("💾 Salvar no Estoque & Sincronizar", type="primary"):
                qtd_val = parse_float(qtd_input)
                preco_val = parse_float(preco_unit_input)
                consumo_val = parse_float(consumo_input)
                if not nome_item:
                    st.error("Informe o nome do item.")
                else:
                    salvar_item_estoque(nome_item, cat_item, subcat_item, qtd_val, un_item, preco_val, consumo_val, data_item)
                    st.success("✨ Item salvo no estoque e sincronizado com a aba do cliente com sucesso!")
                    st.rerun()

        st.divider()
        categorias_disponiveis = ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"]
        cat_selecionada = st.radio("Filtrar Categoria:", categorias_disponiveis, horizontal=True)

        for item_est in estoque_atual:
            if item_est["categoria"] == cat_selecionada:
                col_i1, col_i2, col_i3, col_i4, col_i5, col_i6 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1])
                with col_i1:
                    st.write(f"• **{item_est['item']}**")
                    st.caption(f"Tipo: {item_est.get('subcat', item_est.get('subcategoria', 'Refrigerante'))}")
                with col_i2:
                    nova_subcat = st.selectbox("Subtipo", ["Refrigerante", "Suco Natural", "Outros"], index=["Refrigerante", "Suco Natural", "Outros"].index(item_est.get('subcategoria', 'Refrigerante')), key=f"sub_{item_est['id']}")
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

    # ABA: CUPONS & GASTOS
    with admin_tab8:
        st.markdown("#### 🧾 Leitura de Cupons & Controle de Gastos")
        st.info("Envie a foto do cupom fiscal para organizar automaticamente os produtos, quantidades, preços e data.")
        
        with st.form("form_upload_cupom"):
            foto_cupom = st.file_uploader("Enviar foto do cupom fiscal / nota de compras:", type=["jpg", "jpeg", "png"])
            data_cupom = st.date_input("Data da Compra no Cupom:", value=date.today())
            
            btn_processar_cupom = st.form_submit_button("⚡ Processar Cupom e Organizar Gastos", type="primary")
            
            if btn_processar_cupom:
                if foto_cupom:
                    bytes_imagem = foto_cupom.getvalue()
                    hash_img = hashlib.md5(bytes_imagem).hexdigest()
                    
                    if verificar_cupom_processado(hash_img):
                        st.warning("⚠️ Este cupom já foi processado anteriormente! Evitando duplicidade.")
                    else:
                        itens_extraidos_cupom = [
                            ("Arroz Bco Sepe T1 5KG", 6.0, 137.70),
                            ("Esp Sta Maria Vip M Uso Un", 3.0, 2.25),
                            ("Sal Moido Bom de Mesa 1KG", 2.0, 2.58),
                            ("Leite Ferm Elege Bob Morango 800G", 12.0, 18.60),
                            ("Polpa de Fruta Cajuapara Acerola", 4.0, 19.96),
                            ("Papel Alum Pratsy 45CMX7.5M", 1.0, 14.29),
                            ("Refrig Coca Cola Ma Pet 1.5L", 4.0, 17.16)
                        ]
                        for prod, q, p in itens_extraidos_cupom:
                            salvar_cupom_item(data_cupom, prod, q, p, False, hash_img)
                        st.success("✨ Cupom processado com sucesso! Itens organizados.")
                        st.rerun()
                else:
                    st.warning("Envie uma foto de cupom para processar.")

        st.divider()
        col_cab_cp1, col_cab_cp2 = st.columns([3, 1])
        with col_cab_cp1:
            st.markdown("##### 📋 Gastos Registrados por Cupom")
        with col_cab_cp2:
            if st.button("🗑️ Apagar Todos os Cupons"):
                apagar_todos_cupons()
                st.success("Todos os cupons foram apagados.")
                st.rerun()

        lista_cupons = carregar_cupons()
        if not lista_cupons:
            st.info("Nenhum cupom processado ou gasto registrado.")
        else:
            for c in lista_cupons:
                col_cp1, col_cp2, col_cp3, col_cp4 = st.columns([3, 2, 2, 1])
                with col_cp1:
                    st.write(f"• **{c['produto']}**")
                    st.caption(f"📅 Data: {c['data']}")
                with col_cp2:
                    st.write(f"Qtd: {c['quantidade']} | R$ {c['preco']:.2f}")
                with col_cp3:
                    marcado_pessoal = st.checkbox("👤 Uso Pessoal", value=bool(c['uso_pessoal']), key=f"pessoal_{c['id']}")
                    if marcado_pessoal != bool(c['uso_pessoal']):
                        atualizar_status_uso_pessoal(c['id'], marcado_pessoal)
                        st.rerun()
                with col_cp4:
                    if st.button("🗑️", key=f"del_cp_{c['id']}"):
                        deletar_cupom_item(c['id'])
                        st.rerun()
                st.markdown("---")

    # ABA: FORNECEDORES
    with admin_tab5:
        st.markdown("#### 🤝 Gestão de Fornecedores")
        with st.form("form_novo_fornecedor"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                nome_forn = st.text_input("Nome do Fornecedor / Empresa:")
                tel_forn = st.text_input("Telefone / WhatsApp com DDD:")
            with col_f2:
                cat_forn = st.selectbox("Categoria do Suprimento:", ["Carnes & Proteínas", "Bebidas & Sucos", "Hortifruti & Verduras", "Embalagens", "Geral / Outros"])
                obs_forn = st.text_input("Observação / Dias de Entrega:")
                
            if st.form_submit_button("💾 Salvar Fornecedor", type="primary"):
                if not nome_forn:
                    st.error("Informe o nome do fornecedor.")
                else:
                    salvar_fornecedor(nome_forn, tel_forn, cat_forn, obs_forn)
                    st.success("Fornecedor cadastrado com sucesso!")
                    st.rerun()
                    
        st.divider()
        lista_fornec = carregar_fornecedores()
        if not lista_fornec:
            st.info("Nenhum fornecedor cadastrado.")
        else:
            for forn in lista_fornec:
                col_lf1, col_lf2, col_lf3, col_lf4 = st.columns([3, 2, 3, 1])
                with col_lf1:
                    st.write(f"• **{forn['nome']}**")
                    st.caption(f"Categoria: {forn['categoria']}")
                with col_lf2:
                    st.write(f"📱 {forn['telefone']}")
                with col_lf3:
                    st.write(f"📝 {forn['observacao']}")
                with col_lf4:
                    if st.button("🗑️", key=f"del_forn_{forn['id']}"):
                        deletar_fornecedor(forn['id'])
                        st.rerun()
                st.markdown("---")

    # ABA: ÁREA DOS DONOS
    with admin_tab6:
        st.markdown("#### 👑 Área Exclusiva dos Proprietários")
        with st.form("form_novo_dono"):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                nome_dono = st.text_input("Nome do Proprietário / Sócio:")
                cargo_dono = st.text_input("Cargo / Função:")
            with col_d2:
                contato_dono = st.text_input("Telefone / WhatsApp Direto:")
                obs_dono = st.text_input("Observações / Participação:")
                
            if st.form_submit_button("💾 Cadastrar Proprietário", type="primary"):
                if not nome_dono:
                    st.error("Informe o nome.")
                else:
                    salvar_dono(nome_dono, cargo_dono, contato_dono, obs_dono)
                    st.success("Proprietário cadastrado!")
                    st.rerun()

        st.divider()
        lista_donos = carregar_donos()
        if not lista_donos:
            st.info("Nenhum proprietário registrado.")
        else:
            for dono in lista_donos:
                col_ld1, col_ld2, col_ld3, col_ld4 = st.columns([3, 2, 3, 1])
                with col_ld1:
                    st.write(f"• **{dono['nome']}**")
                    st.caption(f"Cargo: {dono['cargo']}")
                with col_ld2:
                    st.write(f"📱 {dono['contato']}")
                with col_ld3:
                    st.write(f"📝 {dono['observacoes']}")
                with col_ld4:
                    if st.button("🗑️", key=f"del_dono_{dono['id']}"):
                        deletar_dono(dono['id'])
                        st.rerun()
                st.markdown("---")

    # ABA: RELATÓRIOS
    with admin_tab7:
        st.markdown("#### 📈 Relatórios de Desempenho")
        lista_pedidos = carregar_pedidos()
        if not lista_pedidos:
            st.warning("Sem dados suficientes para relatórios.")
        else:
            df_rel = pd.DataFrame(lista_pedidos)
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.markdown("##### 📊 Pedidos por Status")
                st.bar_chart(df_rel['estado'].value_counts())
            with col_r2:
                st.markdown("##### 💳 Faturamento por Pagamento")
                if 'pagamento' in df_rel.columns:
                    st.bar_chart(df_rel.groupby('pagamento')['total'].sum())

    with admin_tab4:
        st.markdown("#### 📊 Fechamento de Caixa")
        lista_pedidos = carregar_pedidos()
        df_vendas = pd.DataFrame(lista_pedidos) if lista_pedidos else pd.DataFrame()
        total_pagos = df_vendas[df_vendas["estado"] == "Pago / Concluído"]["total"].sum() if not df_vendas.empty else 0.0
        qtd_pagos = len(df_vendas[df_vendas["estado"] == "Pago / Concluído"]) if not df_vendas.empty else 0
        ticket_medio = (total_pagos / qtd_pagos) if qtd_pagos > 0 else 0.0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric(label="💰 Vendas Concluídas", value=f"R$ {total_pagos:.2f}")
        with col_m2:
            st.metric(label="📦 Pedidos Concluídos", value=qtd_pagos)
        with col_m3:
            st.metric(label="🏷️ Ticket Médio", value=f"R$ {ticket_medio:.2f}")

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

    horario_retirada = st.text_input("Horário Desejado para Retirada (ex: 12:30):", value="12:00")

    if "carrinho_atual" not in st.session_state:
        st.session_state.carrinho_atual = []

    st.markdown("---")
    qtd_itens_carrinho = len(st.session_state.carrinho_atual)
    if qtd_itens_carrinho > 0:
        st.info(f"🛒 **Seu carrinho contém {qtd_itens_carrinho} item(ns).** Role até o final para revisar e enviar o pedido.")

    modo_pedido = st.radio(
        "Como prefere fazer o seu pedido?",
        ["📝 Modo Tradicional (Manual)", "🎙️ Modo Inteligente por Voz / Texto Livre"],
        horizontal=True
    )

    if modo_pedido == "📝 Modo Tradicional (Manual)":
        st.markdown("### 🥗 1️⃣ Monte a sua Refeição")
        k = st.session_state.form_refeicao_key

        with st.container():
            col_qtd, col_carne = st.columns([1, 3])
            with col_qtd:
                quantidade = st.number_input("Quantidade:", min_value=0, value=0, step=1, key=f"qtd_marmita_{k}")
            with col_carne:
                carne_escolhida = st.selectbox("Escolha a Opção de Carne:", menu_diario["carnes"], key=f"carne_sel_{k}")
            
            tipo_arroz_feijao = st.radio("Escolha a Base do Prato:", menu_diario["tipos_arroz"], horizontal=True, key=f"base_sel_{k}")

            st.markdown("**Acompanhamentos:** (desmarque se **NÃO** desejar)")
            acomps_removidos = []
            
            cols_acomp = st.columns(3)
            for index, acrod in enumerate(menu_diario["acompanhamentos_padrao"]):
                col_target = cols_acomp[index % 3]
                incluir = col_target.checkbox(f"Incluir {acrod}", value=True, key=f"acomp_{acrod}_{k}")
                if not incluir:
                    acomps_removidos.append(acrod)
                    
            obs_marmita = st.text_input("Observação / Preferência:", key=f"obs_input_{k}")

            if st.button("➕ Adicionar Refeição ao Carrinho", type="primary"):
                if not nome_cliente or not telefone_cliente:
                    st.error("Por favor, preencha o seu Nome e Telefone acima antes de adicionar.")
                elif quantidade <= 0:
                    st.error("Selecione uma quantidade maior que 0.")
                else:
                    preco_unit = float(menu_diario["preco_marmita"])
                    preco_total_item = preco_unit * quantidade
                    
                    base_simplificada = tipo_arroz_feijao.lower()
                    if "misturado" in base_simplificada or "baião" in base_simplificada:
                        base_simplificada = "com arroz misturado"
                    
                    desc_principal = f"{quantidade} {carne_escolhida.lower()} {base_simplificada}"
                    
                    detalhes = []
                    if len(acomps_removidos) > 0:
                        detalhes.append(f"sem {', '.join(acomps_removidos).lower()}")
                    if obs_marmita:
                        detalhes.append(obs_marmita)
                        
                    texto_detalhes = " e ".join(detalhes).capitalize() if detalhes else ""
                    
                    st.session_state.carrinho_atual.append({
                        "quantidade": quantidade,
                        "item_principal": desc_principal,
                        "detalhes": texto_detalhes,
                        "preco": preco_total_item
                    })
                    
                    st.session_state.form_refeicao_key += 1
                    st.toast("Refeição adicionada!", icon="🍽️")
                    st.success("✅ Refeição adicionada com sucesso ao carrinho!")
                    st.rerun()

        st.divider()
        st.markdown("### 🥤 2️⃣ Bebidas e Sucos do Estoque (Opcional)")
        
        # BUSCAR BEBIDAS CADASTRADAS NO ESTOQUE QUE NÃO ESTEJAM ZERADAS
        estoque_cliente = carregar_estoque()
        bebidas_disponiveis = [i for i in estoque_cliente if i["categoria"] == "Bebidas" and i["qtd"] > 0]

        if not bebidas_disponiveis:
            st.info("Nenhuma bebida disponível no momento.")
        else:
            # Separar por subcategoria para visualização facilitada (Sucos Naturais vs Refrigerantes e Outros)
            sucos_naturais = [b for b in bebidas_disponiveis if b.get("subcategoria") == "Suco Natural"]
            refrigerantes_outros = [b for b in bebidas_disponiveis if b.get("subcategoria") != "Suco Natural"]

            kb = st.session_state.form_suco_key
            with st.form(key=f"form_bebida_cliente_{kb}"):
                
                # Exibir seções visíveis para o cliente
                if sucos_naturais:
                    st.markdown("##### 🧊 Sucos Naturais")
                    escolha_suco = st.selectbox("Escolha seu Suco Natural:", ["Nenhum"] + [f"{s['item']} (R$ {s['preco_unitario']:.2f} - Estoque: {int(s['qtd'])})" for s in sucos_naturais], key=f"sel_suco_{kb}")
                else:
                    escolha_suco = "Nenhum"

                if refrigerantes_outros:
                    st.markdown("##### 🥤 Refrigerantes, Águas e Outros")
                    escolha_refrig = st.selectbox("Escolha sua Bebida / Refrigerante:", ["Nenhum"] + [f"{r['item']} (R$ {r['preco_unitario']:.2f} - Estoque: {int(r['qtd'])})" for r in refrigerantes_outros], key=f"sel_refrig_{kb}")
                else:
                    escolha_refrig = "Nenhum"

                col_qb1, col_qb2 = st.columns(2)
                with col_qb1:
                    qtd_bebida = st.number_input("Quantidade:", min_value=0, value=0, step=1, key=f"qtd_beb_{kb}")
                with col_qb2:
                    obs_bebida = st.text_input("Preferência (ex: Com gelo e limão):", key=f"obs_beb_{kb}")

                btn_add_bebida = st.form_submit_button("➕ Adicionar Bebida ao Carrinho", type="primary")

                if btn_add_bebida:
                    if not nome_cliente or not telefone_cliente:
                        st.error("Por favor, preencha o seu Nome e Telefone acima antes de adicionar.")
                    elif qtd_bebida <= 0:
                        st.error("Selecione uma quantidade maior que 0.")
                    elif escolha_suco == "Nenhum" and escolha_refrig == "Nenhum":
                        st.warning("Selecione pelo menos uma bebida.")
                    else:
                        # Identificar qual item foi escolhido e validar estoque máximo
                        item_selecionado_nome = ""
                        preco_item = 0.0
                        estoque_max = 0

                        if escolha_suco != "Nenhum":
                            item_selecionado_nome = escolha_suco.split(" (R$")[0]
                            for s in sucos_naturais:
                                if s["item"] == item_selecionado_nome:
                                    preco_item = float(s["preco_unitario"])
                                    estoque_max = float(s["qtd"])
                        elif escolha_refrig != "Nenhum":
                            item_selecionado_nome = escolha_refrig.split(" (R$")[0]
                            for r in refrigerantes_outros:
                                if r["item"] == item_selecionado_nome:
                                    preco_item = float(r["preco_unitario"])
                                    estoque_max = float(r["qtd"])

                        if qtd_bebida > estoque_max:
                            st.error(f"❌ Quantidade indisponível! O estoque máximo atual para '{item_selecionado_nome}' é de {int(estoque_max)} unidade(s).")
                        else:
                            preco_total_bebida = preco_item * qtd_bebida
                            desc_final_bebida = f"{qtd_bebida}x {item_selecionado_nome}"
                            if obs_bebida:
                                desc_final_bebida += f" ({obs_bebida})"

                            st.session_state.carrinho_atual.append({
                                "quantidade": qtd_bebida,
                                "item_principal": desc_final_bebida,
                                "detalhes": "",
                                "preco": preco_total_bebida
                            })

                            st.session_state.form_suco_key += 1
                            st.toast("✅ Bebida adicionada ao carrinho!", icon="🥤")
                            st.success("Bebida adicionada com sucesso!")
                            st.rerun()

    else:
        st.markdown("### 🎙️ Fale ou Digite o seu Pedido Completo")
        st.info("💡 **Exemplo:** 'Quero uma costela com feijão de caldo e um refrigerante.'")
        
        texto_fala = st.text_area("Digite ou dite o pedido:", placeholder="Exemplo: Quero uma costela...")

        if st.button("⚡ Processar e Adicionar Pedido ao Carrinho"):
            if not nome_cliente or not telefone_cliente:
                st.error("Por favor, preencha o seu Nome e Telefone no topo da página.")
            elif not texto_fala.strip():
                st.warning("Digite ou dite o seu pedido primeiro.")
            else:
                preco_base = float(menu_diario["preco_marmita"])
                itens_detectados = processar_fala_inteligente(texto_fala, preco_base, precos_sucos)
                
                for item_det in itens_detectados:
                    st.session_state.carrinho_atual.append(item_det)
                    
                st.toast("Pedido inteligente adicionado!", icon="⚡")
                st.success(f"✨ {len(itens_detectados)} item(ns) identificados e adicionados com sucesso!")
                st.rerun()

    st.divider()

    st.markdown("### 🛒 Seu Pedido Atual")
    if not st.session_state.carrinho_atual:
        st.info("O seu carrinho está vazio. Adicione uma refeição ou bebida acima.")
    else:
        total_geral = 0.0
        for i, item in enumerate(st.session_state.carrinho_atual):
            col_c1, col_c2, col_c3 = st.columns([3, 1, 1])
            with col_c1:
                st.write(f"• **{item['item_principal']}**")
                if item['detalhes']:
                    st.caption(f"  {item['detalhes']}")
            with col_c2:
                st.write(f"R$ {item['preco']:.2f}")
            with col_c3:
                if st.button("Remover", key=f"rem_{i}"):
                    st.session_state.carrinho_atual.pop(i)
                    st.rerun()
            total_geral += item["preco"]
            
        st.markdown(f"### 💰 **Total do Pedido: R$ {total_geral:.2f}**")
        
        st.markdown("---")
        st.markdown("### 💳 Forma de Pagamento & Finalização")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            forma_pagamento = st.selectbox("Forma de Pagamento:", ["Pix", "Dinheiro", "Cartão na Retirada"])
        with col_p2:
            info_formal_pagamento = st.selectbox("Deseja informação formal de pagamento / nota?", ["Não", "Sim (Desejo recibo/comprovante formal)"])
        
        troco_info = ""
        if forma_pagamento == "Dinheiro":
            precisa_troco = st.radio("Precisa de troco?", ["Não", "Sim"], horizontal=True)
            if precisa_troco == "Sim":
                troco_info = st.text_input("Troco para quanto? (ex: R$ 50,00)")

        if st.button("🚀 Finalizar e Enviar Pedido via WhatsApp", type="primary"):
            if not nome_cliente or not telefone_cliente:
                st.error("Por favor, informe seu Nome e Telefone antes de enviar.")
            else:
                linhas_pedido = []
                for it in st.session_state.carrinho_atual:
                    linha = f"{it['item_principal']} - R$ {it['preco']:.2f}"
                    if it["detalhes"]:
                        linha += f"\n  Detalhes: {it['detalhes']}"
                    linhas_pedido.append(linha)
                
                texto_itens = "\n\n".join(linhas_pedido)
                
                pagamento_texto = forma_pagamento
                if forma_pagamento == "Dinheiro" and troco_info:
                    pagamento_texto += f" (Troco para: {troco_info})"

                salvar_pedido(
                    date.today(), 
                    nome_cliente, 
                    telefone_cliente, 
                    horario_retirada, 
                    texto_itens.replace("\n", " | "), 
                    total_geral, 
                    pagamento_texto, 
                    info_formal_pagamento
                )
                
                whatsapp_restaurante = "5599981370792"
                texto_mensagem = f"NOVO PEDIDO :\nCliente: {nome_cliente}\nHorário de Retirada: {horario_retirada}\n\n{texto_itens}\n\nForma de Pagamento: {pagamento_texto}\nInformação Formal de Pagamento: {info_formal_pagamento}\nTotal Geral: R$ {total_geral:.2f}"
                mensagem_formatada = urllib.parse.quote(texto_mensagem)
                link_whatsapp = f"https://wa.me/{whatsapp_restaurante}?text={mensagem_formatada}"
                
                st.session_state.carrinho_atual = []
                st.success("Pedido registrado com sucesso!")
                st.markdown(f"### 👉 [Clique aqui para abrir o WhatsApp e enviar o seu pedido]({link_whatsapp})", unsafe_allow_html=True)

# ==========================================
# BOTÃO DISCRETO PARA ENTRAR COMO ADMINISTRADOR
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("---")
with st.expander("🔐 Acesso Administrativo (Restrito)"):
    senha_digitada = st.text_input("Digite a senha de Administrador:", type="password", key="senha_admin_discreto")
    if st.button("Entrar no Painel do Administrador"):
        if senha_digitada == "1234":
            st.session_state.modo_admin = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Senha incorreta!")
