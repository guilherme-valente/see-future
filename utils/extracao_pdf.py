import io
import re
import requests
from pypdf import PdfReader

DISTRITOS_PT = [
    "Aveiro", "Beja", "Braga", "Bragança", "Castelo Branco", "Coimbra",
    "Évora", "Faro", "Guarda", "Leiria", "Lisboa", "Portalegre", "Porto",
    "Santarém", "Setúbal", "Viana do Castelo", "Vila Real", "Viseu",
    "Açores", "Madeira",
]


def extrair_texto_pdf(url: str) -> str:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    leitor = PdfReader(io.BytesIO(resp.content))
    return "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)


def extrair_peso_preco(texto: str) -> float | None:
    """Procura por algo como 'fator preço: 60%' ou 'preço, com a ponderação de 60%'."""
    padroes = [
        r"pre[çc]o.{0,40}?(\d{1,3})\s*%",
        r"(\d{1,3})\s*%.{0,40}?pre[çc]o",
    ]
    for padrao in padroes:
        m = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
        if m:
            valor = int(m.group(1))
            if 0 < valor <= 100:
                return valor
    return None


def extrair_limiar_anormal(texto: str) -> float | None:
    """Procura por 'preço anormalmente baixo' seguido de percentagem."""
    m = re.search(
        r"anormalmente baixo.{0,80}?(\d{1,3}(?:[.,]\d+)?)\s*%",
        texto, re.IGNORECASE | re.DOTALL
    )
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def extrair_distrito(texto: str) -> str | None:
    """Procura menções diretas a distritos no texto do anúncio."""
    for distrito in DISTRITOS_PT:
        if re.search(rf"\b{re.escape(distrito)}\b", texto, re.IGNORECASE):
            return distrito
    return None


def extrair_campos_do_anuncio(url: str) -> dict:
    """Ponto de entrada único: descarrega, extrai texto, aplica os 3 padrões.
    Nunca lança exceção — devolve campos a None em caso de falha."""
    resultado = {"peso_preco": None, "limiar_anormal": None, "distrito": None}
    try:
        texto = extrair_texto_pdf(url)
        resultado["peso_preco"] = extrair_peso_preco(texto)
        resultado["limiar_anormal"] = extrair_limiar_anormal(texto)
        resultado["distrito"] = extrair_distrito(texto)
    except Exception:
        pass
    return resultado
