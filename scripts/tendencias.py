"""Tendências dos tópicos de um projeto, com a binomial pura e a quase-binomial (com os quantis da normal e da t) lado a
lado (ADR 0009).

Lê `saida/dados/topicos.json` (as séries por ano) e mostra, para cada tópico, a dispersão φ, a direção em cada
modelo e a variação em pontos percentuais. O resumo no fim diz quantos tópicos cada modelo marca como em alta ou
em queda. A coluna "quase, t" é a regra em uso desde a 2.3.0.

Uso (da raiz do repo):
    uv run python scripts/tendencias.py projetos/cp-scielo
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from mapa_da_ciencia.topicos.tendencia import tendencia

MODELOS = {
    "binomial": {"dispersao": "binomial"},
    "quase, normal": {"dispersao": "quase", "quantil": "normal"},
    "quase, t": {"dispersao": "quase", "quantil": "t"},
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("projeto", type=Path)
    args = parser.parse_args()
    dados = json.loads((args.projeto / "saida" / "dados" / "topicos.json").read_text(encoding="utf-8"))
    anos, total = dados["anos"], dados["total_por_ano"]
    contagem = {nome: Counter() for nome in MODELOS}
    print("| tópico | n | φ | " + " | ".join(MODELOS) + " | p.p. no período |")
    print("|---|---|---|" + "---|" * len(MODELOS) + "---|")
    for t in sorted(dados["topicos"], key=lambda t: -t["n"]):
        resultados = {nome: tendencia(t["serie"]["n"], total, anos, **m) for nome, m in MODELOS.items()}
        for nome, r in resultados.items():
            contagem[nome][r.direcao] += 1
        q = resultados["quase, t"]
        phi = f"{q.dispersao:.2f}" if q.dispersao is not None else "—"
        pp = f"{q.pp_periodo:+.2f}" if q.pp_periodo is not None else "—"
        direcoes = " | ".join(r.direcao for r in resultados.values())
        print(f"| {t['rotulo']} | {t['n']} | {phi} | {direcoes} | {pp} |")
    for nome, c in contagem.items():
        print(
            f"\n{nome}: {c['alta']} em alta, {c['queda']} em queda, {c['estavel']} estáveis, "
            f"{c['insuficiente']} sem dados suficientes"
        )


if __name__ == "__main__":
    main()
