import json

import pytest

from mapa_da_ciencia.config import ErroConfig, ModeloLLM
from mapa_da_ciencia.llm.base import ErroProvedor
from mapa_da_ciencia.llm.cache import CacheLLM
from mapa_da_ciencia.llm.ollama import Ollama
from mapa_da_ciencia.topicos import rotulos as R
from mapa_da_ciencia.topicos.rotulos import EntradaTopico, Rotulador, Rotulo, acentos_perdidos, ler_manuais

CFG = ModeloLLM(modelo="qwen3.5:9b")
ENTRADAS = {
    3: EntradaTopico(["coalizão", "congresso", "agenda legislativa"], ["Coalizões no Congresso", "Agenda e veto"]),
    7: EntradaTopico(["gênero", "mulheres", "política"], ["Mulheres na política", "Cotas de gênero"]),
}


def _rotulador(tmp_path, **kw):
    return Rotulador(CFG, tmp_path / "estado.sqlite", ollama=Ollama(), **kw)


def test_acentos_perdidos_e_correcao():
    assert acentos_perdidos("Genero e politica no Brasil", ["gênero", "política pública"]) == {
        "genero": "gênero",
        "politica": "política",
    }
    assert acentos_perdidos("Gênero e política", ["gênero", "política"]) == {}
    assert R._corrigir("Genero e politica", {"genero": "gênero", "politica": "política"}) == "Gênero e política"


def test_acentos_ambiguos_nao_contam():
    # "é" e "à" dos títulos não são a forma certa de "e" e "a" (o erro da versão 1 no piloto)
    titulos = ["Democracia é o regime da maioria?", "Gramsci e à esquerda", "A crítica da razão"]
    assert acentos_perdidos("Financiamento eleitoral e gênero; a esquerda", titulos) == {}
    assert acentos_perdidos("Ele critica a esta hora", ["crítica", "está"]) == {}  # verbos sem acento
    assert acentos_perdidos("politica e Politica", ["política", "politica"]) == {}  # as duas formas no vocabulário
    assert acentos_perdidos("Genero", ["gênero é tema"]) == {"genero": "gênero"}


def test_rotulos_pelo_modelo_e_cache(tmp_path, apis_falsas):
    r = _rotulador(tmp_path)
    saida = r.topicos(ENTRADAS, sem_llm=False, manuais=ler_manuais(tmp_path))
    assert saida[3] == Rotulo("Coalizão e congresso", "Trabalhos sobre coalizão e congresso.", "llm")
    assert r.resumo.chamadas == 2 and r.resumo.modelo.startswith("qwen3.5:9b@")
    pedido = apis_falsas.pedidos_chat[0]["messages"][-1]["content"]
    assert pedido.startswith("Palavras-chave: coalizão, congresso") and "- Agenda e veto" in pedido
    r.fim()
    assert not apis_falsas.carregados  # descarregou o modelo que carregou
    de_novo = _rotulador(tmp_path)
    assert de_novo.topicos(ENTRADAS, sem_llm=False, manuais=ler_manuais(tmp_path)) == saida
    assert de_novo.resumo.chamadas == 0 and de_novo.resumo.do_cache == 2


def test_acento_perdido_gera_nova_tentativa_com_outro_pedido(tmp_path, apis_falsas):
    respostas = iter(["Genero e politica", "Gênero e política"])
    apis_falsas.responder_chat = lambda _: json.dumps({"rotulo": next(respostas), "descricao": "Sobre mulheres."})
    r = _rotulador(tmp_path)
    saida = r.topicos({7: ENTRADAS[7]}, sem_llm=False, manuais=ler_manuais(tmp_path))
    assert saida[7].rotulo == "Gênero e política" and r.resumo.chamadas == 2
    assert "'gênero'" in apis_falsas.pedidos_chat[1]["messages"][-1]["content"]


def test_acento_que_continua_perdido_e_corrigido(tmp_path, apis_falsas):
    apis_falsas.responder_chat = lambda _: json.dumps({"rotulo": "Genero e politica", "descricao": "Genero."})
    r = _rotulador(tmp_path)
    saida = r.topicos({7: ENTRADAS[7]}, sem_llm=False, manuais=ler_manuais(tmp_path))
    assert (saida[7].rotulo, saida[7].descricao) == ("Gênero e política", "Gênero.")
    assert r.resumo.acentos_corrigidos == 1
    with CacheLLM(tmp_path / "estado.sqlite") as cache:
        assert cache.contar(R.TAREFA) == 1  # guardou a versão corrigida


def test_topico_casado_com_palavras_parecidas_mantem_o_rotulo(tmp_path, apis_falsas):
    anterior = Rotulo("Coalizões e agenda", "Presidencialismo de coalizão.", "llm")
    parecido = EntradaTopico(ENTRADAS[3].palavras, [], anterior, ["coalizão", "congresso", "veto"])
    diferente = EntradaTopico(ENTRADAS[7].palavras, ["x"], anterior, ["polícia", "crime", "prisões"])
    r = _rotulador(tmp_path)
    saida = r.topicos({3: parecido, 7: diferente}, sem_llm=False, manuais=ler_manuais(tmp_path))
    assert saida[3] == anterior and saida[7].rotulo == "Gênero e mulheres"
    assert r.resumo.reaproveitados == 1 and r.resumo.chamadas == 1


def test_rotulos_yaml_tem_prioridade(tmp_path, apis_falsas):
    (tmp_path / "rotulos.yaml").write_text(
        "topicos:\n  3: {rotulo: Presidencialismo de coalizão, descricao: Como governam os presidentes.}\n"
        "macrotemas:\n  0: {rotulo: Instituições}\n",
        encoding="utf-8",
    )
    manuais = ler_manuais(tmp_path)
    r = _rotulador(tmp_path)
    saida = r.topicos(ENTRADAS, sem_llm=False, manuais=manuais)
    assert saida[3] == Rotulo("Presidencialismo de coalizão", "Como governam os presidentes.", "manual")
    macros = r.macrotemas(
        {0: [3, 7], 1: [7]}, saida, {0: [("x", 1.0)], 1: [("gênero", 2.0)]}, sem_llm=False, manuais=manuais
    )
    assert macros[0].fonte == "manual" and macros[1].fonte == "llm"
    assert "- Presidencialismo de coalizão" not in apis_falsas.pedidos_chat[-1]["messages"][-1]["content"]
    (tmp_path / "rotulos.yaml").write_text("topicos:\n  3: rotulo sem chaves\n", encoding="utf-8")
    with pytest.raises(ErroConfig, match=r"rotulos\.yaml inválido"):
        ler_manuais(tmp_path)


def test_sem_llm_usa_as_palavras_chave(tmp_path, apis_falsas):
    del apis_falsas.modelos_ollama["qwen3.5:9b"]  # nem precisa do modelo
    r = _rotulador(tmp_path)
    saida = r.topicos(ENTRADAS, sem_llm=True, manuais=ler_manuais(tmp_path))
    assert saida[3] == Rotulo(
        "coalizão, congresso, agenda legislativa",
        "Palavras-chave: coalizão, congresso, agenda legislativa.",
        "palavras",
    )
    macros = r.macrotemas(
        {0: [3]}, saida, {0: [("coalizão", 3.0), ("veto", 5.0)]}, sem_llm=True, manuais=ler_manuais(tmp_path)
    )
    assert macros[0].rotulo == "veto, coalizão" and apis_falsas.chamadas["ollama_chat"] == 0


def test_modelo_ausente_e_memoria_que_acaba(tmp_path, apis_falsas, monkeypatch):
    del apis_falsas.modelos_ollama["qwen3.5:9b"]
    with pytest.raises(ErroProvedor, match=r"ollama pull qwen3\.5:9b"):
        _rotulador(tmp_path).topicos(ENTRADAS, sem_llm=False, manuais=ler_manuais(tmp_path))
    apis_falsas.modelos_ollama["qwen3.5:9b"] = 0.5
    monkeypatch.setattr(R, "memoria_critica", lambda: True)
    with pytest.raises(ErroProvedor, match="memória do computador acabou"):
        _rotulador(tmp_path).topicos(ENTRADAS, sem_llm=False, manuais=ler_manuais(tmp_path))
