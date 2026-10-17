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
# DESIGN E ESTILO CSS ULTRA MODERNO
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
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 18px rgba(16, 185, 129, 0.35) !important;
    }

    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border-radius: 14px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02) !important;
        margin-bottom: 12px !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 10px 10px 0 0;
        padding: 10px 18px;
        font-weight: 600;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        color: #10b981 !important;
        border-bottom: 3px solid #10b981 !important;
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
            <p>Controle do cardápio, recepção de pedidos, estoque e fechamento financeiro.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
        "⚙️ Cardápio & Preços", 
        "📋 Pedidos & Comandas", 
        "📦 Estoque & Conciliação",
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
    # MODO 1: TRADICIONAL (MANUAL COM REFEIÇÕES E SUCOS PROTEGIDOS)
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
                    st.success("✅ Refeição adicionada com sucesso ao carrinho!")
                    st.toast("Refeição adicionada!", icon="🍽️")
                    st.rerun()

        st.divider()
        st.markdown("### 🥤 2️⃣ Sucos e Bebidas (Opcional)")
        
        # FORMULÁRIO COM SELETOR DE QUANTIDADE E PROTEÇÃO CONTRA DUPLO CLIQUE
        ks = st.session_state.form_suco_key
        with st.form(key=f"form_suco_{ks}"):
            col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
            with col_s1:
                sabor_suco = st.selectbox("Sabor do Suco:", ["Acerola", "Cajá", "Maracujá"])
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

            btn_add_suco = st.form_submit_button("➕ Adicionar Suco ao Carrinho", type="primary")

            if btn_add_suco:
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
                    st.success("✅ Suco adicionado com sucesso ao carrinho!")
                    st.toast("Suco adicionado!", icon="🥤")
                    st.rerun()

    # ---------------------------------------------------------
    # MODO 2: INTELIGENTE POR VOZ / TEXTO LIVRE
    # ---------------------------------------------------------
    else:
        st.markdown("### 🎙️ Fale ou Digite o seu Pedido Completo")
        st.info("💡 **Exemplo:** 'Quero uma costela com feijão de caldo, outra costela sem feijão e sem salada e um copo de acerola.'")
        
        texto_fala = st.text_area(
            "Digite ou clique no microfone do teclado do seu celular para ditar o pedido:",
            placeholder="Exemplo: Quero uma costela com feijão de caldo outra costela sem feijao e sem salada e um copo de acerola"
        )

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
                    
                st.success(f"✨ {len(itens_detectados)} item(ns) identificados e adicionados com sucesso!")
                st.toast("Pedido inteligente adicionado!", icon="⚡")
                st.rerun()

    st.divider()

    st.markdown("### 🛒 Seu Pedido Atual")
    if not st.session_state.carrinho_atual:
        st.info("O seu carrinho está vazio. Adicione uma refeição ou suco acima.")
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
