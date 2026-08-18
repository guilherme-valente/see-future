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

@st.cache_data(ttl=300)
def obter_ultima_atualizacao_real():
    resp = client.table("radar_leads").select("updated_at").order("updated_at", desc=True).limit(1).execute()
    if resp.data:
        return resp.data[0]["updated_at"]
    return None

ultima_atualizacao = obter_ultima_atualizacao_real()
if ultima_atualizacao:
    from datetime import datetime
    dt = datetime.fromisoformat(ultima_atualizacao.replace("Z", "+00:00"))
    st.caption(f"Última alteração real aos dados: {dt.strftime('%d/%m/%Y %H:%M')}")

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

def cor_por_score(score: int, minimo: int) -> tuple[str, str, str]:
    """Devolve (cor_fundo, cor_texto, label) consoante o score."""
    if score >= minimo * 2:
        return "#d4edda", "#155724", "Alta prioridade"
    elif score >= minimo * 1.25:
        return "#fff3cd", "#856404", "Prioridade média"
    else:
        return "#f8d7da", "#721c24", "Prioridade baixa"

def renderizar_cartao(lead: dict, score: int, detalhe: list[str], minimo: int, score_max: int):
    cor_fundo, cor_texto, label = cor_por_score(score, minimo)
    percentagem = min(int((score / score_max) * 100), 100) if score_max else 0

    valor_fmt = f"{lead['valor_base']:,.2f} €".replace(",", " ").replace(".", ",", 1) if lead.get("valor_base") else "—"
    prazo_fmt = lead.get("data_limite_propostas") or "—"
    link = lead.get("link_base")
    detalhe_texto = " · ".join(detalhe) if detalhe else "Sem correspondências"

    link_html = f'<a href="{link}" target="_blank" style="font-size:0.85rem;">Ver anúncio</a>' if link else ""

    st.markdown(f"""
    <div style="border:1px solid #e0e0e0; border-radius:10px; padding:16px; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px;">
            <div style="flex:1;">
                <div style="font-weight:600; font-size:1.05rem; margin-bottom:4px;">
                    {lead['objeto_concurso']}
                </div>
                <div style="color:#666; font-size:0.85rem; margin-bottom:8px;">
                    {lead['entidade_adjudicante']} · Ref. {lead['referencia_base']}
                </div>
                <div style="font-size:0.85rem; color:#444; margin-bottom:8px;">
                    Valor base: {valor_fmt} &nbsp;&nbsp; Prazo: {prazo_fmt}
                </div>
                <div style="font-size:0.8rem; color:#888; margin-bottom:6px;">
                    {detalhe_texto}
                </div>
                {link_html}
            </div>
            <div style="text-align:center; min-width:140px;">
                <div style="background:{cor_fundo}; color:{cor_texto}; border-radius:8px; padding:8px 12px; font-weight:600; font-size:0.85rem; margin-bottom:6px;">
                    {label}
                </div>
                <div style="font-size:1.3rem; font-weight:700; color:{cor_texto};">
                    {score} pts
                </div>
                <div style="background:#eee; border-radius:6px; height:8px; margin-top:6px; overflow:hidden;">
                    <div style="background:{cor_texto}; width:{percentagem}%; height:100%;"></div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

score_minimo = config.get("score_minimo") or 40

resultados = []
quase = []
for lead in leads:
    score, detalhe = calcular_score(lead, config)
    if score >= score_minimo:
        resultados.append((lead, score, detalhe))
    elif score > 0:
        quase.append((lead, score, detalhe))

resultados.sort(key=lambda r: r[1], reverse=True)
quase.sort(key=lambda r: r[1], reverse=True)

score_max_geral = max([r[1] for r in resultados] + [q[1] for q in quase], default=1)

st.write(f"**{len(resultados)}** concursos relevantes para **{unidade_selecionada}** (de {len(leads)} abertos)")

for lead, score, detalhe in resultados:
    renderizar_cartao(lead, score, detalhe, score_minimo, score_max_geral)

st.divider()
with st.expander(f"Correspondência parcial — abaixo do score mínimo ({len(quase)} concursos)"):
    for lead, score, detalhe in quase[:30]:
        renderizar_cartao(lead, score, detalhe, score_minimo, score_max_geral)
