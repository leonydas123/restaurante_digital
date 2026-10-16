import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página para mobile e desktop
st.set_page_config(
    page_title="Gestão de Restaurante & Marmitaria",
    page_icon="🍲",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 1. INICIALIZAÇÃO DO ESTADO DA SESSÃO (SESSION STATE)
# -----------------------------------------------------------------------------

if "marmitas_precos" not in st.session_state:
    st.session_state["marmitas_precos"] = {
        "Marmita P": 15.00,
        "Marmita M": 18.00,
        "Marmita G": 22.00,
        "Marmita Executiva": 25.00
    }

if "sucos_precos" not in st.session_state:
    st.session_state["sucos_precos"] = {
        "Suco de Laranja (500ml)": 7.00,
        "Suco de Acerola (500ml)": 6.00,
        "Suco de Maracujá (500ml)": 7.00,
        "Refrigerante Lata": 5.00
    }

if "fornecedores" not in st.session_state:
    st.session_state["fornecedores"] = [
        {"Nome": "Distribuidora de Carnes Silva", "Categoria": "Carnes", "Telefone": "(99) 98111-2233", "Contato": "João"},
        {"Nome": "Hortifruti São José", "Categoria": "Verduras / Legumes", "Telefone": "(99) 98765-4321", "Contato": "Maria"},
        {"Nome": "Embalagens & Cia", "Categoria": "Marmitex / Descartáveis", "Telefone": "(99) 99123-4567", "Contato": "Carlos"}
    ]

if "pedidos" not in st.session_state:
    st.session_state["pedidos"] = []

if "dividas" not in st.session_state:
    st.session_state["dividas"] = [
        {"Cliente": "Restaurante Central", "Valor (R$)": 150.00, "Vencimento": "2026-10-20", "Status": "Pendente"},
        {"Cliente": "Empresa ABC", "Valor (R$)": 320.00, "Vencimento": "2026-10-25", "Status": "Pendente"}
    ]

if "caixa_dia" not in st.session_state:
    st.session_state["caixa_dia"] = [
        {"Hora": "08:30", "Tipo": "Entrada", "Descrição": "Fundo de Caixa Inicial", "Valor (R$)": 200.00},
        {"Hora": "11:45", "Tipo": "Entrada", "Descrição": "Venda de Marmitas à vista", "Valor (R$)": 180.00}
    ]

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# -----------------------------------------------------------------------------
# 2. CABEÇALHO E LOGIN ADMINISTRATIVO
# -----------------------------------------------------------------------------

st.title("🍲 Sistema de Gestão — Marmitaria & Sucos")

if not st.session_state["autenticado"]:
    st.info("🔐 Acesse o Painel Restrito do Dono / Gestor para visualizar todas as opções de controle.")
    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        senha = st.text_input("Digite a senha de Gestor:", type="password")
        if st.button("Entrar no Painel Administrative"):
            if senha == "1234":  # Altere para sua senha preferida
                st.session_state["autenticado"] = True
                st.success("Acesso liberado!")
                st.rerun()
            else:
                st.error("Senha incorreta!")
else:
    st.sidebar.success("🔒 Gestor Autenticado")
    if st.button("Sair do Painel Administrativo"):
        st.session_state["autenticado"] = False
        st.rerun()

    st.markdown("---")
    st.header("📊 Painel Restrito do Dono / Gestor")

    # -------------------------------------------------------------------------
    # 3. ABAS DO PAINEL DO GESTOR (TODAS AS 5 ABAS)
    # -------------------------------------------------------------------------
    
    tab_pedidos, tab_precos, tab_fornecedores, tab_dividas, tab_caixa = st.tabs([
        "📥 Pedidos Recebidos",
        "🏷️ Preço das Marmitas e Sucos",
        "🚚 Fornecedores",
        "📑 Controlo de Dívidas",
        "💵 Caixa do Dia"
    ])

    # -------------------------------------------------------------------------
    # ABA 1: PEDIDOS RECEBIDOS
    # -------------------------------------------------------------------------
    with tab_pedidos:
        st.subheader("Pedidos dos Clientes em Tempo Real")
        if not st.session_state["pedidos"]:
            st.info("Nenhum pedido registrado até o momento.")
        else:
            df_pedidos = pd.DataFrame(st.session_state["pedidos"])
            st.dataframe(df_pedidos, use_container_width=True)

    # -------------------------------------------------------------------------
    # ABA 2: ALTERAR PREÇO DAS MARMITAS E SUCOS
    # -------------------------------------------------------------------------
    with tab_precos:
        st.subheader("Alterar Preços das Marmitas e Bebidas")
        st.write("Atualize os valores praticados no cardápio. As alterações são salvas automaticamente.")

        col_marmitas, col_sucos = st.columns(2)

        with col_marmitas:
            st.markdown("### 🍱 Preço das Marmitas")
            novos_precos_marmitas = {}
            for marmita, preco in st.session_state["marmitas_precos"].items():
                novos_precos_marmitas[marmita] = st.number_input(
                    f"Preço: {marmita}",
                    min_value=0.0,
                    value=float(preco),
                    step=0.50,
                    format="%.2f",
                    key=f"marm_{marmita}"
                )

        with col_sucos:
            st.markdown("### 🥤 Preço dos Sucos e Bebidas")
            novos_precos_sucos = {}
            for suco, preco in st.session_state["sucos_precos"].items():
                novos_precos_sucos[suco] = st.number_input(
                    f"Preço: {suco}",
                    min_value=0.0,
                    value=float(preco),
                    step=0.50,
                    format="%.2f",
                    key=f"suco_{suco}"
                )

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Salvar Novos Preços", type="primary"):
            st.session_state["marmitas_precos"] = novos_precos_marmitas
            st.session_state["sucos_precos"] = novos_precos_sucos
            st.success("Preços atualizados com sucesso!")

    # -------------------------------------------------------------------------
    # ABA 3: FORNECEDORES
    # -------------------------------------------------------------------------
    with tab_fornecedores:
        st.subheader("Cadastro e Consulta de Fornecedores")

        df_forn = pd.DataFrame(st.session_state["fornecedores"])
        st.dataframe(df_forn, use_container_width=True)

        st.markdown("---")
        st.markdown("### ➕ Adicionar Novo Fornecedor")

        with st.form("form_novo_fornecedor"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                nome_f = st.text_input("Nome da Empresa / Fornecedor")
                categoria_f = st.text_input("Categoria (ex: Carnes, Embalagens)")
            with col_f2:
                telefone_f = st.text_input("Telefone / WhatsApp")
                contato_f = st.text_input("Nome do Contato")

            submit_f = st.form_submit_button("Cadastrar Fornecedor")
            if submit_f:
                if nome_f and telefone_f:
                    st.session_state["fornecedores"].append({
                        "Nome": nome_f,
                        "Categoria": categoria_f,
                        "Telefone": telefone_f,
                        "Contato": contato_f
                    })
                    st.success(f"Fornecedor '{nome_f}' cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Preencha ao menos o Nome e o Telefone do fornecedor.")

    # -------------------------------------------------------------------------
    # ABA 4: CONTROLE DE DÍVIDAS
    # -------------------------------------------------------------------------
    with tab_dividas:
        st.subheader("Controlo de Contas a Receber / Dívidas de Clientes")

        df_dividas = pd.DataFrame(st.session_state["dividas"])
        st.dataframe(df_dividas, use_container_width=True)

        st.markdown("---")
        st.markdown("### ➕ Cadastrar Nova Dívida")
        with st.form("form_nova_divida"):
            c_cli, c_val, c_venc = st.columns(3)
            with c_cli:
                cliente_d = st.text_input("Nome do Cliente / Empresa")
            with c_val:
                valor_d = st.number_input("Valor Devido (R$)", min_value=0.0, step=5.0, format="%.2f")
            with c_venc:
                vencimento_d = st.date_input("Data de Vencimento")

            submit_d = st.form_submit_button("Registrar Dívida")
            if submit_d:
                if cliente_d and valor_d > 0:
                    st.session_state["dividas"].append({
                        "Cliente": cliente_d,
                        "Valor (R$)": valor_d,
                        "Vencimento": str(vencimento_d),
                        "Status": "Pendente"
                    })
                    st.success("Dívida registrada com sucesso!")
                    st.rerun()

    # -------------------------------------------------------------------------
    # ABA 5: CAIXA DO DIA
    # -------------------------------------------------------------------------
    with tab_caixa:
        st.subheader("Movimentação do Caixa Diário")

        df_caixa = pd.DataFrame(st.session_state["caixa_dia"])
        st.dataframe(df_caixa, use_container_width=True)

        if not df_caixa.empty:
            entradas = df_caixa[df_caixa["Tipo"] == "Entrada"]["Valor (R$)"].sum()
            saidas = df_caixa[df_caixa["Tipo"] == "Saída"]["Valor (R$)"].sum()
            saldo = entradas - saidas

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Entradas", f"R$ {entradas:.2f}")
            m2.metric("Total Saídas", f"R$ {saidas:.2f}")
            m3.metric("Saldo do Caixa", f"R$ {saldo:.2f}")

        st.markdown("---")
        st.markdown("### ➕ Registrar Lançamento no Caixa")
        with st.form("form_novo_caixa"):
            cx_tipo = st.selectbox("Tipo de Movimentação", ["Entrada", "Saída"])
            cx_desc = st.text_input("Descrição (ex: Compra de Verduras, Venda Pix)")
            cx_val = st.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f")

            submit_cx = st.form_submit_button("Lançar no Caixa")
            if submit_cx:
                if cx_desc and cx_val > 0:
                    hora_atual = datetime.now().strftime("%H:%M")
                    st.session_state["caixa_dia"].append({
                        "Hora": hora_atual,
                        "Tipo": cx_tipo,
                        "Descrição": cx_desc,
                        "Valor (R$)": cx_val
                    })
                    st.success("Lançamento efetuado!")
                    st.rerun()
