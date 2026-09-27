"""Regenera os JSON Schemas do contrato, os dados de exemplo e os casos de referência versionados no repositório.

Uso (da raiz do repo):
    uv run python scripts/gerar_contrato.py            # escreve contrato/schema, exemplo, exemplo-publicado e casos
    uv run python scripts/gerar_contrato.py --checar   # só confere se estão em dia (usado no CI)

Rode sempre que mudar `src/mapa_da_ciencia/contrato/modelos.py` ou o gerador de exemplo.
Depois, regenere os tipos do frontend (`npm run tipos` em frontend/).
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
import tempfile
from pathlib import Path

from mapa_da_ciencia.contrato.exemplo import gerar_exemplo
from mapa_da_ciencia.contrato.exportar import escrever_dados, escrever_schemas
from mapa_da_ciencia.topicos.tendencia import casos_de_referencia

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = RAIZ / "contrato" / "schema"
EXEMPLO = RAIZ / "contrato" / "exemplo" / "dados"
PUBLICADO = RAIZ / "contrato" / "exemplo-publicado" / "dados"
CASOS = RAIZ / "contrato" / "casos"


def gerar(schema: Path, exemplo: Path, casos: Path, publicado: Path) -> None:
    from datetime import UTC, datetime

    from mapa_da_ciencia.publicar import filtrar_dados

    for pasta in (schema, exemplo, casos, publicado):
        shutil.rmtree(pasta, ignore_errors=True)
    escrever_schemas(schema)
    arquivos, fragmentos = gerar_exemplo()
    escrever_dados(exemplo, arquivos, fragmentos)
    # o mesmo exemplo passado pelas regras do `mapa publicar` (o site PUBLICADO dos testes e2e)
    shutil.copytree(exemplo, publicado)
    filtrar_dados(publicado, em=datetime(2026, 9, 26, 12, 0, tzinfo=UTC))
    casos.mkdir(parents=True)
    texto = json.dumps(casos_de_referencia(), ensure_ascii=False, indent=1)
    (casos / "tendencia.json").write_text(texto + "\n", encoding="utf-8")


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
        gerar(SCHEMA, EXEMPLO, CASOS, PUBLICADO)
        print(f"Schemas, exemplo e casos regenerados em {SCHEMA.parent.relative_to(RAIZ)}/.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        gerar(t / "schema", t / "exemplo", t / "casos", t / "publicado")
        difs = [f"schema/{d}" for d in iguais(SCHEMA, t / "schema")]
        difs += [f"exemplo/{d}" for d in iguais(EXEMPLO, t / "exemplo")]
        difs += (
            [f"exemplo-publicado/{d}" for d in iguais(PUBLICADO, t / "publicado")]
            if PUBLICADO.exists()
            else ["exemplo-publicado/"]
        )
        difs += [f"casos/{d}" for d in iguais(CASOS, t / "casos")] if CASOS.exists() else ["casos/"]
    if difs:
        print("Contrato desatualizado; rode `uv run python scripts/gerar_contrato.py`. Diferenças:", *difs, sep="\n  ")
        return 1
    print("Contrato em dia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
