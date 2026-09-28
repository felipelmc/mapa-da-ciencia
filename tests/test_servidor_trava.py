"""Um painel por projeto: o segundo `mapa painel` no mesmo projeto não abre e aponta o primeiro."""

import gc
import sys
import time

import pytest

from mapa_da_ciencia.llm.perfis import PERFIS
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.servidor.trava import ARQUIVO, PainelJaAberto, travar

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="sem fcntl no Windows")


def test_um_painel_por_projeto(tmp_path):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    outro = Projeto.criar(tmp_path / "q", modelo="vazio", perfil=PERFIS["leve"])
    primeiro = travar(p, 8765)
    with pytest.raises(PainelJaAberto, match=r"http://127\.0\.0\.1:8765/"):
        travar(p, 8766)
    # outro projeto abre normalmente, ao mesmo tempo
    segundo = travar(outro, 8767)
    # fechado o primeiro painel, o projeto abre de novo, e o arquivo fica fora do git do projeto
    primeiro.close()
    terceiro = travar(p, 8768)
    assert '"porta": 8768' in (p.raiz / ARQUIVO).read_text(encoding="utf-8")
    assert ARQUIVO in (p.raiz / ".gitignore").read_text(encoding="utf-8")
    terceiro.close()
    segundo.close()


def test_um_projeto_antigo_ganha_a_trava_no_gitignore(tmp_path):
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    ignorar = p.raiz / ".gitignore"
    ignorar.write_text(ignorar.read_text(encoding="utf-8").replace(f"{ARQUIVO}\n", ""), encoding="utf-8")
    travar(p, 8765).close()
    assert ignorar.read_text(encoding="utf-8").split().count(ARQUIVO) == 1
    travar(p, 8765).close()  # e não repete
    assert ignorar.read_text(encoding="utf-8").split().count(ARQUIVO) == 1


def test_o_painel_do_notebook_tambem_trava_o_projeto(tmp_path):
    import mapa_da_ciencia.api as mapa

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    aberto = mapa.painel(p, porta=8797, colab=False)
    try:
        with pytest.raises(PainelJaAberto, match="8797"):
            travar(p, 8798)
    finally:
        aberto.parar()
    travar(p, 8799).close()  # parado o painel, o projeto abre de novo


def test_o_painel_do_notebook_descartado_continua_travando(tmp_path):
    """Sem referência ao `Painel` (a célula que o abriu foi reexecutada), o servidor segue no ar, e a trava também."""
    import mapa_da_ciencia.api as mapa

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    aberto = mapa.painel(p, porta=8796, colab=False)
    servidor = aberto._servidor
    del aberto
    gc.collect()
    try:
        with pytest.raises(PainelJaAberto, match="8796"):
            travar(p, 8795)
    finally:
        servidor.should_exit = True
    for _ in range(200):  # a thread solta a trava ao sair
        try:
            travar(p, 8794).close()
            break
        except PainelJaAberto:
            time.sleep(0.05)
    else:
        pytest.fail("a trava não foi solta depois que o servidor saiu")


def test_o_painel_que_nao_sobe_solta_a_trava(tmp_path, monkeypatch):
    import mapa_da_ciencia.api as mapa
    from mapa_da_ciencia.servidor import app as modulo_app

    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])

    def falha(**_):
        raise RuntimeError("falhou ao montar")

    monkeypatch.setattr(modulo_app, "criar_app", falha)
    with pytest.raises(RuntimeError, match="falhou ao montar"):
        mapa.painel(p, porta=8793, colab=False)
    travar(p, 8793).close()  # o projeto não ficou preso


def _app_com_eventos_sem_fim(**_):
    """Um app com uma rota de eventos que nunca termina, como a da página que acompanha uma etapa."""
    import asyncio

    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    app = FastAPI()

    @app.get("/eventos")
    async def eventos():
        async def fluxo():
            while True:
                yield ": batimento\n\n"
                await asyncio.sleep(0.1)

        return StreamingResponse(fluxo(), media_type="text/event-stream")

    return app


def test_parar_nao_espera_uma_conexao_que_nao_termina(tmp_path, monkeypatch):
    import socket

    import mapa_da_ciencia.api as mapa
    from mapa_da_ciencia.servidor import app as modulo_app

    monkeypatch.setattr(modulo_app, "criar_app", _app_com_eventos_sem_fim)
    p = Projeto.criar(tmp_path / "p", modelo="vazio", perfil=PERFIS["leve"])
    aberto = mapa.painel(p, porta=8792, colab=False)
    conexao = socket.create_connection(("127.0.0.1", 8792))
    try:
        conexao.sendall(b"GET /eventos HTTP/1.1\r\nHost: 127.0.0.1:8792\r\n\r\n")
        assert conexao.recv(64)  # a resposta começou, e não termina
        inicio = time.monotonic()
        aberto.parar()
        assert time.monotonic() - inicio < 5
        travar(p, 8791).close()  # a trava já foi solta
    finally:
        conexao.close()
