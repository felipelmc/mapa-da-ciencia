"""Rotas do projeto no painel: estado das etapas, modelos e download, estimativa, configuração e codebook."""

import threading

import pytest
import yaml
from fastapi.testclient import TestClient

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.app import criar_app
from test_servidor_jobs import LOCAL, esperar_estado, ler_sse


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    return Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )


@pytest.fixture
def cliente(projeto, tmp_path):
    with TestClient(criar_app(pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=tmp_path / "x"),
                    base_url=LOCAL) as c:  # fmt: skip
        yield c


def test_estado_das_etapas(cliente, projeto):
    e = cliente.get("/api/projeto/etapas").json()
    assert {k: v["estado"] for k, v in e.items()} == dict.fromkeys(
        ["coleta", "topicos", "geografia", "classificacao", "validacao"], "pendente"
    )
    coletar(projeto)
    mapa.classificar(projeto, limite=3, progresso=False)
    e = cliente.get("/api/projeto/etapas").json()
    assert e["coleta"]["estado"] == "em_dia" and e["coleta"]["ultima"]["contagens"]["documentos"] == 25
    assert e["topicos"]["estado"] == "pendente" and e["classificacao"]["estado"] == "desatualizada"  # parcial
    mapa.amostra_de_validacao(projeto, n=10)
    e = cliente.get("/api/projeto/etapas").json()
    assert e["validacao"] == {"estado": "desatualizada", "ultima": None, "amostra": {"n": 10, "codificados": 0}}


def test_modelos_e_download(cliente, projeto, apis_falsas):
    m = cliente.get("/api/modelos").json()
    assert m["ollama"]["no_ar"] and {x["nome"] for x in m["instalados"]} >= {"qwen3.5:4b", "qwen3-embedding:0.6b"}
    assert [p["nome"] for p in m["perfis"]] == ["leve", "padrao", "forte"] and m["perfil_sugerido"] in PERFIS
    assert m["projeto"]["classificacao"] == {"modelo": "qwen3.5:4b", "instalado": True, "download_gb": 3.4}

    assert cliente.post("/api/modelos/baixar", json={"modelo": "rm -rf /"}).status_code == 422
    job = cliente.post("/api/modelos/baixar", json={"modelo": "gemma4:26b"}).json()["id"]
    eventos = ler_sse(cliente, job)
    etapas = [d["nome"] for _, t, d in eventos if t == "etapa"]
    assert etapas == ["Baixando gemma4:26b (aaaaaaaaaaaa)", "Baixando gemma4:26b (bbbbbbbbbbbb)"]
    avancos = [(d["etapa"], d["feito"], d["total"]) for _, t, d in eventos if t == "avanco"]
    assert avancos[-1] == ("Baixando gemma4:26b (bbbbbbbbbbbb)", 2, 2)
    assert cliente.get(f"/api/jobs/{job}").json()["resumo"]["frase"] == "gemma4:26b baixado (1,5 GB)."
    assert "gemma4:26b" in {x["nome"] for x in cliente.get("/api/modelos").json()["instalados"]}

    job = cliente.post("/api/modelos/baixar", json={"modelo": "nao-existe:1b"}).json()["id"]
    j = esperar_estado(cliente, job, {"falhou"})
    assert "file does not exist" in j["erro"]


def test_estimativa_da_classificacao(cliente, projeto):
    assert cliente.get("/api/estimativa/classificacao").json()["documentos"] == 0
    coletar(projeto)
    e = cliente.get("/api/estimativa/classificacao").json()
    assert e["documentos"] == 25 and e["pendentes"] == 25 and e["estimativa_s"] is None
    mapa.classificar(projeto, limite=5, progresso=False)
    e = cliente.get("/api/estimativa/classificacao").json()
    assert (e["classificados"], e["pendentes"]) == (5, 20) and e["estimativa_s"] is not None


def test_configuracao_sem_perder_comentarios(cliente, projeto):
    arquivo = projeto.raiz / "mapa.yaml"
    assert cliente.get("/api/configuracao").json()["recorte"]["anos"] == [2024, 2024]
    r = cliente.patch("/api/configuracao", json={"recorte": {"anos": [2020, 2024]}, "titulo": "OP, 2020–2024"})
    assert r.status_code == 200 and r.json()["recorte"]["anos"] == [2020, 2024]
    texto = arquivo.read_text(encoding="utf-8")
    assert "# SciELO Brasil" in texto and "OP, 2020–2024" in texto and "# Opinião Pública" in texto
    assert yaml.safe_load(texto)["recorte"]["anos"] == [2020, 2024]
    assert projeto.config.recorte.anos == (2020, 2024)  # o projeto aberto no painel já vê a mudança

    antes = arquivo.read_text(encoding="utf-8")
    r = cliente.patch("/api/configuracao", json={"recorte": {"anos": ["dois mil"]}})
    assert r.status_code == 422 and "mapa.yaml ficaria inválido" in r.json()["detail"]
    assert arquivo.read_text(encoding="utf-8") == antes
    r = cliente.patch("/api/configuracao", json={"titulo": "x"}, headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403


def test_codebook(cliente, projeto):
    cb = cliente.get("/api/codebook").json()
    assert cb["hash"] == projeto.codebook.hash() and cb["variaveis"][0]["id"] == "abordagem"
    cb["variaveis"][0]["categorias"][0]["definicao"] = "Números e estatística."
    novo = cliente.put("/api/codebook", json=cb).json()
    assert (
        novo["hash"] != cb["hash"] and projeto.codebook.variaveis[0].categorias[0].definicao == "Números e estatística."
    )
    texto = (projeto.raiz / "codebook.yaml").read_text(encoding="utf-8")
    assert texto.startswith("# Codebook de exemplo") and "Números e estatística." in texto

    cb["variaveis"][0]["categorias"] = cb["variaveis"][0]["categorias"][:1]  # categórica com uma categoria só
    r = cliente.put("/api/codebook", json=cb)
    assert r.status_code == 422 and "codebook.yaml ficaria inválido" in r.json()["detail"]


def test_nao_muda_o_projeto_com_uma_etapa_rodando(projeto, tmp_path):
    liberar = threading.Event()

    def lenta(p, o, progresso):
        progresso.etapa("Esperando")
        liberar.wait(10)

    app = criar_app(
        pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=tmp_path / "x", etapas={"lenta": lenta}
    )
    with TestClient(app, base_url=LOCAL) as c:
        job = c.post("/api/etapas/lenta").json()["id"]
        esperar_estado(c, job, {"rodando"})
        assert c.patch("/api/configuracao", json={"titulo": "x"}).status_code == 409
        assert c.put("/api/codebook", json=c.get("/api/codebook").json()).status_code == 409
        liberar.set()
        esperar_estado(c, job, {"concluido"})
        assert c.patch("/api/configuracao", json={"titulo": "x"}).status_code == 200
