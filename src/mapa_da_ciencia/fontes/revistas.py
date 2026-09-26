"""Retrato das revistas do SciELO Brasil, empacotado com o `mapa`.

Serve para montar recortes (`mapa revistas`), resolver acrônimos e ISSNs sem consultar a
API e descobrir a licença de cada revista. Gerado por `scripts/gerar_revistas.py` a partir
da ArticleMeta. Traz só as revistas **correntes**: as descontinuadas não aparecem na
listagem da API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources

from mapa_da_ciencia.texto import normalizar_titulo


@dataclass(frozen=True)
class Revista:
    """Uma revista corrente do SciELO Brasil, como aparece no retrato empacotado."""

    acronimo: str
    titulo: str
    titulo_abreviado: str | None
    issn: str
    issns: tuple[str, ...]
    areas: tuple[str, ...]
    categorias: tuple[str, ...]
    licenca: str | None
    editora: str | None
    uf: str | None


@dataclass(frozen=True)
class Retrato:
    colecao: str
    gerado_em: str
    revistas: tuple[Revista, ...]


@cache
def retrato() -> Retrato:
    dados = json.loads(resources.files("mapa_da_ciencia.fontes").joinpath("scielo-revistas.json").read_text("utf-8"))
    revistas = tuple(
        Revista(
            acronimo=r["acronimo"],
            titulo=r["titulo"],
            titulo_abreviado=r.get("titulo_abreviado"),
            issn=r["issn"],
            issns=tuple(dict.fromkeys([r["issn"], *(i["issn"] for i in r["issns"])])),
            areas=tuple(r["areas"]),
            categorias=tuple(r["categorias"]),
            licenca=r.get("licenca"),
            editora=r.get("editora"),
            uf=r.get("uf"),
        )
        for r in dados["revistas"]
    )
    return Retrato(dados["colecao"], dados["gerado_em"], revistas)


def por_issn(issn: str) -> Revista | None:
    """A revista com esse ISSN (impresso, online ou o usado pelo SciELO)."""
    issn = issn.strip().upper()
    return next((r for r in retrato().revistas if issn in r.issns), None)


def por_acronimo(acronimo: str) -> Revista | None:
    acronimo = acronimo.strip().lower()
    return next((r for r in retrato().revistas if r.acronimo == acronimo), None)


def resolver(identificador: str) -> Revista | None:
    """Aceita ISSN (`0104-6276`) ou acrônimo do SciELO (`op`)."""
    return por_issn(identificador) or por_acronimo(identificador)


def buscar(texto: str = "", area: str = "") -> list[Revista]:
    """Revistas cujo título, acrônimo, categoria ou ISSN contêm `texto` e cuja área contém `area` (sem acentos)."""
    alvo, area_n = normalizar_titulo(texto), normalizar_titulo(area)
    saida = []
    for r in retrato().revistas:
        campos = normalizar_titulo(" ".join([r.titulo, r.titulo_abreviado or "", r.acronimo, *r.categorias]))
        if alvo and alvo not in campos and texto.strip() not in r.issns:
            continue
        if area_n and not any(area_n in normalizar_titulo(a) for a in r.areas):
            continue
        saida.append(r)
    return sorted(saida, key=lambda r: normalizar_titulo(r.titulo))
