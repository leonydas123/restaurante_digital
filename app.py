import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import sqlite3
import json

# Configuração da página com layout amplo e visual mobile-first
st.set_page_config(page_title="App Restaurante - Pedidos e Gestão", page_icon="🍽️", layout="wide")

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
    
    # Tabela de Configurações do Cardápio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    
    # Tabela de Estoque
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
    
    # Tabela de Pedidos
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

    # Tabela de Compras
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT,
            qtd REAL,
            unidade TEXT,
            vl_unit REAL,
            total REAL,
            pessoal INTEGER,
            empresa TEXT,
            data TEXT,
            obs TEXT
        )
    """)

    # Tabela de Fornecedores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            contato TEXT,
            produtos TEXT,
            obs TEXT
        )
    """)
    
    # Inserir dados padrões caso esteja vazio
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
    """, (str(data_ped), cliente, telefone, horario, pedido_str, total, pagamento, nota_info))
    conn.commit()
    conn.close()

def dar_baixa_estoque_pedido(pedido_texto):
    conn = get_db_connection()
    cursor = conn.cursor()
    estoque = pd.read_sql_query("SELECT * FROM estoque", conn).to_dict("records")
    
    # Estima quantidade de marmitas vendidas no texto do pedido
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
        estado_antigo = row["estado"]
        ja_baixou = row["estoque_baixado"]
        pedido_texto = row["pedido"]
        
        # Baixa automática no estoque ao alterar para Pago / Concluído
        if novo_estado == "Pago / Concluído" and not ja_baixou:
            dar_baixa_estoque_pedido(pedido_texto)
            cursor.execute("UPDATE pedidos SET estado = ?, estoque_baixado = 1 WHERE id = ?", (novo_estado, id_ped))
        else:
            cursor.execute("UPDATE pedidos SET estado = ? WHERE id = ?", (novo_estado, id_ped))
            
    conn.commit()
    conn.close()

# ==========================================
# DESIGN E ESTILO CSS PREMIUM
# ==========================================
st.markdown("""
    <style>
    .main { background-color: #f4f6f8; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #111827; font-weight: 700; }
    .stMetric { background-color: #ffffff; padding: 16px; border-radius: 14px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border-left: 5px solid #10b981; }
    .stButton>button { border-radius: 10px; font-weight: 600; background-color: #10b981; color: white; border: none; padding: 0.5rem 1rem; width: 100%; }
    .stButton>button:hover { background-color: #059669; }
    div[data-testid="stExpander"] { background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 12px; }
    .alerta-estoque { background-color: #fee2e2; border-left: 4px solid #ef4444; padding: 10px; border-radius: 8px; color: #991b1b; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# Inicializar sessões
if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

if "form_refeicao_key" not in st.session_state:
    st.session_state.form_refeicao_key = 0

menu_diario = carregar_config("menu_diario")
precos_sucos = carregar_config("precos_sucos")

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================
if st.session_state.modo_admin:
    st.markdown("### 🔒 Painel do Administrador")
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
        "⚙️ Cardápio e Preços", 
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
        
        if st.button("💾 Guardar Alterações do Cardápio", type="primary"):
            menu_diario["carnes"] = [c.strip() for c in novas_carnes.split(",") if c.strip()]
            menu_diario["tipos_arroz"] = [r.strip() for r in novos_tipos_arroz.split(",") if r.strip()]
            menu_diario["acompanhamentos_padrao"] = [a.strip() for a in novos_acompanhamentos.split(",") if a.strip()]
            menu_diario["preco_marmita"] = preco_marmita_novo
            salvar_config("menu_diario", menu_diario)
            st.success("Cardápio salvo permanentemente no banco de dados!")
            st.rerun()
            
    with admin_tab2:
        st.markdown("#### 📥 Pedidos Recebidos & Impressão de Comanda")
        lista_pedidos = carregar_pedidos()
        if not lista_pedidos:
            st.info("Nenhum pedido recebido.")
        else:
            for ped in lista_pedidos:
                with st.expander(f"Pedido #{ped['id']} - {ped['cliente']} | Status: {ped['estado']} (R$ {ped['total']:.2f})"):
                    st.write(f"**Data:** {ped['data']} | **Horário Retirada:** {ped['horario_retirada']}")
                    st.write(f"**Telefone:** {ped['telefone']}")
                    st.write(f"**Itens do Pedido:** {ped['pedido']}")
                    st.write(f"**Forma de Pagamento:** {ped['pagamento']}")
                    st.write(f"**Info Formal / Nota Fiscal:** {ped['nota_info']}")
                    
                    if ped['estoque_baixado']:
                        st.caption("✅ Baixa automática de estoque realizada para este pedido.")

                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        novo_estado = st.selectbox("Alterar Status:", ["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"],
                                                   index=["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"].index(ped['estado']),
                                                   key=f"status_sel_{ped['id']}")
                        if st.button("💾 Atualizar Status", key=f"btn_status_{ped['id']}"):
                            atualizar_status_pedido(ped['id'], novo_estado)
                            st.success("Status atualizado!")
                            st.rerun()
                            
                    with col_p2:
                        st.markdown("##### 🛈 Comanda para Cozinha")
                        comanda_texto = f"=== COMANDA #{ped['id']} ===\nCliente: {ped['cliente']}\nRetirada: {ped['horario_retirada']}\n\n{
