"""Perfis de modelos por quantidade de memória da máquina.

O perfil só define os modelos padrão de um projeto novo. Qualquer modelo pode ser
trocado no `mapa.yaml`. Tamanhos conferidos na biblioteca do Ollama em 2026-09-25.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import psutil

NomePerfil = Literal["leve", "padrao", "forte"]


@dataclass(frozen=True)
class Perfil:
    nome: NomePerfil
    descricao: str
    ram_minima_gb: int
    embeddings: str
    classificacao: str
    rotulos: str
    download_gb: float  # soma dos modelos distintos do perfil


PERFIS: dict[NomePerfil, Perfil] = {
    "leve": Perfil(
        "leve",
        "Máquinas com 8 a 16 GB de memória.",
        8,
        embeddings="qwen3-embedding:0.6b",
        classificacao="qwen3.5:4b",
        rotulos="qwen3.5:4b",
        download_gb=0.6 + 3.4,
    ),
    "padrao": Perfil(
        "padrao",
        "Máquinas com 16 a 32 GB de memória, ou a GPU T4 do Colab.",
        16,
        embeddings="qwen3-embedding:0.6b",
        classificacao="qwen3.5:9b",
        rotulos="qwen3.5:9b",
        download_gb=0.6 + 6.6,
    ),
    "forte": Perfil(
        "forte",
        "Máquinas com 32 GB ou mais: rótulos com um modelo maior.",
        32,
        embeddings="qwen3-embedding:0.6b",
        classificacao="qwen3.5:9b",
        rotulos="gemma4:26b",
        download_gb=0.6 + 6.6 + 17.0,
    ),
}


def ram_total_gb() -> float:
    return psutil.virtual_memory().total / 1024**3


def sugerir_perfil(ram_gb: float | None = None) -> Perfil:
    """O perfil mais forte cuja memória mínima cabe na máquina (nunca menos que `leve`)."""
    ram = ram_total_gb() if ram_gb is None else ram_gb
    escolhido = PERFIS["leve"]
    for perfil in PERFIS.values():
        if ram >= perfil.ram_minima_gb:
            escolhido = perfil
    return escolhido
