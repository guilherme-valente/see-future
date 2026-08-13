import os
import time
import requests
import tomllib
from pathlib import Path
from datetime import datetime, date
from supabase import create_client
from utils.radar import inferir_estado

URL_RECURSO = "https://dados.gov.pt/api/1/datasets/r/1002987e-8985-492f-9215-e732fffdbc83/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def descarregar_anuncios(tentativas: int = 4, espera_inicial: int = 10) -> list[dict]:
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(URL_RECURSO, headers=HEADERS, timeout=180)
            if resp.status_code == 200:
                return resp.json()
            print(f"Tentativa {tentativa}/{tentativas}: status {resp.status_code}, a repetir...")
        except requests.exceptions.RequestException as e:
            print(f"Tentativa {tentativa}/{tentativas}: erro de rede ({e}), a repetir...")
            ultimo_erro = e

        if tentativa < tentativas:
            espera = espera_inicial * tentativa  # 10s, 20s, 30s...
            time.sleep(espera)

    raise RuntimeError(
        f"Não foi possível descarregar o ficheiro após {tentativas} tentativas. "
        f"Último erro: {ultimo_erro}"
    )

def carregar_credenciais() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key

    caminho = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    if caminho.exists():
        with open(caminho, "rb") as f:
            dados = tomllib.load(f)
        return dados["SUPABASE_URL"], dados["SUPABASE_KEY"]

    raise RuntimeError(
        "Credenciais não encontradas. Define SUPABASE_URL/SUPABASE_KEY como "
        "variáveis de ambiente ou cria .streamlit/secrets.toml"
    )

def get_client():
    url, key = carregar_credenciais()
    return create_client(url, key)

def converter_data(valor: str | None) -> str | None:
    if not valor:
        return None
    dia, mes, ano = map(int, valor.split("/"))
    return date(ano, mes, dia).isoformat()

def transformar(anuncio: dict) -> dict:
    return {
        "id_anuncio_base": anuncio["IdIncm"],
        "referencia_base": anuncio["nAnuncio"],
        "entidade_adjudicante": anuncio["designacaoEntidade"],
        "objeto_concurso": anuncio["descricaoAnuncio"],
        "link_base": anuncio.get("url"),
        "valor_base": float(anuncio["PrecoBase"]) if anuncio.get("PrecoBase") and anuncio["PrecoBase"] != "Inexistente" else None,
        "prazo_dias": anuncio.get("PrazoPropostas"),
        "data_publicacao": converter_data(anuncio.get("dataPublicacao")),
        "data_limite_propostas": converter_data(anuncio.get("DataLimitePropostas")),
        "cpv": [c.split(" - ")[0] for c in (anuncio.get("CPVs") or [])],
        "estado_concurso_origem": inferir_estado(anuncio),
        "plataforma_origem": "diariodarepublica",
    }

def main():
    client = get_client()
    anuncios = descarregar_anuncios()
    registos = [transformar(a) for a in anuncios]

    mais_recentes = {}
    for r in registos:
        chave = (r["referencia_base"], r["plataforma_origem"])
        anterior = mais_recentes.get(chave)
        if anterior is None or (r["data_publicacao"] or "") >= (anterior["data_publicacao"] or ""):
            mais_recentes[chave] = r

    registos_dedup = list(mais_recentes.values())

    client.table("radar_leads").upsert(
        registos_dedup, on_conflict="referencia_base,plataforma_origem"
    ).execute()

    print(f"{len(registos_dedup)} leads processados (de {len(registos)} anúncios brutos).")

if __name__ == "__main__":
    main()
