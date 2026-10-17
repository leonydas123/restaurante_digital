import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import sqlite3
import json

# Configuração da página
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
            estado TEXT
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

    # Tabela de Dívidas / Custos Privados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            tipo TEXT,
            valor_mensal REAL,
            parcelas_restantes INTEGER,
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
            ("Pacote Marmita c/ 100un", "Embalagens e Marmitas", 1.0, "Pacotes", 0.01, str(date.today()))
        ]
        cursor.executemany("INSERT INTO estoque (item, categoria, qtd, unidade, consumo_por_marmita, data) VALUES (?, ?, ?, ?, ?, ?)", itens_estoque_padrao)

    conn.commit()
    conn.close()

init_db()

# ==========================================
# FUNÇÕES DE LEITURA E ESCRITA NO BANCO
# ==========================================
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
        INSERT INTO pedidos (data, cliente, telefone, horario_retirada, pedido, total, pagamento, nota_info, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pendente')
    """, (str(data_ped), cliente, telefone, horario, pedido_str, total, pagamento, nota_info))
    conn.commit()
    conn.close()

def atualizar_status_pedido(id_ped, novo_estado):
    conn = get_db_connection()
    cursor = conn.cursor()
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
    </style>
""", unsafe_allow_html=True)

# Inicializar sessões com dados do banco
if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

if "form_refeicao_key" not in st.session_state:
    st.session_state.form_refeicao_key = 0

menu_diario = carregar_config("menu_diario")
precos_sucos = carregar_config("precos_sucos")

# ==========================================
# SE O ADMINISTRADOR ESTIVER LOGADO
# ==========================================
if st.session_state.modo_admin:
    st.markdown("### 🔒 Painel do Administrador")
    if st.button("⬅️ Voltar para a Visão do Cliente"):
        st.session_state.modo_admin = False
        st.rerun()

    st.divider()

    admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
        "⚙️ Cardápio e Preços", 
        "📋 Pedidos em Tempo Real", 
        "📦 Estoque Persistente",
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
        st.markdown("#### 📥 Pedidos Recebidos")
        lista_pedidos = carregar_pedidos()
        if not lista_pedidos:
            st.info("Nenhum pedido recebido.")
        else:
            for ped in lista_pedidos:
                with st.expander(f"Pedido #{ped['id']} - Cliente: {ped['cliente']} | Status: {ped['estado']} (R$ {ped['total']:.2f})"):
                    st.write(f"**Data:** {ped['data']}")
                    st.write(f"**Telefone:** {ped['telefone']}")
                    st.write(f"**Horário Retirada:** {ped['horario_retirada']}")
                    st.write(f"**Pedido:** {ped['pedido']}")
                    st.write(f"**Pagamento:** {ped['pagamento']}")
                    st.write(f"**Nota Formal:** {ped['nota_info']}")
                    
                    novo_estado = st.selectbox("Alterar Status:", ["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"],
                                               index=["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"].index(ped['estado']),
                                               key=f"status_sel_{ped['id']}")
                    if st.button("💾 Atualizar Status", key=f"btn_status_{ped['id']}"):
                        atualizar_status_pedido(ped['id'], novo_estado)
                        st.success("Status atualizado!")
                        st.rerun()

    with admin_tab3:
        st.markdown("#### 📦 Controle de Estoque (Salvo no Banco)")
        st.write("Tudo o que for adicionado aqui continuará salvo ao sair do sistema!")

        with st.form("form_novo_item_estoque"):
            st.markdown("##### ➕ Adicionar Item ao Estoque")
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1:
                nome_item = st.text_input("Nome do Item (ex: Fanta Lata, Coxão Mole):")
                data_item = st.date_input("Data de Entrada:", value=date.today())
            with col_e2:
                cat_item = st.selectbox("Categoria:", ["Bebidas", "Cozinha / Estocáveis", "Verduras", "Embalagens e Marmitas"])
                un_item = st.selectbox("Unidade:", ["KG", "UN", "Litros", "Pacotes"])
            with col_e3:
                qtd_item = st.number_input("Quantidade:", min_value=0.0, value=1.0, step=1.0)
                consumo_marmita = st.number_input("Consumo p/ Marmita:", min_value=0.0, value=0.0, step=0.01)

            if st.form_submit_button("💾 Salvar no Estoque", type="primary"):
                if not nome_item:
                    st.error("Informe o nome do item.")
                else:
                    salvar_item_estoque(nome_item, cat_item, qtd_item, un_item, consumo_marmita, data_item)
                    st.success("Item salvo no banco de dados com sucesso!")
                    st.rerun()

        st.divider()
        st.markdown("##### 📋 Itens em Estoque")
        estoque_atual = carregar_estoque()
        
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
        st.markdown("#### 📊 Fechamento de Caixa")
        lista_pedidos = carregar_pedidos()
        df_vendas = pd.DataFrame(lista_pedidos) if lista_pedidos else pd.DataFrame()
        total_pagos = df_vendas[df_vendas["estado"] == "Pago / Concluído"]["total"].sum() if not df_vendas.empty else 0.0
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(label="Vendas Recebidas Concluídas", value=f"R$ {total_pagos:.2f}")
        with col_m2:
            st.metric(label="Total de Pedidos Registrados", value=len(df_vendas))

# ==========================================
# ABERTURA DIRETA: VISÃO DO CLIENTE
# ==========================================
else:
    st.markdown("<h1 style='text-align: center; color: #10b981;'>🍽️ Restaurante Digital</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6b7280; margin-bottom: 20px;'>Monte o seu pedido, adicione ao carrinho e envie direto para o nosso WhatsApp!</p>", unsafe_allow_html=True)
    
    col_cli1, col_cli2 = st.columns(2)
    with col_cli1:
        nome_cliente = st.text_input("Seu Nome:")
    with col_cli2:
        telefone_cliente = st.text_input("Seu Telefone / WhatsApp:")

    horario_retirada = st.text_input("Horário de Retirada (ex: 12:30):", value="12:00")

    if "carrinho_atual" not in st.session_state:
        st.session_state.carrinho_atual = []

    st.markdown("---")
    st.markdown("#### 🥗 Monte a sua Refeição")
    
    k = st.session_state.form_refeicao_key

    with st.container():
        col_qtd, col_carne = st.columns([1, 3])
        with col_qtd:
            quantidade = st.number_input("Qtd:", min_value=0, value=0, step=1, key=f"qtd_marmita_{k}")
        with col_carne:
            carne_escolhida = st.selectbox("Escolha a Carne do Prato:", menu_diario["carnes"], key=f"carne_sel_{k}")
        
        tipo_arroz_feijao = st.radio("Escolha o acompanhamento base:", menu_diario["tipos_arroz"], horizontal=True, key=f"base_sel_{k}")

        st.markdown("**Outros Acompanhamentos:** (desmarque o que **NÃO** deseja)")
        acomps_removidos = []
        
        cols_acomp = st.columns(3)
        for index, acrod in enumerate(menu_diario["acompanhamentos_padrao"]):
            col_target = cols_acomp[index % 3]
            incluir = col_target.checkbox(f"Incluir {acrod}", value=True, key=f"acomp_{acrod}_{k}")
            if not incluir:
                acomps_removidos.append(acrod)
                
        obs_marmita = st.text_input("Observação (ex: 'Caprichar no caldo'):", key=f"obs_input_{k}")

        if st.button("➕ Adicionar Refeição ao Carrinho", type="primary"):
            if not nome_cliente or not telefone_cliente:
                st.error("Por favor, preencha o seu Nome e Telefone antes de adicionar itens.")
            elif quantidade <= 0:
                st.error("Por favor, selecione uma quantidade maior que 0.")
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
                st.success("Refeição adicionada ao carrinho com sucesso!")
                st.rerun()

    st.divider()

    st.markdown("#### 🛒 O Seu Pedido Atual")
    if not st.session_state.carrinho_atual:
        st.info("O seu carrinho ainda está vazio.")
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
            
        st.markdown(f"### 💰 **Total Geral: R$ {total_geral:.2f}**")
        
        st.markdown("---")
        st.markdown("#### 💳 Forma de Pagamento e Informações Fiscais")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            forma_pagamento = st.selectbox("Como vai pagar?", ["Pix", "Dinheiro", "Cartão na Retirada"])
        with col_p2:
            info_formal_pagamento = st.selectbox("Deseja informação formal de pagamento / nota?", ["Não", "Sim (Desejo recibo/comprovante formal)"])
        
        troco_info = ""
        if forma_pagamento == "Dinheiro":
            precisa_troco = st.radio("Precisa de troco?", ["Não", "Sim"], horizontal=True)
            if precisa_troco == "Sim":
                troco_info = st.text_input("Troco para quanto? (ex: R$ 50,00)")

        if st.button("🚀 Finalizar e Enviar Pedido para o WhatsApp", type="primary"):
            if not nome_cliente or not telefone_cliente:
                st.error("Por favor, preencha o seu Nome e Telefone antes de enviar.")
            else:
                linhas_pedido = []
                for it in st.session_state.carrinho_atual:
                    linha = it["item_principal"]
                    if it["detalhes"]:
                        linha += f"\n{it['detalhes']}"
                    linhas_pedido.append(linha)
                
                texto_itens = "\n\n".join(linhas_pedido)
                
                pagamento_texto = forma_pagamento
                if forma_pagamento == "Dinheiro" and troco_info:
                    pagamento_texto += f" (Troco para: {troco_info})"

                # Salva o pedido no Banco de Dados
                salvar_pedido(date.today(), nome_cliente, telefone_cliente, horario_retirada, texto_itens.replace("\n", " | "), total_geral, pagamento_texto, info_formal_pagamento)
                
                whatsapp_restaurante = "5599981370792"
                texto_mensagem = f"NOVO PEDIDO :\nCliente: {nome_cliente}\nHorário de Retirada: {horario_retirada}\n\n{texto_itens}\n\nForma de Pagamento: {pagamento_texto}\nInformação Formal de Pagamento: {info_formal_pagamento}\nTotal Geral: R$ {total_geral:.2f}"
                mensagem_formatada = urllib.parse.quote(texto_mensagem)
                link_whatsapp = f"https://wa.me/{whatsapp_restaurante}?text={mensagem_formatada}"
                
                st.session_state.carrinho_atual = []
                st.success("Pedido registado e salvo com sucesso no banco de dados!")
                st.markdown(f"### 👉 [Clique aqui para abrir o WhatsApp e enviar o seu pedido]({link_whatsapp})", unsafe_allow_html=True)

# ==========================================
# BOTÃO DISCRETO PARA ENTRAR COMO ADMINISTRADOR
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("---")
with st.expander("🔐 Acesso Administrativo (Restrito)"):
    senha_digitada = st.text_input("Digite a senha do Administrador:", type="password", key="senha_admin_discreto")
    if st.button("Entrar como Administrador"):
        if senha_digitada == "1234":
            st.session_state.modo_admin = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Senha incorreta!")
