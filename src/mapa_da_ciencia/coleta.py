"""Etapa de coleta: monta `dados/documentos.parquet` a partir das fontes do projeto.

Fluxo: resolve o recorte (revistas, anos, tipos) → lista os PIDs de cada revista →
busca os registros (com cache) → normaliza → filtra por tipo → grava o Parquet →
registra o manifesto. Rodar de novo reaproveita tudo o que já está em `brutos/`.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.fontes import revistas as retrato
from mapa_da_ciencia.fontes.articlemeta import RevistaRef, buscar_registros, listar_pids, normalizar
from mapa_da_ciencia.fontes.base import Buscador, limpar_temporarios
from mapa_da_ciencia.fontes.openalex import casar_todos, listar_por_revista
from mapa_da_ciencia.manifesto import registrar_execucao
from mapa_da_ciencia.progresso import Progresso, ProgressoNulo
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.rede import variavel


@dataclass
class OpcoesColeta:
    """Ajustes de uma execução. `revistas` e `anos` substituem o recorte do `mapa.yaml` só nesta execução."""

    revistas: list[str] | None = None
    anos: tuple[int, int] | None = None
    limite: int | None = None
    atualizar: bool = False
    offline: bool = False
    sem_openalex: bool = False


@dataclass
class Plano:
    revistas: list[RevistaRef]
    anos: tuple[int, int]
    tipos: list[str]
    avisos: list[str] = field(default_factory=list)
    openalex: bool = True


@dataclass
class ResumoColeta:
    documentos: int
    por_revista: dict[str, int]
    fora_do_periodo: int
    excluidos_por_tipo: dict[str, int]
    nao_encontrados: int
    casamento: dict[str, int]
    requisicoes: dict[str, int]
    do_cache: dict[str, int]
    creditos_openalex: int
    duracao_s: float
    avisos: list[str]
    plano: Plano

    @property
    def total_requisicoes(self) -> int:
        return sum(self.requisicoes.values())


def interpretar_anos(texto: str) -> tuple[int, int]:
    """`"2024"` → (2024, 2024); `"2010-2025"` → (2010, 2025)."""
    partes = [p.strip() for p in texto.replace("–", "-").split("-")]
    try:
        anos = [int(p) for p in partes if p]
    except ValueError as e:
        raise ErroConfig(f"Anos inválidos: {texto!r}. Use 2024 ou 2010-2025.") from e
    if len(anos) == 1:
        return anos[0], anos[0]
    if len(anos) == 2 and anos[0] <= anos[1]:
        return anos[0], anos[1]
    raise ErroConfig(f"Anos inválidos: {texto!r}. Use 2024 ou 2010-2025, com o primeiro ano antes do segundo.")


def resolver_revistas(identificadores: list[str], colecao: str = "scl") -> list[RevistaRef]:
    saida, desconhecidas = [], []
    for ident in identificadores:
        r = retrato.resolver(ident)
        if r is None:
            desconhecidas.append(ident)
        else:
            saida.append(RevistaRef.de_revista(r, colecao))
    if desconhecidas:
        raise ErroConfig(
            f"Revista(s) não encontrada(s) no retrato do SciELO Brasil: {', '.join(desconhecidas)}. "
            "Confira o ISSN ou o acrônimo com `mapa revistas`."
        )
    return list({r.issn: r for r in saida}.values())


def planejar(projeto: Projeto, opcoes: OpcoesColeta) -> Plano:
    cfg = projeto.config
    scielo = cfg.fontes.scielo
    colecao = scielo.colecao if scielo else "scl"
    avisos = []
    do_yaml = list(scielo.revistas) if scielo else []
    idents = opcoes.revistas or do_yaml
    if not idents:
        raise ErroConfig("Nenhuma revista no recorte: preencha `fontes.scielo.revistas` no mapa.yaml ou use --revista.")
    revistas = resolver_revistas(idents, colecao)
    anos = opcoes.anos or cfg.recorte.anos
    if opcoes.revistas and {r.issn for r in revistas} != {r.issn for r in resolver_revistas(do_yaml, colecao)}:
        avisos.append("As revistas desta execução (--revista) diferem das do mapa.yaml.")
    if opcoes.anos and tuple(opcoes.anos) != tuple(cfg.recorte.anos):
        avisos.append(f"Os anos desta execução ({anos[0]}–{anos[1]}) diferem dos do mapa.yaml.")
    tipos = list(scielo.tipos) if scielo else ["research-article", "review-article"]
    return Plano(revistas, anos, tipos, avisos, openalex=cfg.fontes.openalex.enriquecer)


async def _enriquecer(
    buscador: Buscador,
    projeto: Projeto,
    plano: Plano,
    documentos: list[Documento],
    opcoes: OpcoesColeta,
    progresso: Progresso,
) -> list[Documento]:
    """Casa os documentos de cada revista com os trabalhos do OpenAlex do mesmo período."""
    api_key = variavel("OPENALEX_API_KEY", projeto.raiz)
    progresso.etapa("OpenAlex", len(plano.revistas))
    saida: list[Documento] = []
    for revista in plano.revistas:
        da_revista = [d for d in documentos if d.revista_issn == revista.issn]
        if da_revista:
            obras = await listar_por_revista(buscador, revista, plano.anos, api_key=api_key, atualizar=opcoes.atualizar)
            saida += casar_todos(da_revista, obras)
        progresso.avancar()
    outros = [d for d in documentos if d.revista_issn not in {r.issn for r in plano.revistas}]
    return saida + outros


async def coletar_async(
    projeto: Projeto, opcoes: OpcoesColeta | None = None, progresso: Progresso | None = None
) -> ResumoColeta:
    opcoes = opcoes or OpcoesColeta()
    progresso = progresso or ProgressoNulo()
    plano = planejar(projeto, opcoes)
    inicio = datetime.now(UTC)
    t0 = time.perf_counter()
    limpar_temporarios(projeto.brutos)
    avisos = list(plano.avisos)

    async with Buscador(projeto.brutos, pasta_projeto=projeto.raiz, offline=opcoes.offline) as buscador:
        progresso.etapa("Listas de PIDs", len(plano.revistas))
        pids_por_revista: dict[str, list[str]] = {}
        fora_do_periodo = 0
        for revista in plano.revistas:
            lista = await listar_pids(buscador, revista, plano.anos, atualizar=opcoes.atualizar)
            pids_por_revista[revista.issn] = lista.pids
            fora_do_periodo += lista.fora_do_periodo
            if lista.aviso:
                avisos.append(f"{revista.titulo}: {lista.aviso}")
            progresso.avancar()

        pids = [(r, p) for r in plano.revistas for p in pids_por_revista[r.issn]]
        if opcoes.limite is not None:
            pids = pids[: opcoes.limite]
        progresso.etapa("Registros da ArticleMeta", len(pids))
        revista_do_pid = {p: r for r, p in pids}
        registros = await buscar_registros(buscador, [p for _, p in pids], ao_avancar=lambda _pid: progresso.avancar())

        progresso.etapa("Normalizando", len(registros))
        documentos: list[Documento] = []
        excluidos: Counter[str] = Counter()
        nao_encontrados = 0
        for pid, registro in registros.items():
            progresso.avancar()
            if registro is None:
                nao_encontrados += 1
                continue
            doc = normalizar(registro, revista_do_pid[pid])
            if doc.tipo not in plano.tipos:
                excluidos[doc.tipo or "sem tipo"] += 1
                continue
            documentos.append(doc)

        if plano.openalex and not opcoes.sem_openalex:
            documentos = await _enriquecer(buscador, projeto, plano, documentos, opcoes, progresso)
        contadores = buscador.contadores

    n = gravar_documentos(documentos, projeto.dados / ARQUIVO)
    progresso.fim()

    resumo = ResumoColeta(
        documentos=n,
        casamento=dict(sorted(Counter(d.casamento for d in documentos).items())),
        por_revista=dict(Counter(d.revista_acronimo or "?" for d in documentos).most_common()),
        fora_do_periodo=fora_do_periodo,
        excluidos_por_tipo=dict(excluidos.most_common()),
        nao_encontrados=nao_encontrados,
        requisicoes=dict(contadores.requisicoes),
        do_cache=dict(contadores.do_cache),
        creditos_openalex=contadores.creditos_openalex,
        duracao_s=round(time.perf_counter() - t0, 2),
        avisos=avisos,
        plano=plano,
    )
    registrar_execucao(
        projeto,
        "coleta",
        inicio=inicio,
        fim=datetime.now(UTC),
        contagens={
            "documentos": n,
            "fora_do_periodo": fora_do_periodo,
            "excluidos_por_tipo": sum(excluidos.values()),
            "nao_encontrados": nao_encontrados,
            "requisicoes": resumo.total_requisicoes,
            "do_cache": sum(resumo.do_cache.values()),
            "creditos_openalex": resumo.creditos_openalex,
            "casados_openalex": sum(v for k, v in resumo.casamento.items() if k[0].isdigit()),
        },
        parametros=_parametros(plano, opcoes),
    )
    return resumo


def _parametros(plano: Plano, opcoes: OpcoesColeta) -> dict[str, Any]:
    return {
        "revistas": [r.issn for r in plano.revistas],
        "anos": list(plano.anos),
        "tipos": plano.tipos,
        "limite": opcoes.limite,
        "offline": opcoes.offline,
        "atualizar": opcoes.atualizar,
        "openalex": plano.openalex and not opcoes.sem_openalex,
    }


def coletar(projeto: Projeto, opcoes: OpcoesColeta | None = None, progresso: Progresso | None = None) -> ResumoColeta:
    """Roda a coleta. Funciona também dentro de um laço de eventos já ativo (Jupyter, Colab)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coletar_async(projeto, opcoes, progresso))
    resultado: dict[str, Any] = {}

    def em_thread() -> None:
        try:
            resultado["ok"] = asyncio.run(coletar_async(projeto, opcoes, progresso))
        except BaseException as e:  # repassa para quem chamou
            resultado["erro"] = e

    t = threading.Thread(target=em_thread)
    t.start()
    t.join()
    if "erro" in resultado:
        raise resultado["erro"]
    return resultado["ok"]
