"""Jobs do painel: etapas em segundo plano, progresso por SSE com retomada, cancelamento e falhas."""

import json
import threading
import time
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor import jobs as modulo_jobs
from mapa_da_ciencia.servidor.app import criar_app
from mapa_da_ciencia.servidor.jobs import Jobs

LOCAL = "http://127.0.0.1:8765"


@dataclass
class ResumoFalso:
    n: int

    def __str__(self) -> str:
        return f"{self.n} passos feitos."


class Etapas:
    """Etapas falsas: `lenta` espera a liberação a cada passo; `longa` avança sem parar; `falha` dá erro."""

    def __init__(self) -> None:
        self.liberar = threading.Event()

    def lenta(self, projeto, opcoes, progresso):
        progresso.etapa("Passos", total=3)
        for _ in range(3):
            assert self.liberar.wait(10)
            progresso.avancar()
        progresso.mensagem(f"opções: {json.dumps(opcoes)}")
        return ResumoFalso(3)

    def longa(self, projeto, opcoes, progresso):
        progresso.etapa("Muitos passos", total=10_000)
        for _ in range(10_000):
            time.sleep(0.005)
            progresso.avancar()
        return ResumoFalso(10_000)

    def falha(self, projeto, opcoes, progresso):
        progresso.etapa("Tentando")
        raise ErroConfig("O projeto ainda não tem corpus.")

    def registro(self):
        return {"lenta": self.lenta, "longa": self.longa, "falha": self.falha}


@pytest.fixture
def etapas(monkeypatch):
    monkeypatch.setattr(modulo_jobs, "INTERVALO_AVANCO", 0)
    return Etapas()


@pytest.fixture
def cliente(tmp_path, etapas):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    app = criar_app(pasta_dados=p.saida / "dados", projeto=p, estatico=tmp_path / "x", etapas=etapas.registro())
    with TestClient(app, base_url=LOCAL) as c:
        c.projeto = p
        yield c


def ler_sse(cliente, job, **headers):
    """Os eventos do fluxo SSE até o `fim`, como (id, tipo, dados)."""
    eventos, atual = [], {}
    with cliente.stream("GET", f"/api/jobs/{job}/eventos", headers=headers) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        for linha in r.iter_lines():
            if not linha:
                if "event" in atual:
                    eventos.append((int(atual["id"]), atual["event"], json.loads(atual["data"])))
                    if atual["event"] == "fim":
                        break
                atual = {}
                continue
            if linha.startswith(":"):
                continue
            chave, _, valor = linha.partition(": ")
            atual[chave] = valor
    return eventos


def esperar_estado(cliente, job, estados, tempo=10):
    fim = time.monotonic() + tempo
    while time.monotonic() < fim:
        j = cliente.get(f"/api/jobs/{job}").json()
        if j["estado"] in estados:
            return j
        time.sleep(0.02)
    raise AssertionError(f"o job não chegou a {estados}: {j}")


def test_etapa_com_progresso_ao_vivo_e_uma_por_vez(cliente, etapas):
    r = cliente.post("/api/etapas/lenta", json={"limite": 5})
    assert r.status_code == 202
    job = r.json()["id"]
    esperar_estado(cliente, job, {"rodando"})
    ocupado = cliente.post("/api/etapas/falha")
    assert ocupado.status_code == 409 and ocupado.json()["detail"]["job"]["id"] == job

    etapas.liberar.set()
    eventos = ler_sse(cliente, job)
    tipos = [t for _, t, _ in eventos]
    assert tipos[0] == "estado" and tipos[-2:] == ["resumo", "fim"]
    assert [i for i, _, _ in eventos] == list(range(1, len(eventos) + 1))  # ids em sequência
    assert ("etapa", {"nome": "Passos", "total": 3}) in [(t, d) for _, t, d in eventos]
    avancos = [d["feito"] for _, t, d in eventos if t == "avanco"]
    assert avancos[-1] == 3 and avancos == sorted(avancos)
    assert any(t == "mensagem" and '"limite": 5' in d["texto"] for _, t, d in eventos)
    fim = eventos[-1][2]
    assert fim == {"estado": "concluido"}

    j = cliente.get(f"/api/jobs/{job}").json()
    assert j["estado"] == "concluido" and j["resumo"] == {"frase": "3 passos feitos.", "n": 3}
    assert j["inicio"] and j["fim"] and [x["id"] for x in cliente.get("/api/jobs").json()] == [job]


def test_reconexao_recebe_so_o_que_perdeu(cliente, etapas):
    job = cliente.post("/api/etapas/lenta").json()["id"]
    etapas.liberar.set()
    tudo = ler_sse(cliente, job)
    meio = tudo[len(tudo) // 2][0]
    depois = ler_sse(cliente, job, **{"Last-Event-ID": str(meio)})
    assert depois == [e for e in tudo if e[0] > meio]
    assert ler_sse(cliente, job) == tudo  # relido do banco, igual
    r = cliente.get(f"/api/jobs/{job}/eventos?desde={tudo[-2][0]}")
    assert "event: fim" in r.text and "event: resumo" not in r.text


def test_cancelar_para_no_proximo_avanco(cliente):
    job = cliente.post("/api/etapas/longa").json()["id"]
    esperar_estado(cliente, job, {"rodando"})
    time.sleep(0.1)
    assert cliente.delete(f"/api/jobs/{job}").status_code == 200
    j = esperar_estado(cliente, job, {"cancelado"})
    assert j["fim"] and j["resumo"] is None
    eventos = ler_sse(cliente, job)
    assert eventos[-1][1:] == ("fim", {"estado": "cancelado"})
    feitos = [d["feito"] for _, t, d in eventos if t == "avanco"]
    assert 0 < feitos[-1] < 10_000
    # depois de cancelado, outra etapa pode rodar
    assert cliente.post("/api/etapas/falha").status_code == 202


def test_falha_vira_erro_no_job(cliente):
    job = cliente.post("/api/etapas/falha").json()["id"]
    eventos = ler_sse(cliente, job)
    assert [t for _, t, _ in eventos][-2:] == ["erro", "fim"]
    assert eventos[-2][2] == {"mensagem": "O projeto ainda não tem corpus."}
    j = cliente.get(f"/api/jobs/{job}").json()
    assert (j["estado"], j["erro"]) == ("falhou", "O projeto ainda não tem corpus.")


def test_rotas_desconhecidas_e_escrita_de_fora(cliente, tmp_path):
    assert cliente.post("/api/etapas/nada").status_code == 404
    assert cliente.get("/api/jobs/naoexiste").status_code == 404
    r = cliente.post("/api/etapas/lenta", headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403
    assert cliente.get("/api/jobs").json() == []


def test_job_interrompido_numa_sessao_anterior(tmp_path, etapas):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    jobs = Jobs(p, etapas.registro())
    job = jobs.iniciar("lenta")
    esperar = time.monotonic() + 5
    while jobs.obter(job.id).estado != "rodando" and time.monotonic() < esperar:
        time.sleep(0.01)
    # o painel caiu com o job rodando: ao abrir de novo, ele aparece como falho, e outro pode começar
    etapas.liberar.set()
    jobs._executor.shutdown(wait=True)
    import sqlite3

    with sqlite3.connect(p.estado) as con:
        con.execute("UPDATE jobs SET estado = 'rodando' WHERE id = ?", (job.id,))
    de_novo = Jobs(p, etapas.registro())
    j = de_novo.obter(job.id)
    assert j.estado == "falhou" and "interrompido" in j.erro
    assert de_novo.iniciar("lenta").estado == "na_fila"
    de_novo.fechar()


def test_opcoes_das_etapas_reais_sao_validadas(tmp_path):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    with TestClient(criar_app(pasta_dados=p.saida / "dados", projeto=p, estatico=tmp_path / "x"), base_url=LOCAL) as c:
        r = c.post("/api/etapas/classificacao", json={"limite": 0})
        assert r.status_code == 422 and r.json()["detail"]["problemas"]
        assert c.post("/api/etapas/coleta", json={"desconhecida": True}).status_code == 422
        # sem corpus, a etapa começa e falha com a mensagem da CLI
        for etapa in ("geografia", "topicos"):
            job = c.post(f"/api/etapas/{etapa}").json()["id"]
            j = esperar_estado(c, job, {"falhou"})
            assert "Rode `mapa coletar`" in j["erro"], (etapa, j["erro"])


def test_site_estatico_nao_tem_rotas_de_escrita(tmp_path):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    app = criar_app(pasta_dados=p.saida / "dados", projeto=p, api=False, estatico=tmp_path / "x")
    with TestClient(app, base_url=LOCAL) as c:
        assert c.post("/api/etapas/coleta").status_code in (404, 405)
        assert c.get("/api/jobs").status_code == 404
