import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# --- TRANCAR A PÁGINA CONTRA ACESSOS DIRETOS ---
if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()
# -----------------------------------------------

# --- BOTÃO DE VOLTAR AO MENU PRINCIPAL (na sidebar, acima da navegação) ---
with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

st.markdown(
    """
    <style>
    [data-testid="stMetricLabel"] {
        font-size: 14px !important;
        white-space: normal !important;
        word-break: break-word !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 24px !important;
    }
    .sim-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .sim-value {
        font-size: 26px;
        font-weight: bold;
        color: #1b365d;
    }
    .sim-label {
        font-size: 13px;
        color: #64748b;
        margin-top: 5px;
    }
    .n-badge {
        display: inline-block;
        background-color: #eef2ff;
        color: #4338ca;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 999px;
        margin-left: 6px;
    }
    .consorcio-badge {
        display: inline-block;
        background-color: #fef3c7;
        color: #92400e;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 999px;
        margin-left: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

@st.cache_resource
def iniciar_ligacao():
    url = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    return create_client(url, chave)

def formatar_moeda(valor):
    if pd.isna(valor):
        return "0,00 €"
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def defining_escalao(valor):
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

try:
    supabase: Client = iniciar_ligacao()

    resp_concursos = supabase.table("concursos").select("*, clientes(nome_cliente)").execute()
    # --- NOVO: propostas + junção com empresas via proposta_empresas ---
    resp_propostas = supabase.table("propostas").select(
        "*, proposta_empresas(papel, empresas(id, nome_empresa))"
    ).execute()

    df_concursos = pd.DataFrame(resp_concursos.data) if resp_concursos.data else pd.DataFrame()
    df_propostas_raw = pd.DataFrame(resp_propostas.data) if resp_propostas.data else pd.DataFrame()

    if not df_concursos.empty:
        df_concursos['nome_cliente'] = df_concursos['clientes'].apply(lambda x: x.get('nome_cliente', 'Desconhecido') if isinstance(x, dict) else 'Desconhecido')
        df_concursos['Regiao'] = df_concursos['distrito'].apply(lambda x: str(x) if pd.notna(x) else 'Não Definido')
        df_concursos['escalao'] = df_concursos['preco_base'].apply(defining_escalao)

        col_data_candidatos = ['data_concurso', 'data_publicacao', 'data_abertura', 'created_at', 'data']
        col_data_concurso = next((c for c in col_data_candidatos if c in df_concursos.columns), None)
        if col_data_concurso:
            df_concursos['_data_norm'] = pd.to_datetime(df_concursos[col_data_concurso], errors='coerce')
        else:
            df_concursos['_data_norm'] = pd.NaT

        if 'data_adjudicacao' in df_concursos.columns:
            df_concursos['_data_adjudicacao_norm'] = pd.to_datetime(df_concursos['data_adjudicacao'], errors='coerce')
        else:
            df_concursos['_data_adjudicacao_norm'] = pd.NaT
    else:
        col_data_concurso = None

    # --- PROCESSAMENTO DA ESTRUTURA proposta -> empresas (1:N) ---
    # df_propostas: nível de PROPOSTA (uma linha por proposta, sem duplicar por consórcio)
    # df_empresa_exploded: nível de EMPRESA (uma linha por empresa em cada proposta, para análises de concorrente)
    df_propostas = pd.DataFrame()
    df_empresa_exploded = pd.DataFrame()

    if not df_propostas_raw.empty:
        if 'desclassificado' not in df_propostas_raw.columns:
            df_propostas_raw['desclassificado'] = False
        else:
            df_propostas_raw['desclassificado'] = df_propostas_raw['desclassificado'].fillna(False).astype(bool)

        if 'em_consorcio' not in df_propostas_raw.columns:
            df_propostas_raw['em_consorcio'] = False
        else:
            df_propostas_raw['em_consorcio'] = df_propostas_raw['em_consorcio'].fillna(False).astype(bool)

        def extrair_lider(lista_pe):
            """Devolve o nome da empresa líder (ou única) de uma proposta, para exibição/agregação simples."""
            if not isinstance(lista_pe, list) or len(lista_pe) == 0:
                return "Desconhecida"
            for item in lista_pe:
                if item.get('papel') == 'lider':
                    emp = item.get('empresas')
                    return emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
            # Se não há líder explícito (proposta individual), usa a primeira/única
            emp = lista_pe[0].get('empresas')
            return emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'

        def extrair_nomes_todas(lista_pe):
            if not isinstance(lista_pe, list):
                return []
            nomes = []
            for item in lista_pe:
                emp = item.get('empresas')
                if isinstance(emp, dict) and emp.get('nome_empresa'):
                    nomes.append(emp.get('nome_empresa'))
            return nomes

        df_propostas = df_propostas_raw.copy()
        df_propostas['nome_lider'] = df_propostas['proposta_empresas'].apply(extrair_lider)
        df_propostas['nomes_todas_empresas'] = df_propostas['proposta_empresas'].apply(extrair_nomes_todas)
        df_propostas['n_empresas_na_proposta'] = df_propostas['nomes_todas_empresas'].apply(len)
        # Rótulo legível do consórcio, ex: "Empresa A + Empresa B"
        df_propostas['label_concorrente'] = df_propostas['nomes_todas_empresas'].apply(
            lambda lst: " + ".join(lst) if lst else "Desconhecida"
        )

        # --- EXPLODE: uma linha por (proposta, empresa) para análises ao nível da empresa ---
        linhas_explodidas = []
        for _, prop in df_propostas.iterrows():
            lista_pe = prop.get('proposta_empresas')
            if not isinstance(lista_pe, list) or len(lista_pe) == 0:
                continue
            for item in lista_pe:
                emp = item.get('empresas')
                nome_emp = emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
                linhas_explodidas.append({
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
        df_empresa_exploded = pd.DataFrame(linhas_explodidas)

    st.title("Simulador de Cenário Concorrencial e Preço Alvo")
    st.markdown("Estudo prospectivo de viabilidade comercial e análise de concorrência baseada em histórico.")
    st.divider()

    if df_concursos.empty or df_propostas.empty:
        st.info("Aguardando inserção de histórico de dados no Supabase para calibrar o motor preditivo.")
    else:
        with st.container(border=True):
            col_in1, col_in2, col_in3 = st.columns(3)
            with col_in1:
                lista_clientes = sorted(df_concursos['nome_cliente'].unique())
                cliente_sel = st.selectbox("Cliente em Análise", lista_clientes)
                mercado_sel = st.selectbox("Mercado do Concurso", ["Fiscalização", "Projeto", "Coordenação", "Construção"])
                distrito_sel = st.selectbox("Zona / Distrito da Obra", ["Lisboa", "Norte", "Centro", "Sul", "Outro"])

            with col_in2:
                preco_base_input = st.number_input("Preço Base do Concurso (€)", min_value=1000.0, value=100000.0, step=5000.0)
                criterio_sel = st.selectbox("Critério de Avaliação", ["Preço Mais Baixo", "Qualidade/Preço (Fatores Ponderados)"])
                escalao_sim = defining_escalao(preco_base_input)
                st.caption(f"Escalão Financeiro Identificado: {escalao_sim}")

            with col_in3:
                limiar_anormal = st.number_input("Limiar Preço Anormalmente Baixo (% do Valor Base)", min_value=10.0, max_value=90.0, value=60.0, step=1.0)

                if criterio_sel == "Preço Mais Baixo":
                    w_preco, w_tecnico = 100, 0
                else:
                    w_preco = st.slider("Ponderação do Preço (%)", 10, 90, 60, step=5)
                    w_tecnico = 100 - w_preco

        # --- PROCESSAMENTO DO MOTOR ESTATÍSTICO ---
        filtro_cliente = df_concursos['nome_cliente'] == cliente_sel
        filtro_mercado_zona = (df_concursos['mercado'] == mercado_sel) & (df_concursos['distrito'] == distrito_sel)
        filtro_historico = df_concursos[filtro_cliente | filtro_mercado_zona]

        n_concursos_cliente = int(filtro_cliente.sum())
        n_concursos_mercado_zona = int(filtro_mercado_zona.sum())
        n_concursos_total_historico = len(filtro_historico)

        alpha_fiabilidade = 0.1
        desconto_medio_esperado = 0.08
        desconto_mediano_esperado = 0.08
        desconto_desvio = 0.0
        nota_tecnica_future = 85.0
        nota_tecnica_future_real = False
        nota_tecnica_conc_media = 0.82 * 100
        nota_tecnica_conc_real = False
        n_propostas_validas = 0
        n_propostas_future_com_nota = 0
        n_propostas_concorrentes_com_nota = 0
        taxa_desclassificacao = None
        taxa_sucesso_future = None
        n_concursos_future_participou = 0
        n_concursos_future_ganhou = 0
        media_concorrentes_por_concurso = None
        evolucao_desconto_temporal = pd.DataFrame()
        tempo_medio_adjudicacao_dias = None
        n_concursos_com_adjudicacao = 0
        n_propostas_consorcio = 0
        taxa_consorcio = None
        dados_tabela_concorrentes = []
        dados_tabela_consorcios = []

        if not filtro_historico.empty:
            ids_concursos_filtrados = filtro_historico['id'].tolist()

            # --- Nível PROPOSTA (sem duplicação por consórcio) ---
            df_propostas_contexto = df_propostas[df_propostas['concurso_id'].isin(ids_concursos_filtrados)].copy()
            df_propostas_validas = df_propostas_contexto[df_propostas_contexto['desclassificado'] == False].copy()
            n_propostas_validas = len(df_propostas_validas)
            n_propostas_consorcio = int(df_propostas_contexto['em_consorcio'].sum())
            if len(df_propostas_contexto) > 0:
                taxa_consorcio = n_propostas_consorcio / len(df_propostas_contexto)

            alpha_fiabilidade = min(1.0, 0.05 + (n_concursos_total_historico * 0.10) + (min(n_propostas_validas, 20) * 0.01))

            if len(df_propostas_contexto) > 0:
                taxa_desclassificacao = df_propostas_contexto['desclassificado'].mean()

            # --- Nível EMPRESA (explodido) para nº médio de concorrentes ---
            df_emp_contexto = df_empresa_exploded[df_empresa_exploded['concurso_id'].isin(ids_concursos_filtrados)].copy()
            df_emp_validas = df_emp_contexto[df_emp_contexto['desclassificado'] == False].copy()
            if not df_emp_validas.empty:
                media_concorrentes_por_concurso = df_emp_validas.groupby('concurso_id')['nome_empresa'].nunique().mean()

            df_prazo = filtro_historico.dropna(subset=['_data_norm', '_data_adjudicacao_norm']).copy()
            if not df_prazo.empty:
                df_prazo['_dias_ate_adjudicacao'] = (df_prazo['_data_adjudicacao_norm'] - df_prazo['_data_norm']).dt.days
                df_prazo = df_prazo[df_prazo['_dias_ate_adjudicacao'] >= 0]
                if not df_prazo.empty:
                    tempo_medio_adjudicacao_dias = df_prazo['_dias_ate_adjudicacao'].mean()
                    n_concursos_com_adjudicacao = len(df_prazo)

            if not df_propostas_validas.empty:
                # --- Cruzamento ao nível da PROPOSTA (desconto, evolução temporal, etc.) ---
                df_cruzado = pd.merge(
                    df_propostas_validas,
                    filtro_historico[['id', 'preco_base', 'escalao', 'mercado', 'distrito', 'nome_cliente', '_data_norm']],
                    left_on='concurso_id', right_on='id'
                )
                df_cruzado['desconto'] = (df_cruzado['preco_base'] - df_cruzado['valor_proposto']) / df_cruzado['preco_base']

                q1 = df_cruzado['desconto'].quantile(0.25)
                q3 = df_cruzado['desconto'].quantile(0.75)
                iqr = q3 - q1
                limite_inf = q1 - 1.5 * iqr
                limite_sup = q3 + 1.5 * iqr
                df_desconto_limpo = df_cruzado[(df_cruzado['desconto'] >= limite_inf) & (df_cruzado['desconto'] <= limite_sup)]

                if not df_desconto_limpo.empty:
                    media_desc = df_desconto_limpo['desconto'].mean()
                    mediana_desc = df_desconto_limpo['desconto'].median()
                    desvio_desc = df_desconto_limpo['desconto'].std()
                    if pd.notna(media_desc):
                        desconto_medio_esperado = float(media_desc)
                    if pd.notna(mediana_desc):
                        desconto_mediano_esperado = float(mediana_desc)
                    if pd.notna(desvio_desc):
                        desconto_desvio = float(desvio_desc)

                if df_cruzado['_data_norm'].notna().sum() >= 2:
                    df_temporal = df_cruzado.dropna(subset=['_data_norm']).sort_values('_data_norm')
                    df_temporal['ano_mes'] = df_temporal['_data_norm'].dt.to_period('M').astype(str)
                    evolucao_desconto_temporal = df_temporal.groupby('ano_mes')['desconto'].mean().reset_index()
                    evolucao_desconto_temporal.columns = ['Período', 'Desconto Médio']

                # --- Nota técnica FUTURE (ao nível da proposta, já que notas são por proposta) ---
                df_future_historico = df_cruzado[df_cruzado['nome_lider'].str.upper() == 'FUTURE']
                notas_extraidas = []
                for _, r in df_future_historico.iterrows():
                    n_json = r.get('notas_criterios')
                    if isinstance(n_json, dict):
                        soma_notas = n_json.get('CVs', 0) + n_json.get('Metodologia', 0) + n_json.get('Afetacao', 0)
                        if soma_notas > 0:
                            notas_extraidas.append(soma_notas)
                n_propostas_future_com_nota = len(notas_extraidas)
                if notas_extraidas:
                    nota_tecnica_future = float(np.mean(notas_extraidas))
                    nota_tecnica_future_real = True

                if not df_future_historico.empty and 'vencedor' in df_future_historico.columns:
                    n_concursos_future_participou = df_future_historico['concurso_id'].nunique()
                    n_concursos_future_ganhou = int(df_future_historico[df_future_historico['vencedor'] == True]['concurso_id'].nunique())
                    if n_concursos_future_participou > 0:
                        taxa_sucesso_future = n_concursos_future_ganhou / n_concursos_future_participou

                # --- Notas técnicas da concorrência (excluindo FUTURE), ao nível da proposta ---
                df_conc_propostas = df_cruzado[df_cruzado['nome_lider'].str.upper() != 'FUTURE']
                notas_conc_extraidas = []
                for _, r in df_conc_propostas.iterrows():
                    n_json = r.get('notas_criterios')
                    if isinstance(n_json, dict):
                        soma_notas = n_json.get('CVs', 0) + n_json.get('Metodologia', 0) + n_json.get('Afetacao', 0)
                        if soma_notas > 0:
                            notas_conc_extraidas.append(soma_notas)
                n_propostas_concorrentes_com_nota = len(notas_conc_extraidas)
                if notas_conc_extraidas:
                    nota_tecnica_conc_media = float(np.mean(notas_conc_extraidas))
                    nota_tecnica_conc_real = True

                # --- TABELA DE CONCORRENTES (nível EMPRESA, para captar cada participante do consórcio) ---
                df_emp_cruzado = pd.merge(
                    df_emp_validas,
                    filtro_historico[['id', 'preco_base', 'escalao', 'mercado', 'distrito', 'nome_cliente']],
                    left_on='concurso_id', right_on='id'
                )
                df_emp_cruzado['desconto'] = (df_emp_cruzado['preco_base'] - df_emp_cruzado['valor_proposto']) / df_emp_cruzado['preco_base']
                empresas_adversarias = df_emp_cruzado[df_emp_cruzado['nome_empresa'].str.upper() != 'FUTURE']

                if not empresas_adversarias.empty:
                    total_concursos_contexto = df_emp_cruzado['concurso_id'].nunique()

                    for empresa, df_emp in empresas_adversarias.groupby('nome_empresa'):
                        n_props_emp = df_emp['proposta_id'].nunique()
                        n_props_consorcio_emp = int(df_emp['em_consorcio'].sum())
                        match_cliente = df_emp['nome_cliente'].eq(cliente_sel).sum()
                        match_escalao = df_emp['escalao'].eq(escalao_sim).sum()
                        match_mercado = df_emp['mercado'].eq(mercado_sel).sum()
                        match_zona = df_emp['distrito'].eq(distrito_sel).sum()

                        score_presenca = (match_cliente * 0.4) + (match_escalao * 0.2) + (match_mercado * 0.2) + (match_zona * 0.2)
                        prob_participacao = min(95.0, 15.0 + (score_presenca / max(1, total_concursos_contexto)) * 100)

                        desc_medio_emp = df_emp['desconto'].mean() if not df_emp['desconto'].empty else desconto_medio_esperado
                        valor_numerario_desconto = preco_base_input * desc_medio_emp

                        dados_tabela_concorrentes.append({
                            "Concorrente": empresa,
                            "N": n_props_emp,
                            "Em Consórcio": f"{n_props_consorcio_emp}/{n_props_emp}",
                            "Probabilidade Participação": f"{prob_participacao:.1f}%",
                            "Desconto Estimado Face ao Base": f"{desc_medio_emp * 100:.1f}%",
                            "Diferença Estimada (Numerário)": formatar_moeda(valor_numerario_desconto),
                            "Ordem_Prob": prob_participacao
                        })

                    # --- TABELA DE PARCERIAS FREQUENTES (consórcios recorrentes) ---
                    df_so_consorcios = df_propostas_contexto[df_propostas_contexto['em_consorcio'] == True]
                    if not df_so_consorcios.empty:
                        contagem_parcerias = df_so_consorcios['label_concorrente'].value_counts()
                        for label, contagem in contagem_parcerias.items():
                            if contagem >= 2:  # só mostra parcerias que já se repetiram
                                dados_tabela_consorcios.append({
                                    "Consórcio": label,
                                    "Nº de Concursos Conjuntos": int(contagem)
                                })

        if dados_tabela_concorrentes:
            dados_tabela_concorrentes = sorted(dados_tabela_concorrentes, key=lambda x: x["Ordem_Prob"], reverse=True)
            for item in dados_tabela_concorrentes:
                del item["Ordem_Prob"]

        LIMIAR_AMOSTRA_MINIMA = 3
        if n_concursos_total_historico < LIMIAR_AMOSTRA_MINIMA:
            st.warning(
                f"Atenção: esta análise assenta apenas em {n_concursos_total_historico} concurso(s) histórico(s) "
                f"para este cliente/mercado/zona. Com menos de {LIMIAR_AMOSTRA_MINIMA} concursos, os indicadores abaixo "
                f"têm fiabilidade estatística reduzida e devem ser interpretados com cautela."
            )

        st.markdown("#### Indicadores Analíticos de Calibração")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        with col_m1:
            st.metric(
                label="Índice de Fiabilidade Analítica (alpha)",
                value=f"{alpha_fiabilidade * 100:.0f}%",
                help=f"Robustez estatística do cenário. Baseado em {n_concursos_total_historico} concurso(s) histórico(s) "
                     f"({n_concursos_cliente} do mesmo cliente, {n_concursos_mercado_zona} do mesmo mercado/zona) "
                     f"e {n_propostas_validas} proposta(s) válida(s)."
            )
        with col_m2:
            st.metric(
                label="Preço Médio Estimado da Concorrência",
                value=formatar_moeda(preco_base_input * (1 - desconto_medio_esperado)),
                help=f"Baseado na mediana de desconto histórico ({desconto_mediano_esperado*100:.1f}%) e média sem outliers "
                     f"({desconto_medio_esperado*100:.1f}% +/- {desconto_desvio*100:.1f} p.p.), n = {n_propostas_validas} propostas."
            )
        with col_m3:
            nota_help = (
                f"Baseado em {n_propostas_future_com_nota} proposta(s) real(is) da FUTURE com notas registadas."
                if nota_tecnica_future_real else
                "Valor por omissão (85.0) — não existem notas técnicas reais da FUTURE no histórico filtrado."
            )
            st.metric(
                label="Nota Técnica Esperada (FUTURE)" + ("" if nota_tecnica_future_real else " (estimado)"),
                value=f"{nota_tecnica_future:.1f} Pts",
                help=nota_help
            )
        with col_m4:
            if taxa_sucesso_future is not None:
                st.metric(
                    label="Taxa de Sucesso Histórica FUTURE",
                    value=f"{taxa_sucesso_future*100:.0f}%",
                    help=f"{n_concursos_future_ganhou} ganhos em {n_concursos_future_participou} concurso(s) participado(s) neste contexto."
                )
            else:
                st.metric(
                    label="Taxa de Sucesso Histórica FUTURE",
                    value="N/D",
                    help="Não existe coluna 'vencedor' na tabela de propostas, ou não há dados suficientes para calcular esta taxa."
                )

        st.divider()

        st.markdown("#### Indicadores de Contexto Adicional")
        col_x1, col_x2, col_x3, col_x4, col_x5 = st.columns(5)

        with col_x1:
            if media_concorrentes_por_concurso is not None:
                st.metric(
                    label="Nº Médio de Concorrentes por Concurso",
                    value=f"{media_concorrentes_por_concurso:.1f}",
                    help="Média de empresas distintas (excluindo desclassificados) por concurso. Cada membro de um consórcio conta individualmente."
                )
            else:
                st.metric(label="Nº Médio de Concorrentes por Concurso", value="N/D")

        with col_x2:
            if taxa_desclassificacao is not None:
                st.metric(
                    label="Taxa Histórica de Desclassificação",
                    value=f"{taxa_desclassificacao*100:.1f}%",
                    help="Percentagem de propostas neste contexto que foram desclassificadas."
                )
            else:
                st.metric(label="Taxa Histórica de Desclassificação", value="N/D")

        with col_x3:
            nota_conc_help = (
                f"Baseado em {n_propostas_concorrentes_com_nota} proposta(s) real(is) de concorrentes com notas registadas."
                if nota_tecnica_conc_real else
                "Valor por omissão (82.0) — não existem notas técnicas reais de concorrentes no histórico filtrado."
            )
            st.metric(
                label="Nota Técnica Média da Concorrência" + ("" if nota_tecnica_conc_real else " (estimado)"),
                value=f"{nota_tecnica_conc_media:.1f} Pts",
                help=nota_conc_help
            )

        with col_x4:
            if tempo_medio_adjudicacao_dias is not None:
                st.metric(
                    label="Tempo Médio até Adjudicação",
                    value=f"{tempo_medio_adjudicacao_dias:.0f} dias",
                    help=f"Baseado em {n_concursos_com_adjudicacao} concurso(s) com ambas as datas preenchidas."
                )
            else:
                st.metric(
                    label="Tempo Médio até Adjudicação",
                    value="N/D",
                    help="Não há concursos neste contexto com data_concurso e data_adjudicacao preenchidas em simultâneo."
                )

        with col_x5:
            if taxa_consorcio is not None:
                st.metric(
                    label="Taxa de Propostas em Consórcio",
                    value=f"{taxa_consorcio*100:.0f}%",
                    help=f"{n_propostas_consorcio} de {len(df_propostas_contexto)} proposta(s) neste contexto foram submetidas em agrupamento/consórcio."
                )
            else:
                st.metric(label="Taxa de Propostas em Consórcio", value="N/D")

        st.divider()

        if not evolucao_desconto_temporal.empty:
            st.markdown("#### Evolução Temporal do Desconto Médio Praticado")
            st.line_chart(evolucao_desconto_temporal.set_index('Período'))
        elif col_data_concurso is None:
            st.caption("Não foi encontrada uma coluna de data reconhecível na tabela concursos "
                       "(procurados: data_concurso, data_publicacao, data_abertura, created_at, data), "
                       "pelo que a evolução temporal não pode ser calculada.")

        st.divider()

        st.markdown("#### Previsão de Participação e Comportamento da Concorrência")
        st.markdown(
            f"Índice de fiabilidade específico destas métricas concorrenciais: **{int(alpha_fiabilidade * 100)} / 100**"
            f"&nbsp;&nbsp;{badge_n(n_concursos_total_historico)}",
            unsafe_allow_html=True
        )
        st.caption("A coluna 'Em Consórcio' mostra quantas das propostas desta empresa foram submetidas em agrupamento, sobre o total.")

        if dados_tabela_concorrentes:
            df_mostrar_concorrentes = pd.DataFrame(dados_tabela_concorrentes)
            df_mostrar_concorrentes = df_mostrar_concorrentes.rename(columns={"N": "Nº Propostas Observadas"})
            st.dataframe(df_mostrar_concorrentes, use_container_width=True, hide_index=True)
        else:
            st.info("Não existem dados históricos suficientes para projetar concorrentes específicos.")

        if dados_tabela_consorcios:
            st.markdown("##### Parcerias Recorrentes Identificadas")
            st.caption("Combinações de empresas que já concorreram juntas em mais do que um concurso, neste contexto.")
            df_mostrar_consorcios = pd.DataFrame(dados_tabela_consorcios).sort_values("Nº de Concursos Conjuntos", ascending=False)
            st.dataframe(df_mostrar_consorcios, use_container_width=True, hide_index=True)

        st.divider()

        st.markdown("#### Arena de Modelação Comercial de Preço")

        preco_future_min = float(preco_base_input * 0.3)
        preco_future_max = float(preco_base_input * 1.0)

        st.caption(f"Insira um valor entre {formatar_moeda(preco_future_min)} e {formatar_moeda(preco_future_max)} (30% a 100% do preço base).")

        preco_future = st.number_input(
            "Defina o Valor da Proposta Comercial da FUTURE (€)",
            min_value=preco_future_min,
            max_value=preco_future_max,
            value=float(preco_base_input * 0.90),
            step=500.0,
            format="%.2f"
        )

        valor_limiar_critico = preco_base_input * (limiar_anormal / 100)

        if preco_future < valor_limiar_critico:
            st.error(f"Alerta de Exclusão: O preço simulado ({formatar_moeda(preco_future)}) situa-se abaixo do limiar de preço anormalmente baixo parametrizado ({limiar_anormal}% do valor base = {formatar_moeda(valor_limiar_critico)}). Risco de desclassificação direta.")

        preco_medio_conc = preco_base_input * (1 - desconto_medio_esperado)
        pontos_preco_fut = (preco_medio_conc / preco_future) * w_preco if preco_future > 0 else 0
        pontos_preco_conc = w_preco
        pontos_tec_fut = (nota_tecnica_future / 100) * w_tecnico
        pontos_tec_conc = (nota_tecnica_conc_media / 100) * w_tecnico

        score_diferencial = (pontos_preco_fut + pontos_tec_fut) - (pontos_preco_conc + pontos_tec_conc)
        prob_bruta = 1 / (1 + np.exp(-0.2 * score_diferencial))
        prob_ponderada_final = (prob_bruta * alpha_fiabilidade) + (0.5 * (1 - alpha_fiabilidade))

        st.markdown("<br>", unsafe_allow_html=True)
        col_res1, col_res2 = st.columns([2, 1])

        with col_res1:
            st.markdown("##### Avaliação de Viabilidade do Cenário de Preço")
            if preco_future < valor_limiar_critico:
                st.error("Proposta inviabilizada. O valor está situado abaixo do factor mínimo exigido por Lei/Caderno de Encargos.")
            elif prob_ponderada_final > 0.65:
                st.success(f"Posicionamento Altamente Competitivo: O valor de {formatar_moeda(preco_future)} confere uma vantagem estatística robusta perante as curvas de agressividade mapeadas.")
            elif prob_ponderada_final > 0.45:
                st.warning("Equilíbrio de Forças no Mercado: Margem de decisão estrita. O resultado assentará na avaliação fina do júri relativamente aos critérios técnicos.")
            else:
                st.error("Posicionamento de Baixa Competitividade: Margem financeira excessivamente conservadora. O valor situa-se acima das médias agressivas operadas neste mercado.")

            if n_concursos_total_historico < LIMIAR_AMOSTRA_MINIMA:
                st.caption("Recorda-te: esta avaliação assenta numa amostra pequena — trata-a como indicativa, não conclusiva.")

        with col_res2:
            valor_prob_exibir = 0.0 if preco_future < valor_limiar_critico else prob_ponderada_final * 100

            tooltip_texto = (
                f"Cálculo baseado em: (1) rácio entre o preço médio estimado da concorrência e o preço simulado, "
                f"ponderado a {w_preco}%; (2) nota técnica esperada da FUTURE ({nota_tecnica_future:.1f} pts) "
                f"face à nota técnica média da concorrência ({nota_tecnica_conc_media:.1f} pts), ponderada a {w_tecnico}%; "
                f"(3) o resultado é ajustado pelo índice de fiabilidade analítica (alpha = {alpha_fiabilidade*100:.0f}%), "
                f"que pondera o valor calculado com um cenário neutro de 50% quando a amostra histórica é reduzida "
                f"(n = {n_concursos_total_historico} concurso(s) histórico(s))."
            )

            st.metric(
                label="Probabilidade de Sucesso Estimada",
                value=f"{valor_prob_exibir:.1f}%",
                help=tooltip_texto
            )

except Exception as e:
    st.error(f"Erro na execução técnica do ambiente analítico: {e}")