import numpy as np
from conftest import vetor_falso
from corpus_sintetico import TEMAS, corpus_sintetico

from mapa_da_ciencia.topicos.ctfidf import STOPWORDS, palavras_chave, representativos, texto_de_exibicao


def test_palavras_dos_temas_plantados_em_portugues():
    docs, temas = corpus_sintetico()
    textos = [texto_de_exibicao(d, "pt", "en") for d in docs]
    topicos = np.array([list(TEMAS).index(temas[d.id]) for d in docs])
    pc = palavras_chave(textos, topicos, n=10)
    assert sorted(pc) == list(range(len(TEMAS)))
    for t, tema in enumerate(TEMAS):
        vocabulario = set(TEMAS[tema][1].split())
        palavras = {p for termo, _ in pc[t] for p in termo.split()}
        assert len(palavras & vocabulario) >= 6, (tema, pc[t])  # o vocabulário do tema, em português
        assert not palavras & {"estudo", "análise", "artigo", "pesquisa", "não"}  # nada de gênero acadêmico
        pesos = [peso for _, peso in pc[t]]
        assert pesos == sorted(pesos, reverse=True) and all(p > 0 for p in pesos)


def test_par_de_palavras_substitui_as_palavras_soltas():
    textos = ["violência no rio de janeiro e milícias"] * 4 + ["eleições e campanhas no interior"] * 4
    topicos = np.array([0] * 4 + [1] * 4)
    termos = [t for t, _ in palavras_chave(textos, topicos, n=6)[0]]
    assert "rio janeiro" in termos and "janeiro" not in termos and "rio" not in termos
    assert not {"de", "no", "e"} & set(termos) and {"de", "no", "e"} <= set(STOPWORDS)


def test_ruido_fica_de_fora_e_termos_raros_nao_contam():
    textos = ["coalizões congresso agenda"] * 3 + ["palavraúnica congresso"] + ["qualquer coisa"] * 3
    topicos = np.array([0, 0, 0, 0, -1, -1, -1])
    pc = palavras_chave(textos, topicos, n=5)
    assert list(pc) == [0] and "palavraúnica" not in dict(pc[0])  # aparece em 1 documento só (min_df = 3)


def test_representativos_sao_os_mais_centrais():
    docs, temas = corpus_sintetico(n_por_tema=20)
    ids = [d.id for d in docs]
    matriz = np.array([vetor_falso(texto_de_exibicao(d, "en", "en")) for d in docs], dtype=np.float32)
    topicos = np.array([list(TEMAS).index(temas[i]) for i in ids])
    rep = representativos(matriz, topicos, ids, n=5)
    for t, escolhidos in rep.items():
        assert len(escolhidos) == 5 and all(temas[i] == list(TEMAS)[t] for i in escolhidos)
        membros = np.flatnonzero(topicos == t)
        centro = matriz[membros].mean(axis=0)
        melhor = ids[membros[np.argmax(matriz[membros] @ centro)]]
        assert escolhidos[0] == melhor
