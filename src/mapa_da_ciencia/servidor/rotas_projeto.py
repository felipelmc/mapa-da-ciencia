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
  (`edicao.py`), validados antes de ir para o disco, e recusados enquanto uma etapa roda;
- `GET` e `PATCH /api/rotulos`: os rótulos dos tópicos e dos macrotemas (o atual, a fonte e a entrada do
  `rotulos.yaml`), e as mudanças no `rotulos.yaml` (`null` tira uma entrada), que a etapa de tópicos aplica com
  `aplicar_rotulos` (sem refazer os tópicos nem chamar o modelo).
"""

from __future__ import annotations

import dataclasses
import io
import re
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Codebook, ConfigProjeto, ErroConfig
from ..llm.base import ErroProvedor
from ..manifesto import estados_das_etapas
from ..projeto import Projeto
from ..trava_etapas import mensagem as mensagem_da_trava
from .jobs import Jobs, Ocupado, fora_do_painel
from .origem import conferir_origem

NOME_MODELO = re.compile(r"^[\w.:/-]{1,80}$")


class PedidoDownload(BaseModel):
    modelo: str = Field(pattern=NOME_MODELO.pattern)


class RotuloEditado(BaseModel):
    """O rótulo e a descrição de um tópico (ou macrotema), escritos à mão no editor do painel."""

    model_config = ConfigDict(extra="forbid")
    rotulo: str = Field(min_length=1, max_length=80)
    descricao: str = Field("", max_length=1000)


class PedidoRotulos(BaseModel):
    """O que muda no `rotulos.yaml`: por número, o rótulo novo, ou `null` para voltar ao do modelo."""

    model_config = ConfigDict(extra="forbid")
    topicos: dict[int, RotuloEditado | None] = Field(default_factory=dict)
    macrotemas: dict[int, RotuloEditado | None] = Field(default_factory=dict)


CABECALHO_ROTULOS = """\
# rotulos.yaml: rótulos dos tópicos e dos macrotemas escritos à mão (aqui ou pelo editor do painel).
# Cada entrada vale para o número do tópico (ou do macrotema) que aparece no painel, tem prioridade sobre o modelo e
# continua valendo quando os tópicos são refeitos. `mapa topicos --aplicar-rotulos` aplica sem refazer os tópicos.
"""


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


def rotas_projeto(projeto: Projeto, jobs: Jobs) -> APIRouter:
    rotas = APIRouter(prefix="/api", tags=["projeto"])

    def _livre() -> None:
        if (ativo := jobs.ativo()) is not None:
            raise HTTPException(409, f"Espere a etapa {ativo.etapa} terminar (ou cancele-a) antes de mudar o projeto.")
        if (dono := fora_do_painel(projeto)) is not None:
            raise HTTPException(409, mensagem_da_trava(projeto, dono))

    @rotas.get("/projeto/etapas")
    def etapas() -> dict[str, Any]:
        """O estado de cada etapa do pipeline, para a linha de metrô da vista Projeto. Com uma etapa rodando fora do
        painel (no terminal ou num notebook), `em_andamento` diz qual, onde e desde quando."""
        estados = estados_das_etapas(projeto)
        if (dono := fora_do_painel(projeto)) is not None:
            estados["em_andamento"] = dono | {"mensagem": mensagem_da_trava(projeto, dono)}
        return estados

    @rotas.get("/projeto/em-andamento")
    def em_andamento() -> dict[str, Any]:
        """Só a etapa que roda fora do painel (`em_andamento`, ou `null`), sem o estado das etapas: uma consulta leve,
        que a vista Projeto faz a cada poucos segundos para notar uma etapa que começou no terminal."""
        dono = fora_do_painel(projeto)
        return {"em_andamento": dono | {"mensagem": mensagem_da_trava(projeto, dono)} if dono is not None else None}

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
            # o corpo traz os padrões que a leitura preencheu (`exemplos: []`…): eles não vão para o arquivo
            novo = editar_yaml(
                projeto.raiz / "codebook.yaml", corpo, Codebook.model_validate, substituir=True, omitir_vazios=True
            )
        except ErroConfig as e:
            raise HTTPException(422, str(e)) from e
        projeto._codebook = novo
        return {**novo.model_dump(mode="json"), "hash": novo.hash()}

    def _resultado_dos_topicos():
        from ..topicos.resultado import PASTA, Resultado

        r = Resultado.ler(projeto.dados / PASTA)
        if r is None:
            raise HTTPException(404, "O projeto ainda não tem tópicos: rode a etapa Tópicos antes dos rótulos.")
        return r

    @rotas.get("/rotulos")
    def rotulos() -> dict[str, Any]:
        """Os rótulos dos tópicos e dos macrotemas: o atual, a fonte (`llm`, `palavras` ou `manual`), as palavras-chave
        e a entrada do `rotulos.yaml`; `pendentes` conta as entradas do arquivo ainda não aplicadas."""
        from ..topicos.aplicar import rotulos_pendentes
        from ..topicos.rotulos import ler_manuais

        r = _resultado_dos_topicos()
        try:
            manuais = ler_manuais(projeto.raiz)
        except ErroConfig as e:
            raise HTTPException(422, str(e)) from e

        def entrada(grupo: dict, i: int) -> dict[str, str] | None:
            return grupo[i].model_dump() if i in grupo else None

        return {
            "topicos": [
                {
                    "id": t.id,
                    "macro": t.macro,
                    "cor": t.cor,
                    "rotulo": t.rotulo,
                    "descricao": t.descricao,
                    "fonte": t.rotulo_fonte,
                    "palavras": [p for p, _ in t.palavras[:10]],
                    "n_nucleo": t.n_nucleo,
                    "manual": entrada(manuais.topicos, t.id),
                }
                for t in r.topicos
            ],
            "macrotemas": [
                {
                    "id": m.id,
                    "cor": m.cor,
                    "rotulo": m.rotulo,
                    "descricao": m.descricao,
                    "fonte": m.rotulo_fonte,
                    "topicos": m.topicos,
                    "manual": entrada(manuais.macrotemas, m.id),
                }
                for m in r.macrotemas
            ],
            "pendentes": rotulos_pendentes(r, manuais),
        }

    @rotas.patch("/rotulos", dependencies=[Depends(conferir_origem)])
    def mudar_rotulos(pedido: PedidoRotulos) -> dict[str, Any]:
        """Grava as mudanças no `rotulos.yaml`, sem perder os comentários, e devolve os rótulos (`rotulos()`) com
        `avisos` de acentos que parecem perdidos (pelo vocabulário do tópico; a gravação não é recusada por isso)."""
        from ..edicao import _sem_vazios, _yaml, editar_yaml
        from ..topicos.rotulos import ARQUIVO_MANUAL, _Manuais, acentos_perdidos

        _livre()
        r = _resultado_dos_topicos()
        ids = {"topicos": {t.id for t in r.topicos}, "macrotemas": {m.id for m in r.macrotemas}}
        nomes = {"topicos": "tópico", "macrotemas": "macrotema"}
        faltam = [f"{nomes[g]} {i}" for g in ids for i in getattr(pedido, g) if i not in ids[g]]
        if faltam:
            raise HTTPException(422, f"Não há {', '.join(faltam)} nos tópicos atuais.")
        # uma descrição vazia não vai para o arquivo (e tira a que existia); `null` tira a entrada
        parcial = {
            g: {i: None if e is None else {"rotulo": e.rotulo.strip(), "descricao": e.descricao.strip() or None}
                for i, e in getattr(pedido, g).items()}
            for g in ids
            if getattr(pedido, g)
        }  # fmt: skip
        arquivo = projeto.raiz / ARQUIVO_MANUAL
        try:
            if arquivo.exists():
                editar_yaml(arquivo, parcial, _Manuais.model_validate, omitir_vazios=True)
            else:  # o primeiro rótulo à mão: o arquivo nasce com um cabeçalho que explica o formato
                conteudo = {g: d for g, d in _sem_vazios(parcial).items() if d}
                _Manuais.model_validate(conteudo)
                texto = io.StringIO()
                if conteudo:
                    _yaml().dump(conteudo, texto)
                arquivo.write_text(CABECALHO_ROTULOS + texto.getvalue(), encoding="utf-8")
        except (ErroConfig, ValidationError) as e:
            raise HTTPException(422, str(e)) from e
        palavras = {t.id: [p for p, _ in t.palavras] for t in r.topicos}
        avisos = [
            f"Tópico {i}: “{sem}” perdeu o acento? As palavras do tópico têm “{com}”."
            for i, e in pedido.topicos.items()
            if e is not None
            for sem, com in acentos_perdidos(f"{e.rotulo} {e.descricao}", palavras.get(i, [])).items()
        ]
        return {**rotulos(), "avisos": avisos}

    return rotas
