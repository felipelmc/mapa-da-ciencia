"""Tendências dos tópicos de um projeto, com a binomial pura e com a quase-binomial lado a lado (ADR 0009).

Lê `saida/dados/topicos.json` (as séries por ano) e mostra, para cada tópico, a dispersão φ, a direção em cada
modelo e a variação em pontos percentuais. O resumo no fim diz quantos tópicos cada modelo marca como em alta ou
em queda.

Uso (da raiz do repo):
    uv run python scripts/tendencias.py projetos/cp-scielo
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from mapa_da_ciencia.topicos.tendencia import tendencia


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("projeto", type=Path)
    args = parser.parse_args()
    dados = json.loads((args.projeto / "saida" / "dados" / "topicos.json").read_text(encoding="utf-8"))
    anos, total = dados["anos"], dados["total_por_ano"]
    contagem = {"binomial": Counter(), "quase": Counter()}
    print("| tópico | n | φ | binomial | quase | p.p. no período |")
    print("|---|---|---|---|---|---|")
    for t in sorted(dados["topicos"], key=lambda t: -t["n"]):
        b = tendencia(t["serie"]["n"], total, anos, dispersao="binomial")
        q = tendencia(t["serie"]["n"], total, anos, dispersao="quase")
        contagem["binomial"][b.direcao] += 1
        contagem["quase"][q.direcao] += 1
        phi = f"{q.dispersao:.2f}" if q.dispersao is not None else "—"
        pp = f"{q.pp_periodo:+.2f}" if q.pp_periodo is not None else "—"
        print(f"| {t['rotulo']} | {t['n']} | {phi} | {b.direcao} | {q.direcao} | {pp} |")
    for modelo, c in contagem.items():
        print(
            f"\n{modelo}: {c['alta']} em alta, {c['queda']} em queda, {c['estavel']} estáveis, "
            f"{c['insuficiente']} sem dados suficientes"
        )


if __name__ == "__main__":
    main()
