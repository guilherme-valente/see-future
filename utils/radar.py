import json
from datetime import date

def carregar_anuncios(path_json: str) -> list[dict]:
    with open(path_json, encoding="utf-8") as f:
        return json.load(f)

def inferir_estado(anuncio: dict) -> str | None:
    """Aproximação: se prazo ainda não passou, consideramos 'aberto'.
    Devolve None (não 'desconhecido') quando não é possível apurar,
    porque a constraint da tabela só aceita os 5 estados válidos ou NULL."""
    limite = anuncio.get("DataLimitePropostas")
    if not limite:
        return None
    dia, mes, ano = map(int, limite.split("/"))
    return "aberto" if date(ano, mes, dia) >= date.today() else "encerrado"

def calcular_score(anuncio: dict, palavras_chave: list[str]) -> int:
    texto = anuncio.get("descricaoAnuncio", "").lower()
    return sum(10 for p in palavras_chave if p.lower() in texto)
