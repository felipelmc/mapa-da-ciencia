"""Recursos da máquina: memória, swap e disco.

O M0 mostrou que carregar um modelo de 17 GB numa máquina de 24 GB, com outros programas
abertos, esgota o swap e trava o computador. Por isso nenhum modelo é carregado sem
passar por `cabe_na_memoria`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import psutil

from mapa_da_ciencia.formatar import gb

GB = 1024**3
MARGEM_PADRAO_GB = 1.5


@dataclass(frozen=True)
class Memoria:
    total_gb: float
    disponivel_gb: float
    swap_usado_gb: float
    swap_total_gb: float


def memoria() -> Memoria:
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()
    return Memoria(vm.total / GB, vm.available / GB, sw.used / GB, sw.total / GB)


def disco_livre_gb(pasta: Path) -> float:
    alvo = pasta if pasta.exists() else Path.home()
    return shutil.disk_usage(alvo).free / GB


@dataclass(frozen=True)
class Folga:
    cabe: bool
    precisa_gb: float
    disponivel_gb: float

    def explicar(self, modelo: str) -> str:
        if self.cabe:
            return f"{modelo} cabe na memória ({gb(self.precisa_gb)} de {gb(self.disponivel_gb)} disponíveis)."
        return (
            f"{modelo} precisa de ~{gb(self.precisa_gb)} e há {gb(self.disponivel_gb)} disponíveis agora. "
            "Feche programas pesados ou escolha um modelo menor (ver `mapa diagnostico`)."
        )


def cabe_na_memoria(
    tamanho_gb: float, *, margem_gb: float = MARGEM_PADRAO_GB, disponivel_gb: float | None = None
) -> Folga:
    """O modelo, mais uma margem para o contexto e o sistema, cabe na memória disponível agora?"""
    disp = memoria().disponivel_gb if disponivel_gb is None else disponivel_gb
    precisa = tamanho_gb + margem_gb
    return Folga(disp >= precisa, precisa, disp)
