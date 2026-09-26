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
from mapa_da_ciencia.topicos.agrupamento import agrupar, conferir_tamanho, min_cluster_size_automatico
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
