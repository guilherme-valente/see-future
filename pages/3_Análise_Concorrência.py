import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

st.set_page_config(page_title="Análise de Concorrência | See Future", layout="wide")
st.title("Análise de Concorrência")
st.markdown("Pesquisa por empresa para obter estatísticas detalhadas e histórico de confrontos diretos filtrados por período.")
st.divider()

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] a[href*="Avaliação"] { display: none !important; }
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
        return "N/A"
    try:
        return f"{float(valor):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "N/A"

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

        if 'desclassificado' not in df_propostas.columns:
            df_propostas['desclassificado'] = False
        else:
            df_propostas['desclassificado'] = df_propostas['desclassificado'].fillna(False).astype(bool)

        if df_propostas.empty:
            st.info("Não existem dados suficientes na base de dados para realizar a análise de concorrência.")
        else:
            df_geral = pd.merge(df_propostas, df_concursos, left_on='concurso_id', right_on='id', suffixes=('_prop', '_conc'))

            df_geral['data_concurso'] = pd.to_datetime(df_geral['data_concurso'], errors='coerce')
            df_geral = df_geral.dropna(subset=['data_concurso'])
            df_geral['ano'] = df_geral['data_concurso'].dt.year
            df_geral['mes'] = df_geral['data_concurso'].dt.month
            df_geral['semestre'] = df_geral['mes'].apply(lambda x: '1º Semestre' if x <= 6 else '2º Semestre')

            df_geral = df_geral[df_geral['preco_base'] > 0]
            df_geral['diferenca_base_perc'] = ((df_geral['preco_base'] - df_geral['valor_proposto']) / df_geral['preco_base']) * 100
            df_geral['escalao'] = df_geral['preco_base'].apply(definir_escalao)

            st.sidebar.header("Filtros Temporais")
            anos_disponiveis = sorted(df_geral['ano'].dropna().unique(), reverse=True)
            ano_selecionado = st.sidebar.selectbox("Selecionar Ano", ["Todos"] + [int(a) for a in anos_disponiveis])
            semestre_selecionado = st.sidebar.selectbox("Selecionar Semestre", ["Ano Completo", "1º Semestre", "2º Semestre"])

            df_geral_filtrado = df_geral.copy()
            if ano_selecionado != "Todos":
                df_geral_filtrado = df_geral_filtrado[df_geral_filtrado['ano'] == ano_selecionado]
            if semestre_selecionado != "Ano Completo":
                df_geral_filtrado = df_geral_filtrado[df_geral_filtrado['semestre'] == semestre_selecionado]

            lista_empresas = sorted([e for e in df_geral_filtrado['nome_empresa'].dropna().unique() if str(e).upper() != 'FUTURE'])

            st.subheader("Pesquisa por Empresa")
            empresa_alvo = st.selectbox("Selecione o Concorrente a analisar:", [""] + lista_empresas)

            if empresa_alvo:
                df_comp = df_geral_filtrado[df_geral_filtrado['nome_empresa'] == empresa_alvo].copy()
                df_future = df_geral_filtrado[df_geral_filtrado['nome_empresa'].str.upper() == 'FUTURE'].copy()

                # Dataframe sem desclassificados: usado para todas as médias/estatísticas
                # que não devem ser "contaminadas" por propostas excluídas do concurso.
                df_comp_validos = df_comp[~df_comp['desclassificado']].copy()

                df_confrontos = pd.merge(df_comp, df_future, on='concurso_id', suffixes=('_comp', '_fut'))
                # Confrontos válidos para efeitos de diferença média para a FUTURE:
                # exclui propostas do concorrente que foram desclassificadas.
                df_confrontos_validos_desc = df_confrontos[~df_confrontos['desclassificado_comp']].copy()

                num_participacoes_total = df_comp['proposta_id'].nunique() if 'proposta_id' in df_comp.columns else len(df_comp)
                num_participacoes_contra = df_confrontos['proposta_id_comp'].nunique() if 'proposta_id_comp' in df_confrontos.columns else len(df_confrontos)
                num_vitorias_contra = df_confrontos['vencedor_comp'].sum() if not df_confrontos.empty else 0

                # Estatísticas de valor/diferença: apenas propostas não desclassificadas
                valor_medio_proposto = df_comp_validos['valor_proposto'].mean()
                diferenca_media_base = df_comp_validos['diferenca_base_perc'].mean()

                num_desclassificacoes = df_comp['desclassificado'].sum()
                taxa_desclassificacao = (num_desclassificacoes / num_participacoes_total) * 100 if num_participacoes_total > 0 else 0.0

                diff_media_para_nos = 0.0
                if not df_confrontos_validos_desc.empty:
                    df_confrontos_validos = df_confrontos_validos_desc[df_confrontos_validos_desc['valor_proposto_fut'] > 0]
                    if not df_confrontos_validos.empty:
                        df_confrontos_validos['diff_para_fut'] = ((df_confrontos_validos['valor_proposto_comp'] - df_confrontos_validos['valor_proposto_fut']) / df_confrontos_validos['valor_proposto_fut']) * 100
                        diff_media_para_nos = df_confrontos_validos['diff_para_fut'].mean()

                # Classificação: apenas propostas não desclassificadas
                classificacoes_validas = df_comp_validos[df_comp_validos['classificacao_final'] > 0]['classificacao_final']
                class_media = classificacoes_validas.mean() if not classificacoes_validas.empty else 0
                class_melhor = classificacoes_validas.min() if not classificacoes_validas.empty else 0
                class_pior = classificacoes_validas.max() if not classificacoes_validas.empty else 0

                st.divider()

                periodo_label = f" ({ano_selecionado}" if ano_selecionado != "Todos" else " (Histórico Total"
                periodo_label += f" - {semestre_selecionado})" if semestre_selecionado != "Ano Completo" else ")"

                st.markdown(f"### Estatísticas Globais: **{empresa_alvo}**{periodo_label}")

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Participações contra nós", num_participacoes_contra)
                    c2.metric("Vitórias contra nós", num_vitorias_contra)
                    c3.metric("Valor Médio Proposto", formatar_moeda(valor_medio_proposto))
                    c4.metric("Diferença Média p/ Preço Base", f"{diferenca_media_base:.1f}%" if pd.notna(diferenca_media_base) else "N/A")

                    st.markdown("<br>", unsafe_allow_html=True)

                    c5, c6, c7, c8 = st.columns(4)
                    c5.metric("Classificação Média", f"{class_media:.1f}" if class_media > 0 else "N/A")
                    c6.metric("Melhor / Pior Lugar", f"{int(class_melhor)}º / {int(class_pior)}º" if class_melhor > 0 else "N/A")
                    sinal_diff = "+" if diff_media_para_nos > 0 else ""
                    c7.metric("Diferença Média para FUTURE", f"{sinal_diff}{diff_media_para_nos:.1f}%" if num_participacoes_contra > 0 else "N/A")
                    c8.metric("Desclassificações (Taxa)", f"{int(num_desclassificacoes)} ({taxa_desclassificacao:.1f}%)", help="Volume de exclusões em concursos e percentagem face ao total de propostas.")

                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("Distribuição do Concorrente por Categoria")

                col_dist1, col_dist2, col_dist3, col_dist4 = st.columns(4)

                with col_dist1:
                    with st.container(border=True):
                        st.markdown("**Segmentação por Unidade de Negócio**")
                        if not df_comp.empty and not df_comp['mercado'].dropna().empty:
                            dist_mercado = df_comp['mercado'].value_counts(normalize=True).reset_index()
                            dist_mercado.columns = ['Unidade de Negócio', 'Percentagem']
                            dist_mercado['Percentagem'] = (dist_mercado['Percentagem'] * 100).map('{:.1f}%'.format)
                            st.table(dist_mercado)
                        else:
                            st.info("Sem dados de Unidades de Negócio.")

                with col_dist2:
                    with st.container(border=True):
                        st.markdown("**Segmentação por Cliente**")
                        if not df_comp.empty and not df_comp['nome_cliente'].dropna().empty:
                            dist_cliente = df_comp['nome_cliente'].value_counts(normalize=True).reset_index()
                            dist_cliente.columns = ['Cliente', 'Percentagem']
                            dist_cliente['Percentagem'] = (dist_cliente['Percentagem'] * 100).map('{:.1f}%'.format)
                            st.table(dist_cliente)
                        else:
                            st.info("Sem dados de clientes.")

                with col_dist3:
                    with st.container(border=True):
                        st.markdown("**Segmentação por Região/Distrito**")
                        if not df_comp.empty and 'distrito' in df_comp.columns and not df_comp['distrito'].dropna().empty:
                            dist_distrito = df_comp['distrito'].value_counts(normalize=True).reset_index()
                            dist_distrito.columns = ['Distrito', 'Percentagem']
                            dist_distrito['Percentagem'] = (dist_distrito['Percentagem'] * 100).map('{:.1f}%'.format)
                            st.table(dist_distrito)
                        else:
                            st.info("Sem dados geográficos.")

                with col_dist4:
                    with st.container(border=True):
                        st.markdown("**Segmentação por País**")
                        if not df_comp.empty and 'pais' in df_comp.columns and not df_comp['pais'].dropna().empty:
                            dist_pais = df_comp['pais'].value_counts(normalize=True).reset_index()
                            dist_pais.columns = ['País', 'Percentagem']
                            dist_pais['Percentagem'] = (dist_pais['Percentagem'] * 100).map('{:.1f}%'.format)
                            st.table(dist_pais)
                        else: 
                            st.info("Sem dados geográficos.")
                        

                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("Análise por Escalão de Preço Base")

                if not df_comp.empty:
                    ordem_escaloes = ["< 50k€", "50k€ - 250k€", "250k€ - 500k€", "> 500k€"]
                    df_comp['escalao'] = pd.Categorical(df_comp['escalao'], categories=ordem_escaloes, ordered=True)

                    g_col1, g_col2 = st.columns(2)

                    with g_col1:
                        with st.container(border=True):
                            part_escalao = df_comp['escalao'].value_counts(normalize=True).reset_index()
                            part_escalao.columns = ['Escalão', 'Percentagem']
                            part_escalao['Percentagem'] = part_escalao['Percentagem'] * 100
                            fig1 = px.bar(part_escalao, x='Escalão', y='Percentagem', title="Distribuição de Participações por Escalão (%)", labels={'Percentagem': 'Participação (%)'}, color_discrete_sequence=['#0052CC'])
                            fig1.update_layout(yaxis=dict(ticksuffix="%"))
                            st.plotly_chart(fig1, use_container_width=True)

                    with g_col2:
                        with st.container(border=True):
                            desc_escalao = df_comp.groupby('escalao', observed=False)['diferenca_base_perc'].mean().reset_index()
                            desc_escalao.columns = ['Escalão', 'Diferença Média (%)']
                            fig2 = px.line(desc_escalao, x='Escalão', y='Diferença Média (%)', markers=True, title="Diferença Face ao Preço Base por Escalão (%)", color_discrete_sequence=['#FF991F'])
                            st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Não existem dados suficientes para gerar a análise por escalão para este período.")
    else:
        st.info("Não existem dados suficientes na base de dados para realizar a análise de concorrência.")

except Exception as e:
    st.error(f"Erro ao ligar à base de dados: {e}")
