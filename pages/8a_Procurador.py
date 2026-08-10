import streamlit as st
from utils.radar import carregar_anuncios, inferir_estado, calcular_score

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

anuncios = carregar_anuncios("data/anuncios2026.json")

palavras_chave = st.text_input("Palavras-chave (separadas por vírgula)", "seguros, hospitalar")
lista_palavras = [p.strip() for p in palavras_chave.split(",") if p.strip()]

resultados = []
for a in anuncios:
    estado = inferir_estado(a)
    if estado != "aberto":
        continue
    score = calcular_score(a, lista_palavras)
    if score > 0:
        resultados.append({**a, "estado": estado, "score": score})

resultados.sort(key=lambda x: x["score"], reverse=True)

st.write(f"{len(resultados)} concursos ativos relevantes")
st.dataframe(resultados)
