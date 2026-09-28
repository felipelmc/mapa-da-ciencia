"""Quem é quem: as autorias do corpus agrupadas em pessoas.

Cada autoria (um autor num documento) junta o nome da ArticleMeta com a autoria do OpenAlex alinhada a ele (pela
posição e pelo sobrenome, como na geografia), de onde vêm o id do autor no OpenAlex e o ORCID. As autorias viram
pessoas num *union-find*, em ordem de confiança:

1. mesmo id do OpenAlex, ou mesmo ORCID — mas nunca juntando dois ORCIDs diferentes (o OpenAlex às vezes funde
   homônimos; o conflito fica registrado);
2. uma autoria sem id nem ORCID entra na pessoa com o mesmo nome, se houver exatamente uma;
3. duas pessoas com o mesmo nome e sem ORCIDs em conflito se juntam se tiverem um coautor em comum.

O resto dos homônimos vira `candidatos`, que `mapa redes --revisar` lista para o `pessoas.yaml` do projeto
(`fundir`, `nao_fundir`, `nomes`). O id interno de uma pessoa é o menor id do OpenAlex dela, senão o ORCID, senão o
nome; o id publicado é um *hash* curto dele (o site não publica ORCIDs).
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import ErroConfig
from ..documento import Documento
from ..geografia import normalizar
from ..geografia.casamento import alinhar

ARQUIVO_PESSOAS = "pessoas.yaml"
_PARTICULAS = {"de", "da", "do", "dos", "das", "e", "d"}


def chave_nome(nome: str | None) -> str:
    """Nome na forma de comparação: sem acentos, minúsculas, sem partículas."""
    return " ".join(p for p in normalizar.chave(nome or "").split() if p not in _PARTICULAS)


def id_publicado(interno: str) -> str:
    return "p" + hashlib.sha256(interno.encode("utf-8")).hexdigest()[:10]


@dataclass(frozen=True)
class Autoria:
    doc: str
    posicao: int
    nome: str
    openalex: str | None
    orcid: str | None

    @property
    def chave(self) -> str:
        return chave_nome(self.nome)


def autorias_do_corpus(documentos: list[Documento]) -> list[Autoria]:
    """Uma autoria por autor de cada documento, com o id do OpenAlex e o ORCID quando se sabe."""
    saida = []
    for d in documentos:
        if d.autores:
            pares = alinhar(d.autores, d.autorias_openalex) if d.autorias_openalex else {}
            for i, a in enumerate(d.autores):
                oa = d.autorias_openalex[pares[i]] if i in pares else None
                nome = " ".join(x for x in (a.nome, a.sobrenome) if x).strip() or (oa.nome if oa else "") or ""
                if not nome:
                    continue
                saida.append(Autoria(d.id, i, nome, oa.id if oa else None, a.orcid or (oa.orcid if oa else None)))
        else:
            for j, oa in enumerate(d.autorias_openalex):
                if oa.nome:
                    saida.append(Autoria(d.id, j, oa.nome, oa.id, oa.orcid))
    return saida


class CorrecoesPessoas(BaseModel):
    """O `pessoas.yaml` do projeto: correções manuais da identidade das pessoas."""

    model_config = ConfigDict(extra="forbid")
    fundir: list[list[str]] = Field(default_factory=list, description="Grupos de ids internos que são a mesma pessoa.")
    nao_fundir: list[list[str]] = Field(default_factory=list, description="Pares de ids que são pessoas diferentes.")
    nomes: dict[str, str] = Field(default_factory=dict, description="Id interno → nome a exibir.")


def ler_correcoes(raiz: Path) -> CorrecoesPessoas:
    arquivo = raiz / ARQUIVO_PESSOAS
    if not arquivo.exists():
        return CorrecoesPessoas()
    try:
        return CorrecoesPessoas.model_validate(yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {})
    except (yaml.YAMLError, ValidationError) as e:
        raise ErroConfig(f"{ARQUIVO_PESSOAS} tem um problema: {e}") from e


class _Grupos:
    """Union-find com o conjunto de ORCIDs de cada grupo (dois ORCIDs diferentes nunca se juntam)."""

    def __init__(self, n: int, orcids: list[str | None]) -> None:
        self.pai = list(range(n))
        self.orcids = [{o} if o else set() for o in orcids]

    def achar(self, i: int) -> int:
        while self.pai[i] != i:
            self.pai[i] = self.pai[self.pai[i]]
            i = self.pai[i]
        return i

    def unir(self, a: int, b: int, *, forcar: bool = False) -> bool:
        ra, rb = self.achar(a), self.achar(b)
        if ra == rb:
            return True
        if not forcar and len(self.orcids[ra] | self.orcids[rb]) > 1:
            return False
        ra, rb = min(ra, rb), max(ra, rb)
        self.pai[rb] = ra
        self.orcids[ra] |= self.orcids[rb]
        return True


@dataclass
class Pessoa:
    interno: str
    publicado: str
    nome: str
    autorias: list[int]  # índices em `Identidade.autorias`
    openalex: list[str]
    orcids: list[str]
    via: str  # openalex | orcid | nome


@dataclass
class Identidade:
    autorias: list[Autoria]
    pessoas: list[Pessoa]
    pessoa_da_autoria: list[int]  # autoria → índice da pessoa
    candidatos: list[tuple[str, str, str]] = field(default_factory=list)  # (id, id, nome em comum)
    conflitos: int = 0  # uniões recusadas por ORCIDs diferentes


def identificar(documentos: list[Documento], correcoes: CorrecoesPessoas | None = None) -> Identidade:
    correcoes = correcoes or CorrecoesPessoas()
    autorias = autorias_do_corpus(documentos)
    g = _Grupos(len(autorias), [a.orcid for a in autorias])
    conflitos = 0
    # 1. o mesmo id do OpenAlex e o mesmo ORCID
    for atributo in ("openalex", "orcid"):
        primeiro: dict[str, int] = {}
        for i, a in enumerate(autorias):
            valor = getattr(a, atributo)
            if not valor:
                continue
            if valor in primeiro:
                conflitos += not g.unir(primeiro[valor], i)
            else:
                primeiro[valor] = i
    # 2. sem id nem ORCID: a pessoa com o mesmo nome, se houver só uma
    por_nome: dict[str, set[int]] = defaultdict(set)
    for i, a in enumerate(autorias):
        if a.openalex or a.orcid:
            por_nome[a.chave].add(g.achar(i))
    for i, a in enumerate(autorias):
        if a.openalex or a.orcid or not a.chave:
            continue
        grupos = {g.achar(j) for j in por_nome.get(a.chave, set())}
        if len(grupos) == 1:
            g.unir(next(iter(grupos)), i)
        else:
            por_nome[a.chave].add(g.achar(i))
    # 3. homônimos com um coautor em comum
    docs_do_grupo: dict[int, set[str]] = defaultdict(set)
    for i, a in enumerate(autorias):
        docs_do_grupo[g.achar(i)].add(a.doc)
    grupos_do_doc: dict[str, set[int]] = defaultdict(set)
    for i, a in enumerate(autorias):
        grupos_do_doc[a.doc].add(g.achar(i))
    mudou = True
    while mudou:
        mudou = False
        por_chave: dict[str, set[int]] = defaultdict(set)
        for i, a in enumerate(autorias):
            if a.chave:
                por_chave[a.chave].add(g.achar(i))
        for grupos in por_chave.values():
            lista = sorted(grupos)
            for x in range(len(lista)):
                for y in range(x + 1, len(lista)):
                    ra, rb = g.achar(lista[x]), g.achar(lista[y])
                    if ra == rb:
                        continue
                    coautores_a = {h for d in docs_do_grupo[ra] for h in grupos_do_doc[d]} - {ra}
                    coautores_b = {h for d in docs_do_grupo[rb] for h in grupos_do_doc[d]} - {rb}
                    if {g.achar(h) for h in coautores_a} & {g.achar(h) for h in coautores_b} and g.unir(ra, rb):
                        raiz = g.achar(ra)
                        docs_do_grupo[raiz] = docs_do_grupo[ra] | docs_do_grupo[rb]
                        for d in docs_do_grupo[raiz]:
                            grupos_do_doc[d] = {g.achar(h) for h in grupos_do_doc[d]}
                        mudou = True
    pessoas, pessoa_da_autoria, candidatos = _montar(autorias, g, correcoes)
    return Identidade(autorias, pessoas, pessoa_da_autoria, candidatos, conflitos)


def _interno(membros: list[Autoria]) -> tuple[str, str]:
    ids = sorted({a.openalex for a in membros if a.openalex})
    if ids:
        return f"openalex:{ids[0]}", "openalex"
    orcids = sorted({a.orcid for a in membros if a.orcid})
    if orcids:
        return f"orcid:{orcids[0]}", "orcid"
    return f"nome:{membros[0].chave}", "nome"


def _internos(autorias: list[Autoria], grupos: dict[int, list[int]]) -> dict[int, tuple[str, str]]:
    """O id interno de cada grupo. Quando o OpenAlex fundiu pessoas com ORCIDs diferentes, o mesmo id do OpenAlex
    fica em mais de um grupo: aí o id vem do ORCID (ou do documento mais antigo), para continuar único."""
    internos = {raiz: _interno([autorias[i] for i in membros]) for raiz, membros in grupos.items()}
    repetidos = Counter(interno for interno, _ in internos.values())
    for raiz, (interno, via) in list(internos.items()):
        if repetidos[interno] > 1:
            membros = [autorias[i] for i in grupos[raiz]]
            orcids = sorted({a.orcid for a in membros if a.orcid})
            internos[raiz] = (
                (f"orcid:{orcids[0]}", "orcid") if orcids else (f"{interno}#{min(a.doc for a in membros)}", via)
            )
    return internos


def _montar(
    autorias: list[Autoria], g: _Grupos, correcoes: CorrecoesPessoas
) -> tuple[list[Pessoa], list[int], list[tuple[str, str, str]]]:
    grupos: dict[int, list[int]] = defaultdict(list)
    for i in range(len(autorias)):
        grupos[g.achar(i)].append(i)
    internos = _internos(autorias, grupos)
    antes = [internos[g.achar(i)][0] for i in range(len(autorias))]  # para `nomes` com um id de antes da fusão
    # correções manuais: `fundir` junta (mesmo com ORCIDs diferentes); `nao_fundir` só impede a sugestão
    raiz_do_interno = {interno: raiz for raiz, (interno, _) in internos.items()}
    for grupo in correcoes.fundir:
        raizes = [raiz_do_interno[x] for x in grupo if x in raiz_do_interno]
        for r in raizes[1:]:
            g.unir(raizes[0], r, forcar=True)
    if correcoes.fundir:
        grupos = defaultdict(list)
        for i in range(len(autorias)):
            grupos[g.achar(i)].append(i)
        internos = _internos(autorias, grupos)
    pessoas: list[Pessoa] = []
    pessoa_da_autoria = [0] * len(autorias)
    for raiz, membros in sorted(grupos.items(), key=lambda kv: internos[kv[0]][0]):
        interno, via = internos[raiz]
        nomes = Counter(autorias[i].nome for i in membros)
        ids = [interno, *sorted({antes[i] for i in membros})]
        manual = next((correcoes.nomes[x] for x in ids if x in correcoes.nomes), None)
        nome = manual or sorted(nomes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        for i in membros:
            pessoa_da_autoria[i] = len(pessoas)
        pessoas.append(
            Pessoa(
                interno,
                id_publicado(interno),
                nome,
                sorted(membros),
                sorted({autorias[i].openalex for i in membros if autorias[i].openalex}),
                sorted({autorias[i].orcid for i in membros if autorias[i].orcid}),
                via,
            )
        )
    nao = {frozenset(p) for p in correcoes.nao_fundir}
    por_chave: dict[str, list[Pessoa]] = defaultdict(list)
    for p in pessoas:
        por_chave[chave_nome(p.nome)].append(p)
    candidatos = [
        (a.interno, b.interno, a.nome)
        for grupo in por_chave.values()
        for x, a in enumerate(grupo)
        for b in grupo[x + 1 :]
        if frozenset((a.interno, b.interno)) not in nao
    ]
    return pessoas, pessoa_da_autoria, candidatos
