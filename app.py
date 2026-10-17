import streamlit as st
import pandas as pd
from datetime import date
import urllib.parse
import random

# Configuração da página com layout amplo e visual mobile-first
st.set_page_config(page_title="App Restaurante - Pedidos e Gestão", page_icon="🍽️", layout="wide")

# ==========================================
# ESTILO CSS - APARÊNCIA DE APLICATIVO
# ==========================================
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #ff4b4b;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INICIALIZAÇÃO DO SISTEMA E BANCO DE DADOS
# ==========================================
if "usuarios_cadastrados" not in st.session_state:
    st.session_state.usuarios_cadastrados = {
        "admin@restaurante.com": {
            "nome": "Gerente Admin",
            "telefone": "(99) 99999-9999",
            "tipo": "Administrador",
            "senha": "admin"
        }
    }

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

if "codigo_verificacao_temp" not in st.session_state:
    st.session_state.codigo_verificacao_temp = None

if "menu_diario" not in st.session_state:
    st.session_state.menu_diario = {
        "carnes": ["Panelada", "Assado de Panela", "Costela", "Chambaril", "Frango Grelhado", "Peixe Frito"],
        "tipos_arroz": [
            "Arroz com feijão de caldo", 
            "Arroz misturado / arroz baião",
            "Sem feijão"
        ],
        "acompanhamentos_padrao": ["Salada", "Macarrão", "Farofa"],
        "preco_marmita": 20.00,
        "preco_porcao_avulsa": 15.00
    }

if "precos_sucos" not in st.session_state:
    st.session_state.precos_sucos = {
        "Acerola - Copo (300 ml)": 7.00,
        "Acerola - Jarra (1 L)": 14.00,
        "Cajá - Copo (300 ml)": 9.00,
        "Cajá - Jarra (1 L)": 18.00,
        "Maracujá - Copo (300 ml)": 10.00,
        "Maracujá - Jarra (1 L)": 20.00
    }

if "pedidos_clientes" not in st.session_state:
    st.session_state.pedidos_clientes = []

if "compras_registro" not in st.session_state:
    st.session_state.compras_registro = []

if "cupons_importados" not in st.session_state:
    st.session_state.cupons_importados = set()

if "fornecedores_registro" not in st.session_state:
    st.session_state.fornecedores_registro = [
        {
            "nome": "Supermercado Local",
            "contato": "(99) 99999-9999",
            "produtos": "Hortifruti, Bebidas, Limpeza e Estocáveis",
            "obs": "Compra de insumos diários com emissão de NFC-e"
        }
    ]

if "dividas_privadas" not in st.session_state:
    st.session_state.dividas_privadas = [
        {"descricao": "Parcela Financiamento Carro", "tipo": "Pessoal", "valor_mensal": 1200.00, "parcelas_restantes": 24, "obs": "Financiamento do veículo da família"},
        {"descricao": "Salários e Encargos Funcionários", "tipo": "Empresa (Funcionários)", "valor_mensal": 3500.00, "parcelas_restantes": 12, "obs": "Folha de pagamento + taxas/impostos de 2 funcionários"}
    ]

# ==========================================
# 0. TELA DE LOGIN E CADASTRO
# ==========================================
if st.session_state.usuario_logado is None:
    st.title("🍽️ Restaurante Digital")
    st.markdown("Seja bem-vindo! Faça login ou crie sua conta para acessar o cardápio ou sistema de gestão.")

    tab_login, tab_cadastro = st.tabs(["🔑 Fazer Login", "📝 Criar Nova Conta"])

    with tab_login:
        st.subheader("Acessar sua Conta")
        email_login = st.text_input("E-mail cadastrado:", key="email_log")
        
        tipo_perfil_login = st.radio("Entrar como:", ["Cliente", "Administrador"], key="radio_perfil_log", horizontal=True)
        
        if tipo_perfil_login == "Administrador":
            senha_login = st.text_input("Sua Senha:", type="password", key="senha_log")

        if st.button("🚀 Entrar no Aplicativo", type="primary"):
            if email_login in st.session_state.usuarios_cadastrados:
                user_info = st.session_state.usuarios_cadastrados[email_login]
                if user_info["tipo"] != tipo_perfil_login:
                    st.error(f"Este e-mail está cadastrado como '{user_info['tipo']}'. Altere a opção acima para prosseguir.")
                elif tipo_perfil_login == "Administrador" and user_info.get("senha") != senha_login:
                    st.error("Senha de administrador incorreta!")
                else:
                    st.session_state.usuario_logado = user_info
                    st.session_state.usuario_logado["email"] = email_login
                    st.success(f"Bem-vindo(a), {user_info['nome']}!")
                    st.rerun()
            else:
                st.error("E-mail não encontrado! Por favor, faça o cadastro na aba 'Criar Nova Conta'.")

    with tab_cadastro:
        st.subheader("Cadastro de Novo Usuário")
        
        tipo_usuario = st.radio("Quem é você?", ["Cliente", "Administrador"], horizontal=True)
        
        nome_cad = st.text_input("Seu Nome Completo (ou Primeiro Nome):")
        telefone_cad = st.text_input("Seu Telefone / WhatsApp com DDD:")
        email_cad = st.text_input("Seu E-mail:")

        if tipo_usuario == "Administrador":
            senha_cad = st.text_input("Crie uma Senha para Administrador:", type="password")

        if tipo_usuario == "Cliente":
            if st.button("📲 Solicitar Código de Verificação"):
                if not email_cad or not telefone_cad:
                    st.error("Preencha seu Telefone e E-mail para receber o código.")
                else:
                    st.session_state.codigo_verificacao_temp = str(random.randint(1000, 9999))
                    st.info(f"🔑 Código enviado para o seu e-mail/celular: **{st.session_state.codigo_verificacao_temp}**")

            codigo_digitado = st.text_input("Digite o Código de 4 Dígitos Recebido:")

        if st.button("✅ Concluir Cadastro", type="primary"):
            if not nome_cad or not email_cad or not telefone_cad:
                st.error("Preencha todos os campos para cadastrar.")
            elif email_cad in st.session_state.usuarios_cadastrados:
                st.warning("Este e-mail já está cadastrado. Vá até a aba de Login.")
            elif tipo_usuario == "Cliente" and codigo_digitado != st.session_state.codigo_verificacao_temp:
                st.error("Código de verificação incorreto!")
            elif tipo_usuario == "Administrador" and not senha_cad:
                st.error("Crie uma senha para o perfil de Administrador.")
            else:
                novo_user = {
                    "nome": nome_cad,
                    "telefone": telefone_cad,
                    "tipo": tipo_usuario
                }
                if tipo_usuario == "Administrador":
                    novo_user["senha"] = senha_cad

                st.session_state.usuarios_cadastrados[email_cad] = novo_user
                st.session_state.usuario_logado = novo_user
                st.session_state.usuario_logado["email"] = email_cad
                st.success("Cadastro realizado com sucesso!")
                st.rerun()

# ==========================================
# SISTEMA PRINCIPAL (APÓS LOGIN)
# ==========================================
else:
    usuario = st.session_state.usuario_logado

    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title("🍽️ Restaurante Digital")
        st.write(f"Olá, **{usuario['nome']}**! ({usuario['tipo']})")
    with col_head2:
        if st.button("🚪 Sair / Trocar Conta"):
            st.session_state.usuario_logado = None
            st.rerun()

    st.divider()

    # ==========================================
    # 1. VISÃO DO CLIENTE
    # ==========================================
    if usuario["tipo"] == "Cliente":
        st.subheader("🍽️ Cardápio Digital do Dia")
        st.write("Monte o seu pedido item por item e adicione ao carrinho!")
        
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            horario_retirada = st.text_input("Horário de Retirada (ex: 12:30):", value="12:00")

        if "carrinho_atual" not in st.session_state:
            st.session_state.carrinho_atual = []

        st.markdown("### 1️⃣ Monte a sua Refeição")
        with st.container():
            col_qtd, col_carne = st.columns([1, 3])
            with col_qtd:
                quantidade = st.number_input("Qtd:", min_value=1, value=1, step=1)
            with col_carne:
                carne_escolhida = st.selectbox("Escolha a Carne do Prato:", st.session_state.menu_diario["carnes"])
            
            tipo_arroz_feijao = st.radio("Escolha o acompanhamento base:", st.session_state.menu_diario["tipos_arroz"], horizontal=True)

            st.markdown("**Outros Acompanhamentos:** (desmarque o que **NÃO** deseja)")
            acomps_removidos = []
            
            cols_acomp = st.columns(3)
            for index, acrod in enumerate(st.session_state.menu_diario["acompanhamentos_padrao"]):
                col_target = cols_acomp[index % 3]
                incluir = col_target.checkbox(f"Incluir {acrod}", value=True, key=f"acomp_{acrod}")
                if not incluir:
                    acomps_removidos.append(acrod)
                    
            obs_marmita = st.text_input("Observação (ex: 'Caprichar no caldo'):")

            if st.button("➕ Adicionar Refeição ao Carrinho", type="primary"):
                preco_unit = st.session_state.menu_diario["preco_marmita"]
                preco_total_item = preco_unit * quantidade
                
                desc_principal = f"{quantidade} {carne_escolhida.lower()} com {tipo_arroz_feijao.lower()}"
                
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
                st.success("Refeição adicionada ao carrinho!")

        st.divider()

        st.markdown("### 2️⃣ Sucos e Bebidas (Opcional)")
        quer_suco = st.checkbox("🥤 Deseja adicionar um Suco / Bebida ao seu pedido?")

        if quer_suco:
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                sabor_suco = st.selectbox("Sabor do Suco:", ["Acerola", "Cajá", "Maracujá"])
            with col_s2:
                tamanho_suco = st.selectbox("Tamanho do Suco:", ["Copo de 300 ml", "Jarra de 1 L"])
                
            chave_tamanho_busca = "Copo (300 ml)" if "Copo" in tamanho_suco else "Jarra (1 L)"
            chave_preco = f"{sabor_suco} - {chave_tamanho_busca}"
            preco_suco = st.session_state.precos_sucos.get(chave_preco, 7.00)
            
            ponto_acucar = st.radio("Açúcar:", ["Com Açúcar", "Sem Açúcar", "Pouco Açúcar"], horizontal=True)
            st.info(f"Valor do Suco: **R$ {preco_suco:.2f}**")

            if st.button("➕ Adicionar Suco ao Carrinho"):
                artigo = "Um" if "copo" in tamanho_suco.lower() else "Uma"
                desc_suco = f"{artigo} {tamanho_suco.lower()} de suco de {sabor_suco.lower()} {ponto_acucar.lower()}"
                st.session_state.carrinho_atual.append({
                    "quantidade": 1,
                    "item_principal": desc_suco,
                    "detalhes": "",
                    "preco": preco_suco
                })
                st.success("Suco adicionado ao carrinho!")

        st.divider()

        st.markdown("### 🛒 O Seu Pedido Atual")
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
            
            st.markdown("### 💳 Forma de Pagamento")
            forma_pagamento = st.selectbox("Como vai pagar?", ["Pix", "Dinheiro", "Cartão na Retirada"])
            
            troco_info = ""
            if forma_pagamento == "Dinheiro":
                precisa_troco = st.radio("Precisa de troco?", ["Não", "Sim"], horizontal=True)
                if precisa_troco == "Sim":
                    troco_info = st.text_input("Troco para quanto? (ex: R$ 50,00)")

            if st.button("🚀 Finalizar e Enviar Pedido para o WhatsApp", type="primary"):
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

                id_pedido = len(st.session_state.pedidos_clientes) + 1
                registo = {
                    "ID": id_pedido,
                    "Data": date.today().strftime("%Y-%m-%d"),
                    "Cliente": usuario["nome"],
                    "Telefone": usuario["telefone"],
                    "Horário Retirada": horario_retirada,
                    "Pedido": texto_itens.replace("\n", " | "),
                    "Total": total_geral,
                    "Pagamento": pagamento_texto,
                    "Estado": "Pendente"
                }
                st.session_state.pedidos_clientes.append(registo)
                
                whatsapp_restaurante = "5599981370792"
                
                texto_mensagem = f"NOVO PEDIDO :\n" \
                                 f"Cliente: {usuario['nome']}\n" \
                                 f"Horário de Retirada: {horario_retirada}\n\n" \
                                 f"{texto_itens}\n\n" \
                                 f"Forma de Pagamento: {pagamento_texto}\n" \
                                 f"Total Geral: R$ {total_geral:.2f}"
                
                mensagem_formatada = urllib.parse.quote(texto_mensagem)
                link_whatsapp = f"https://wa.me/{whatsapp_restaurante}?text={mensagem_formatada}"
                
                st.session_state.carrinho_atual = []
                
                st.success("Pedido registado com sucesso no sistema!")
                st.markdown(f"### 👉 [Clique aqui para abrir o WhatsApp e enviar o seu pedido]({link_whatsapp})", unsafe_allow_html=True)

    # ==========================================
    # 2. PAINEL DO ADMINISTRADOR
    # ==========================================
    elif usuario["tipo"] == "Administrador":
        st.subheader("🔒 Painel do Administrador")
        
        admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5, admin_tab6 = st.tabs([
            "⚙️ Cardápio e Preços", 
            "📋 Pedidos em Tempo Real", 
            "🛒 Compras e Cupons",
            "🚚 Fornecedores",
            "🔐 Finanças dos Sócios",
            "📊 Fechamento de Caixa"
        ])
        
        with admin_tab1:
            st.markdown("### 🥩 Configuração de Carnes do Dia")
            novas_carnes = st.text_area("Lista de Carnes (separadas por vírgula):", value=", ".join(st.session_state.menu_diario["carnes"]))
            
            st.divider()
            st.markdown("### 🍚 Opções de Acompanhamento Base")
            novos_tipos_arroz = st.text_area("Opções Base (separadas por vírgula):", value=", ".join(st.session_state.menu_diario["tipos_arroz"]))

            st.divider()
            st.markdown("### 🥗 Outros Acompanhamentos")
            novos_acompanhamentos = st.text_area("Outros Acompanhamentos:", value=", ".join(st.session_state.menu_diario["acompanhamentos_padrao"]))
            
            st.divider()
            st.markdown("### 💰 Preço Padrão da Refeição")
            preco_marmita_novo = st.number_input("Preço Padrão (R$):", value=st.session_state.menu_diario["preco_marmita"], step=1.00)
            
            st.divider()
            st.markdown("### 🧃 Gestão de Preços de Sucos")
            novos_precos_sucos = {}
            for chave_suco, preco_atual in st.session_state.precos_sucos.items():
                novos_precos_sucos[chave_suco] = st.number_input(f"Preço ({chave_suco}) (R$):", min_value=0.0, value=float(preco_atual), step=0.50)
            
            if st.button("💾 Guardar Alterações do Cardápio", type="primary"):
                st.session_state.menu_diario["carnes"] = [c.strip() for c in novas_carnes.split(",") if c.strip()]
                st.session_state.menu_diario["tipos_arroz"] = [r.strip() for r in novos_tipos_arroz.split(",") if r.strip()]
                st.session_state.menu_diario["acompanhamentos_padrao"] = [a.strip() for a in novos_acompanhamentos.split(",") if a.strip()]
                st.session_state.menu_diario["preco_marmita"] = preco_marmita_novo
                st.session_state.precos_sucos = novos_precos_sucos
                st.success("Cardápio e preços atualizados com sucesso!")
                
        with admin_tab2:
            st.markdown("### 📥 Acompanhamento de Pedidos")
            if not st.session_state.pedidos_clientes:
                st.info("Nenhum pedido recebido.")
            else:
                filtro_status = st.selectbox("Filtrar por Status:", ["Todos", "Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"])
                
                pedidos_filtrados = st.session_state.pedidos_clientes
                if filtro_status != "Todos":
                    pedidos_filtrados = [p for p in st.session_state.pedidos_clientes if p["Estado"] == filtro_status]
                
                for index, ped in enumerate(st.session_state.pedidos_clientes):
                    with st.expander(f"Pedido #{ped['ID']} - Cliente: {ped['Cliente']} | Status: {ped['Estado']} (R$ {ped['Total']:.2f})"):
                        st.write(f"**Telefone:** {ped['Telefone']}")
                        st.write(f"**Horário de Retirada:** {ped['Horário Retirada']}")
                        st.write(f"**Pedido:** {ped['Pedido']}")
                        st.write(f"**Pagamento:** {ped['Pagamento']}")
                        
                        novo_estado = st.selectbox("Alterar Status:", ["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"], index=["Pendente", "Em Preparo", "Pronto p/ Retirada", "Pago / Concluído", "Cancelado"].index(ped['Estado']), key=f"status_sel_{ped['ID']}")
                        if st.button("💾 Atualizar Status", key=f"btn_status_{ped['ID']}"):
                            st.session_state.pedidos_clientes[index]["Estado"] = novo_estado
                            st.rerun()

        with admin_tab3:
            st.markdown("### 🧾 Gestão de Compras e Cupons")
            col_cup1, col_cup2, col_cup3 = st.columns(3)
            with col_cup1:
                empresa_cupom = st.text_input("Empresa / Estabelecimento:", placeholder="ex: Supermercado...")
            with col_cup2:
                data_compra_cupom = st.date_input("Data da Compra:", value=date.today())
            with col_cup3:
                obs_compra_cupom = st.text_input("Observação / Finalidade:", placeholder="ex: Insumos da semana...")

            uploaded_file = st.file_uploader("Enviar Foto do Cupom Fiscal:", type=["jpg", "png", "jpeg"])

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("📸 Simular Leitura Automática do Cupom", type="primary"):
                    empresa_nome_final = empresa_cupom.strip() if empresa_cupom.strip() else "Fornecedor Geral"
                    data_formatada = data_compra_cupom.strftime("%d/%m/%Y")
                    obs_final = obs_compra_cupom.strip() if obs_compra_cupom.strip() else "Compra de insumos"
                    
                    id_cupom_unico = f"{empresa_nome_final}_{data_formatada}_{obs_final}"
                    
                    if id_cupom_unico in st.session_state.cupons_importados:
                        st.warning("⚠️ Este cupom já foi importado anteriormente!")
                    else:
                        raw_items = [
                            {"produto": "PEPINO", "qtd": 1.615, "unidade": "KG", "vl_unit": 3.99, "total": 6.44, "pessoal": False},
                            {"produto": "ALFACE CRESPA", "qtd": 2, "unidade": "UN", "vl_unit": 6.90, "total": 13.80, "pessoal": False},
                            {"produto": "OLEO SOJA PET 900ML", "qtd": 20, "unidade": "UN", "vl_unit": 7.99, "total": 159.80, "pessoal": False},
                        ]
                        for item in raw_items:
                            item["empresa"] = empresa_nome_final
                            item["data"] = data_formatada
                            item["obs"] = obs_final

                        st.session_state.compras_registro.extend(raw_items)
                        st.session_state.cupons_importados.add(id_cupom_unico)
                        st.success("Cupom importado com sucesso!")
                        st.rerun()

            with col_b2:
                if st.button("🗑️ Limpar Compras"):
                    st.session_state.compras_registro = []
                    st.session_state.cupons_importados = set()
                    st.rerun()

            st.divider()
            st.markdown("### 📋 Itens Registrados")
            total_empresa = sum([c["total"] for c in st.session_state.compras_registro if not c["pessoal"]])
            total_pessoal = sum([c["total"] for c in st.session_state.compras_registro if c["pessoal"]])

            for idx, comp in enumerate(st.session_state.compras_registro):
                col_item1, col_item2, col_item3, col_item4 = st.columns([3, 1, 1, 1])
                with col_item1:
                    st.write(f"• **{comp['produto']}** (R$ {comp['vl_unit']:.2f})")
                    st.caption(f"🏢 {comp.get('empresa')} | 📅 {comp.get('data')}")
                    st.file_uploader("Foto produto:", type=["jpg", "png"], key=f"img_up_{idx}", label_visibility="collapsed")
                with col_item2:
                    st.write(f"R$ {comp['total']:.2f}")
                with col_item3:
                    pessoal_check = st.checkbox("Uso Pessoal?", value=comp["pessoal"], key=f"comp_pessoal_{idx}")
                    st.session_state.compras_registro[idx]["pessoal"] = pessoal_check
                with col_item4:
                    if st.button("Excluir", key=f"del_comp_{idx}"):
                        st.session_state.compras_registro.pop(idx)
                        st.rerun()

            c_tot1, c_tot2 = st.columns(2)
            with c_tot1:
                st.metric("Custos Empresa", f"R$ {total_empresa:.2f}")
            with c_tot2:
                st.metric("Gastos Pessoais", f"R$ {total_pessoal:.2f}")

        with admin_tab4:
            st.markdown("### 🚚 Gestão de Fornecedores")
            with st.form("form_novo_fornecedor"):
                nome_fornecedor = st.text_input("Nome do Fornecedor:")
                contato_fornecedor = st.text_input("Telefone / WhatsApp:")
                produtos_fornecidos = st.text_input("Produtos:")
                obs_fornecedor = st.text_input("Observações:")
                if st.form_submit_button("💾 Salvar Fornecedor", type="primary"):
                    st.session_state.fornecedores_registro.append({"nome": nome_fornecedor, "contato": contato_fornecedor, "produtos": produtos_fornecidos, "obs": obs_fornecedor})
                    st.rerun()

            for idx, forn in enumerate(st.session_state.fornecedores_registro):
                with st.expander(f"🏢 {forn['nome']}"):
                    st.write(f"**Contato:** {forn['contato']} | **Produtos:** {forn['produtos']}")

        with admin_tab5:
            st.markdown("### 🔐 Área Restrita dos Proprietários (Patrão)")
            st.info("Apenas o dono da empresa tem acesso ao balanço final de dívidas e despesas particulares.")
            senha_acesso = st.text_input("Digite a Senha Mestra do Proprietário:", type="password")

            if senha_acesso != "1234":
                st.warning("🔒 Digite a senha mestra (padrão: 1234) para liberar o acesso exclusivo do dono.")
            else:
                st.success("🔓 Acesso exclusivo liberado.")
                df_vendas = pd.DataFrame(st.session_state.pedidos_clientes) if st.session_state.pedidos_clientes else pd.DataFrame()
                total_pagos = df_vendas[df_vendas["Estado"] == "Pago / Concluído"]["Total"].sum() if not df_vendas.empty else 0.0
                custo_compras_insumos = sum([c["total"] for c in st.session_state.compras_registro if not c["pessoal"]])
                lucro_operacional = total_pagos - custo_compras_insumos
                
                st.metric("Lucro Líquido Operacional", f"R$ {lucro_operacional:.2f}")

        with admin_tab6:
            st.markdown("### 📊 Fechamento de Caixa")
            df_vendas = pd.DataFrame(st.session_state.pedidos_clientes) if st.session_state.pedidos_clientes else pd.DataFrame()
            total_pagos = df_vendas[df_vendas["Estado"] == "Pago / Concluído"]["Total"].sum() if not df_vendas.empty else 0.0
            custo_compras = sum([c["total"] for c in st.session_state.compras_registro if not c["pessoal"]])
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric(label="Vendas Recebidas", value=f"R$ {total_pagos:.2f}")
            with col_m2:
                st.metric(label="Compras Insumos", value=f"R$ {custo_compras:.2f}")
