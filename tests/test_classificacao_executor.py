"""O executor da classificação contra o Ollama falso (classificacao/executor.py)."""

import json
from importlib import resources
from pathlib import Path

import pytest
from conftest import resposta_classificacao_falsa

from mapa_da_ciencia.classificacao import executor as ex
from mapa_da_ciencia.classificacao.executor import Classificador, Texto, textos_para_classificar
from mapa_da_ciencia.config import ModeloLLM, carregar_codebook
from mapa_da_ciencia.documento import Documento
from mapa_da_ciencia.documento import Texto as TextoDoc
from mapa_da_ciencia.llm.base import ErroProvedor

CODEBOOK = carregar_codebook(Path(str(resources.files("mapa_da_ciencia.modelos_projeto") / "codebook-exemplo.yaml")))
TEXTOS = [
    Texto(
        f"d{i}", f"Título {i}", f"Este artigo número {i} analisa eleições municipais no Brasil com dados do TSE.", "pt"
    )
    for i in range(4)
]


@pytest.fixture
def classificador(tmp_path, apis_falsas):
    def novo(**cfg) -> Classificador:
        return Classificador(ModeloLLM(modelo="qwen3.5:9b", **cfg), CODEBOOK, tmp_path / "estado.sqlite")

    return novo


def test_classifica_confere_e_retoma_do_cache(classificador, apis_falsas):
    c = classificador()
    r = list(c.classificar(TEXTOS[:3]))
    assert [x.doc for x in r] == ["d0", "d1", "d2"] and c.contadores.chamadas == 3 and c.contadores.novos == 3
    x = r[0]
    assert x.valores["abordagem"] == "quantitativa" and x.valores["brasil_como_caso"] is True
    assert x.conferencias["abordagem"].status == "literal" and x.conferencias["abordagem"].inicio == 0
    assert x.tentativas == 1 and x.valida_na_primeira and not x.do_cache
    c.fim()
    assert "qwen3.5:9b" not in apis_falsas.carregados  # a etapa carregou, a etapa descarrega

    de_novo = classificador()
    r2 = list(de_novo.classificar(TEXTOS))
    assert de_novo.contadores.do_cache == 3 and de_novo.contadores.chamadas == 1  # só o d3 é novo
    assert [x.doc for x in r2[:3]] == ["d0", "d1", "d2"] and all(x.do_cache for x in r2[:3])
    assert de_novo.pendentes(TEXTOS) == []


def test_nova_tentativa_quando_a_evidencia_nao_esta_no_texto(classificador, apis_falsas):
    respostas = iter(["inventada", None])

    def responder(corpo):
        saida = json.loads(resposta_classificacao_falsa(corpo))
        if next(respostas) is not None:
            saida["subarea"]["evidencia"] = "um trecho que não está no resumo de jeito nenhum"
        return json.dumps(saida)

    apis_falsas.responder_chat = responder
    c = classificador()
    (x,) = c.classificar(TEXTOS[:1])
    assert x.tentativas == 2 and x.conferencias["subarea"].status == "literal"
    correcao = apis_falsas.pedidos_chat[-1]["messages"][-1]["content"]
    assert "`subarea`" in correcao and apis_falsas.pedidos_chat[-1]["messages"][-2]["role"] == "assistant"


def test_resposta_fora_do_codebook_nao_vai_para_o_cache(classificador, apis_falsas):
    apis_falsas.responder_chat = lambda corpo: json.dumps({"abordagem": {"evidencia": "x", "valor": "outra"}})
    c = classificador()
    assert list(c.classificar(TEXTOS[:1])) == [] and c.contadores.falhas == ["d0"] and c.contadores.chamadas == 2
    apis_falsas.responder_chat = lambda corpo: "isto não é JSON"
    c = classificador()
    assert list(c.classificar(TEXTOS[:1])) == [] and c.contadores.chamadas == 2  # pediu de novo: nada guardado
    apis_falsas.responder_chat = resposta_classificacao_falsa
    assert len(list(classificador().classificar(TEXTOS[:1]))) == 1


def test_concorrencia(classificador):
    c = classificador(concorrencia=3)
    assert sorted(x.doc for x in c.classificar(TEXTOS)) == ["d0", "d1", "d2", "d3"] and c.contadores.novos == 4


def test_para_quando_a_memoria_acaba(classificador, monkeypatch):
    monkeypatch.setattr(ex, "memoria_critica", lambda: True)
    with pytest.raises(ErroProvedor, match="memória"):
        list(classificador().classificar(TEXTOS[:1]))


def test_chave_muda_com_o_codebook_e_o_modelo(classificador, tmp_path, apis_falsas):
    list(classificador().classificar(TEXTOS[:1]))
    outro = CODEBOOK.model_copy(update={"versao": "0.2"})
    c = Classificador(ModeloLLM(modelo="qwen3.5:9b"), outro, tmp_path / "estado.sqlite")
    assert c.pendentes(TEXTOS[:1]) == TEXTOS[:1]
    apis_falsas.digests["qwen3.5:9b"] = "abcdef012345"  # modelo atualizado
    assert classificador().pendentes(TEXTOS[:1]) == TEXTOS[:1]


def test_textos_para_classificar():
    def doc(id_, resumos=(), titulos=()):
        return Documento(
            id=id_, fonte="articlemeta", tipo="research-article", ano=2020,
            resumos=[TextoDoc(idioma=i, texto=t) for i, t in resumos],
            titulos=[TextoDoc(idioma=i, texto=t) for i, t in titulos],
        )  # fmt: skip

    docs = [
        doc("a", [("en", "Abstract."), ("pt", "Resumo.")], [("pt", "Título")]),
        doc("b", [("en", "Only English.")], [("en", "Title"), ("pt", "Título")]),
        doc("c", [], [("pt", "Só título")]),
    ]
    textos, sem = textos_para_classificar(docs, ["pt", "en"])
    assert [(t.doc, t.resumo, t.titulo) for t in textos] == [
        ("a", "Resumo.", "Título"),
        ("b", "Only English.", "Title"),
    ]
    assert sem == ["c"]
