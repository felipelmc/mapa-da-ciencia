"""Manifesto de execução: o registro reprodutível de cada vez que uma etapa roda.

Cada execução grava `execucoes/<AAAAMMDD-HHMMSS>-<etapa>.json` com versões, hashes da
configuração e do codebook, modelos usados, parâmetros, contagens e duração. É daqui
que saem o `mapa status` e a página de metodologia do site publicado.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mapa_da_ciencia import __version__
from mapa_da_ciencia.projeto import ARQUIVO_CONFIG, ETAPAS, Projeto


def _hash_arquivo(caminho: Path) -> str | None:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()[:16] if caminho.exists() else None


def registrar_execucao(
    projeto: Projeto,
    etapa: str,
    *,
    inicio: datetime,
    fim: datetime,
    contagens: dict[str, int] | None = None,
    modelos: dict[str, str] | None = None,
    parametros: dict[str, Any] | None = None,
) -> Path:
    """Grava o manifesto de uma execução concluída e devolve o caminho do arquivo."""
    if etapa not in ETAPAS:
        raise ValueError(f"etapa desconhecida: {etapa}")
    manifesto = {
        "etapa": etapa,
        "versao_pacote": __version__,
        "python": sys.version.split()[0],
        "plataforma": platform.platform(),
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "duracao_s": round((fim - inicio).total_seconds(), 3),
        "hash_config": _hash_arquivo(projeto.raiz / ARQUIVO_CONFIG),
        "hash_codebook": projeto.codebook.hash() if etapa in ("classificacao", "validacao") else None,
        "modelos": modelos or {},
        "parametros": parametros or {},
        "contagens": contagens or {},
    }
    projeto.execucoes.mkdir(exist_ok=True)
    carimbo = fim.astimezone(UTC).strftime("%Y%m%d-%H%M%S")
    arquivo = projeto.execucoes / f"{carimbo}-{etapa}.json"
    arquivo.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return arquivo


def ultima_execucao(
    projeto: Projeto, etapa: str, filtro: Callable[[dict[str, Any]], bool] | None = None
) -> dict[str, Any] | None:
    """O manifesto mais recente da etapa (que passe no `filtro`, se houver), ou `None` se ela nunca rodou."""
    for arquivo in sorted(projeto.execucoes.glob(f"*-{etapa}.json"), reverse=True):
        m = json.loads(arquivo.read_text(encoding="utf-8"))
        if filtro is None or filtro(m):
            return m
    return None


def da_classificacao_principal(projeto: Projeto) -> Callable[[dict[str, Any]], bool]:
    """Filtro das execuções que contam como "a" classificação do projeto: o modelo principal, e não uma rodada de
    comparação (`--modelo X`) nem só a amostra. Funciona também com os manifestos antigos."""
    principal = projeto.config.modelos.classificacao.modelo.removesuffix(":latest")

    def filtro(m: dict[str, Any]) -> bool:
        modelo = (m.get("modelos") or {}).get("classificacao", "").split("@", 1)[0].removesuffix(":latest")
        return modelo == principal and not (m.get("parametros") or {}).get("somente_amostra")

    return filtro


def status_das_etapas(projeto: Projeto) -> dict[str, dict[str, Any] | None]:
    return {
        etapa: ultima_execucao(
            projeto, etapa, da_classificacao_principal(projeto) if etapa == "classificacao" else None
        )
        for etapa in ETAPAS
    }


def estados_das_etapas(projeto: Projeto) -> dict[str, dict[str, Any]]:
    """Cada etapa: `pendente` (nunca rodou), `em_dia`, `incompleta` (a classificação parou antes do fim, a amostra
    não foi toda codificada) ou `desatualizada` (o corpus, o codebook ou as correções mudaram depois), com a última
    execução."""
    from mapa_da_ciencia.armazenamento import ARQUIVO, ler_documentos
    from mapa_da_ciencia.classificacao.pipeline import classificacao_em_dia
    from mapa_da_ciencia.geografia.pipeline import geografia_em_dia
    from mapa_da_ciencia.topicos.resultado import PASTA, Resultado, assinatura_corpus
    from mapa_da_ciencia.validacao.amostra import documentos_completos
    from mapa_da_ciencia.validacao.amostra import ler as ler_amostra

    ultimas = status_das_etapas(projeto)
    tem_corpus = (projeto.dados / ARQUIVO).exists()
    topicos: bool | None = None
    if tem_corpus and (r := Resultado.ler(projeto.dados / PASTA)) is not None:
        topicos = r.assinatura == assinatura_corpus([d.id for d in ler_documentos(projeto.dados / ARQUIVO)])
    amostra = ler_amostra(projeto)
    codificados = len(documentos_completos(projeto) & set(amostra.docs)) if amostra else 0
    classificacao: bool | str | None = None
    if tem_corpus:
        from mapa_da_ciencia.classificacao.resultado import PASTA as PASTA_CLS
        from mapa_da_ciencia.classificacao.resultado import Resultado as ResultadoCls

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
