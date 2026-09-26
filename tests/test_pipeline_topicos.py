"""A etapa de tópicos de ponta a ponta, no corpus sintético (6 temas plantados), com o Ollama falso."""

import numpy as np
import pytest
from corpus_sintetico import corpus_sintetico

from mapa_da_ciencia.armazenamento import ARQUIVO, gravar_documentos
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import ultima_execucao
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.topicos.identidade import Identidade
from mapa_da_ciencia.topicos.pipeline import OpcoesTopicos, gerar_topicos
from mapa_da_ciencia.topicos.resultado import PASTA, Resultado, ler_atribuicoes


def _projeto(tmp_path, n_por_tema=50):
    p = Projeto.criar(tmp_path / "sintetico", modelo="vazio", perfil=PERFIS["leve"])
    docs, temas = corpus_sintetico(n_por_tema=n_por_tema)
    gravar_documentos(docs, p.dados / ARQUIVO)
    return p, temas


def test_topicos_de_ponta_a_ponta_e_segunda_execucao(tmp_path, apis_falsas):
    from sklearn.metrics import homogeneity_score

    p, temas = _projeto(tmp_path)
    r = gerar_topicos(p)
    assert r.documentos == 300 and r.topicos >= 5 and r.nucleo + r.reatribuidos + r.sem_topico == 300
    # os temas plantados não têm estrutura interna: como `leaf` os subdivide muda com a semente e com a máquina
    # (numba), e o ARI entre sementes fica entre ~0,7 (Linux do CI) e ~0,9 (macOS)
    assert r.estabilidade_ari is not None and r.estabilidade_ari > 0.6 and r.rotulos.chamadas >= r.topicos

    resultado = Resultado.ler(p.dados / PASTA)
    atrib = ler_atribuicoes(p.dados / PASTA)
    assert len(atrib) == 300 and all(len(a["vizinhos"]) == 5 and a["id"] not in a["vizinhos"] for a in atrib)
    com_topico = [a for a in atrib if a["topico"] >= 0]
    # a seleção `leaf` pode dividir um tema plantado em subtemas, mas um tópico não mistura temas
    assert homogeneity_score([temas[a["id"]] for a in com_topico], [a["topico"] for a in com_topico]) >= 0.85
    assert 6 <= r.topicos <= 15
    assert {t.id for t in resultado.topicos} == {a["topico"] for a in com_topico}
    assert all(t.rotulo_fonte == "llm" and t.palavras and len(t.representativos) == 5 for t in resultado.topicos)
    assert sum(len(m.topicos) for m in resultado.macrotemas) == r.topicos
    assert {a["fonte_analise"] for a in atrib} >= {"resumo", "reserva"}
    m = ultima_execucao(p, "topicos")
    assert m["contagens"]["topicos"] == r.topicos and m["modelos"]["rotulos"].startswith("qwen3.5:4b@")
    assert m["parametros"]["min_cluster_size"] == 10  # automático: 300 documentos → mínimo de 10

    embeds, chats = apis_falsas.chamadas["ollama"], apis_falsas.chamadas["ollama_chat"]
    de_novo = gerar_topicos(p)
    assert apis_falsas.chamadas["ollama"] == embeds and apis_falsas.chamadas["ollama_chat"] == chats  # tudo do cache
    assert de_novo.casados == de_novo.mesma_cor == de_novo.topicos
    resultado2 = Resultado.ler(p.dados / PASTA)
    assert [(t.id, t.cor, t.rotulo) for t in resultado2.topicos] == [(t.id, t.cor, t.rotulo) for t in resultado.topicos]
    assert Identidade.ler(p.dados / PASTA).proximo_id == r.topicos


def test_sem_rotulos_nao_chama_o_modelo(tmp_path, apis_falsas):
    p, _ = _projeto(tmp_path)
    del apis_falsas.modelos_ollama["qwen3.5:4b"]
    r = gerar_topicos(p, OpcoesTopicos(sem_rotulos=True))
    assert apis_falsas.chamadas["ollama_chat"] == 0 and r.rotulos.chamadas == 0
    resultado = Resultado.ler(p.dados / PASTA)
    assert all(t.rotulo_fonte == "palavras" and ", " in t.rotulo for t in resultado.topicos)
    assert "rotulos" not in ultima_execucao(p, "topicos")["modelos"]


def test_modelo_de_rotulos_ausente_sugere_sem_rotulos(tmp_path, apis_falsas):
    p, _ = _projeto(tmp_path)
    del apis_falsas.modelos_ollama["qwen3.5:4b"]
    with pytest.raises(ErroProvedor, match="--sem-rotulos"):
        gerar_topicos(p)


def test_corpus_pequeno(tmp_path, apis_falsas):
    p, _ = _projeto(tmp_path, n_por_tema=5)
    with pytest.raises(ErroConfig, match="pelo menos 50"):
        gerar_topicos(p)
    assert not (p.dados / PASTA / "resultado.json").exists()


def test_medoide():
    from mapa_da_ciencia.topicos.pipeline import _medoide

    arco = np.array([[np.cos(a), np.sin(a)] for a in np.linspace(0, np.pi, 21)])
    x, y = _medoide(arco)
    assert (x, y) == pytest.approx((0.0, 1.0), abs=1e-6)  # no meio do arco, e não no centro vazio (0, 0,64)
