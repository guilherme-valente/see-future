import streamlit as st
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from supabase import create_client, Client

# =============================================================================
# GUARDA DE ACESSO
# =============================================================================
if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

# =============================================================================
# ESTILO / TEMA
# =============================================================================
st.markdown(
    """
    <style>
    [data-testid="stMetricLabel"] {
        font-size: 13px !important;
        white-space: normal !important;
        word-break: break-word !important;
        color: #475569 !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 26px !important;
        color: #0f172a !important;
    }
    .fs-hero {
        background: linear-gradient(135deg, #1b365d 0%, #274972 100%);
        border-radius: 16px;
        padding: 28px 32px;
        color: white;
        margin-bottom: 22px;
    }
    .fs-hero h1 { margin: 0; font-size: 26px; }
    .fs-hero p { margin: 6px 0 0 0; opacity: 0.85; font-size: 14px; }

    .fs-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 14px;
    }
    .fs-card h4 { margin-top: 0; color: #1b365d; }

    .fs-index-wrap { text-align: center; padding: 10px 0 0 0; }
    .fs-index-value { font-size: 52px; font-weight: 800; line-height: 1; }
    .fs-index-label { font-size: 13px; color: #64748b; margin-top: 6px; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase; }
    .fs-index-badge {
        display: inline-block; margin-top: 10px; padding: 5px 14px;
        border-radius: 999px; font-size: 13px; font-weight: 700;
    }

    .fs-badge-excelente { background: #dcfce7; color: #166534; }
    .fs-badge-competitivo { background: #dbeafe; color: #1e40af; }
    .fs-badge-equilibrado { background: #fef3c7; color: #92400e; }
    .fs-badge-fragil { background: #fee2e2; color: #991b1b; }
    .fs-badge-critico { background: #fecaca; color: #7f1d1d; }

    .n-badge {
        display: inline-block; background-color: #eef2ff; color: #4338ca;
        font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; margin-left: 6px;
    }
    .fs-insight {
        border-left: 4px solid #1b365d;
        background: #f8fafc;
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 8px;
        font-size: 14px;
        color: #1e293b;
    }
    .fs-insight-alerta { border-left-color: #dc2626; background: #fef2f2; }
    .fs-insight-oportunidade { border-left-color: #16a34a; background: #f0fdf4; }
    .fs-factor-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px;
    }
    .fs-factor-row:last-child { border-bottom: none; }
    </style>
    """,
    unsafe_allow_html=True
)

# =============================================================================
# CONSTANTES
# =============================================================================
LIMIAR_AMOSTRA_MINIMA = 3
PESO_ESCALAO, PESO_MERCADO, PESO_ZONA, PESO_CLIENTE = 0.2, 0.2, 0.2, 0.4


# =============================================================================
# UTILITÁRIOS DE FORMATAÇÃO
# =============================================================================
def formatar_moeda(valor):
    if pd.isna(valor):
        return "0,00 €"
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentagem(valor, casas=1):
    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{valor * 100:.{casas}f}%"


def definir_escalao(valor):
    if valor < 50000:
        return "Micro (Até 50k€)"
    elif valor < 150000:
        return "Médio (50k€ a 150k€)"
    elif valor < 500000:
        return "Grande (150k€ a 500k€)"
    else:
        return "Especial (Superior a 500k€)"


def badge_n(n):
    return f"<span class='n-badge'>n = {n}</span>"


def classificar_indice(indice):
    """Devolve (rótulo, classe_css) para o Índice Estratégico (0-100)."""
    if indice >= 75:
        return "Posicionamento Excelente", "fs-badge-excelente"
    elif indice >= 60:
        return "Posicionamento Competitivo", "fs-badge-competitivo"
    elif indice >= 45:
        return "Posicionamento Equilibrado", "fs-badge-equilibrado"
    elif indice >= 30:
        return "Posicionamento Frágil", "fs-badge-fragil"
    else:
        return "Posicionamento Crítico", "fs-badge-critico"


# =============================================================================
# LIGAÇÃO À BASE DE DADOS
# =============================================================================
@st.cache_resource
def iniciar_ligacao():
    url = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    return create_client(url, chave)


@st.cache_data(ttl=300)
def carregar_dados():
    """Vai buscar concursos e propostas (com empresas associadas) ao Supabase."""
    supabase = iniciar_ligacao()
    resp_concursos = supabase.table("concursos").select("*, clientes(nome_cliente)").execute()
    resp_propostas = supabase.table("propostas").select(
        "*, proposta_empresas(papel, empresas(id, nome_empresa))"
    ).execute()
    df_concursos = pd.DataFrame(resp_concursos.data) if resp_concursos.data else pd.DataFrame()
    df_propostas_raw = pd.DataFrame(resp_propostas.data) if resp_propostas.data else pd.DataFrame()
    return df_concursos, df_propostas_raw


# =============================================================================
# PROCESSAMENTO DE DADOS
# =============================================================================
def processar_concursos(df_concursos):
    if df_concursos.empty:
        return df_concursos, None

    df = df_concursos.copy()
    df['nome_cliente'] = df['clientes'].apply(
        lambda x: x.get('nome_cliente', 'Desconhecido') if isinstance(x, dict) else 'Desconhecido'
    )
    df['Regiao'] = df['distrito'].apply(lambda x: str(x) if pd.notna(x) else 'Não Definido')
    df['escalao'] = df['preco_base'].apply(definir_escalao)

    col_data_candidatos = ['data_concurso', 'data_publicacao', 'data_abertura', 'created_at', 'data']
    col_data_concurso = next((c for c in col_data_candidatos if c in df.columns), None)
    df['_data_norm'] = pd.to_datetime(df[col_data_concurso], errors='coerce') if col_data_concurso else pd.NaT

    if 'data_adjudicacao' in df.columns:
        df['_data_adjudicacao_norm'] = pd.to_datetime(df['data_adjudicacao'], errors='coerce')
    else:
        df['_data_adjudicacao_norm'] = pd.NaT

    return df, col_data_concurso


def _extrair_lider(lista_pe):
    if not isinstance(lista_pe, list) or len(lista_pe) == 0:
        return "Desconhecida"
    for item in lista_pe:
        if item.get('papel') == 'lider':
            emp = item.get('empresas')
            return emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
    emp = lista_pe[0].get('empresas')
    return emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'


def _extrair_nomes_todas(lista_pe):
    if not isinstance(lista_pe, list):
        return []
    return [
        item.get('empresas').get('nome_empresa')
        for item in lista_pe
        if isinstance(item.get('empresas'), dict) and item.get('empresas').get('nome_empresa')
    ]


def processar_propostas(df_propostas_raw):
    """Devolve (df_propostas ao nível da proposta, df_empresa_exploded ao nível da empresa)."""
    if df_propostas_raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df_propostas_raw.copy()
    df['desclassificado'] = df.get('desclassificado', False)
    df['desclassificado'] = df['desclassificado'].fillna(False).astype(bool)
    df['em_consorcio'] = df.get('em_consorcio', False)
    df['em_consorcio'] = df['em_consorcio'].fillna(False).astype(bool)

    df['nome_lider'] = df['proposta_empresas'].apply(_extrair_lider)
    df['nomes_todas_empresas'] = df['proposta_empresas'].apply(_extrair_nomes_todas)
    df['n_empresas_na_proposta'] = df['nomes_todas_empresas'].apply(len)
    df['label_concorrente'] = df['nomes_todas_empresas'].apply(lambda lst: " + ".join(lst) if lst else "Desconhecida")

    linhas = []
    for _, prop in df.iterrows():
        lista_pe = prop.get('proposta_empresas')
        if not isinstance(lista_pe, list) or len(lista_pe) == 0:
            continue
        for item in lista_pe:
            emp = item.get('empresas')
            nome_emp = emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
            linhas.append({
                'proposta_id': prop['id'],
                'concurso_id': prop['concurso_id'],
                'nome_empresa': nome_emp,
                'papel': item.get('papel', 'individual'),
                'em_consorcio': prop['em_consorcio'],
                'valor_proposto': prop.get('valor_proposto'),
                'desclassificado': prop.get('desclassificado'),
                'vencedor': prop.get('vencedor'),
                'notas_criterios': prop.get('notas_criterios'),
            })
    df_empresa_exploded = pd.DataFrame(linhas)
    return df, df_empresa_exploded


def _soma_notas(notas_json):
    if isinstance(notas_json, dict):
        soma = notas_json.get('CVs', 0) + notas_json.get('Metodologia', 0) + notas_json.get('Afetacao', 0)
        return soma if soma > 0 else None
    return None


# =============================================================================
# CONTEXTO ESTATÍSTICO (histórico filtrado por cliente / mercado / zona)
# =============================================================================
@dataclass
class ContextoHistorico:
    n_concursos_cliente: int = 0
    n_concursos_mercado_zona: int = 0
    n_concursos_total: int = 0
    n_propostas_validas: int = 0
    alpha_fiabilidade: float = 0.1

    desconto_medio: float = 0.08
    desconto_mediano: float = 0.08
    desconto_desvio: float = 0.0

    nota_tecnica_future: float = 85.0
    nota_tecnica_future_real: bool = False
    n_propostas_future_com_nota: int = 0

    nota_tecnica_conc: float = 82.0
    nota_tecnica_conc_real: bool = False
    n_propostas_conc_com_nota: int = 0

    taxa_desclassificacao: float = None
    taxa_sucesso_future: float = None
    n_concursos_future_participou: int = 0
    n_concursos_future_ganhou: int = 0

    media_concorrentes: float = None
    tempo_medio_adjudicacao: float = None
    n_concursos_com_adjudicacao: int = 0

    n_propostas_consorcio: int = 0
    n_propostas_contexto: int = 0
    taxa_consorcio: float = None

    evolucao_desconto: pd.DataFrame = field(default_factory=pd.DataFrame)
    tabela_concorrentes: list = field(default_factory=list)
    tabela_consorcios: list = field(default_factory=list)


def calcular_contexto(df_concursos, df_propostas, df_empresa_exploded, cliente_sel, mercado_sel,
                       distrito_sel, escalao_sim, preco_base_input):
    ctx = ContextoHistorico()

    filtro_cliente = df_concursos['nome_cliente'] == cliente_sel
    filtro_mercado_zona = (df_concursos['mercado'] == mercado_sel) & (df_concursos['distrito'] == distrito_sel)
    filtro_historico = df_concursos[filtro_cliente | filtro_mercado_zona]

    ctx.n_concursos_cliente = int(filtro_cliente.sum())
    ctx.n_concursos_mercado_zona = int(filtro_mercado_zona.sum())
    ctx.n_concursos_total = len(filtro_historico)

    if filtro_historico.empty:
        return ctx

    ids_concursos = filtro_historico['id'].tolist()

    # Nível proposta
    df_prop_ctx = df_propostas[df_propostas['concurso_id'].isin(ids_concursos)].copy()
    df_prop_validas = df_prop_ctx[df_prop_ctx['desclassificado'] == False].copy()
    ctx.n_propostas_validas = len(df_prop_validas)
    ctx.n_propostas_contexto = len(df_prop_ctx)
    ctx.n_propostas_consorcio = int(df_prop_ctx['em_consorcio'].sum())
    if len(df_prop_ctx) > 0:
        ctx.taxa_consorcio = ctx.n_propostas_consorcio / len(df_prop_ctx)
        ctx.taxa_desclassificacao = df_prop_ctx['desclassificado'].mean()

    ctx.alpha_fiabilidade = min(
        1.0, 0.05 + (ctx.n_concursos_total * 0.10) + (min(ctx.n_propostas_validas, 20) * 0.01)
    )

    # Nível empresa (explodido)
    df_emp_ctx = df_empresa_exploded[df_empresa_exploded['concurso_id'].isin(ids_concursos)].copy()
    df_emp_validas = df_emp_ctx[df_emp_ctx['desclassificado'] == False].copy()
    if not df_emp_validas.empty:
        ctx.media_concorrentes = df_emp_validas.groupby('concurso_id')['nome_empresa'].nunique().mean()

    # Prazo até adjudicação
    df_prazo = filtro_historico.dropna(subset=['_data_norm', '_data_adjudicacao_norm']).copy()
    if not df_prazo.empty:
        df_prazo['_dias'] = (df_prazo['_data_adjudicacao_norm'] - df_prazo['_data_norm']).dt.days
        df_prazo = df_prazo[df_prazo['_dias'] >= 0]
        if not df_prazo.empty:
            ctx.tempo_medio_adjudicacao = df_prazo['_dias'].mean()
            ctx.n_concursos_com_adjudicacao = len(df_prazo)

    if df_prop_validas.empty:
        return ctx

    df_cruzado = pd.merge(
        df_prop_validas,
        filtro_historico[['id', 'preco_base', 'escalao', 'mercado', 'distrito', 'nome_cliente', '_data_norm']],
        left_on='concurso_id', right_on='id'
    )
    df_cruzado['desconto'] = (df_cruzado['preco_base'] - df_cruzado['valor_proposto']) / df_cruzado['preco_base']

    # Remoção de outliers (IQR)
    q1, q3 = df_cruzado['desconto'].quantile([0.25, 0.75])
    iqr = q3 - q1
    df_limpo = df_cruzado[(df_cruzado['desconto'] >= q1 - 1.5 * iqr) & (df_cruzado['desconto'] <= q3 + 1.5 * iqr)]

    if not df_limpo.empty:
        if pd.notna(df_limpo['desconto'].mean()):
            ctx.desconto_medio = float(df_limpo['desconto'].mean())
        if pd.notna(df_limpo['desconto'].median()):
            ctx.desconto_mediano = float(df_limpo['desconto'].median())
        if pd.notna(df_limpo['desconto'].std()):
            ctx.desconto_desvio = float(df_limpo['desconto'].std())

    # Evolução temporal
    if df_cruzado['_data_norm'].notna().sum() >= 2:
        df_temp = df_cruzado.dropna(subset=['_data_norm']).sort_values('_data_norm')
        df_temp['ano_mes'] = df_temp['_data_norm'].dt.to_period('M').astype(str)
        ctx.evolucao_desconto = df_temp.groupby('ano_mes')['desconto'].mean().reset_index()
        ctx.evolucao_desconto.columns = ['Período', 'Desconto Médio']

    # Nota técnica FUTURE
    df_future = df_cruzado[df_cruzado['nome_lider'].str.upper() == 'FUTURE']
    notas_future = [n for n in df_future.get('notas_criterios', pd.Series(dtype=object)).apply(_soma_notas) if n]
    ctx.n_propostas_future_com_nota = len(notas_future)
    if notas_future:
        ctx.nota_tecnica_future = float(np.mean(notas_future))
        ctx.nota_tecnica_future_real = True

    if not df_future.empty and 'vencedor' in df_future.columns:
        ctx.n_concursos_future_participou = df_future['concurso_id'].nunique()
        ctx.n_concursos_future_ganhou = int(df_future[df_future['vencedor'] == True]['concurso_id'].nunique())
        if ctx.n_concursos_future_participou > 0:
            ctx.taxa_sucesso_future = ctx.n_concursos_future_ganhou / ctx.n_concursos_future_participou

    # Nota técnica da concorrência
    df_conc = df_cruzado[df_cruzado['nome_lider'].str.upper() != 'FUTURE']
    notas_conc = [n for n in df_conc.get('notas_criterios', pd.Series(dtype=object)).apply(_soma_notas) if n]
    ctx.n_propostas_conc_com_nota = len(notas_conc)
    if notas_conc:
        ctx.nota_tecnica_conc = float(np.mean(notas_conc))
        ctx.nota_tecnica_conc_real = True

    # Tabela de concorrentes (nível empresa)
    df_emp_cruzado = pd.merge(
        df_emp_validas,
        filtro_historico[['id', 'preco_base', 'escalao', 'mercado', 'distrito', 'nome_cliente']],
        left_on='concurso_id', right_on='id'
    )
    df_emp_cruzado['desconto'] = (df_emp_cruzado['preco_base'] - df_emp_cruzado['valor_proposto']) / df_emp_cruzado['preco_base']
    adversarias = df_emp_cruzado[df_emp_cruzado['nome_empresa'].str.upper() != 'FUTURE']

    if not adversarias.empty:
        total_concursos_ctx = df_emp_cruzado['concurso_id'].nunique()
        linhas_tabela = []
        for empresa, df_emp in adversarias.groupby('nome_empresa'):
            n_props = df_emp['proposta_id'].nunique()
            n_props_consorcio = int(df_emp['em_consorcio'].sum())
            match_cliente = df_emp['nome_cliente'].eq(cliente_sel).sum()
            match_escalao = df_emp['escalao'].eq(escalao_sim).sum()
            match_mercado = df_emp['mercado'].eq(mercado_sel).sum()
            match_zona = df_emp['distrito'].eq(distrito_sel).sum()

            score_presenca = (
                match_cliente * PESO_CLIENTE + match_escalao * PESO_ESCALAO +
                match_mercado * PESO_MERCADO + match_zona * PESO_ZONA
            )
            prob_participacao = min(95.0, 15.0 + (score_presenca / max(1, total_concursos_ctx)) * 100)
            desc_medio_emp = df_emp['desconto'].mean() if not df_emp['desconto'].empty else ctx.desconto_medio
            valor_numerario = preco_base_input * desc_medio_emp

            linhas_tabela.append({
                "Concorrente": empresa,
                "N": n_props,
                "Em Consórcio": f"{n_props_consorcio}/{n_props}",
                "Probabilidade Participação": f"{prob_participacao:.1f}%",
                "Desconto Estimado Face ao Base": f"{desc_medio_emp * 100:.1f}%",
                "Diferença Estimada (Numerário)": formatar_moeda(valor_numerario),
                "Ordem_Prob": prob_participacao
            })
        linhas_tabela = sorted(linhas_tabela, key=lambda x: x["Ordem_Prob"], reverse=True)
        for item in linhas_tabela:
            del item["Ordem_Prob"]
        ctx.tabela_concorrentes = linhas_tabela

        df_so_consorcios = df_prop_ctx[df_prop_ctx['em_consorcio'] == True]
        if not df_so_consorcios.empty:
            contagem = df_so_consorcios['label_concorrente'].value_counts()
            ctx.tabela_consorcios = [
                {"Consórcio": label, "Nº de Concursos Conjuntos": int(n)}
                for label, n in contagem.items() if n >= 2
            ]

    return ctx


# =============================================================================
# MOTOR DE ÍNDICE ESTRATÉGICO
# =============================================================================
def calcular_indice_estrategico(preco_future, preco_medio_conc, nota_tecnica_future, nota_tecnica_conc,
                                 w_preco, w_tecnico, alpha_fiabilidade, valor_limiar_critico):
    """
    Calcula o Índice Estratégico (0-100) para um dado preço, decompondo-o nos
    fatores de preço, técnico e fiabilidade da amostra. Devolve um dicionário
    com o índice final e a contribuição de cada fator (para explicação).
    """
    if preco_future < valor_limiar_critico:
        return {
            "indice": 0.0,
            "excluido": True,
            "pontos_preco_fut": 0.0, "pontos_preco_conc": w_preco,
            "pontos_tec_fut": 0.0, "pontos_tec_conc": w_tecnico,
            "score_diferencial": None,
        }

    pontos_preco_fut = (preco_medio_conc / preco_future) * w_preco if preco_future > 0 else 0
    pontos_preco_conc = w_preco
    pontos_tec_fut = (nota_tecnica_future / 100) * w_tecnico
    pontos_tec_conc = (nota_tecnica_conc / 100) * w_tecnico

    score_diferencial = (pontos_preco_fut + pontos_tec_fut) - (pontos_preco_conc + pontos_tec_conc)
    prob_bruta = 1 / (1 + np.exp(-0.2 * score_diferencial))
    indice_ajustado = (prob_bruta * alpha_fiabilidade) + (0.5 * (1 - alpha_fiabilidade))

    return {
        "indice": float(indice_ajustado * 100),
        "excluido": False,
        "pontos_preco_fut": pontos_preco_fut, "pontos_preco_conc": pontos_preco_conc,
        "pontos_tec_fut": pontos_tec_fut, "pontos_tec_conc": pontos_tec_conc,
        "score_diferencial": score_diferencial,
    }


def gerar_curva_sensibilidade(preco_min, preco_max, preco_medio_conc, nota_tecnica_future, nota_tecnica_conc,
                               w_preco, w_tecnico, alpha_fiabilidade, valor_limiar_critico, n_pontos=60):
    """Varre uma grelha de preços e devolve o Índice Estratégico e o Valor Esperado (preço x índice) em cada ponto."""
    precos = np.linspace(preco_min, preco_max, n_pontos)
    linhas = []
    for p in precos:
        r = calcular_indice_estrategico(
            p, preco_medio_conc, nota_tecnica_future, nota_tecnica_conc,
            w_preco, w_tecnico, alpha_fiabilidade, valor_limiar_critico
        )
        indice = r["indice"]
        valor_esperado = p * (indice / 100)
        linhas.append({"Preço": p, "Índice Estratégico": indice, "Valor Esperado": valor_esperado})
    return pd.DataFrame(linhas)


def calcular_preco_otimo(df_curva):
    """
    Preço ótimo = o que maximiza o Valor Esperado (preço x índice estratégico),
    isto é, o melhor compromisso entre competitividade e receita.
    """
    if df_curva.empty:
        return None
    linha_otima = df_curva.loc[df_curva["Valor Esperado"].idxmax()]
    return {
        "preco": float(linha_otima["Preço"]),
        "indice": float(linha_otima["Índice Estratégico"]),
        "valor_esperado": float(linha_otima["Valor Esperado"]),
    }


# =============================================================================
# INSIGHTS AUTOMÁTICOS
# =============================================================================
def gerar_insights(ctx: ContextoHistorico, preco_future, preco_otimo_info, valor_limiar_critico,
                    preco_base_input, indice_atual):
    insights = []

    if ctx.n_concursos_total < LIMIAR_AMOSTRA_MINIMA:
        insights.append(("alerta", f"A amostra histórica é pequena ({ctx.n_concursos_total} concurso(s)). "
                                    "Trata os indicadores como indicativos, não conclusivos."))

    if preco_future < valor_limiar_critico:
        insights.append(("alerta", f"O preço simulado está abaixo do limiar de anormalidade "
                                    f"({formatar_moeda(valor_limiar_critico)}). Risco elevado de desclassificação direta."))

    if preco_otimo_info and abs(preco_otimo_info["preco"] - preco_future) / max(preco_future, 1) > 0.03:
        direcao = "reduzir" if preco_otimo_info["preco"] < preco_future else "aumentar"
        insights.append((
            "oportunidade",
            f"O preço que maximiza o valor esperado é {formatar_moeda(preco_otimo_info['preco'])} "
            f"(Índice {preco_otimo_info['indice']:.0f}/100). Considera {direcao} a proposta atual "
            f"({formatar_moeda(preco_future)}) para se aproximar deste ponto."
        ))

    if ctx.taxa_consorcio is not None and ctx.taxa_consorcio > 0.4:
        insights.append(("info", f"Neste contexto, {formatar_percentagem(ctx.taxa_consorcio, 0)} das propostas "
                                  "são submetidas em agrupamento — vale a pena avaliar parcerias estratégicas."))

    if ctx.tabela_consorcios:
        top_parceria = max(ctx.tabela_consorcios, key=lambda x: x["Nº de Concursos Conjuntos"])
        insights.append(("info", f"A parceria mais recorrente identificada é '{top_parceria['Consórcio']}', "
                                  f"com {top_parceria['Nº de Concursos Conjuntos']} concursos conjuntos."))

    if ctx.taxa_desclassificacao is not None and ctx.taxa_desclassificacao > 0.2:
        insights.append(("alerta", f"A taxa histórica de desclassificação neste contexto é elevada "
                                    f"({formatar_percentagem(ctx.taxa_desclassificacao, 0)}). "
                                    "Revê com atenção os requisitos formais das propostas."))

    if not ctx.nota_tecnica_future_real:
        insights.append(("info", "A nota técnica da FUTURE usada no cálculo é uma estimativa por omissão — "
                                  "ainda não existem propostas reais com notas registadas neste contexto."))

    if ctx.taxa_sucesso_future is not None:
        if ctx.taxa_sucesso_future >= 0.5:
            insights.append(("oportunidade", f"A FUTURE tem uma taxa de sucesso histórica de "
                                              f"{formatar_percentagem(ctx.taxa_sucesso_future, 0)} neste contexto "
                                              f"({ctx.n_concursos_future_ganhou}/{ctx.n_concursos_future_participou})."))
        else:
            insights.append(("alerta", f"A taxa de sucesso histórica da FUTURE neste contexto é de apenas "
                                        f"{formatar_percentagem(ctx.taxa_sucesso_future, 0)} "
                                        f"({ctx.n_concursos_future_ganhou}/{ctx.n_concursos_future_participou})."))

    if ctx.tabela_concorrentes:
        top_conc = ctx.tabela_concorrentes[0]
        insights.append(("info", f"'{top_conc['Concorrente']}' é o concorrente com maior probabilidade "
                                  f"de participação estimada ({top_conc['Probabilidade Participação']})."))

    if not insights:
        insights.append(("info", "Sem padrões adicionais relevantes identificados no histórico filtrado."))

    return insights


# =============================================================================
# COMPONENTES DE INTERFACE
# =============================================================================
def render_hero():
    st.markdown(
        """
        <div class="fs-hero">
            <h1>Simulador de Cenário Concorrencial e Preço Alvo</h1>
            <p>Estudo prospectivo de viabilidade comercial e análise de concorrência baseada em histórico.</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_indicadores_calibracao(ctx: ContextoHistorico, preco_base_input):
    st.markdown("#### Indicadores Analíticos de Calibração")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "Índice de Fiabilidade Analítica (alpha)",
            f"{ctx.alpha_fiabilidade * 100:.0f}%",
            help=f"Robustez estatística do cenário. Baseado em {ctx.n_concursos_total} concurso(s) histórico(s) "
                 f"({ctx.n_concursos_cliente} do mesmo cliente, {ctx.n_concursos_mercado_zona} do mesmo mercado/zona) "
                 f"e {ctx.n_propostas_validas} proposta(s) válida(s)."
        )
    with c2:
        st.metric(
            "Preço Médio Estimado da Concorrência",
            formatar_moeda(preco_base_input * (1 - ctx.desconto_medio)),
            help=f"Baseado na mediana de desconto histórico ({ctx.desconto_mediano * 100:.1f}%) e média sem outliers "
                 f"({ctx.desconto_medio * 100:.1f}% +/- {ctx.desconto_desvio * 100:.1f} p.p.), n = {ctx.n_propostas_validas} propostas."
        )
    with c3:
        nota_help = (
            f"Baseado em {ctx.n_propostas_future_com_nota} proposta(s) real(is) da FUTURE com notas registadas."
            if ctx.nota_tecnica_future_real else
            "Valor por omissão (85.0) — não existem notas técnicas reais da FUTURE no histórico filtrado."
        )
        st.metric(
            "Nota Técnica Esperada (FUTURE)" + ("" if ctx.nota_tecnica_future_real else " (estimado)"),
            f"{ctx.nota_tecnica_future:.1f} Pts",
            help=nota_help
        )
    with c4:
        if ctx.taxa_sucesso_future is not None:
            st.metric(
                "Taxa de Sucesso Histórica FUTURE",
                f"{ctx.taxa_sucesso_future * 100:.0f}%",
                help=f"{ctx.n_concursos_future_ganhou} ganhos em {ctx.n_concursos_future_participou} concurso(s) participado(s)."
            )
        else:
            st.metric("Taxa de Sucesso Histórica FUTURE", "N/D",
                      help="Não existe coluna 'vencedor', ou não há dados suficientes.")


def render_indicadores_contexto(ctx: ContextoHistorico):
    st.markdown("#### Indicadores de Contexto Adicional")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Nº Médio de Concorrentes",
                  f"{ctx.media_concorrentes:.1f}" if ctx.media_concorrentes is not None else "N/D",
                  help="Média de empresas distintas (excl. desclassificados) por concurso. Membros de consórcio contam individualmente.")
    with c2:
        st.metric("Taxa de Desclassificação",
                  formatar_percentagem(ctx.taxa_desclassificacao) if ctx.taxa_desclassificacao is not None else "N/D",
                  help="Percentagem de propostas neste contexto que foram desclassificadas.")
    with c3:
        nota_conc_help = (
            f"Baseado em {ctx.n_propostas_conc_com_nota} proposta(s) real(is) de concorrentes com notas registadas."
            if ctx.nota_tecnica_conc_real else
            "Valor por omissão (82.0) — não existem notas técnicas reais de concorrentes no histórico filtrado."
        )
        st.metric("Nota Técnica Média da Concorrência" + ("" if ctx.nota_tecnica_conc_real else " (estimado)"),
                  f"{ctx.nota_tecnica_conc:.1f} Pts", help=nota_conc_help)
    with c4:
        st.metric("Tempo Médio até Adjudicação",
                  f"{ctx.tempo_medio_adjudicacao:.0f} dias" if ctx.tempo_medio_adjudicacao is not None else "N/D",
                  help=f"Baseado em {ctx.n_concursos_com_adjudicacao} concurso(s) com ambas as datas preenchidas."
                  if ctx.tempo_medio_adjudicacao is not None else
                  "Não há concursos com data_concurso e data_adjudicacao preenchidas em simultâneo.")
    with c5:
        st.metric("Taxa de Propostas em Consórcio",
                  f"{ctx.taxa_consorcio * 100:.0f}%" if ctx.taxa_consorcio is not None else "N/D",
                  help=f"{ctx.n_propostas_consorcio} de {ctx.n_propostas_contexto} proposta(s) submetidas em agrupamento."
                  if ctx.taxa_consorcio is not None else None)


def render_tabelas_concorrencia(ctx: ContextoHistorico):
    st.markdown("#### Previsão de Participação e Comportamento da Concorrência")
    st.markdown(
        f"Índice de fiabilidade específico destas métricas concorrenciais: **{int(ctx.alpha_fiabilidade * 100)} / 100**"
        f"&nbsp;&nbsp;{badge_n(ctx.n_concursos_total)}",
        unsafe_allow_html=True
    )
    st.caption("A coluna 'Em Consórcio' mostra quantas das propostas desta empresa foram submetidas em agrupamento, sobre o total.")

    if ctx.tabela_concorrentes:
        df_mostrar = pd.DataFrame(ctx.tabela_concorrentes).rename(columns={"N": "Nº Propostas Observadas"})
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    else:
        st.info("Não existem dados históricos suficientes para projetar concorrentes específicos.")

    if ctx.tabela_consorcios:
        st.markdown("##### Parcerias Recorrentes Identificadas")
        st.caption("Combinações de empresas que já concorreram juntas em mais do que um concurso, neste contexto.")
        df_consorcios = pd.DataFrame(ctx.tabela_consorcios).sort_values("Nº de Concursos Conjuntos", ascending=False)
        st.dataframe(df_consorcios, use_container_width=True, hide_index=True)


def render_indice_estrategico(resultado, preco_future, valor_limiar_critico):
    with st.container(border=True):
        st.markdown("##### Índice Estratégico")
        if resultado["excluido"]:
            st.markdown(
                """
                <div class="fs-index-wrap">
                    <div class="fs-index-value" style="color:#dc2626;">0</div>
                    <div class="fs-index-label">de 100 pontos</div>
                    <span class="fs-index-badge fs-badge-critico">Proposta Excluída</span>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.error("Proposta inviabilizada: o valor está abaixo do limiar mínimo exigido (risco de "
                     "desclassificação por preço anormalmente baixo).")
        else:
            indice = resultado["indice"]
            rotulo, classe = classificar_indice(indice)
            cor = "#16a34a" if indice >= 60 else ("#d97706" if indice >= 45 else "#dc2626")
            st.markdown(
                f"""
                <div class="fs-index-wrap">
                    <div class="fs-index-value" style="color:{cor};">{indice:.0f}</div>
                    <div class="fs-index-label">de 100 pontos</div>
                    <span class="fs-index-badge {classe}">{rotulo}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.progress(min(1.0, max(0.0, indice / 100)))


def render_explicacao_fatores(resultado, ctx: ContextoHistorico, w_preco, w_tecnico, preco_future, preco_medio_conc):
    with st.expander("Ver decomposição do Índice Estratégico por fator", expanded=False):
        if resultado["excluido"]:
            st.write("Sem decomposição disponível — a proposta foi excluída por preço anormalmente baixo.")
            return

        st.markdown(
            f"""
            <div class="fs-factor-row"><span>Peso atribuído ao Preço</span><strong>{w_preco}%</strong></div>
            <div class="fs-factor-row"><span>Peso atribuído à Qualidade Técnica</span><strong>{w_tecnico}%</strong></div>
            <div class="fs-factor-row"><span>Pontos de Preço (FUTURE)</span><strong>{resultado['pontos_preco_fut']:.1f}</strong></div>
            <div class="fs-factor-row"><span>Pontos de Preço (Concorrência de referência)</span><strong>{resultado['pontos_preco_conc']:.1f}</strong></div>
            <div class="fs-factor-row"><span>Pontos Técnicos (FUTURE)</span><strong>{resultado['pontos_tec_fut']:.1f}</strong></div>
            <div class="fs-factor-row"><span>Pontos Técnicos (Concorrência de referência)</span><strong>{resultado['pontos_tec_conc']:.1f}</strong></div>
            <div class="fs-factor-row"><span>Score Diferencial (FUTURE vs. referência)</span><strong>{resultado['score_diferencial']:.2f}</strong></div>
            <div class="fs-factor-row"><span>Índice de Fiabilidade Analítica aplicado</span><strong>{ctx.alpha_fiabilidade * 100:.0f}%</strong></div>
            """,
            unsafe_allow_html=True
        )
        st.caption(
            f"O preço simulado ({formatar_moeda(preco_future)}) é comparado ao preço médio estimado da "
            f"concorrência ({formatar_moeda(preco_medio_conc)}). A nota técnica da FUTURE "
            f"({ctx.nota_tecnica_future:.1f} pts) é comparada à nota técnica média da concorrência "
            f"({ctx.nota_tecnica_conc:.1f} pts). O resultado bruto é depois ponderado pelo Índice de Fiabilidade "
            f"Analítica — quanto menor a amostra histórica, mais o resultado é puxado para um cenário neutro (50 pts)."
        )


def render_curva_sensibilidade(df_curva, preco_future, preco_otimo_info, valor_limiar_critico):
    st.markdown("##### Curva de Sensibilidade ao Preço")
    st.caption("Mostra como o Índice Estratégico varia consoante o valor da proposta comercial, dentro do intervalo permitido.")

    df_plot = df_curva.set_index("Preço")[["Índice Estratégico"]]
    st.line_chart(df_plot)

    if preco_otimo_info:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Preço Ótimo Estimado", formatar_moeda(preco_otimo_info["preco"]),
                      help="Preço que maximiza o Valor Esperado (Índice Estratégico x valor da proposta).")
        with c2:
            st.metric("Índice no Preço Ótimo", f"{preco_otimo_info['indice']:.0f} / 100")
        with c3:
            diferenca = preco_otimo_info["preco"] - preco_future
            st.metric("Diferença Face ao Preço Simulado", formatar_moeda(abs(diferenca)),
                      delta=f"{'reduzir' if diferenca < 0 else 'aumentar'}")


def render_insights(insights):
    st.markdown("##### Insights Automáticos")
    classe_map = {"alerta": "fs-insight-alerta", "oportunidade": "fs-insight-oportunidade", "info": ""}
    icone_map = {"alerta": "⚠️", "oportunidade": "💡", "info": "ℹ️"}
    for tipo, texto in insights:
        classe = classe_map.get(tipo, "")
        icone = icone_map.get(tipo, "ℹ️")
        st.markdown(f"<div class='fs-insight {classe}'>{icone} {texto}</div>", unsafe_allow_html=True)


# =============================================================================
# APLICAÇÃO PRINCIPAL
# =============================================================================
def main():
    render_hero()

    try:
        df_concursos_raw, df_propostas_raw = carregar_dados()
        df_concursos, col_data_concurso = processar_concursos(df_concursos_raw)
        df_propostas, df_empresa_exploded = processar_propostas(df_propostas_raw)

        if df_concursos.empty or df_propostas.empty:
            st.info("Aguardando inserção de histórico de dados no Supabase para calibrar o motor preditivo.")
            return

        # --- INPUTS ---
        with st.container(border=True):
            st.markdown("#### Parâmetros do Cenário")
            col_in1, col_in2, col_in3 = st.columns(3)
            with col_in1:
                lista_clientes = sorted(df_concursos['nome_cliente'].unique())
                cliente_sel = st.selectbox("Cliente em Análise", lista_clientes)
                mercado_sel = st.selectbox("Mercado do Concurso", ["Fiscalização", "Projeto", "Coordenação", "Construção"])
                distrito_sel = st.selectbox("Zona / Distrito da Obra", ["Lisboa", "Norte", "Centro", "Sul", "Outro"])
            with col_in2:
                preco_base_input = st.number_input("Preço Base do Concurso (€)", min_value=1000.0, value=100000.0, step=5000.0)
                criterio_sel = st.selectbox("Critério de Avaliação", ["Preço Mais Baixo", "Qualidade/Preço (Fatores Ponderados)"])
                escalao_sim = definir_escalao(preco_base_input)
                st.caption(f"Escalão Financeiro Identificado: {escalao_sim}")
            with col_in3:
                limiar_anormal = st.number_input("Limiar Preço Anormalmente Baixo (% do Valor Base)", min_value=10.0, max_value=90.0, value=60.0, step=1.0)
                if criterio_sel == "Preço Mais Baixo":
                    w_preco, w_tecnico = 100, 0
                else:
                    w_preco = st.slider("Ponderação do Preço (%)", 10, 90, 60, step=5)
                    w_tecnico = 100 - w_preco

        # --- CONTEXTO HISTÓRICO ---
        ctx = calcular_contexto(df_concursos, df_propostas, df_empresa_exploded, cliente_sel,
                                 mercado_sel, distrito_sel, escalao_sim, preco_base_input)

        if ctx.n_concursos_total < LIMIAR_AMOSTRA_MINIMA:
            st.warning(
                f"Atenção: esta análise assenta apenas em {ctx.n_concursos_total} concurso(s) histórico(s) "
                f"para este cliente/mercado/zona. Com menos de {LIMIAR_AMOSTRA_MINIMA} concursos, os indicadores "
                f"têm fiabilidade estatística reduzida e devem ser interpretados com cautela."
            )

        aba_visao, aba_concorrencia, aba_simulacao = st.tabs(
            ["📊 Visão Geral", "🏢 Concorrência", "🎯 Simulação de Preço"]
        )

        with aba_visao:
            render_indicadores_calibracao(ctx, preco_base_input)
            st.divider()
            render_indicadores_contexto(ctx)
            st.divider()
            if not ctx.evolucao_desconto.empty:
                st.markdown("#### Evolução Temporal do Desconto Médio Praticado")
                st.line_chart(ctx.evolucao_desconto.set_index('Período'))
            elif col_data_concurso is None:
                st.caption("Não foi encontrada uma coluna de data reconhecível na tabela concursos "
                           "(procurados: data_concurso, data_publicacao, data_abertura, created_at, data).")

        with aba_concorrencia:
            render_tabelas_concorrencia(ctx)

        with aba_simulacao:
            preco_medio_conc = preco_base_input * (1 - ctx.desconto_medio)
            preco_future_min = float(preco_base_input * 0.3)
            preco_future_max = float(preco_base_input * 1.0)
            valor_limiar_critico = preco_base_input * (limiar_anormal / 100)

            st.markdown("#### Arena de Modelação Comercial de Preço")
            st.caption(f"Insira um valor entre {formatar_moeda(preco_future_min)} e {formatar_moeda(preco_future_max)} (30% a 100% do preço base).")

            preco_future = st.number_input(
                "Defina o Valor da Proposta Comercial da FUTURE (€)",
                min_value=preco_future_min, max_value=preco_future_max,
                value=float(preco_base_input * 0.90), step=500.0, format="%.2f"
            )

            resultado = calcular_indice_estrategico(
                preco_future, preco_medio_conc, ctx.nota_tecnica_future, ctx.nota_tecnica_conc,
                w_preco, w_tecnico, ctx.alpha_fiabilidade, valor_limiar_critico
            )

            df_curva = gerar_curva_sensibilidade(
                preco_future_min, preco_future_max, preco_medio_conc, ctx.nota_tecnica_future,
                ctx.nota_tecnica_conc, w_preco, w_tecnico, ctx.alpha_fiabilidade, valor_limiar_critico
            )
            preco_otimo_info = calcular_preco_otimo(df_curva)

            st.markdown("<br>", unsafe_allow_html=True)
            col_res1, col_res2 = st.columns([1, 1])
            with col_res1:
                render_indice_estrategico(resultado, preco_future, valor_limiar_critico)
                render_explicacao_fatores(resultado, ctx, w_preco, w_tecnico, preco_future, preco_medio_conc)
            with col_res2:
                if ctx.n_concursos_total < LIMIAR_AMOSTRA_MINIMA:
                    st.caption("Recorda-te: esta avaliação assenta numa amostra pequena — trata-a como indicativa, não conclusiva.")
                render_curva_sensibilidade(df_curva, preco_future, preco_otimo_info, valor_limiar_critico)

            st.divider()
            insights = gerar_insights(ctx, preco_future, preco_otimo_info, valor_limiar_critico,
                                       preco_base_input, resultado.get("indice"))
            render_insights(insights)

    except Exception as e:
        st.error(f"Erro na execução técnica do ambiente analítico: {e}")


main()