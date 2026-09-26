"""As etapas que o painel roda como jobs, com as opções que cada uma aceita.

Cada etapa é uma função `(projeto, opções, progresso) -> resumo`, a mesma que a CLI chama. As opções chegam da
interface em JSON e são validadas aqui (campos desconhecidos são recusados). Os testes trocam este registro por
etapas falsas, que emitem progresso sob controle.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..progresso import Progresso
from ..projeto import Projeto


class _Opcoes(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpcoesColetaPainel(_Opcoes):
    limite: int | None = Field(None, ge=1, description="Só os primeiros N documentos (um piloto).")
    atualizar: bool = Field(False, description="Busca de novo as listas de artigos, em vez do cache.")
    sem_openalex: bool = False


class OpcoesTopicosPainel(_Opcoes):
    sem_rotulos: bool = False
    refazer_embeddings: bool = False


class OpcoesGeografiaPainel(_Opcoes):
    pass


class OpcoesClassificacaoPainel(_Opcoes):
    estimar: bool = False
    limite: int | None = Field(None, ge=1)
    somente_amostra: bool = False
    modelo: str | None = None


def _coleta(p: Projeto, o: dict[str, Any], progresso: Progresso) -> Any:
    from ..coleta import OpcoesColeta, coletar

    return coletar(p, OpcoesColeta(**OpcoesColetaPainel(**o).model_dump()), progresso)


def _topicos(p: Projeto, o: dict[str, Any], progresso: Progresso) -> Any:
    from ..topicos.pipeline import OpcoesTopicos, gerar_topicos

    return gerar_topicos(p, OpcoesTopicos(**OpcoesTopicosPainel(**o).model_dump()), progresso)


def _geografia(p: Projeto, o: dict[str, Any], progresso: Progresso) -> Any:
    from ..geografia.pipeline import gerar_geografia

    OpcoesGeografiaPainel(**o)
    return gerar_geografia(p, progresso)


def _classificacao(p: Projeto, o: dict[str, Any], progresso: Progresso) -> Any:
    from ..classificacao.pipeline import OpcoesClassificacao, classificar

    return classificar(p, OpcoesClassificacao(**OpcoesClassificacaoPainel(**o).model_dump()), progresso)


OPCOES = {
    "coleta": OpcoesColetaPainel,
    "topicos": OpcoesTopicosPainel,
    "geografia": OpcoesGeografiaPainel,
    "classificacao": OpcoesClassificacaoPainel,
}
ETAPAS_DO_PAINEL = {"coleta": _coleta, "topicos": _topicos, "geografia": _geografia, "classificacao": _classificacao}
