import os
import requests
import tomllib
from pathlib import Path
from datetime import datetime
from supabase import create_client
from utils.radar import inferir_estado

URL_RECURSO = "https://dados.gov.pt/api/1/datasets/r/1002987e-8985-492f-9215-e732fffdbc83/"

def descarregar_anuncios() -> list[dict]:
    resp = requests.get(URL_RECURSO, timeout=180)
    resp.raise_for_status()
    return resp.json()

def get_client():
    url = os.environ.get("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def transformar(anuncio: dict) -> dict:
    dia, mes, ano = map(int, anuncio["dataPublicacao"].split("/"))
    return {
        "id_anuncio_base": anuncio["IdIncm"],
        "referencia_base": anuncio["nAnuncio"],
        "entidade_adjudicante": anuncio["designacaoEntidade"],
        "objeto_concurso": anuncio["descricaoAnuncio"],
        "link_base": anuncio.get("url"),
        "valor_base": float(anuncio["PrecoBase"]) if anuncio.get("PrecoBase") and anuncio["PrecoBase"] != "Inexistente" else None,
        "prazo_dias": anuncio.get("PrazoPropostas"),
        "data_publicacao": datetime(ano, mes, dia).date().isoformat(),
        "data_limite_propostas": anuncio.get("DataLimitePropostas") or None,
        "cpv": [c.split(" - ")[0] for c in anuncio.get("CPVs", [])],
        "estado_concurso_origem": inferir_estado(anuncio),
        "plataforma_origem": "diariodarepublica",
    }

def main():
    client = get_client()
    anuncios = descarregar_anuncios()
    registos = [transformar(a) for a in anuncios]
    client.table("radar_leads").upsert(registos, on_conflict="id_anuncio_base").execute()
    print(f"{len(registos)} leads processados.")

if __name__ == "__main__":
    main()
