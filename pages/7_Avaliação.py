import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# --- TRANCAR A PÁGINA CONTRA ACESSOS DIRETOS ---
if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()
# -----------------------------------------------

st.set_page_config(page_title="Avaliação Estratégica | See Future", layout="wide")

# Inicializar o controlo da aba lateral
if 'aba_avaliacao' not in st.session_state:
    st.session_state['aba_avaliacao'] = 'Posicionamento'

# --- OCULTAR GESTÃO DE UTILIZADORES PARA NÃO ADMINS ---
papel_atual = str(st.session_state.get('papel_utilizador', '')).strip().lower()

css_admin = ""
if papel_atual != 'admin':
    css_admin = """
    [data-testid="stSidebarNav"] a[href*="Gestão_Utilizadores" i],
    [data-testid="stSidebarNav"] a[href*="Gest%C3%A3o_Utilizadores" i],
    [data-testid="stSidebarNav"] a[href*="Utilizadores" i] { display: none !important; }
    [data-testid="stSidebarNav"] li:has(a[href*="Gestão_Utilizadores" i]),
    [data-testid="stSidebarNav"] li:has(a[href*="Gest%C3%A3o_Utilizadores" i]),
    [data-testid="stSidebarNav"] li:has(a[href*="Utilizadores" i]) { display: none !important; }
    """

# Injetar CSS para formatar as métricas e manter segurança
st.markdown(
    f"""
    <style>
    /* Esconde a lista automática de páginas na barra lateral (mantém os botões manuais) */
    [data-testid="stSidebarNav"] {{ display: none !important; }}
    
    {css_admin}
    
    /* Formatação de Métricas IGUAL ao Laboratório */
    [data-testid="stMetricLabel"] {{
        font-size: 14px !important;
        white-space: normal !important;
        word-break: break-word !important;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 24px !important;
    }}
    
    /* Estilos dos cartões simulador */
    .sim-card {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }}
    .sim-value {{
        font-size: 26px;
        font-weight: bold;
        color: #1b365d;
    }}
    .sim-label {{
        font-size: 13px;
        color: #64748b;
        margin-top: 5px;
    }}
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
    if pd.isna(valor): return "0,00 €"
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def defining_escalao(valor):
    if valor < 50000: return "Micro (Até 50k€)"
    elif valor < 250000: return "Médio (50k€ a 250k€)"
    elif valor < 500000: return "Grande (250k€ a 500k€)"
    else: return "Especial (Superior a 500k€)"

try:
    supabase: Client = iniciar_ligacao()
    
    # Extração de dados históricos
    resp_concursos = supabase.table("concursos").select("*, clientes(nome_cliente)").execute()
    resp_propostas = supabase.table("propostas").select("*, empresas(nome_empresa)").execute()
    
    df_concursos = pd.DataFrame(resp_concursos.data) if resp_concursos.data else pd.DataFrame()
    df_propostas = pd.DataFrame(resp_propostas.data) if resp_propostas.data else pd.DataFrame()
    
    if not df_concursos.empty:
        df_concursos['nome_cliente'] = df_concursos['clientes'].apply(lambda x: x.get('nome_cliente', 'Desconhecido') if isinstance(x, dict) else 'Desconhecido')
        df_concursos['Regiao'] = df_concursos['distrito'].apply(lambda x: str(x) if pd.notna(x) else 'Não Definido')
        df_concursos['escalao'] = df_concursos['preco_base'].apply(defining_escalao) 
    
    if not df_propostas.empty:
        # Assegurar que os desclassificados estao booleanos
        if 'desclassificado' not in df_propostas.columns:
            df_propostas['desclassificado'] = False
        else:
            df_propostas['desclassificado'] = df_propostas['desclassificado'].fillna(False).astype(bool)
        df_propostas['nome_empresa'] = df_propostas['empresas'].apply(lambda x: x.get('nome_empresa', 'Desconhecida') if isinstance(x, dict) else 'Desconhecida')

    # --- MENU LATERAL EM FORMATO DE ABAS/BOTÕES ---
    with st.sidebar:
        st.header("Navegação")
        
        if st.button("⬅ Voltar ao Menu Principal", use_container_width=True):
            st.switch_page("Menu_Principal.py")
            
        st.divider()
        st.header("Módulos de Avaliação")
        
        # Botão Posicionamento (Destacado se ativo)
        tipo_pos = "primary" if st.session_state['aba_avaliacao'] == 'Posicionamento' else "secondary"
        if st.button("🎯 Posicionamento", type=tipo_pos, use_container_width=True):
            st.session_state['aba_avaliacao'] = 'Posicionamento'
            st.rerun()
            
        # Botão Rentabilidade (Destacado se ativo)
        tipo_rent = "primary" if st.session_state['aba_avaliacao'] == 'Rentabilidade' else "secondary"
        if st.button("📈 Rentabilidade", type=tipo_rent, use_container_width=True):
            st.session_state['aba_avaliacao'] = 'Rentabilidade'
            st.rerun()

    # ==========================================================
    # LÓGICA DE APRESENTAÇÃO
    # ==========================================================

    if st.session_state['aba_avaliacao'] == "Rentabilidade":
        st.title("Avaliação de Rentabilidade")
        st.markdown("Análise financeira e margem operacional do concurso.")
        st.divider()
        st.info("Espaço estrutural reservado. Aguardando a inserção das fórmulas analíticas de rentabilidade.")

    elif st.session_state['aba_avaliacao'] == "Posicionamento":
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
                    mercado_sel = st.selectbox("Unidade de Negócio", [
            "Infraestruturas de Transporte",
            "Sistema de Metro e Ferroviário",
            "Marítima e Portuária",
            "Água, Saneamento e Resíduos",
            "Cidades e Edifícios",
            "Sustentabilidade e Energia",
            "Real Estate",
            "Gestão e Supervisão da Construção",
            "GEOLAB"
        ])
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
            filtro_historico = df_concursos[
                (df_concursos['nome_cliente'] == cliente_sel) | 
                ((df_concursos['mercado'] == mercado_sel) & (df_concursos['distrito'] == distrito_sel))
            ]
            
            alpha_fiabilidade = 0.1
            desconto_medio_esperado = 0.08
            nota_tecnica_future = 85.0
            dados_tabela_concorrentes = []
            
            if not filtro_historico.empty:
                ids_concursos_filtrados = filtro_historico['id'].tolist()
                df_propostas_validas = df_propostas[(df_propostas['concurso_id'].isin(ids_concursos_filtrados)) & (df_propostas['desclassificado'] == False)].copy()
                
                # Calculo do factor alpha
                alpha_fiabilidade = min(1.0, 0.1 + (len(filtro_historico) * 0.15))
                
                if not df_propostas_validas.empty:
                    df_cruzado = pd.merge(df_propostas_validas, filtro_historico[['id', 'preco_base', 'escalao', 'mercado', 'distrito', 'nome_cliente']], left_on='concurso_id', right_on='id')
                    df_cruzado['desconto'] = (df_cruzado['preco_base'] - df_cruzado['valor_proposto']) / df_cruzado['preco_base']
                    media_desc = df_cruzado['desconto'].mean()
                    if pd.notna(media_desc):
                        desconto_medio_esperado = float(media_desc)
                    
                    # Nota tecnica historica FUTURE
                    df_future_historico = df_cruzado[df_cruzado['nome_empresa'].str.upper() == 'FUTURE']
                    notas_extraidas = []
                    for _, r in df_future_historico.iterrows():
                        n_json = r.get('notas_criterios')
                        if isinstance(n_json, dict):
                            soma_notas = n_json.get('CVs', 0) + n_json.get('Metodologia', 0) + n_json.get('Afetacao', 0)
                            if soma_notas > 0: notas_extraidas.append(soma_notas)
                    if notas_extraidas:
                        nota_tecnica_future = np.mean(notas_extraidas)
                    
                    # Geracao da Tabela de Concorrentes Prováveis
                    empresas_adversarias = df_cruzado[df_cruzado['nome_empresa'].str.upper() != 'FUTURE']
                    if not empresas_adversarias.empty:
                        total_concursos_contexto = df_cruzado['concurso_id'].nunique()
                        
                        for empresa, df_emp in empresas_adversarias.groupby('nome_empresa'):
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
                                "Probabilidade Participação": f"{prob_participacao:.1f}%",
                                "Desconto Estimado Face ao Base": f"{desc_medio_emp * 100:.1f}%",
                                "Diferença Estimada (Numerário)": formatar_moeda(valor_numerario_desconto),
                                "Ordem_Prob": prob_participacao
                            })
            
            # Ordenar tabela pelos mais provaveis e limpar coluna auxiliar
            if dados_tabela_concorrentes:
                dados_tabela_concorrentes = sorted(dados_tabela_concorrentes, key=lambda x: x["Ordem_Prob"], reverse=True)
                for item in dados_tabela_concorrentes:
                    del item["Ordem_Prob"]

            st.markdown("#### Indicadores Analíticos de Calibração")
            col_m1, col_m2, col_m3 = st.columns(3)
            
            with col_m1:
                st.metric(
                    label="Índice de Fiabilidade Analítica (alpha)", 
                    value=f"{alpha_fiabilidade * 100:.0f}%",
                    help="Representa a robustez estatística do cenário calculado. Baseado no volume de dados históricos encontrados na base de dados para o cliente e região selecionados. Quanto maior a amostra, mais próximo de 100% estará o indicador."
                )
            with col_m2:
                st.metric(
                    label="Preço Médio Estimado da Concorrência", 
                    value=formatar_moeda(preco_base_input * (1 - desconto_medio_esperado)),
                    help="Valor de proposta médio esperado. Resulta da aplicação da taxa média de desconto histórico praticada por concorrentes (neste cliente ou unidade de negócio) sobre o preço base actual do concurso."
                )
            with col_m3:
                st.metric(
                    label="Nota Técnica Esperada (FUTURE)", 
                    value=f"{nota_tecnica_future:.1f} Pts",
                    help="Média ponderada das classificações obtidas pela FUTURE em componentes não-financeiras (Metodologia, Currículos, etc) em concursos passados com características semelhantes."
                )

            st.divider()

            # --- TABELA DE CONCORRENTES ---
            st.markdown("#### Previsão de Participação e Comportamento da Concorrência")
            st.markdown(f"Índice de fiabilidade específico destas métricas concorrenciais: **{int(alpha_fiabilidade * 100)} / 100**")
            
            if dados_tabela_concorrentes:
                df_mostrar_concorrentes = pd.DataFrame(dados_tabela_concorrentes)
                st.dataframe(df_mostrar_concorrentes, use_container_width=True, hide_index=True)
            else:
                st.info("Não existem dados históricos suficientes para projetar concorrentes específicos.")

            st.divider()

            # --- SIMULADOR DE PROPOSTA ---
            st.markdown("#### Arena de Modelação Comercial de Preço")
            
            preco_future = st.slider(
                "Defina o Valor da Proposta Comercial da FUTURE (€)", 
                min_value=float(preco_base_input * 0.3), 
                max_value=float(preco_base_input * 1.0), 
                value=float(preco_base_input * 0.90), 
                step=500.0
            )

            # Validacao de Preco Anormalmente Baixo
            valor_limiar_critico = preco_base_input * (limiar_anormal / 100)
            
            if preco_future < valor_limiar_critico:
                st.error(f"Alerta de Exclusão: O preço simulado ({formatar_moeda(preco_future)}) situa-se abaixo do limiar de preço anormalmente baixo parametrizado ({limiar_anormal}% do valor base = {formatar_moeda(valor_limiar_critico)}). Risco de desclassificação direta.")
            
            # Motor probabilistico logistico
            preco_medio_conc = preco_base_input * (1 - desconto_medio_esperado)
            pontos_preco_fut = (preco_medio_conc / preco_future) * w_preco if preco_future > 0 else 0
            pontos_preco_conc = w_preco
            pontos_tec_fut = (nota_tecnica_future / 100) * w_tecnico
            pontos_tec_conc = 0.82 * w_tecnico
            
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
                    st.error("Posicionamento de Baixa Competitividade: Margem financeira excessivamente conservadora. O valor situa-se acima das médias agressivas operadas neste tipo de concurso.")
            
            with col_res2:
                cor_painel = "#ef4444" if preco_future < valor_limiar_critico else ("#22c55e" if prob_ponderada_final > 0.65 else "#eab308")
                valor_prob_exibir = 0.0 if preco_future < valor_limiar_critico else prob_ponderada_final * 100
                st.markdown(
                    f"<div style='text-align: center; border: 2px solid #e2e8f0; border-radius: 12px; padding: 15px;'>"
                    f"<div style='font-size: 14px; color: #64748b;'>Probabilidade de Sucesso Estimada</div>"
                    f"<div style='font-size: 40px; font-weight: 800; color: {cor_painel};'>{valor_prob_exibir:.1f}%</div>"
                    f"</div>", 
                    unsafe_allow_html=True
                )

except Exception as e:
    st.error(f"Erro na execução técnica do ambiente analítico: {e}")
