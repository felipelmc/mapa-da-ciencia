"""Limpeza e normalização de textos e identificadores vindos das fontes.

- Resumos da ArticleMeta trazem entidades HTML (às vezes duplamente escapadas, como
  `&amp;#8217;`), tags e prefixos como "Resumo:". A limpeza precisa ser estável, porque
  os offsets das evidências do M5 são calculados sobre o texto limpo.
- E-mails aparecem em vários campos das fontes e nunca podem chegar aos dados do projeto.
"""

from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

# E-mails, com as variações que aparecem em afiliações: espaço em volta do @ ou depois do ponto, e "[at]"/"(arroba)"
# e "[dot]"/"(ponto)" entre colchetes ou parênteses. O primeiro ramo é o padrão comum; os outros dois exigem o
# domínio final em minúsculas e só com letras, para não pegar "p @ 0.05" nem "o perfil @fulano. Em seguida".
_AT = r"(?:@|＠|﹫|[\[({][ \t]*(?:at|arroba)[ \t]*[\])}])"
_DOT = r"(?:\.|[ \t]*[\[({][ \t]*(?:dot|ponto)[ \t]*[\])}][ \t]*)"
EMAIL = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    rf"|[\w.+-]*\w[ \t]*{_AT}[ \t]*[\w-]+(?:{_DOT}[\w-]+)*{_DOT}(?-i:[a-z]{{2,24}})(?!\w)"
    r"|[\w.+-]*\w@[\w-]+(?:\. ?[\w-]+)*\. ?(?-i:[a-z]{2,24})(?!\w)",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")
_PREFIXO_RESUMO = re.compile(r"^\s*(resumo|abstract|resumen|résumé)\s*[:.\-–—]?\s+", re.IGNORECASE)
_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_ORCID = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.IGNORECASE)


def desescapar(texto: str) -> str:
    """Desfaz entidades HTML, inclusive as escapadas mais de uma vez (`&amp;#8217;` → `’`)."""
    for _ in range(3):
        novo = html.unescape(texto)
        if novo == texto:
            break
        texto = novo
    return texto


def limpar(texto: str | None, *, prefixo_resumo: bool = False) -> str:
    """Texto pronto para exibir e analisar: sem entidades, tags nem espaços sobrando, em NFC."""
    if not texto:
        return ""
    texto = desescapar(texto)
    texto = _TAG.sub(" ", texto)
    texto = unicodedata.normalize("NFC", texto)
    texto = _ESPACOS.sub(" ", texto).strip()
    if prefixo_resumo:
        texto = _PREFIXO_RESUMO.sub("", texto, count=1)
    return texto


def remover_emails(texto: str) -> str:
    """Tira endereços de e-mail de um texto (ex.: afiliações que trazem o e-mail no meio)."""
    return _ESPACOS.sub(" ", EMAIL.sub("", texto)).strip(" ,;")


def contem_email(valor: Any) -> bool:
    """Procura e-mails em qualquer estrutura JSON (usado na varredura final e nos testes)."""
    if isinstance(valor, str):
        return bool(EMAIL.search(valor))
    if isinstance(valor, dict):
        return any(contem_email(v) for v in valor.values())
    if isinstance(valor, list | tuple):
        return any(contem_email(v) for v in valor)
    return False


def normalizar_doi(doi: str | None) -> str | None:
    """`https://doi.org/10.1590/ABC` → `10.1590/abc`. Devolve `None` se não parecer um DOI."""
    if not doi:
        return None
    achado = _DOI.search(doi.strip())
    if not achado:
        return None
    return achado.group(0).rstrip(".,;)]").lower()


def normalizar_orcid(orcid: str | None) -> str | None:
    if not orcid:
        return None
    achado = _ORCID.search(orcid)
    return achado.group(1).upper() if achado else None


def normalizar_titulo(titulo: str | None) -> str:
    """Forma canônica para comparar títulos: sem acentos, minúsculas, só letras e números."""
    base = unicodedata.normalize("NFKD", desescapar(titulo or "")).encode("ascii", "ignore").decode().lower()
    return _ESPACOS.sub(" ", re.sub(r"[^a-z0-9]+", " ", base)).strip()


def similaridade_titulo(a: str | None, b: str | None) -> float:
    """Similaridade entre 0 e 1 de dois títulos, depois de normalizados."""
    na, nb = normalizar_titulo(a), normalizar_titulo(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb, autojunk=False).ratio()
