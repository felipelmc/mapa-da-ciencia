"""Macrotemas: tópicos próximos agrupados, para a cor e a navegação do mapa.

Aglomeração hierárquica (Ward) dos centros dos tópicos no espaço dos embeddings (média do núcleo, normalizada).
No piloto, a ligação média deixava macrotemas de um tópico só; a de Ward dá grupos equilibrados (ADR 0007).
Em corpus pequenos, com poucos tópicos, o número de macrotemas cai para que cada um reúna em média ao menos
`TOPICOS_POR_MACROTEMA` tópicos: 13 tópicos em 7 macrotemas deixariam cores para grupos de um tópico só.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

TOPICOS_POR_MACROTEMA = 3


def numero_de_macrotemas(k: int, n: int) -> int:
    """Quantos macrotemas para `k` tópicos: `n` (o configurado), no máximo, e em média ao menos 3 tópicos em cada."""
    return min(k, n, max(2, k // TOPICOS_POR_MACROTEMA))


def centros(matriz: np.ndarray, topicos: np.ndarray, ids_topicos: list[int]) -> np.ndarray:
    """Centro de cada tópico (na ordem de `ids_topicos`): média dos embeddings do núcleo, normalizada."""
    import numpy as np

    c = np.array([matriz[topicos == t].mean(axis=0) for t in ids_topicos], dtype=np.float32)
    return c / np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-12)


def agrupar_macrotemas(centros_topicos: np.ndarray, tamanhos: list[int], n: int) -> list[int]:
    """Grupo (0 = o de mais documentos) de cada tópico, em até `n` grupos (ver `numero_de_macrotemas`)."""
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage

    k = len(centros_topicos)
    if k == 0:
        return []
    alvo = numero_de_macrotemas(k, n)
    if k <= alvo:
        grupos = np.arange(k)
    else:
        grupos = fcluster(linkage(centros_topicos, method="ward"), t=alvo, criterion="maxclust") - 1
    peso = {g: sum(t for t, gg in zip(tamanhos, grupos, strict=True) if gg == g) for g in set(grupos.tolist())}
    ordem = sorted(peso, key=lambda g: (-peso[g], g))
    return [ordem.index(int(g)) for g in grupos]
