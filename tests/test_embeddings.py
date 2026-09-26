import httpx
import numpy as np
import pytest
from conftest import OLLAMA_FALSO, vetor_falso

from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.documento import Documento, Texto
from mapa_da_ciencia.embeddings import PASTA, calcular_embeddings, texto_de_analise
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.manifesto import ultima_execucao
from mapa_da_ciencia.projeto import Projeto


def _doc(titulos=(), resumos=()) -> Documento:
    return Documento(
        id="S1",
        fonte="articlemeta",
        tipo="research-article",
        ano=2020,
        titulos=[Texto(idioma=i, texto=t) for i, t in titulos],
        resumos=[Texto(idioma=i, texto=t) for i, t in resumos],
    )


def test_texto_de_analise_nunca_mistura_idiomas():
    completo = _doc([("pt", "Coalizões."), ("en", "Coalitions.")], [("pt", "Resumo."), ("en", "Abstract.")])
    t = texto_de_analise(completo, "en")
    assert (t.texto, t.idioma, t.fonte) == ("Coalitions. Abstract.", "en", "resumo")
    # resumo em inglês, título só em português: vai só o resumo
    assert texto_de_analise(_doc([("pt", "Coalizões")], [("en", "Abstract.")]), "en").texto == "Abstract."
    # sem resumo em inglês: reserva, com título e resumo do mesmo idioma
    t = texto_de_analise(_doc([("pt", "Coalizões"), ("en", "Coalitions")], [("pt", "Resumo.")]), "en")
    assert (t.texto, t.idioma, t.fonte) == ("Coalizões. Resumo.", "pt", "reserva")
    # sem resumo: só o título, de preferência no idioma de análise
    t = texto_de_analise(_doc([("pt", "Coalizões"), ("en", "Coalitions")]), "en")
    assert (t.texto, t.fonte) == ("Coalitions", "so_titulo")
    assert texto_de_analise(_doc(), "en") is None


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(tmp_path / "op", modelo="vazio", perfil=PERFIS["leve"], revistas=["op"], anos=(2024, 2024))
    coletar(p)
    return p


def test_primeira_vez_calcula_e_depois_vem_do_cache(projeto, apis_falsas):
    e = calcular_embeddings(projeto)
    assert e.matriz.shape == (25, 64) and e.novos == 25 and e.do_cache == 0
    assert np.allclose(np.linalg.norm(e.matriz, axis=1), 1)
    assert e.ids == sorted(e.ids) and e.por_fonte == {"resumo": 25}
    assert np.allclose(e.matriz[0], vetor_falso(e.textos[0].texto), atol=1e-6)
    assert apis_falsas.chamadas["ollama"] == 1 and not apis_falsas.carregados  # descarregou no fim
    m = ultima_execucao(projeto, "embeddings")
    assert m["contagens"]["novos"] == 25 and m["modelos"]["embeddings"].startswith("qwen3-embedding:0.6b@")

    de_novo = calcular_embeddings(projeto)
    assert de_novo.novos == 0 and de_novo.do_cache == 25 and apis_falsas.chamadas["ollama"] == 1
    assert np.array_equal(de_novo.matriz, e.matriz)
    assert calcular_embeddings(projeto, refazer=True).novos == 25


def test_so_o_que_mudou_vai_ao_ollama(projeto, apis_falsas, monkeypatch):
    calcular_embeddings(projeto)
    antes = len(apis_falsas.textos_embutidos)
    monkeypatch.setattr("mapa_da_ciencia.embeddings.VERSAO_TEXTO", 2)  # mudar o texto invalida tudo
    assert calcular_embeddings(projeto).novos == 25
    assert len(apis_falsas.textos_embutidos) == antes + 25
    # um modelo atualizado (digest novo) ganha outro arquivo de cache, e o antigo fica como estava
    apis_falsas.digests["qwen3-embedding:0.6b"] = "fedcba9876543210"
    assert calcular_embeddings(projeto).novos == 25
    arquivos = sorted(p.name for p in (projeto.dados / PASTA).glob("*.npz"))
    assert len(arquivos) == 2 and "qwen3-embedding_0.6b@fedcba987654.npz" in arquivos


def test_ollama_fora_do_ar_usa_o_cache_completo(projeto, apis_falsas):
    calcular_embeddings(projeto)
    apis_falsas.router.get(f"{OLLAMA_FALSO}/api/tags").mock(side_effect=httpx.ConnectError("recusada"))
    e = calcular_embeddings(projeto)
    assert e.novos == 0 and "cache" in e.avisos[0]
    with pytest.raises(ErroProvedor, match="ollama serve"):
        calcular_embeddings(projeto, refazer=True)


def test_modelo_ausente(projeto, apis_falsas):
    del apis_falsas.modelos_ollama["qwen3-embedding:0.6b"]
    with pytest.raises(ErroProvedor, match=r"ollama pull qwen3-embedding:0\.6b"):
        calcular_embeddings(projeto)
