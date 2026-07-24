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