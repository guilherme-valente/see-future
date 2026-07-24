import streamlit as st
import pandas as pd
from supabase import create_client, Client

if 'autenticado' not in st.session_state or not st.session_state['autenticado']:
    st.error("Acesso negado. Por favor, inicie sessão na página inicial para aceder a este conteúdo.")
    st.stop()

with st.sidebar:
    if st.button("Voltar ao Menu Principal", use_container_width=True):
        st.session_state['modulo_ativo'] = 'menu'
        st.rerun()
    st.divider()

st.set_page_config(page_title="Consultar Concursos | See Future", layout="wide")
st.title("Consulta de Concursos na Base de Dados")
st.markdown("Pesquisa, explora, edita ou elimina os detalhes e propostas de cada concurso.")
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
        return "N/A"
    try:
        return f"{float(valor):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "N/A"

def safe_float(valor, default=0.0):
    try:
        if pd.isna(valor):
            return default
        return float(valor)
    except (ValueError, TypeError):
        return default

def safe_int_or_none(valor):
    try:
        if pd.isna(valor) or valor is None or str(valor).strip() == "":
            return None
        v = int(valor)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None

def explodir_propostas(df_propostas_raw):
    """Uma linha por (proposta, empresa). Devolve também 'nomes_todas_empresas' e 'label_concorrente'
    ao nível da proposta original, úteis para reconstruir o campo de edição em texto."""
    if df_propostas_raw is None or df_propostas_raw.empty:
        return pd.DataFrame()

    linhas = []
    for _, prop in df_propostas_raw.iterrows():
        base = prop.to_dict()
        lista_pe = base.pop('proposta_empresas', None)

        nomes_ordenados = []
        if isinstance(lista_pe, list) and len(lista_pe) > 0:
            lideres = [i for i in lista_pe if isinstance(i, dict) and i.get('papel') == 'lider']
            membros = [i for i in lista_pe if isinstance(i, dict) and i.get('papel') != 'lider']
            for item in lideres + membros:
                emp = item.get('empresas')
                nome_emp = emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
                nomes_ordenados.append(str(nome_emp).strip())

            for item in (lideres + membros):
                emp = item.get('empresas')
                nome_emp = emp.get('nome_empresa', 'Desconhecida') if isinstance(emp, dict) else 'Desconhecida'
                linha = dict(base)
                linha['nome_empresa'] = str(nome_emp).strip()
                linha['papel'] = item.get('papel', 'individual')
                linha['em_consorcio'] = len(lista_pe) > 1
                linha['label_concorrente'] = " + ".join(nomes_ordenados)
                linhas.append(linha)
        else:
            linha = dict(base)
            linha['nome_empresa'] = 'Desconhecida'
            linha['papel'] = None
            linha['em_consorcio'] = False
            linha['label_concorrente'] = 'Desconhecida'
            linhas.append(linha)

    return pd.DataFrame(linhas)

def guardar_proposta_com_empresas(supabase, concurso_id, nomes_empresas_raw, valor_proposto,
                                   classificacao_final, vencedor, desclassificado, notas_criterios):
    """Cria uma proposta e associa 1..N empresas (consórcio) via proposta_empresas.
    Devolve True se guardou com sucesso, False caso contrário (erros reportados via st.error)."""
    nomes_lista = [n.strip().upper() for n in str(nomes_empresas_raw).split(";") if n.strip()]
    if not nomes_lista:
        return False

    dados_proposta = {
        "concurso_id": concurso_id,
        "valor_proposto": valor_proposto,
        "classificacao_final": classificacao_final,
        "vencedor": vencedor,
        "desclassificado": desclassificado,
        "notas_criterios": notas_criterios,
        "em_consorcio": len(nomes_lista) > 1
    }

    try:
        nova_proposta = supabase.table("propostas").insert(dados_proposta).execute()
        if not nova_proposta.data:
            st.error(f"Falha ao gravar a proposta para '{nomes_empresas_raw}'.")
            return False
        proposta_id = nova_proposta.data[0]['id']
    except Exception as e:
        st.error(f"Erro ao gravar proposta '{nomes_empresas_raw}': {e}")
        return False

    for posicao, nome_emp in enumerate(nomes_lista):
        try:
            resp_emp = supabase.table("empresas").select("id").eq("nome_empresa", nome_emp).execute()
            if resp_emp.data and len(resp_emp.data) > 0:
                empresa_id = resp_emp.data[0]['id']
            else:
                nova_emp = supabase.table("empresas").insert({"nome_empresa": nome_emp}).execute()
                if not nova_emp.data:
                    st.error(f"Falha ao criar a empresa '{nome_emp}'.")
                    continue
                empresa_id = nova_emp.data[0]['id']

            papel = "individual" if len(nomes_lista) == 1 else ("lider" if posicao == 0 else "membro")
            supabase.table("proposta_empresas").insert({
                "proposta_id": proposta_id,
                "empresa_id": empresa_id,
                "papel": papel
            }).execute()
        except Exception as e:
            st.error(f"Erro ao associar a empresa '{nome_emp}' à proposta: {e}")

    return True

if 'editando' not in st.session_state:
    st.session_state.editando = False
if 'confirmar_delete' not in st.session_state:
    st.session_state.confirmar_delete = False
if 'ultimo_selecionado' not in st.session_state:
    st.session_state.ultimo_selecionado = ""

try:
    supabase: Client = iniciar_ligacao()

    resp_concursos = supabase.table("concursos").select("*, clientes(nome_cliente)").execute()
    resp_propostas = supabase.table("propostas").select(
        "*, proposta_empresas(papel, empresas(id, nome_empresa))"
    ).execute()

    if resp_concursos.data and len(resp_concursos.data) > 0:
        df_concursos = pd.DataFrame(resp_concursos.data)
        df_propostas_raw = pd.DataFrame(resp_propostas.data) if resp_propostas.data else pd.DataFrame()
        df_propostas = explodir_propostas(df_propostas_raw)

        df_concursos['data_concurso'] = pd.to_datetime(df_concursos['data_concurso'], errors='coerce').dt.date
        df_concursos = df_concursos.dropna(subset=['data_concurso'])
        df_concursos['Cliente'] = df_concursos['clientes'].apply(lambda x: x.get('nome_cliente', '') if isinstance(x, dict) else '')
        df_concursos['Distrito'] = df_concursos['distrito'].apply(lambda x: str(x) if pd.notna(x) else '')

        if not df_propostas.empty and 'proposta_id' in df_propostas.columns:
            contagem_concorrentes = df_propostas.groupby('concurso_id')['nome_empresa'].nunique().reset_index(name='Nº Concorrentes')
            df_concursos = pd.merge(df_concursos, contagem_concorrentes, left_on='id', right_on='concurso_id', how='left')
            df_concursos['Nº Concorrentes'] = df_concursos['Nº Concorrentes'].fillna(0).astype(int)
        else:
            df_concursos['Nº Concorrentes'] = 0

        data_minima = df_concursos['data_concurso'].min()
        data_maxima = df_concursos['data_concurso'].max()

        with st.expander("Abrir Filtros de Pesquisa", expanded=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                pesquisa_texto = st.text_input("Referência ou Cliente", placeholder="Escreva o termo de pesquisa...")
            with c2:
                filtro_mercado = st.multiselect("Unidade de Negócio", options=sorted(df_concursos['mercado'].dropna().unique()))
            with c3:
                distritos_limpos = [d for d in df_concursos['Distrito'].unique() if d]
                filtro_distrito = st.multiselect("Distrito", options=sorted(distritos_limpos))
            with c4:
                filtro_estado = st.multiselect("Estado", options=df_concursos['estado'].dropna().unique())
            with c5:
                filtro_datas = st.date_input("Intervalo de Datas", value=(data_minima, data_maxima))

        df_filtrado = df_concursos.copy()

        if pesquisa_texto:
            termo = pesquisa_texto.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado['referencia'].astype(str).str.lower().str.contains(termo, na=False) |
                df_filtrado['Cliente'].astype(str).str.lower().str.contains(termo, na=False)
            ]
        if filtro_mercado:
            df_filtrado = df_filtrado[df_filtrado['mercado'].isin(filtro_mercado)]
        if filtro_distrito:
            df_filtrado = df_filtrado[df_filtrado['Distrito'].isin(filtro_distrito)]
        if filtro_estado:
            df_filtrado = df_filtrado[df_filtrado['estado'].isin(filtro_estado)]

        if isinstance(filtro_datas, (tuple, list)) and len(filtro_datas) == 2:
            data_inicio, data_fim = filtro_datas
            df_filtrado = df_filtrado[(df_filtrado['data_concurso'] >= data_inicio) & (df_filtrado['data_concurso'] <= data_fim)]

        st.markdown(f"**Resultados Encontrados:** {len(df_filtrado)} concursos")

        if not df_filtrado.empty:
            df_resumo = df_filtrado[['referencia', 'Cliente', 'mercado', 'Distrito', 'preco_base', 'Nº Concorrentes', 'estado', 'data_concurso']].copy()
            df_resumo.columns = ['Referência', 'Cliente', 'Unidade de Negócio', 'Distrito', 'Preço Base (€)', 'Nº Concorrentes', 'Estado', 'Data']

            st.dataframe(df_resumo, use_container_width=True, hide_index=True)
            st.divider()

            st.subheader("Visualização Detalhada")

            opcoes_concursos = df_filtrado['referencia'].tolist()
            concurso_selecionado = st.selectbox("Selecione um concurso da lista acima para visualizar ou editar:", [""] + opcoes_concursos)

            if concurso_selecionado:
                if concurso_selecionado != st.session_state.ultimo_selecionado:
                    st.session_state.editando = False
                    st.session_state.confirmar_delete = False
                    st.session_state.ultimo_selecionado = concurso_selecionado

                dados_cc = df_filtrado[df_filtrado['referencia'] == concurso_selecionado].iloc[0]
                is_qualidade_preco = "CVs" in str(dados_cc['criterio_adjudicacao']) or "Metodologia" in str(dados_cc['criterio_adjudicacao'])

                # --- MODO DE EDIÇÃO ---
                if st.session_state.editando:
                    st.markdown("### Alterar Dados do Concurso")
                    with st.container(border=True):
                        col_ed1, col_ed2 = st.columns(2)
                        with col_ed1:
                            estados_possiveis = ["Aberto", "Em Avaliação", "Fechado", "Adjudicado"]
                            estado_atual = dados_cc['estado'] if dados_cc['estado'] in estados_possiveis else "Aberto"
                            novo_estado = st.selectbox("Alterar Estado", estados_possiveis, index=estados_possiveis.index(estado_atual))
                        with col_ed2:
                            if novo_estado == "Adjudicado":
                                data_adj_padrao = pd.to_datetime(dados_cc.get('data_adjudicacao')).date() if pd.notna(dados_cc.get('data_adjudicacao')) else dados_cc['data_concurso']
                                data_adjudicacao_ed = st.date_input("Data de Adjudicação", value=data_adj_padrao)
                            else:
                                data_adjudicacao_ed = None

                    st.caption("Para propostas em consórcio/agrupamento, separa as empresas por ponto-e-vírgula, com o líder em primeiro lugar. Ex: 'Empresa A; Empresa B'")

                    df_propostas_editado = pd.DataFrame()
                    if novo_estado != "Aberto":
                        st.markdown("#### Grelha de Propostas e Pontuações")
                        linhas_existentes = []
                        if not df_propostas.empty:
                            propostas_deste = df_propostas[df_propostas['concurso_id'] == dados_cc['id']].copy()
                            # Deduplicar por proposta_id, já que agora há várias linhas por proposta (consórcio)
                            if 'proposta_id' in propostas_deste.columns:
                                ids_unicos = propostas_deste['proposta_id'].unique()
                            else:
                                ids_unicos = propostas_deste.get('id', pd.Series(dtype=object)).unique()

                            chave_id = 'proposta_id' if 'proposta_id' in propostas_deste.columns else 'id'
                            for pid in ids_unicos:
                                linhas_prop = propostas_deste[propostas_deste[chave_id] == pid]
                                if linhas_prop.empty:
                                    continue
                                prop = linhas_prop.iloc[0]
                                label_empresa = prop.get('label_concorrente', 'Desconhecida')

                                notas = prop.get("notas_criterios") or {}
                                if not isinstance(notas, dict):
                                    notas = {}

                                item = {
                                    "Empresa": label_empresa,
                                    "Valor Proposto (€)": safe_float(prop.get("valor_proposto")),
                                    "Classificação Final": safe_int_or_none(prop.get("classificacao_final")) or 0,
                                    "Vencedor?": bool(prop.get("vencedor", False)),
                                    "Desclassificado?": bool(prop.get("desclassificado", False))
                                }
                                if is_qualidade_preco:
                                    item.update({
                                        "Pts Preço": safe_float(notas.get("Preco")),
                                        "Pts CVs": safe_float(notas.get("CVs")),
                                        "Pts Metodologia": safe_float(notas.get("Metodologia")),
                                        "Pts Afetação": safe_float(notas.get("Afetacao"))
                                    })
                                linhas_existentes.append(item)

                        if len(linhas_existentes) == 0:
                            linha_base = {"Empresa": "FUTURE", "Valor Proposto (€)": 0.0, "Classificação Final": 0, "Vencedor?": False, "Desclassificado?": False}
                            if is_qualidade_preco:
                                linha_base.update({"Pts Preço": 0.0, "Pts CVs": 0.0, "Pts Metodologia": 0.0, "Pts Afetação": 0.0})
                            df_editor_base = pd.DataFrame([linha_base])
                        else:
                            df_editor_base = pd.DataFrame(linhas_existentes)

                        df_propostas_editado = st.data_editor(df_editor_base, num_rows="dynamic", use_container_width=True, hide_index=True)

                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("Gravar Alterações", type="primary", use_container_width=True):
                            erro_validacao = False
                            if novo_estado != "Aberto" and not df_propostas_editado.empty:
                                for _, row in df_propostas_editado.iterrows():
                                    nome_emp_v = str(row.get("Empresa", "")).strip()
                                    if not nome_emp_v or nome_emp_v.upper() == "NAN":
                                        continue
                                    is_desc_v = bool(row.get("Desclassificado?", False))
                                    v_check = row.get("Valor Proposto (€)")
                                    if not is_desc_v and (pd.isna(v_check) or v_check is None or str(v_check).strip() == ""):
                                        st.error(f"Erro de Validação: A empresa/consórcio '{nome_emp_v}' tem o valor proposto em branco. Impossível salvar.")
                                        erro_validacao = True

                            if not erro_validacao:
                                try:
                                    df_propostas_editado["Desclassificado?"] = df_propostas_editado.get("Desclassificado?", pd.Series(dtype=bool)).fillna(False)
                                    df_propostas_editado["Vencedor?"] = df_propostas_editado.get("Vencedor?", pd.Series(dtype=bool)).fillna(False)
                                    concurso_id_limpo = int(dados_cc['id'])

                                    dados_update = {
                                        "estado": novo_estado,
                                        "data_adjudicacao": str(data_adjudicacao_ed) if novo_estado == "Adjudicado" and data_adjudicacao_ed else None
                                    }
                                    supabase.table("concursos").update(dados_update).eq("id", concurso_id_limpo).execute()

                                    # Apagar propostas antigas (proposta_empresas cai em cascata, conforme criado na BD)
                                    supabase.table("propostas").delete().eq("concurso_id", concurso_id_limpo).execute()

                                    if novo_estado != "Aberto" and not df_propostas_editado.empty:
                                        for _, row in df_propostas_editado.iterrows():
                                            nomes_raw = str(row.get("Empresa", "")).strip()
                                            if not nomes_raw or nomes_raw.upper() == "NAN":
                                                continue

                                            is_desc_row = bool(row.get("Desclassificado?", False))
                                            valor_prop_row = safe_float(row.get("Valor Proposto (€)"))

                                            if is_desc_row:
                                                vencedor_ed = False
                                                class_ed = None
                                                notas_ed = None
                                            else:
                                                vencedor_ed = bool(row.get("Vencedor?", False))
                                                class_ed = safe_int_or_none(row.get("Classificação Final"))
                                                if is_qualidade_preco:
                                                    notas_ed = {
                                                        "Preco": safe_float(row.get("Pts Preço")),
                                                        "CVs": safe_float(row.get("Pts CVs")),
                                                        "Metodologia": safe_float(row.get("Pts Metodologia")),
                                                        "Afetacao": safe_float(row.get("Pts Afetação"))
                                                    }
                                                else:
                                                    notas_ed = None

                                            guardar_proposta_com_empresas(
                                                supabase, concurso_id_limpo, nomes_raw, valor_prop_row,
                                                class_ed, vencedor_ed, is_desc_row, notas_ed
                                            )

                                    st.success("As alterações foram guardadas com sucesso!")
                                    st.session_state.editando = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao guardar alterações: {e}")
                    with col_b2:
                        if st.button("Cancelar", use_container_width=True):
                            st.session_state.editando = False
                            st.rerun()

                # --- MODO VISUALIZAÇÃO PADRÃO ---
                else:
                    with st.container(border=True):
                        st.markdown(f"### Ficha do Concurso: {dados_cc['referencia']}")
                        colA, colB, colC = st.columns(3)
                        with colA:
                            st.markdown(f"**Cliente:** {dados_cc['Cliente']}")
                            st.markdown(f"**Distrito:** {dados_cc['Distrito'] if dados_cc['Distrito'] else 'Não definido'}")
                            st.markdown(f"**Mercado:** {dados_cc['mercado']}")
                        with colB:
                            st.markdown(f"**Preço Base:** {formatar_moeda(dados_cc['preco_base'])}")
                            st.markdown(f"**Prazo:** {dados_cc['prazo_dias']} dias")
                            st.markdown(f"**Data:** {dados_cc['data_concurso']}")
                        with colC:
                            st.markdown(f"**Estado:** {dados_cc['estado']}")
                            st.markdown("**Critério de Adjudicação:**")
                            st.info(dados_cc['criterio_adjudicacao'])

                        if dados_cc['estado'] == "Aberto":
                            st.info("O concurso encontra-se em fase de Candidaturas/Aberto. Não existem propostas registadas.")
                        else:
                            if not df_propostas.empty:
                                propostas_deste = df_propostas[df_propostas['concurso_id'] == dados_cc['id']].copy()
                                chave_id = 'proposta_id' if 'proposta_id' in propostas_deste.columns else 'id'
                                # Uma linha por proposta (não por empresa), usando o label de consórcio
                                propostas_deduplicadas = propostas_deste.drop_duplicates(subset=[chave_id]) if chave_id in propostas_deste.columns else propostas_deste

                                if not propostas_deduplicadas.empty:
                                    st.markdown("#### Concorrentes e Propostas")
                                    propostas_deduplicadas['Vencedor'] = propostas_deduplicadas['vencedor'].apply(lambda x: "Sim" if x else "Não")
                                    propostas_deduplicadas['Desclassificado'] = propostas_deduplicadas['desclassificado'].apply(lambda x: "Sim" if x else "Não")
                                    propostas_deduplicadas['Empresa'] = propostas_deduplicadas.get('label_concorrente', propostas_deduplicadas.get('nome_empresa'))

                                    if is_qualidade_preco:
                                        propostas_deduplicadas['Pts Preço'] = propostas_deduplicadas['notas_criterios'].apply(lambda x: x.get('Preco', 0.0) if isinstance(x, dict) else 0.0)
                                        propostas_deduplicadas['Pts CVs'] = propostas_deduplicadas['notas_criterios'].apply(lambda x: x.get('CVs', 0.0) if isinstance(x, dict) else 0.0)
                                        propostas_deduplicadas['Pts Metodologia'] = propostas_deduplicadas['notas_criterios'].apply(lambda x: x.get('Metodologia', 0.0) if isinstance(x, dict) else 0.0)
                                        propostas_deduplicadas['Pts Afetação'] = propostas_deduplicadas['notas_criterios'].apply(lambda x: x.get('Afetacao', 0.0) if isinstance(x, dict) else 0.0)

                                        df_prop_mostrar = propostas_deduplicadas[['Empresa', 'valor_proposto', 'Pts Preço', 'Pts CVs', 'Pts Metodologia', 'Pts Afetação', 'classificacao_final', 'Vencedor', 'Desclassificado']].copy()
                                        df_prop_mostrar.columns = ['Empresa', 'Valor Proposto', 'Pts Preço', 'Pts CVs', 'Pts Metodologia', 'Pts Afetação', 'Classificação', 'Vencedor?', 'Desclassificado?']
                                    else:
                                        df_prop_mostrar = propostas_deduplicadas[['Empresa', 'valor_proposto', 'classificacao_final', 'Vencedor', 'Desclassificado']].copy()
                                        df_prop_mostrar.columns = ['Empresa', 'Valor Proposto', 'Classificação', 'Vencedor?', 'Desclassificado?']

                                    df_prop_mostrar = df_prop_mostrar.sort_values(by='Valor Proposto', ascending=True)
                                    st.dataframe(df_prop_mostrar, use_container_width=True, hide_index=True)
                                else:
                                    st.info("Ainda não existem propostas de concorrentes registadas para este concurso.")

                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("Editar Estado e Propostas", type="primary", use_container_width=True, on_click=lambda: setattr(st.session_state, 'editando', True))

                    # --- ZONA DE PERIGO ---
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.container(border=True):
                        st.subheader("Zona de Perigo")
                        if not st.session_state.confirmar_delete:
                            if st.button("Eliminar este Concurso", type="secondary", use_container_width=True):
                                st.session_state.confirmar_delete = True
                                st.rerun()
                        else:
                            st.warning("Aviso: Esta ação elimina o concurso, as propostas e vai limpar da base de dados quaisquer empresas ou clientes que fiquem sem histórico.")
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button("Sim, eliminar permanentemente", type="primary", use_container_width=True):
                                    try:
                                        concurso_id_apagar = int(dados_cc['id'])
                                        cliente_id_apagar = dados_cc.get('cliente_id')

                                        # Identificar empresas envolvidas via proposta_empresas, antes de apagar
                                        resp_props = supabase.table("propostas").select("id").eq("concurso_id", concurso_id_apagar).execute()
                                        propostas_ids = [p['id'] for p in resp_props.data] if resp_props.data else []

                                        empresas_envolvidas = set()
                                        if propostas_ids:
                                            resp_pe = supabase.table("proposta_empresas").select("empresa_id").in_("proposta_id", propostas_ids).execute()
                                            empresas_envolvidas = {p['empresa_id'] for p in resp_pe.data} if resp_pe.data else set()

                                        # A eliminação de propostas arrasta proposta_empresas em cascata
                                        supabase.table("propostas").delete().eq("concurso_id", concurso_id_apagar).execute()
                                        supabase.table("concursos").delete().eq("id", concurso_id_apagar).execute()

                                        if cliente_id_apagar is not None:
                                            restantes_cliente = supabase.table("concursos").select("id").eq("cliente_id", int(cliente_id_apagar)).execute()
                                            if not restantes_cliente.data:
                                                supabase.table("clientes").delete().eq("id", int(cliente_id_apagar)).execute()

                                        for emp_id in empresas_envolvidas:
                                            restantes_empresa = supabase.table("proposta_empresas").select("id").eq("empresa_id", emp_id).execute()
                                            if not restantes_empresa.data:
                                                info_empresa = supabase.table("empresas").select("nome_empresa").eq("id", emp_id).execute()
                                                if info_empresa.data and str(info_empresa.data[0]['nome_empresa']).upper() != 'FUTURE':
                                                    supabase.table("empresas").delete().eq("id", emp_id).execute()

                                        st.success("O concurso e os dados órfãos associados foram removidos com sucesso!")
                                        st.session_state.confirmar_delete = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao eliminar dados: {e}")
                            with col_no:
                                if st.button("Cancelar", use_container_width=True):
                                    st.session_state.confirmar_delete = False
                                    st.rerun()
        else:
            st.warning("Nenhum concurso corresponde aos filtros de pesquisa atuais.")
    else:
        st.info("Ainda não existem dados na base de dados para consultar.")

except Exception as e:
    st.error(f"Erro ao ligar à base de dados: {e}")