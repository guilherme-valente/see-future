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

st.set_page_config(page_title="Análise de Clientes | See Future", layout="wide")
st.title("Análise de Clientes (Entidades Adjudicantes)")
st.markdown("Avalie o comportamento, histórico de preços e concorrência direta em cada cliente.")
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
    elif valor < 150000: return "50k€ - 150k€"
    elif valor < 500000: return "150k€ - 500k€"
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

    if resp_concursos.data:
        df_concursos = pd.DataFrame(resp_concursos.data)
        df_propostas_raw = pd.DataFrame(resp_propostas.data) if resp_propostas.data else pd.DataFrame()
        df_propostas = explodir_propostas(df_propostas_raw)

        df_concursos['nome_cliente'] = df_concursos['clientes'].apply(lambda x: x.get('nome_cliente', 'Desconhecido') if isinstance(x, dict) else 'Desconhecido')
        df_concursos['escalao'] = df_concursos['preco_base'].apply(definir_escalao)

        df_concursos['data_concurso'] = pd.to_datetime(df_concursos['data_concurso'], errors='coerce')
        df_concursos = df_concursos.dropna(subset=['data_concurso'])
        df_concursos['ano'] = df_concursos['data_concurso'].dt.year
        df_concursos['mes'] = df_concursos['data_concurso'].dt.month
        df_concursos['semestre'] = df_concursos['mes'].apply(lambda x: '1º Semestre' if x <= 6 else '2º Semestre')

        st.sidebar.header("Filtros Temporais")
        anos_disponiveis = sorted(df_concursos['ano'].dropna().unique(), reverse=True)
        ano_selecionado = st.sidebar.selectbox("Selecionar Ano", ["Todos"] + [int(a) for a in anos_disponiveis])
        semestre_selecionado = st.sidebar.selectbox("Selecionar Semestre", ["Ano Completo", "1º Semestre", "2º Semestre"])

        df_conc_filtrado = df_concursos.copy()
        if ano_selecionado != "Todos":
            df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['ano'] == ano_selecionado]
        if semestre_selecionado != "Ano Completo":
            df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['semestre'] == semestre_selecionado]

        lista_clientes = sorted(df_conc_filtrado['nome_cliente'].dropna().unique())

        st.subheader("Pesquisa por Cliente")
        cliente_alvo = st.selectbox("Selecione o Cliente a analisar:", [""] + lista_clientes)

        if cliente_alvo:
            df_conc_alvo = df_conc_filtrado[df_conc_filtrado['nome_cliente'] == cliente_alvo].copy()

            df_prop_alvo = pd.DataFrame()
            prop_adversarios = pd.DataFrame()
            if not df_propostas.empty:
                df_prop_alvo = df_propostas[df_propostas['concurso_id'].isin(df_conc_alvo['id'])].copy()
                if not df_prop_alvo.empty:
                    df_prop_alvo = pd.merge(df_prop_alvo, df_conc_alvo[['id', 'preco_base', 'escalao']], left_on='concurso_id', right_on='id')
                    df_prop_alvo = df_prop_alvo[df_prop_alvo['preco_base'] > 0]
                    df_prop_alvo['diferenca_base_perc'] = ((df_prop_alvo['preco_base'] - df_prop_alvo['valor_proposto']) / df_prop_alvo['preco_base']) * 100

            num_concursos = len(df_conc_alvo)
            valor_medio_base = df_conc_alvo['preco_base'].mean()

            taxa_sucesso_nos = 0.0
            num_participacoes_nos = 0
            top_concorrente_nome = "N/A"

            if not df_prop_alvo.empty:
                prop_future = df_prop_alvo[df_prop_alvo['nome_empresa'].str.upper() == 'FUTURE']
                num_participacoes_nos = prop_future['proposta_id'].nunique() if 'proposta_id' in prop_future.columns else len(prop_future)
                if num_participacoes_nos > 0:
                    vitorias_future = prop_future['vencedor'].sum()
                    taxa_sucesso_nos = (vitorias_future / num_participacoes_nos) * 100

                prop_adversarios = df_prop_alvo[df_prop_alvo['nome_empresa'].str.upper() != 'FUTURE']
                if not prop_adversarios.empty:
                    top_concorrente_nome = prop_adversarios['nome_empresa'].value_counts().index[0]

            st.divider()

            periodo_label = f" ({ano_selecionado}" if ano_selecionado != "Todos" else " (Histórico Total"
            periodo_label += f" - {semestre_selecionado})" if semestre_selecionado != "Ano Completo" else ")"

            st.markdown(f"### Visão Global do Cliente: **{cliente_alvo}**{periodo_label}")

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Nº de Concursos Lançados", num_concursos)
                c2.metric("Valor Base Médio", formatar_moeda(valor_medio_base))
                c3.metric("Nossa Taxa de Sucesso", f"{taxa_sucesso_nos:.1f}%" if num_participacoes_nos > 0 else "Sem part.", help=f"Baseado em {num_participacoes_nos} participações da FUTURE.")
                c4.metric("Adversário Mais Frequente", top_concorrente_nome)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("Métricas por Escalão de Preço")

            if not df_prop_alvo.empty:
                ordem_escaloes = ["< 50k€", "50k€ - 150k€", "150k€ - 500k€", "> 500k€"]
                df_conc_alvo['escalao'] = pd.Categorical(df_conc_alvo['escalao'], categories=ordem_escaloes, ordered=True)
                df_prop_alvo['escalao'] = pd.Categorical(df_prop_alvo['escalao'], categories=ordem_escaloes, ordered=True)

                col_graf1, col_graf2 = st.columns(2)

                with col_graf1:
                    with st.container(border=True):
                        contagem_por_concurso = df_prop_alvo.groupby('concurso_id')['nome_empresa'].nunique().reset_index(name='num_concorrentes')
                        contagem_por_concurso = pd.merge(contagem_por_concurso, df_conc_alvo[['id', 'escalao']], left_on='concurso_id', right_on='id')
                        media_conc_escalao = contagem_por_concurso.groupby('escalao', observed=False)['num_concorrentes'].mean().reset_index()
                        media_conc_escalao.columns = ['Escalão', 'Nº Médio de Concorrentes']
                        fig1 = px.bar(media_conc_escalao, x='Escalão', y='Nº Médio de Concorrentes', title="Nº Médio de Concorrentes por Escalão", color_discrete_sequence=['#0052CC'])
                        st.plotly_chart(fig1, use_container_width=True)

                with col_graf2:
                    with st.container(border=True):
                        propostas_vencedoras = df_prop_alvo[df_prop_alvo['vencedor'] == True]
                        if not propostas_vencedoras.empty:
                            desc_venc_escalao = propostas_vencedoras.groupby('escalao', observed=False)['diferenca_base_perc'].mean().reset_index()
                            desc_venc_escalao.columns = ['Escalão', 'Desconto Vencedor (%)']
                            fig2 = px.line(desc_venc_escalao, x='Escalão', y='Desconto Vencedor (%)', markers=True, title="Desconto Médio do Vencedor por Escalão (%)", color_discrete_sequence=['#FF991F'])
                            st.plotly_chart(fig2, use_container_width=True)
                        else:
                            st.info("Sem dados de propostas vencedoras para calcular os descontos.")
            else:
                st.info("Não existem propostas registadas neste cliente para gerar os gráficos de escalão.")

            st.markdown("<br>", unsafe_allow_html=True)
            col_tab1, col_tab2 = st.columns(2)

            with col_tab1:
                with st.container(border=True):
                    st.markdown("**Top Concorrentes Mais Frequentes (Neste Cliente)**")
                    if not prop_adversarios.empty:
                        freq_concorrentes = prop_adversarios['nome_empresa'].value_counts().reset_index()
                        freq_concorrentes.columns = ['Empresa Concorrente', 'Nº de Participações']
                        st.dataframe(freq_concorrentes, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sem dados suficientes sobre concorrentes neste cliente.")

            with col_tab2:
                with st.container(border=True):
                    st.markdown("**Distribuição Geográfica de Obras (Distrito do Concurso)**")
                    if not df_conc_alvo.empty and 'distrito' in df_conc_alvo.columns and not df_conc_alvo['distrito'].dropna().empty:
                        freq_distritos = df_conc_alvo['distrito'].value_counts().reset_index()
                        freq_distritos.columns = ['Distrito da Obra', 'Volume de Concursos Lançados']
                        st.dataframe(freq_distritos, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sem dados geográficos registados para os concursos deste cliente.")
    else:
        st.info("Ainda não existem dados de concursos na plataforma.")

except Exception as e:
    st.error(f"Erro ao ligar à base de dados: {e}")