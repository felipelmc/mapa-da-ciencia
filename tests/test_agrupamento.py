"""Vizinhos, UMAP e HDBSCAN sobre o corpus sintético. O UMAP roda uma vez só (escopo de módulo): a compilação
do numba leva alguns segundos. Nunca se comparam coordenadas exatas, que variam entre máquinas."""

import numpy as np
import pytest
from conftest import vetor_falso
from corpus_sintetico import TEMAS, corpus_sintetico

from mapa_da_ciencia.config import ConfigTopicos, ErroConfig
from mapa_da_ciencia.embeddings import texto_de_analise
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.topicos.agrupamento import (
    agrupar,
    conferir_tamanho,
    estabilidade,
    min_cluster_size_automatico,
    reatribuir,
)
from mapa_da_ciencia.topicos.reducao import reduzir
from mapa_da_ciencia.topicos.vizinhos import knn_exato


@pytest.fixture(scope="module")
def sintetico(tmp_path_factory):
    docs, temas = corpus_sintetico()
    textos = [t for d in docs if (t := texto_de_analise(d, "en"))]
    matriz = np.array([vetor_falso(t.texto) for t in textos], dtype=np.float32)
    knn = knn_exato(matriz, 15)
    cache = tmp_path_factory.mktemp("reducoes")
    params = {"n_vizinhos": 15, "semente": 42, "cache": cache, "base": "sintetico"}
    coords5 = reduzir(matriz, knn, n_componentes=5, min_dist=0.0, **params)
    coords2 = reduzir(matriz, knn, n_componentes=2, min_dist=0.1, **params)
    planted = np.array([list(TEMAS).index(temas[t.id]) for t in textos])
    return {"matriz": matriz, "knn": knn, "coords5": coords5, "coords2": coords2, "temas": planted, "params": params}


def test_knn_exato_confere_com_forca_bruta():
    rng = np.random.default_rng(0)
    m = rng.normal(size=(40, 8)).astype(np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    indices, distancias = knn_exato(m, 6, bloco=7)  # blocos pequenos para cruzar fronteiras
    assert (indices[:, 0] == np.arange(40)).all() and (distancias[:, 0] == 0).all()
    assert (np.diff(distancias, axis=1) >= -1e-6).all()
    for i in range(40):
        esperado = np.argsort(-(m @ m[i]))[:6]
        assert set(indices[i]) == set(esperado)
        assert np.allclose(distancias[i, 1:], 1 - (m @ m[i])[indices[i, 1:]], atol=1e-5)


def test_temas_plantados_sao_recuperados(sintetico):
    from sklearn.metrics import adjusted_rand_score

    agr = agrupar(sintetico["coords5"], min_cluster_size=15, min_samples=5)
    nucleo = agr.rotulos != -1
    assert 5 <= agr.n_topicos <= 8 and agr.fracao_ruido < 0.3
    assert adjusted_rand_score(sintetico["temas"][nucleo], agr.rotulos[nucleo]) >= 0.85


def test_mapa_2d_e_cache_das_reducoes(sintetico, monkeypatch):
    coords2 = sintetico["coords2"]
    assert coords2.shape == (len(sintetico["matriz"]), 2) and np.isfinite(coords2).all()

    import umap

    def proibido(*_, **__):
        raise AssertionError("o UMAP não devia rodar de novo")

    monkeypatch.setattr(umap, "UMAP", proibido)
    de_novo = reduzir(sintetico["matriz"], sintetico["knn"], n_componentes=5, min_dist=0.0, **sintetico["params"])
    assert np.array_equal(de_novo, sintetico["coords5"])


def test_corpus_pequeno_e_tamanho_automatico():
    with pytest.raises(ErroConfig, match="pelo menos 50"):
        conferir_tamanho(49)
    conferir_tamanho(50)
    assert min_cluster_size_automatico(300) == 10 and min_cluster_size_automatico(4275) == 21


def test_secao_topicos_do_mapa_yaml(tmp_path):
    p = Projeto.criar(tmp_path / "cp", modelo="ciencia-politica", perfil=PERFIS["padrao"])
    t = p.config.topicos
    assert t == ConfigTopicos() and t.min_cluster_size is None and t.sementes[0] == 42


def _knn(vizinhos: list[list[int]], sims: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    """Grafo de vizinhança à mão: a coluna 0 é o próprio documento."""
    indices = np.array([[i, *v] for i, v in enumerate(vizinhos)])
    dist = np.array([[0.0, *(1 - np.array(s))] for s in sims])
    return indices, dist


def test_reatribuicao_por_votos_dos_vizinhos_do_nucleo():
    #        0  1  2  3  4  5  6   7   8   9
    rotulos = np.array([0, 0, 1, 1, 1, 1, -1, -1, -1, -1])
    vizinhos = [[1, 2, 3, 4]] * 6 + [
        [2, 3, 4, 0],  # 6: três do tópico 1 → vai para o 1
        [0, 1, 2, 9],  # 7: dois do 0, um do 1 → só 2 votos, fica sem tópico
        [9, 7, 6, 8],  # 8: nenhum vizinho no núcleo
        [0, 1, 2, 3],  # 9: empate 2 × 2, desfeito pela similaridade
    ]
    sims = [[0.9, 0.8, 0.7, 0.6]] * 9 + [[0.5, 0.5, 0.9, 0.9]]
    indices, dist = _knn(vizinhos, sims)
    saida = reatribuir(rotulos, indices, dist, votos_minimos=3)
    assert saida.tolist() == [0, 0, 1, 1, 1, 1, 1, -1, -1, -1]
    assert reatribuir(rotulos, indices, dist, votos_minimos=2).tolist()[7:] == [0, -1, 1]
    assert (saida[rotulos >= 0] == rotulos[rotulos >= 0]).all()  # o núcleo não muda


def test_estabilidade_entre_sementes():
    a = np.array([0, 0, 1, 1, 2, 2, -1])
    assert estabilidade([a, a]) == 1.0
    assert estabilidade([a, np.array([5, 5, 3, 3, 9, 9, 0])]) == 1.0  # os números dos tópicos não importam
    assert estabilidade([a, np.array([0, 1, 0, 1, 0, 1, 0])]) < 0.2
    assert estabilidade([a]) is None


def test_reatribuicao_no_corpus_sintetico(sintetico):
    """Documentos arrancados do núcleo (20%, como ruído) voltam, pela vizinhança, para o tema certo."""
    from sklearn.metrics import adjusted_rand_score

    agr = agrupar(sintetico["coords5"], min_cluster_size=15, min_samples=5)
    arrancados = np.random.default_rng(3).random(len(agr.rotulos)) < 0.2
    com_ruido = np.where(arrancados, -1, agr.rotulos)
    finais = reatribuir(com_ruido, *sintetico["knn"], votos_minimos=3)
    voltaram = arrancados & (finais >= 0)
    assert voltaram.sum() >= 0.9 * arrancados.sum()
    assert adjusted_rand_score(sintetico["temas"][voltaram], finais[voltaram]) >= 0.85
