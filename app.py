import streamlit as st

st.set_page_config(page_title="Restaurante Digital", page_icon="🍽️", layout="centered")

# Senha secreta do dono
SENHA_DO_DONO = "sua_senha_secreta_aqui"

# Verificar em qual "modo" o sistema está
if 'modo_admin' not in st.session_state:
    st.session_state['modo_admin'] = False

# ----------------------------------------------------
# SE O DONO ESTIVER LOGADO NO PAINEL ADMINISTRATIVO
# ----------------------------------------------------
if st.session_state['modo_admin']:
    st.success("🔐 Painel Restrito do Dono")
    
    if st.button("Sair do Painel Administrativo"):
        st.session_state['modo_admin'] = False
        st.rerun()
        
    st.divider()
    st.subheader("Gestão de Dívidas e Caixa (Área Exclusiva)")
    st.write("Aqui ficam os registos financeiros e de dívidas que só o dono pode ver.")

# ----------------------------------------------------
# VISÃO NORMAL DO CLIENTE (O que todo mundo abre primeiro)
# ----------------------------------------------------
else:
    st.title("🍽️ Restaurante Digital - Cardápio")
    st.write("Bem-vindo ao nosso restaurante! Faça o seu pedido abaixo.")
    
    # Simulação do cardápio e pedido do cliente
    with st.form("pedido_cliente"):
        nome = st.text_input("Seu Nome")
        telefone = st.text_input("Seu Telemóvel / WhatsApp")
        pedido = st.text_area("O que vai pedir?")
        enviar = st.form_submit_button("Enviar Pedido")
        if enviar:
            if nome and telefone and pedido:
                st.success(f"Pedido enviado com sucesso, {nome}!")
            else:
                st.error("Por favor, preencha o seu nome, telefone e o pedido.")

    st.divider()
    
    # ----------------------------------------------------
    # O ATALHO SECRETO DO DONO (Discreto no rodapé)
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
