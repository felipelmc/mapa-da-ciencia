"""A decisão do júri numa variável, a partir dos votos dos membros (funções puras, sem modelo nem disco).

Um **voto** é a resposta de um membro: o valor, a evidência e o status da conferência da evidência. A regra é a
maioria estrita (mais da metade dos membros), com uma condição: uma maioria que não é unânime só vale se ao menos um
dos votos dela trouxer evidência que não seja `ausente` (um valor sem trecho no texto que o sustente não desempata
nada). A unanimidade decide mesmo sem evidência: não há disputa para deliberar nem candidatos para o supervisor
escolher, e a decisão fica com o status `ausente`, que a auditoria pode sortear.

- `categorica` e `booleana`: compara o valor;
- `multipla`: categoria a categoria (entra a que a maioria estrita escolheu; um empate numa categoria deixa sem
  maioria), e a decisão só vale se algum membro deu exatamente esse conjunto;
- `texto`: compara a forma normalizada (sem maiúsculas, acentos, espaços e tipo de traço).

O resultado é uma **etapa**: `unanime` (todos iguais), `maioria` ou `sem_maioria`. A evidência da decisão é a do
voto da maioria com o melhor status (`literal` > `aproximada` > `dispensada`), e, no empate, a do primeiro membro na
ordem do júri. `candidatos` lista os valores distintos, cada um com o voto que melhor o sustenta: é o que o
supervisor vê quando não há maioria.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from ..config import Variavel
from ..validacao.metricas import normalizar_texto

Etapa = Literal["unanime", "maioria", "sem_maioria"]
ORDEM_STATUS = {"literal": 0, "aproximada": 1, "dispensada": 2, "ausente": 3}


@dataclass(frozen=True)
class Voto:
    membro: str
    valor: Any  # já normalizado pelo codebook: str, bool ou lista de categorias
    evidencia: str = ""
    status: str = "literal"
    campo: str | None = None
    inicio: int | None = None
    fim: int | None = None


@dataclass(frozen=True)
class Candidato:
    chave: str
    valor: Any
    voto: Voto  # o voto que melhor sustenta o valor
    membros: tuple[str, ...]


@dataclass(frozen=True)
class Decisao:
    etapa: Etapa
    valor: Any | None  # None quando sem maioria
    voto: Voto | None  # o voto cuja evidência representa a decisão
    candidatos: tuple[Candidato, ...] = field(default_factory=tuple)

    @property
    def decidida(self) -> bool:
        return self.etapa != "sem_maioria"


def chave(variavel: Variavel, valor: Any) -> str:
    """A forma do valor usada para comparar votos."""
    if variavel.tipo == "multipla":
        return json.dumps(sorted(set(valor or [])), ensure_ascii=False)
    if variavel.tipo == "booleana":
        return "true" if valor else "false"
    if variavel.tipo == "texto":
        return normalizar_texto(str(valor))
    return str(valor)


def _melhor(votos: list[Voto], ordem: dict[str, int]) -> Voto:
    return min(votos, key=lambda v: (ORDEM_STATUS.get(v.status, 9), ordem[v.membro]))


def candidatos(variavel: Variavel, votos: list[Voto]) -> tuple[Candidato, ...]:
    """Os valores distintos dos votos, em ordem de chave, cada um com o voto que melhor o sustenta."""
    ordem = {v.membro: i for i, v in enumerate(votos)}
    grupos: dict[str, list[Voto]] = {}
    for v in votos:
        grupos.setdefault(chave(variavel, v.valor), []).append(v)
    return tuple(
        Candidato(k, _melhor(g, ordem).valor, _melhor(g, ordem), tuple(v.membro for v in g))
        for k, g in sorted(grupos.items())
    )


def agregar(variavel: Variavel, votos: list[Voto]) -> Decisao:
    """A decisão do júri numa variável. `votos` vem na ordem dos membros (o primeiro preside)."""
    if not votos:
        return Decisao("sem_maioria", None, None)
    ordem = {v.membro: i for i, v in enumerate(votos)}
    n = len(votos)
    todos = candidatos(variavel, votos)
    if variavel.tipo == "multipla":
        contagem: dict[str, int] = {}
        for v in votos:
            for c in set(v.valor or []):
                contagem[c] = contagem.get(c, 0) + 1
        if any(2 * k == n for k in contagem.values()):  # empate numa categoria: sem maioria
            return Decisao("sem_maioria", None, None, todos)
        escolhidas = sorted(c for c, k in contagem.items() if 2 * k > n)
        vencedora = json.dumps(escolhidas, ensure_ascii=False)
    else:
        por_chave: dict[str, int] = {}
        for v in votos:
            k = chave(variavel, v.valor)
            por_chave[k] = por_chave.get(k, 0) + 1
        vencedora, k = max(por_chave.items(), key=lambda kv: kv[1])
        if 2 * k <= n:
            return Decisao("sem_maioria", None, None, todos)
    apoio = [v for v in votos if chave(variavel, v.valor) == vencedora]
    if not apoio:
        return Decisao("sem_maioria", None, None, todos)
    etapa: Etapa = "unanime" if len(apoio) == n else "maioria"
    if etapa == "maioria" and all(v.status == "ausente" for v in apoio):
        return Decisao("sem_maioria", None, None, todos)
    melhor = _melhor(apoio, ordem)
    return Decisao(etapa, melhor.valor, melhor, todos)
