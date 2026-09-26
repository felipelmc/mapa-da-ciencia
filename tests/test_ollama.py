import httpx
import pytest
import respx
from conftest import DIM_FALSA, OLLAMA_FALSO, vetor_falso

from mapa_da_ciencia import recursos
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.memoria import garantir_modelo, situacao
from mapa_da_ciencia.llm.ollama import Ollama

TEXTOS = [f"texto número {i} sobre coalizões e presidencialismo" for i in range(70)]


def test_embeddings_em_lotes_na_ordem(apis_falsas):
    avancos = []
    lotes = list(Ollama().embutir_lotes("qwen3-embedding:0.6b", TEXTOS, lote=32, ao_avancar=avancos.append))
    assert [len(lote) for lote in lotes] == [32, 32, 6] and avancos == [32, 32, 6]
    assert apis_falsas.chamadas["ollama"] == 3 and apis_falsas.textos_embutidos == TEXTOS
    vetores = [v for lote in lotes for v in lote]
    assert vetores[5] == vetor_falso(TEXTOS[5]) and len(vetores[0]) == DIM_FALSA
    assert Ollama().embutir("qwen3-embedding:0.6b", TEXTOS[:3]) == vetores[:3]


def test_modelo_nao_instalado_da_a_dica_de_pull(apis_falsas):
    with pytest.raises(ErroProvedor, match=r"ollama pull bge-m3 \(download de ~1,2 GB\)"):
        Ollama().embutir("bge-m3", ["x"])


@respx.mock
def test_resposta_com_tamanho_errado_e_erro():
    respx.post(f"{OLLAMA_FALSO}/api/embed").respond(json={"embeddings": [[0.1, 0.2]]})
    with pytest.raises(ErroProvedor, match="1 embeddings para 2 textos"):
        Ollama(OLLAMA_FALSO).embutir("qwen3-embedding:0.6b", ["a", "b"])


@respx.mock
def test_ollama_fora_do_ar():
    respx.post(f"{OLLAMA_FALSO}/api/embed").mock(side_effect=httpx.ConnectError("recusada"))
    with pytest.raises(ErroProvedor, match="ollama serve"):
        Ollama(OLLAMA_FALSO).embutir("qwen3-embedding:0.6b", ["a"])


def test_garantir_modelo(apis_falsas, monkeypatch):
    ollama = Ollama()
    assert garantir_modelo(ollama, "qwen3-embedding:0.6b").digest  # instalado e cabe
    with pytest.raises(ErroProvedor, match="ollama pull gemma4:26b"):
        garantir_modelo(ollama, "gemma4:26b")
    # pouca memória: recusa carregar, mas um modelo já carregado segue (a memória livre já o desconta)
    monkeypatch.setattr(recursos, "memoria", lambda: recursos.Memoria(24, 0.5, 6.0, 7.0))
    with pytest.raises(ErroProvedor, match="Feche programas pesados"):
        garantir_modelo(ollama, "qwen3.5:9b")
    apis_falsas.carregados.add("qwen3.5:9b")
    assert situacao(ollama, "qwen3.5:9b").carregado and garantir_modelo(ollama, "qwen3.5:9b")
    ollama.descarregar("qwen3.5:9b")
    assert not apis_falsas.carregados
