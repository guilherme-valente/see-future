import streamlit as st
import bcrypt
from supabase import create_client, Client

# ==========================================================
# 1. CONFIGURAÇÃO DA PÁGINA PRINCIPAL
# ==========================================================
st.set_page_config(page_title="Portal | See Future", layout="wide", initial_sidebar_state="collapsed")

# ==========================================================
# 2. LIGAÇÃO À BASE DE DADOS (SUPABASE)
# ==========================================================
@st.cache_resource
def iniciar_ligacao():
    url = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    return create_client(url, chave)

try:
    supabase: Client = iniciar_ligacao()
except Exception as e:
    st.error(f"Erro de ligação ao servidor: {e}")

# ==========================================================
# 3. INICIALIZAÇÃO DA MEMÓRIA DE SESSÃO (SESSION STATE)
# ==========================================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
if 'nome_utilizador' not in st.session_state:
    st.session_state['nome_utilizador'] = ""
if 'papel_utilizador' not in st.session_state:
    st.session_state['papel_utilizador'] = ""
if 'modulo_ativo' not in st.session_state:
    st.session_state['modulo_ativo'] = 'menu'  # 'menu' | 'laboratorio' | 'avaliacao'

# ==========================================================
# 4. DEFINIÇÃO DAS PÁGINAS (st.Page)
# ==========================================================
# --- Laboratório ---
pg_dashboard = st.Page("pages/0_Dashboard.py", title="Dashboard", default=True)
pg_novo = st.Page("pages/1_Novo_Concurso.py", title="Novo Concurso")
pg_consultar = st.Page("pages/2_Consultar_Concursos.py", title="Consultar Concursos")
pg_concorrencia = st.Page("pages/3_Análise_Concorrência.py", title="Análise Concorrência")
pg_clientes = st.Page("pages/4_Análise_Clientes.py", title="Análise Clientes")
pg_estatisticas = st.Page("pages/5_Estatísticas_FUTURE.py", title="Estatísticas FUTURE")
pg_gestao_utilizadores = st.Page("pages/6_Gestão_Utilizadores.py", title="Gestão Utilizadores")

# --- Avaliação ---
pg_posicionamento = st.Page("pages/7a_Posicionamento.py", title="Posicionamento", default=True)
pg_rentabilidade = st.Page("pages/7b_Rentabilidade.py", title="Rentabilidade")

# ==========================================================
# 5. CSS GLOBAL (cartões do menu principal)
# ==========================================================
# ==========================================================
# 5. CSS GLOBAL FUTURE
# ==========================================================

st.markdown("""
<style>
:root{
    --future-blue:#091E42;
    --future-teal:#00AEAD;
    --future-light:#F4F7FA;
    --future-text:#42526E;
    --future-border:#E6EAF0;
}

/* Página */
.stApp{
    background-color:white;
    font-family:'Segoe UI',sans-serif;
}

/* Header Streamlit */
header{
    visibility:hidden;
}

/* Tipografia */
h1,h2,h3,h4{
    color:var(--future-blue);
    font-family:'Segoe UI',sans-serif;
}

p,span,label,div{
    font-family:'Segoe UI',sans-serif;
}

/* Inputs */
.stTextInput input{
    border-radius:12px;
    border:1px solid var(--future-border);
}
.stTextInput input:focus{
    border-color:var(--future-teal);
}

/* Botões */
.stButton button,
.stFormSubmitButton button{
    width:100%;
    background:var(--future-teal)!important;
    color:white!important;
    border:none!important;
    border-radius:12px!important;
    font-weight:700!important;
    height:48px!important;
    transition:0.3s ease!important;
}

.stButton button:hover,
.stFormSubmitButton button:hover{
    background:var(--future-blue)!important;
    transform:translateY(-2px);
}

/* Cards */
.uau-card{
    background:white;
    border:1px solid var(--future-border);
    border-radius:22px;
    padding:35px;
    min-height:280px;
    display:flex;
    flex-direction:column;
    justify-content:center;
    text-align:center;
    transition:0.3s ease;
    box-shadow:
    0px 4px 12px rgba(9,30,66,0.05);
    margin-bottom:12px;
}

.uau-card:hover{
    transform:translateY(-6px);
    border-color:var(--future-teal);
    box-shadow:
    0px 12px 24px rgba(0,174,173,0.15);
}

.uau-title{
    color:var(--future-blue);
    font-size:32px;
    font-weight:800;
    margin-bottom:15px;
}

.uau-desc{
    color:#5E6C84;
    line-height:1.7;
    font-size:15px;
}

/* Containers */
[data-testid="stVerticalBlockBorderWrapper"]{
    border-radius:20px;
}

/* Sidebar */
[data-testid="stSidebar"]{
    background:#091E42;
}

[data-testid="stSidebar"] *{
    color:white;
}

/* Métricas */
[data-testid="metric-container"]{
    border:1px solid var(--future-border);
    border-radius:16px;
    background:white;
    padding:15px;
}

/* Tabelas */
[data-testid="stDataFrame"]{
    border-radius:16px;
    overflow:hidden;
}

/* Dividers */
hr{
    border-color:#E6EAF0;
}
</style>
""", unsafe_allow_html=True)


def ecra_login():
    """Formulário de autenticação (Face 1)."""
    st.markdown("""
    <div style="
    text-align:center;
    padding-top:50px;
    padding-bottom:30px;
    ">
    
    <h1 style="
    font-size:56px;
    font-weight:900;
    color:#091E42;
    margin-bottom:10px;
    ">
    SEE FUTURE
    </h1>
    
    <p style="
    font-size:22px;
    color:#00AEAD;
    font-weight:600;
    margin-bottom:5px;
    ">
    Engineering Intelligence Platform
    </p>
    
    <p style="
    color:#6B778C;
    font-size:16px;
    ">
    Innovation • Leadership • Results
    </p>
    
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='text-align: center; margin-bottom: 30px;'>", unsafe_allow_html=True)
    st.title("Acesso Reservado")
    st.markdown("Por favor, introduza as suas credenciais para aceder à plataforma **See Future**.")
    st.markdown("</div>", unsafe_allow_html=True)

    col_vazia1, col_login, col_vazia2 = st.columns([1, 2, 1])

    with col_login:
        with st.container(border=True):
            with st.form("form_login"):
                email_inserido = st.text_input("Email Corporativo", placeholder="exemplo@seefuture.pt")
                password_inserida = st.text_input("Palavra-Passe", type="password", placeholder="••••••••")

                submetido = st.form_submit_button("Iniciar Sessão", type="primary", use_container_width=True)

                if submetido:
                    if email_inserido and password_inserida:
                        resposta = supabase.table("utilizadores").select("*").eq(
                            "email", email_inserido.strip().lower()
                        ).execute()

                        if len(resposta.data) > 0:
                            dados_utilizador = resposta.data[0]
                            hash_guardado = dados_utilizador['password_hash']

                            if bcrypt.checkpw(password_inserida.encode('utf-8'), hash_guardado.encode('utf-8')):
                                st.session_state['autenticado'] = True
                                st.session_state['nome_utilizador'] = dados_utilizador['nome']
                                st.session_state['papel_utilizador'] = dados_utilizador['papel']
                                st.success("Acesso Autorizado! A preparar ambiente...")
                                st.rerun()
                            else:
                                st.error("A palavra-passe introduzida está incorreta.")
                        else:
                            st.error("Não foi encontrado nenhum utilizador com este endereço de email.")
                    else:
                        st.warning("É obrigatório preencher ambos os campos para validar o acesso.")


def ecra_selecao_modulo():
    """Ecrã de seleção de módulo (Face 2) — Laboratório / Avaliação / Radar."""
    st.markdown("""
    <div style="
    text-align:center;
    margin-bottom:40px;
    ">
    
    <h1 style="
    font-size:46px;
    font-weight:900;
    color:#091E42;
    ">
    SEE FUTURE
    </h1>
    
    <p style="
    font-size:20px;
    color:#00AEAD;
    font-weight:700;
    margin-top:-10px;
    ">
    Engenharia Para Além da Técnica
    </p>
    
    </div>
    """, unsafe_allow_html=True)

    col_header1, col_header2 = st.columns([4, 1])
    with col_header1:
        st.markdown(
            f"Sessão iniciada como: **{st.session_state['nome_utilizador']}** "
            f"({st.session_state['papel_utilizador'].upper()})"
        )
    with col_header2:
        if st.button("Terminar Sessão", use_container_width=True):
            st.session_state['autenticado'] = False
            st.session_state['nome_utilizador'] = ""
            st.session_state['papel_utilizador'] = ""
            st.session_state['modulo_ativo'] = 'menu'
            st.rerun()

    st.divider()

    st.title("Plataforma See Future")
    st.markdown("Selecione o ambiente operacional ou estratégico pretendido.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            '''
            <div class="uau-card">
                <div class="uau-title">Laboratório</div>
                <div class="uau-desc">Espaço analítico dedicado à gestão de concursos públicos, avaliação da concorrência e comportamento de clientes.</div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        if st.button("Entrar no Laboratório", type="primary", use_container_width=True):
            st.session_state['modulo_ativo'] = 'laboratorio'
            st.rerun()

    with col2:
        st.markdown(
            '''
            <div class="uau-card">
                <div class="uau-title">Avaliação</div>
                <div class="uau-desc">Módulo de inteligência preditiva. Simule cenários concorrenciais e avalie a rentabilidade antes de submeter propostas.</div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        if st.button("Entrar na Avaliação", type="primary", use_container_width=True):
            st.session_state['modulo_ativo'] = 'avaliacao'
            st.rerun()

    with col3:
        st.markdown(
            '''
            <div class="uau-card">
                <div class="uau-title">Radar</div>
                <div class="uau-desc">Módulo estratégico em desenvolvimento. Destinado à prospeção avançada e mapeamento preventivo de mercado.</div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        if st.button("Entrar no Radar", type="primary", use_container_width=True):
            st.info("O módulo Radar encontra-se em fase de desenvolvimento técnico e estará disponível brevemente.")


# ==========================================================
# 6. ROTEAMENTO PRINCIPAL
# ==========================================================
if not st.session_state['autenticado']:
    ecra_login()

elif st.session_state['modulo_ativo'] == 'laboratorio':
    paginas_lab = [pg_dashboard, pg_novo, pg_consultar, pg_concorrencia, pg_clientes, pg_estatisticas]
    if str(st.session_state.get('papel_utilizador', '')).strip().lower() == 'admin':
        paginas_lab.append(pg_gestao_utilizadores)
    nav = st.navigation(paginas_lab)
    nav.run()

elif st.session_state['modulo_ativo'] == 'avaliacao':
    paginas_aval = [pg_posicionamento, pg_rentabilidade]
    nav = st.navigation(paginas_aval)
    nav.run()

else:
    ecra_selecao_modulo()
