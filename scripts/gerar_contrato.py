"""Regenera os JSON Schemas do contrato e os dados de exemplo versionados no repositório.

Uso (da raiz do repo):
    uv run python scripts/gerar_contrato.py            # escreve contrato/schema e contrato/exemplo
    uv run python scripts/gerar_contrato.py --checar   # só confere se estão em dia (usado no CI)

Rode sempre que mudar `src/mapa_da_ciencia/contrato/modelos.py` ou o gerador de exemplo.
Depois, regenere os tipos do frontend (`npm run tipos` em frontend/).
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

from mapa_da_ciencia.contrato.exemplo import gerar_exemplo
from mapa_da_ciencia.contrato.exportar import escrever_dados, escrever_schemas

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = RAIZ / "contrato" / "schema"
EXEMPLO = RAIZ / "contrato" / "exemplo" / "dados"


def gerar(schema: Path, exemplo: Path) -> None:
    for pasta in (schema, exemplo):
        shutil.rmtree(pasta, ignore_errors=True)
    escrever_schemas(schema)
    arquivos, fragmentos = gerar_exemplo()
    escrever_dados(exemplo, arquivos, fragmentos)


def iguais(a: Path, b: Path) -> list[str]:
    """Arquivos que diferem (ou só existem de um lado) entre duas pastas, recursivamente."""
    cmp = filecmp.dircmp(a, b)
    difs = [*cmp.left_only, *cmp.right_only, *cmp.diff_files]
    for sub in cmp.common_dirs:
        difs += [f"{sub}/{d}" for d in iguais(a / sub, b / sub)]
    return difs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--checar", action="store_true", help="não escreve; falha se os arquivos estiverem desatualizados")
    args = ap.parse_args()
    if not args.checar:
        gerar(SCHEMA, EXEMPLO)
        print(f"Schemas em {SCHEMA.relative_to(RAIZ)} e exemplo em {EXEMPLO.relative_to(RAIZ)} regenerados.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        gerar(t / "schema", t / "exemplo")
        difs = [f"schema/{d}" for d in iguais(SCHEMA, t / "schema")]
        difs += [f"exemplo/{d}" for d in iguais(EXEMPLO, t / "exemplo")]
    if difs:
        print("Contrato desatualizado; rode `uv run python scripts/gerar_contrato.py`. Diferenças:", *difs, sep="\n  ")
        return 1
    print("Contrato em dia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
