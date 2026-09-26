"""Vizinhos mais próximos exatos, por similaridade de cosseno, calculados em blocos.

Um só grafo de vizinhança alimenta tudo o que precisa dele: o UMAP 5D (agrupamento) e 2D (mapa), as sementes
da estabilidade e os 5 vizinhos exportados para o cartão do mapa. Calcular aqui, e não deixar o umap-learn
calcular, dá um só caminho de código para qualquer tamanho de corpus: o umap-learn usa busca exata abaixo de
4.096 documentos e aproximada (pynndescent) acima, e o piloto tem 4.275.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def knn_exato(matriz: np.ndarray, k: int, *, bloco: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    """Índices e distâncias de cosseno (1 − similaridade) dos `k` vizinhos de cada linha de `matriz` (normalizada).

    A coluna 0 é sempre a própria linha, com distância 0, como o umap-learn espera. Empates são desfeitos pelo
    índice, para o resultado não depender da ordem interna do numpy.
    """
    import numpy as np

    n = len(matriz)
    k = min(k, n)
    indices = np.empty((n, k), dtype=np.int64)
    distancias = np.empty((n, k), dtype=np.float32)
    for inicio in range(0, n, bloco):
        linhas = np.arange(inicio, min(inicio + bloco, n))
        sim = matriz[linhas] @ matriz.T
        sim[np.arange(len(linhas)), linhas] = np.inf  # a própria linha primeiro
        # ordena por similaridade decrescente e, no empate, pelo índice
        candidatos = (
            np.argpartition(-sim, kth=k - 1, axis=1)[:, :k] if k < n else np.tile(np.arange(n), (len(linhas), 1))
        )
        sims = np.take_along_axis(sim, candidatos, axis=1)
        ordem = np.lexsort((candidatos, -sims), axis=1)
        escolhidos = np.take_along_axis(candidatos, ordem, axis=1)
        dist = 1.0 - np.take_along_axis(sim, escolhidos, axis=1)
        dist[:, 0] = 0.0
        indices[linhas] = escolhidos
        distancias[linhas] = np.clip(dist, 0.0, 2.0)
    return indices, distancias
