import streamlit as st
from supabase import create_client

if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

st.set_page_config(page_title="Procurador | See Future", layout="wide")
st.title("Procurador de Concursos")

@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

client = get_client()

@st.cache_data(ttl=300)
def carregar_configs():
    resp = client.table("radar_config").select("*").eq("ativo", True).execute()
    return resp.data

configs = carregar_configs()

if not configs:
    st.warning("Não existem configurações de radar ativas. Cria uma em radar_config para começar.")
    st.stop()

configs_ordenadas = sorted(configs, key=lambda c: c.get("prioridade") or 999)
nomes_config = {c["unidade_negocio"]: c for c in configs_ordenadas}
unidade_selecionada = st.selectbox("Unidade de negócio", list(nomes_config.keys()))
config = nomes_config[unidade_selecionada]

if config.get("descricao"):
    st.caption(config["descricao"])

@st.cache_data(ttl=300)
def carregar_leads_abertos():
    resp = client.table("radar_leads").select("*").eq("estado_concurso_origem", "aberto").execute()
    return resp.data

leads = carregar_leads_abertos()

def normalizar_cpv(codigo: str) -> str:
    """Remove o dígito de controlo (ex: '71318100-1' -> '71318100')."""
    return codigo.split("-")[0].strip()

def calcular_score(lead: dict, cfg: dict) -> tuple[int, list[str]]:
    score = 0
    detalhe = []

    cpv_config = {normalizar_cpv(c) for c in (cfg.get("cpv_codes") or [])}
    cpv_lead = {normalizar_cpv(c) for c in (lead.get("cpv") or [])}
    if cpv_config and cpv_lead & cpv_config:
        score += 40
        detalhe.append("CPV coincide")

    texto = (lead.get("objeto_concurso") or "").lower()
    palavras = cfg.get("palavras_chave") or []
    correspondencias = [p for p in palavras if p.lower() in texto]
    if correspondencias:
        score += 10 * len(correspondencias)
        detalhe.append(f"Palavras-chave: {', '.join(correspondencias)}")

    valor = lead.get("valor_base")
    valor_min = cfg.get("valor_min")
    valor_max = cfg.get("valor_max")
    if valor is not None:
        if valor_min is not None and valor < valor_min:
            return 0, []
        if valor_max is not None and valor > valor_max:
            return 0, []

    entidades_ignoradas = set(cfg.get("entidades_ignoradas") or [])
    if lead.get("entidade_adjudicante") in entidades_ignoradas:
        return 0, []

    return score, detalhe

resultados = []
for lead in leads:
    score, detalhe = calcular_score(lead, config)
    if score >= (config.get("score_minimo") or 0):
        resultados.append({**lead, "score_calculado": score, "detalhe_score": "; ".join(detalhe)})

resultados.sort(key=lambda r: r["score_calculado"], reverse=True)

st.write(f"**{len(resultados)}** concursos relevantes para **{unidade_selecionada}** (de {len(leads)} abertos)")

for lead in resultados:
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{lead['objeto_concurso']}**")
            st.caption(f"{lead['entidade_adjudicante']} · Ref. {lead['referencia_base']}")
            if lead.get("valor_base"):
                st.caption(f"Valor base: {lead['valor_base']:,.2f} €")
            if lead.get("data_limite_propostas"):
                st.caption(f"Prazo: {lead['data_limite_propostas']}")
            if lead.get("link_base"):
                st.markdown(f"[Ver anúncio]({lead['link_base']})")
        with col2:
            st.metric("Score", lead["score_calculado"])
            if lead.get("detalhe_score"):
                st.caption(lead["detalhe_score"])
