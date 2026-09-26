"""Redução de dimensão com UMAP: 5 dimensões para o agrupamento e 2 para o mapa.

As reduções ficam em cache (`dados/topicos/reducoes/<chave>.npy`), com uma chave que inclui os embeddings,
os ids, os parâmetros, a semente e as versões do umap-learn e do numba. Reexecutar sem mudanças não roda o
UMAP de novo, e o UMAP é o passo mais lento depois dos embeddings (mais o tempo de compilação do numba).

Com semente fixa, o umap-learn roda numa thread só e dá o mesmo resultado na mesma máquina. Entre máquinas
diferentes (arm64 × x86) as coordenadas podem variar um pouco: o numba compila com `fastmath`.
"""

from __future__ import annotations

import hashlib
import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def chave_reducao(base: str, *, n_componentes: int, n_vizinhos: int, min_dist: float, semente: int) -> str:
    """Chave do cache: `base` identifica os dados (modelo, ids e hash da matriz); o resto, a redução."""
    import numba
    import umap

    partes = [base, str(n_componentes), str(n_vizinhos), f"{min_dist:.4f}", str(semente)]
    partes += [umap.__version__, numba.__version__]
    return hashlib.sha256("|".join(partes).encode()).hexdigest()[:20]


def assinatura_dados(ids: list[str], matriz: np.ndarray, rotulo_modelo: str) -> str:
    h = hashlib.sha256(rotulo_modelo.encode())
    h.update("\n".join(ids).encode())
    h.update(matriz.tobytes())
    return h.hexdigest()[:20]


def reduzir(
    matriz: np.ndarray,
    knn: tuple[np.ndarray, np.ndarray],
    *,
    n_componentes: int,
    n_vizinhos: int,
    min_dist: float,
    semente: int,
    cache: Path | None = None,
    base: str = "",
) -> np.ndarray:
    """Coordenadas UMAP (`n_componentes` colunas) a partir do grafo de vizinhança já calculado."""
    import numpy as np

    arquivo = None
    if cache is not None:
        chave = chave_reducao(
            base, n_componentes=n_componentes, n_vizinhos=n_vizinhos, min_dist=min_dist, semente=semente
        )
        arquivo = cache / f"{chave}.npy"
        if arquivo.exists():
            try:
                return np.load(arquivo, allow_pickle=False)
            except (OSError, ValueError):
                arquivo.unlink(missing_ok=True)

    import umap

    n_vizinhos = min(n_vizinhos, len(matriz) - 1)
    indices, distancias = knn
    with warnings.catch_warnings():
        # sem índice de busca não há `transform` (não usamos), e a semente força uma thread (é o que queremos)
        warnings.filterwarnings("ignore", message=".*search index.*")
        warnings.filterwarnings("ignore", message=".*n_jobs.*")
        warnings.filterwarnings("ignore", category=UserWarning, module="umap")
        modelo = umap.UMAP(
            n_components=n_componentes,
            n_neighbors=n_vizinhos,
            min_dist=min_dist,
            metric="cosine",
            random_state=semente,
            n_jobs=1,
            precomputed_knn=(indices[:, :n_vizinhos], distancias[:, :n_vizinhos], None),
        )
        coords = modelo.fit_transform(matriz).astype(np.float32)
    if arquivo is not None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_name(arquivo.stem + ".tmp.npy")
        np.save(temporario, coords)
        os.replace(temporario, arquivo)
    return coords
