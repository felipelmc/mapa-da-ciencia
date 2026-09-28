"""Adaptador da ArticleMeta, a API de metadados do SciELO (fonte principal do corpus).

Duas particularidades moldam este módulo (ADR 0003):

- a API não filtra por ano de publicação (o `from/until` é a data de processamento), então
  listamos todos os PIDs da revista e filtramos pelo ano embutido no PID;
- o registro traz e-mails em vários campos (afiliações, registro da revista embutido,
  referências). A normalização copia só campos de uma **lista branca** e ainda passa uma
  varredura final que remove qualquer e-mail restante.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mapa_da_ciencia.documento import Afiliacao, Autor, Documento, Texto, mais_restritiva, normalizar_licenca
from mapa_da_ciencia.fontes import revistas
from mapa_da_ciencia.fontes.base import Buscador
from mapa_da_ciencia.fontes.revistas import Revista
from mapa_da_ciencia.texto import contem_email, limpar, normalizar_doi, normalizar_orcid, remover_emails

URL = "https://articlemeta.scielo.org/api/v1"
TAMANHO_PAGINA = 1000
# Chaves da v70 (afiliação) que podem ser copiadas: instituição, cidade, UF, país e divisões.
# Ficam de fora `e` (e-mail) e campos sem uso (`9`, `q`, `l`, `8`).
_DIVISOES_V70 = ("1", "2", "3", "4")


@dataclass
class ListaPids:
    pids: list[str]
    total_na_api: int
    repetidos: int = 0
    fora_do_periodo: int = 0
    dois: dict[str, str] = field(default_factory=dict)  # DOI → PID, de toda a revista (não só do período)

    @property
    def aviso(self) -> str | None:
        if self.repetidos:
            return (
                f"A listagem da ArticleMeta repetiu {self.repetidos} PID(s) entre páginas; "
                "a coleta usa cada PID uma vez só."
            )
        return None


@dataclass
class RevistaRef:
    """O que a coleta precisa saber de uma revista (vem do retrato empacotado)."""

    issn: str
    acronimo: str
    titulo: str
    licenca: str | None = None
    colecao: str = "scl"
    issns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def de_revista(cls, r: Revista, colecao: str = "scl") -> RevistaRef:
        return cls(r.issn, r.acronimo, r.titulo, r.licenca, colecao, r.issns)

    @property
    def prefixo_cache(self) -> str:
        return self.acronimo if self.colecao == "scl" else f"{self.colecao}-{self.acronimo}"


def revista_do_registro(registro: dict, colecao: str | None = None) -> RevistaRef:
    """A revista de um artigo a partir do próprio registro. Serve para revistas fora do retrato do SciELO
    Brasil, como as de outras coleções (Argentina, Colômbia...) que chegam por importação."""
    colecao = colecao or registro.get("collection") or "scl"
    titulo = registro.get("title") or {}

    def primeiro(campo: str) -> str | None:
        valores = titulo.get(campo) or []
        return valores[0].get("_") if valores else None

    pid = registro.get("code") or ""
    issn = primeiro("v400") or pid[1:10]
    if colecao == "scl" and (conhecida := revistas.por_issn(issn)):
        return RevistaRef.de_revista(conhecida)
    issns = tuple(dict.fromkeys([issn, *(x.get("_") for x in titulo.get("v435") or [] if x.get("_"))]))
    return RevistaRef(
        issn=issn,
        acronimo=primeiro("v68") or issn,
        titulo=primeiro("v100") or issn,
        licenca=primeiro("v541"),
        colecao=colecao,
        issns=issns,
    )


def ano_do_pid(pid: str) -> int | None:
    """`S0104-62762024000100200` → 2024. O ano ocupa as posições 10 a 13 do PID."""
    trecho = pid[10:14]
    return int(trecho) if trecho.isdigit() else None


async def listar_pids(
    buscador: Buscador, revista: RevistaRef, anos: tuple[int, int], *, atualizar: bool = False
) -> ListaPids:
    """Todos os PIDs da revista publicados no período, sem repetição."""
    objetos: list[dict] = []
    offset, total = 0, 0
    while True:
        dados = await buscador.json(
            "articlemeta",
            f"{URL}/article/identifiers/",
            {"collection": revista.colecao, "issn": revista.issn, "limit": TAMANHO_PAGINA, "offset": offset},
            f"articlemeta/identificadores/{revista.prefixo_cache}-{offset}.json.gz",
            atualizar=atualizar,
        )
        objetos += dados.get("objects") or []
        total = int((dados.get("meta") or {}).get("total") or 0)
        offset += TAMANHO_PAGINA
        if offset >= total or not dados.get("objects"):
            break
    codigos = [o["code"] for o in objetos if o.get("code")]
    unicos = sorted(set(codigos))
    no_periodo = [p for p in unicos if (a := ano_do_pid(p)) is not None and anos[0] <= a <= anos[1]]
    return ListaPids(
        pids=no_periodo,
        total_na_api=total,
        repetidos=len(codigos) - len(unicos),
        fora_do_periodo=len(unicos) - len(no_periodo),
        dois={doi: o["code"] for o in objetos if o.get("code") and (doi := normalizar_doi(o.get("doi")))},
    )


async def buscar_registros(
    buscador: Buscador,
    pids: list[str],
    colecao: str = "scl",
    *,
    ao_avancar: Callable[[str], None] | None = None,
    tratar: Callable[[str, dict], Any] | None = None,
) -> dict[str, Any]:
    """O registro de cada PID (ou `None` se a API não o conhece). Usa o cache e grava cada um ao chegar.

    Com `tratar(pid, registro)`, guarda o que ela devolver no lugar do registro, que é descartado assim que
    chega. Os registros brutos são grandes (a lista de referências ocupa ~90%): no piloto, guardar todos até
    o fim levava a coleta a ~2,6 GB de memória.
    """

    async def um(pid: str) -> tuple[str, Any]:
        registro = await buscador.json(
            "articlemeta",
            f"{URL}/article/",
            {"collection": colecao, "code": pid, "format": "json"},
            f"articlemeta/artigos/{pid}.json.gz",
        )
        if ao_avancar:
            ao_avancar(pid)
        if tratar is not None and registro is not None:
            return pid, tratar(pid, registro)
        return pid, registro

    return dict(await asyncio.gather(*(um(p) for p in pids)))


# ---------------------------------------------------------------- normalização
def _textos(itens: list[dict] | None, chave: str, *, resumo: bool = False) -> list[Texto]:
    """Títulos ou resumos: um por idioma (o primeiro que aparecer)."""
    vistos: dict[str | None, Texto] = {}
    for item in itens or []:
        texto = limpar(item.get(chave), prefixo_resumo=resumo)
        idioma = (item.get("l") or "").lower() or None
        if texto and idioma not in vistos:
            vistos[idioma] = Texto(idioma=idioma, texto=texto)
    return list(vistos.values())


def _palavras_chave(itens: list[dict] | None) -> list[Texto]:
    """Palavras-chave: várias por idioma, sem repetição."""
    vistas: dict[tuple[str | None, str], Texto] = {}
    for item in itens or []:
        texto = limpar(item.get("k"))
        idioma = (item.get("l") or "").lower() or None
        if texto and (idioma, texto.lower()) not in vistas:
            vistas[(idioma, texto.lower())] = Texto(idioma=idioma, texto=texto)
    return list(vistas.values())


def _limpo(valor: str | None) -> str | None:
    texto = remover_emails(limpar(valor)) if valor else ""
    return texto or None


def _afiliacoes(artigo: dict) -> tuple[list[Afiliacao], str]:
    v240 = artigo.get("v240") or []
    v70 = artigo.get("v70") or []
    saida: list[Afiliacao] = []
    for a in v240:
        saida.append(
            Afiliacao(
                id=a.get("i"),
                instituicao=_limpo(a.get("_")),
                cidade=_limpo(a.get("c")),
                uf=_limpo(a.get("s")),
                pais=_limpo(a.get("p")),
                fonte="v240",
            )
        )
    ids_v240 = {a.id for a in saida if a.id}
    # A v240 às vezes não cobre todas as afiliações: completa com a v70 as que faltarem.
    for a in v70:
        if a.get("i") and a.get("i") in ids_v240:
            continue
        saida.append(
            Afiliacao(
                id=a.get("i"),
                instituicao=_limpo(a.get("_")),
                divisoes=[d for k in _DIVISOES_V70 if (d := _limpo(a.get(k)))],
                cidade=_limpo(a.get("c")),
                uf=_limpo(a.get("s")),
                pais=_limpo(a.get("p")),
                fonte="v70",
            )
        )
    fonte = "v240" if v240 else ("v70" if v70 else "nenhuma")
    return saida, fonte


def _autores(artigo: dict) -> list[Autor]:
    return [
        Autor(
            nome=_limpo(a.get("n")),
            sobrenome=_limpo(a.get("s")),
            orcid=normalizar_orcid(a.get("k")),
            afiliacoes=(a.get("1") or "").split(),
        )
        for a in artigo.get("v10") or []
    ]


COLUNAS_REFERENCIAS_AM = {
    "doc": "VARCHAR",
    "posicao": "INTEGER",
    "titulo": "VARCHAR",
    "titulo_fonte": "VARCHAR",
    "sobrenomes": "VARCHAR[]",
    "prenomes": "VARCHAR[]",
    "ano": "INTEGER",
}


def referencias_do_registro(registro: dict, doc: str) -> list[dict[str, Any]]:
    """As referências (`citations`) de um registro da ArticleMeta, por lista branca: o título (v12: artigo ou
    capítulo), o título da fonte (v18: o livro, ou a revista), até três autores (v10, e v16 quando a referência é a
    obra inteira) e o ano (v64). Servem para conferir a autoria das obras mais citadas (o cânone) e para a cobertura
    das referências; nenhum e-mail passa (os campos são limpos, e só esses entram)."""
    saida = []
    for k, c in enumerate(registro.get("citations") or []):
        titulo = next((_limpo(x.get("_")) for x in c.get("v12") or [] if x.get("_")), None)
        fonte = next((_limpo(x.get("_")) for x in c.get("v18") or [] if x.get("_")), None)
        autores = [a for campo in ("v10", "v16") for a in c.get(campo) or [] if a.get("s") or a.get("_")][:3]
        ano = next((x.get("_") for x in c.get("v64") or [] if str(x.get("_") or "")[:4].isdigit()), None)
        saida.append(
            {
                "doc": doc,
                "posicao": k,
                "titulo": titulo,
                "titulo_fonte": fonte,
                "sobrenomes": [_limpo(a.get("s") or a.get("_")) or "" for a in autores],
                "prenomes": [_limpo(a.get("n")) or "" for a in autores],
                "ano": int(str(ano)[:4]) if ano else None,
            }
        )
    return saida


def _sem_emails(valor: Any) -> Any:
    """Varredura final: remove qualquer e-mail que tenha escapado da lista branca."""
    if isinstance(valor, str):
        return remover_emails(valor) if contem_email(valor) else valor
    if isinstance(valor, dict):
        return {k: _sem_emails(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sem_emails(v) for v in valor]
    return valor


def _url(registro: dict, pid: str) -> str | None:
    html = (registro.get("fulltexts") or {}).get("html") or {}
    if html:
        return next(iter(html.values()))
    if (registro.get("collection") or "scl") == "scl":
        return f"https://www.scielo.br/scielo.php?script=sci_arttext&pid={pid}"
    return None


def normalizar(registro: dict, revista: RevistaRef) -> Documento:
    """Registro bruto da ArticleMeta → `Documento`, sem e-mails."""
    artigo = registro.get("article") or {}
    pid = registro.get("code") or artigo.get("code")
    ano = registro.get("publication_year")
    ano = int(ano) if str(ano or "").isdigit() else ano_do_pid(pid)
    afiliacoes, fonte_afiliacoes = _afiliacoes(artigo)
    idioma = next((x.get("_") for x in artigo.get("v40") or [] if x.get("_")), None)
    doi = normalizar_doi(registro.get("doi")) or normalizar_doi(
        next((x.get("_") for x in artigo.get("v237") or []), None)
    )
    licenca_revista = normalizar_licenca(revista.licenca)
    licenca, fonte_licenca = mais_restritiva(None, licenca_revista)
    dados = {
        "id": pid,
        "pid": pid,
        "colecao": registro.get("collection") or revista.colecao,
        "doi": doi,
        "fonte": "articlemeta",
        "origens": [f"scielo:{revista.issn}"],
        "tipo": registro.get("document_type"),
        "ano": ano,
        "idioma_original": idioma.lower() if idioma else None,
        "revista_issn": revista.issn,
        "revista_acronimo": revista.acronimo,
        "revista_titulo": revista.titulo,
        "titulos": _textos(artigo.get("v12"), "_"),
        "resumos": _textos(artigo.get("v83"), "a", resumo=True),
        "palavras_chave": _palavras_chave(artigo.get("v85")),
        "autores": _autores(artigo),
        "afiliacoes": afiliacoes,
        "afiliacoes_fonte": fonte_afiliacoes,
        "url": _url(registro, pid),
        "n_referencias": len(registro.get("citations") or []),
        "licenca": licenca,
        "licenca_fonte": fonte_licenca,
        "licenca_revista": licenca_revista,
    }
    dados = _sem_emails(Documento(**dados).model_dump())
    return Documento.model_validate(dados)
