"""Deduplicação dos documentos vindos de fontes diferentes (e da própria ArticleMeta).

Regras, em ordem:

1. **Mesmo PID** → o mesmo documento (ex.: um artigo coletado da revista e também importado).
2. **Mesmo DOI e títulos compatíveis** → o mesmo documento, inclusive dentro da ArticleMeta, que
   tem artigos carregados duas vezes com PIDs diferentes (Dados e Lua Nova, 2025). DOI igual com
   títulos diferentes *não* funde: a ArticleMeta também tem DOIs trocados (Dados, 2014).
3. **Sem DOI, mesmo título, ano e sobrenome do 1º autor, em fontes diferentes** → o mesmo documento.

Ao fundir, fica a versão da ArticleMeta (ou o menor id) e as `origens` se somam; os pares
fundidos vão para o manifesto da coleta. Dentro da mesma fonte, dois documentos com o mesmo
título, ano e 1º autor **sem** DOI em comum viram só uma **suspeita** (`possivel_duplicata_de`):
sem a confirmação do DOI, apagar é decisão do pesquisador. Títulos curtos e genéricos
("Apresentação") nunca contam como duplicata.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.texto import normalizar_titulo, similaridade_titulo

TITULO_MINIMO = 20  # caracteres do título normalizado para valer como chave de duplicata
SIMILARIDADE_MINIMA = 0.6


@dataclass
class RelatorioDedup:
    fundidos: list[tuple[str, str]] = field(default_factory=list)  # (removido, mantido)
    suspeitas: list[tuple[str, str]] = field(default_factory=list)  # (documento, possível original)


def _chave(doc: Documento) -> tuple[str, int, str] | None:
    titulo = normalizar_titulo(doc.titulos[0].texto) if doc.titulos else ""
    sobrenome = normalizar_titulo(doc.autores[0].sobrenome) if doc.autores and doc.autores[0].sobrenome else ""
    if len(titulo) < TITULO_MINIMO or not sobrenome:
        return None
    return titulo, doc.ano, sobrenome


def titulos_compativeis(a: Documento, b: Documento) -> bool:
    if not a.titulos or not b.titulos:
        return True
    return max(similaridade_titulo(x.texto, y.texto) for x in a.titulos for y in b.titulos) >= SIMILARIDADE_MINIMA


def fundir(principal: Documento, outro: Documento) -> Documento:
    """Mantém o principal e completa o que falta com o outro; as origens se somam."""
    mudancas: dict = {"origens": list(dict.fromkeys([*principal.origens, *outro.origens]))}
    for campo in ("doi", "openalex_id", "citacoes", "pid", "url", "licenca_openalex"):
        if getattr(principal, campo) is None and getattr(outro, campo) is not None:
            mudancas[campo] = getattr(outro, campo)
    if not principal.resumos and outro.resumos:
        mudancas["resumos"] = outro.resumos
    return principal.model_copy(update=mudancas)


def _prioridade(doc: Documento) -> tuple[int, str]:
    return (0 if doc.fonte == "articlemeta" else 1, doc.id)


def deduplicar(documentos: list[Documento]) -> tuple[list[Documento], RelatorioDedup]:
    relatorio = RelatorioDedup()
    mantidos: dict[str, Documento] = {}
    por_pid: dict[str, str] = {}
    por_doi: dict[str, str] = {}
    por_chave: dict[tuple[str, int, str], str] = {}

    for doc in sorted(documentos, key=_prioridade):
        alvo: str | None = None
        chave = _chave(doc)
        if doc.pid and doc.pid in por_pid:
            alvo = por_pid[doc.pid]
        elif doc.doi and doc.doi in por_doi and titulos_compativeis(doc, mantidos[por_doi[doc.doi]]):
            alvo = por_doi[doc.doi]
        elif chave and chave in por_chave:
            existente = mantidos[por_chave[chave]]
            if existente.fonte != doc.fonte and (doc.doi is None or existente.doi is None):
                alvo = existente.id
            elif existente.fonte == doc.fonte:
                doc = doc.model_copy(update={"possivel_duplicata_de": existente.id})
                relatorio.suspeitas.append((doc.id, existente.id))
        if alvo is not None:
            mantidos[alvo] = fundir(mantidos[alvo], doc)
            relatorio.fundidos.append((doc.id, alvo))
            continue
        mantidos[doc.id] = doc
        if doc.pid:
            por_pid.setdefault(doc.pid, doc.id)
        if doc.doi:
            por_doi.setdefault(doc.doi, doc.id)
        if chave:
            por_chave.setdefault(chave, doc.id)
    return sorted(mantidos.values(), key=lambda d: d.id), relatorio
