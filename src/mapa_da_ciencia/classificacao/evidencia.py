"""Conferência da evidência: o trecho que o modelo copiou está mesmo no texto?

Cada evidência recebe um status:

- `literal`: o trecho está no resumo (ou no título), a menos de maiúsculas, espaços, aspas (que o modelo
  costuma tirar) e travessões;
- `aproximada`: pelo menos `PROPORCAO_APROXIMADA` dos caracteres do trecho casam, em blocos, com um pedaço do resumo
  de tamanho parecido (uma palavra trocada, uma vírgula a mais); o pedaço fica em volta do maior bloco em comum, para
  letras soltas espalhadas por um resumo longo não somarem um casamento; também quando o modelo cortou o trecho com
  reticências ("analisa as edições ... e O Mensageiro da Paz") e cada pedaço está no resumo;
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
FOLGA_APROXIMADA = 0.2  # quanto o pedaço do resumo pode ser maior (de cada lado) que o trecho
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
    # o pedaço do texto alinhado com o maior bloco em comum, com uma folga de cada lado
    maior = SequenceMatcher(None, normal, trecho, autojunk=False).find_longest_match(0, len(normal), 0, len(trecho))
    if not maior.size:
        return None
    folga = max(TAMANHO_MINIMO, int(len(trecho) * FOLGA_APROXIMADA))
    inicio = max(0, maior.a - maior.b - folga)
    pedaco = normal[inicio : maior.a - maior.b + len(trecho) + folga]
    blocos = [b for b in SequenceMatcher(None, pedaco, trecho, autojunk=False).get_matching_blocks() if b.size]
    casados = sum(b.size for b in blocos)
    a, b = inicio + blocos[0].a, inicio + blocos[-1].a + blocos[-1].size
    if casados / len(trecho) < PROPORCAO_APROXIMADA or b - a > len(trecho) * (1 + FOLGA_APROXIMADA):
        return None
    return "aproximada", posicoes[a], posicoes[b - 1] + 1


def _achar_pedacos(trecho: str, resumo: str, titulo: str | None) -> Conferencia | None:
    """Um trecho cortado com reticências: cada pedaço precisa estar no resumo ou no título. As posições vão do
    primeiro ao último pedaço achado no resumo."""
    pedacos = [p for p in (p.strip(_BORDAS) for p in trecho.split("...")) if len(p) >= TAMANHO_MINIMO]
    if len(pedacos) < 2:
        return None
    no_resumo = []
    for p in pedacos:
        achado = _achar(p, resumo)
        if achado:
            no_resumo.append(achado)
        elif not (titulo and _achar(p, titulo)):
            return None
    if not no_resumo:
        return Conferencia("aproximada", "titulo")
    return Conferencia("aproximada", "resumo", min(a[1] for a in no_resumo), max(a[2] for a in no_resumo))


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
    if pedacos := _achar_pedacos(trecho, resumo, titulo):
        return pedacos
    if no_titulo:
        return Conferencia("aproximada", "titulo")
    return Conferencia("ausente")
