"""Macrotemas: tópicos próximos agrupados, para a cor e a navegação do mapa.

Aglomeração hierárquica (Ward) dos centros dos tópicos no espaço dos embeddings (média do núcleo, normalizada).
No piloto, a ligação média deixava macrotemas de um tópico só; a de Ward dá grupos equilibrados (ADR 0007).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def centros(matriz: np.ndarray, topicos: np.ndarray, ids_topicos: list[int]) -> np.ndarray:
    """Centro de cada tópico (na ordem de `ids_topicos`): média dos embeddings do núcleo, normalizada."""
    import numpy as np

    c = np.array([matriz[topicos == t].mean(axis=0) for t in ids_topicos], dtype=np.float32)
    return c / np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-12)


def agrupar_macrotemas(centros_topicos: np.ndarray, tamanhos: list[int], n: int) -> list[int]:
    """Grupo (0 = o de mais documentos) de cada tópico. Com menos tópicos que `n`, cada tópico é um grupo."""
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage

    k = len(centros_topicos)
    if k == 0:
        return []
    if k <= n:
        grupos = np.arange(k)
    else:
        grupos = fcluster(linkage(centros_topicos, method="ward"), t=n, criterion="maxclust") - 1
    peso = {g: sum(t for t, gg in zip(tamanhos, grupos, strict=True) if gg == g) for g in set(grupos.tolist())}
    ordem = sorted(peso, key=lambda g: (-peso[g], g))
    return [ordem.index(int(g)) for g in grupos]
