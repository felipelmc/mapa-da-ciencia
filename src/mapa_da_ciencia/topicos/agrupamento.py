"""Agrupamento dos documentos em tópicos com HDBSCAN, sobre a redução UMAP de 5 dimensões.

O HDBSCAN encontra regiões densas e deixa de fora (rótulo −1, "ruído") o que não pertence claramente a
nenhuma. Os documentos agrupados formam o **núcleo** de cada tópico; é dele que saem as palavras-chave, os
representativos, os contornos e a identidade estável.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mapa_da_ciencia.config import ErroConfig

if TYPE_CHECKING:
    import numpy as np

MINIMO_DOCUMENTOS = 50


def min_cluster_size_automatico(n: int) -> int:
    """Um tópico precisa ter ao menos 1 a cada 200 documentos (e nunca menos de 10), como no spike M0a."""
    return max(10, n // 200)


def conferir_tamanho(n: int) -> None:
    if n < MINIMO_DOCUMENTOS:
        raise ErroConfig(
            f"O corpus tem {n} documento(s) com texto, e os tópicos precisam de pelo menos {MINIMO_DOCUMENTOS}. "
            "Amplie o recorte (mais anos ou mais revistas) e rode `mapa coletar` de novo."
        )


@dataclass
class Agrupamento:
    rotulos: np.ndarray  # tópico bruto do HDBSCAN por documento; −1 = ruído
    probabilidades: np.ndarray  # força da ligação ao tópico (0 no ruído)

    @property
    def n_topicos(self) -> int:
        return int(self.rotulos.max()) + 1 if len(self.rotulos) else 0

    @property
    def fracao_ruido(self) -> float:
        return float((self.rotulos == -1).mean()) if len(self.rotulos) else 0.0


def agrupar(coords: np.ndarray, *, min_cluster_size: int, min_samples: int, selecao: str = "eom") -> Agrupamento:
    from sklearn.cluster import HDBSCAN

    modelo = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        cluster_selection_method=selecao,
        copy=True,
    )
    modelo.fit(coords)
    return Agrupamento(modelo.labels_.astype("int64"), modelo.probabilities_.astype("float32"))
