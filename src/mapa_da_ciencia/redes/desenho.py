"""O desenho das redes: posições fixas e reprodutíveis para cada nó.

Cada componente conectado é desenhado à parte (`spring_layout` do networkx, semente 7, pelos pesos). O **maior
componente fica em cima**, centrado, com tamanho proporcional à raiz do número de nós: é nele que estão as
comunidades. Os outros vêm embaixo, numa faixa de prateleiras, do maior para o menor, menores (60% da escala) e as
duplas e os trios bem juntos, como contexto; a largura da faixa deixa o desenho perto de 1,6 : 1, a proporção da
vista. O conjunto é normalizado para [-1, 1], com quatro casas decimais, e o eixo y cresce para cima (a vista inverte
para a tela): o mesmo corpus dá sempre as mesmas coordenadas (os nós entram em ordem de id).
"""

from __future__ import annotations

import math

SEMENTE = 7
PEQUENO = 3  # componentes de até 3 nós: desenhados menores e mais juntos
LADO_PEQUENO = 0.5  # a largura de uma dupla ou de um trio, contra ~√n no maior componente
ESCALA_DOS_OUTROS = 0.6  # os componentes fora do maior, em relação a ele
PROPORCAO = 1.6  # largura : altura do desenho, perto da da vista


def _bloco(grafo, nos: list[str], fator: float = 1.0) -> dict[str, tuple[float, float]]:
    """As posições de um componente, centradas em (0, 0), com largura de ~fator·√n (`LADO_PEQUENO` nos pequenos)."""
    import networkx as nx

    n = len(nos)
    if n == 1:
        return {nos[0]: (0.0, 0.0)}
    if n == 2:
        return {nos[0]: (-LADO_PEQUENO / 2, 0.0), nos[1]: (LADO_PEQUENO / 2, 0.0)}
    sub = nx.Graph()
    sub.add_nodes_from(nos)
    sub.add_weighted_edges_from(
        sorted((a, b, d.get("peso", 1.0)) for a, b, d in grafo.subgraph(nos).edges(data=True)), weight="peso"
    )
    pos = {k: (float(v[0]), float(v[1])) for k, v in nx.spring_layout(sub, seed=SEMENTE, weight="peso").items()}
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    amplitude = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    escala = (LADO_PEQUENO if n <= PEQUENO else fator * math.sqrt(n)) / amplitude
    return {k: ((x - cx) * escala, (y - cy) * escala) for k, (x, y) in pos.items()}


def _medidas(bloco: dict[str, tuple[float, float]]) -> tuple[float, float]:
    xs, ys = [p[0] for p in bloco.values()], [p[1] for p in bloco.values()]
    return max(xs) - min(xs), max(ys) - min(ys)


def desenhar(grafo) -> dict[str, tuple[float, float]]:
    """Posições de todos os nós do grafo (networkx), em [-1, 1], com o maior componente em cima."""
    import networkx as nx

    componentes = sorted((sorted(c) for c in nx.connected_components(grafo)), key=lambda c: (-len(c), c[0]))
    if not componentes:
        return {}
    maior = _bloco(grafo, componentes[0])
    resto = [(_bloco(grafo, nos, ESCALA_DOS_OUTROS), len(nos)) for nos in componentes[1:]]
    lm, am = _medidas(maior)
    # a área que a faixa de baixo ocupa (com as margens), e a largura que deixa o desenho em PROPORCAO : 1
    area = sum(max(LADO_PEQUENO, *_medidas(b)) ** 2 * (1.6 if n > PEQUENO else 2.3) for b, n in resto)
    largura = max(lm, 1.0, (PROPORCAO * am + math.sqrt((PROPORCAO * am) ** 2 + 4 * PROPORCAO * area)) / 2)
    posicoes = {k: (px + largura / 2, py) for k, (px, py) in maior.items()}
    # as prateleiras dos outros componentes, de cima para baixo, logo abaixo do maior
    y = -am / 2 - max(0.8, 0.06 * largura)
    x = altura = 0.0
    for bloco, n in resto:
        w, h = (max(LADO_PEQUENO, m) for m in _medidas(bloco))
        margem = 0.25 if n <= PEQUENO else 0.15 * max(w, h) + 0.5
        if x > 0 and x + w > largura:
            x, y, altura = 0.0, y - altura, 0.0
        for k, (px, py) in bloco.items():
            posicoes[k] = (px + x + w / 2, py + y - h / 2)
        x += w + margem
        altura = max(altura, h + margem)
    xs, ys = [p[0] for p in posicoes.values()], [p[1] for p in posicoes.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    meia = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 2
    return {k: (round((px - cx) / meia, 4), round((py - cy) / meia, 4)) for k, (px, py) in posicoes.items()}
