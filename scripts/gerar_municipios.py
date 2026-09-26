"""Gera `src/mapa_da_ciencia/geografia/dados/municipios.csv` a partir da API de localidades do IBGE.

Uma requisição (`/api/v1/localidades/municipios?view=nivelado`), com código, nome e UF de cada município. A geografia
usa a tabela para achar a UF de uma cidade brasileira quando o nome é único no país.

    uv run python scripts/gerar_municipios.py
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
DESTINO = Path(__file__).resolve().parents[1] / "src/mapa_da_ciencia/geografia/dados/municipios.csv"


def main() -> None:
    resposta = httpx.get(URL, params={"view": "nivelado"}, timeout=60)
    resposta.raise_for_status()
    linhas = sorted((str(m["municipio-id"]), m["municipio-nome"], m["UF-sigla"]) for m in resposta.json())
    saida = io.StringIO()
    saida.write("# gerado por scripts/gerar_municipios.py (IBGE, API de localidades); não editar à mão\n")
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(["codigo", "nome", "uf"])
    escritor.writerows(linhas)
    DESTINO.write_text(saida.getvalue(), encoding="utf-8")
    print(f"{len(linhas)} municípios em {DESTINO}")


if __name__ == "__main__":
    main()
