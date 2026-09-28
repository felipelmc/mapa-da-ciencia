"""O desenho das redes: posições fixas e reprodutíveis para cada nó.

Cada componente conectado é desenhado à parte (`spring_layout` do networkx, semente 7, pelos pesos), com tamanho
proporcional à raiz do número de nós; pares viram um segmento. Os componentes são empacotados em prateleiras, do
maior para o menor, e o conjunto é normalizado para [-1, 1], com quatro casas decimais: o mesmo corpus dá sempre as
mesmas coordenadas (os nós entram em ordem de id).
"""

from __future__ import annotations

import math

SEMENTE = 7


def desenhar(grafo) -> dict[str, tuple[float, float]]:
    """Posições de todos os nós do grafo (networkx), em [-1, 1]."""
    import networkx as nx

    componentes = sorted((sorted(c) for c in nx.connected_components(grafo)), key=lambda c: (-len(c), c[0]))
    blocos = []
    for nos in componentes:
        n = len(nos)
        if n == 1:
            pos = {nos[0]: (0.0, 0.0)}
        elif n == 2:
            pos = {nos[0]: (-0.5, 0.0), nos[1]: (0.5, 0.0)}
        else:
            sub = nx.Graph()
            sub.add_nodes_from(nos)
            sub.add_weighted_edges_from(
                sorted((a, b, d.get("peso", 1.0)) for a, b, d in grafo.subgraph(nos).edges(data=True)), weight="peso"
            )
            pos = {k: (float(v[0]), float(v[1])) for k, v in nx.spring_layout(sub, seed=SEMENTE, weight="peso").items()}
        xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        amplitude = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
        escala = math.sqrt(n) / amplitude
        blocos.append({k: ((x - cx) * escala, (y - cy) * escala) for k, (x, y) in pos.items()})
    # prateleiras: largura total ~ raiz da área somada
    tamanhos = [max(1.0, _largura(b)) for b in blocos]
    largura_total = math.sqrt(sum(t * t for t in tamanhos)) * 1.6
    posicoes: dict[str, tuple[float, float]] = {}
    x = y = altura = 0.0
    for bloco, t in zip(blocos, tamanhos, strict=True):
        margem = t * 0.15 + 0.5
        if x > 0 and x + t > largura_total:
            x, y, altura = 0.0, y + altura, 0.0
        for k, (px, py) in bloco.items():
            posicoes[k] = (px + x + t / 2, py + y + t / 2)
        x += t + margem
        altura = max(altura, t + margem)
    if not posicoes:
        return {}
    xs, ys = [p[0] for p in posicoes.values()], [p[1] for p in posicoes.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    meia = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 2
    return {k: (round((px - cx) / meia, 4), round((py - cy) / meia, 4)) for k, (px, py) in posicoes.items()}


def _largura(bloco: dict[str, tuple[float, float]]) -> float:
    xs, ys = [p[0] for p in bloco.values()], [p[1] for p in bloco.values()]
    return max(max(xs) - min(xs), max(ys) - min(ys))
