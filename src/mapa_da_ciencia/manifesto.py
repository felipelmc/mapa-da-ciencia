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


def ultima_execucao(projeto: Projeto, etapa: str) -> dict[str, Any] | None:
    """O manifesto mais recente da etapa, ou `None` se ela nunca rodou."""
    arquivos = sorted(projeto.execucoes.glob(f"*-{etapa}.json"))
    return json.loads(arquivos[-1].read_text(encoding="utf-8")) if arquivos else None


def status_das_etapas(projeto: Projeto) -> dict[str, dict[str, Any] | None]:
    return {etapa: ultima_execucao(projeto, etapa) for etapa in ETAPAS}
