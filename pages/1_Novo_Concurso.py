import streamlit as st
import pandas as pd
from supabase import create_client, Client

# 
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

st.set_page_config(page_title="Novo Concurso | See Future", layout="wide")
st.title("Adição de Novo Concurso na Plataforma")
st.divider()

# Injetar CSS para melhorar visualização
st.markdown(
    """<style>
    [data-testid="stSidebarNav"] a[href*="Avaliação"] { display: none !important; }
    [data-testid="stMetricLabel"] { font-size: 13px !important; white-space: normal !important; }
    [data-testid="stMetricValue"] { font-size: 22px !important; }
    </style>""", unsafe_allow_html=True
)

@st.cache_resource
def iniciar_ligacao():
    url = st.secrets["SUPABASE_URL"]
    chave = st.secrets["SUPABASE_KEY"]
    return create_client(url, chave)

supabase: Client = iniciar_ligacao()

with st.container(border=True):
    st.subheader("1. Dados Gerais do Concurso")
    col1, col2 = st.columns(2)
    
    with col1:
        referencia = st.text_input("Referência*")
        cliente_nome = st.text_input("Cliente (Entidade Adjudicante)*")
        distrito = st.selectbox("Região/Distrito", ["Lisboa", "Norte", "Centro", "Sul", "Outro"])
        mercado = st.selectbox("Mercado", ["Fiscalização", "Projeto", "Coordenação", "Construção"])
    
    with col2:
        preco_base = st.number_input("Preço Base (€)", min_value=0.0, step=1000.0)
        prazo_dias = st.number_input("Prazo (dias)", min_value=1, step=1)
        data_concurso = st.date_input("Data do Concurso")
        estado = st.selectbox("Estado do Concurso", ["Aberto", "Em Avaliação", "Fechado", "Adjudicado"], help="Se estiver Aberto, não será pedida a grelha de concorrentes.")

    st.markdown("##### Critério de Adjudicação")
    criterio = st.selectbox("Seleciona o Critério", ["Preço Mais Baixo", "Qualidade/Preço (Fatores Ponderados)"])
    
    ponderacao_final = "Preço Mais Baixo (100%)"
    soma_ponderacoes = 100
    pond_preco, pond_cvs, pond_metodologia, pond_afetacao = 100, 0, 0, 0
    
    if criterio == "Qualidade/Preço (Fatores Ponderados)":
        st.info("Defina as ponderações (soma deve ser 100%):")
        col_fat1, col_fat2, col_fat3, col_fat4 = st.columns(4)
        with col_fat1: pond_preco = st.slider("Preço (%)", 0, 100, 50, step=5)
        with col_fat2: pond_cvs = st.slider("Currículos (%)", 0, 100, 20, step=5)
        with col_fat3: pond_metodologia = st.slider("Metodologia (%)", 0, 100, 15, step=5)
        with col_fat4: pond_afetacao = st.slider("Afetação (%)", 0, 100, 15, step=5)
            
        soma_ponderacoes = pond_preco + pond_cvs + pond_metodologia + pond_afetacao
        if soma_ponderacoes != 100:
            st.warning(f"Atenção: A soma atual é de {soma_ponderacoes}%.")
        ponderacao_final = f"Preço: {pond_preco}% | CVs: {pond_cvs}% | Metodologia: {pond_metodologia}% | Afetação: {pond_afetacao}%"

st.divider()

# --- MAPEAMENTO DE CRITÉRIOS ATIVOS (ponderação > 0) ---
# Cada critério de pontuação só aparece na grelha se a sua ponderação for diferente de 0%
criterios_pontuacao_disponiveis = [
    {"coluna": "Pts CVs",         "campo_bd": "CVs",          "ponderacao": pond_cvs},
    {"coluna": "Pts Metodologia", "campo_bd": "Metodologia",  "ponderacao": pond_metodologia},
    {"coluna": "Pts Afetação",    "campo_bd": "Afetacao",     "ponderacao": pond_afetacao},
]
criterios_ativos = [c for c in criterios_pontuacao_disponiveis if c["ponderacao"] != 0]
usa_pts_preco = criterio == "Qualidade/Preço (Fatores Ponderados)" and pond_preco != 0

# --- GRELHA DINÂMICA DE PROPOSTAS ---
df_propostas_editado = pd.DataFrame()
data_adjudicacao = None

if estado == "Aberto":
    st.info("Como o concurso está Aberto, a fase de propostas ainda não terminou. Podes guardar os dados gerais agora e adicionar as propostas e pontuações mais tarde.")
else:
    with st.container(border=True):
        st.subheader("2. Grelha de Concorrentes e Pontuações")
        st.markdown("Preenche as propostas como se fosse um Excel. Clica no **+** em baixo para adicionar mais empresas concorrentes.")
        st.caption("Para propostas em consórcio/agrupamento, separa as empresas por ponto-e-vírgula, com o líder em primeiro lugar. Ex: 'Empresa A; Empresa B'")

        if criterio == "Qualidade/Preço (Fatores Ponderados)" and criterios_ativos:
            nomes_ativos = ", ".join(c["coluna"] for c in criterios_ativos)
            st.caption(f"Apenas os critérios com ponderação diferente de 0% aparecem na grelha: {nomes_ativos}.")

        if estado == "Adjudicado":
            data_adjudicacao = st.date_input("Data de Adjudicação")
        
        # --- CONSTRUÇÃO DINÂMICA DAS COLUNAS ---
        colunas_base = ["Empresa", "Valor Proposto (€)", "Classificação Final", "Vencedor?", "Desclassificado?"]
        linha_fut = {"Empresa": "FUTURE", "Valor Proposto (€)": 0.0, "Classificação Final": 0, "Vencedor?": False, "Desclassificado?": False}

        if criterio == "Qualidade/Preço (Fatores Ponderados)":
            if usa_pts_preco:
                colunas_base.append("Pts Preço")
                linha_fut["Pts Preço"] = 0.0
            for c in criterios_ativos:
                colunas_base.append(c["coluna"])
                linha_fut[c["coluna"]] = 0.0

        df_base = pd.DataFrame([linha_fut], columns=colunas_base)
        
        df_propostas_editado = st.data_editor(
            df_base, 
            num_rows="dynamic", 
            use_container_width=True,
            hide_index=True
        )

st.markdown("<br>", unsafe_allow_html=True)
submetido = st.button("Guardar Registo na Base de Dados", type="primary", use_container_width=True)

if submetido:
    if not referencia or not cliente_nome:
        st.error("A Referência e o Cliente são de preenchimento obrigatório.")
    elif criterio == "Qualidade/Preço (Fatores Ponderados)" and soma_ponderacoes != 100:
        st.error("Impossível guardar o concurso: as ponderações não somam 100%.")
    else:
        # --- ENGENHARIA DE PRÉ-VALIDAÇÃO (ANTI-GRAVAÇÃO FANTASMA) ---
        if estado != "Aberto" and not df_propostas_editado.empty:
            for indice, linha in df_propostas_editado.iterrows():
                nome_emp_raw = str(linha.get("Empresa", "")).strip().upper()
                if not nome_emp_raw or nome_emp_raw == "NAN" or nome_emp_raw == "":
                    continue
                
                is_desclassificado = bool(linha.get("Desclassificado?", False))
                valor_prop = linha.get("Valor Proposto (€)")
                
                if not is_desclassificado:
                    if pd.isna(valor_prop) or valor_prop is None or str(valor_prop).strip() == "":
                        st.error(f"Erro de Validação: A empresa '{nome_emp_raw}' tem o valor proposto em branco. Preencha a célula ou remova a linha.")
                        st.stop()

        try:
            # 1. Gerir Cliente
            resposta_cliente = supabase.table("clientes").select("id").eq("nome_cliente", cliente_nome).execute()
            if len(resposta_cliente.data) > 0:
                cliente_id = resposta_cliente.data[0]['id']
            else:
                novo_cliente = supabase.table("clientes").insert({"nome_cliente": cliente_nome}).execute()
                cliente_id = novo_cliente.data[0]['id']

            # 2. Guardar Concurso
            dados_concurso = {
                "referencia": referencia,
                "cliente_id": cliente_id,
                "distrito": distrito,
                "mercado": mercado,
                "preco_base": preco_base,
                "prazo_dias": prazo_dias,
                "data_concurso": str(data_concurso),
                "criterio_adjudicacao": ponderacao_final,
                "estado": estado
            }
            if estado == "Adjudicado" and data_adjudicacao:
                dados_concurso["data_adjudicacao"] = str(data_adjudicacao)

            novo_concurso = supabase.table("concursos").insert(dados_concurso).execute()
            concurso_id = novo_concurso.data[0]['id']

            # 3. Guardar Propostas (com suporte a consórcios) e Limpeza de Desclassificados
            if not df_propostas_editado.empty:
                df_propostas_editado["Desclassificado?"] = df_propostas_editado.get("Desclassificado?", pd.Series(dtype=bool)).fillna(False)
                df_propostas_editado["Vencedor?"] = df_propostas_editado.get("Vencedor?", pd.Series(dtype=bool)).fillna(False)

                for indice, linha in df_propostas_editado.iterrows():
                    nomes_empresas_raw = str(linha.get("Empresa", "")).strip()
                    if not nomes_empresas_raw or nomes_empresas_raw.upper() == "NAN":
                        continue

                    # --- SPLIT DE EMPRESAS EM CONSÓRCIO ---
                    nomes_lista = [n.strip().upper() for n in nomes_empresas_raw.split(";") if n.strip()]
                    if not nomes_lista:
                        continue

                    is_desclassificado = bool(linha.get("Desclassificado?", False))

                    # --- A MÁGICA DA LIMPEZA DAS PONTUAÇÕES ---
                    notas_json = None
                    classificacao = None
                    vencedor = False
                    valor_proposto = float(linha["Valor Proposto (€)"]) if pd.notna(linha["Valor Proposto (€)"]) else 0.0

                    if not is_desclassificado:
                        vencedor = bool(linha["Vencedor?"])
                        classificacao = int(linha["Classificação Final"]) if pd.notna(linha["Classificação Final"]) and linha["Classificação Final"] > 0 else None

                        if criterio == "Qualidade/Preço (Fatores Ponderados)":
                            notas_json = {}
                            if usa_pts_preco:
                                notas_json["Preco"] = float(linha.get("Pts Preço", 0)) if pd.notna(linha.get("Pts Preço", 0)) else 0.0
                            for c in criterios_ativos:
                                valor_pt = linha.get(c["coluna"], 0)
                                notas_json[c["campo_bd"]] = float(valor_pt) if pd.notna(valor_pt) else 0.0
                            # Se por algum motivo nenhum critério ficou ativo, não gravamos objeto vazio
                            if not notas_json:
                                notas_json = None
                    else:
                        valor_proposto = valor_proposto if valor_proposto > 0 else 0.0
                        # notas_json e classificacao ficam a None (NULL na BD)

                    # 1. Guardar a proposta (sem empresa_id direto — vai para a tabela de junção)
                    dados_proposta = {
                        "concurso_id": concurso_id,
                        "valor_proposto": valor_proposto,
                        "classificacao_final": classificacao,
                        "vencedor": vencedor,
                        "desclassificado": is_desclassificado,
                        "notas_criterios": notas_json,
                        "em_consorcio": len(nomes_lista) > 1
                    }
                    nova_proposta = supabase.table("propostas").insert(dados_proposta).execute()
                    proposta_id = nova_proposta.data[0]['id']

                    # 2. Guardar cada empresa do consórcio na tabela de junção
                    for posicao, nome_emp in enumerate(nomes_lista):
                        resp_emp = supabase.table("empresas").select("id").eq("nome_empresa", nome_emp).execute()
                        if len(resp_emp.data) > 0:
                            empresa_id = resp_emp.data[0]['id']
                        else:
                            nova_emp = supabase.table("empresas").insert({"nome_empresa": nome_emp}).execute()
                            empresa_id = nova_emp.data[0]['id']

                        papel = "individual" if len(nomes_lista) == 1 else ("lider" if posicao == 0 else "membro")
                        supabase.table("proposta_empresas").insert({
                            "proposta_id": proposta_id,
                            "empresa_id": empresa_id,
                            "papel": papel
                        }).execute()

            st.success(f"O concurso {referencia} foi registado com sucesso! Concorrentes desclassificados foram limpos automaticamente.")
            
        except Exception as e:
            st.error(f"Erro ao comunicar com a base de dados: {e}")