"""Em que ponto está cada etapa do projeto: pendente, em dia, incompleta ou desatualizada.

Usado pela linha de metrô do painel (`GET /api/projeto/etapas`) e pelo `mapa status`.
"""

from __future__ import annotations

from typing import Any

from .manifesto import status_das_etapas
from .projeto import Projeto


def estados_das_etapas(projeto: Projeto) -> dict[str, dict[str, Any]]:
    """Cada etapa: `pendente` (nunca rodou), `em_dia`, `incompleta` (a classificação parou antes do fim, a amostra
    não foi toda codificada) ou `desatualizada` (o corpus, o codebook ou as correções mudaram depois), com a última
    execução. Nas redes desatualizadas, `mudou` diz o quê."""
    from .armazenamento import ARQUIVO, ler_documentos
    from .classificacao.pipeline import classificacao_em_dia
    from .geografia.pipeline import geografia_em_dia
    from .redes.pipeline import o_que_mudou, redes_em_dia
    from .topicos.resultado import PASTA, Resultado, assinatura_corpus
    from .validacao.amostra import codificacoes
    from .validacao.amostra import ler as ler_amostra

    ultimas = status_das_etapas(projeto)
    tem_corpus = (projeto.dados / ARQUIVO).exists()
    topicos: bool | None = None
    if tem_corpus and (r := Resultado.ler(projeto.dados / PASTA)) is not None:
        topicos = r.assinatura == assinatura_corpus([d.id for d in ler_documentos(projeto.dados / ARQUIVO)])
    amostra = ler_amostra(projeto)
    codificados = len({c["doc"] for c in codificacoes(projeto)} & set(amostra.docs)) if amostra else 0
    classificacao: bool | str | None = None
    if tem_corpus:
        from .classificacao.resultado import PASTA as PASTA_CLS
        from .classificacao.resultado import Resultado as ResultadoCls

        cfg = projeto.config.modelos.classificacao
        r_cls = ResultadoCls.ler(projeto.dados / PASTA_CLS, cfg.modelo, projeto.codebook.hash())
        em_dia_cls = classificacao_em_dia(projeto)
        classificacao = "incompleta" if r_cls is not None and r_cls.parcial else em_dia_cls
    em_dia: dict[str, bool | str | None] = {
        "coleta": True if tem_corpus else None,
        "topicos": topicos,
        "geografia": geografia_em_dia(projeto) if tem_corpus else None,
        "redes": redes_em_dia(projeto) if tem_corpus else None,
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
    if em_dia["redes"] is False:
        saida["redes"]["mudou"] = o_que_mudou(projeto)
    return saida
