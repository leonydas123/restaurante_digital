import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import sqlite3
import json
import re
import hashlib
import os

# Configuração da página com layout amplo e visual mobile-first
st.set_page_config(
    page_title="App Restaurante - Pedidos e Gestão", 
    page_icon="🍽️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Criar pasta para imagens se não existir
if not os.path.exists("imagens_produtos"):
    os.makedirs("imagens_produtos")

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
            data TEXT,
            ordem INTEGER DEFAULT 99,
            imagem_path TEXT DEFAULT ''
        )
    """)

    try:
        cursor.execute("ALTER TABLE estoque ADD COLUMN ordem INTEGER DEFAULT 99")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE estoque ADD COLUMN imagem_path TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

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
            estoque_baixado INTEGER DEFAULT 1
        )
    """)

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
            ("Coca Cola Lata 300ml", "Bebidas", "Refrigerante", 10.0, "UN", 6.00, 0.0, str(date.today()), 1, ""),
            ("Fanta Lata 300ml", "Bebidas", "Refrigerante", 20.0, "UN", 6.00, 0.0, str(date.today()), 2, ""),
            ("Água Mineral 500ml", "Bebidas", "Outros", 30.0, "UN", 4.00, 0.0, str(date.today()), 3, "")
        ]
        cursor.executemany("INSERT INTO estoque (item, categoria, subcategoria, qtd, unidade, preco_unitario, consumo_por_marmita, data, ordem, imagem_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", itens_estoque_padrao)

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
    df = pd.read_sql_query("SELECT * FROM estoque ORDER BY ordem ASC, id DESC", conn)
    conn.close()
    return df.to_dict("records")

def salvar_item_estoque(item, categoria, subcategoria, qtd, unidade, preco_unit, consumo, data_ent, ordem, imagem_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO estoque (item, categoria, subcategoria, qtd, unidade, preco_unitario, consumo_por_marmita, data, ordem, imagem_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (item, categoria, subcategoria, qtd, unidade, preco_unit, consumo, str(data_ent), ordem, imagem_path))
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

def baixar_estoque_item(nome_item_procurado, qtd_a_baixar):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, qtd FROM estoque WHERE LOWER(item) LIKE ?", (f"%{nome_item_procurado.lower()}%",))
    row = cursor.fetchone()
    if row:
        item_id = row["id"]
        qtd_atual = float(row["qtd"])
        nova_qtd = max(0.0, qtd_atual - float(qtd_a_baixar))
        cursor.execute("UPDATE estoque SET qtd = ? WHERE id = ?", (nova_qtd, item_id))
        conn.commit()
    conn.close()

def estornar_estoque_item(nome_item_procurado, qtd_a_estornar):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, qtd FROM estoque WHERE LOWER(item) LIKE ?", (f"%{nome_item_procurado.lower()}%",))
    row = cursor.fetchone()
    if row:
        item_id = row["id"]
        qtd_atual = float(row["qtd"])
        nova_qtd = qtd_atual + float(qtd_a_estornar)
        cursor.execute("UPDATE estoque SET qtd = ? WHERE id = ?", (nova_qtd, item_id))
        conn.commit()
    conn.close()

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

def carregar_cupons():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM cupons_gastos ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def carregar_fornecedores():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM fornecedores ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

def carregar_donos():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM donos ORDER BY id DESC", conn)
    conn.close()
    return df.to_dict("records")

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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pendente', 1)
    """, (str(data_ped), str(cliente), str(telefone), str(horario), str(pedido_str), float(total), str(pagamento), str(nota_info)))
    conn.commit()
    conn.close()

def atualizar_status_pedido(id_ped, novo_estado):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET estado = ? WHERE id = ?", (novo_estado, id_ped))
    conn.commit()
    conn.close()

# ==========================================
# PARSER INTELIGENTE
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

    qtd_marmitas = 1
    if "duas" in texto or "2" in texto:
        qtd_marmitas = 2
    elif "tres" in texto or "três" in texto or "3" in texto:
        qtd_marmitas = 3

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
# DESIGN E ESTILO CSS
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
    </style>
""", unsafe_allow_html=True)

if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

if "form_refeicao_key" not in st.session_state:
    st.session_state.form_refeicao_key = 0

if "form_bebida_key" not in st.session_state:
    st.session_state.form_bebida_key = 0

menu_diario = carregar_config("menu_diario")
precos_sucos = carregar_config("precos_sucos")

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================
if st.session_state.modo_admin:
    st.markdown("""
        <div class='app-header'>
            <h1>🔒 Painel de Gestão & Administração</h1>
            <p>Seus registros ficam permanentemente salvos no sistema por tempo indeterminado.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab_carnes, admin_tab8, admin_tab5, admin_tab6, admin_tab7, admin_tab4 = st.tabs([
        "⚙️ Cardápio & Preços", 
        "📋 Pedidos & Comandas", 
        "📦 Estoque & Ordem",
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

        if st.button("💾 Salvar Alterações do Cardápio & Sucos", type="primary"):
            menu_diario["carnes"] = [c.strip() for c in novas_carnes.split(",") if c.strip()]
            menu_diario["tipos_arroz"] = [r.strip() for r in novos_tipos_arroz.split(",") if r.strip()]
            menu_diario["acompanhamentos_padrao"] = [a.strip() for a in novos_acompanhamentos.split(",") if a.strip()]
            menu_diario["preco_marmita"] = preco_marmita_novo
            salvar_config("menu_diario", menu_diario)
            salvar_config("precos_sucos", novos_precos_sucos)
            st.success("✨ Cardápio atualizado!")
            st.rerun()
            
    with admin_tab2:
        st.markdown("#### 📥 Pedidos Recebidos")
        lista_pedidos = carregar_pedidos()
        if not lista_pedidos:
            st.info("Nenhum pedido encontrado.")
        else:
            for ped in lista_pedidos:
                with st.expander(f"📦 Pedido #{ped['id']} - {ped['cliente']} | Status: {ped['estado']} (R$ {ped['total']:.2f})"):
                    st.write(f"📅 Data: {ped['data']} | ⏰ Retirada: {ped['horario_retirada']}")
                    st.write(f"📱 Telefone: {ped['telefone']}")
                    st.write(f"🍽️ Itens: {ped['pedido']}")
                    st.write(f"💳 Pagamento: {ped['pagamento']}")
                    
                    novo_estado = st.selectbox("Atualizar Status:", ["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"],
                                               index=["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"].index(ped['estado']),
                                               key=f"status_sel_{ped['id']}")
                    if st.button("💾 Confirmar Status", key=f"btn_status_{ped['id']}"):
                        atualizar_status_pedido(ped['id'], novo_estado)
                        st.success("Status atualizado!")
                        st.rerun()

    with admin_tab3:
        st.markdown("#### 📦 Controle de Estoque, Ordem e Imagens")
        with st.form("form_novo_item_estoque"):
            st.markdown("##### ➕ Cadastrar Novo Item / Bebida")
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                nome_item = st.text_input("Nome do Item (ex: Coca Mini 250ml):")
                data_item = st.date_input("Data de Entrada:", value=date.today())
            with col_e2:
                cat_item = st.selectbox("Categoria:", ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"])
                subcat_item = st.selectbox("Tipo de Bebida:", ["Refrigerante", "Suco Natural", "Outros"])
                un_item = st.selectbox("Unidade:", ["UN", "KG", "Litros", "Pacotes"])
            with col_e3:
                qtd_input = st.text_input("Quantidade Inicial:", value="15.0")
                preco_unit_input = st.text_input("Preço de Venda (R$):", value="5.00")
                ordem_input = st.number_input("Ordem de Exibição (1 = Primeiro):", min_value=1, value=1, step=1)

            foto_produto = st.file_uploader("Foto / Imagem do Produto (Opcional):", type=["jpg", "jpeg", "png"])

            if st.form_submit_button("💾 Salvar no Estoque", type="primary"):
                qtd_val = parse_float(qtd_input)
                preco_val = parse_float(preco_unit_input)
                
                img_path_saved = ""
                if foto_produto:
                    img_path_saved = os.path.join("imagens_produtos", f"{hashlib.md5(foto_produto.read()).hexdigest()}_{foto_produto.name}")
                    with open(img_path_saved, "wb") as f:
                        f.write(foto_produto.getbuffer())

                if not nome_item:
                    st.error("Informe o nome do item.")
                else:
                    salvar_item_estoque(nome_item, cat_item, subcat_item, qtd_val, un_item, preco_val, 0.0, data_item, int(ordem_input), img_path_saved)
                    st.success("✨ Item salvo com sucesso!")
                    st.rerun()

        st.divider()
        estoque_atual = carregar_estoque()
        cat_selecionada = st.radio("Filtrar Categoria:", ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"], horizontal=True)

        for item_est in estoque_atual:
            if item_est["categoria"] == cat_selecionada:
                col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns([2, 1, 1, 1, 1])
                with col_i1:
                    st.write(f"• **{item_est['item']}**")
                    if item_est['qtd'] <= 0:
                        st.caption("🔴 ESGOTADO")
                with col_i2:
                    nova_ordem = st.number_input("Ordem", value=int(item_est.get('ordem', 99)), step=1, key=f"ordem_{item_est['id']}")
                    if nova_ordem != item_est.get('ordem', 99):
                        atualizar_item_estoque(item_est['id'], "ordem", nova_ordem)
                        st.rerun()
                with col_i3:
                    nova_qtd = st.number_input("Qtd", value=float(item_est['qtd']), step=1.0, key=f"est_qtd_{item_est['id']}")
                    if nova_qtd != item_est['qtd']:
                        atualizar_item_estoque(item_est['id'], "qtd", nova_qtd)
                with col_i4:
                    novo_preco = st.number_input("Preço R$", value=float(item_est.get('preco_unitario', 5.0)), step=0.5, key=f"est_preco_{item_est['id']}")
                    if novo_preco != item_est.get('preco_unitario', 5.0):
                        atualizar_item_estoque(item_est['id'], "preco_unitario", novo_preco)
                with col_i5:
                    if st.button("🗑️ Deletar", key=f"del_est_{item_est['id']}"):
                        deletar_item_estoque(item_est['id'])
                        st.rerun()
                st.markdown("---")

    with admin_tab_carnes:
        st.markdown("#### 🥩 Controle de Rendimento de Carnes")
        with st.form("form_novo_rendimento_carne"):
            col_rc1, col_rc2 = st.columns(2)
            with col_rc1:
                nome_c_input = st.text_input("Nome da Carne:", value="Costela")
                quilos_prep = st.text_input("Quilos Preparados:", value="7.0")
            with col_rc2:
                gramas_porc_input = st.text_input("Gramas por porção:", value="150")
                data_c_reg = st.date_input("Data:", value=date.today())

            if st.form_submit_button("💾 Salvar Rendimento", type="primary"):
                salvar_carne_rendimento(nome_c_input, parse_float(quilos_prep), parse_float(gramas_porc_input), data_c_reg)
                st.success("Salvo!")
                st.rerun()

        for c_r in carregar_carnes_rendimento():
            st.write(f"• **{c_r['nome_carne']}** | Restam: **{int(c_r['qtd_atual_disponivel'])} marmitas**")

    with admin_tab8:
        st.markdown("#### 🧾 Cupons & Gastos")
        for c in carregar_cupons():
            st.write(f"• {c['produto']} - R$ {c['preco']:.2f}")

    with admin_tab5:
        st.markdown("#### 🤝 Fornecedores")
        for f in carregar_fornecedores():
            st.write(f"• {f['nome']} - {f['telefone']}")

    with admin_tab6:
        st.markdown("#### 👑 Gestão de Sócios")
        for d in carregar_donos():
            st.write(f"• {d['nome']} ({d['cargo']})")

    with admin_tab7:
        st.markdown("#### 📈 Relatórios Gerais")
        lista_p = carregar_pedidos()
        if lista_p:
            st.bar_chart(pd.DataFrame(lista_p)['estado'].value_counts())

    with admin_tab4:
        st.markdown("#### 📊 Fechamento e Controle de Caixa")
        pedidos_todos = carregar_pedidos()
        data_caixa = st.date_input("Data do Caixa:", value=date.today())
        pedidos_dia = [p for p in pedidos_todos if str(p['data']) == str(data_caixa) and p['estado'] == 'Pago / Concluído']
        total_bruto = sum([p['total'] for p in pedidos_dia])
        st.metric("💰 Total Vendido no Dia", f"R$ {total_bruto:.2f}")

# ==========================================
# VISÃO DO CLIENTE
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

        carnes_cardapio_config = menu_diario.get("carnes", [])
        carnes_rend_cliente = carregar_carnes_rendimento()
        
        carnes_disponiveis_cardapio = []
        for carne_nome in carnes_cardapio_config:
            encontrada = False
            for c in carnes_rend_cliente:
                if c['nome_carne'].strip().lower() == carne_nome.strip().lower():
                    if float(c['qtd_atual_disponivel']) > 0:
                        carnes_disponiveis_cardapio.append(carne_nome)
                    encontrada = True
                    break
            if not encontrada:
                carnes_disponiveis_cardapio.append(carne_nome)

        if not carnes_disponiveis_cardapio:
            carnes_disponiveis_cardapio = ["Indisponível"]

        with st.container():
            col_qtd, col_carne = st.columns([1, 3])
            with col_qtd:
                quantidade = st.number_input("Quantidade:", min_value=0, value=0, step=1, key=f"qtd_marmita_{k}")
            with col_carne:
                carne_escolhida = st.selectbox("Escolha a Opção de Carne:", carnes_disponiveis_cardapio, key=f"carne_sel_{k}")
            
            tipo_arroz_feijao = st.radio("Escolha a Base do Prato:", menu_diario["tipos_arroz"], horizontal=True, key=f"base_sel_{k}")

            acomps_removidos = []
            cols_acomp = st.columns(3)
            for index, acrod in enumerate(menu_diario["acompanhamentos_padrao"]):
                if not cols_acomp[index % 3].checkbox(f"Incluir {acrod}", value=True, key=f"acomp_{acrod}_{k}"):
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
                    preco_total_item = float(menu_diario["preco_marmita"]) * quantidade
                    base_simp = tipo_arroz_feijao.lower()
                    desc_principal = f"{quantidade} {carne_escolhida.lower()} {base_simp}"
                    
                    st.session_state.carrinho_atual.append({
                        "quantidade": quantidade,
                        "item_principal": desc_principal,
                        "detalhes": obs_marmita,
                        "preco": preco_total_item
                    })
                    st.session_state.form_refeicao_key += 1
                    st.success("✅ Refeição adicionada ao carrinho com sucesso!")
                    st.rerun()

        st.divider()
        st.markdown("### 🥤 2️⃣ Bebidas e Refrigerantes (Tabela em Grade)")
        
        estoque_cliente = carregar_estoque()
        refris_outros = [i for i in estoque_cliente if i["categoria"] == "Bebidas" and i["qtd"] > 0]

        if not refris_outros:
            st.info("Nenhum refrigerante ou bebida disponível no momento.")
        else:
            kb = st.session_state.form_bebida_key
            cols_grid = st.columns(3)
            for idx, r in enumerate(refris_outros):
                col_target = cols_grid[idx % 3]
                with col_target:
                    st.markdown(f"**{r['item']}**")
                    if r.get("imagem_path") and os.path.exists(r["imagem_path"]):
                        st.image(r["imagem_path"], width=120)
                    st.write(f"Preço: **R$ {r['preco_unitario']:.2f}**")
                    st.write(f"Disponível: **{int(r['qtd'])} un**")
                    
                    # Chave dinâmica baseada em `kb` para resetar para 0 após adicionar
                    qtd_comprar = st.number_input("Qtd:", min_value=0, max_value=int(r['qtd']), value=0, step=1, key=f"grid_qtd_{r['id']}_{kb}")
                    
                    if st.button(f"Adicionar", key=f"btn_add_bev_{r['id']}_{kb}"):
                        if not nome_cliente or not telefone_cliente:
                            st.error("Preencha seu Nome e Telefone.")
                        elif qtd_comprar <= 0:
                            st.error("Selecione quantidade maior que 0.")
                        else:
                            baixar_estoque_item(r['item'], qtd_comprar)
                            st.session_state.carrinho_atual.append({
                                "quantidade": qtd_comprar,
                                "item_principal": f"{qtd_comprar}x {r['item']}",
                                "detalhes": "",
                                "preco": float(r['preco_unitario']) * qtd_comprar,
                                "item_estoque_nome": r['item']
                            })
                            st.session_state.form_bebida_key += 1
                            st.success(f"✅ {qtd_comprar}x {r['item']} adicionado!")
                            st.rerun()
                st.markdown("---")

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
                    if "item_estoque_nome" in item:
                        estornar_estoque_item(item["item_estoque_nome"], item["quantidade"])
                    st.session_state.carrinho_atual.pop(i)
                    st.rerun()
            total_geral += item["preco"]
            
        st.markdown(f"### 💰 **Total: R$ {total_geral:.2f}**")
        
        st.divider()
        forma_pagamento = st.selectbox("Forma de Pagamento:", ["Pix", "Dinheiro", "Cartão na Retirada"])
        info_formal = st.selectbox("Deseja informação formal / nota?", ["Non", "Sim"])

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