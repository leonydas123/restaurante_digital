import streamlit as st
import pandas as pd

st.set_page_config(page_title="Restaurante Digital", page_icon="🍽️", layout="centered")

# Senha secreta do dono/administrador
SENHA_DO_DONO = "sua_senha_secreta_aqui"

# Inicializar os estados da sessão para guardar dados e modo de acesso
if 'modo_admin' not in st.session_state:
    st.session_state['modo_admin'] = False

if 'lista_pedidos' not in st.session_state:
    st.session_state['lista_pedidos'] = []

if 'lista_dividas' not in st.session_state:
    st.session_state['lista_dividas'] = []

# ----------------------------------------------------
# 1. SE O DONO ESTIVER LOGADO NO PAINEL ADMINISTRATIVO
# ----------------------------------------------------
if st.session_state['modo_admin']:
    st.success("🔐 Painel Restrito do Dono / Gestor")
    
    if st.button("Sair do Painel Administrativo"):
        st.session_state['modo_admin'] = False
        st.rerun()
        
    st.divider()
    st.subheader("📊 Caixa e Dívidas")
    
    # Abas de gestão dentro da área do administrador
    aba_adm1, aba_adm2, aba_adm3 = st.tabs(["Pedidos Recebidos", "Controlo de Dívidas", "Caixa do Dia"])
    
    with aba_adm1:
        st.write("### Pedidos dos Clientes em Tempo Real")
        if len(st.session_state['lista_pedidos']) == 0:
            st.info("Nenhum pedido registado até ao momento.")
        else:
            df_pedidos = pd.DataFrame(st.session_state['lista_pedidos'])
            st.dataframe(df_pedidos, use_container_width=True)
            
    with aba_adm2:
        st.write("### Registo de Clientes Fiados / Dívidas")
        with st.form("form_divida"):
            cliente_divida = st.text_input("Nome do Cliente")
            valor_divida = st.number_input("Valor em Dívida (€ / R$)", format="%.2f")
            btn_add_divida = st.form_submit_button("Registar Dívida")
            
            if btn_add_divida:
                if cliente_divida and valor_divida > 0:
                    st.session_state['lista_dividas'].append({"Cliente": cliente_divida, "Valor": valor_divida})
                    st.success(f"Dívida de {cliente_divida} registada com sucesso!")
                else:
                    st.error("Preencha o nome e um valor válido.")
                    
        if len(st.session_state['lista_dividas']) > 0:
            st.write("#### Lista Atual de Dívidas:")
            df_dividas = pd.DataFrame(st.session_state['lista_dividas'])
            st.dataframe(df_dividas, use_container_width=True)
            
    with aba_adm3:
        st.write("### Fechamento de Caixa e Balanço")
        st.metric(label="Total Faturado (Simulação)", value="R$ 0,00")
        st.write("Aqui pode acompanhar o fluxo de caixa diário do restaurante.")

# ----------------------------------------------------
# 2. VISÃO NORMAL DO CLIENTE (Acesso direto e livre)
# ----------------------------------------------------
else:
    st.title("🍽️ Restaurante Digital - Cardápio")
    st.write("Bem-vindo ao nosso restaurante! Faça o seu pedido de forma rápida e prática.")
    
    # Formulário direto para o cliente fazer o pedido sem precisar de login prévio
    with st.form("pedido_cliente"):
        st.subheader("Faça o seu Pedido")
        nome = st.text_input("Seu Primeiro Nome")
        telefone = st.text_input("Seu Número de Telemóvel / WhatsApp")
        pedido = st.text_area("O que deseja pedir?")
        
        enviar = st.form_submit_button("Enviar Pedido ao Restaurante")
        
        if enviar:
            if nome and telefone and pedido:
                # Salva o pedido na lista geral para o dono ver no painel
                novo_pedido = {"Nome": nome, "Telefone": telefone, "Pedido": pedido}
                st.session_state['lista_pedidos'].append(novo_pedido)
                st.success(f"Pedido enviado com sucesso, {nome}! O restaurante já está a preparar.")
            else:
                st.error("Por favor, preencha o seu nome, o telefone e o pedido.")

    st.divider()
    
    # ----------------------------------------------------
    # 3. O ATALHO SECRETO DO DONO (Discreto no rodapé)
    # ----------------------------------------------------
    with st.expander("⚙️ Acesso Restrito (Gestão)"):
        senha_digitada = st.text_input("Senha do Administrador", type="password")
        entrar_admin = st.button("Entrar como Dono")
        
        if entrar_admin:
            if senha_digitada == SENHA_DO_DONO:
                st.session_state['modo_admin'] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
