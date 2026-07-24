import streamlit as st

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

st.title("Avaliação de Rentabilidade")
st.markdown("Análise financeira e margem operacional do concurso.")
st.divider()
st.info("Espaço estrutural reservado. Aguardando a inserção das fórmulas analíticas de rentabilidade.")