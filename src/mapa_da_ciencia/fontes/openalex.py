"""Adaptador do OpenAlex: enriquece os documentos com citações, licença e, se faltar, o resumo.

O casamento de cada documento da ArticleMeta com um trabalho do OpenAlex segue uma cascata
(DOI → PID na URL → DOI derivado do PID → título+ano) e é **conferido**: o ano precisa bater
(±1), o título precisa ser parecido e cada trabalho só pode ser usado uma vez. A conferência
existe porque a própria ArticleMeta tem DOIs trocados (ADR 0003, adendo).

Custos (créditos do OpenAlex, 1.000 por dia sem chave): 1 por página de lista (até 200
trabalhos, inclusive a lista por DOIs, em lotes de 50), 10 por página de busca, 0 por trabalho
buscado no endereço direto `/works/doi:…`.

As listas por revista filtram por `locations.source.issn`, e não só pela location principal: o
OpenAlex às vezes elege um repositório (LA Referencia, por exemplo) como location principal de um
artigo de revista, e ele sumia da lista da revista (Novos Estudos, 2015–2018; ADR 0003, adendo).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.documento import (
    Afiliacao,
    AfiliacaoOpenAlex,
    Autor,
    AutoriaOpenAlex,
    Casamento,
    Documento,
    InstituicaoOpenAlex,
    Texto,
    mais_restritiva,
    normalizar_licenca,
)
from mapa_da_ciencia.fontes.articlemeta import RevistaRef
from mapa_da_ciencia.fontes.base import Buscador
from mapa_da_ciencia.texto import (
    limpar,
    normalizar_doi,
    normalizar_orcid,
    normalizar_titulo,
    remover_emails,
    similaridade_titulo,
)

URL = "https://api.openalex.org"
CAMPOS = (
    "id,doi,title,publication_year,language,type,primary_location,locations,"
    "abstract_inverted_index,cited_by_count,authorships,open_access,ids"
)
POR_PAGINA = 200
SIMILARIDADE_MINIMA = 0.6
TITULO_QUASE_IGUAL = 0.9  # aceita ano divergente (o OpenAlex tem anos errados: Novos Estudos 2025 → 2005)
TITULO_MINIMO = 20  # caracteres do título normalizado para confirmar sozinho um casamento com ano divergente
_PID_NA_URL = re.compile(r"pid=(S\d{4}-\d{3}[\dX]\d{13})", re.IGNORECASE)


def local_da_revista(obra: dict, issns: set[str] | frozenset[str] = frozenset()) -> dict:
    """A location do trabalho na revista: a que tem um dos `issns`, senão a primeira de uma revista,
    senão a principal. Quando a principal é um repositório, é aqui que estão a revista e a licença dela."""
    locais = obra.get("locations") or []
    for local in locais:
        if issns & set(((local.get("source") or {}).get("issn")) or []):
            return local
    principal = obra.get("primary_location") or {}
    if ((principal.get("source") or {}).get("type")) == "journal":
        return principal
    return next((lc for lc in locais if (lc.get("source") or {}).get("type") == "journal"), principal)


def licenca_da_obra(obra: dict, issns: set[str] | frozenset[str] = frozenset()) -> str | None:
    """A licença informada na location da revista; se ela não informar, a da location principal."""
    local = local_da_revista(obra, issns)
    principal = obra.get("primary_location") or {}
    return normalizar_licenca(local.get("license") or principal.get("license"))


def issns_da_obra(obra: dict) -> list[str]:
    """Todos os ISSNs das fontes onde o trabalho aparece, sem repetição."""
    locais = [obra.get("primary_location") or {}, *(obra.get("locations") or [])]
    return list(dict.fromkeys(i for lc in locais for i in ((lc.get("source") or {}).get("issn") or [])))


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
    maximo: int | None = None,
) -> list[dict]:
    """Todos os trabalhos de um filtro, página a página (cursor), com cache por página.

    Com `maximo`, confere o total na primeira página e para com uma mensagem se passar do limite.
    """
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
        total = (dados.get("meta") or {}).get("count") or 0
        if pagina == 0 and maximo is not None and total > maximo:
            paginas = -(-total // POR_PAGINA)
            raise ErroConfig(
                f"A busca encontrou {total} trabalhos no OpenAlex (~{paginas * custo_pagina} créditos). "
                f"O limite é {maximo}: refine a consulta, restrinja as revistas ou use anos mais estreitos."
            )
        trabalhos += resultados
        cursor = (dados.get("meta") or {}).get("next_cursor") if resultados else None
        pagina += 1
    return trabalhos


MAXIMO_BUSCA = 2000  # 10 páginas de busca = 100 créditos


async def consultar(
    buscador: Buscador,
    consulta: str,
    revistas: list[RevistaRef],
    anos: tuple[int, int],
    *,
    api_key: str | None = None,
) -> list[dict]:
    """Trabalhos cujo título ou resumo respondem à `consulta`, nas revistas dadas (ou em todo o SciELO).

    Busca custa 10 créditos por página de 200. Aceita a sintaxe do OpenAlex: aspas, AND, OR, NOT.
    """
    termo = " ".join(consulta.replace(",", " ").split())
    base = [f"title_and_abstract.search:{termo}", f"publication_year:{anos[0]}-{anos[1]}"]
    if not revistas:
        filtros = [",".join([*base, "primary_location.source.listed_in:scielo"])]
    else:
        issns = sorted({i for r in revistas for i in (r.issns or (r.issn,))})
        filtros = [
            ",".join([*base, "locations.source.issn:" + "|".join(issns[i : i + 100])])
            for i in range(0, len(issns), 100)
        ]
    obras: dict[str, dict] = {}
    for filtro in filtros:
        for o in await listar_paginas(
            buscador, filtro, "consultas/busca", api_key=api_key, custo_pagina=10, maximo=MAXIMO_BUSCA
        ):
            obras[o["id"]] = o
    return list(obras.values())


async def listar_por_revista(
    buscador: Buscador,
    revista: RevistaRef,
    anos: tuple[int, int],
    *,
    api_key: str | None = None,
    atualizar: bool = False,
) -> list[dict]:
    issns = "|".join(sorted(set(revista.issns or (revista.issn,))))
    filtro = f"locations.source.issn:{issns},publication_year:{anos[0]}-{anos[1]}"
    return await listar_paginas(
        buscador, filtro, f"revistas/{revista.prefixo_cache}", api_key=api_key, atualizar=atualizar
    )


async def buscar_por_dois(buscador: Buscador, dois: list[str], *, api_key: str | None = None) -> list[dict]:
    """Trabalhos do OpenAlex para uma lista de DOIs, em lotes de 50 (1 crédito por lote)."""
    unicos = sorted({d for d in dois if d})
    obras: list[dict] = []
    for i in range(0, len(unicos), 50):
        filtro = "doi:" + "|".join(unicos[i : i + 50])
        obras += await listar_paginas(buscador, filtro, "dois/lote", api_key=api_key)
    return obras


async def buscar_obra(buscador: Buscador, doi: str, *, api_key: str | None = None) -> dict | None:
    """Um trabalho pelo DOI, no endereço direto (`/works/doi:…`, sem custo em créditos), ou `None`.

    O endereço direto acha trabalhos que o filtro `doi:` ainda não acha (IDs novos, fora do índice de filtros).
    """
    params: dict[str, Any] = {"select": CAMPOS}
    if api_key:
        params["api_key"] = api_key
    return await buscador.json(
        "openalex",
        f"{URL}/works/doi:{doi}",
        params,
        f"openalex/obras/{_hash(doi, CAMPOS)}.json.gz",
        ausente_se_404=True,
    )


def pid_da_obra(obra: dict) -> str | None:
    """O PID do SciELO que o OpenAlex guarda nos endereços do trabalho, se houver."""
    for loc in obra.get("locations") or []:
        if m := _PID_NA_URL.search(loc.get("landing_page_url") or ""):
            return m.group(1).upper()
    return None


TIPOS_OPENALEX = {
    "article": "research-article",
    "review": "review-article",
    "preprint": "preprint",
    "editorial": "editorial",
    "letter": "letter",
    "erratum": "correction",
    "book-chapter": "book-chapter",
}


def _curto(url: str | None) -> str | None:
    """`https://openalex.org/I123` → `I123`; `https://ror.org/abc` → `abc`."""
    return url.rstrip("/").rsplit("/", 1)[-1] if url else None


def autorias_da_obra(obra: dict) -> list[AutoriaOpenAlex]:
    """Os autores da obra com as instituições e os textos de afiliação, sem e-mails, na ordem do OpenAlex."""
    saida = []
    for autoria in obra.get("authorships") or []:
        instituicoes = []
        for inst in autoria.get("institutions") or []:
            iid = _curto(inst.get("id"))
            if not iid:
                continue
            instituicoes.append(
                InstituicaoOpenAlex(
                    id=iid,
                    ror=_curto(inst.get("ror")),
                    nome=remover_emails(limpar(inst.get("display_name"))) or None,
                    pais=inst.get("country_code"),
                    tipo=inst.get("type"),
                    linhagem=[x for x in (_curto(u) for u in inst.get("lineage") or []) if x and x != iid],
                )
            )
        afiliacoes = [
            AfiliacaoOpenAlex(
                texto=texto, instituicoes=[x for x in (_curto(u) for u in f.get("institution_ids") or []) if x]
            )
            for f in autoria.get("affiliations") or []
            if (texto := remover_emails(limpar(f.get("raw_affiliation_string"))))
        ]
        if not afiliacoes:
            afiliacoes = [
                AfiliacaoOpenAlex(texto=texto)
                for bruto in autoria.get("raw_affiliation_strings") or []
                if (texto := remover_emails(limpar(bruto)))
            ]
        autor = autoria.get("author") or {}
        saida.append(
            AutoriaOpenAlex(
                nome=remover_emails(limpar(autor.get("display_name") or autoria.get("raw_author_name"))) or None,
                instituicoes=instituicoes,
                paises=list(autoria.get("countries") or []),
                afiliacoes=afiliacoes,
            )
        )
    return saida


def documento_de_obra(obra: dict, origem: str) -> Documento:
    """Documento montado só com o OpenAlex, para artigos importados que não estão na ArticleMeta."""
    oid = obra["id"].rsplit("/", 1)[-1]
    doi = normalizar_doi(obra.get("doi"))
    local = local_da_revista(obra)
    fonte = local.get("source") or {}
    licenca = licenca_da_obra(obra)
    autores, afiliacoes = [], []
    for i, autoria in enumerate(obra.get("authorships") or []):
        nome = remover_emails(limpar((autoria.get("author") or {}).get("display_name")))
        partes = nome.rsplit(" ", 1)
        ids_af = []
        for j, inst in enumerate(autoria.get("institutions") or []):
            ids_af.append(f"oa{i}-{j}")
            afiliacoes.append(
                Afiliacao(
                    id=f"oa{i}-{j}",
                    instituicao=remover_emails(limpar(inst.get("display_name"))) or None,
                    pais=inst.get("country_code"),
                    fonte="openalex",
                )
            )
        autores.append(
            Autor(
                nome=partes[0] if len(partes) == 2 else None,
                sobrenome=partes[-1] or None,
                orcid=normalizar_orcid((autoria.get("author") or {}).get("orcid")),
                afiliacoes=ids_af,
            )
        )
    resumo = reconstruir_resumo(obra.get("abstract_inverted_index"))
    titulo = limpar(obra.get("title"))
    return Documento(
        id=f"doi:{doi}" if doi else f"openalex:{oid}",
        doi=doi,
        openalex_id=oid,
        fonte="openalex",
        origens=[origem],
        tipo=TIPOS_OPENALEX.get(obra.get("type") or "", obra.get("type")),
        ano=int(obra.get("publication_year") or 0),
        idioma_original=obra.get("language"),
        revista_issn=(fonte.get("issn") or [None])[0],
        revista_titulo=fonte.get("display_name"),
        titulos=[Texto(idioma=obra.get("language"), texto=titulo, origem="openalex")] if titulo else [],
        resumos=[Texto(idioma=obra.get("language"), texto=resumo, origem="openalex")] if resumo else [],
        autores=autores,
        afiliacoes=afiliacoes,
        afiliacoes_fonte="openalex" if afiliacoes else "nenhuma",
        autorias_openalex=autorias_da_obra(obra),
        url=local.get("landing_page_url"),
        citacoes=obra.get("cited_by_count"),
        licenca=licenca or "desconhecida",
        licenca_fonte="openalex" if licenca else "nenhuma",
        licenca_openalex=licenca,
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
    """O trabalho do OpenAlex é mesmo este documento? Ano ±1 e título parecido em algum idioma.

    Com o ano fora da folga, só aceita título longo e praticamente igual: o identificador bateu e o
    título confirma, então o ano errado é do OpenAlex. Títulos curtos ("Apresentação") não confirmam nada.
    """
    ano = obra.get("publication_year")
    ano_confere = ano is None or abs(int(ano) - doc.ano) <= 1
    titulo = obra.get("title")
    if not titulo or not doc.titulos:
        return ano_confere  # sem título para comparar: fica com o que o identificador disse
    semelhanca = max(similaridade_titulo(t.texto, titulo) for t in doc.titulos)
    if ano_confere:
        return semelhanca >= SIMILARIDADE_MINIMA
    return semelhanca >= TITULO_QUASE_IGUAL and len(normalizar_titulo(titulo)) >= TITULO_MINIMO


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
    """Acrescenta ao documento o que o OpenAlex sabe: id, citações, licença e, se faltar, DOI, título e resumo."""
    if obra is None:
        return doc.model_copy(update={"casamento": passo})
    licenca_oa = licenca_da_obra(obra, {doc.revista_issn} if doc.revista_issn else frozenset())
    licenca, fonte = mais_restritiva(licenca_oa, doc.licenca_revista)
    mudancas: dict[str, Any] = {
        "openalex_id": obra["id"].rsplit("/", 1)[-1],
        "citacoes": obra.get("cited_by_count"),
        "licenca_openalex": licenca_oa,
        "licenca": licenca,
        "licenca_fonte": fonte,
        "casamento": passo,
        "doi": doc.doi or normalizar_doi(obra.get("doi")),
        "autorias_openalex": autorias_da_obra(obra),
    }
    if not doc.resumos and (resumo := reconstruir_resumo(obra.get("abstract_inverted_index"))):
        mudancas["resumos"] = [Texto(idioma=obra.get("language"), texto=resumo, origem="openalex")]
    if not doc.titulos and (titulo := limpar(obra.get("title"))):
        mudancas["titulos"] = [Texto(idioma=obra.get("language"), texto=titulo, origem="openalex")]
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
