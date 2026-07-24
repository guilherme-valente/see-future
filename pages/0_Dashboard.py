import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import numpy as np

if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

st.title("Dashboard Executivo | See Future")
st.markdown("Visão global de métricas e performance de concursos.")
st.divider()

st.markdown(
    """
    <style>
    [data-testid="stMetricLabel"] { font-size: 14px !important; white-space: normal !important; word-break: break-word !important; }
    [data-testid="stMetricValue"] { font-size: 24px !important; }
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
    try:
        return f"{float(valor):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 €"

def explodir_propostas(df_propostas_raw):
    """Transforma a relação proposta_empresas em linhas (uma por empresa/proposta),
    incluindo consórcios. Devolve sempre um DataFrame válido, mesmo sem dados."""
    if df_propostas_raw is None or df_propostas_raw.empty:
        return pd.DataFrame()

    linhas = []
    for _, prop in df_propostas_raw.iterrows():
        base = prop.to_dict()
        lista_pe = base.pop('proposta_empresas', None)

        if isinstance(lista_pe, list) and len(lista_pe) > 0:
            for item in lista_pe:
                if not isinstance(item, dict):
                    continue
                emp = item.get('empresas')
                nome_emp = emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
                linha = dict(base)
                linha['nome_empresa'] = str(nome_emp).strip() if nome_emp else 'Desconhecida'
                linha['papel'] = item.get('papel', 'individual')
                linha['em_consorcio'] = len(lista_pe) > 1
                linhas.append(linha)
        else:
            linha = dict(base)
            linha['nome_empresa'] = 'Desconhecida'
            linha['papel'] = None
            linha['em_consorcio'] = False
            linhas.append(linha)

    return pd.DataFrame(linhas)

try:
    supabase: Client = iniciar_ligacao()

    df_concursos = pd.DataFrame(supabase.table("concursos").select("*").execute().data or [])
    df_clientes = pd.DataFrame(supabase.table("clientes").select("*").execute().data or [])
    df_empresas = pd.DataFrame(supabase.table("empresas").select("*").execute().data or [])

    resposta_propostas = supabase.table("propostas").select(
        "*, proposta_empresas(papel, empresas(id, nome_empresa))"
    ).execute()
    df_propostas_raw = pd.DataFrame(resposta_propostas.data) if resposta_propostas.data else pd.DataFrame()
    df_propostas = explodir_propostas(df_propostas_raw)

    if not df_concursos.empty:
        df_concursos['data_concurso'] = pd.to_datetime(df_concursos['data_concurso'], errors='coerce')
        df_concursos = df_concursos.dropna(subset=['data_concurso'])
        df_concursos['ano'] = df_concursos['data_concurso'].dt.year
        df_concursos['mes'] = df_concursos['data_concurso'].dt.month
        df_concursos['semestre'] = df_concursos['mes'].apply(lambda x: '1º Semestre' if x <= 6 else '2º Semestre')

        num_clientes = len(df_clientes)

        st.sidebar.header("Filtros Temporais")
        anos_disponiveis = sorted(df_concursos['ano'].dropna().unique(), reverse=True)
        ano_selecionado = st.sidebar.selectbox("Selecionar Ano", ["Todos"] + [int(a) for a in anos_disponiveis])
        semestre_selecionado = st.sidebar.selectbox("Selecionar Semestre", ["Ano Completo", "1º Semestre", "2º Semestre"])

        df_concursos_filtrado = df_concursos.copy()
        if ano_selecionado != "Todos":
            df_concursos_filtrado = df_concursos_filtrado[df_concursos_filtrado['ano'] == ano_selecionado]
        if semestre_selecionado != "Ano Completo":
            df_concursos_filtrado = df_concursos_filtrado[df_concursos_filtrado['semestre'] == semestre_selecionado]

        concursos_ids_filtrados = df_concursos_filtrado['id'].tolist()

        num_participacoes = 0
        taxa_sucesso = 0.0
        valor_total_adjudicado = 0.0
        diferenca_media_perc = np.nan
        df_propostas_filtrado = pd.DataFrame()
        propostas_future = pd.DataFrame()

        if not df_propostas.empty:
            df_propostas['vencedor'] = df_propostas.get('vencedor', False)
            df_propostas['vencedor'] = df_propostas['vencedor'].fillna(False).astype(bool)
            df_propostas['valor_proposto'] = pd.to_numeric(df_propostas.get('valor_proposto'), errors='coerce').fillna(0.0)
            df_propostas['classificacao_final'] = pd.to_numeric(df_propostas.get('classificacao_final'), errors='coerce').fillna(0)

            # Preço base e data vêm agora do concurso associado (merge), não de coluna aninhada antiga
            df_concursos_map = df_concursos[['id', 'preco_base', 'data_concurso']].rename(columns={'id': 'concurso_id'})
            df_propostas = pd.merge(df_propostas, df_concursos_map, on='concurso_id', how='left')
            df_propostas['ano'] = df_propostas['data_concurso'].dt.year

            df_propostas_filtrado = df_propostas[df_propostas['concurso_id'].isin(concursos_ids_filtrados)].copy()

            if not df_propostas_filtrado.empty:
                df_propostas_filtrado = df_propostas_filtrado[df_propostas_filtrado['preco_base'] > 0]
                df_propostas_filtrado['diferenca_perc'] = ((df_propostas_filtrado['preco_base'] - df_propostas_filtrado['valor_proposto']) / df_propostas_filtrado['preco_base']) * 100
                propostas_future = df_propostas_filtrado[df_propostas_filtrado['nome_empresa'].str.upper() == 'FUTURE']
                num_participacoes = propostas_future['proposta_id'].nunique() if 'proposta_id' in propostas_future.columns else len(propostas_future)

                vitorias_future = propostas_future[propostas_future['vencedor'] == True]
                valor_total_adjudicado = vitorias_future['valor_proposto'].sum()

                if num_participacoes > 0:
                    taxa_sucesso = (len(vitorias_future) / num_participacoes) * 100

                    derrotas_future = propostas_future[propostas_future['vencedor'] == False]
                    if not derrotas_future.empty:
                        concursos_perdidos_ids = derrotas_future['concurso_id'].tolist()
                        vencedores_desses_concursos = df_propostas_filtrado[
                            (df_propostas_filtrado['concurso_id'].isin(concursos_perdidos_ids)) &
                            (df_propostas_filtrado['vencedor'] == True)
                        ]

                        if not vencedores_desses_concursos.empty:
                            df_comparacao = pd.merge(
                                derrotas_future[['concurso_id', 'valor_proposto']],
                                vencedores_desses_concursos[['concurso_id', 'valor_proposto']],
                                on='concurso_id',
                                suffixes=('_future', '_vencedor')
                            )
                            if not df_comparacao.empty:
                                df_comparacao = df_comparacao[df_comparacao['valor_proposto_vencedor'] > 0]
                                df_comparacao['diff_perc'] = ((df_comparacao['valor_proposto_future'] - df_comparacao['valor_proposto_vencedor']) / df_comparacao['valor_proposto_vencedor']) * 100
                                df_comparacao['diff_perc'] = df_comparacao['diff_perc'].replace([np.inf, -np.inf], np.nan)
                                diferenca_media_perc = df_comparacao['diff_perc'].mean()

        if pd.isna(diferenca_media_perc):
            texto_diff_media = "N/A"
        else:
            sinal = "+" if diferenca_media_perc > 0 else ""
            texto_diff_media = f"{sinal}{diferenca_media_perc:.1f}%"

        st.subheader("1. Indicadores Chave")
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nº Concursos Participados", num_participacoes)
            c2.metric("Taxa de Sucesso", f"{taxa_sucesso:.1f}%")
            c3.metric("Valor Total dos Concursos", formatar_moeda(df_concursos_filtrado['preco_base'].sum()))
            c4.metric("Valor Adjudicado (FUTURE)", formatar_moeda(valor_total_adjudicado), help="Soma das propostas adjudicadas à FUTURE.")

            st.markdown("<br>", unsafe_allow_html=True)

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Diferença Média p/ Vencedor", texto_diff_media, help="Desvio percentual face ao preço do vencedor nas nossas derrotas.")
            c6.metric("Nº de Clientes", num_clientes)
            n_concorrentes = len(df_empresas[df_empresas['nome_empresa'].str.upper() != 'FUTURE']) if not df_empresas.empty else 0
            c7.metric("Nº Concorrentes Analisados", n_concorrentes)
            c8.empty()

        st.divider()

        st.subheader("2. Análise Gráfica")

        if not propostas_future.empty:
            g_col1, g_col2 = st.columns(2)

            with g_col1:
                with st.container(border=True):
                    stats_ano = propostas_future.groupby('ano').agg(Participações=('concurso_id', 'count'), Vitórias=('vencedor', 'sum')).reset_index()
                    fig1 = px.bar(stats_ano, x='ano', y=['Participações', 'Vitórias'], barmode='group', title="Participações vs Vitórias por Ano", color_discrete_sequence=['#0052CC', '#36B37E'])
                    fig1.update_layout(xaxis=dict(tickformat="d"))
                    st.plotly_chart(fig1, use_container_width=True)

            with g_col2:
                with st.container(border=True):
                    desc_ano = propostas_future.groupby('ano')['diferenca_perc'].mean().reset_index()
                    fig2 = px.line(desc_ano, x='ano', y='diferenca_perc', markers=True, title="Evolução do Desconto Médio (%) face ao Preço Base", labels={'diferenca_perc': 'Desconto Médio (%)'}, color_discrete_sequence=['#FF991F'])
                    fig2.update_layout(xaxis=dict(tickformat="d"))
                    st.plotly_chart(fig2, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            g_col3, g_col4 = st.columns(2)

            with g_col3:
                with st.container(border=True):
                    df_outros = df_propostas_filtrado[df_propostas_filtrado['nome_empresa'].str.upper() != 'FUTURE'].copy()
                    df_confrontos = pd.merge(
                        df_outros,
                        propostas_future[['concurso_id', 'classificacao_final']],
                        on='concurso_id',
                        suffixes=('_comp', '_fut')
                    )

                    if not df_confrontos.empty:
                        def ficou_acima(row):
                            if row.get('vencedor') == True:
                                return True
                            class_comp = row.get('classificacao_final_comp', 0)
                            class_fut = row.get('classificacao_final_fut', 0)
                            if class_comp > 0 and class_fut > 0 and class_comp < class_fut:
                                return True
                            return False

                        df_confrontos['ficou_acima'] = df_confrontos.apply(ficou_acima, axis=1)
                        df_acima = df_confrontos[df_confrontos['ficou_acima'] == True]

                        if not df_acima.empty:
                            top_c = df_acima.groupby('nome_empresa').agg(
                                Ficou_Acima=('concurso_id', 'count'),
                                Ganhou=('vencedor', 'sum')
                            ).reset_index()

                            top_c = top_c.sort_values(by='Ficou_Acima', ascending=True).tail(10)

                            fig3 = px.bar(
                                top_c, y='nome_empresa', x=['Ficou_Acima', 'Ganhou'], orientation='h', barmode='group',
                                title="Concorrentes (Ficou Acima de nós vs Venceu)",
                                labels={'value': 'Nº de Concursos', 'variable': 'Resultado', 'nome_empresa': 'Empresa'},
                                color_discrete_sequence=['#FF991F', '#FF5630']
                            )
                            fig3.for_each_trace(lambda t: t.update(name={'Ficou_Acima': 'Ficou Acima', 'Ganhou': 'Acabou por Vencer'}.get(t.name, t.name)))
                            st.plotly_chart(fig3, use_container_width=True)
                        else:
                            st.info("Nenhuma empresa ficou à nossa frente nos concursos analisados.")
                    else:
                        st.info("Ainda não há dados suficientes de confrontos com a concorrência.")

            with g_col4:
                with st.container(border=True):
                    stats_mercado = df_concursos_filtrado.groupby('mercado').size().reset_index(name='Quantidade')
                    fig4 = px.pie(stats_mercado, values='Quantidade', names='mercado', hole=0.4, title="Distribuição de Concursos por Unidade de Negócio", color_discrete_sequence=px.colors.qualitative.Set3)
                    st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Sem participações registadas para os filtros selecionados.")
    else:
        st.warning("Ainda não existem dados na plataforma.")

except Exception as e:
    st.error(f"Erro ao gerar dashboard: {e}")