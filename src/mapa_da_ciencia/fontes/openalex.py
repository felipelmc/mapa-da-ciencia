"""Adaptador do OpenAlex: enriquece os documentos com citações, licença e, se faltar, o resumo.

O casamento de cada documento da ArticleMeta com um trabalho do OpenAlex segue uma cascata
(DOI → PID na URL → DOI derivado do PID → título+ano) e é **conferido**: o ano precisa bater
(±1), o título precisa ser parecido e cada trabalho só pode ser usado uma vez. A conferência
existe porque a própria ArticleMeta tem DOIs trocados (ADR 0003, adendo).

Custos (créditos do OpenAlex, 1.000 por dia sem chave): 1 por página de lista (até 200
trabalhos), 10 por página de busca, 0 por trabalho buscado pelo DOI.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from mapa_da_ciencia.documento import Casamento, Documento, Texto, mais_restritiva, normalizar_licenca
from mapa_da_ciencia.fontes.articlemeta import RevistaRef
from mapa_da_ciencia.fontes.base import Buscador
from mapa_da_ciencia.texto import limpar, normalizar_doi, normalizar_titulo, similaridade_titulo

URL = "https://api.openalex.org"
CAMPOS = (
    "id,doi,title,publication_year,language,type,primary_location,locations,"
    "abstract_inverted_index,cited_by_count,authorships,open_access,ids"
)
POR_PAGINA = 200
SIMILARIDADE_MINIMA = 0.6
_PID_NA_URL = re.compile(r"pid=(S\d{4}-\d{3}[\dX]\d{13})", re.IGNORECASE)


def _hash(*partes: str) -> str:
    return hashlib.sha256("|".join(partes).encode()).hexdigest()[:8]


async def listar_paginas(
    buscador: Buscador,
    filtro: str,
    cache_prefixo: str,
    *,
    api_key: str | None = None,
    custo_pagina: int = 1,
    atualizar: bool = False,
) -> list[dict]:
    """Todos os trabalhos de um filtro, página a página (cursor), com cache por página."""
    trabalhos: list[dict] = []
    cursor, pagina = "*", 0
    chave = _hash(filtro, CAMPOS)
    while cursor:
        params: dict[str, Any] = {"filter": filtro, "select": CAMPOS, "per-page": POR_PAGINA, "cursor": cursor}
        if api_key:
            params["api_key"] = api_key
        dados = await buscador.json(
            "openalex",
            f"{URL}/works",
            params,
            f"openalex/{cache_prefixo}-{chave}-{pagina}.json.gz",
            atualizar=atualizar,
            custo=custo_pagina,
        )
        resultados = dados.get("results") or []
        trabalhos += resultados
        cursor = (dados.get("meta") or {}).get("next_cursor") if resultados else None
        pagina += 1
    return trabalhos


async def listar_por_revista(
    buscador: Buscador,
    revista: RevistaRef,
    anos: tuple[int, int],
    *,
    api_key: str | None = None,
    atualizar: bool = False,
) -> list[dict]:
    issns = "|".join(sorted(set(revista.issns or (revista.issn,))))
    filtro = f"primary_location.source.issn:{issns},publication_year:{anos[0]}-{anos[1]}"
    return await listar_paginas(
        buscador, filtro, f"revistas/{revista.prefixo_cache}", api_key=api_key, atualizar=atualizar
    )


# ---------------------------------------------------------------- casamento
@dataclass
class Indice:
    por_doi: dict[str, list[str]] = field(default_factory=dict)
    por_pid: dict[str, list[str]] = field(default_factory=dict)
    por_titulo_ano: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    obras: dict[str, dict] = field(default_factory=dict)


def indexar(obras: list[dict]) -> Indice:
    ind = Indice()
    for o in obras:
        oid = o.get("id")
        if not oid:
            continue
        ind.obras[oid] = o
        if doi := normalizar_doi(o.get("doi")):
            ind.por_doi.setdefault(doi, []).append(oid)
        for loc in o.get("locations") or []:
            if m := _PID_NA_URL.search(loc.get("landing_page_url") or ""):
                ind.por_pid.setdefault(m.group(1).upper(), []).append(oid)
        if o.get("title") and o.get("publication_year"):
            chave = (normalizar_titulo(o["title"]), int(o["publication_year"]))
            ind.por_titulo_ano.setdefault(chave, []).append(oid)
    return ind


def conferir(doc: Documento, obra: dict) -> bool:
    """O trabalho do OpenAlex é mesmo este documento? Ano ±1 e título parecido em algum idioma."""
    ano = obra.get("publication_year")
    if ano is not None and abs(int(ano) - doc.ano) > 1:
        return False
    titulo = obra.get("title")
    if not titulo or not doc.titulos:
        return True  # sem título para comparar: fica com o que o identificador disse
    return max(similaridade_titulo(t.texto, titulo) for t in doc.titulos) >= SIMILARIDADE_MINIMA


def casar(doc: Documento, indice: Indice, usados: set[str]) -> tuple[dict | None, Casamento]:
    """O trabalho do OpenAlex que corresponde ao documento, e o passo da cascata que o encontrou."""
    candidatos: list[tuple[Casamento, list[str]]] = []
    if doc.doi:
        candidatos.append(("1_doi", indice.por_doi.get(doc.doi, [])))
    if doc.pid:
        candidatos.append(("2_pid_url", indice.por_pid.get(doc.pid.upper(), [])))
        candidatos.append(("3_doi_derivado", indice.por_doi.get(f"10.1590/{doc.pid.lower()}", [])))
    for t in doc.titulos:
        candidatos.append(("4_titulo_ano", indice.por_titulo_ano.get((normalizar_titulo(t.texto), doc.ano), [])))
    for passo, ids in candidatos:
        for oid in ids:
            if oid in usados:
                continue
            obra = indice.obras[oid]
            if conferir(doc, obra):
                return obra, passo
    return None, "sem_casamento"


def reconstruir_resumo(indice_invertido: dict[str, list[int]] | None) -> str:
    """O OpenAlex guarda o resumo como índice invertido (palavra → posições). Remonta o texto."""
    if not indice_invertido:
        return ""
    posicoes = {pos: palavra for palavra, lista in indice_invertido.items() for pos in lista}
    return limpar(" ".join(posicoes[i] for i in sorted(posicoes)))


def enriquecer(doc: Documento, obra: dict | None, passo: Casamento) -> Documento:
    """Acrescenta ao documento o que o OpenAlex sabe: id, citações, licença e, se faltar, DOI e resumo."""
    if obra is None:
        return doc.model_copy(update={"casamento": passo})
    licenca_oa = normalizar_licenca((obra.get("primary_location") or {}).get("license"))
    licenca, fonte = mais_restritiva(licenca_oa, doc.licenca_revista)
    mudancas: dict[str, Any] = {
        "openalex_id": obra["id"].rsplit("/", 1)[-1],
        "citacoes": obra.get("cited_by_count"),
        "licenca_openalex": licenca_oa,
        "licenca": licenca,
        "licenca_fonte": fonte,
        "casamento": passo,
        "doi": doc.doi or normalizar_doi(obra.get("doi")),
    }
    if not doc.resumos and (resumo := reconstruir_resumo(obra.get("abstract_inverted_index"))):
        mudancas["resumos"] = [Texto(idioma=obra.get("language"), texto=resumo, origem="openalex")]
    return doc.model_copy(update=mudancas)


def casar_todos(documentos: list[Documento], obras: list[dict]) -> list[Documento]:
    """Casa cada documento (em ordem de id, para ser determinístico) e devolve os documentos enriquecidos."""
    indice = indexar(obras)
    usados: set[str] = set()
    saida = []
    for doc in sorted(documentos, key=lambda d: d.id):
        obra, passo = casar(doc, indice, usados)
        if obra is not None:
            usados.add(obra["id"])
        saida.append(enriquecer(doc, obra, passo))
    return saida
