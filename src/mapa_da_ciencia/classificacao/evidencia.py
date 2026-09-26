"""Conferência da evidência: o trecho que o modelo copiou está mesmo no texto?

Cada evidência recebe um status:

- `literal`: o trecho está no resumo (ou no título), a menos de maiúsculas, espaços, aspas (que o modelo
  costuma tirar) e travessões;
- `aproximada`: pelo menos `PROPORCAO_APROXIMADA` dos caracteres do trecho casam, em blocos, com o resumo (uma
  palavra trocada, uma vírgula a mais);
- `ausente`: nenhum dos dois; o modelo parafraseou ou inventou;
- `dispensada`: evidência vazia numa resposta "sem informação" (ver `codebook.sem_informacao`), que não conta como
  falha.

Quando o trecho está no resumo, os *offsets* `[inicio, fim)` apontam para ele no resumo original (não no
normalizado), para a interface destacá-lo no texto que mostra.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

Status = Literal["literal", "aproximada", "ausente", "dispensada"]
PROPORCAO_APROXIMADA = 0.9
TAMANHO_MINIMO = 3  # menos que isso não é evidência

_TROCAS = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "`": "'",
                         "–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-", "…": "..."})  # fmt: skip
_BORDAS = " .,;:()[]"
_ASPAS = frozenset("\"'")


@dataclass(frozen=True)
class Conferencia:
    status: Status
    campo: Literal["resumo", "titulo"] | None = None
    inicio: int | None = None
    fim: int | None = None


def _normalizar(texto: str) -> tuple[str, list[int]]:
    """Texto normalizado e, para cada caractere dele, a posição no original."""
    saida: list[str] = []
    posicoes: list[int] = []
    for i, c in enumerate(texto):
        for d in unicodedata.normalize("NFKC", c).translate(_TROCAS).casefold():
            if d in _ASPAS:
                continue  # o modelo costuma tirar ou trocar as aspas do trecho que copia
            if d.isspace():
                if not saida or saida[-1] == " ":
                    continue
                d = " "
            saida.append(d)
            posicoes.append(i)
    while saida and saida[-1] == " ":
        saida.pop()
        posicoes.pop()
    return "".join(saida), posicoes


def _limpar(evidencia: str) -> str:
    return _normalizar(evidencia)[0].strip(_BORDAS)


def _achar(trecho: str, texto: str) -> tuple[Status, int, int] | None:
    """Status e posições (no original) do trecho no texto, ou None se ausente."""
    normal, posicoes = _normalizar(texto)
    if not normal:
        return None
    i = normal.find(trecho)
    if i >= 0:
        return "literal", posicoes[i], posicoes[i + len(trecho) - 1] + 1
    blocos = [b for b in SequenceMatcher(None, normal, trecho, autojunk=False).get_matching_blocks() if b.size]
    casados = sum(b.size for b in blocos)
    if casados / len(trecho) < PROPORCAO_APROXIMADA:
        return None
    return "aproximada", posicoes[blocos[0].a], posicoes[blocos[-1].a + blocos[-1].size - 1] + 1


def conferir(evidencia: str, resumo: str, titulo: str | None = None, *, sem_informacao: bool = False) -> Conferencia:
    """Onde a evidência está no resumo (ou no título) e com que fidelidade."""
    trecho = _limpar(evidencia)
    if len(trecho) < TAMANHO_MINIMO:
        return Conferencia("dispensada" if sem_informacao and not trecho else "ausente")
    no_resumo = _achar(trecho, resumo)
    if no_resumo and no_resumo[0] == "literal":
        return Conferencia("literal", "resumo", no_resumo[1], no_resumo[2])
    no_titulo = _achar(trecho, titulo) if titulo else None
    if no_titulo and no_titulo[0] == "literal":
        return Conferencia("literal", "titulo")
    if no_resumo:
        return Conferencia("aproximada", "resumo", no_resumo[1], no_resumo[2])
    if no_titulo:
        return Conferencia("aproximada", "titulo")
    return Conferencia("ausente")
