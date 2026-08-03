import time
import logging
from typing import Optional, Dict, Any

import streamlit as st
import bcrypt
from supabase import create_client, Client

# --------- Configuration & Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PAGE_TITLE = "Portal | See Future"
ROLE_ADMIN = "admin"
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 60 * 5  # 5 minutes


st.set_page_config(page_title=PAGE_TITLE, layout="wide", initial_sidebar_state="collapsed")


# --------- Supabase client ----------
@st.cache_resource
def get_supabase_client() -> Optional[Client]:
    """Initialize and return a Supabase client; return None on failure."""
    try:
        url = st.secrets.get("SUPABASE_URL")
        chave = st.secrets.get("SUPABASE_KEY")
        if not url or not chave:
            logger.error("Supabase secrets are missing.")
            return None
        return create_client(url, chave)
    except Exception as e:
        logger.exception("Failed to create Supabase client")
        return None


# --------- Session state initialization ----------
def init_session_state() -> None:
    defaults = {
        "autenticado": False,
        "nome_utilizador": "",
        "papel_utilizador": "",
        "modulo_ativo": "menu",  # 'menu' | 'laboratorio' | 'avaliacao'
        "login_attempts": 0,
        "lockout_until": 0.0,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


init_session_state()


# --------- CSS injection (idempotent) ----------
def inject_css() -> None:
    if st.session_state.get("_css_injected"):
        return
    st.markdown(
        """
        <style>
        .uau-card {
            background: linear-gradient(145deg, #ffffff, #f4f6f9);
            border: 1px solid #e1e4e8;
            border-radius: 16px;
            padding: 40px 25px;
            text-align: center;
            box-shadow: 5px 5px 20px rgba(0, 0, 0, 0.04), -5px -5px 20px rgba(255, 255, 255, 1);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            height: 220px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            margin-bottom: 15px;
        }
        .uau-card:hover {
            transform: translateY(-8px);
            box-shadow: 0px 15px 30px rgba(0, 82, 204, 0.15);
            border-color: #00AEAD;
        }
        .uau-title {
            color: #091E42;
            font-size: 28px;
            font-weight: 800;
            margin-bottom: 12px;
            letter-spacing: -0.5px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .uau-desc {
            color: #5E6C84;
            font-size: 15px;
            line-height: 1.6;
        }
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_css_injected"] = True


inject_css()


# --------- Auth helpers ----------
def is_locked_out() -> bool:
    return time.time() < float(st.session_state.get("lockout_until", 0.0))


def record_failed_attempt() -> None:
    st.session_state["login_attempts"] = st.session_state.get("login_attempts", 0) + 1
    if st.session_state["login_attempts"] >= MAX_LOGIN_ATTEMPTS:
        st.session_state["lockout_until"] = time.time() + LOCKOUT_SECONDS
        logger.warning("User locked out due to too many attempts.")


def reset_login_attempts() -> None:
    st.session_state["login_attempts"] = 0
    st.session_state["lockout_until"] = 0.0


def authenticate_user(supabase: Client, email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate against the 'utilizadores' table.
    Returns user record (dict) on success, else None.
    Uses generic error messages to avoid user enumeration.
    """
    if not supabase:
        logger.error("Supabase client is not initialized.")
        return None

    try:
        email_clean = email.strip().lower()
        resposta = supabase.table("utilizadores").select("*").eq("email", email_clean).limit(1).execute()

        # supabase client returns different shapes depending on version; be defensive:
        data = None
        if hasattr(resposta, "data"):
            data = resposta.data
        elif isinstance(resposta, dict):
            data = resposta.get("data")
        else:
            # last resort: try to inspect
            try:
                data = getattr(resposta, "json", lambda: None)()
            except Exception:
                data = None

        if not data:
            logger.info("Authentication failed: no user found for email %s", email_clean)
            return None

        user = data[0]
        stored_hash = user.get("password_hash") or user.get("password") or ""

        # Defensive: ensure stored_hash is a string
        if not stored_hash:
            logger.error("No password hash stored for user %s", email_clean)
            return None

        # bcrypt expects bytes
        try:
            match = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception as ex:
            logger.exception("bcrypt check failed")
            return None

        if match:
            logger.info("Authentication successful for user %s", email_clean)
            return user
        else:
            logger.info("Authentication failed: incorrect password for %s", email_clean)
            return None
    except Exception:
        logger.exception("Error during authentication")
        return None


# --------- UI rendering ----------
def render_login(supabase: Optional[Client]) -> None:
    """Render the login form and handle authentication flow."""
    st.markdown("<div style='text-align: center; margin-bottom: 30px;'>", unsafe_allow_html=True)
    st.title("Acesso Reservado")
    st.markdown("Por favor, introduza as suas credenciais para aceder à plataforma **See Future**.")
    st.markdown("</div>", unsafe_allow_html=True)

    if not supabase:
        st.error("Erro de ligação ao servidor. Por favor verifique a configuração do servidor.")
        return

    if is_locked_out():
        remaining = int(st.session_state["lockout_until"] - time.time())
        st.error(f"Muitas tentativas falhadas. Tente novamente em {remaining} segundos.")
        return

    col_vazia1, col_login, col_vazia2 = st.columns([1, 2, 1])
    with col_login:
        with st.form("form_login"):
            email_inserido = st.text_input("Email Corporativo", placeholder="exemplo@seefuture.pt")
            password_inserida = st.text_input("Palavra-Passe", type="password", placeholder="••••••••")
            submetido = st.form_submit_button("Iniciar Sessão", type="primary", use_container_width=True)

            if submetido:
                if not email_inserido or not password_inserida:
                    st.warning("É obrigatório preencher ambos os campos para validar o acesso.")
                    return

                with st.spinner("A validar credenciais..."):
                    user = authenticate_user(supabase, email_inserido, password_inserida)

                if user:
                    # Successful login
                    st.session_state["autenticado"] = True
                    st.session_state["nome_utilizador"] = user.get("nome", "")
                    st.session_state["papel_utilizador"] = user.get("papel", "")
                    reset_login_attempts()
                    st.success("Acesso Autorizado! A preparar ambiente...")
                    st.experimental_rerun()
                else:
                    # Generic message to avoid user enumeration
                    record_failed_attempt()
                    attempts_left = max(0, MAX_LOGIN_ATTEMPTS - st.session_state.get("login_attempts", 0))
                    st.error(f"Credenciais inválidas. Tentativas restantes: {attempts_left}")


def _render_card(title: str, desc: str) -> None:
    st.markdown(
        f"""
        <div class="uau-card">
            <div class="uau-title">{title}</div>
            <div class="uau-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_module_selection() -> None:
    """Render the module selection screen (Laboratório / Avaliação / Radar)."""
    col_header1, col_header2 = st.columns([4, 1])
    with col_header1:
        st.markdown(
            f"Sessão iniciada como: **{st.session_state['nome_utilizador']}** "
            f"({st.session_state['papel_utilizador'].upper()})"
        )
    with col_header2:
        if st.button("Terminar Sessão", use_container_width=True):
            st.session_state["autenticado"] = False
            st.session_state["nome_utilizador"] = ""
            st.session_state["papel_utilizador"] = ""
            st.session_state["modulo_ativo"] = "menu"
            st.experimental_rerun()

    st.divider()
    st.title("Plataforma See Future")
    st.markdown("Selecione o ambiente operacional ou estratégico pretendido.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        _render_card(
            "Laboratório",
            "Espaço analítico dedicado à gestão de concursos públicos, avaliação da concorrência e comportamento de clientes.",
        )
        if st.button("Entrar no Laboratório", type="primary", use_container_width=True):
            st.session_state["modulo_ativo"] = "laboratorio"
            st.experimental_rerun()

    with col2:
        _render_card(
            "Avaliação",
            "Módulo de inteligência preditiva. Simule cenários concorrenciais e avalie a rentabilidade antes de submeter propostas.",
        )
        if st.button("Entrar na Avaliação", type="primary", use_container_width=True):
            st.session_state["modulo_ativo"] = "avaliacao"
            st.experimental_rerun()

    with col3:
        _render_card(
            "Radar",
            "Módulo estratégico em desenvolvimento. Destinado à prospeção avançada e mapeamento preventivo de mercado.",
        )
        if st.button("Entrar no Radar", type="primary", use_container_width=True):
            st.info("O módulo Radar encontra-se em fase de desenvolvimento técnico e estará disponível brevemente.")


# --------- Page definitions (Streamlit Page objects) ----------
pg_dashboard = st.Page("pages/0_Dashboard.py", title="Dashboard", default=True)
pg_novo = st.Page("pages/1_Novo_Concurso.py", title="Novo Concurso")
pg_consultar = st.Page("pages/2_Consultar_Concursos.py", title="Consultar Concursos")
pg_concorrencia = st.Page("pages/3_Análise_Concorrência.py", title="Análise Concorrência")
pg_clientes = st.Page("pages/4_Análise_Clientes.py", title="Análise Clientes")
pg_estatisticas = st.Page("pages/5_Estatísticas_FUTURE.py", title="Estatísticas FUTURE")
pg_gestao_utilizadores = st.Page("pages/6_Gestão_Utilizadores.py", title="Gestão Utilizadores")

pg_posicionamento = st.Page("pages/7a_Posicionamento.py", title="Posicionamento", default=True)
pg_rentabilidade = st.Page("pages/7b_Rentabilidade.py", title="Rentabilidade")


# --------- Main routing ----------
def main() -> None:
    supabase = get_supabase_client()

    if not st.session_state.get("autenticado"):
        render_login(supabase)

    elif st.session_state.get("modulo_ativo") == "laboratorio":
        paginas_lab = [pg_dashboard, pg_novo, pg_consultar, pg_concorrencia, pg_clientes, pg_estatisticas]
        if str(st.session_state.get("papel_utilizador", "")).strip().lower() == ROLE_ADMIN:
            paginas_lab.append(pg_gestao_utilizadores)
        nav = st.navigation(paginas_lab)
        nav.run()

    elif st.session_state.get("modulo_ativo") == "avaliacao":
        paginas_aval = [pg_posicionamento, pg_rentabilidade]
        nav = st.navigation(paginas_aval)
        nav.run()

    else:
        render_module_selection()


if __name__ == "__main__":
    main()
