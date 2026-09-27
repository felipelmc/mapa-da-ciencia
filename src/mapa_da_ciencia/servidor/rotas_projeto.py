"""Rotas do projeto no painel: o estado das etapas, os modelos, a estimativa da classificação, a configuração e o
codebook.

- `GET /api/projeto/etapas`: cada etapa do pipeline como `pendente`, `em_dia`, `incompleta` ou `desatualizada`,
  com a última execução (a linha de metrô da vista Projeto);
- `GET /api/modelos`: a memória da máquina, o perfil sugerido, os perfis, os modelos instalados no Ollama e os do
  projeto (instalados ou não, com o tamanho do download);
- `POST /api/modelos/baixar`: baixa um modelo (`ollama pull`) como um job, com o progresso ao vivo;
- `GET /api/estimativa/classificacao`: quantos documentos faltam classificar e quanto tempo isso deve levar;
- `GET /api/revistas`: as revistas correntes do SciELO Brasil, para escolher as fontes;
- `GET` e `PATCH /api/configuracao`, `GET` e `PUT /api/codebook`: lidos e gravados sem perder os comentários do YAML
  (`edicao.py`), validados antes de ir para o disco, e recusados enquanto uma etapa roda.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import Codebook, ConfigProjeto, ErroConfig
from ..llm.base import ErroProvedor
from ..manifesto import status_das_etapas
from ..projeto import Projeto
from .jobs import Jobs, Ocupado
from .origem import conferir_origem

NOME_MODELO = re.compile(r"^[\w.:/-]{1,80}$")


class PedidoDownload(BaseModel):
    modelo: str = Field(pattern=NOME_MODELO.pattern)


@dataclass
class ResumoDownload:
    modelo: str
    tamanho_gb: float | None

    def __str__(self) -> str:
        tamanho = f" ({self.tamanho_gb:.1f} GB)".replace(".", ",") if self.tamanho_gb else ""
        return f"{self.modelo} baixado{tamanho}."


def etapa_baixar_modelo(projeto: Projeto, opcoes: dict[str, Any], progresso) -> ResumoDownload:
    from ..llm.ollama import Ollama

    pedido = PedidoDownload(**opcoes)
    ollama = Ollama()
    ollama.baixar(pedido.modelo, progresso)
    instalado = ollama.instalado(pedido.modelo)
    return ResumoDownload(pedido.modelo, round(instalado.tamanho_gb, 2) if instalado else None)


def estados_das_etapas(projeto: Projeto) -> dict[str, dict[str, Any]]:
    """Cada etapa: `pendente` (nunca rodou), `em_dia`, `incompleta` (a classificação parou antes do fim, a amostra
    não foi toda codificada) ou `desatualizada` (o corpus, o codebook ou as correções mudaram depois), com a última
    execução."""
    from ..armazenamento import ARQUIVO, ler_documentos
    from ..classificacao.pipeline import classificacao_em_dia
    from ..geografia.pipeline import geografia_em_dia
    from ..topicos.resultado import PASTA, Resultado, assinatura_corpus
    from ..validacao.amostra import codificacoes
    from ..validacao.amostra import ler as ler_amostra

    ultimas = status_das_etapas(projeto)
    tem_corpus = (projeto.dados / ARQUIVO).exists()
    topicos: bool | None = None
    if tem_corpus and (r := Resultado.ler(projeto.dados / PASTA)) is not None:
        topicos = r.assinatura == assinatura_corpus([d.id for d in ler_documentos(projeto.dados / ARQUIVO)])
    amostra = ler_amostra(projeto)
    codificados = len({c["doc"] for c in codificacoes(projeto)} & set(amostra.docs)) if amostra else 0
    classificacao: bool | str | None = None
    if tem_corpus:
        from ..classificacao.resultado import PASTA as PASTA_CLS
        from ..classificacao.resultado import Resultado as ResultadoCls

        cfg = projeto.config.modelos.classificacao
        r_cls = ResultadoCls.ler(projeto.dados / PASTA_CLS, cfg.modelo, projeto.codebook.hash())
        em_dia_cls = classificacao_em_dia(projeto)
        classificacao = "incompleta" if r_cls is not None and r_cls.parcial else em_dia_cls
    em_dia: dict[str, bool | str | None] = {
        "coleta": True if tem_corpus else None,
        "topicos": topicos,
        "geografia": geografia_em_dia(projeto) if tem_corpus else None,
        "classificacao": classificacao,
        "validacao": None if not amostra else (True if codificados >= len(amostra.docs) else "incompleta"),
    }
    nomes = {None: "pendente", True: "em_dia", False: "desatualizada", "incompleta": "incompleta"}
    saida = {}
    for etapa, estado in em_dia.items():
        m = ultimas.get(etapa)
        saida[etapa] = {
            "estado": nomes[estado],
            "ultima": None
            if m is None
            else {"fim": m["fim"], "duracao_s": m["duracao_s"], "contagens": m["contagens"]},
        }
    if amostra:
        saida["validacao"]["amostra"] = {"n": len(amostra.docs), "codificados": codificados}
    return saida


def rotas_projeto(projeto: Projeto, jobs: Jobs) -> APIRouter:
    rotas = APIRouter(prefix="/api", tags=["projeto"])

    def _livre() -> None:
        if (ativo := jobs.ativo()) is not None:
            raise HTTPException(409, f"Espere a etapa {ativo.etapa} terminar (ou cancele-a) antes de mudar o projeto.")

    @rotas.get("/projeto/etapas")
    def etapas() -> dict[str, Any]:
        """O estado de cada etapa do pipeline, para a linha de metrô da vista Projeto."""
        return estados_das_etapas(projeto)

    @rotas.get("/modelos")
    def modelos() -> dict[str, Any]:
        """Memória, perfis, modelos instalados no Ollama e os modelos do projeto."""
        from ..llm.ollama import Ollama
        from ..llm.perfis import PERFIS, TAMANHOS_GB, ram_total_gb, sugerir_perfil

        ram = ram_total_gb()
        ollama = {"no_ar": True, "erro": None}
        instalados: list[dict[str, Any]] = []
        try:
            instalados = [
                {"nome": m.nome, "tamanho_gb": round(m.tamanho_gb, 2)} for m in Ollama(timeout=5).listar_modelos()
            ]
        except ErroProvedor as e:
            ollama = {"no_ar": False, "erro": str(e)}
        nomes = {m["nome"].removesuffix(":latest") for m in instalados}
        cfg = projeto.config.modelos
        do_projeto = {
            papel: {
                "modelo": getattr(cfg, papel).modelo,
                "instalado": getattr(cfg, papel).modelo.removesuffix(":latest") in nomes,
                "download_gb": TAMANHOS_GB.get(getattr(cfg, papel).modelo),
            }
            for papel in ("embeddings", "classificacao", "rotulos")
        }
        return {
            "ram_gb": round(ram, 1),
            "perfil_sugerido": sugerir_perfil(ram).nome,
            "perfis": [dataclasses.asdict(p) for p in PERFIS.values()],
            "tamanhos_gb": TAMANHOS_GB,
            "ollama": ollama,
            "instalados": instalados,
            "projeto": do_projeto,
        }

    @rotas.post("/modelos/baixar", status_code=202, dependencies=[Depends(conferir_origem)])
    def baixar(pedido: PedidoDownload) -> dict[str, Any]:
        """Baixa um modelo do Ollama em segundo plano (um job, com o progresso em MB)."""
        try:
            return dataclasses.asdict(jobs.iniciar("modelo", pedido.model_dump()))
        except Ocupado as e:
            raise HTTPException(409, {"mensagem": str(e), "job": dataclasses.asdict(e.job)}) from e

    @rotas.get("/estimativa/classificacao")
    def estimativa() -> dict[str, Any]:
        """Quanto falta classificar, pelo tempo mediano por documento das execuções anteriores."""
        from ..armazenamento import ARQUIVO, ler_documentos
        from ..classificacao.executor import textos_para_classificar
        from ..classificacao.resultado import PASTA, Resultado

        cfg = projeto.config
        documentos = 0
        if (projeto.dados / ARQUIVO).exists():
            docs = ler_documentos(projeto.dados / ARQUIVO)
            documentos = len(
                textos_para_classificar(docs, [cfg.recorte.idioma_exibicao, cfg.recorte.idioma_analise])[0]
            )
        r = Resultado.ler(projeto.dados / PASTA, cfg.modelos.classificacao.modelo, projeto.codebook.hash())
        classificados = r.classificados if r else 0
        pendentes = max(0, documentos - classificados)
        por_doc = r.segundos_por_documento if r else None
        return {
            "modelo": cfg.modelos.classificacao.modelo,
            "documentos": documentos,
            "classificados": classificados,
            "pendentes": pendentes,
            "segundos_por_documento": por_doc,
            "estimativa_s": round(por_doc * pendentes / max(1, cfg.modelos.classificacao.concorrencia))
            if por_doc is not None
            else None,
        }

    @rotas.get("/revistas")
    def revistas(busca: str = "", area: str = "", issn: str = "") -> list[dict[str, Any]]:
        """As revistas correntes do SciELO Brasil (o retrato empacotado), por nome, acrônimo, ISSN ou área; com
        `issn`, só as desses ISSNs (separados por vírgula), na ordem pedida."""
        from ..fontes import revistas as retrato

        if issn:
            achadas = [retrato.resolver(i) for i in issn.split(",") if i.strip()]
            lista = [r for r in achadas if r is not None]
        else:
            lista = retrato.buscar(busca, area)[:50]
        return [{"issn": r.issn, "acronimo": r.acronimo, "titulo": r.titulo, "areas": list(r.areas)} for r in lista]

    @rotas.get("/configuracao")
    def configuracao() -> dict[str, Any]:
        """O `mapa.yaml`, com os valores padrão preenchidos."""
        return projeto.config.model_dump(mode="json")

    @rotas.patch("/configuracao", dependencies=[Depends(conferir_origem)])
    def mudar_configuracao(parcial: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
        """Muda parte do `mapa.yaml` (os campos enviados), sem perder os comentários."""
        from ..edicao import editar_yaml

        _livre()
        try:
            novo = editar_yaml(projeto.raiz / "mapa.yaml", parcial, ConfigProjeto.model_validate)
        except ErroConfig as e:
            raise HTTPException(422, str(e)) from e
        projeto._config = novo
        return novo.model_dump(mode="json")

    @rotas.get("/codebook")
    def codebook() -> dict[str, Any]:
        """O `codebook.yaml` e o hash que identifica a versão."""
        cb = projeto.codebook
        return {**cb.model_dump(mode="json"), "hash": cb.hash()}

    @rotas.put("/codebook", dependencies=[Depends(conferir_origem)])
    def mudar_codebook(corpo: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
        """Troca o codebook inteiro, sem perder os comentários do que continua igual."""
        from ..edicao import editar_yaml

        _livre()
        corpo = {k: v for k, v in corpo.items() if k != "hash"}
        try:
            novo = editar_yaml(projeto.raiz / "codebook.yaml", corpo, Codebook.model_validate, substituir=True)
        except ErroConfig as e:
            raise HTTPException(422, str(e)) from e
        projeto._codebook = novo
        return {**novo.model_dump(mode="json"), "hash": novo.hash()}

    return rotas
