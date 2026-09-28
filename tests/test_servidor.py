import pytest
from fastapi.testclient import TestClient

from mapa_da_ciencia.contrato.exemplo import gerar_exemplo
from mapa_da_ciencia.contrato.exportar import escrever_dados
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.app import criar_app


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(tmp_path / "p", modelo="ciencia-politica", perfil=PERFIS["padrao"])


def test_projeto_vazio_serve_manifesto_minimo_com_api(projeto, tmp_path):
    app = criar_app(pasta_dados=projeto.saida / "dados", projeto=projeto, estatico=tmp_path / "sem-build")
    c = TestClient(app, base_url="http://127.0.0.1")
    m = c.get("/dados/manifesto.json").json()
    assert m["api"] is True
    assert m["arquivos"] == ["manifesto"]
    assert m["contagens"]["documentos"] == 0
    assert m["recorte"]["fontes"] == ["scielo:scl", "openalex"]
    assert c.get("/dados/documentos.json").status_code == 404
    info = c.get("/api/projeto").json()
    assert info["nome"] == "p" and info["etapas"]["coleta"] is None
    assert c.get("/api/saude").json()["ok"] is True


def test_sem_build_explica_como_compilar(projeto, tmp_path):
    c = TestClient(
        criar_app(pasta_dados=tmp_path / "d", projeto=projeto, estatico=tmp_path / "sem-build"),
        base_url="http://127.0.0.1",
    )
    r = c.get("/")
    assert r.status_code == 200
    assert "npm run empacotar" in r.text


def test_exemplo_estatico_sem_api(tmp_path):
    dados = tmp_path / "dados"
    escrever_dados(dados, *gerar_exemplo(n_docs=80))
    estatico = tmp_path / "estatico"
    estatico.mkdir()
    (estatico / "index.html").write_text("<!doctype html><title>app</title>")
    c = TestClient(criar_app(pasta_dados=dados, api=False, estatico=estatico), base_url="http://127.0.0.1")
    assert c.get("/dados/manifesto.json").json()["api"] is False
    assert c.get("/dados/documentos.json").json()["n"] == 80
    assert c.get("/dados/detalhes/00.json").status_code in (200, 404)
    assert "<title>app</title>" in c.get("/").text
    assert c.get("/api/projeto").status_code == 404


def test_so_responde_a_host_local_em_todas_as_rotas(tmp_path):
    """Contra DNS apontado para cá: /dados/ e a interface também exigem um Host local (não só /api/)."""
    from fastapi.testclient import TestClient

    from mapa_da_ciencia.servidor.app import criar_app

    (tmp_path / "dados").mkdir()
    app = criar_app(pasta_dados=tmp_path / "dados", estatico=tmp_path)
    fora = TestClient(app, base_url="http://rebind.exemplo.invalid")
    for rota in ("/dados/manifesto.json", "/openapi.json", "/", "/api/saude"):
        assert fora.get(rota).status_code == 403, rota
    assert TestClient(app, base_url="http://127.0.0.1").get("/api/saude").status_code == 200


def test_no_colab_a_escrita_de_outra_pagina_e_recusada(tmp_path):
    from fastapi.testclient import TestClient

    from mapa_da_ciencia.llm.perfis import PERFIS
    from mapa_da_ciencia.projeto import Projeto
    from mapa_da_ciencia.servidor.app import criar_app

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    app = criar_app(pasta_dados=p.saida / "dados", projeto=p, estatico=tmp_path, so_local=False)
    cliente = TestClient(app, base_url="https://8765-m-abc.colab.googleusercontent.com")
    for origem in ("https://outro.exemplo", "null"):
        r = cliente.patch("/api/configuracao", json={}, headers={"Origin": origem})
        assert r.status_code == 403, origem
    # a própria página do Colab grava (qualquer outra resposta, e não só um 403, quebraria o painel no Colab)
    r = cliente.patch(
        "/api/configuracao", json={}, headers={"Origin": "https://8765-m-abc.colab.googleusercontent.com"}
    )
    assert r.status_code == 200, r.text
