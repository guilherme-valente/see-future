import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import numpy as np

if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

st.set_page_config(page_title="Estatísticas Globais | See Future", layout="wide")
st.title("Estatísticas Globais de Mercado")
st.markdown("Análise macroscópica do mercado, concorrência e performance da FUTURE.")
st.divider()

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] a[href*="Avaliação"] { display: none !important; }
    [data-testid="stMetricLabel"] { font-size: 13px !important; white-space: normal !important; word-break: break-word !important; line-height: 1.2 !important; min-height: 32px !important; }
    [data-testid="stMetricValue"] { font-size: 22px !important; }
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

def definir_escalao(valor):
    if pd.isna(valor):
        return "Não Definido"
    if valor < 50000: return "< 50k€"
    elif valor < 250000: return "50k€ - 250k€"
    elif valor < 500000: return "250k€ - 500k€"
    else: return "> 500k€"

def explodir_propostas(df_propostas_raw):
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

    resp_concursos = supabase.table("concursos").select("*, clientes(nome_cliente)").execute()
    resp_propostas = supabase.table("propostas").select(
        "*, proposta_empresas(papel, empresas(id, nome_empresa))"
    ).execute()

    if resp_concursos.data and resp_propostas.data:
        df_concursos = pd.DataFrame(resp_concursos.data)
        df_propostas_raw = pd.DataFrame(resp_propostas.data)
        df_propostas = explodir_propostas(df_propostas_raw)

        df_concursos['nome_cliente'] = df_concursos['clientes'].apply(lambda x: x.get('nome_cliente', 'Desconhecido') if isinstance(x, dict) else 'Desconhecido')
        df_concursos['Regiao'] = df_concursos['distrito'].apply(lambda x: str(x) if pd.notna(x) else 'Não Definido')
        df_concursos['escalao'] = df_concursos['preco_base'].apply(definir_escalao)
        df_concursos['data_concurso'] = pd.to_datetime(df_concursos['data_concurso'], errors='coerce')
        df_concursos = df_concursos.dropna(subset=['data_concurso'])
        df_concursos['ano'] = df_concursos['data_concurso'].dt.year
        df_concursos['semestre'] = df_concursos['data_concurso'].dt.month.apply(lambda x: '1º Semestre' if x <= 6 else '2º Semestre')

        if df_propostas.empty:
            st.warning("Ainda não existem dados na base de dados para gerar estatísticas.")
        else:
            df_propostas['vencedor'] = df_propostas.get('vencedor', False)
            df_propostas['vencedor'] = df_propostas['vencedor'].fillna(False).astype(bool)
            df_propostas['valor_proposto'] = pd.to_numeric(df_propostas.get('valor_proposto'), errors='coerce').fillna(0.0)

            df_geral = pd.merge(df_propostas, df_concursos, left_on='concurso_id', right_on='id', suffixes=('_prop', '_conc'))
            df_geral = df_geral[df_geral['preco_base'] > 0]
            df_geral['desconto_perc'] = ((df_geral['preco_base'] - df_geral['valor_proposto']) / df_geral['preco_base']) * 100

            st.sidebar.header("Filtros Temporais")
            anos_disponiveis = sorted(df_concursos['ano'].dropna().unique(), reverse=True)
            ano_selecionado = st.sidebar.selectbox("Selecionar Ano", ["Todos"] + [int(a) for a in anos_disponiveis])
            semestre_selecionado = st.sidebar.selectbox("Selecionar Semestre", ["Ano Completo", "1º Semestre", "2º Semestre"])

            if ano_selecionado != "Todos":
                df_concursos = df_concursos[df_concursos['ano'] == ano_selecionado]
                df_geral = df_geral[df_geral['ano'] == ano_selecionado]
            if semestre_selecionado != "Ano Completo":
                df_concursos = df_concursos[df_concursos['semestre'] == semestre_selecionado]
                df_geral = df_geral[df_geral['semestre'] == semestre_selecionado]

            tab_mercado, tab_regiao, tab_concorrencia, tab_precos, tab_future = st.tabs([
                "Unidade de Negócio", "Região", "Concorrência", "Preços", "Performance"
            ])

            with tab_mercado:
                st.subheader("Análise por Categoria de Unidade de Negócio")
                if not df_concursos.empty:
                    col1, col2 = st.columns(2)
                    stats_mercado = df_concursos.groupby('mercado').agg(
                        Num_Concursos=('id', 'count'),
                        Valor_Total_Base=('preco_base', 'sum')
                    ).reset_index()

                    with col1:
                        with st.container(border=True):
                            fig_m1 = px.pie(stats_mercado, values='Num_Concursos', names='mercado', hole=0.4, title="Distribuição de Concursos (Quantidade)", color_discrete_sequence=px.colors.qualitative.Prism)
                            st.plotly_chart(fig_m1, use_container_width=True)
                    with col2:
                        with st.container(border=True):
                            fig_m2 = px.pie(stats_mercado, values='Valor_Total_Base', names='mercado', hole=0.4, title="Distribuição de Concursos (Valor Base €)", color_discrete_sequence=px.colors.qualitative.Safe)
                            st.plotly_chart(fig_m2, use_container_width=True)
                else:
                    st.info("Sem dados de mercado para os filtros selecionados.")

            with tab_regiao:
                st.subheader("Análise por Região / Distrito")
                if not df_concursos.empty:
                    col_r1, col_r2 = st.columns(2)
                    stats_regiao = df_concursos.groupby('Regiao').agg(
                        Num_Concursos=('id', 'count'),
                        Valor_Total=('preco_base', 'sum')
                    ).reset_index().sort_values(by='Num_Concursos', ascending=False)

                    with col_r1:
                        with st.container(border=True):
                            fig_r1 = px.bar(stats_regiao, x='Regiao', y='Num_Concursos', title="Volume de Concursos por Região", color_discrete_sequence=['#0052CC'])
                            st.plotly_chart(fig_r1, use_container_width=True)
                    with col_r2:
                        with st.container(border=True):
                            st.markdown("**Tabela Detalhada por Região**")
                            tabela_r = stats_regiao.copy()
                            tabela_r['Valor_Total'] = tabela_r['Valor_Total'].apply(formatar_moeda)
                            tabela_r.columns = ['Região', 'Nº de Concursos', 'Valor Base Total']
                            st.dataframe(tabela_r, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem dados de região para os filtros selecionados.")

            with tab_concorrencia:
                st.subheader("Análise Global da Concorrência")
                df_comp = df_geral[df_geral['nome_empresa'].str.upper() != 'FUTURE'].copy()

                if not df_comp.empty:
                    stats_comp = df_comp.groupby('nome_empresa').agg(
                        Participacoes=('proposta_id', 'nunique') if 'proposta_id' in df_comp.columns else ('id_prop', 'count'),
                        Vitorias=('vencedor', 'sum'),
                        Desconto_Medio=('desconto_perc', 'mean')
                    ).reset_index()
                    stats_comp['Derrotas'] = stats_comp['Participacoes'] - stats_comp['Vitorias']

                    c1, c2 = st.columns(2)
                    with c1:
                        with st.container(border=True):
                            st.markdown("**Quem Aparece Mais (Nº Participações)**")
                            top_aparece = stats_comp.sort_values(by='Participacoes', ascending=False).head(5)
                            st.dataframe(top_aparece[['nome_empresa', 'Participacoes']].rename(columns={'nome_empresa': 'Empresa'}), hide_index=True, use_container_width=True)

                        with st.container(border=True):
                            st.markdown("**Quem Baixa Mais (Maior Desconto Médio %)**")
                            top_baixa = stats_comp.sort_values(by='Desconto_Medio', ascending=False).head(5).copy()
                            top_baixa['Desconto_Medio'] = top_baixa['Desconto_Medio'].map('{:.1f}%'.format)
                            st.dataframe(top_baixa[['nome_empresa', 'Desconto_Medio']].rename(columns={'nome_empresa': 'Empresa'}), hide_index=True, use_container_width=True)

                    with c2:
                        with st.container(border=True):
                            st.markdown("**Quem Ganha Mais (Nº Vitórias)**")
                            top_ganha = stats_comp.sort_values(by='Vitorias', ascending=False).head(5)
                            st.dataframe(top_ganha[['nome_empresa', 'Vitorias']].rename(columns={'nome_empresa': 'Empresa'}), hide_index=True, use_container_width=True)

                        with st.container(border=True):
                            st.markdown("**Quem Perde Mais (Nº Derrotas)**")
                            top_perde = stats_comp.sort_values(by='Derrotas', ascending=False).head(5)
                            st.dataframe(top_perde[['nome_empresa', 'Derrotas']].rename(columns={'nome_empresa': 'Empresa'}), hide_index=True, use_container_width=True)
                else:
                    st.info("Sem dados de concorrentes suficientes para o período selecionado.")

            with tab_precos:
                st.subheader("Comportamento de Preços e Descontos no Mercado")
                if not df_geral.empty:
                    desc_medio_global = df_geral['desconto_perc'].mean()

                    propostas_acima = len(df_geral[df_geral['desconto_perc'] < 0])
                    propostas_normais = len(df_geral[(df_geral['desconto_perc'] >= 0) & (df_geral['desconto_perc'] <= 40)])
                    propostas_anormais = len(df_geral[df_geral['desconto_perc'] > 40])

                    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                    col_p1.metric("Desconto Médio Global", f"{desc_medio_global:.1f}%" if pd.notna(desc_medio_global) else "N/A")
                    col_p2.metric("Propostas Acima do V.Base", propostas_acima, help="Desconto negativo (mais caro que a base).")
                    col_p3.metric("Descontos Normais (0 a 40%)", propostas_normais)
                    col_p4.metric("Anormalmente Baixos (>40%)", propostas_anormais, help="Descontos muito agressivos.")

                    st.markdown("<br>", unsafe_allow_html=True)
                    col_g1, col_g2 = st.columns(2)

                    with col_g1:
                        with st.container(border=True):
                            fig_hist = px.histogram(df_geral, x='desconto_perc', nbins=20, title="Distribuição dos Descontos Praticados (%)", labels={'desconto_perc': 'Desconto (%)', 'count': 'Nº de Propostas'}, color_discrete_sequence=['#FF991F'])
                            st.plotly_chart(fig_hist, use_container_width=True)

                    with col_g2:
                        with st.container(border=True):
                            agressividade = df_geral.groupby('ano')['desconto_perc'].mean().reset_index()
                            fig_agr = px.line(agressividade, x='ano', y='desconto_perc', markers=True, title="Evolução da Agressividade (Desconto Médio por Ano)", color_discrete_sequence=['#FF5630'])
                            fig_agr.update_layout(xaxis=dict(tickformat="d"))
                            st.plotly_chart(fig_agr, use_container_width=True)
                else:
                    st.info("Sem dados de preços suficientes.")

            with tab_future:
                st.subheader("Performance Interna (FUTURE)")
                df_future = df_geral[df_geral['nome_empresa'].str.upper() == 'FUTURE'].copy()

                if not df_future.empty:
                    total_part_fut = df_future['proposta_id'].nunique() if 'proposta_id' in df_future.columns else len(df_future)
                    vitorias_fut = df_future['vencedor'].sum()
                    taxa_suc_fut = (vitorias_fut / total_part_fut) * 100 if total_part_fut > 0 else 0

                    c_f1, c_f2, c_f3 = st.columns(3)
                    c_f1.metric("Nossa Taxa de Sucesso", f"{taxa_suc_fut:.1f}%")
                    c_f2.metric("Nº Vitórias (FUTURE)", int(vitorias_fut))
                    c_f3.metric("Nº Participações (FUTURE)", total_part_fut)

                    st.markdown("<br>", unsafe_allow_html=True)
                    col_fut1, col_fut2, col_fut3 = st.columns(3)

                    with col_fut1:
                        with st.container(border=True):
                            st.markdown("**Unidades de Negócio onde ganhamos mais**")
                            win_mercado = df_future[df_future['vencedor'] == True].groupby('mercado').size().reset_index(name='Vitórias').sort_values(by='Vitórias', ascending=False)
                            if not win_mercado.empty:
                                st.dataframe(win_mercado, use_container_width=True, hide_index=True)
                            else:
                                st.write("Sem vitórias registadas.")

                    with col_fut2:
                        with st.container(border=True):
                            st.markdown("**Clientes onde ganhamos mais**")
                            win_cli = df_future[df_future['vencedor'] == True].groupby('nome_cliente').size().reset_index(name='Vitórias').sort_values(by='Vitórias', ascending=False)
                            if not win_cli.empty:
                                st.dataframe(win_cli, use_container_width=True, hide_index=True)
                            else:
                                st.write("Sem vitórias registadas.")

                    with col_fut3:
                        with st.container(border=True):
                            st.markdown("**Escalões onde somos + competitivos**")
                            win_esc = df_future[df_future['vencedor'] == True].groupby('escalao').size().reset_index(name='Vitórias').sort_values(by='Vitórias', ascending=False)
                            if not win_esc.empty:
                                st.dataframe(win_esc, use_container_width=True, hide_index=True)
                            else:
                                st.write("Sem vitórias registadas.")
                else:
                    st.info("A FUTURE não tem propostas registadas neste período.")
    else:
        st.warning("Ainda não existem dados na base de dados para gerar estatísticas.")

except Exception as e:
    st.error(f"Erro ao gerar relatório global: {e}")
