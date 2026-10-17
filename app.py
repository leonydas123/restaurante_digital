import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import sqlite3
import json
import re

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
            qtd REAL,
            unidade TEXT,
            consumo_por_marmita REAL,
            data TEXT
        )
    """)
    
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
        CREATE TABLE IF NOT EXISTS gastos_donos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            descricao TEXT,
            categoria TEXT,
            valor REAL,
            responsavel TEXT
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
            ("Refrigerante Coca-Cola Lata", "Bebidas", 24.0, "UN", 0.0, str(date.today())),
            ("Refrigerante Fanta Lata", "Bebidas", 24.0, "UN", 0.0, str(date.today())),
            ("Arroz", "Cozinha / Estocáveis", 25.0, "KG", 0.150, str(date.today())),
            ("Feijão", "Cozinha / Estocáveis", 15.0, "KG", 0.100, str(date.today())),
            ("Coxão Mole", "Cozinha / Estocáveis", 7.0, "KG", 0.300, str(date.today())),
            ("Alface / Verduras", "Verduras", 5.0, "KG", 0.080, str(date.today())),
            ("Marmita / Embalagem PBR", "Embalagens e Marmitas", 100.0, "UN", 1.0, str(date.today()))
        ]
        cursor.executemany("INSERT INTO estoque (item, categoria, qtd, unidade, consumo_por_marmita, data) VALUES (?, ?, ?, ?, ?, ?)", itens_estoque_padrao)

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

def salvar_item_estoque(item, categoria, qtd, unidade, consumo, data_ent):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO estoque (item, categoria, qtd, unidade, consumo_por_marmita, data) VALUES (?, ?, ?, ?, ?, ?)",
                   (item, categoria, qtd, unidade, consumo, str(data_ent)))
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

# FORNECEDORES
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

# GASTOS DOS DONOS
def carregar_gastos_donos():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM gastos_donos ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def salvar_gasto_dono(data_gasto, desc, cat, valor, resp):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO gastos_donos (data, descricao, categoria, valor, responsavel) VALUES (?, ?, ?, ?, ?)",
                   (str(data_gasto), desc, cat, float(valor), resp))
    conn.commit()
    conn.close()

def deletar_gasto_dono(id_gasto):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos_donos WHERE id = ?", (id_gasto,))
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
# DESIGN E ESTILO CSS SEGURO E ELEGANTE
# ==========================================
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #1e293b;
    }
    
    .app-header {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        padding: 24px;
        border-radius: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.4);
        margin-bottom: 25px;
    }
    .app-header h1 {
        color: #ffffff !important;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
    }
    .app-header p {
        color: #e6f4ea;
        font-size: 1.05rem;
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
        background-color: #ffffff !important;
        border-radius: 14px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02) !important;
        margin-bottom: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializar sessões
if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

if "acesso_donos_liberado" not in st.session_state:
    st.session_state.acesso_donos_liberado = False

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
            <p>Controle do cardápio, recepção de pedidos, estoque, fornecedores, caixa e área dos donos.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.session_state.acesso_donos_liberado = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab5, admin_tab4, admin_tab6 = st.tabs([
        "⚙️ Cardápio & Preços", 
        "📋 Pedidos & Comandas", 
        "📦 Estoque & Conciliação",
        "🤝 Fornecedores",
        "📊 Fechamento de Caixa",
        "🔑 Área Restrita dos Donos"
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
        lista_pedidos = carregar_pedidos()
        if not lista_pedidos:
            st.info("Nenhum pedido recebido até o momento.")
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
        st.markdown("#### 📦 Controle de Estoque & Conciliação Inteligente")
        
        estoque_atual = carregar_estoque()
        itens_criticos = [i for i in estoque_atual if i['qtd'] <= (5.0 if i['unidade'] == 'KG' else 10.0)]
        if itens_criticos:
            st.markdown("<div style='background-color:#fef2f2; border-left:5px solid #ef4444; padding:14px; border-radius:12px; color:#991b1b; font-weight:600;'>⚠️ ATENÇÃO: Itens com estoque baixo detectados!</div>", unsafe_allow_html=True)
            for ic in itens_criticos:
                st.write(f"• **{ic['item']}**: Restam apenas **{ic['qtd']} {ic['unidade']}**")
            st.divider()

        with st.form("form_novo_item_estoque"):
            st.markdown("##### ➕ Cadastrar Novo Item no Estoque")
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                nome_item = st.text_input("Nome do Item (ex: Fanta Lata, Coxão Mole):")
                data_item = st.date_input("Data de Entrada:", value=date.today())
            with col_e2:
                cat_item = st.selectbox("Categoria:", ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"])
                un_item = st.selectbox("Unidade:", ["KG", "UN", "Litros", "Pacotes"])
            with col_e3:
                qtd_input = st.text_input("Quantidade (ex: 7 ou 7.00):", value="10.0")
                consumo_input = st.text_input("Gasto p/ Marmita (ex: 0.30):", value="0.0")

            if st.form_submit_button("💾 Salvar no Estoque", type="primary"):
                qtd_val = parse_float(qtd_input)
                consumo_val = parse_float(consumo_input)
                if not nome_item:
                    st.error("Informe o nome do item.")
                else:
                    salvar_item_estoque(nome_item, cat_item, qtd_val, un_item, consumo_val, data_item)
                    st.success("Item registrado no estoque!")
                    st.rerun()

        st.divider()
        st.markdown("##### 📋 Gerenciar Estoque por Categoria")
        
        categorias_disponiveis = ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"]
        cat_selecionada = st.radio("Filtrar Categoria:", categorias_disponiveis, horizontal=True)

        for item_est in estoque_atual:
            if item_est["categoria"] == cat_selecionada:
                col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns([2, 2, 2, 2, 1])
                with col_i1:
                    st.write(f"• **{item_est['item']}**")
                    st.caption(f"📅 Entrada: {item_est['data']}")
                with col_i2:
                    nova_cat = st.selectbox("Categoria", categorias_disponiveis, index=categorias_disponiveis.index(item_est["categoria"]), key=f"est_cat_{item_est['id']}")
                    if nova_cat != item_est["categoria"]:
                        atualizar_item_estoque(item_est['id'], "categoria", nova_cat)
                        st.rerun()
                with col_i3:
                    nova_qtd = st.number_input(f"Qtd ({item_est['unidade']})", value=float(item_est['qtd']), step=1.0, key=f"est_qtd_{item_est['id']}")
                    if nova_qtd != item_est["qtd"]:
                        atualizar_item_estoque(item_est['id'], "qtd", nova_qtd)
                with col_i4:
                    novo_consumo = st.number_input("Gasto/Marmita", value=float(item_est['consumo_por_marmita']), step=0.01, key=f"est_cons_{item_est['id']}")
                    if novo_consumo != item_est["consumo_por_marmita"]:
                        atualizar_item_estoque(item_est['id'], "consumo_por_marmita", novo_consumo)
                with col_i5:
                    if st.button("🗑️", key=f"del_est_{item_est['id']}"):
                        deletar_item_estoque(item_est['id'])
                        st.rerun()
                st.markdown("---")

    with admin_tab5:
        st.markdown("#### 🤝 Gestão de Fornecedores")
        with st.form("form_novo_fornecedor"):
            st.markdown("##### ➕ Cadastrar Novo Fornecedor")
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
        st.markdown("##### 📋 Fornecedores Cadastrados")
        lista_fornec = carregar_fornecedores()
        if not lista_fornec:
            st.info("Nenhum fornecedor cadastrado até o momento.")
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

    with admin_tab4:
        st.markdown("#### 📊 Fechamento de Caixa & Resumo Financeiro")
        lista_pedidos = carregar_pedidos()
        df_vendas = pd.DataFrame(lista_pedidos) if lista_pedidos else pd.DataFrame()
        
        total_pagos = df_vendas[df_vendas["estado"] == "Pago / Concluído"]["total"].sum() if not df_vendas.empty else 0.0
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(label="💰 Vendas Concluídas", value=f"R$ {total_pagos:.2f}")
        with col_m2:
            st.metric(label="📦 Total de Pedidos Faturados", value=len(df_vendas))

    # ABA RESTRITA DOS DONOS (PROTEGIDA POR SENHA)
    with admin_tab6:
        st.markdown("#### 🔑 Área Restrita dos Sócios & Gestão de Funcionários")
        
        if not st.session_state.acesso_donos_liberado:
            st.warning("⚠️ Esta área é restrita e contém informações financeiras confidenciais e gastos com colaboradores.")
            senha_donos = st.text_input("Digite a Senha Exclusiva dos Donos:", type="password", key="input_senha_donos")
            if st.button("Liberar Acesso dos Donos"):
                if senha_donos == "9988": # Senha específica dos donos
                    st.session_state.acesso_donos_liberado = True
                    st.success("Acesso liberado com sucesso!")
                    st.rerun()
                else:
                    st.error("Senha dos donos incorreta!")
        else:
            st.success("🔓 Área dos Donos Autenticada")
            
            with st.form("form_gasto_dono"):
                st.markdown("##### ➕ Registrar Gasto / Pró-Labore / Funcionários")
                col_gd1, col_gd2 = st.columns(2)
                with col_gd1:
                    desc_gasto = st.text_input("Descrição do Gasto (ex: Salario Cozinheiro, Pró-labore):")
                    cat_gasto = st.selectbox("Categoria:", ["Funcionários & Salários", "Retirada de Sócios", "Manutenção", "Impostos & Taxas", "Outros"])
                with col_gd2:
                    valor_gasto = st.text_input("Valor (R$):", value="0.00")
                    resp_gasto = st.text_input("Responsável / Beneficiário:")
                    data_gasto = st.date_input("Data:", value=date.today())

                if st.form_submit_button("💾 Salvar Registro Financeiro", type="primary"):
                    val_convertido = parse_float(valor_gasto)
                    if not desc_gasto or val_convertido <= 0:
                        st.error("Preencha a descrição e um valor válido.")
                    else:
                        salvar_gasto_dono(data_gasto, desc_gasto, cat_gasto, val_convertido, resp_gasto)
                        st.success("Gasto registrado com sucesso na área restrita!")
                        st.rerun()

            st.divider()
            st.markdown("##### 📋 Histórico de Gastos & Funcionários Registrados")
            lista_gastos = carregar_gastos_donos()
            if not lista_gastos:
                st.info("Nenhum registro encontrado.")
            else:
                total_gastos_geral = 0.0
                for g in lista_gastos:
                    col_g1, col_g2, col_g3, col_g4 = st.columns([3, 2, 2, 1])
                    with col_g1:
                        st.write(f"• **{g['descricao']}**")
                        st.caption(f"Cat: {g['categoria']} | Beneficiário: {g['responsavel']} | Data: {g['data']}")
                    with col_g2:
                        st.write(f"**R$ {g['valor']:.2f}**")
                    with col_g3:
                        st.write("")
                    with col_g4:
                        if st.button("🗑️", key=f"del_gasto_{g['id']}"):
                            deletar_gasto_dono(g['id'])
                            st.rerun()
                    total_gastos_geral += g['valor']
                    st.markdown("---")
                st.markdown(f"### 📉 **Total de Gastos / Funcionários: R$ {total_gastos_geral:.2f}**")

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

    modo_pedido = st.radio(
        "Como prefere fazer o seu pedido?",
        ["📝 Modo Tradicional (Manual)", "🎙️ Modo Inteligente por Voz / Texto Livre"],
        horizontal=True
    )

    # ---------------------------------------------------------
    # MODO 1: TRADICIONAL (MANUAL COM REFEIÇÕES E SUCOS)
    # ---------------------------------------------------------
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
                    
            obs_marmita = st.text_input("Observação / Preferência (ex: 'Caprichar no caldo'):", key=f"obs_input_{k}")

            if st.button("➕ Adicionar Refeição ao Carrinho", type="primary"):
                if not nome_cliente or not telefone_cliente:
                    st.error("Por favor, preencha o
