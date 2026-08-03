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
# 5. IDENTIDADE VISUAL FUTURE — CSS GLOBAL
# ==========================================================
# Paleta oficial (Manual de Identidade FUTURE):
#   Pantone Black   -> CMYK 0,0,0,100  -> RGB 35,31,32   -> #232021
#   Pantone 7711C   -> CMYK 92,0,40,0  -> RGB 0,174,173  -> #00AEAD
# Tons derivados para gradientes/estados (variações da cor principal, tal
# como o manual permite "diferentes percentagens de cada uma das duas cores").

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,300;0,400;0,600;0,700;0,900;1,400&display=swap');

    :root {
        --future-black: #232021;
        --future-teal: #00AEAD;
        --future-teal-dark: #017D82;
        --future-teal-darker: #0B4F5C;
        --future-teal-light: #4FD1CE;
        --future-grey: #5E6C84;
        --future-bg: #F5F8F8;
    }

    html, body, [class*="css"]  {
        font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
    }

    /* Fundo geral da app, ligeiramente esverdeado como o papel dos relatórios FUTURE */
    .stApp {
        background: var(--future-bg);
    }

    /* Esconder cabeçalho nativo do Streamlit para dar lugar à nossa barra de marca */
    header[data-testid="stHeader"] {
        background: transparent;
    }

    /* ---------------------------------------------------------------
       BARRA DE MARCA — imita a faixa superior colorida usada nos
       slides e relatórios FUTURE (número/etiqueta de secção + logo)
       --------------------------------------------------------------- */
    .future-topbar {
        background: linear-gradient(100deg, var(--future-teal-darker) 0%, var(--future-teal) 55%, var(--future-teal-light) 100%);
        border-radius: 0 0 22px 22px;
        padding: 22px 40px;
        margin: -1rem -1rem 2rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 6px 24px rgba(0, 78, 78, 0.18);
        position: relative;
        overflow: hidden;
    }
    /* diagonais decorativas, como as usadas nos fundos dos slides FUTURE */
    .future-topbar::after {
        content: "";
        position: absolute;
        top: -40%;
        right: -5%;
        width: 260px;
        height: 260px;
        background: rgba(255,255,255,0.08);
        border-radius: 50%;
        transform: rotate(20deg);
    }
    .future-topbar::before {
        content: "";
        position: absolute;
        bottom: -60%;
        right: 18%;
        width: 160px;
        height: 160px;
        background: rgba(255,255,255,0.06);
        border-radius: 50%;
    }
    .future-wordmark {
        font-family: 'Source Sans 3', sans-serif;
        font-weight: 900;
        font-size: 26px;
        letter-spacing: 4px;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 1;
    }
    /* pequeno traço acima do texto, referência ao grafismo do "F" da marca */
    .future-wordmark .grafismo {
        width: 22px;
        height: 6px;
        background: #ffffff;
        border-radius: 4px 4px 0 0;
        display: inline-block;
        margin-right: 2px;
    }
    .future-tagline {
        font-size: 11px;
        letter-spacing: 2px;
        color: rgba(255,255,255,0.85);
        text-transform: uppercase;
        font-weight: 400;
        margin-top: 2px;
    }
    .future-session-info {
        color: #ffffff;
        font-size: 14px;
        text-align: right;
        z-index: 1;
    }
    .future-session-info b {
        font-weight: 700;
    }

    /* ---------------------------------------------------------------
       CARTÕES DE MÓDULO — cantos bem arredondados (como as "cápsulas"
       usadas em todos os separadores de capítulo do manual FUTURE)
       --------------------------------------------------------------- */
    .uau-card {
        background: #ffffff;
        border: 1px solid #E3EDED;
        border-radius: 28px;
        padding: 40px 28px;
        text-align: left;
        box-shadow: 0 10px 30px rgba(0, 78, 78, 0.06);
        transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        height: 230px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-bottom: 15px;
        position: relative;
        overflow: hidden;
    }
    .uau-card::before {
        content: "";
        position: absolute;
        top: -30px;
        left: -30px;
        width: 90px;
        height: 90px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--future-teal-light), var(--future-teal));
        opacity: 0.12;
    }
    .uau-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 18px 34px rgba(0, 174, 173, 0.18);
        border-color: var(--future-teal);
    }
    .uau-eyebrow {
        color: var(--future-teal-dark);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 8px;
        z-index: 1;
    }
    .uau-title {
        color: var(--future-black);
        font-size: 26px;
        font-weight: 800;
        margin-bottom: 12px;
        letter-spacing: -0.3px;
        z-index: 1;
    }
    .uau-desc {
        color: var(--future-grey);
        font-size: 14.5px;
        line-height: 1.6;
        z-index: 1;
    }

    /* Botões primários com a cor de marca */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(100deg, var(--future-teal-dark), var(--future-teal));
        border: none;
        border-radius: 12px;
        font-weight: 600;
        letter-spacing: 0.3px;
        box-shadow: 0 4px 14px rgba(0, 174, 173, 0.25);
    }
    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(100deg, var(--future-teal-darker), var(--future-teal-dark));
        box-shadow: 0 6px 18px rgba(0, 174, 173, 0.35);
    }
    div.stButton > button:not([kind="primary"]) {
        border-radius: 12px;
        border: 1px solid #D7E3E3;
    }

    /* Divider mais fino, na cor de marca */
    hr {
        border-top: 1px solid #D7E3E3 !important;
    }

    /* Cartão de login */
    div[data-testid="stForm"] {
        border-radius: 22px !important;
        border: 1px solid #E3EDED !important;
        padding: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def future_topbar(session_line: str | None = None):
    """Barra superior com a identidade FUTURE (gradiente petróleo + wordmark)."""
    session_html = f'<div class="future-session-info">{session_line}</div>' if session_line else '<div></div>'
    st.markdown(
        f"""
        <div class="future-topbar">
            <div>
                <div class="future-wordmark"><span class="grafismo"></span>FUTURE</div>
                <div class="future-tagline">Engenharia para além da técnica</div>
            </div>
            {session_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def ecra_login():
    """Formulário de autenticação (Face 1)."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    future_topbar()

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
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    sessao = (
        f"Sessão iniciada como <b>{st.session_state['nome_utilizador']}</b>"
        f" &nbsp;·&nbsp; {st.session_state['papel_utilizador'].upper()}"
    )
    future_topbar(sessao)

    col_header1, col_header2 = st.columns([5, 1])
    with col_header2:
        if st.button("Terminar Sessão", use_container_width=True):
            st.session_state['autenticado'] = False
            st.session_state['nome_utilizador'] = ""
            st.session_state['papel_utilizador'] = ""
            st.session_state['modulo_ativo'] = 'menu'
            st.rerun()

    st.title("Plataforma See Future")
    st.markdown("Selecione o ambiente operacional ou estratégico pretendido.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            '''
            <div class="uau-card">
                <div class="uau-eyebrow">01 · Operacional</div>
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
                <div class="uau-eyebrow">02 · Estratégico</div>
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
                <div class="uau-eyebrow">03 · Em breve</div>
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
    nav = st.navigation(paginas_aval)
    nav.run()

else:
    ecra_selecao_modulo()
