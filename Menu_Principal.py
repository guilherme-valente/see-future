import streamlit as st
import bcrypt
from pathlib import Path
from supabase import create_client, Client

FAVICON_PATH = Path(__file__).parent / "assets" / "future_icon.png"

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================================
st.set_page_config(
    page_title="Portal | SEE FUTURE",
    page_icon=str(FAVICON_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Cores oficiais da marca FUTURE
TEAL = "#00AEAD"        # Pantone 7711C
TEAL_DARK = "#00807F"
BLACK = "#232122"       # Pantone Black


# ==========================================================
# LIGAÇÃO À BASE DE DADOS (SUPABASE)
# ==========================================================
@st.cache_resource
def iniciar_ligacao() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


try:
    supabase = iniciar_ligacao()
except Exception as e:
    st.error(f"Erro de ligação ao servidor: {e}")
    st.stop()


# ==========================================================
# ESTADO DA SESSÃO
# ==========================================================
def garantir_estado(chave: str, valor_inicial):
    """Cria a chave no session_state caso ainda não exista."""
    if chave not in st.session_state:
        st.session_state[chave] = valor_inicial


garantir_estado("autenticado", False)
garantir_estado("nome_utilizador", "")
garantir_estado("papel_utilizador", "")
garantir_estado("modulo_ativo", "menu")  # 'menu' | 'laboratorio' | 'avaliacao'


# ==========================================================
# PÁGINAS (st.Page)
# ==========================================================
paginas_laboratorio = {
    "dashboard": st.Page("pages/0_Dashboard.py", title="Dashboard", default=True),
    "novo": st.Page("pages/1_Novo_Concurso.py", title="Novo Concurso"),
    "consultar": st.Page("pages/2_Consultar_Concursos.py", title="Consultar Concursos"),
    "concorrencia": st.Page("pages/3_Análise_Concorrência.py", title="Análise Concorrência"),
    "clientes": st.Page("pages/4_Análise_Clientes.py", title="Análise Clientes"),
    "estatisticas": st.Page("pages/5_Estatísticas_Globais.py", title="Estatísticas Globais"),
    "gestao_utilizadores": st.Page("pages/6_Gestão_Utilizadores.py", title="Gestão Utilizadores"),
}

paginas_avaliacao = [
    st.Page("pages/7a_Posicionamento.py", title="Posicionamento", default=True),
    st.Page("pages/7b_Rentabilidade.py", title="Rentabilidade"),
]


# ==========================================================
# CSS GLOBAL — identidade visual FUTURE
# ==========================================================
CSS_GLOBAL = f"""
<style>
.uau-card {{
    background: linear-gradient(145deg, #ffffff, #f4f6f9);
    border: 1px solid #e1e4e8;
    border-top: 4px solid {TEAL};
    border-radius: 24px;
    padding: 40px 25px;
    text-align: center;
    box-shadow: 5px 5px 20px rgba(0, 0, 0, 0.04), -5px -5px 20px rgba(255, 255, 255, 1);
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    height: 220px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    margin-bottom: 15px;
}}
.uau-card:hover {{
    transform: translateY(-8px);
    box-shadow: 0px 15px 30px rgba(0, 174, 173, 0.25);
    border-color: {TEAL};
}}
.uau-title {{
    color: {BLACK};
    font-size: 28px;
    font-weight: 800;
    margin-bottom: 12px;
    letter-spacing: -0.5px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}}
.uau-desc {{
    color: #5E6C84;
    font-size: 15px;
    line-height: 1.6;
}}
.future-header {{
    background: linear-gradient(120deg, {TEAL}, {TEAL_DARK});
    border-radius: 0 0 40px 40px;
    padding: 18px 30px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 25px;
}}
div.stButton > button[kind="primary"] {{
    background-color: {TEAL};
    border: none;
    border-radius: 10px;
}}
div.stButton > button[kind="primary"]:hover {{
    background-color: {TEAL_DARK};
}}
/* Esconde o selo do Streamlit Community Cloud */
[data-testid="stStatusWidget"],
.viewerBadge_container__r5tak,
.viewerBadge_link__qRIco {{
    display: none !important;
}}
</style>
"""

# CSS usado nos ecrãs de login e seleção de módulo, para esconder a barra lateral
CSS_ESCONDER_SIDEBAR = """
<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
</style>
"""

st.markdown(CSS_GLOBAL, unsafe_allow_html=True)


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================
def mostrar_cartao(titulo: str, descricao: str):
    """Desenha um cartão de apresentação de módulo."""
    st.markdown(
        f"""
        <div class="uau-card">
            <div class="uau-title">{titulo}</div>
            <div class="uau-desc">{descricao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def terminar_sessao():
    """Repõe o estado de autenticação e volta ao ecrã inicial."""
    st.session_state["autenticado"] = False
    st.session_state["nome_utilizador"] = ""
    st.session_state["papel_utilizador"] = ""
    st.session_state["modulo_ativo"] = "menu"
    st.rerun()


# ==========================================================
# ECRÃ 1 — LOGIN
# ==========================================================
def ecra_login():
    st.markdown(CSS_ESCONDER_SIDEBAR, unsafe_allow_html=True)

    _, col_login, _ = st.columns([1, 2, 1])

    with col_login:
        st.markdown(
            "<div style='text-align: center; margin-bottom: 30px;'>"
            "<h2 style='color:#232122;'>Acesso Reservado</h2>"
            "<p>Por favor, introduza as suas credenciais para aceder à plataforma "
            "<b>SEE FUTURE</b>.</p></div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            with st.form("form_login"):
                email = st.text_input("Email Corporativo", placeholder="exemplo@future.proman.pt")
                password = st.text_input("Palavra-Passe", type="password", placeholder="••••••••")
                submetido = st.form_submit_button("Iniciar Sessão", type="primary", use_container_width=True)

                if submetido:
                    validar_login(email, password)


def validar_login(email: str, password: str):
    """Verifica as credenciais introduzidas contra a base de dados."""
    if not email or not password:
        st.warning("É obrigatório preencher ambos os campos para validar o acesso.")
        return

    resposta = supabase.table("utilizadores").select("*").eq(
        "email", email.strip().lower()
    ).execute()

    if not resposta.data:
        st.error("E-mail/Utilizador ou Palavra-Passe incorreto(s)")
        return

    utilizador = resposta.data[0]
    hash_guardado = utilizador["password_hash"]

    if bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8")):
        st.session_state["autenticado"] = True
        st.session_state["nome_utilizador"] = utilizador["nome"]
        st.session_state["papel_utilizador"] = utilizador["papel"]
        st.success("Acesso Autorizado! A preparar ambiente...")
        st.rerun()
    else:
        st.error("E-mail/Utilizador ou Palavra-Passe incorreto(s)")


# ==========================================================
# ECRÃ 2 — SELEÇÃO DE MÓDULO
# ==========================================================
def ecra_selecao_modulo():
    st.markdown(CSS_ESCONDER_SIDEBAR, unsafe_allow_html=True)

    col_info, col_sair = st.columns([3, 1])
    with col_info:
        st.markdown(
            f"Sessão iniciada como: **{st.session_state['nome_utilizador']}** "
            f"({st.session_state['papel_utilizador'].upper()})"
        )
    with col_sair:
        if st.button("Terminar Sessão", use_container_width=True):
            terminar_sessao()

    st.divider()

    st.markdown(f"<h1 style='color:{BLACK};'>Plataforma SEE FUTURE</h1>", unsafe_allow_html=True)
    st.markdown("Selecione o ambiente operacional ou estratégico pretendido.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        mostrar_cartao(
            "Laboratório",
            "Espaço analítico dedicado à gestão de concursos públicos, avaliação "
            "da concorrência e comportamento de clientes.",
        )
        if st.button("Entrar no Laboratório", type="primary", use_container_width=True):
            st.session_state["modulo_ativo"] = "laboratorio"
            st.rerun()

    with col2:
        mostrar_cartao(
            "Avaliação",
            "Módulo de inteligência preditiva. Simule cenários concorrenciais e "
            "avalie a rentabilidade antes de submeter propostas.",
        )
        if st.button("Entrar na Avaliação", type="primary", use_container_width=True):
            st.session_state["modulo_ativo"] = "avaliacao"
            st.rerun()

    with col3:
        mostrar_cartao(
            "Radar",
            "Módulo estratégico em desenvolvimento. Destinado à prospeção "
            "avançada e mapeamento preventivo de mercado.",
        )
        if st.button("Entrar no Radar", type="primary", use_container_width=True):
            st.info("O módulo Radar encontra-se em fase de desenvolvimento técnico e estará disponível brevemente.")


# ==========================================================
# ROTEAMENTO PRINCIPAL
# ==========================================================
def rotear():
    if not st.session_state["autenticado"]:
        ecra_login()
        return

    modulo = st.session_state["modulo_ativo"]

    if modulo == "laboratorio":
        paginas = list(paginas_laboratorio.values())[:-1]  # todas exceto gestão de utilizadores
        if str(st.session_state.get("papel_utilizador", "")).strip().lower() == "admin":
            paginas.append(paginas_laboratorio["gestao_utilizadores"])
        st.navigation(paginas).run()

    elif modulo == "avaliacao":
        st.navigation(paginas_avaliacao).run()

    else:
        ecra_selecao_modulo()


rotear()
