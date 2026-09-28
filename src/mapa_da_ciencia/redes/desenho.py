"""O desenho das redes: posições fixas e reprodutíveis para cada nó.

**O maior componente, por comunidades.** Cada comunidade do Louvain (a partição inteira, também as pequenas) é
desenhada à parte (`spring_layout`, semente 7) num disco de área proporcional ao número de nós. Os discos são
arrumados pelo grafo das comunidades: um `spring_layout` em que o peso entre duas comunidades é a soma dos pesos das
arestas entre elas, que aproxima os grupos muito ligados. Esse arranjo é ampliado até nenhum disco encostar noutro e
depois contraído aos poucos, desfazendo as sobreposições a cada passo, o que o preserva melhor que relaxar a partir
dele apertado. O resultado separa as comunidades à vista, que é o
que a vista rotula e deixa clicar, sem perder as pontes entre elas.

**Os outros componentes** são desenhados como antes (`spring_layout` pelos pesos), menores, e arrumados em
prateleiras: primeiro à direita do maior, na altura dele, e depois embaixo, na largura toda. A largura é a que deixa
o desenho visível por padrão (o maior e os componentes de `MINIMO_VISIVEL` nós ou mais) perto de `PROPORCAO`, a de
uma tela larga. As duplas e os trios, escondidos por padrão na vista, ficam embaixo de tudo.

**Sem nós sobrepostos** na tela de referência (`TELA`, a área do grafo numa tela de 1920 × 1080): com os raios que a
vista desenha (`raios`, em pixels), um relaxamento dentro de cada componente afasta os nós que se tocariam, e o
empacotamento é refeito com os componentes já afastados. Em telas menores, o zoom separa.

O conjunto é normalizado para [-1, 1], com quatro casas decimais, e o eixo y cresce para cima (a vista inverte para
a tela): o mesmo corpus dá sempre as mesmas coordenadas.
"""

from __future__ import annotations

import math

SEMENTE = 7
PEQUENO = 3  # componentes de até 3 nós: desenhados menores e mais juntos
MINIMO_VISIVEL = 4  # a vista esconde por padrão os componentes menores que isso (`MINIMO_VISIVEL` em ModoGrafo)
LADO_PEQUENO = 0.5  # a largura de uma dupla ou de um trio, contra ~√n no maior componente
ESCALA_DOS_OUTROS = 0.6  # os componentes fora do maior, em relação a ele
PROPORCAO = 1.6  # largura : altura do desenho visível por padrão, perto da da vista
ALONGAR_MAIOR = 1.3  # quanto o arranjo das comunidades do maior componente se alonga na horizontal
TELA = (1250, 840)  # a área do grafo (px) em que o desenho não pode ter nós sobrepostos
MARGEM_TELA = 28  # a margem do enquadramento em Grafo.svelte
FOLGA_PX = 2.0  # a distância mínima entre as bordas de dois nós, na tela de referência
FOLGA_COMUNIDADES = 0.35  # entre os discos das comunidades, em unidades do desenho (~√n de largura)
FOLGA_MAIOR = 1.6  # entre o maior componente e os outros
FOLGA_OUTROS = 0.7  # entre os outros componentes


def _centrar(pos: dict[str, tuple[float, float]], lado: float) -> dict[str, tuple[float, float]]:
    """Centra em (0, 0), com a maior dimensão igual a `lado`."""
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    escala = lado / max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    return {k: ((x - cx) * escala, (y - cy) * escala) for k, (x, y) in pos.items()}


def _spring(grafo, nos: list[str], **opcoes) -> dict[str, tuple[float, float]]:
    import networkx as nx

    sub = nx.Graph()
    sub.add_nodes_from(nos)
    sub.add_weighted_edges_from(
        sorted((a, b, d.get("peso", 1.0)) for a, b, d in grafo.subgraph(nos).edges(data=True)), weight="peso"
    )
    pos = nx.spring_layout(sub, seed=SEMENTE, weight="peso", **opcoes)
    return {k: (float(v[0]), float(v[1])) for k, v in pos.items()}


def _bloco(grafo, nos: list[str], fator: float = 1.0) -> dict[str, tuple[float, float]]:
    """As posições de um componente, centradas em (0, 0), com largura de ~fator·√n (`LADO_PEQUENO` nos pequenos)."""
    n = len(nos)
    if n == 1:
        return {nos[0]: (0.0, 0.0)}
    if n == 2:
        return {nos[0]: (-LADO_PEQUENO / 2, 0.0), nos[1]: (LADO_PEQUENO / 2, 0.0)}
    return _centrar(_spring(grafo, nos), LADO_PEQUENO if n <= PEQUENO else fator * math.sqrt(n))


def _por_comunidades(grafo, nos: list[str], particao: list[set[str]]) -> dict[str, tuple[float, float]]:
    """O maior componente: cada comunidade num disco, os discos arrumados pelo grafo das comunidades."""
    import networkx as nx
    import numpy as np

    n = len(nos)
    conj = set(nos)
    grupos = sorted((sorted(c & conj) for c in particao if c & conj), key=lambda c: (-len(c), c[0]))
    vistos = {x for c in grupos for x in c}
    grupos += [[x] for x in nos if x not in vistos]  # nó fora da partição (não deveria haver): um grupo só dele
    if len(grupos) < 2 or n <= PEQUENO:
        return _bloco(grafo, nos)
    de = {x: k for k, c in enumerate(grupos) for x in c}

    # 1. dentro de cada comunidade
    internos, raios = [], []
    for c in grupos:
        if len(c) == 1:
            internos.append({c[0]: (0.0, 0.0)})
            raios.append(0.35)
            continue
        lado = 0.9 * math.sqrt(len(c)) + 0.4
        internos.append(_centrar(_spring(grafo, c, k=1.6 / math.sqrt(len(c)), iterations=200), lado))
        raios.append(lado / 2 * 1.05)

    # 2. o grafo das comunidades, com o peso das arestas entre elas
    s = nx.Graph()
    s.add_nodes_from(range(len(grupos)))
    for a, b, d in sorted(grafo.subgraph(nos).edges(data=True)):
        ka, kb = de[a], de[b]
        if ka != kb:
            s.add_edge(ka, kb, w=s.get_edge_data(ka, kb, {"w": 0.0})["w"] + d.get("peso", 1.0))
    centro = nx.spring_layout(s, seed=SEMENTE, weight="w", k=1.5 / math.sqrt(len(grupos)), iterations=300)
    c = np.array([centro[k] for k in range(len(grupos))], dtype=float)
    r = np.array(raios)
    c = c - c.mean(axis=0)
    c[:, 0] *= ALONGAR_MAIOR  # um pouco mais largo que alto, como a tela

    c = _arranjar_discos(c, r, FOLGA_COMUNIDADES)

    pos = {x: (px + c[k, 0], py + c[k, 1]) for k, grupo in enumerate(internos) for x, (px, py) in grupo.items()}
    return _centrar(pos, 1.25 * math.sqrt(n))


def _arranjar_discos(c, r, folga: float, voltas: int = 600):
    """Os discos das comunidades sem se sobrepor, mantendo o arranjo do grafo das comunidades: primeiro o arranjo é
    ampliado até nenhum disco encostar noutro (a posição relativa fica a mesma), e depois contraído aos poucos para o
    centro de massa, desfazendo a cada passo as sobreposições que a contração criar. Assim as comunidades muito
    ligadas continuam perto uma da outra (relaxar a partir do arranjo apertado as embaralhava)."""
    import numpy as np

    area = r**2
    c = c - (c * area[:, None]).sum(axis=0) / area.sum()
    n = len(r)
    ampliar = 1.0
    for i in range(n):
        for j in range(i + 1, n):
            ampliar = max(ampliar, (r[i] + r[j] + folga) / max(math.hypot(*(c[i] - c[j])), 1e-9))
    c = c * ampliar
    for volta in range(voltas + 1):
        if volta < voltas:
            c = c - 0.03 * (c - (c * area[:, None]).sum(axis=0) / area.sum())
        # entre as contrações, umas poucas passadas; no fim, até não sobrar sobreposição nenhuma
        for _ in range(3 if volta < voltas else 500):
            mexeu = False
            for i in range(n):
                for j in range(i + 1, n):
                    d = c[j] - c[i]
                    dist = math.hypot(d[0], d[1])
                    alvo = r[i] + r[j] + folga
                    if dist >= alvo:
                        continue
                    if dist < 1e-9:  # coincidentes: uma direção fixa pelo índice
                        d, dist = np.array([math.cos(i * 2.399), math.sin(i * 2.399)]), 1.0
                    passo = (alvo - dist) * d / dist
                    c[i] -= passo * area[j] / (area[i] + area[j])
                    c[j] += passo * area[i] / (area[i] + area[j])
                    mexeu = True
            if not mexeu:
                break
    return c


def _medidas(bloco: dict[str, tuple[float, float]]) -> tuple[float, float, float, float]:
    """Largura, altura e o canto (x mínimo, y máximo) de um bloco."""
    xs, ys = [p[0] for p in bloco.values()], [p[1] for p in bloco.values()]
    return max(max(xs) - min(xs), LADO_PEQUENO), max(max(ys) - min(ys), LADO_PEQUENO), min(xs), max(ys)


def _empacotar(blocos: list[dict], visiveis: list[bool]) -> dict[str, tuple[float, float]]:
    """O maior (`blocos[0]`) no alto, à esquerda; os outros visíveis em prateleiras à direita dele e depois embaixo;
    os escondidos por padrão embaixo de tudo. Devolve as posições com o y crescendo para baixo."""
    medidas = [_medidas(b) for b in blocos]
    gw, gh = medidas[0][0], medidas[0][1]

    def arrumar(largura: float, quais: list[int]) -> tuple[dict[int, tuple[float, float]], float]:
        lugares = {0: (0.0, 0.0)}
        xa = gw + FOLGA_MAIOR
        x, y, linha, embaixo, fundo = xa, 0.0, 0.0, False, gh
        for k in quais:
            w, h = medidas[k][0], medidas[k][1]
            if not embaixo:
                if x + w > largura and x > xa:
                    x, y, linha = xa, y + linha + FOLGA_OUTROS, 0.0
                if xa + w > largura or y + h > gh:
                    embaixo, x, y, linha = True, 0.0, fundo + FOLGA_MAIOR, 0.0
            if embaixo and x > 0 and x + w > largura:
                x, y, linha = 0.0, y + linha + FOLGA_OUTROS, 0.0
            lugares[k] = (x, y)
            x += w + FOLGA_OUTROS
            linha = max(linha, h)
            fundo = max(fundo, y + h)
        return lugares, fundo

    vis = [k for k in range(1, len(blocos)) if visiveis[k]]
    esc = [k for k in range(1, len(blocos)) if not visiveis[k]]

    def erro(largura: float) -> tuple[float, float]:
        # a distância (em log) até PROPORCAO; no empate, a menor largura
        return round(abs(math.log(largura / arrumar(largura, vis)[1] / PROPORCAO)), 9), largura

    largura = min((gw * (1 + 0.05 * passo) for passo in range(61)), key=erro)
    lugares, fundo = arrumar(largura, vis)
    x, y, linha = 0.0, fundo + FOLGA_MAIOR, 0.0
    for k in esc:
        w, h = medidas[k][0], medidas[k][1]
        if x > 0 and x + w > largura:
            x, y, linha = 0.0, y + linha + FOLGA_OUTROS, 0.0
        lugares[k] = (x, y)
        x += w + FOLGA_OUTROS
        linha = max(linha, h)
    saida = {}
    for k, bloco in enumerate(blocos):
        ox, oy = lugares[k]
        _, _, x0, y1 = medidas[k]
        for no, (px, py) in bloco.items():
            saida[no] = (ox + px - x0, oy + y1 - py)
    return saida


def _escala_da_tela(pos: dict[str, tuple[float, float]], nos: list[str]) -> float:
    """Pixels por unidade do desenho quando `nos` enquadram a tela de referência (como `ajuste` em Grafo.svelte)."""
    xs, ys = [pos[k][0] for k in nos], [pos[k][1] for k in nos]
    w, h = TELA
    return min((w - 2 * MARGEM_TELA) / ((max(xs) - min(xs)) or 1), (h - 2 * MARGEM_TELA) / ((max(ys) - min(ys)) or 1))


def _afastar(pos: dict[str, tuple[float, float]], raio: dict[str, float], folga: float, voltas: int = 60):
    """Empurra os pares de nós mais perto que r_i + r_j + folga, metade para cada lado (determinístico)."""
    import numpy as np
    from scipy.spatial import cKDTree

    nos = sorted(pos)
    p = np.array([pos[k] for k in nos], dtype=float)
    r = np.array([raio[k] for k in nos], dtype=float)
    alcance = 2 * r.max() + folga
    for _ in range(voltas):
        pares = np.array(sorted(cKDTree(p).query_pairs(alcance)), dtype=np.int64).reshape(-1, 2)
        if not len(pares):
            break
        i, j = pares[:, 0], pares[:, 1]
        d = p[j] - p[i]
        dist = np.hypot(d[:, 0], d[:, 1])
        alvo = r[i] + r[j] + folga
        perto = dist < alvo
        if not perto.any():
            break
        i, j, d, dist, alvo = i[perto], j[perto], d[perto], dist[perto], alvo[perto]
        juntos = dist < 1e-12
        d[juntos] = np.column_stack([np.cos(i[juntos] * 2.399), np.sin(i[juntos] * 2.399)])
        dist[juntos] = 1.0
        empurrao = ((alvo - np.where(juntos, 0.0, dist)) / 2)[:, None] * d / dist[:, None]
        delta = np.zeros_like(p)
        np.add.at(delta, i, -empurrao)
        np.add.at(delta, j, empurrao)
        p += 0.9 * delta
    return {k: (float(p[n, 0]), float(p[n, 1])) for n, k in enumerate(nos)}


def desenhar(
    grafo, particao: list[set[str]] | None = None, raios: dict[str, float] | None = None
) -> dict[str, tuple[float, float]]:
    """Posições de todos os nós do grafo (networkx), em [-1, 1], com o maior componente no alto, à esquerda.

    `particao`: as comunidades do Louvain (todas), para desenhar o maior componente por comunidades; sem ela, ele
    sai de um `spring_layout` só. `raios`: o raio de cada nó na vista, em pixels, para não haver sobreposição na tela
    de referência; sem eles, nenhum relaxamento."""
    import networkx as nx

    componentes = sorted((sorted(c) for c in nx.connected_components(grafo)), key=lambda c: (-len(c), c[0]))
    if not componentes:
        return {}
    maior = _por_comunidades(grafo, componentes[0], particao) if particao else _bloco(grafo, componentes[0])
    originais = [maior] + [_bloco(grafo, nos, ESCALA_DOS_OUTROS) for nos in componentes[1:]]
    visiveis = [k == 0 or len(c) >= MINIMO_VISIVEL for k, c in enumerate(componentes)]
    blocos = originais
    if raios:
        # a escala da tela depende do empacotamento, e o empacotamento, do tamanho dos blocos já afastados: três voltas
        nos_visiveis = [k for c, v in zip(componentes, visiveis, strict=True) if v for k in c]
        for _ in range(3):
            escala = _escala_da_tela(_empacotar(blocos, visiveis), nos_visiveis)
            blocos = [
                _afastar(b, {k: raios.get(k, 0.0) / escala for k in b}, FOLGA_PX / escala) if len(b) > 1 else b
                for b in originais
            ]
    posicoes = _empacotar(blocos, visiveis)
    xs, ys = [p[0] for p in posicoes.values()], [p[1] for p in posicoes.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    meia = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 2
    # o y do empacotamento cresce para baixo; o do contrato, para cima
    return {k: (round((px - cx) / meia, 4), round((cy - py) / meia, 4)) for k, (px, py) in posicoes.items()}


def raios_na_vista(documentos: dict[str, int], rede: str) -> dict[str, float]:
    """O raio de cada nó (px) como a vista desenha (`RAIO` em ModoGrafo): pela raiz dos documentos do nó no corpus, de
    1 documento (o raio mínimo) ao nó com mais documentos (o máximo)."""
    minimo, maximo = {"coautoria": (1.8, 8.0), "instituicoes": (3.0, 14.0)}[rede]
    teto = math.sqrt(max(1, *documentos.values())) if documentos else 1.0
    escala = (maximo - minimo) / (teto - 1) if teto > 1 else 0.0
    return {k: minimo + escala * max(0.0, math.sqrt(v) - 1) for k, v in documentos.items()}
