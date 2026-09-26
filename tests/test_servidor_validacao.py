"""API local da codificação: fila cega por codificador, gravação com conferência de origem e métricas ao vivo."""

import pytest
from fastapi.testclient import TestClient

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.coleta import coletar
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.app import criar_app
from mapa_da_ciencia.validacao import amostra as va

LOCAL = "http://127.0.0.1:8765"


@pytest.fixture
def projeto(tmp_path, apis_falsas):
    p = Projeto.criar(
        tmp_path / "op", modelo="ciencia-politica", perfil=PERFIS["leve"], revistas=["0104-6276"], anos=(2024, 2024)
    )
    coletar(p)
    cfg = p.raiz / "mapa.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("n: 200", "n: 10"), encoding="utf-8")
    return Projeto.abrir(p.raiz)


def _cliente(p: Projeto, tmp_path, base: str = LOCAL) -> TestClient:
    return TestClient(criar_app(pasta_dados=p.saida / "dados", projeto=p, estatico=tmp_path / "x"), base_url=base)


def _respostas(p: Projeto, abordagem: str = "quantitativa") -> dict:
    saida = {}
    for v in p.codebook.variaveis:
        valor = {"booleana": True, "texto": "2010–2020"}.get(v.tipo) or v.categorias[0].valor
        saida[v.id] = {"valor": abordagem if v.id == "abordagem" else valor}
    return saida


def test_sem_amostra(projeto, tmp_path):
    c = _cliente(projeto, tmp_path)
    r = c.get("/api/validacao/fila", params={"codificador": "maria"})
    assert r.status_code == 404 and "validar amostra" in r.json()["detail"]


def test_fila_cega_e_embaralhada_por_codificador(projeto, tmp_path):
    a = va.sortear(projeto)
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    c = _cliente(projeto, tmp_path)
    f = c.get("/api/validacao/fila", params={"codificador": "maria"}).json()
    docs = [x["doc"] for x in f["fila"]]
    assert sorted(docs) == sorted(a.docs) and f["tipo"] is None and f["amostra"]["n"] == 10
    assert f["codebook"]["hash"] == projeto.codebook.hash()
    assert all(set(x) == {"doc", "titulo", "resumo", "idioma", "respostas", "completa"} for x in f["fila"])
    assert all(x["respostas"] == {} and not x["completa"] for x in f["fila"])  # nada do modelo
    outra = [x["doc"] for x in c.get("/api/validacao/fila", params={"codificador": "joao"}).json()["fila"]]
    assert outra != docs and [x["doc"] for x in c.get("/api/validacao/fila?codificador=maria").json()["fila"]] == docs
    assert c.get("/api/validacao/fila", params={"codificador": "Ma ria"}).status_code == 400


def test_gravar_parcial_completa_e_retomar(projeto, tmp_path):
    va.sortear(projeto)
    c = _cliente(projeto, tmp_path)
    doc = c.get("/api/validacao/fila?codificador=maria").json()["fila"][0]["doc"]
    url = f"/api/validacao/codificacoes/{doc}"
    r = c.put(url, json={"codificador": "maria", "respostas": {"abordagem": {"valor": "qualitativa", "incerto": True}}})
    assert r.status_code == 200 and r.json() == {"ok": True, "completa": False}
    r = c.put(url, json={"codificador": "maria", "respostas": {"abordagem": {"valor": "x"}}})
    assert r.status_code == 422 and "não é uma das categorias" in r.json()["detail"]["problemas"][0]
    r = c.put(url, json={"codificador": "maria", "respostas": {"abordagem": {"valor": "mista"}}, "completa": True})
    assert r.status_code == 422  # faltam variáveis
    r = c.put(url, json={"codificador": "maria", "respostas": _respostas(projeto, "mista"), "completa": True})
    assert r.json() == {"ok": True, "completa": True}

    f = c.get("/api/validacao/fila?codificador=maria").json()
    ficha = next(x for x in f["fila"] if x["doc"] == doc)
    assert ficha["completa"] and ficha["respostas"]["abordagem"] == {
        "valor": "mista",
        "evidencia": "",
        "incerto": False,
        "nota": "",
    }
    assert ficha["respostas"]["brasil_como_caso"]["valor"] is True and f["tipo"] == "humano"
    assert c.put("/api/validacao/codificacoes/S0000", json={"codificador": "maria", "respostas": {}}).status_code == 404


def test_escrita_so_desta_maquina(projeto, tmp_path):
    va.sortear(projeto)
    doc = va.ler(projeto).docs[0]
    corpo = {"codificador": "maria", "respostas": {"abordagem": {"valor": "mista"}}}
    url = f"/api/validacao/codificacoes/{doc}"
    c = _cliente(projeto, tmp_path)
    assert c.put(url, json=corpo, headers={"Origin": "https://malicioso.example"}).status_code == 403
    assert c.put(url, json=corpo, headers={"Origin": "http://localhost:5173"}).status_code == 200
    fora = _cliente(projeto, tmp_path, base="http://painel.example")  # DNS apontado para cá
    assert fora.put(url, json=corpo).status_code == 403
    assert va.codificacoes(projeto, "maria")[0]["valor"] == "mista"


def test_metricas_ao_vivo_com_divergencias_de_pessoas(projeto, tmp_path):
    a = va.sortear(projeto)
    mapa.classificar(projeto, somente_amostra=True, progresso=False)
    c = _cliente(projeto, tmp_path)
    for i, doc in enumerate(a.docs):
        corpo = {"codificador": "maria", "respostas": _respostas(projeto, "mista" if i < 2 else "quantitativa")}
        assert c.put(f"/api/validacao/codificacoes/{doc}", json={**corpo, "completa": True}).status_code == 200
    v = c.get("/api/validacao/metricas").json()
    assert [(x["nome"], x["tipo"]) for x in v["codificadores"]] == [("maria", "humano"), ("qwen3.5:4b", "modelo")]
    m = next(x for x in v["metricas"] if x["variavel"] == "abordagem")
    assert m["concordancia"] == 0.8 and m["comparacao"] == "maria × qwen3.5:4b"
    assert len(v["divergencias"]) == 2 and {d["codificador"] for d in v["divergencias"]} == {"maria"}


def test_site_sem_api_nao_tem_rotas_de_validacao(projeto, tmp_path):
    app = criar_app(pasta_dados=projeto.saida / "dados", projeto=projeto, api=False, estatico=tmp_path / "x")
    assert TestClient(app, base_url=LOCAL).get("/api/validacao/fila?codificador=a").status_code == 404


def test_sortear_a_amostra_pelo_painel(projeto, tmp_path):
    c = _cliente(projeto, tmp_path)
    r = c.post("/api/validacao/amostra", json={"n": 6})
    assert r.status_code == 200 and r.json()["n"] == 6 and r.json()["estratificar_por"] == "revista"
    assert (projeto.raiz / "validacao" / "amostra.jsonl").exists()
    assert c.post("/api/validacao/amostra", json={"n": 8}).status_code == 409
    assert c.post("/api/validacao/amostra", json={"n": 8, "refazer": True}).json()["n"] == 8
    assert c.post("/api/validacao/amostra", json={}, headers={"Origin": "https://malicioso.example"}).status_code == 403
