"""Calibra os parâmetros dos tópicos num projeto: grade de UMAP × HDBSCAN, com 3 sementes.

Para cada combinação mede o número de tópicos, a fração de ruído (documentos sem tópico no HDBSCAN), o
tamanho do maior tópico e a estabilidade (ARI médio entre os pares de sementes, sobre os documentos que
estão no núcleo nas duas execuções). Os resultados embasam os padrões da seção `topicos:` (ADR 0007).

Usa os embeddings em cache do projeto (calcula os que faltarem) e o cache das reduções: rodar de novo é rápido.
Não grava nada do pipeline (nem identidade, nem tópicos).

Uso (da raiz do repo):
    uv run python scripts/calibrar_topicos.py projetos/cp-scielo
    uv run python scripts/calibrar_topicos.py projetos/cp-scielo --vizinhos 15 30 --saida calibracao.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

from mapa_da_ciencia.api import abrir, embeddings
from mapa_da_ciencia.topicos.agrupamento import agrupar, min_cluster_size_automatico
from mapa_da_ciencia.topicos.reducao import assinatura_dados, reduzir
from mapa_da_ciencia.topicos.vizinhos import knn_exato

SEMENTES = (42, 7, 2024)


def ari_entre(rotulos: list[np.ndarray]) -> float:
    valores = []
    for a, b in itertools.combinations(rotulos, 2):
        ambos = (a != -1) & (b != -1)
        if ambos.sum() > 1:
            valores.append(adjusted_rand_score(a[ambos], b[ambos]))
    return float(np.mean(valores)) if valores else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("projeto", type=Path)
    parser.add_argument("--vizinhos", type=int, nargs="+", default=[15, 30])
    parser.add_argument("--tamanhos", type=int, nargs="+", default=None, help="min_cluster_size (padrão: grade)")
    parser.add_argument("--amostras", type=int, nargs="+", default=[1, 3, 5, 10], help="min_samples")
    parser.add_argument("--saida", type=Path, default=None, help="JSON com todos os resultados")
    args = parser.parse_args()

    p = abrir(args.projeto)
    e = embeddings(p, progresso=False)
    n = len(e.ids)
    automatico = min_cluster_size_automatico(n)
    tamanhos = args.tamanhos or sorted({10, 15, automatico, 30, 40})
    cache = p.dados / "topicos" / "reducoes"
    base = assinatura_dados(e.ids, e.matriz, e.rotulo_modelo)
    print(f"{n} documentos; min_cluster_size automático = {automatico}")

    resultados = []
    k_max = max(args.vizinhos)
    t0 = time.perf_counter()
    knn = knn_exato(e.matriz, k_max)
    print(f"kNN exato (k={k_max}): {time.perf_counter() - t0:.1f} s")
    for vizinhos in args.vizinhos:
        reducoes = []
        for semente in SEMENTES:
            t0 = time.perf_counter()
            coords = reduzir(
                e.matriz,
                (knn[0][:, :vizinhos], knn[1][:, :vizinhos]),
                n_componentes=5,
                n_vizinhos=vizinhos,
                min_dist=0.0,
                semente=semente,
                cache=cache,
                base=base,
            )
            print(f"UMAP 5D, {vizinhos} vizinhos, semente {semente}: {time.perf_counter() - t0:.1f} s")
            reducoes.append(coords)
        for tamanho, amostras, selecao in itertools.product(tamanhos, args.amostras, ("eom", "leaf")):
            t0 = time.perf_counter()
            grupos = [agrupar(c, min_cluster_size=tamanho, min_samples=amostras, selecao=selecao) for c in reducoes]
            principal = grupos[0]
            tamanhos_topicos = np.bincount(principal.rotulos[principal.rotulos >= 0]) if principal.n_topicos else []
            resultados.append(
                {
                    "vizinhos": vizinhos,
                    "min_cluster_size": tamanho,
                    "min_samples": amostras,
                    "selecao": selecao,
                    "topicos": principal.n_topicos,
                    "topicos_sementes": [g.n_topicos for g in grupos],
                    "ruido": round(principal.fracao_ruido, 4),
                    "ruido_sementes": [round(g.fracao_ruido, 4) for g in grupos],
                    "maior_topico": round(float(max(tamanhos_topicos, default=0)) / n, 4),
                    "mediana_topico": int(np.median(tamanhos_topicos)) if len(tamanhos_topicos) else 0,
                    "ari": round(ari_entre([g.rotulos for g in grupos]), 4),
                    "segundos_hdbscan": round((time.perf_counter() - t0) / len(grupos), 2),
                }
            )

    print("\n| viz. | mcs | ms | seleção | tópicos (3 sementes) | ruído | maior | mediana | ARI |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in resultados:
        print(
            f"| {r['vizinhos']} | {r['min_cluster_size']} | {r['min_samples']} | {r['selecao']} | "
            f"{r['topicos']} ({'/'.join(map(str, r['topicos_sementes']))}) | {r['ruido']:.1%} | "
            f"{r['maior_topico']:.1%} | {r['mediana_topico']} | {r['ari']:.3f} |"
        )
    if args.saida:
        args.saida.write_text(json.dumps({"n": n, "resultados": resultados}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
