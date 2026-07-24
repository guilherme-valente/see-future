import streamlit as st
import bcrypt
from supabase import create_client, Client

# 1. Ligar à Base de Dados (usando a service_role do secrets.toml)
url = st.secrets["SUPABASE_URL"]
chave = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, chave)

# 2. Dados do Novo Administrador
nome = "Guilherme"
email = "admin@seefuture.pt"          # Podes alterar para o teu email real
password_texto = "admin123!"          # Podes (e deves) alterar para uma password forte

print("A iniciar processo de segurança...")

# 3. A Magia da Encriptação (Hashing)
# O algoritmo cria um 'salt' (um código aleatório) e mistura-o com a tua password
salt = bcrypt.gensalt()
password_hash = bcrypt.hashpw(password_texto.encode('utf-8'), salt).decode('utf-8')

try:
    # 4. Inserir de forma segura no Supabase
    resposta = supabase.table("utilizadores").insert({
        "email": email,
        "nome": nome,
        "password_hash": password_hash,
        "papel": "admin"
    }).execute()
    
    print("\nUtilizador Administrador criado com sucesso!")
    print(f"Nome: {nome}")
    print(f"Email: {email}")
    print(f"Hash gerado (o que a BD vê): {password_hash}")
    print("\nPodes agora apagar este ficheiro (criar_admin.py) por motivos de segurança.")

except Exception as e:
    print(f"\nOcorreu um erro ao criar o utilizador: {e}")