import uuid
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
import bcrypt
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController

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
TEAL = "#00AEAD"  # Pantone 7711C
TEAL_DARK = "#00807F"
BLACK = "#232122"  # Pantone Black

# ==========================================================
# CONFIGURAÇÃO DE SESSÃO / COOKIES
# ==========================================================
TEMPO_LIMITE_INATIVIDADE = timedelta(minutes=60)
NOME_COOKIE_SESSAO = "see_future_session"

cookies = CookieController()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


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
garantir_estado("utilizador_id", None)
garantir_estado("modulo_ativo", "menu")  # 'menu' | 'laboratorio' | 'avaliacao'
garantir_estado("sessao_token", None)
garantir_estado("sessao_restaurada", False)  # evita repetir a restauração em todo rerun

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

paginas_radar = [
    st.Page("pages/8a_Procurador.py", title="Procurador", default=True),
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
# FUNÇÕES AUXILIARES — UI
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


# ==========================================================
# FUNÇÕES AUXILIARES — SESSÃO, COOKIES E LOGS
# ==========================================================
def criar_sessao(utilizador: dict) -> str:
    """Cria um registo de sessão na BD, define o cookie e o session_state."""
    token = str(uuid.uuid4())
    expira_em = _agora() + TEMPO_LIMITE_INATIVIDADE

    supabase.table("sessoes_ativas").insert({
        "token": token,
        "utilizador_id": utilizador["id"],
        "criado_em": _agora().isoformat(),
        "ultima_atividade": _agora().isoformat(),
        "expira_em": expira_em.isoformat(),
    }).execute()

    st.session_state["autenticado"] = True
    st.session_state["nome_utilizador"] = utilizador["nome"]
    st.session_state["papel_utilizador"] = utilizador["papel"]
    st.session_state["utilizador_id"] = utilizador["id"]
    st.session_state["sessao_token"] = token

    cookies.set(
        NOME_COOKIE_SESSAO,
        token,
        max_age=int(TEMPO_LIMITE_INATIVIDADE.total_seconds()),
    )

    registar_log(utilizador["id"], utilizador.get("email", ""), "login", sessao_token=token)
    return token


def restaurar_sessao_do_cookie():
    if st.session_state["autenticado"]:
        return

    todos_cookies = cookies.getAll()

    # O componente ainda não sincronizou com o browser nesta execução —
    # não podemos concluir nada ainda, tentamos de novo no próximo run.
    if todos_cookies is None:
        return

    if st.session_state["sessao_restaurada"]:
        return
    st.session_state["sessao_restaurada"] = True

    token = todos_cookies.get(NOME_COOKIE_SESSAO)
    if not token:
        return

    resposta = supabase.table("sessoes_ativas").select("*, utilizadores(*)").eq(
        "token", token
    ).execute()

    if not resposta.data:
        cookies.remove(NOME_COOKIE_SESSAO)
        return

    sessao = resposta.data[0]
    expira_em = datetime.fromisoformat(sessao["expira_em"])
    if expira_em < _agora():
        supabase.table("sessoes_ativas").delete().eq("token", token).execute()
        cookies.remove(NOME_COOKIE_SESSAO)
        return

    utilizador = sessao["utilizadores"]
    st.session_state["autenticado"] = True
    st.session_state["nome_utilizador"] = utilizador["nome"]
    st.session_state["papel_utilizador"] = utilizador["papel"]
    st.session_state["utilizador_id"] = utilizador["id"]
    st.session_state["sessao_token"] = token

    registar_atividade()


def registar_atividade():
    """Atualiza 'última atividade' na BD e prolonga a expiração da sessão + cookie."""
    token = st.session_state.get("sessao_token")
    if not token:
        return

    nova_expiracao = _agora() + TEMPO_LIMITE_INATIVIDADE
    supabase.table("sessoes_ativas").update({
        "ultima_atividade": _agora().isoformat(),
        "expira_em": nova_expiracao.isoformat(),
    }).eq("token", token).execute()

    cookies.set(
        NOME_COOKIE_SESSAO,
        token,
        max_age=int(TEMPO_LIMITE_INATIVIDADE.total_seconds()),
    )


def sessao_expirou() -> bool:
    token = st.session_state.get("sessao_token")
    if not token:
        return False

    resposta = supabase.table("sessoes_ativas").select("expira_em").eq("token", token).execute()
    if not resposta.data:
        return True  # sessão foi removida da BD (ex: admin forçou logout)

    expira_em = datetime.fromisoformat(resposta.data[0]["expira_em"])
    return expira_em < _agora()


def registar_log(utilizador_id, email: str, evento: str, detalhe: str = None, sessao_token: str = None):
    """Escreve uma linha na tabela logs_atividade. Nunca deve rebentar a app."""
    try:
        supabase.table("logs_atividade").insert({
            "utilizador_id": utilizador_id,
            "email": email,
            "evento": evento,
            "detalhe": detalhe,
            "sessao_token": sessao_token or st.session_state.get("sessao_token"),
        }).execute()
    except Exception:
        pass  # falha a registar log nunca deve impedir o uso da app


def registar_pagina_vista(nome_pagina: str):
    """Chamar no topo de cada página em pages/ para registar navegação."""
    registar_log(
        st.session_state.get("utilizador_id"),
        "",
        "pagina_vista",
        detalhe=nome_pagina,
    )


def terminar_sessao(motivo: str = "manual"):
    """Repõe o estado de autenticação, limpa cookies/BD e volta ao ecrã inicial."""
    token = st.session_state.get("sessao_token")
    utilizador_id = st.session_state.get("utilizador_id")

    if token:
        registar_log(
            utilizador_id, "",
            "logout" if motivo == "manual" else "logout_inatividade",
            sessao_token=token,
        )
        try:
            supabase.table("sessoes_ativas").delete().eq("token", token).execute()
        except Exception:
            pass

    cookies.remove(NOME_COOKIE_SESSAO)

    st.session_state["autenticado"] = False
    st.session_state["nome_utilizador"] = ""
    st.session_state["papel_utilizador"] = ""
    st.session_state["utilizador_id"] = None
    st.session_state["sessao_token"] = None
    st.session_state["modulo_ativo"] = "menu"
    st.session_state["sessao_restaurada"] = False

    if motivo == "inatividade":
        st.session_state["mensagem_logout"] = True
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
        st.error("Não foi encontrado nenhum utilizador com este endereço de email.")
        return

    utilizador = resposta.data[0]
    hash_guardado = utilizador["password_hash"]

    if bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8")):
        criar_sessao(utilizador)
        st.success("Acesso Autorizado! A preparar ambiente...")
        st.rerun()
    else:
        st.error("A palavra-passe introduzida está incorreta.")


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
            terminar_sessao(motivo="manual")

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
            st.session_state["modulo_ativo"] = "radar"
            st.rerun()

# ==========================================================
# ROTEAMENTO PRINCIPAL
# ==========================================================
def rotear():
    restaurar_sessao_do_cookie()

    if st.session_state.pop("mensagem_logout", False):
        st.warning("A sua sessão expirou por inatividade. Inicie sessão novamente.")

    if not st.session_state["autenticado"]:
        ecra_login()
        return

    if sessao_expirou():
        terminar_sessao(motivo="inatividade")
        return

    registar_atividade()

    modulo = st.session_state["modulo_ativo"]

    if modulo == "laboratorio":
        paginas = list(paginas_laboratorio.values())[:-1]
        if str(st.session_state.get("papel_utilizador", "")).strip().lower() == "admin":
            paginas.append(paginas_laboratorio["gestao_utilizadores"])
        st.navigation(paginas).run()
    elif modulo == "avaliacao":
        st.navigation(paginas_avaliacao).run()
    elif modulo == "radar":
        st.navigation(paginas_radar).run()
    else:
        ecra_selecao_modulo()


rotear()
