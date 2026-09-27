"""`api.painel()`: o painel aberto de dentro de um notebook, e o modo Colab (pelo proxy do Google)."""

import socket
import sys
import time
import types

import httpx
import pytest

import mapa_da_ciencia.api as mapa
from mapa_da_ciencia.config import ErroConfig
from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto

PROXY = {"Host": "8765-m-abc.colab.googleusercontent.com", "Origin": "https://8765-m-abc.colab.googleusercontent.com"}


@pytest.fixture
def projeto(tmp_path):
    return Projeto.criar(tmp_path / "p", modelo="ciencia-politica", perfil=PERFIS["padrao"])


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def parar(painel: mapa.Painel) -> None:
    painel.parar()
    for _ in range(100):
        try:
            httpx.get(painel.url, timeout=0.2)
        except httpx.TransportError:
            return
        time.sleep(0.05)


def test_painel_num_notebook(projeto):
    painel = mapa.painel(projeto, porta=porta_livre(), colab=False)
    try:
        assert painel.url.startswith("http://127.0.0.1:") and painel.url in painel._repr_html_()
        assert httpx.get(f"{painel.url}api/saude").json()["projeto"] == "p"
        assert httpx.get(f"{painel.url}api/saude", headers=PROXY).status_code == 403  # fora do Colab, só daqui
        with pytest.raises(ErroConfig, match="já está em uso"):
            mapa.painel(projeto, porta=int(painel.url.rsplit(":", 1)[1].strip("/")), colab=False)
    finally:
        parar(painel)


def test_painel_no_colab(projeto, monkeypatch):
    janelas = []
    output = types.SimpleNamespace(serve_kernel_port_as_window=lambda porta, **k: janelas.append((porta, k)))
    colab = types.ModuleType("google.colab")
    colab.output = output
    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    monkeypatch.setitem(sys.modules, "google.colab", colab)

    porta = porta_livre()
    painel = mapa.painel(projeto, porta=porta)  # detecta o Colab sozinho
    try:
        assert janelas and janelas[0][0] == porta
        # o proxy chega com o endereço do Google: leitura e escrita passam
        assert httpx.get(f"{painel.url}api/saude", headers=PROXY).status_code == 200
        r = httpx.patch(f"{painel.url}api/configuracao", json={"titulo": "Oficina"}, headers=PROXY)
        assert r.status_code == 200 and Projeto.abrir(projeto.raiz).config.titulo == "Oficina"
    finally:
        parar(painel)
