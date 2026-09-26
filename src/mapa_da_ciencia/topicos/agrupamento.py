"""Agrupamento dos documentos em tópicos com HDBSCAN, reatribuição do ruído e estabilidade entre sementes.

O HDBSCAN encontra regiões densas na redução UMAP de 5 dimensões e deixa de fora (rótulo −1, "ruído") o que
não pertence claramente a nenhuma. Os documentos agrupados formam o **núcleo** de cada tópico; é dele que saem
as palavras-chave, os representativos, os contornos e a identidade estável.

No piloto, um terço do corpus fica como ruído em qualquer configuração estável (ADR 0007). Esses documentos
são **reatribuídos por vizinhança**: vão para o tópico que tem mais vizinhos seus no núcleo, se forem pelo
menos `votos_minimos` dos 15 mais próximos no espaço dos embeddings (e não no UMAP, que distorce distâncias).
Quem não chega lá continua sem tópico. A marca `vizinho` fica em cada documento reatribuído.
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


def reatribuir(rotulos: np.ndarray, knn_indices: np.ndarray, knn_dist: np.ndarray, *, votos_minimos: int) -> np.ndarray:
    """Tópico de cada documento depois da reatribuição do ruído (−1 para quem não teve votos suficientes).

    Cada vizinho do núcleo vota no próprio tópico, com peso igual à similaridade; vence o tópico com mais peso,
    e ele precisa ter ao menos `votos_minimos` vizinhos. O núcleo não muda.
    """
    import numpy as np

    saida = rotulos.copy()
    for i in np.flatnonzero(rotulos == -1):
        vizinhos, similaridades = knn_indices[i, 1:], 1.0 - knn_dist[i, 1:]
        topicos = rotulos[vizinhos]
        no_nucleo = topicos >= 0
        if not no_nucleo.any():
            continue
        pesos = np.bincount(topicos[no_nucleo], weights=similaridades[no_nucleo])
        vencedor = int(np.argmax(pesos))
        if int((topicos == vencedor).sum()) >= votos_minimos:
            saida[i] = vencedor
    return saida


def estabilidade(rotulos_por_semente: list[np.ndarray]) -> float | None:
    """ARI médio entre os pares de sementes, sobre os documentos que estão no núcleo nas duas execuções.

    Mede se os tópicos são do corpus ou do acaso: perto de 1, sementes diferentes encontram os mesmos tópicos.
    """
    import itertools

    import numpy as np
    from sklearn.metrics import adjusted_rand_score

    valores = []
    for a, b in itertools.combinations(rotulos_por_semente, 2):
        ambos = (a >= 0) & (b >= 0)
        if ambos.sum() > 1:
            valores.append(adjusted_rand_score(a[ambos], b[ambos]))
    return round(float(np.mean(valores)), 4) if valores else None
