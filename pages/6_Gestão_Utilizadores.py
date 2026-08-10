import streamlit as st
import pandas as pd
import bcrypt as bcrypt
from supabase import create_client, Client

# ==========================================================
# CONFIGURAÇÃO BASE DA PÁGINA (Deve ser o primeiro comando)
# ==========================================================
st.set_page_config(page_title="Gestão de Utilizadores | See Future", layout="centered")

# --- TRANCAR A PÁGINA CONTRA ACESSOS DIRETOS E NÃO ADMINS ---
if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

# Normalização do papel para validação estrita
papel_atual = str(st.session_state.get('papel_utilizador', '')).strip().lower()

if papel_atual != 'admin':
    st.error("Acesso restrito. Apenas utilizadores com privilégios de Administrador podem aceder a esta secção.")
    st.stop()
# -----------------------------------------------------------

# Regista a visita a esta página no log de atividade (função definida em Menu_Principal.py)
try:
    registar_pagina_vista("Gestão_Utilizadores")
except NameError:
    pass  # segurança: nunca bloquear a página por causa do logging

st.title("Gestão de Utilizadores e Acessos")
st.markdown("Crie e monitorize as contas de acesso à plataforma corporativa.")
st.divider()

# Ligação à Base de Dados
@st.cache_resource
def iniciar_ligacao():
    url = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    return create_client(url, chave)

try:
    supabase: Client = iniciar_ligacao()
except Exception as e:
    st.error(f"Erro de ligação: {e}")
    st.stop()

# ==========================================================
# BLOCO 2: A INTERFACE DE INTRODUÇÃO (FORMULÁRIO)
# ==========================================================
st.subheader("Criar Novo Utilizador")

with st.container(border=True):
    with st.form("form_novo_utilizador", clear_on_submit=True):

        nome = st.text_input("Nome Completo", placeholder="Ex: João Silva")
        email = st.text_input("Email Corporativo", placeholder="Ex: joao.silva@seefuture.pt")

        col_pass, col_papel = st.columns(2)
        with col_pass:
            password_texto = st.text_input("Palavra-Passe Inicial", type="password", placeholder="Defina uma senha forte")
        with col_papel:
            papel = st.selectbox("Nível de Acesso (Cargo)", ["user", "admin"], index=0,
                                 help="Administradores têm permissões totais de eliminação e criação.")

        botao_criar = st.form_submit_button("Registar Utilizador", type="primary", use_container_width=True)

        if botao_criar:
            if nome and email and password_texto:
                if "@" not in email or "." not in email:
                    st.error("Por favor, introduza um endereço de email válido.")
                else:
                    try:
                        existe = supabase.table("utilizadores").select("id").eq("email", email.strip().lower()).execute()

                        if len(existe.data) > 0:
                            st.error("Este email já se encontra registado no sistema.")
                        else:
                            st.info("A processar chaves de segurança...")
                            salt = bcrypt.gensalt(rounds=12)
                            password_hash = bcrypt.hashpw(password_texto.encode('utf-8'), salt).decode('utf-8')

                            supabase.table("utilizadores").insert({
                                "nome": nome.strip(),
                                "email": email.strip().lower(),
                                "password_hash": password_hash,
                                "papel": papel
                            }).execute()

                            st.success(f"Utilizador {nome} registado com sucesso no ecossistema!")

                    except Exception as e:
                        st.error(f"Erro ao comunicar com o servidor: {e}")
            else:
                st.warning("Todos os campos do formulário são de preenchimento obrigatório.")

# ==========================================================
# EXTRA: VISUALIZAR UTILIZADORES ATIVOS
# ==========================================================
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Utilizadores com Acesso à Plataforma")

try:
    usuarios_bd = supabase.table("utilizadores").select("nome, email, papel, criado_em").execute()
    if usuarios_bd.data:
        df_usuarios = pd.DataFrame(usuarios_bd.data)
        df_usuarios['criado_em'] = pd.to_datetime(df_usuarios['criado_em']).dt.date
        df_usuarios.columns = ['Nome', 'Email', 'Nível de Acesso', 'Data de Registo']
        st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
except Exception as e:
    pass

# ==========================================================
# BLOCO 3: ATIVIDADE DOS UTILIZADORES (LOGS)
# ==========================================================
st.markdown("<br>", unsafe_allow_html=True)
st.divider()
st.subheader("Atividade dos Utilizadores")
st.caption("Auditoria de acessos: quem entrou, quando, duração da sessão e páginas visitadas.")

col_data_ini, col_data_fim, col_email = st.columns(3)
with col_data_ini:
    data_inicio = st.date_input("De", value=None, key="logs_data_inicio")
with col_data_fim:
    data_fim = st.date_input("Até", value=None, key="logs_data_fim")
with col_email:
    filtro_email = st.text_input("Filtrar por email (opcional)", key="logs_filtro_email")

try:
    query = supabase.table("logs_atividade").select("*").order("criado_em", desc=True).limit(1000)

    if data_inicio:
        query = query.gte("criado_em", data_inicio.isoformat())
    if data_fim:
        query = query.lte("criado_em", data_fim.isoformat())
    if filtro_email:
        query = query.ilike("email", f"%{filtro_email}%")

    resposta_logs = query.execute()
    logs = pd.DataFrame(resposta_logs.data)

    if logs.empty:
        st.info("Sem registos de atividade para os filtros selecionados.")
    else:
        logs['criado_em'] = pd.to_datetime(logs['criado_em'])

        # --- Tabela de eventos ---
        st.markdown("**Eventos**")
        st.dataframe(
            logs[['criado_em', 'email', 'evento', 'detalhe', 'sessao_token']]
            .rename(columns={
                'criado_em': 'Data/Hora',
                'email': 'Utilizador',
                'evento': 'Evento',
                'detalhe': 'Detalhe',
                'sessao_token': 'Sessão',
            }),
            use_container_width=True,
            hide_index=True,
        )

        # --- Duração de sessões (pares login / logout com o mesmo sessao_token) ---
        st.markdown("**Duração das sessões**")

        logins = logs[logs['evento'] == 'login'][['sessao_token', 'email', 'criado_em']].rename(
            columns={'criado_em': 'inicio'}
        )
        logouts = logs[logs['evento'].isin(['logout', 'logout_inatividade'])][
            ['sessao_token', 'criado_em', 'evento']
        ].rename(columns={'criado_em': 'fim', 'evento': 'tipo_fim'})

        sessoes = logins.merge(logouts, on='sessao_token', how='left')
        sessoes['duracao_min'] = (
            (sessoes['fim'] - sessoes['inicio']).dt.total_seconds() / 60
        ).where(sessoes['fim'].notna())
        sessoes['tipo_fim'] = sessoes['tipo_fim'].fillna('sessão ativa / sem logout registado')

        st.dataframe(
            sessoes[['email', 'inicio', 'fim', 'duracao_min', 'tipo_fim']]
            .rename(columns={
                'email': 'Utilizador',
                'inicio': 'Início',
                'fim': 'Fim',
                'duracao_min': 'Duração (min)',
                'tipo_fim': 'Terminou por',
            })
            .round({'Duração (min)': 1}),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Sessões sem 'Fim' registado correspondem a acessos ainda em curso ou a "
            "encerramentos anómalos do browser (ex: fechar o separador sem clicar em "
            "'Terminar Sessão'), que não disparam o evento de logout."
        )

except Exception as e:
    st.warning(
        "Não foi possível carregar os logs de atividade. Confirma se a tabela "
        f"'logs_atividade' já foi criada no Supabase. Detalhe: {e}"
    )
