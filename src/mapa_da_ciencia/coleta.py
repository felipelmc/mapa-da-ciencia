"""Etapa de coleta: monta `dados/documentos.parquet` a partir das fontes do projeto.

Fluxo: resolve o recorte (revistas, anos, tipos) → lista os PIDs de cada revista →
busca os registros (com cache) → normaliza → filtra por tipo → grava o Parquet →
registra o manifesto. Rodar de novo reaproveita tudo o que já está em `brutos/`.
"""

from __future__ import annotations

import asyncio
import shutil
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mapa_da_ciencia.armazenamento import ARQUIVO, ARQUIVO_INSTITUICOES, gravar_documentos, gravar_tabela
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.contrato.exportar import exportar
from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.fontes import revistas as retrato
from mapa_da_ciencia.fontes.articlemeta import (
    RevistaRef,
    buscar_registros,
    listar_pids,
    normalizar,
    revista_do_registro,
)
from mapa_da_ciencia.fontes.base import Buscador, ErroFonte, limpar_temporarios
from mapa_da_ciencia.fontes.dedup import deduplicar
from mapa_da_ciencia.fontes.importar import FORMATOS, Identificador, Importacao, ler_arquivo
from mapa_da_ciencia.fontes.importar import colecao_da_url as colecao_da_url
from mapa_da_ciencia.fontes.openalex import (
    COLUNAS_INSTITUICOES,
    buscar_instituicoes,
    buscar_obra,
    buscar_por_dois,
    casar_todos,
    consultar,
    documento_de_obra,
    issns_da_obra,
    linha_de_instituicao,
    listar_por_revista,
    pid_da_obra,
)
from mapa_da_ciencia.formatar import num, periodo
from mapa_da_ciencia.manifesto import registrar_execucao
from mapa_da_ciencia.progresso import Progresso, ProgressoNulo
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.rede import variavel
from mapa_da_ciencia.texto import normalizar_doi

PASTA_IMPORTADOS = "importados"


@dataclass
class OpcoesColeta:
    """Ajustes de uma execução. `revistas` e `anos` substituem o recorte do `mapa.yaml` só nesta execução."""

    revistas: list[str] | None = None
    anos: tuple[int, int] | None = None
    limite: int | None = None
    atualizar: bool = False
    offline: bool = False
    sem_openalex: bool = False
    consulta: str | None = None


@dataclass
class Plano:
    revistas: list[RevistaRef]
    anos: tuple[int, int]
    tipos: list[str]
    avisos: list[str] = field(default_factory=list)
    openalex: bool = True
    importados: list[Path] = field(default_factory=list)
    consulta: str | None = None


@dataclass
class ResumoColeta:
    """O que uma execução da coleta fez. `print(resumo)` mostra os números principais numa frase.

    `documentos` e `por_revista` contam o que foi gravado no corpus. `fora_do_periodo`, `excluidos_por_tipo`
    e `nao_encontrados` contam o que ficou de fora, e `casamento` conta os documentos por passo da ligação
    com o OpenAlex. `requisicoes`, `do_cache` e `creditos_openalex` medem o acesso às APIs.
    """

    documentos: int
    por_revista: dict[str, int]
    fora_do_periodo: int
    excluidos_por_tipo: dict[str, int]
    nao_encontrados: int
    casamento: dict[str, int]
    fundidos: int
    possiveis_duplicatas: list[tuple[str, str]]
    importacoes: list[str]
    requisicoes: dict[str, int]
    do_cache: dict[str, int]
    creditos_openalex: int
    duracao_s: float
    avisos: list[str]
    plano: Plano

    @property
    def total_requisicoes(self) -> int:
        return sum(self.requisicoes.values())

    def __str__(self) -> str:
        casados = sum(v for k, v in self.casamento.items() if k[0].isdigit())
        return (
            f"{num(self.documentos, 0)} documento(s) de {len(self.por_revista)} revista(s), "
            f"{periodo(self.plano.anos)}, em {num(self.duracao_s)} s. "
            f"De fora: {num(self.fora_do_periodo, 0)} fora do período, "
            f"{num(sum(self.excluidos_por_tipo.values()), 0)} por tipo, {num(self.nao_encontrados, 0)} não "
            f"encontrado(s). OpenAlex: {num(casados, 0)} casado(s), {num(self.creditos_openalex, 0)} crédito(s). "
            f"{num(self.total_requisicoes, 0)} requisição(ões), {num(sum(self.do_cache.values()), 0)} do cache."
        )


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
    importados = [projeto.raiz / p for p in cfg.fontes.importar]
    pasta = projeto.raiz / PASTA_IMPORTADOS
    if pasta.exists():
        importados += sorted(p for p in pasta.iterdir() if p.suffix.lower() in FORMATOS)
    consulta = opcoes.consulta or cfg.fontes.openalex.consulta
    if consulta and (opcoes.sem_openalex or not cfg.fontes.openalex.enriquecer):
        raise ErroConfig("A busca por termo usa o OpenAlex: não combine `consulta` com --sem-openalex.")
    if not idents and not importados and not consulta:
        raise ErroConfig(
            "Nenhuma fonte no recorte: preencha `fontes.scielo.revistas` no mapa.yaml, use --revista "
            "importe uma lista de artigos com `mapa importar` ou defina uma busca (`fontes.openalex.consulta`)."
        )
    revistas = resolver_revistas(idents, colecao) if idents else []
    anos = opcoes.anos or cfg.recorte.anos
    if opcoes.revistas and {r.issn for r in revistas} != {r.issn for r in resolver_revistas(do_yaml, colecao)}:
        avisos.append("As revistas desta execução (--revista) diferem das do mapa.yaml.")
    if opcoes.anos and tuple(opcoes.anos) != tuple(cfg.recorte.anos):
        avisos.append(f"Os anos desta execução ({anos[0]}–{anos[1]}) diferem dos do mapa.yaml.")
    tipos = list(scielo.tipos) if scielo else ["research-article", "review-article"]
    return Plano(
        revistas,
        anos,
        tipos,
        avisos,
        openalex=cfg.fontes.openalex.enriquecer,
        importados=importados,
        consulta=consulta,
    )


async def _enriquecer(
    buscador: Buscador,
    projeto: Projeto,
    plano: Plano,
    documentos: list[Documento],
    opcoes: OpcoesColeta,
    progresso: Progresso,
) -> list[Documento]:
    """Casa os documentos de cada revista com os trabalhos do OpenAlex do mesmo período.

    Os que sobram sem casamento são procurados pelo DOI (o da ArticleMeta e o derivado do PID): o OpenAlex
    às vezes não liga o trabalho à revista (só a um repositório, como o DOAJ) ou registra o ano errado.
    """
    api_key = variavel("OPENALEX_API_KEY", projeto.raiz)
    progresso.etapa("OpenAlex", len(plano.revistas) + 1)
    saida: list[Documento] = []
    for revista in plano.revistas:
        da_revista = [d for d in documentos if d.revista_issn == revista.issn]
        if da_revista:
            obras = await listar_por_revista(buscador, revista, plano.anos, api_key=api_key, atualizar=opcoes.atualizar)
            saida += casar_todos(da_revista, obras)
        progresso.avancar()

    sobras = [d for d in saida if d.casamento == "sem_casamento"]
    dois = [d.doi for d in sobras if d.doi] + [f"10.1590/{d.pid.lower()}" for d in sobras if d.pid]
    if dois:
        usados = {d.openalex_id for d in saida if d.openalex_id}
        obras = [
            o
            for o in await buscar_por_dois(buscador, dois, api_key=api_key)
            if o["id"].rsplit("/", 1)[-1] not in usados
        ]
        casados = {d.id: d for d in casar_todos(sobras, obras)}
        # o filtro por DOI ainda não acha alguns trabalhos novos; o endereço direto acha e não custa créditos
        ainda = [d for d in casados.values() if d.casamento == "sem_casamento" and d.doi]
        diretas = await asyncio.gather(*(buscar_obra(buscador, d.doi, api_key=api_key) for d in ainda))
        usados |= {d.openalex_id for d in casados.values() if d.openalex_id}
        obras = [o for o in diretas if o and o["id"].rsplit("/", 1)[-1] not in usados]
        if obras:
            casados |= {d.id: d for d in casar_todos(ainda, obras)}
        saida = [casados.get(d.id, d) for d in saida]
    progresso.avancar()
    outros = [d for d in documentos if d.revista_issn not in {r.issn for r in plano.revistas}]
    return saida + outros


def _colecao_da_obra(obra: dict) -> str | None:
    return colecao_da_url(" ".join(loc.get("landing_page_url") or "" for loc in obra.get("locations") or []))


async def _pid_da_obra(buscador: Buscador, obra: dict, dois_por_revista: dict[str, dict[str, str]]) -> str | None:
    """O PID de uma obra do OpenAlex: nos endereços dela ou, para revistas do SciELO Brasil, pelo DOI na lista de
    identificadores da revista na ArticleMeta (a mesma do cache da coleta; os endereços novos não trazem o PID)."""
    if pid := pid_da_obra(obra):
        return pid
    doi = normalizar_doi(obra.get("doi"))
    for issn in issns_da_obra(obra):
        if doi is None or (revista := retrato.por_issn(issn)) is None:
            continue
        if revista.issn not in dois_por_revista:
            lista = await listar_pids(buscador, RevistaRef.de_revista(revista), (0, 9999))
            dois_por_revista[revista.issn] = lista.dois
        if pid := dois_por_revista[revista.issn].get(doi):
            return pid
    return None


async def _hidratar(
    buscador: Buscador,
    projeto: Projeto,
    plano: Plano,
    opcoes: OpcoesColeta,
    itens: list[tuple[Identificador, str]],
    *,
    obras: list[dict] | None = None,
) -> tuple[list[Documento], int]:
    """Transforma identificadores (PID e/ou DOI, com a origem) em documentos. Devolve (documentos, não encontrados).

    PID → ArticleMeta, na coleção de cada um. Só DOI → OpenAlex (ou `obras`, se já vieram de uma busca), que pode
    apontar um PID; sem PID, o documento é montado com os dados do OpenAlex.
    """
    usar_openalex = plano.openalex and not opcoes.sem_openalex
    api_key = variavel("OPENALEX_API_KEY", projeto.raiz)

    origem_do_pid: dict[str, str] = {}
    por_colecao: dict[str, set[str]] = {}
    for ident, origem in itens:
        if ident.pid:
            origem_do_pid.setdefault(ident.pid, origem)
            por_colecao.setdefault(ident.colecao or "scl", set()).add(ident.pid)
    documentos: list[Documento] = []
    for colecao, pids in sorted(por_colecao.items()):

        def tratar(pid: str, registro: dict, colecao: str = colecao) -> Documento:
            doc = normalizar(registro, revista_do_registro(registro, colecao))
            return doc.model_copy(update={"origens": [origem_do_pid[pid]]})

        achados = await buscar_registros(buscador, sorted(pids), colecao, tratar=tratar)
        documentos += [doc for doc in achados.values() if doc is not None]
    encontrados = {d.pid for d in documentos}

    pendentes = [(i, o) for i, o in itens if not i.pid or i.pid not in encontrados]
    if obras is None:
        dois = [i.doi for i, _ in pendentes if i.doi] + [d.doi for d in documentos if d.doi]
        obras = await buscar_por_dois(buscador, dois, api_key=api_key) if usar_openalex and dois else []
    por_doi = {normalizar_doi(o.get("doi")): o for o in obras}
    nao_encontrados, so_openalex = 0, []
    dois_por_revista: dict[str, dict[str, str]] = {}
    for ident, origem in pendentes:
        obra = por_doi.get(ident.doi) if ident.doi else None
        if obra is None:
            nao_encontrados += 1
            continue
        pid = await _pid_da_obra(buscador, obra, dois_por_revista)
        if pid and pid not in encontrados:
            colecao = _colecao_da_obra(obra) or "scl"
            achado = await buscar_registros(
                buscador, [pid], colecao, tratar=lambda _p, r, c=colecao: normalizar(r, revista_do_registro(r, c))
            )
            if (doc := achado[pid]) is not None:
                documentos.append(doc.model_copy(update={"origens": [origem]}))
                encontrados.add(pid)
                continue
        if not pid or pid not in encontrados:
            so_openalex.append(documento_de_obra(obra, origem))
    if obras:
        documentos = casar_todos(documentos, obras)
    return documentos + so_openalex, nao_encontrados


def guardar_importacao(projeto: Projeto, arquivo: Path) -> Importacao:
    """Lê o arquivo e o copia para `importados/`, de onde ele entra em toda coleta do projeto.

    Recusa arquivos sem nenhum PID ou DOI, que quase sempre são exportações no formato errado.
    """
    arquivo = Path(arquivo)
    if not arquivo.exists():
        raise ErroConfig(f"Arquivo não encontrado: {arquivo}")
    leitura = ler_arquivo(arquivo)
    if not leitura.itens:
        raise ErroConfig(f"{arquivo.name}: nenhum PID ou DOI encontrado. Confira se é uma exportação do SciELO.")
    destino = projeto.raiz / PASTA_IMPORTADOS
    destino.mkdir(exist_ok=True)
    if arquivo.resolve() != (destino / arquivo.name).resolve():
        shutil.copy2(arquivo, destino / arquivo.name)
    return leitura


async def _importar(
    buscador: Buscador, projeto: Projeto, plano: Plano, opcoes: OpcoesColeta, progresso: Progresso
) -> tuple[list[Documento], list[str], int]:
    """Artigos dos arquivos importados. Devolve (documentos, relatórios de leitura, não encontrados)."""
    itens: list[tuple[Identificador, str]] = []
    relatorios = []
    for arquivo in plano.importados:
        imp = ler_arquivo(arquivo)
        relatorios.append(imp.resumo())
        itens += [(i, f"importar:{arquivo.name}") for i in imp.itens]
    if not itens:
        return [], relatorios, 0
    progresso.etapa("Artigos importados", len(itens))
    documentos, nao_encontrados = await _hidratar(buscador, projeto, plano, opcoes, itens)
    progresso.avancar(len(itens))
    return documentos, relatorios, nao_encontrados


async def _consultar(
    buscador: Buscador, projeto: Projeto, plano: Plano, opcoes: OpcoesColeta, progresso: Progresso
) -> tuple[list[Documento], int]:
    """Artigos que respondem à busca por termo no OpenAlex, nas revistas do recorte (ou em todo o SciELO)."""
    assert plano.consulta
    progresso.etapa("Busca no OpenAlex", 1)
    api_key = variavel("OPENALEX_API_KEY", projeto.raiz)
    obras = await consultar(buscador, plano.consulta, plano.revistas, plano.anos, api_key=api_key)
    origem = f"consulta:{plano.consulta}"
    itens = [
        (
            Identificador(
                pid_da_obra(o), _colecao_da_obra(o), normalizar_doi(o.get("doi")), o.get("title"), None, origem
            ),
            origem,
        )
        for o in obras
    ]
    documentos, nao_encontrados = await _hidratar(buscador, projeto, plano, opcoes, itens, obras=obras)
    progresso.avancar()
    return documentos, nao_encontrados


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
        # Com busca por termo, as revistas só restringem a busca: não se coleta a revista inteira.
        coletar_revistas = [] if plano.consulta else plano.revistas
        progresso.etapa("Listas de PIDs", len(coletar_revistas))
        pids_por_revista: dict[str, list[str]] = {}
        fora_do_periodo = 0
        for revista in coletar_revistas:
            lista = await listar_pids(buscador, revista, plano.anos, atualizar=opcoes.atualizar)
            pids_por_revista[revista.issn] = lista.pids
            fora_do_periodo += lista.fora_do_periodo
            if lista.aviso:
                avisos.append(f"{revista.titulo}: {lista.aviso}")
            progresso.avancar()

        pids = [(r, p) for r in coletar_revistas for p in pids_por_revista[r.issn]]
        if opcoes.limite is not None:
            pids = pids[: opcoes.limite]
        progresso.etapa("Registros da ArticleMeta", len(pids))
        revista_do_pid = {p: r for r, p in pids}
        normalizados = await buscar_registros(
            buscador,
            [p for _, p in pids],
            ao_avancar=lambda _pid: progresso.avancar(),
            tratar=lambda pid, registro: normalizar(registro, revista_do_pid[pid]),
        )

        documentos: list[Documento] = []
        excluidos: Counter[str] = Counter()
        nao_encontrados = 0
        for doc in normalizados.values():
            if doc is None:
                nao_encontrados += 1
                continue
            if doc.tipo not in plano.tipos:
                excluidos[doc.tipo or "sem tipo"] += 1
                continue
            documentos.append(doc)

        if documentos and plano.openalex and not opcoes.sem_openalex:
            documentos = await _enriquecer(buscador, projeto, plano, documentos, opcoes, progresso)
        if plano.consulta:
            da_busca, nao_achados = await _consultar(buscador, projeto, plano, opcoes, progresso)
            documentos += da_busca
            nao_encontrados += nao_achados

        importados, importacoes, nao_achados = await _importar(buscador, projeto, plano, opcoes, progresso)
        nao_encontrados += nao_achados
        for doc in importados:
            if not plano.anos[0] <= doc.ano <= plano.anos[1]:
                fora_do_periodo += 1
            elif doc.tipo not in plano.tipos:
                excluidos[doc.tipo or "sem tipo"] += 1
            else:
                documentos.append(doc)

        # registros das instituições que o OpenAlex associou aos autores (siglas, nomes, local, linhagem):
        # a base do casamento das afiliações na geografia
        instituicoes: list[dict] = []
        ids_inst = {
            i for d in documentos for a in d.autorias_openalex for x in a.instituicoes for i in (x.id, *x.linhagem)
        }
        if ids_inst and plano.openalex and not opcoes.sem_openalex:
            try:
                api_key = variavel("OPENALEX_API_KEY", projeto.raiz)
                instituicoes = await buscar_instituicoes(buscador, ids_inst, api_key=api_key)
            except ErroFonte as erro:
                avisos.append(
                    f"Registros das instituições do OpenAlex indisponíveis ({erro}); a geografia vai usar só os nomes."
                )
        contadores = buscador.contadores

    documentos, dedup = deduplicar(documentos)
    avisos += [
        f"{doc}: o DOI {doi} é de outro artigo ({dono}, confirmado pelo OpenAlex); o documento ficou sem DOI."
        for doc, doi, dono in dedup.dois_removidos
    ]
    if dedup.resumos_descartados:
        exemplos = ", ".join(sorted({doc for doc, _ in dedup.resumos_descartados})[:5])
        avisos.append(
            f"{num(len(dedup.resumos_descartados), 0)} resumo(s) descartado(s) por se repetirem em documentos "
            f"diferentes (um texto padrão, e não o resumo do artigo), por exemplo em {exemplos}."
        )
    n = gravar_documentos(documentos, projeto.dados / ARQUIVO)
    if instituicoes:
        gravar_tabela(
            [linha_de_instituicao(r) for r in instituicoes], COLUNAS_INSTITUICOES, projeto.dados / ARQUIVO_INSTITUICOES
        )
    progresso.fim()

    resumo = ResumoColeta(
        documentos=n,
        casamento=dict(sorted(Counter(d.casamento for d in documentos).items())),
        fundidos=len(dedup.fundidos),
        possiveis_duplicatas=dedup.suspeitas,
        importacoes=importacoes,
        por_revista=dict(Counter(d.chave_revista for d in documentos).most_common()),
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
            "fundidos": resumo.fundidos,
            "possiveis_duplicatas": len(resumo.possiveis_duplicatas),
            "resumos_descartados": len(dedup.resumos_descartados),
        },
        parametros=_parametros(plano, opcoes)
        | {
            "duplicatas_fundidas": dedup.fundidos,
            "dois_removidos": dedup.dois_removidos,
            "resumos_descartados": dedup.resumos_descartados,
        },
    )
    avisos += exportar(projeto)  # manifesto e revistas; tópicos que ficaram de outro corpus, com aviso
    return resumo


def _parametros(plano: Plano, opcoes: OpcoesColeta) -> dict[str, Any]:
    return {
        "revistas": [r.issn for r in plano.revistas],
        "importados": [p.name for p in plano.importados],
        "consulta": plano.consulta,
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
