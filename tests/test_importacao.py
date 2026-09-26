"""A CLI e a API abrem rápido: as bibliotecas numéricas (o numba leva segundos só para importar e
compilar) carregam apenas quando uma etapa precisa delas."""

import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).parents[1] / "src"
PESADAS = ("numpy", "scipy", "sklearn", "umap", "numba", "pynndescent")


def test_cli_e_api_nao_carregam_bibliotecas_numericas():
    codigo = (
        "import sys, mapa_da_ciencia.cli, mapa_da_ciencia.api\n"
        f"print(','.join(m for m in {PESADAS!r} if m in sys.modules))"
    )
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )
    assert r.stdout.strip() == ""
